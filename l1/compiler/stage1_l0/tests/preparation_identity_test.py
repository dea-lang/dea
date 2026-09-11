#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native identities, compiler adapters, runtime policy and conservative reuse."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
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
            compilers = {str(Path(path).resolve()) for name in ("gcc", "clang", "tcc") if (path := shutil.which(name))}
            for compiler in sorted(compilers):
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
            clang = shutil.which("clang")
            if clang:
                child = root / "target.rsp"
                child.write_text("-fPIC -DCONFIG_APP_ONLY=1\n")
                configuration = root / "native.cfg"
                configuration.write_text("@target.rsp\n")
                selected = {**config, "compiler": clang, "options": ["--config=" + str(configuration)]}
                configured = identity(library, selected)
                assert "-fPIC" in configured[2]["runtime"]["options"]
                assert "-DCONFIG_APP_ONLY=1" not in configured[2]["runtime"]["options"]
                child.write_text("-fPIC -DCONFIG_APP_ONLY=2\n")
                assert identity(library, selected)[1] != configured[1]
                nested = root / "config-selection.rsp"
                nested.write_text(shlex.quote("--config=" + str(configuration)))
                selected = {**config, "compiler": clang, "options": ["@" + str(nested)]}
                assert "-fPIC" in identity(library, selected)[2]["runtime"]["options"]
                child.write_text("-fPIC -flto\n")
                identity(library, selected, eligible=False)
                identity(library, {**selected, "force": 1}, eligible=False)
    print("native identity, runtime policy, adapters and memo invalidation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
