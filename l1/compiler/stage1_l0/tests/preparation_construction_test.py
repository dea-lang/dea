#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Construct native payloads from explicit inputs without managed identity or storage."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from l1c_stage1_managed_preparation_test import preparation_c_compiler
from l1c_stage1_compile_only_test import stage1_compiler
from preparation_support_test import L1_ROOT, Service, build_library

for scripts in (L1_ROOT / "scripts", L1_ROOT.parent / "scripts"):
    sys.path.insert(0, str(scripts))

from build_stage1_l1c import stage1_support_args
from build_stage2_l1c import build_support_objects
from dea_tooling.bootstrap import resolve_bootstrap_compiler, wrapper_command


def construction_inputs(root: Path) -> dict:
    """Snapshot explicit semantic, header, and native configuration for one module.

    Args:
        root: Owned fixture directory.

    Returns:
        Normalized construction inputs with separate generated and runtime options.
    """
    compiler = str(Path(preparation_c_compiler()).resolve())
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=True).stdout
    family = "clang" if "clang" in version else "gcc"
    archiver = subprocess.run([compiler, "-print-prog-name=ar"], capture_output=True,
                              text=True, check=True).stdout.strip()
    archiver = str(Path(shutil.which(archiver) or archiver).resolve())
    semantic = root / "interfaces/std/types.l1m"
    semantic.parent.mkdir(parents=True)
    shutil.copyfile(stage1_compiler().parent.parent / "interfaces/std/types.l1m", semantic)
    headers = root / "public headers"
    shutil.copytree(stage1_compiler().parent.parent / "include", headers)
    return dict(compiler=compiler, family=family, archiver=archiver, variant="check_basic",
                home=str(L1_ROOT / "compiler"), semantic_root=str(root / "interfaces"), include=str(headers),
                modules={"std.types": "verified by frontend"},
                interfaces={"modules/std/types.l1m": hashlib.sha256(semantic.read_bytes()).hexdigest()},
                options=["-O0", "-std=c99", "-DPROFILE_CONSTRUCTION_SENTINEL=1"],
                runtime_options=["-O2", "-std=c99", "-DDEA_RT_CHECK_BASIC"],
                codegen=dict(no_line_directives=1, check_basic=1))


def native_write(service: Service, relative: str, data: bytes) -> int:
    """Write through the production declared-output authorization.

    Args:
        service: Active constructor.
        relative: Payload or registered scratch path.
        data: Bytes to write.

    Returns:
        Native success indicator.
    """
    service.lib.l1c_prep_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                         ctypes.c_char_p, ctypes.c_int]
    path = relative.encode()
    return service.lib.l1c_prep_write(service.context, path, len(path), data, len(data))


def check_native(library: Path, root: Path, inputs: dict) -> None:
    """Check frozen inputs, real native commands, incomplete payloads and borrowed ownership.

    Args:
        library: Compiled shared native service.
        root: Owned fixture directory.
        inputs: Explicit normalized configuration.
    """
    destination = root / "native payload"
    destination.mkdir()
    sentinel = destination / "caller-owned"
    sentinel.write_text("retain")
    with Service(library, inputs, destination) as service:
        assert service.call("error_code") == 0, service.get("error")
        assert all(service.get(field) == "" for field in ("native_key", "dea_key", "local", "selected"))
        with patch.dict(os.environ, L1_CC="missing-compiler", L1_CFLAGS="-ffast-math",
                        L1_RUNTIME_CC="missing-runtime", RUNTIME_CFLAGS="invalid", AR="missing-ar",
                        L1_HOME="missing-home", L1_RUNTIME_INCLUDE="missing-headers",
                        L1_STDLIB_CACHE=str(root / "must-not-exist")):
            service.require("copy_interfaces")
            assert native_write(service, "generated/std/types.c", b"""
#ifndef PROFILE_CONSTRUCTION_SENTINEL
#error lost normalized generated options
#endif
#ifdef DEA_RT_CHECK_BASIC
#error mixed runtime and generated options
#endif
int construction_sentinel(void) { return PROFILE_CONSTRUCTION_SENTINEL; }
""") == 1
            service.lib.l1c_prep_compile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            assert service.lib.l1c_prep_compile(service.context, b"std.types", 9) == 1, service.get("error")
            service.require("runtime")
            service.require("construction_complete")
        inventory = json.loads(service.get("construction_inventory"))
        assert {item["path"] for item in inventory} == {
            "modules/std/types.l1m", "modules/std/types.o", "lib/libdea_rt_check_basic.a"}
        assert service.stats()["native_resolutions"] == service.stats()["probes"] == 0
        assert service.stats()["module_compiles"] == 1 and service.stats()["build_commands"] == 11
        assert not (destination / "manifest.json").exists()
        assert not (root / "must-not-exist").exists()
        assert native_write(service, "generated/std/types.c", b"late write") == 0
    assert sentinel.read_text() == "retain" and (destination / "modules/std/types.o").is_file()
    assert not (destination / "runtime-build").exists()

    for failure in ("incomplete", "undeclared", "changed-interface", "invalid-options", "native-failure"):
        target = root / failure
        target.mkdir()
        config = {**inputs, "options": [False]} if failure == "invalid-options" else inputs
        with Service(library, config, target) as service:
            if failure == "invalid-options":
                assert service.call("error_code") == 2151
                continue
            if failure == "changed-interface":
                semantic = Path(inputs["semantic_root"]) / "std/types.l1m"
                original = semantic.read_bytes()
                try:
                    semantic.write_bytes(b"changed after input verification")
                    assert service.call("copy_interfaces") == 0 and service.call("error_code") == 2158
                finally:
                    semantic.write_bytes(original)
            elif failure == "undeclared":
                assert native_write(service, "../escaped", b"bad") == 0
                assert not (root / "escaped").exists()
            else:
                service.require("copy_interfaces")
                if failure == "native-failure":
                    assert native_write(service, "generated/std/types.c", b"#error construction failure\n") == 1
                    service.lib.l1c_prep_compile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
                    assert service.lib.l1c_prep_compile(service.context, b"std.types", 9) == 0
                    assert service.call("error_code") == 2156
                else:
                    assert service.call("construction_complete") == 0 and service.call("error_code") == 2153
            assert Path(service.get("construction_root")) == target
            assert service.get("construction_inventory") == ""
        assert target.is_dir() and not (target / "manifest.json").exists()

    if os.name != "nt":
        escaped = root / "escaped-directory"
        escaped.mkdir()
        external = root / "external"
        external.mkdir()
        (escaped / "modules").symlink_to(external, target_is_directory=True)
        with Service(library, inputs, escaped) as service:
            assert service.call("error_code") == 2150
        assert list(external.iterdir()) == []


def check_frontend(root: Path, inputs: dict) -> None:
    """Run the selected stage's full frontend constructor with hostile later defaults.

    Args:
        root: Owned fixture directory.
        inputs: Explicit normalized construction inputs.
    """
    env = dict(os.environ)
    stage2 = "L1_TEST_COMPILER" in env
    stage, extension = ("stage2_l1", "l1") if stage2 else ("stage1_l0", "l0")
    fixture = L1_ROOT / f"compiler/{stage}/tests/fixtures/preparation/construction.{extension}"
    executable = root / ("constructor.exe" if os.name == "nt" else "constructor")
    if stage2:
        command = wrapper_command(Path(env["L1_TEST_COMPILER"]))
        support = build_support_objects(root / "support", env)
    else:
        _, command = resolve_bootstrap_compiler(
            override_text=env.get("L1_BOOTSTRAP_L0C"),
            default_path=L1_ROOT.parent / "l0/build/dea/bin/l0c-stage2",
            env_var_name="L1_BOOTSTRAP_L0C", setup_hint="run make -C ../l0 use-dev-stage2")
        support = stage1_support_args()
    trace = env.get("L1_CONSTRUCTION_TRACE") == "1"
    trace_options = ["--trace-arc", "--trace-memory"] if trace else []
    built = subprocess.run([*command, "--build", *trace_options, "--project-root", str(L1_ROOT / f"compiler/{stage}/src"),
                            *support, str(fixture), "-o", str(executable)], cwd=L1_ROOT, env=env,
                           capture_output=True, text=True, timeout=600)
    assert built.returncode == 0, built.stderr
    config = root / "inputs.json"
    config.write_text(json.dumps(inputs))
    destination = root / "frontend payload"
    destination.mkdir()
    env.update(L1_CONSTRUCTION_INPUTS=str(config), L1_CONSTRUCTION_DESTINATION=str(destination),
               L1_CC="missing-compiler", L1_CFLAGS="-ffast-math", L1_RUNTIME_CC="missing-runtime",
               L1_RUNTIME_INCLUDE="missing-headers", L1_HOME="missing-home", AR="missing-archiver",
               L1_STDLIB_CACHE=str(root / "unused-cache"))
    for failure in (False, True):
        if failure:
            config.write_text(json.dumps({**inputs, "include": str(root / "missing-headers")}))
            destination = root / "failed frontend payload"
            destination.mkdir()
            env.update(L1_CONSTRUCTION_FAILURE="1", L1_CONSTRUCTION_DESTINATION=str(destination))
        trace_path = root / ("failure.trace" if failure else "success.trace")
        with trace_path.open("w") as stderr:
            result = subprocess.run([str(executable)], cwd=L1_ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=stderr, text=True, timeout=120)
        assert result.returncode == 0, (result.stdout, trace_path.read_text()[-4000:])
        if trace:
            checker = L1_ROOT / f"compiler/{stage}/scripts/check_trace_log.py"
            checked = subprocess.run([sys.executable, str(checker), str(trace_path), "--triage", "--max-details", "5"],
                                     capture_output=True, text=True, timeout=120)
            assert checked.returncode == 0, checked.stdout + checked.stderr
            for balanced in ("errors=0", "leaked_object_ptrs=0", "leaked_string_ptrs=0"):
                assert balanced in checked.stdout, checked.stdout
            for family in ("mem", "arc"):
                count = re.search(r"^\s*" + family + r"_events=(\d+)$", checked.stdout, re.MULTILINE)
                assert count and int(count[1]) > 0, checked.stdout
        if not failure:
            assert (destination / "modules/std/types.o").is_file()
            assert (destination / "lib/libdea_rt_check_basic.a").is_file()
        assert b"#line " not in (destination / "generated/std/types.c").read_bytes()
        assert not (destination / "manifest.json").exists() and not (root / "unused-cache").exists()



def main() -> int:
    """Verify native boundary and selected-stage frontend construction."""
    with tempfile.TemporaryDirectory(prefix="l1-construction-") as temporary:
        root = Path(temporary).resolve()
        inputs = construction_inputs(root)
        check_native(build_library(root), root, inputs)
        check_frontend(root, inputs)
    print("explicit construction inputs, payload validation and destination ownership: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
