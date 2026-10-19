#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Compose L1 modules through caller-owned profiles without managed preparation."""

from __future__ import annotations

from functools import partial
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from l1c_managed_preparation_test import invoke, preparation_c_compiler, toolchain_fixture
from l1c_compile_only_test import L1_ROOT


def snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Record payload bytes and modification times to detect consumer writes.

    Args:
        root: Selected profile directory.

    Returns:
        Relative names mapped to size, nanosecond timestamp and digest.
    """
    return {path.relative_to(root).as_posix():
            (path.stat().st_size, path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in root.rglob("*") if path.is_file()}


def no_preparation(result: subprocess.CompletedProcess[str]) -> None:
    """Reject managed selection and construction evidence in an explicit consumer.

    Args:
        result: Captured compiler invocation at debug verbosity.
    """
    for marker in ("Preparing stdlib", "Preparation selection:", "Preparation native key:",
                   "Preparation Dea key:", "Reuse prepared profile:", "'_dea_preparation'"):
        assert marker not in result.stderr, (marker, result.stderr)


def execute(path: Path, expected: str) -> None:
    """Run a composed executable and check lifecycle and bundled output.

    Args:
        path: Executable output.
        expected: Exact stdout.
    """
    result = subprocess.run([str(path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and result.stdout == expected, result


def main() -> int:
    """Check explicit composition, isolation, configuration locking and failure behavior.

    Returns:
        Zero on successful validation.
    """
    cc = preparation_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="l1 explicit profile ") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        call = partial(invoke, root, env, compiler=compiler)
        profile = root / "profile with spaces"
        cache = root / "managed cache"
        flags = "-O0 -DPROFILE_SENTINEL=1"
        common = ("--c-compiler", cc, "--c-options=" + flags, "--check-basic", "--no-line-directives")
        # Fixed dependency order and existing lifecycle observer exercise the same compiler/linker.
        fixtures = L1_ROOT / "compiler/tests/fixtures/separate_compilation"
        shutil.copytree(fixtures / "lifecycle", root / "lifecycle")
        main_source = root / "lifecycle/main.l1"
        main_source.write_text(main_source.read_text().replace("module lifecycle.main;",
                              "module lifecycle.main;\nimport std.io;").replace(
                                  "    return 0;", '    printl_s("profile-ok");\n    return 0;'))
        shim = root / "observer.o"
        subprocess.run([cc, "-c", str(fixtures / "lifecycle_observer.c"), "-o", str(shim)], check=True)
        created = call("--create-profile", *common, "-o", str(profile), "-vvv")
        assert not created.stdout and (profile / "profile.json").is_file(), created
        assert not cache.exists()
        manifest_bytes = (profile / "profile.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        assert manifest["schema"] == manifest["contract"] == 1
        assert manifest["kind"] == "l1-explicit-profile"
        assert manifest["configuration"]["variant"] == "check_basic"
        assert Path(manifest["configuration"]["compiler"]).is_absolute()
        assert "std.io" in manifest["modules"]
        assert all(not Path(item["path"]).is_absolute() for item in manifest["payloads"])
        before = snapshot(profile)
        # Ordinary managed composition remains available for equivalent configuration.
        managed = root / "managed-app"
        call("--build", "lifecycle.main", *common, "--stdlib-cache", str(cache),
             "--foreign-object", str(shim), "--keep-c", "-o", str(managed))
        execute(managed, "profile-ok\n")
        original_env = dict(env)
        # Poison every ambient selector and remove original bundled/native inputs.
        env.update(L1_CC="missing-profile-compiler", L1_CFLAGS="-ffast-math", L1_SYSTEM=str(root / "missing-system"),
                   L1_RUNTIME_INCLUDE=str(root / "missing-headers"), L1_RUNTIME_LIB=str(root / "missing-runtime"),
                   L1_STDLIB_CACHE=str(root / "must-not-create-cache"))
        shutil.rmtree(Path(env["L1_HOME"]) / "shared")
        shutil.rmtree(Path(env["L1_BUILD_DIR"]) / "interfaces")
        shutil.rmtree(Path(env["L1_BUILD_DIR"]) / "include")
        moved = root / "moved profile"
        profile.rename(moved)
        permissions = {}
        if os.name != "nt":
            for path in [moved, *moved.rglob("*")]:
                permissions[path] = path.stat().st_mode & 0o777
                path.chmod(0o555 if path.is_dir() else 0o444)
        selected = ("--profile", str(moved))
        modules = root / "objects"
        retained: dict[str, bytes] = {}
        for name in ("leaf", "provider", "side_effect", "main"):
            output = modules / "lifecycle" / (name + ".o")
            output.parent.mkdir(parents=True, exist_ok=True)
            compiled = call("--compile", "lifecycle." + name, *selected, "-I", str(modules),
                            "-o", str(output), "--keep-c", "-vvv")
            no_preparation(compiled)
            assert output.is_file() and output.with_suffix(".l1m").is_file()
            retained[name] = output.with_suffix(".c").read_bytes()
        manual = root / "manual-app"
        linked = call("--link", str(modules / "lifecycle/main.o"), "-I", str(modules), *selected,
                      "--foreign-object", str(shim), "--no-auto-prepare", "-o", str(manual), "-vvv")
        no_preparation(linked)
        execute(manual, "profile-ok\n")
        direct = root / "direct-app"
        built = call("--build", "lifecycle.main", *selected, "--foreign-object", str(shim),
                     "--keep-c", "-o", str(direct), "-vvv")
        no_preparation(built)
        execute(direct, "profile-ok\n")
        retained_root = root / "direct-app.dea-c"
        for name, data in retained.items():
            assert (retained_root / "lifecycle" / (name + ".c")).read_bytes() == data
            assert (root / "managed-app.dea-c/lifecycle" / (name + ".c")).read_bytes() == data
        assert not (retained_root / "std").exists(), "prebuilt bundled providers regenerated retained C"
        ran = call("--run", "lifecycle.main", *selected, "--foreign-object", str(shim), "-vvv")
        no_preparation(ran)
        assert ran.stdout == "profile-ok\n"
        assert before == snapshot(moved), "explicit consumers modified the profile"
        assert not (root / "must-not-create-cache").exists()
        for path, mode in permissions.items():
            path.chmod(mode)
        override = root / "invalid-provider/std"
        override.mkdir(parents=True)
        (override / "io.l1m").write_text("invalid explicit interface\n")
        failed = call("--compile", "lifecycle.main", *selected, "-I", str(override.parent),
                      "-I", str(modules), "-o", str(root / "invalid-provider.o"), expected=1)
        assert "io.l1m" in failed.stderr and not (root / "invalid-provider.o").exists(), failed.stderr
        no_preparation(failed)
        for mode, target in (("--compile", "lifecycle.leaf"), ("--build", "lifecycle.main"),
                             ("--link", str(modules / "lifecycle/main.o"))):
            name = "unconsumed-output.o" if mode == "--compile" else "unconsumed-output"
            refused = call(mode, target, *selected, "-I", str(modules),
                           "-o", str(moved / name), expected=1)
            assert "L1C-218" in refused.stderr, refused.stderr
            assert before == snapshot(moved), "output publication modified a selected profile"
        saved_temp = {name: env.get(name) for name in ("TMPDIR", "TEMP", "TMP")}
        env.update({name: str(moved) for name in saved_temp})
        refused = call("--compile", "lifecycle.leaf", *selected, "-o", str(root / "bad-temp.o"), expected=1)
        assert "L1C-2184" in refused.stderr, refused.stderr
        assert before == snapshot(moved), "temporary allocation modified a selected profile"
        for name, value in saved_temp.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        # Redundant settings are accepted; explicit conflicts fail without output publication.
        call("--compile", "lifecycle.leaf", *selected, *common, "-o", str(root / "redundant.o"))
        for conflict in (("--unchecked",), ("--c-options=-O3",), ("--trace-memory",),
                         ("--c-compiler", str(root / "missing-compiler"))):
            failed = call("--compile", "lifecycle.leaf", *selected, *conflict,
                          "-o", str(root / "conflict.o"), expected=1)
            assert "L1C-2184" in failed.stderr, failed.stderr
            assert not (root / "conflict.o").exists()
        # Missing/corrupt/unsupported selected profiles never fall back to the valid managed cache.
        env["L1_STDLIB_CACHE"] = str(cache)
        missing = call("--build", "lifecycle.main", "--profile", str(root / "absent"), expected=1)
        assert "L1C-2182" in missing.stderr
        marker = moved / "profile.json"
        for field in ("schema", "contract"):
            changed = {**manifest, field: 999}
            marker.write_text(json.dumps(changed))
            failed = call("--build", "lifecycle.main", *selected, expected=1)
            assert "L1C-218" in failed.stderr
        marker.write_bytes(manifest_bytes)
        damaged = moved / "modules/std/io.o"
        object_bytes = damaged.read_bytes()
        damaged.write_bytes(b"!" + object_bytes[1:])
        # Compile-only does not consume imported native objects.
        call("--compile", "lifecycle.main", *selected, "-I", str(modules), "-o", str(root / "unused-native.o"))
        failed = call("--link", str(modules / "lifecycle/main.o"), *selected, "-I", str(modules),
                      "-o", str(root / "damaged-app"), expected=1)
        assert "L1C-2183" in failed.stderr
        damaged.write_bytes(object_bytes)
        header = moved / "include/dea_rt.h"
        header.write_bytes(header.read_bytes() + b"\n/* damaged */\n")
        failed = call("--compile", "lifecycle.leaf", *selected, "-o", str(root / "bad-header.o"), expected=1)
        assert "L1C-2183" in failed.stderr
        # Creation refuses overwrite, response-file interpretation and configuration paths.
        env.clear()
        env.update(original_env)
        refused = call("--create-profile", *common, "-o", str(moved), expected=1)
        assert "L1C-2181" in refused.stderr
    print("explicit L1 profiles: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
