#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Validate explicit-profile schema, integrity, configuration and publication ownership."""

from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
from contextlib import chdir
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from compiler_filesystem_support_test import resolve_c_compiler
from preparation_construction_test import native_write
from preparation_support_test import SUPPORT, Service, compile_native


CODEGEN = dict(no_line_directives=0, trace_arc=0, trace_memory=0, unchecked=0, check_basic=0)


def build_windows_macro_library(root: Path) -> Path:
    """Compile complete native support with the Windows COM macro visible on every host.

    Args:
        root: Owned directory for the native service library.

    Returns:
        Library used by the profile schema, selection and creation checks.
    """
    library = root / ("preparation.dll" if os.name == "nt" else "preparation.so")
    flags = ("-shared",) if os.name == "nt" else ("-shared", "-fPIC")
    compile_native(library, [SUPPORT / "preparation_support.c", SUPPORT / "compiler_support.c"],
                   (*flags, "-Dinterface=struct"))
    return library


class ProfileService(Service):
    """Reuse the native test adapter's lifetime rules for public profile contexts."""

    def __init__(self, library: Path, path: Path | bytes, config: dict | None = None):
        """Open one load or construction context, with independent DLL ownership.

        Args:
            library: Compiled native service library.
            path: Selected root or new output directory, optionally a raw byte span.
            config: Construction configuration; omitted for read-only selection.

        Raises:
            OSError: If the service library cannot be loaded.
        """
        super().__init__(library, b"{")
        try:
            self.lib.l1c_profile_load.argtypes = [ctypes.c_char_p, ctypes.c_int]
            self.lib.l1c_profile_load.restype = ctypes.c_void_p
            self.lib.l1c_profile_create.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                                   ctypes.c_char_p, ctypes.c_int]
            self.lib.l1c_profile_create.restype = ctypes.c_void_p
            self.lib.l1c_profile_publish.argtypes = [ctypes.c_void_p]
            self.lib.l1c_profile_verify.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.lib.l1c_profile_match.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            self.lib.l1c_prep_compile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            self.lib.l1c_prep_free(self.context)
            self.context = None
            encoded = path if isinstance(path, bytes) else os.fsencode(path)
            if config is None:
                self.context = self.lib.l1c_profile_load(encoded, len(encoded))
            else:
                data = json.dumps(config).encode()
                self.context = self.lib.l1c_profile_create(data, len(data), encoded, len(encoded))
        except BaseException:
            self.close()
            raise

    def verify(self, native: bool) -> int:
        """Validate the bytes required by compile-only or native linking.

        Args:
            native: Include object and runtime bytes when true.

        Returns:
            Native success indicator.
        """
        return self._open_library().l1c_profile_verify(self.context, int(native))

    def match(self, supplied: dict) -> int:
        """Compare explicit settings without probing another compiler.

        Args:
            supplied: Only the explicitly supplied native/codegen settings.

        Returns:
            Native success indicator.
        """
        data = json.dumps(supplied).encode()
        return self._open_library().l1c_profile_match(self.context, data, len(data))

    def publish(self) -> int:
        """Complete and publish this constructor's new destination.

        Returns:
            Native success indicator.
        """
        return self._open_library().l1c_profile_publish(self.context)


def fixture(root: Path) -> dict:
    """Create opaque trusted payloads to isolate format checks from semantic verification.

    Args:
        root: New owned fixture directory.

    Returns:
        Complete public manifest whose compiler intentionally does not exist.
    """
    root.mkdir()
    roles = {"modules/std/types.l1m": "interface", "modules/std/types.o": "object",
             "lib/libdea_rt.a": "runtime", "include/dea_rt.h": "header", "include/l1_real.h": "header"}
    payloads = []
    for relative, role in roles.items():
        payload = root / relative
        payload.parent.mkdir(parents=True, exist_ok=True)
        data = ("trusted opaque fixture: " + relative).encode()
        payload.write_bytes(data)
        payloads.append(dict(path=relative, role=role, size=len(data), sha256=hashlib.sha256(data).hexdigest()))
    manifest = dict(schema=1, kind="l1-explicit-profile", contract=1,
                    producer=dict(name="l1c", language="L1"),
                    configuration=dict(compiler=str(root.parent / "absent toolchain/compiler"), family="gcc",
                                       options=["-std=c99"], runtime_options=["-O2", "-std=c99"],
                                       runtime_configuration_isolation="none", variant="default", codegen=dict(CODEGEN)),
                    include="include", modules={"std.types": "modules/std/types.l1m"},
                    runtime=["lib/libdea_rt.a"], payloads=payloads)
    write_manifest(root, manifest)
    return manifest


def write_manifest(root: Path, manifest: dict) -> None:
    """Write exact fixture metadata after a deliberate mutation.

    Args:
        root: Existing profile fixture.
        manifest: Public manifest data.
    """
    (root / "profile.json").write_text(json.dumps(manifest), encoding="utf-8")


def reject(library: Path, root: Path, expected: int) -> None:
    """Require a specific public diagnostic from exact selection.

    Args:
        library: Compiled native service.
        root: Invalid selected artifact.
        expected: Numeric diagnostic code without the compiler prefix.
    """
    with ProfileService(library, root) as service:
        assert service.call("error_code") == expected, (root.name, service.call("error_code"), service.get("error"))
        assert service.get("error"), root
        assert service.stats()["probes"] == service.stats()["native_resolutions"] == 0


def check_manifest(library: Path, root: Path) -> None:
    """Reject malformed, unbounded, unknown and inconsistent public metadata.

    Args:
        library: Compiled native service.
        root: Owned directory for independent mutations.
    """
    mutations = {
        "schema": (lambda m: m.update(schema=2), 2182),
        "contract": (lambda m: m.update(contract=2), 2184),
        "kind": (lambda m: m.update(kind="managed-cache-entry"), 2182),
        "unknown-field": (lambda m: m.update(cache_key="not consumption authority"), 2182),
        "missing-producer": (lambda m: m.pop("producer"), 2182),
        "invalid-producer": (lambda m: m["producer"].update(language="L0"), 2182),
        "relative-compiler": (lambda m: m["configuration"].update(compiler="clang"), 2182),
        "unknown-family": (lambda m: m["configuration"].update(family="unknown"), 2182),
        "unknown-runtime": (lambda m: m["configuration"].update(variant="unknown"), 2182),
        "missing-codegen": (lambda m: m["configuration"]["codegen"].pop("trace_arc"), 2182),
        "invalid-codegen": (lambda m: m["configuration"]["codegen"].update(trace_arc=2), 2182),
        "incompatible-codegen": (lambda m: m["configuration"]["codegen"].update(unchecked=1, trace_arc=1), 2182),
        "runtime-codegen-mismatch": (lambda m: m["configuration"]["codegen"].update(check_basic=1), 2182),
        "nonarray-options": (lambda m: m["configuration"].update(options="-std=c99"), 2182),
        "nonstring-options": (lambda m: m["configuration"].update(options=[True]), 2182),
        "too-many-options": (lambda m: m["configuration"].update(options=["-O0"] * 4097), 2182),
        "oversized-option": (lambda m: m["configuration"].update(options=["-D" + "x" * 32768]), 2182),
        "relative-option": (lambda m: m["configuration"].update(options=["-I", "relative headers"]), 2182),
        "response-option": (lambda m: m["configuration"].update(options=["@caller.rsp"]), 2182),
        "response-definition": (lambda m: m["configuration"].update(options=["-D", "@caller.rsp"]), 2182),
        "response-runtime-option": (lambda m: m["configuration"].update(runtime_options=["-D", "@caller.rsp"]), 2182),
        "config-option": (lambda m: m["configuration"].update(runtime_options=["--config=caller.cfg"]), 2182),
        "noncanonical-option": (lambda m: m["configuration"].update(options=["-I" + str(root)]), 2182),
        "invalid-isolation": (lambda m: m["configuration"].update(runtime_configuration_isolation="future"), 2182),
        "empty-modules": (lambda m: m.update(modules={}), 2182),
    }
    for name, (mutate, code) in mutations.items():
        selected = root / name
        manifest = fixture(selected)
        mutate(manifest)
        write_manifest(selected, manifest)
        reject(library, selected, code)
    for name, data in {"malformed": b"{", "duplicate": b'{"schema":1,"schema":1}',
                       "invalid-utf8": b'{"schema":"\xff"}',
                       "oversized": b" " * (16 * 1024 * 1024 + 1)}.items():
        selected = root / name
        selected.mkdir()
        (selected / "profile.json").write_bytes(data)
        reject(library, selected, 2182)
    reject(library, root / "absent", 2182)
    incomplete = root / "incomplete"
    incomplete.mkdir()
    reject(library, incomplete, 2182)


def check_inventory(library: Path, root: Path) -> None:
    """Verify exact paths, roles, completeness, sizes and digests before host tools.

    Args:
        library: Compiled native service.
        root: Owned directory for payload fixtures.
    """
    mutations = {
        "duplicate": lambda m: m["payloads"].append(copy.deepcopy(m["payloads"][0])),
        "missing": lambda m: m["payloads"].pop(),
        "unknown-role": lambda m: m["payloads"][0].update(role="native-command"),
        "wrong-role": lambda m: m["payloads"][0].update(role="object"),
        "negative-size": lambda m: m["payloads"][0].update(size=-1),
        "wrong-size": lambda m: m["payloads"][0].update(size=0),
        "wrong-digest": lambda m: m["payloads"][0].update(sha256="0" * 64),
        "malformed-digest": lambda m: m["payloads"][0].update(sha256="not a digest"),
        "extra-field": lambda m: m["payloads"][0].update(command="do not execute"),
        "module-mapping": lambda m: m.update(modules={"std.types": "modules/std/other.l1m"}),
        "module-name": lambda m: m.update(modules={"../escape": "modules/std/types.l1m"}),
        "runtime-order": lambda m: m.update(runtime=["modules/std/types.o"]),
    }
    for index, invalid_path in enumerate(("../escape", "/absolute", "include/../escape", "include//header.h",
                                          "include/./header.h", "C:/escape", "include\\header.h", "include/line\n.h")):
        mutations[f"invalid-path-{index}"] = lambda m, path=invalid_path: m["payloads"][0].update(path=path)
    for name, mutate in mutations.items():
        selected = root / name
        manifest = fixture(selected)
        mutate(manifest)
        write_manifest(selected, manifest)
        reject(library, selected, 2183)
    undeclared = root / "undeclared-header"
    fixture(undeclared)
    (undeclared / "include/stdint.h").write_text("/* undeclared header must not shadow host headers */")
    reject(library, undeclared, 2183)
    for relative in ("include/dea_rt.h", "modules/std/types.l1m", "modules/std/types.o", "lib/libdea_rt.a"):
        selected = root / ("missing-" + Path(relative).name)
        fixture(selected)
        (selected / relative).unlink()
        reject(library, selected, 2183)
    for relative in ("modules/std/types.o", "lib/libdea_rt.a"):
        selected = root / ("deferred-" + Path(relative).name)
        fixture(selected)
        (selected / relative).write_bytes(b"damaged native bytes")
        with ProfileService(library, selected) as service:
            assert service.call("error_code") == 0, service.get("error")
            assert service.verify(False) == 1, "compile-only need not hash unused native bytes"
            assert service.verify(True) == 0 and service.call("error_code") == 2183
    if os.name != "nt":
        for name, relative in (("file-alias", "include/dea_rt.h"), ("directory-escape", "include")):
            selected = root / name
            fixture(selected)
            external = root / (name + "-external")
            payload = selected / relative
            if payload.is_dir():
                shutil.copytree(payload, external)
                shutil.rmtree(payload)
                payload.symlink_to(external, target_is_directory=True)
            else:
                shutil.copyfile(payload, external)
                payload.unlink()
                payload.symlink_to(external)
            reject(library, selected, 2183)


def check_selection(library: Path, root: Path) -> None:
    """Keep selection read-only, movable and independent of ambient native defaults.

    Args:
        library: Compiled native service.
        root: Owned fixture directory.
    """
    selected = root / "read-only profile"
    manifest = fixture(selected)
    moved = root / "moved profile"
    selected.rename(moved)
    before = {str(path.relative_to(moved)): path.read_bytes() for path in moved.rglob("*") if path.is_file()}
    ignored = root / "must-not-exist"
    with chdir(root), patch.dict(os.environ, L1_CC="missing", L1_CFLAGS="@missing.rsp", L1_SYSTEM="missing",
                                L1_RUNTIME_INCLUDE="missing", L1_RUNTIME_LIB="missing", L1_BUILD_DIR="missing",
                                L1_STDLIB_CACHE=str(ignored)):
        with ProfileService(library, Path("moved profile")) as service:
            assert service.call("error_code") == 0, service.get("error")
            assert service.verify(True) == 1
            assert Path(service.get("selected")) == moved
            assert service.get("compiler") == manifest["configuration"]["compiler"]
            assert all(service.get(field) == "" for field in ("native_key", "dea_key", "local"))
            assert service.match({}) == 1
            assert service.match(dict(compiler="compiler", options=["-std=c99"], codegen=dict(CODEGEN))) == 1
            assert service.stats()["probes"] == service.stats()["native_resolutions"] == 0
    assert not ignored.exists()
    after = {str(path.relative_to(moved)): path.read_bytes() for path in moved.rglob("*") if path.is_file()}
    assert before == after, "selection must not repair payloads or create validation memos"
    for supplied in (dict(compiler="different-compiler"), dict(options=["-O3"]),
                     dict(variant="unchecked"), dict(codegen=dict(trace_arc=1))):
        with ProfileService(library, moved) as service:
            assert service.match(supplied) == 0 and service.call("error_code") == 2184
            assert service.stats()["probes"] == 0, "conflicts must not probe alternate compiler identities"
    headers = root / "external headers"
    headers.mkdir()
    manifest["configuration"]["options"] = ["-I", str(headers)]
    write_manifest(moved, manifest)
    with chdir(root), ProfileService(library, moved) as service:
        assert service.call("error_code") == 0, service.get("error")
        assert service.match(dict(options=["-Iexternal headers"])) == 1, service.get("error")
    with ProfileService(library, moved) as service:
        assert service.match(dict(options=["-I", str(root / "different headers")])) == 0


def creation_config(root: Path) -> dict:
    """Provide one tiny canonical input set for ownership and failure tests.

    Args:
        root: Owned input fixture directory.

    Returns:
        Native profile creation configuration without managed-cache requirements.
    """
    home = root / "compiler"
    for relative, data in {"shared/l1/stdlib/std/types.l1": "module std.types;\n",
                           "interfaces/std/types.l1m": "trusted semantic fixture\n",
                           "include/dea_rt.h": "/* public runtime fixture */\n",
                           "include/l1_real.h": "/* public real fixture */\n"}.items():
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
    (home / "shared/runtime").mkdir()
    compiler = resolve_c_compiler()
    implementation = root / "l1c"
    implementation.write_text("protected compiler fixture")
    return dict(home=str(home), self=str(implementation), compiler=compiler,
                options=["-std=c99"], variant="default", codegen=dict(CODEGEN))


def check_creation(library: Path, root: Path) -> None:
    """Protect caller inputs and clean registered failures while retaining unexpected evidence.

    Args:
        library: Compiled native service.
        root: Owned creation fixture directory.
    """
    config = creation_config(root)
    existing = root / "existing"
    existing.mkdir()
    sentinel = existing / "caller-owned"
    sentinel.write_text("retain caller bytes")
    outputs = [existing, Path(config["home"]) / "new", Path(config["home"]) / "interfaces/new",
               Path(config["home"]) / "include/new", Path(config["self"]), Path(config["compiler"])]
    if os.name != "nt":
        alias = root / "protected-alias"
        alias.symlink_to(config["home"], target_is_directory=True)
        outputs.append(alias / "new")
    for output in outputs:
        with ProfileService(library, output, config) as service:
            assert service.call("error_code") == 2181, (output, service.get("error"))
            assert service.get("profile_stage") == ""
    assert sentinel.read_text() == "retain caller bytes"
    external = root / "external headers"
    external.mkdir()
    with ProfileService(library, external / "profile", {
            **config, "options": ["-I", str(external)]}) as service:
        assert service.call("error_code") == 2181, service.get("error")
        assert service.get("profile_stage") == ""
    assert list(external.iterdir()) == []
    for raw in (b"", b"output\x00suffix"):
        with ProfileService(library, raw, config) as service:
            assert service.call("error_code") == 2181, service.get("error")
            assert service.get("profile_stage") == ""
    with ProfileService(library, root / "incompatible-codegen", {
            **config, "codegen": {**CODEGEN, "unchecked": 1, "trace_arc": 1}}) as service:
        assert service.call("error_code") == 2180, service.get("error")
        assert service.get("profile_stage") == ""
    with chdir(root), ProfileService(library, root / "relative-options", {
            **config, "options": ["-Iexternal headers", "-include", "external header.h",
                                  "-D", "PROFILE_VALUE=@literal"]}) as service:
        assert service.call("error_code") == 0, service.get("error")
        stage = Path(service.get("profile_stage"))
        inputs = json.loads(service.get("construction_inputs"))
        expected = ["-I", str(root / "external headers"), "-include", str(root / "external header.h"),
                    "-D", "PROFILE_VALUE=@literal"]
        assert inputs["options"] == expected, inputs["options"]
    assert not stage.exists(), "unpublished normalized-option construction must clean its owned stage"
    response = root / "caller.rsp"
    response.write_text("PROFILE_RESPONSE=1\n")
    for index, flag in enumerate(("-D", "-U", "-target", "--target", "-arch", "-I", "-include")):
        output = root / ("response-operand-" + str(index))
        with ProfileService(library, output, {**config, "options": [flag, "@" + str(response)]}) as service:
            assert service.call("error_code") == 2180, (flag, service.get("error"))
            assert service.get("profile_stage") == ""
            assert service.stats()["probes"] == 0, "response operands must fail before any native work"
        assert not output.exists()
    assert response.read_text() == "PROFILE_RESPONSE=1\n"
    relative = "x/" * 16380 + "x"
    suffix_size = 32760 - len(str(root).encode("utf-8")) - 1
    absolute = str(root) + os.sep + "x/" * (suffix_size // 2) + "x" * (suffix_size % 2)
    assert len(absolute.encode("utf-8")) <= 32768
    assert len(("--gcc-toolchain=" + absolute).encode("utf-8")) > 32768
    for index, options in enumerate((["-I", relative], ["--gcc-toolchain", absolute])):
        output = root / ("oversized-normalized-option-" + str(index))
        with chdir(root), ProfileService(library, output, {**config, "options": options}) as service:
            assert service.call("error_code") == 2180, service.get("error")
            assert service.get("profile_stage") == ""
            assert service.stats()["probes"] == 0, "normalized argv bounds must fail before native work"
        assert not output.exists()
    for index, options in enumerate((["@options.rsp"], ["--config=compiler.cfg"], ["-specs=compiler.specs"],
                                     ["-Xclang", "-load"], ["-Wl,@linker.rsp"], ["-I"], ["--sysroot="],
                                     ["-iprefixrelative"], ["-iframeworkwithsysrootrelative"],
                                     ["-isystemrelative"], ["-include-pch"], ["-include-pchrelative"],
                                     ["-isystem-after", "relative"], ["--sysrootrelative"], ["-I-"],
                                     ["-MFrelative.d"], ["-MJrelative.json"], ["-orelative.o"],
                                     ["-working-directoryrelative"], ["-dumpdirrelative"],
                                     ["-dumpbaserelative"], ["-auxbaserelative"], ["-save-temps"],
                                     ["-I=/relative"], ["-isystem=/relative"], ["-include=relative"],
                                     ["-I$SYSROOT/include"], ["-I", "$SYSROOT/include"],
                                     ["--sysroot=$SYSROOT"])):
        output = root / ("rejected-options-" + str(index))
        with ProfileService(library, output, {**config, "options": options}) as service:
            assert service.call("error_code") == 2180, (options, service.get("error"))
            assert service.get("profile_stage") == ""
        assert not output.exists()
    for name in ("incomplete", "native-failure", "publication-race", "changed-input-directory", "unexpected-evidence"):
        output = root / name
        with ProfileService(library, output, config) as service:
            assert service.call("error_code") == 0, (name, service.get("error"))
            stage = Path(service.get("profile_stage"))
            assert stage.parent == output.parent and stage != output and stage.is_dir()
            if name == "native-failure":
                service.require("copy_interfaces")
                assert native_write(service, "generated/std/types.c", b"#error deliberate profile failure\n") == 1
                assert service.lib.l1c_prep_compile(service.context, b"std.types", 9) == 0
                assert service.call("error_code") == 2156
            elif name in ("publication-race", "changed-input-directory"):
                service.require("copy_interfaces")
                inputs = json.loads(service.get("construction_inputs"))
                native_payloads = ["modules/std/types.o"]
                if inputs["family"] == "tcc":
                    native_payloads.extend("lib/tcc/default/" + name + ".o" for name in (
                        "dea_rt_panic", "dea_rt_sys", "dea_rt_math", "dea_rt_rand", "dea_rt_string",
                        "dea_rt_alloc", "dea_rt_io", "dea_rt_hash", "dea_rt_time"))
                else:
                    native_payloads.append("lib/libdea_rt.a")
                for relative in native_payloads:
                    assert native_write(service, relative, b"trusted opaque native fixture") == 1
                if name == "publication-race":
                    output.mkdir()
                    (output / "caller-owned").write_text("retain racing destination")
                    expected = 2185
                else:
                    added_input = Path(config["home"]) / "shared/runtime/new-header.h"
                    added_input.write_text("/* newly added caller-owned runtime input */")
                    expected = 2151
                assert service.publish() == 0 and service.call("error_code") == expected, service.get("error")
            else:
                if name == "unexpected-evidence":
                    (stage / "caller-owned-evidence").write_text("retain unexpected contents")
                assert service.publish() == 0, "incomplete profile cannot be published"
        if name == "unexpected-evidence":
            assert (stage / "caller-owned-evidence").read_text() == "retain unexpected contents"
            assert not (stage / "profile.json").exists()
        else:
            assert not stage.exists(), (name, stage)
        if name == "publication-race":
            assert (output / "caller-owned").read_text() == "retain racing destination"
        else:
            assert not output.exists(), name


def check_implicit_configuration(library: Path, root: Path) -> None:
    """Refuse selected implicit Clang configuration before staging or cache writes.

    Args:
        library: Compiled native service.
        root: Owned compiler-wrapper and configuration fixture directory.
    """
    if os.name == "nt":
        print("implicit Clang configuration fixture: SKIP (POSIX compiler wrapper)")
        return
    compiler = shutil.which("clang")
    if compiler is None:
        print("implicit Clang configuration fixture: SKIP (Clang unavailable)")
        return
    config = creation_config(root)
    selected = root / "implicit compiler configuration.cfg"
    selected.write_text("-Irelative-header-directory\n")
    wrapper = root / "implicit config-clang"
    wrapper.write_text(
        '#!/bin/sh\nselection=0\nisolated=0\nfor argument in "$@"; do\n'
        '    case "$argument" in\n'
        '        -###) selection=1 ;;\n'
        '        --config|--config=*|--no-default-config) isolated=1 ;;\n'
        '    esac\ndone\n'
        'if [ "$selection" = 1 ] && [ "$isolated" = 0 ]; then\n'
        "    printf '%s\\n' " + shlex.quote("Configuration file: " + str(selected)) + " >&2\n"
        'fi\nexec ' + shlex.quote(compiler) + ' "$@"\n')
    wrapper.chmod(0o755)
    observed = subprocess.run([str(wrapper), "-###", "-x", "c", "-c", os.devnull],
                              capture_output=True, text=True, check=True)
    assert "Configuration file: " + str(selected) in observed.stderr
    output = root / "new profile parent/profile"
    cache = root / "must-not-exist-cache"
    before = {str(path.relative_to(root)) for path in root.rglob("*")}
    with patch.dict(os.environ, L1_STDLIB_CACHE=str(cache)), ProfileService(
            library, output, {**config, "compiler": str(wrapper)}) as service:
        assert service.call("error_code") == 2180, service.get("error")
        assert "implicit compiler configuration" in service.get("error")
        assert str(selected) in service.get("error")
        assert service.get("profile_stage") == ""
        assert service.get("local") == "" and service.stats()["native_resolutions"] == 0
    assert not output.parent.exists() and not cache.exists()
    after = {str(path.relative_to(root)) for path in root.rglob("*")}
    assert before == after, "implicit-configuration rejection must precede profile publication mutations"
    assert selected.read_text() == "-Irelative-header-directory\n"


def check_windows_path_spellings(root: Path) -> None:
    """Compile production Windows lexical helpers on every host, without filesystem claims.

    Args:
        root: Owned source and executable fixture directory.
    """
    platform = (SUPPORT / "preparation/platform.h").read_text()
    profile = (SUPPORT / "preparation/profile.h").read_text()
    separator = platform[platform.index("static int pc_separator("):platform.index("static char *pc_join(")]
    comparisons = platform[platform.index("static int pc_path_equal("):
                           platform.index("/** Resolve aliases through")]
    absolute = profile[profile.index("static int pc_profile_absolute("):profile.index("/** Bound argv")]
    source = root / "windows-profile-paths.c"
    source.write_text(r'''#include <assert.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#define _WIN32 1
#endif
/** Supply allocation only; comparison and absolute-path rules come from production. */
static char *pc_slice(const char *s, size_t n) {
    char *p = calloc(n + 1, 1);
    assert(p);
    memcpy(p, s, n);
    return p;
}
''' + separator + comparisons + absolute + r'''
int main(void) {
    assert(pc_profile_absolute("C:\\Program Files\\profile"));
    assert(pc_profile_absolute("C:/Program Files\\profile"));
    assert(pc_profile_absolute("\\\\server\\share/profile"));
    assert(!pc_profile_absolute("C:relative"));
    assert(!pc_profile_absolute("relative\\profile"));
    assert(!pc_profile_absolute("/drive-relative"));
    assert(pc_path_equal("C:/Profile With Spaces/include", "c:\\profile with spaces\\include"));
    assert(!pc_path_equal("C:/Profile/include", "D:/Profile/include"));
    assert(pc_within("C:\\Profile With Spaces/include/foo.h", "c:/profile with spaces"));
    assert(!pc_within("C:/Profile With Spaces-other/include", "C:\\Profile With Spaces"));
    assert(!pc_within("D:/Profile With Spaces/include", "C:/Profile With Spaces"));
    assert(pc_within("\\\\server\\share/profile/include", "//SERVER/share/profile"));
    assert(!pc_within("\\\\server\\other/profile/include", "//server/share/profile"));
    return 0;
}
''')
    executable = root / ("windows-profile-paths.exe" if os.name == "nt" else "windows-profile-paths")
    compile_native(executable, [source])
    subprocess.run([str(executable)], capture_output=True, text=True, check=True)
    if os.name != "nt":
        print("Windows profile lexical path helpers: PASS (simulated; native filesystem validation separate)")


def main() -> int:
    """Run native format and ownership checks without requiring an installed compiler.

    Returns:
        Zero after every profile assertion succeeds.
    """
    with tempfile.TemporaryDirectory(prefix="l1-profile-native-") as temporary:
        root = Path(temporary).resolve()
        windows = root / "windows-paths"
        windows.mkdir()
        check_windows_path_spellings(windows)
        library = build_windows_macro_library(root)
        for name, check in (("manifest", check_manifest), ("inventory", check_inventory),
                            ("selection", check_selection), ("creation", check_creation),
                            ("implicit-config", check_implicit_configuration)):
            fixtures = root / name
            fixtures.mkdir()
            check(library, fixtures)
    print("explicit profile schema, integrity, exact selection and publication ownership: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
