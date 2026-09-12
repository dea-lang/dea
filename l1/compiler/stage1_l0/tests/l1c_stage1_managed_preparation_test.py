#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Verify managed native providers and retained C against the semantic bootstrap."""

from __future__ import annotations

import json
from functools import partial
import os
from pathlib import Path
import shutil
import re
import subprocess
import tempfile

from compiler_filesystem_support_test import resolve_c_compiler
from l1c_stage1_compile_only_test import L1_ROOT, stage1_compiler, classify_debug_compiler, resolve_deterministic_host_c_compiler


def preparation_c_compiler() -> str | None:
    """Honor configured GCC/Clang while retaining these fixtures' runtime archive requirement.

    Returns:
        A recognized GCC/Clang driver, or no available archive-producing fixture compiler.
    """
    compiler = resolve_c_compiler()
    return compiler if classify_debug_compiler(compiler) is not None else resolve_deterministic_host_c_compiler()


def invoke(root: Path, env: dict[str, str], *args: str, expected: int = 0,
           compiler: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a Stage 1 case, retaining compiler output in failed assertions."""
    result = subprocess.run([str(compiler or stage1_compiler()), *args], cwd=root, env=env,
                            capture_output=True, text=True, timeout=600)
    diagnostics = "\n".join(line for line in result.stderr.splitlines()
                            if not line.startswith(("Preparation Dea inputs:", "Preparation native inputs:")))
    assert result.returncode == expected, (args, result.returncode, result.stdout, diagnostics)
    return result


def toolchain_fixture(root: Path, env: dict[str, str]) -> Path:
    """Snapshot effective toolchain inputs so concurrent developer edits cannot stale a test."""
    fixture = root / "toolchain"
    home = fixture / "compiler"
    for relative in ("shared", "stage1_l0/src", "stage1_l0/support"):
        shutil.copytree(L1_ROOT / "compiler" / relative, home / relative)
    build = fixture / "build"
    for relative in ("interfaces", "include"):
        shutil.copytree(stage1_compiler().parent.parent / relative, build / relative)
    native = fixture / "l1c.native"
    shutil.copy2(stage1_compiler().parent / "l1c-stage1.native", native)
    env.update(L1_HOME=str(home), L1_BUILD_DIR=str(build))
    return native


def analysis_count(result: subprocess.CompletedProcess[str], module: str) -> int:
    """Count real frontend entry points in verbose output without timing the compiler.

    Args:
        result: Captured verbose compiler invocation.
        module: Exact entry module whose analysis boundaries to count.

    Returns:
        Number of driver analysis starts for that entry module.
    """
    return result.stderr.count(f"Starting analysis for entry module '{module}'")


def main() -> int:
    """Exercise real native preparation and optional scratch independence."""
    cc = preparation_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="l1-managed-provider-") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        call = partial(invoke, root, env, compiler=compiler)
        # std.types is not imported by another bundled module. Validate its own
        # interface even when preparation's per-module source entries would not.
        types_app = root / "types_app.l1"
        types_app.write_text("module types_app; import std.types; func main() {}\n")
        types_object = root / "types_app.o"
        call("--compile", "--c-compiler", cc, "types_app", "-o", str(types_object))
        types_interface = Path(env["L1_BUILD_DIR"]) / "interfaces/std/types.l1m"
        types_bytes = types_interface.read_bytes()
        try:
            for malformed in (False, True):
                if malformed:
                    types_interface.write_text("invalid bundled interface\n")
                else:
                    types_interface.unlink()
                invalid_cache = root / ("invalid-interface" if malformed else "missing-interface")
                for operation in (("--prepare-stdlib",),
                                  ("--link", str(types_object), "-o", str(root / "invalid-app")),
                                  ("--link", "--no-auto-prepare", str(types_object),
                                   "-o", str(root / "invalid-app"))):
                    rejected = call(*operation, "--c-compiler", cc, "--stdlib-cache", str(invalid_cache), expected=1)
                    assert "L1C-2158" in rejected.stderr and "build-stage1" in rejected.stderr, rejected.stderr
                    assert "Preparing stdlib and runtime" not in rejected.stderr, rejected.stderr
                    assert not list(invalid_cache.glob("v1/native/*/manifest.json"))
                types_interface.write_bytes(types_bytes)
        finally:
            types_interface.write_bytes(types_bytes)
        cache = root / "native cache"
        common = ("--c-compiler", cc, "--stdlib-cache", str(cache))
        cold = call("--prepare-stdlib", *common, "-v")
        assert "Preparing stdlib and runtime" in cold.stderr and not cold.stdout
        assert analysis_count(cold, "_dea_preparation") == 1, cold.stderr
        entries = list((cache / "v1/native").glob("*/manifest.json"))
        assert len(entries) == 1
        entry = entries[0].parent
        manifest = json.loads(entries[0].read_text())
        assert all(record["path"].startswith(("modules/", "lib/")) for record in manifest["artifacts"])
        assert not (entry / "include").exists() and not (cache / "v1/interfaces").exists()
        assert call("--prepare-stdlib", *common).stderr == ""
        warm_preparation = call("--prepare-stdlib", *common, "-v")
        assert analysis_count(warm_preparation, "_dea_preparation") == 1, warm_preparation.stderr
        assert "Preparation command" not in warm_preparation.stderr
        source = root / "app.l1"
        source.write_text('module app; import std.io; func main() { printl_s("managed-ok"); }\n')
        # A valid profile does not promise to retain any preparation C scratch.
        canonical_c = (entry / "generated/std/io.c").read_bytes()
        shutil.rmtree(entry / "generated")
        program = root / ("app.exe" if os.name == "nt" else "app")
        kept = call("--build", *common, "--no-auto-prepare", "--keep-c", "app", "-o", str(program), "-v")
        assert "Preparing " not in kept.stderr
        assert analysis_count(kept, "app") == 2 and analysis_count(kept, "_dea_preparation") == 1, kept.stderr
        retained = Path(str(program) + ".dea-c") / "std/io.c"
        assert retained.read_bytes() == canonical_c
        # This fixture imports exactly std.io's ten-module bundled closure.
        expected_managed = {"std.array", "std.assert", "std.integer", "std.io", "std.string", "std.text",
                            "std.unit", "std.vector", "sys.memory", "sys.rt"}
        generated_managed = re.findall(r"Starting analysis for entry module '((?:std|sys)\.[^']+)'", kept.stderr)
        assert sorted(generated_managed) == sorted(expected_managed), generated_managed
        retained_root = Path(str(program) + ".dea-c")
        retained_managed = {path.relative_to(retained_root).with_suffix("").as_posix().replace("/", ".")
                            for namespace in ("std", "sys") for path in (retained_root / namespace).rglob("*.c")}
        assert retained_managed == expected_managed
        result = subprocess.run([str(program)], cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and result.stdout == "managed-ok\n", result
        # Neither stale nor arbitrary debug scratch can affect retained output.
        scratch = entry / "generated/std/io.c"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("poisoned optional scratch")
        shutil.rmtree(Path(str(program) + ".dea-c"))
        call("--build", *common, "--keep-c", "app", "-o", str(program))
        assert retained.read_bytes() == canonical_c and scratch.read_text() == "poisoned optional scratch"
        generated = root / "io.gen.c"
        call("--gen", "std.io", "-o", str(generated))
        assert generated.read_bytes() == canonical_c
        obj = root / "io.o"
        call("--compile", "--c-compiler", cc, "--keep-c", "std.io", "-o", str(obj))
        assert obj.with_suffix(".c").read_bytes() == canonical_c
        # Standalone link discovers only the recorded bundled closure.
        app_obj = root / "app.o"
        call("--compile", "--c-compiler", cc, "app", "-o", str(app_obj))
        linked = root / ("linked.exe" if os.name == "nt" else "linked")
        call("--link", *common, "--no-auto-prepare", str(app_obj), "-o", str(linked))
        result = subprocess.run([str(linked)], cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0 and result.stdout == "managed-ok\n", result
        # Inspect real compiler words while selecting a second complete native profile.
        headers = root / "override headers"
        shutil.copytree(Path(env["L1_BUILD_DIR"]) / "include", headers)
        env["L1_CFLAGS"] = "-O0 -DENV_GENERATED_ONLY=1"
        configured_args = (*common, "--c-options", "-O1 -DCLI_GENERATED_ONLY=1 -fPIC",
                           "--check-basic", "--runtime-include", str(headers))
        configured = call("--build", *configured_args, "app", "-o", str(program), "-vv")
        commands = [(purpose, json.loads(words)) for purpose, words in
                    re.findall(r"^Preparation command \(([^)]+)\): (.*)$", configured.stderr, re.MULTILINE)]
        module_commands = [words for purpose, words in commands if purpose.startswith(("std.", "sys."))]
        runtime_commands = [words for purpose, words in commands if purpose.startswith("dea_rt_")]
        assert len(module_commands) == 23 and len(runtime_commands) == 9
        for words in module_commands:
            assert Path(words[0]).resolve() == Path(cc).resolve()
            assert words.index("-O0") < words.index("-O1") < words.index("-std=c99")
            assert "-DENV_GENERATED_ONLY=1" in words and "-DCLI_GENERATED_ONLY=1" in words
            assert "-fPIC" in words and str(headers) in words
        for words in runtime_commands:
            assert Path(words[0]).resolve() == Path(cc).resolve()
            assert words[1:3] == ["-O2", "-std=c99"] and "-fPIC" in words
            assert "-DDEA_RT_CHECK_BASIC" in words
            assert "-D_RT_QUARANTINE_MAX_BYTES=16777216" in words
            assert "-D_RT_QUARANTINE_MAX_COUNT=4096" in words
            assert not {"-O0", "-O1", "-DENV_GENERATED_ONLY=1", "-DCLI_GENERATED_ONLY=1", str(headers)}.intersection(words)
        records = list(cache.glob("v1/native/*/manifest.json"))
        assert len(records) == 2
        configured_marker = next(path for path in records if path != entries[0])
        configured_entry = configured_marker.parent
        for relative in Path(env["L1_BUILD_DIR"]).joinpath("interfaces").rglob("*.l1m"):
            assert (configured_entry / "modules" / relative.relative_to(Path(env["L1_BUILD_DIR"]) / "interfaces")).read_bytes() == relative.read_bytes()
        assert (configured_entry / "lib/libdea_rt_check_basic.a").is_file()
        # A final runtime-library override and legacy Make controls do not select another N.
        env.update(L1_RUNTIME_CC="missing-runtime-compiler", RUNTIME_CFLAGS="invalid", AR="missing-archiver",
                   L1_RT_QUARANTINE_MAX_BYTES="1", L1_RT_QUARANTINE_MAX_COUNT="1")
        selected = call("--run", *configured_args, "--runtime-lib", str(configured_entry / "lib"),
                        "--no-auto-prepare", "app")
        assert selected.stdout == "managed-ok\n" and selected.stderr == ""
        assert len(list(cache.glob("v1/native/*/manifest.json"))) == 2
        # The environment form of the header override has the same effective configuration.
        env["L1_RUNTIME_INCLUDE"] = str(headers)
        same = call("--run", *configured_args[:-2], "--no-auto-prepare", "app")
        assert same.stdout == "managed-ok\n" and same.stderr == ""
        del env["L1_RUNTIME_INCLUDE"]
        del env["L1_CFLAGS"]
        switched_back = call("--run", *common, "--no-auto-prepare", "app")
        assert switched_back.stdout == "managed-ok\n" and switched_back.stderr == ""
    print("managed semantic/native providers and retained C: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
