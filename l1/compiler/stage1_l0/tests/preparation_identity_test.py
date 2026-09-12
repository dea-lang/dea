#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native identities, compiler adapters, runtime policy and conservative reuse."""

from __future__ import annotations

from contextlib import chdir
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from preparation_support_test import Service, build_library, L1_ROOT
from compiler_filesystem_support_test import resolve_c_compiler
from l1c_stage1_compile_only_test import stage1_compiler


def identity(library: Path, config: dict, *, eligible: bool = True) -> tuple[str, str, dict, dict]:
    """Resolve an identity and inspect its reuse decision and operation counts."""
    with Service(library, config) as service:
        service.require("resolve")
        assert bool(service.get("ineligible")) != eligible, service.get("ineligible")
        value = service.get("native_identity")
        assert service.get("native_key") == hashlib.sha256(value.encode()).hexdigest()
        return service.get("dea_key"), service.get("native_key"), json.loads(value), service.stats()



def check_header_dependencies(library: Path, root: Path, config: dict) -> None:
    """Invalidate generated-C header branches and insertion ahead of a selected header."""
    headers = root / "conditional-headers"
    shutil.copytree(Path(config["build_dir"]) / "include", headers)
    header = headers / "dea_rt.h"
    original = header.read_text()
    conditions = (("DEA_RT_UNCHECKED", {"unchecked": 1}),
                  ("DEA_RT_CHECK_BASIC", {"check_basic": 1}),
                  ("DEA_USE_SYS_REAL", {}), ("!defined(DEA_USE_SYS_REAL)", {}))
    for index, (condition, codegen) in enumerate(conditions):
        child = headers / f"branch_{index}.h"
        child.write_text("#define IDENTITY_BRANCH_VALUE 1\n")
        expression = condition if condition.startswith("!") else "defined(" + condition + ")"
        header.write_text(f'#if {expression}\n#include "{child.name}"\n#endif\n' + original)
        selected = {**config, "runtime_include": str(headers), "codegen": codegen}
        before = identity(library, selected)
        assert str(child) in before[2]["toolchain"]["components"]
        child.write_text("#define IDENTITY_BRANCH_VALUE 2\n")
        assert identity(library, selected)[1] != before[1]
    # The generated float prelude selects <float.h>, independently of runtime C.
    float_header = headers / "float.h"
    float_header.write_text("#include_next <float.h>\n")
    selected = {**config, "options": ["-std=c99", "-I" + str(headers)]}
    before = identity(library, selected)
    assert str(float_header) in before[2]["toolchain"]["components"]
    float_header.write_text("#include_next <float.h>\n#define EXTRA_FLOAT_HEADER 1\n")
    assert identity(library, selected)[1] != before[1]
    # An absent earlier candidate is a dependency too, even if the directory existed.
    earlier = root / "earlier-headers"
    earlier.mkdir()
    selected = {**config, "options": ["-std=c99", "-I" + str(earlier), "-I" + str(headers)]}
    before = identity(library, selected)
    (earlier / "float.h").write_text("#include_next <float.h>\n#define SHADOW_FLOAT_HEADER 1\n")
    after = identity(library, selected)
    assert before[1] != after[1] and str(earlier / "float.h") in after[2]["toolchain"]["components"]


def check_executable_dependencies(library: Path, root: Path, config: dict) -> None:
    """Replace controlled native driver/archiver binaries and fail a previously warm probe."""
    # A compiled test driver exposes deterministic changes without modifying host tools.
    # Its normal command path delegates to the real compiler so adapter queries are real.
    if os.name == "nt":
        return  # POSIX exec fixture; Windows adapter/inventory checks run in the main test.
    compiler = config["compiler"]
    ar_result = subprocess.run([compiler, "-print-prog-name=ar"], capture_output=True, text=True, check=True)
    archiver = shutil.which(ar_result.stdout.strip())
    assert archiver
    native_cc, native_ar = root / "test-native-cc", root / "test-native-ar"
    marker = root / "fail-config-observation"
    source = root / "native-driver.c"

    def compile_driver(destination: Path, delegate: str, revision: int, compiler_driver: bool) -> None:
        """Build a native fixture whose content and probe behavior are independently controlled."""
        source.write_text("#include <stdio.h>\n#include <string.h>\n#include <unistd.h>\n" +
            "int main(int argc, char **argv) {\n" +
            f"if (argc == 99) puts(\"fixture revision {revision}\");\n" +
            (f"for (int i = 1; i < argc; ++i) {{\n"
             f"if (!strcmp(argv[i], \"-print-prog-name=ar\")) {{ puts({json.dumps(str(native_ar))}); return 0; }}\n"
             f"if (!strcmp(argv[i], \"-###\") && access({json.dumps(str(marker))}, F_OK) == 0) return 1;\n}}\n"
             if compiler_driver else "") +
            f"argv[0] = {json.dumps(delegate)}; execv(argv[0], argv); return 127;\n}}\n")
        subprocess.run([compiler, "-std=c99", str(source), "-o", str(destination)], check=True, capture_output=True)

    compile_driver(native_ar, archiver, 1, False)
    compile_driver(native_cc, compiler, 1, True)
    selected = {**config, "compiler": str(native_cc)}
    before = identity(library, selected)
    assert str(native_ar) in before[2]["toolchain"]["components"]
    compile_driver(native_cc, compiler, 2, True)
    after = identity(library, selected)
    assert before[0] == after[0] and before[1] != after[1]
    compile_driver(native_ar, archiver, 2, False)
    assert identity(library, selected)[1] != after[1]
    if before[2]["toolchain"]["family"] == "clang":
        identity(library, selected)  # Establish a warm observation before it becomes unavailable.
        marker.touch()
        identity(library, selected, eligible=False)
        identity(library, {**selected, "force": 1}, eligible=False)
        marker.unlink()
    subordinate = root / "subordinate-tools"
    subordinate.mkdir()
    assembler = shutil.which("as")
    if assembler:
        (subordinate / "as").write_text("#!/bin/sh\nexec " + shlex.quote(assembler) + ' "$@"\n')
        (subordinate / "as").chmod(0o755)
        flags = ("-fno-integrated-as", "-no-integrated-as") if before[2]["toolchain"]["family"] == "clang" else (None,)
        for flag in flags:
            identity(library, {**config, "options": ["-B" + str(subordinate)] + ([flag] if flag else [])}, eligible=False)
    native_ar.write_text("#!/bin/sh\nexec " + shlex.quote(archiver) + ' "$@"\n')
    native_ar.chmod(0o755)
    identity(library, selected, eligible=False)



def check_runtime_compilation(library: Path, config: dict, variant: str, family: str) -> None:
    """Compile actual runtime translation units for every checking/trace and TinyCC path."""
    with Service(library, {**config, "variant": variant}) as service:
        service.require("resolve")
        service.require("private")
        service.require("begin")
        service.require("copy_interfaces")
        entry = Path(service.get("selected"))
        inventory = json.loads(service.get("native_inventory"))
        for relative, role in inventory.items():
            if role == "object":
                (entry / relative).write_bytes(b"opaque native module fixture")
        service.require("runtime")
        service.require("complete")
        runtime = [entry / relative for relative, role in inventory.items() if role == "runtime"]
        count = 10 if variant == "traced" else 9
        assert service.stats()["build_commands"] == count + (family != "tcc")
        assert len(runtime) == (count if family == "tcc" else 1)
        assert all(path.stat().st_size > 0 for path in runtime)
    assert not entry.exists()


def check_implementation_library(library: Path, root: Path, config: dict) -> None:
    """Invalidate an unchanged native driver when its private shared library changes.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration using a real native compiler.
    """
    if os.name == "nt":
        return  # This fixture uses POSIX exec; DLL discovery needs native Windows coverage.
    directory = root / "implementation library"
    directory.mkdir()
    driver, source = directory / "native-driver", directory / "driver.c"
    implementation = directory / ("libfixture.dylib" if sys.platform == "darwin" else "libfixture.so")
    implementation_source = directory / "implementation.c"
    source.write_text('#include <unistd.h>\nextern int fixture_revision(void);\n'
                      'int main(int argc, char **argv) { (void)argc; if (fixture_revision() < 0) return 1;\n'
                      f'argv[0] = {json.dumps(config["compiler"])}; execv(argv[0], argv); return 127; }}\n')

    def build_implementation(revision: int) -> None:
        """Build the dependency without changing the already linked driver."""
        implementation_source.write_text(f"int fixture_revision(void) {{ return {revision}; }}\n")
        command = [config["compiler"], "-shared", "-fPIC", str(implementation_source), "-o", str(implementation)]
        if sys.platform == "darwin":
            command.append("-Wl,-install_name," + str(implementation))
        subprocess.run(command, check=True, capture_output=True)

    build_implementation(1)
    subprocess.run([config["compiler"], str(source), str(implementation), "-Wl,-rpath," + str(directory),
                    "-o", str(driver)], check=True, capture_output=True)
    selected = {**config, "compiler": str(driver)}
    before = identity(library, selected)
    assert str(implementation) in before[2]["toolchain"]["components"]
    driver_bytes = driver.read_bytes()
    warm = identity(library, selected)
    assert warm[:2] == before[:2] and warm[3]["identity_content_reads"] == 0
    build_implementation(2)
    changed = identity(library, selected)
    assert driver.read_bytes() == driver_bytes
    assert changed[0] == before[0] and changed[1] != before[1]


def discovery_digest(discovery: dict) -> str:
    """Hash a discovery fixture using the native canonical JSON control escapes.

    Args:
        discovery: Parsed discovery record with integral JSON numbers.

    Returns:
        The digest expected by the native discovery validator.
    """
    escapes = {"\\b": "\\u0008", "\\f": "\\u000c", "\\n": "\\u000a", "\\r": "\\u000d", "\\t": "\\u0009"}
    canonical = json.dumps(discovery, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    canonical = re.sub(r"\\.", lambda match: escapes.get(match[0], match[0]), canonical)
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_structured_memos(library: Path, config: dict) -> None:
    """Treat parseable but incomplete discovery records as disposable observations.

    Args:
        library: Compiled preparation service.
        config: Isolated preparation configuration with writable memo storage.
    """
    config = {**config, "cache": str(Path(config["cache"]).parent / "structured-memo-cache")}
    initial = identity(library, config)
    # This fixture tests record acceptance. Other tests may legitimately invalidate
    # shared PATH/search directories, so retain only its owned directory observations.
    # Component-file metadata and the resulting native identity remain unchanged.
    owned = (Path(config["home"]), Path(config["build_dir"]))
    for path in Path(config["cache"]).glob("v1/memo/toolchains/*.json"):
        record = json.loads(path.read_text())
        assert "native" not in record and "native_key" not in record
        if "discovery" in record:
            discovery = record["discovery"]
            assert record["discovery_digest"] == discovery_digest(discovery)
            discovery["dependencies"] = {name: metadata for name, metadata in discovery["dependencies"].items()
                                         if any(Path(name).is_relative_to(parent) for parent in owned)}
            assert discovery["dependencies"], "fixture has no owned directory observations"
            record["discovery_digest"] = discovery_digest(discovery)
            path.write_text(json.dumps(record))
    before = identity(library, config)
    assert before[:2] == initial[:2] and before[3]["identity_content_reads"] == 0, (initial[3], before[3])
    for path in Path(config["cache"]).glob("v1/memo/toolchains/*.json"):
        record = json.loads(path.read_text())
        assert "native" not in record and "native_key" not in record
        if "discovery" in record:
            record.update(native={"legacy": "ignored"}, native_key="0" * 64)
            path.write_text(json.dumps(record))
    legacy = identity(library, config)
    assert legacy[:2] == before[:2] and legacy[3]["identity_content_reads"] == 0, (before[3], legacy[3])
    assert legacy[3]["probes"] == before[3]["probes"], (before[3], legacy[3])
    for field, value in (("version", []), ("toolchain", None), ("paths", {})):
        records = []
        for path in Path(config["cache"]).glob("v1/memo/toolchains/*.json"):
            record = json.loads(path.read_text())
            if "discovery" in record:
                records.append(path)
                record["discovery"][field] = value
                record["discovery_digest"] = discovery_digest(record["discovery"])
                path.write_text(json.dumps(record))
        assert records, "fixture did not create a native discovery memo"
        observed = identity(library, config)
        assert observed[:2] == before[:2] and observed[3]["probes"] > before[3]["probes"], (field, before[3], observed[3])


def check_clang_configuration_inputs(library: Path, root: Path, config: dict, compiler: str) -> None:
    """Observe relative includes and encoded option files using Clang as the oracle.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available Clang executable.
    """
    encodings = (("utf-8", b""), ("utf-8-sig", b""),
                 ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff"))
    for encoding, bom in encodings:
        directory = root / ("configuration " + encoding)
        nested = directory / "nested"
        nested.mkdir(parents=True)
        definitions = nested / "definitions.rsp"
        definitions.write_text("-DDEA_CONFIG_CHILD=1 -fPIC\n")
        child = nested / "child.rsp"
        child.write_bytes(bom + " # @ignored.rsp \U0001f680\n@<CFGDIR>/defi\\\nnitions.rsp\n".encode(encoding))
        parent = directory / "parent.cfg"
        parent.write_bytes(bom + "@nested/child.rsp\n".encode(encoding))
        options = ["-std=c99", "--config=" + str(parent)]
        selected = {**config, "compiler": compiler, "options": options}
        before = identity(library, selected)
        for path in (parent, child, definitions):
            assert before[2]["toolchain"]["components"][str(path)] == hashlib.sha256(path.read_bytes()).hexdigest()
        definitions.write_text("-DDEA_CONFIG_CHILD=2 -fPIC\n")
        actual = subprocess.run([compiler, *options, "-dM", "-E", "-x", "c", "-"], input="",
                                check=True, capture_output=True, text=True)
        assert "#define DEA_CONFIG_CHILD 2" in actual.stdout
        changed = identity(library, selected)
        assert changed[0] == before[0] and changed[1] != before[1]
        assert "-fPIC" in changed[2]["runtime"]["options"]
        assert "-DDEA_CONFIG_CHILD=2" not in changed[2]["runtime"]["options"]
        warm = identity(library, selected)
        assert warm[:2] == changed[:2] and warm[3]["identity_content_reads"] == 0
        assert identity(library, {**selected, "force": 1})[:2] == changed[:2]
    direct = root / "encoded-direct.rsp"
    direct.write_bytes(b"\xef\xbb\xbf" + ("@" + shlex.quote(definitions.as_posix()) + "\n").encode())
    selected = {**config, "compiler": compiler, "options": ["@" + str(direct)]}
    assert str(definitions) in identity(library, selected)[2]["toolchain"]["components"]


def check_implicit_clang_configuration(library: Path, root: Path, config: dict, compiler: str) -> None:
    """Observe creation and editing of implicitly selected Clang configuration.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available Clang executable.
    """
    directory = root / "implicit configuration"
    directory.mkdir()
    selector = root / "implicit-selection.rsp"
    selector.write_text(shlex.quote("--config-system-dir=" + directory.as_posix()))
    selected = {**config, "compiler": compiler, "options": ["@" + str(selector)]}
    before = identity(library, selected)
    configuration = directory / "clang.cfg"
    configuration.write_text("-DDEA_IMPLICIT_CONFIG=1 -fPIC\n")
    created = identity(library, selected)
    assert created[0] == before[0] and created[1] != before[1]
    assert str(configuration) in created[2]["toolchain"]["components"]
    configuration.write_text("-DDEA_IMPLICIT_CONFIG=2 -fPIC\n")
    changed = identity(library, selected)
    assert changed[1] != created[1] and "-fPIC" in changed[2]["runtime"]["options"]
    assert identity(library, selected)[:2] == changed[:2]


def check_sdk_configuration(library: Path, root: Path, config: dict) -> None:
    """Observe selected SDK metadata without writing to the installed SDK.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
    """
    if sys.platform != "darwin":
        return
    compiler = subprocess.check_output(["/usr/bin/xcrun", "--find", "clang"], text=True).strip()
    actual_sdk = Path(subprocess.check_output(["/usr/bin/xcrun", "--show-sdk-path"], text=True).strip())
    sdk = root / "selected SDK.sdk"
    sdk.mkdir()
    for child in actual_sdk.iterdir():
        if child.name in ("SDKSettings.json", "SDKSettings.plist"):
            shutil.copy2(child, sdk / child.name)
        else:
            (sdk / child.name).symlink_to(child, target_is_directory=child.is_dir())
    metadata = sdk / "SDKSettings.json"
    original = metadata.read_bytes()
    changed_bytes = json.dumps({**json.loads(original), "DeaFixtureRevision": 1}).encode()
    response = root / "sdk-selection.rsp"
    response.write_text("-isysroot " + shlex.quote(sdk.as_posix()))
    for indirect in (False, True):
        metadata.write_bytes(original)
        selected = {**config, "compiler": compiler, "options": ["@" + str(response)] if indirect else []}
        with patch.dict(os.environ, {"SDKROOT": str(actual_sdk if indirect else sdk)}):
            before = identity(library, selected)
            metadata.write_bytes(changed_bytes)
            changed = identity(library, selected)
            assert changed[0] == before[0] and changed[1] != before[1]
            assert changed[2]["toolchain"]["components"][str(metadata)] == hashlib.sha256(changed_bytes).hexdigest()
            metadata.unlink()
            assert identity(library, selected)[1] != changed[1]
            metadata.write_bytes(changed_bytes)
            assert identity(library, selected)[:2] == changed[:2]


def check_option_file_reuse(library: Path, root: Path, config: dict, compiler: str, *,
                            configuration_files: bool = True) -> None:
    """Reuse command-local parsing without changing ordered options or input limits.

    Args:
        library: Compiled preparation service with option-work counters.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available native compiler supporting response files.
        configuration_files: Whether modern Clang configuration behavior is available.
    """
    directory = root / "option reuse"
    directory.mkdir()
    leaf, parent = directory / "leaf.rsp", directory / "parent.rsp"
    leaf.write_text("-fPIC\n")
    reference = "@" + shlex.quote(leaf.as_posix())
    parent.write_text(reference + " -fno-pic " + reference)
    selected = {**config, "compiler": compiler, "options": ["@" + str(parent), "@" + str(leaf)]}
    before = identity(library, selected)
    assert before[2]["stdlib"]["options"] == selected["options"]
    flags = {"-fPIC", "-fpic", "-fno-pic"}
    assert [word for word in before[2]["runtime"]["options"] if word in flags] == [
        "-fPIC", "-fno-pic", "-fPIC", "-fPIC"]
    assert before[3]["option_file_parses"] == 2 and before[3]["option_root_expansions"] == 1
    warm = identity(library, selected)
    assert warm[:2] == before[:2] and warm[3]["identity_content_reads"] == 0
    assert warm[3]["option_file_parses"] == 2 and warm[3]["option_root_expansions"] == 1
    if configuration_files:
        assert warm[3]["probes"] > 0, "command-local reuse must preserve fresh Clang configuration observation"
    leaf.write_text("-fpic\n")
    changed = identity(library, selected)
    assert changed[0] == before[0] and changed[1] != before[1]
    assert [word for word in changed[2]["runtime"]["options"] if word in flags] == [
        "-fpic", "-fno-pic", "-fpic", "-fpic"]
    leaf.unlink()
    with Service(library, selected) as removed:
        assert removed.call("resolve") == 0 and removed.call("error_code") == 2154
    leaf.write_text("-fPIC\n")
    assert identity(library, selected)[:2] == before[:2]
    # An already parsed shallow leaf must still count toward a deeper occurrence's limit.
    chain = []
    for index in range(16):
        path = directory / f"depth-{index}.rsp"
        child = chain[-1] if chain else leaf
        path.write_text("@" + shlex.quote(child.as_posix()))
        chain.append(path)
    bounded = {**selected, "options": ["@" + str(leaf), "@" + str(chain[-2])]}
    valid = identity(library, bounded)
    assert valid[3]["option_file_parses"] == 16 and valid[3]["option_root_expansions"] == 1
    with Service(library, {**bounded, "options": ["@" + str(leaf), "@" + str(chain[-1])]}) as too_deep:
        assert too_deep.call("resolve") == 0 and too_deep.call("error_code") == 2154
        assert "depth" in too_deep.get("error")
    cycle = directory / "cycle.rsp"
    cycle.write_text("@" + shlex.quote(cycle.as_posix()))
    with Service(library, {**selected, "options": ["@" + str(cycle)]}) as cyclic:
        assert cyclic.call("resolve") == 0 and cyclic.call("error_code") == 2154
        assert "depth" in cyclic.get("error") and cyclic.stats()["option_file_parses"] == 1
    boundary = directory / "size-boundary.rsp"
    boundary.write_bytes(b" " * (1024 * 1024 - 6) + b"-fPIC\n")
    sized = {**selected, "options": ["@" + str(boundary)]}
    assert identity(library, sized)[3]["option_file_parses"] == 1
    with boundary.open("ab") as output:
        output.write(b" ")
    with Service(library, sized) as oversized:
        assert oversized.call("resolve") == 0 and oversized.call("error_code") == 2154
        assert "compiler option file" in oversized.get("error")
    for malformed in (b"\xff\xfe\x00", b"-DVALUE=1\x00-fPIC", b"\xff\xfe\x00\xd8", b"'-fPIC"):
        boundary.write_bytes(malformed)
        with Service(library, sized) as invalid:
            assert invalid.call("resolve") == 0 and invalid.call("error_code") == 2154
            assert "compiler option file" in invalid.get("error")
    leaf.write_text("-fPIC -flto\n")
    identity(library, selected, eligible=False)
    identity(library, {**selected, "force": 1}, eligible=False)
    leaf.write_text("-fPIC\n")
    if not configuration_files:
        return
    # The same lexical file used as a response and as a configuration child has
    # separate syntax contexts, each shared by all subsequent consumers.
    configuration = directory / "native.cfg"
    configuration.write_text("@<CFGDIR>/leaf.rsp\n")
    mixed = {**selected, "options": ["--config=" + str(configuration), "@" + str(leaf)]}
    observed = identity(library, mixed)
    assert observed[3]["option_file_parses"] == 3 and observed[3]["option_root_expansions"] == 2
    selector = directory / "config-selection.rsp"
    selector.write_text(shlex.quote("--config=" + configuration.as_posix()))
    indirect = {**selected, "options": ["@" + str(selector), "@" + str(leaf)]}
    observed = identity(library, indirect)
    assert observed[3]["option_file_parses"] == 4 and observed[3]["option_root_expansions"] == 2
    leaf.write_text("-fPIC -flto\n")
    identity(library, indirect, eligible=False)
    identity(library, {**indirect, "force": 1}, eligible=False)
    leaf.write_text("-fPIC\n")


def check_option_file_spelling(library: Path, root: Path, config: dict, compiler: str, *,
                               configuration_files: bool = True) -> None:
    """Preserve quoted empty operands and host-specific relative filename syntax.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available native compiler supporting response files.
        configuration_files: Whether modern Clang configuration behavior is available.
    """
    directory = root / "option spelling"
    directory.mkdir()
    response = directory / "empty-operand.rsp"
    response.write_text("-B '' -fPIC\n")
    selected = {**config, "compiler": compiler, "options": ["@" + str(response)]}
    with Service(library, selected) as observed:
        observed.require("resolve")
        options = json.loads(observed.get("native_identity"))["runtime"]["options"]
        assert options[options.index("-B"):options.index("-B") + 3] == ["-B", "", "-fPIC"]
    if configuration_files and os.name != "nt":
        child = directory / "x:child.rsp"
        child.write_text("-fPIC\n")
        configuration = directory / "colon.cfg"
        configuration.write_text("@x:child.rsp\n")
        selected["options"] = ["--config=" + str(configuration)]
        observed = identity(library, selected)
        assert str(child) in observed[2]["toolchain"]["components"]
        assert "-fPIC" in observed[2]["runtime"]["options"]


def check_option_expansion_boundaries(library: Path, root: Path, config: dict, compiler: str, *,
                                     configuration_files: bool = True) -> None:
    """Keep paired operands, relative bases, and repeated configuration occurrences intact.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available native compiler supporting response files.
        configuration_files: Whether modern Clang configuration behavior is available.
    """
    directory = root / "option boundaries"
    directory.mkdir()
    response = directory / "paired.rsp"
    pairs = [("-B", directory.as_posix())]
    if configuration_files:
        target = subprocess.check_output([compiler, "-dumpmachine"], text=True).strip()
        pairs.append(("-target", target))
    for flag, value in pairs:
        for option_in_file in (False, True):
            response.write_text(flag if option_in_file else shlex.quote(value))
            options = ["@" + str(response), value] if option_in_file else [flag, "@" + str(response)]
            selected = {**config, "compiler": compiler, "options": options}
            observed = identity(library, selected)
            runtime = observed[2]["runtime"]["options"]
            assert runtime[runtime.index(flag):runtime.index(flag) + 2] == [flag, value]
        response.write_text(flag)
        with Service(library, {**selected, "options": ["@" + str(response)]}) as missing:
            assert missing.call("resolve") == 0 and missing.call("error_code") == 2154
    invocation, including = directory / "invocation", directory / "including"
    invocation.mkdir()
    including.mkdir()
    direct_child, config_child = invocation / "same.rsp", including / "same.rsp"
    direct_child.write_text("-fPIC\n")
    config_child.write_text("-fpic\n")
    direct, configuration = including / "direct.rsp", including / "selected.cfg"
    direct.write_text("@same.rsp\n")
    configuration.write_text("@same.rsp\n")
    selected = {**config, "compiler": compiler, "options": ["@" + str(direct)]}
    with chdir(invocation):
        observed = identity(library, selected)
        assert str(direct_child) in observed[2]["toolchain"]["components"]
        assert str(config_child) not in observed[2]["toolchain"]["components"]
    if not configuration_files:
        return
    selected["options"].append("--config=" + str(configuration))
    with chdir(invocation):
        observed = identity(library, selected)
        components = observed[2]["toolchain"]["components"]
        assert str(direct_child) in components and str(config_child) in components
        assert [word for word in observed[2]["runtime"]["options"] if word in ("-fPIC", "-fpic")] == [
            "-fpic", "-fPIC"]
        for path in (configuration, config_child):
            original = path.read_bytes()
            path.write_bytes(b"\xff\xfe\x00")
            with Service(library, selected) as malformed:
                assert malformed.call("resolve") == 0 and malformed.call("error_code") == 2154
            path.write_bytes(original)
    first, second = directory / "first.cfg", directory / "second.cfg"
    first.write_text("-fPIC\n")
    second.write_text("-fno-pic\n")
    selected["options"] = ["--config=" + str(path) for path in (first, second, first)]
    observed = identity(library, selected)
    assert [word for word in observed[2]["runtime"]["options"] if word in ("-fPIC", "-fno-pic")] == [
        "-fPIC", "-fno-pic", "-fPIC"]
    assert observed[3]["option_file_parses"] == 2 and observed[3]["option_root_expansions"] == 3


def check_clang_configuration_support(library: Path, root: Path, config: dict, compiler: str) -> bool:
    """Verify the existing refusal when Clang cannot disable default configuration.

    Args:
        library: Compiled preparation service.
        root: Owned temporary fixture directory.
        config: Isolated preparation configuration.
        compiler: Available Clang executable.

    Returns:
        Whether the successful modern Clang configuration cases can run.
    """
    probe = subprocess.run([compiler, "--no-default-config", "-print-prog-name=ar"],
                           capture_output=True, text=True)
    if probe.returncode == 0:
        return True
    assert "unsupported option" in probe.stderr and "--no-default-config" in probe.stderr, probe.stderr
    configuration = root / "unsupported-clang.cfg"
    configuration.write_text("-fPIC\n")
    for force in (0, 1):
        selected = {**config, "compiler": compiler, "force": force}
        with Service(library, selected) as plain:
            assert plain.call("resolve") == 0 and plain.call("error_code") == 2154
            assert "selected compiler must locate a usable runtime archiver" in plain.get("error")
        with Service(library, {**selected, "options": ["--config=" + str(configuration)]}) as configured:
            configured.require("resolve")
            reason = configured.get("ineligible")
            assert "effective configuration target options" in reason and "unsupported option '--config=" in reason
    print("Clang lacks --no-default-config: existing plain failure and config reuse refusal verified; "
          "modern Clang configuration cases unavailable")
    return False


def main() -> int:
    """Exercise effective input/option invalidation without rebuilding native fixtures."""
    with tempfile.TemporaryDirectory(prefix="l1-native-identity-") as directory:
        root = Path(directory).resolve()
        library = build_library(root)
        home, build = root / "compiler", root / "build"
        shutil.copytree(L1_ROOT / "compiler/shared", home / "shared")
        (home / "stage1_l0/src").mkdir(parents=True)
        (home / "stage1_l0/support").mkdir()
        implementation = home / "stage1_l0/src/implementation.l0"
        implementation.write_text("implementation fixture")
        executable = root / "l1c"
        executable.write_text("executable fixture")
        for name in ("include", "interfaces"):
            shutil.copytree(stage1_compiler().parent.parent / name, build / name)
        config = dict(home=str(home), self=str(executable), build_dir=str(build), cache=str(root / "cache"),
                      compiler=resolve_c_compiler(), options=["-std=c99"])
        env = dict(os.environ)
        for name in ("L1_STDLIB_CACHE", "L1_CFLAGS", "L1_RUNTIME_CC", "RUNTIME_CFLAGS", "AR"):
            env.pop(name, None)
        with patch.dict(os.environ, env, clear=True):
            plain = identity(library, config)
            warm = identity(library, config)
            assert warm[:2] == plain[:2] and warm[3]["identity_content_reads"] == 0
            assert warm[3]["probes"] <= 4
            forced = identity(library, {**config, "force": 1})
            assert forced[:2] == plain[:2] and forced[3]["identity_content_reads"] > 0
            for path in (executable, implementation, home / "shared/l1/stdlib/std/io.l1",
                         home / "shared/runtime/src/dea_rt_io.c", home / "shared/runtime/include/dea_rt.h"):
                original = path.read_bytes()
                path.write_bytes(original + b"\n/* changed working input */\n")
                changed = identity(library, config)
                assert changed[0] != plain[0] and changed[1] != plain[1], path
                assert changed[3]["probes"] > 4, "new D must re-observe toolchain eligibility"
                path.write_bytes(original)
            for variant in ("default", "traced", "unchecked", "check_basic"):
                check_runtime_compilation(library, config, variant, plain[2]["toolchain"]["family"])
            for variant in ("traced", "unchecked", "check_basic"):
                changed = identity(library, {**config, "variant": variant})
                assert changed[0] == plain[0] and changed[1] != plain[1]
                assert changed[2]["runtime"]["variant"] == variant
            configured = identity(library, {**config, "options": ["-O0", "-DAPP_ONLY=1", "-std=c11", "-fPIC"]})
            runtime = configured[2]["runtime"]["options"]
            assert runtime[:2] == ["-O2", "-std=c99"] and "-fPIC" in runtime
            assert not {"-O0", "-DAPP_ONLY=1", "-std=c11"}.intersection(runtime)
            assert "-D_RT_QUARANTINE_MAX_BYTES=16777216" in runtime and "-D_RT_QUARANTINE_MAX_COUNT=4096" in runtime
            with patch.dict(os.environ, {"L1_RUNTIME_CC": "missing", "RUNTIME_CFLAGS": "invalid", "AR": "missing",
                                         "L1_RT_QUARANTINE_MAX_BYTES": "1", "L1_RT_QUARANTINE_MAX_COUNT": "1",
                                         "DEA_RT_QUARANTINE_MAX_BYTES": "2", "DEA_RT_QUARANTINE_MAX_COUNT": "2"}):
                assert identity(library, config)[:2] == plain[:2]
            headers = root / "headers"
            shutil.copytree(build / "include", headers)
            overridden = {**config, "runtime_include": str(headers)}
            initial = identity(library, overridden)
            (headers / "dea_rt.h").write_bytes((headers / "dea_rt.h").read_bytes() + b"\n/* override changed */\n")
            changed = identity(library, overridden)
            assert initial[0] == changed[0] == plain[0] and initial[1] != changed[1]
            assert identity(library, {**config, "runtime_lib": "other", "output": "elsewhere", "project_root": "app"})[:2] == plain[:2]
            for memo in (root / "cache/v1/memo/toolchains").glob("*.json"):
                memo.write_text("{")
            fresh = identity(library, config)
            assert fresh[:2] == plain[:2] and fresh[3]["probes"] > 4 and fresh[3]["identity_content_reads"] > 0
            response = root / "options.rsp"
            response.write_text("-DRESPONSE_VALUE=1 -fPIC")
            selected = {**config, "options": ["-std=c99", "@" + str(response)]}
            initial = identity(library, selected)
            response.write_text("-DRESPONSE_VALUE=2 -fPIC")
            changed = identity(library, selected)
            assert initial[0] == changed[0] and initial[1] != changed[1]
            assert "-fPIC" in changed[2]["runtime"]["options"]
            if os.name != "nt":
                wrapper = root / "opaque-cc"
                wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(config["compiler"]) + ' "$@"\n')
                wrapper.chmod(0o755)
                identity(library, {**config, "compiler": str(wrapper)}, eligible=False)
                identity(library, {**config, "compiler": str(wrapper), "force": 1}, eligible=False)
            identity(library, {**config, "options": ["-std=c99", "-flto"]}, eligible=False)
            clang = shutil.which("clang")
            clang_configuration = bool(clang and check_clang_configuration_support(library, root, config, clang))
            compilers = {str(Path(path).resolve()) for name in ("gcc", "clang", "tcc") if (path := shutil.which(name))}
            for compiler in sorted(compilers):
                if clang and compiler == str(Path(clang).resolve()) and not clang_configuration:
                    continue  # The unavailable adapter's exact failure was asserted above.
                observed = identity(library, {**config, "compiler": compiler})
                assert observed[2]["toolchain"]["family"] in ("gcc", "clang", "tcc")
                if observed[2]["toolchain"]["family"] == "tcc":
                    check_runtime_compilation(library, {**config, "compiler": compiler}, "traced", "tcc")
                    with Service(library, {**config, "compiler": compiler, "variant": "traced"}) as tcc:
                        tcc.require("resolve")
                        inventory = json.loads(tcc.get("native_inventory"))
                        assert sum(role == "runtime" for role in inventory.values()) == 10
                        assert not any(path.endswith(".a") for path in inventory)
            check_header_dependencies(library, root, config)
            check_executable_dependencies(library, root, config)
            check_implementation_library(library, root, config)
            check_structured_memos(library, config)
            check_sdk_configuration(library, root, config)
            if clang_configuration:
                check_clang_configuration_inputs(library, root, config, clang)
                check_implicit_clang_configuration(library, root, config, clang)
            option_compiler = clang if clang_configuration else config["compiler"]
            check_option_file_reuse(library, root, config, option_compiler, configuration_files=clang_configuration)
            check_option_file_spelling(library, root, config, option_compiler, configuration_files=clang_configuration)
            check_option_expansion_boundaries(library, root, config, option_compiler,
                                              configuration_files=clang_configuration)
    print("native identity, runtime policy, adapters and memo invalidation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
