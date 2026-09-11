#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Use a read-only installed-input fixture with a cold per-user native cache."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from l1c_stage1_compile_only_test import L1_ROOT, stage1_compiler, resolve_deterministic_host_c_compiler


def main() -> int:
    """Build and link through installed interfaces without installed native artifacts."""
    native = stage1_compiler().parent / "l1c-stage1.native"
    cc = resolve_deterministic_host_c_compiler()
    assert cc
    with tempfile.TemporaryDirectory(prefix="l1-installation-fixture-") as directory:
        root = Path(directory).resolve()
        shutil.copy2(native, root / "l1c.native")
        native = root / "l1c.native"
        home, user = root / "toolchain", root / "user"
        shutil.copytree(L1_ROOT / "compiler/shared", home / "shared")
        shutil.copytree(stage1_compiler().parent.parent / "interfaces", home / "interfaces")
        shutil.copytree(stage1_compiler().parent.parent / "include", home / "include")
        env = dict(os.environ)
        for name in ("L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_CFLAGS", "L1_STDLIB_CACHE"):
            env.pop(name, None)
        env.update(L1_HOME=str(home), L1_BUILD_DIR=str(root / "ignored-build"), L1_CC=cc,
                   HOME=str(user), USERPROFILE=str(user), LOCALAPPDATA=str(user / "Local"),
                   XDG_CACHE_HOME=str(user / "xdg"))
        cache = (user / "Local/Dea/L1/Cache" if os.name == "nt" else
                 user / "Library/Caches/dea/l1" if sys.platform == "darwin" else user / "xdg/dea/l1")
        (root / "app.l1").write_text('module app; import std.io; func main() { printl_s("installed-ok"); }\n')
        originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in home.rglob("*") if path.is_file()}
        modes = {path: path.stat().st_mode for path in [home, *home.rglob("*")]}
        if os.name != "nt":
            for path in modes:
                path.chmod(0o555 if path.is_dir() else 0o444)

        def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
            """Invoke the native executable using only the fixture's installed context."""
            result = subprocess.run([str(native), *args], cwd=root, env=env, text=True,
                                    capture_output=True, timeout=600)
            assert result.returncode == expected, (args, result.stdout, result.stderr)
            return result

        try:
            run("--compile", "app", "-o", str(root / "app.o"))
            assert not cache.exists()
            missing = run("--run", "--no-auto-prepare", "app", expected=1)
            assert "L1C-2159" in missing.stderr
            cold = run("--run", "app")
            assert cold.stdout == "installed-ok\n" and "Preparing stdlib and runtime" in cold.stderr
            executable = root / ("linked.exe" if os.name == "nt" else "linked")
            warm = run("--link", "--no-auto-prepare", str(root / "app.o"), "-o", str(executable))
            assert "Preparing " not in warm.stderr
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            assert result.returncode == 0 and result.stdout == "installed-ok\n"
            markers = list(cache.glob("v1/native/*/manifest.json"))
            assert len(markers) == 1
            if os.name != "nt":
                # Existing read-only output directories fail only after begin succeeds.
                marker = markers[0]
                blocked = marker.parent / "modules/std"
                marker.unlink()
                blocked.chmod(0o500)
                try:
                    fallback = run("--run", "app")
                    assert fallback.stdout == "installed-ok\n" and "fresh command-private support" in fallback.stderr
                    assert not marker.exists()
                    run("--prepare-stdlib", expected=1)
                    run("--run", "--no-auto-prepare", "app", expected=1)
                finally:
                    blocked.chmod(0o755)
            unrelated = cache / "caller-owned.txt"
            unrelated.write_text("retain this sibling")
            shutil.rmtree(cache / "v1")
            rebuilt = run("--run", "app")
            assert rebuilt.stdout == "installed-ok\n" and unrelated.read_text() == "retain this sibling"
            run("--prepare-stdlib", "--stdlib-cache", str(home), expected=1)
            assert not (home / "v1").exists() and not (root / "ignored-build").exists()
            assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in home.rglob("*") if path.is_file()} == originals
        finally:
            if os.name != "nt":
                for path, mode in modes.items():
                    path.chmod(mode)
    print("installed semantic inputs, cold per-user cache and read-only ownership: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
