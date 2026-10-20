#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Use read-only installed inputs with managed preparation and explicit profiles."""

from __future__ import annotations

import os
from pathlib import Path
from support.compiler_subject import selected_native
import shutil
import subprocess
import sys
import tempfile

from l1c_compile_only_test import L1_ROOT, stage1_compiler
from l1c_managed_preparation_test import analysis_count, preparation_c_compiler
from l1c_profile_test import snapshot


def main() -> int:
    """Build through installed inputs and consume a profile after removing them."""
    native = selected_native(stage1_compiler().parent / "l1c.native")
    cc = preparation_c_compiler()
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
        (root / "app.l1").write_text(
            'module app; import std.io; func main() { printl_s("installed-ok"); }\n', encoding="utf-8")
        originals = snapshot(home)
        modes = {path: path.stat().st_mode for path in [home, *home.rglob("*")]}
        for path in modes:
            if os.name != "nt" or path.is_file():
                path.chmod(0o555 if path.is_dir() else 0o444)

        def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
            """Invoke the native executable using only the fixture's installed context."""
            result = subprocess.run([str(native), *args], cwd=root, env=env, text=True,
                                    encoding="utf-8", errors="replace", capture_output=True, timeout=600)
            assert result.returncode == expected, (args, result.stdout, result.stderr)
            return result

        try:
            run("--compile", "app", "-o", str(root / "app.o"))
            assert not cache.exists()
            profile = root / "explicit profile"
            run("--create-profile", "--check-basic", "-o", str(profile))
            assert not cache.exists() and not (root / "ignored-build").exists()
            missing = run("--run", "--no-auto-prepare", "app", expected=1)
            assert "L1C-2159" in missing.stderr
            cold = run("--run", "app")
            assert cold.stdout == "installed-ok\n" and "Preparing stdlib and runtime" in cold.stderr
            explicit = run("--run", "--sys-root", str(home / "shared/l1/stdlib"),
                           "--no-auto-prepare", "-vvv", "app")
            assert explicit.stdout == "installed-ok\n"
            assert analysis_count(explicit, "std.io") == 0, explicit.stderr
            assert "Preparing stdlib and runtime" not in explicit.stderr, explicit.stderr
            executable = root / ("linked.exe" if os.name == "nt" else "linked")
            warm = run("--link", "--no-auto-prepare", str(root / "app.o"), "-o", str(executable))
            assert "Preparing " not in warm.stderr
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=30)
            assert result.returncode == 0 and result.stdout == "installed-ok\n"
            markers = list(cache.glob("v1/native/*/manifest.json"))
            assert len(markers) == 1
            # A nonempty output directory fails during interface copying after begin,
            # including for privileged users that can bypass chmod restrictions.
            marker = markers[0]
            blocked = marker.parent / "modules/std/io.l1m"
            original_interface = blocked.read_bytes()
            marker.unlink()
            blocked.unlink()
            blocked.mkdir()
            sentinel = blocked / "owned-obstruction"
            sentinel.write_text("retain this obstruction", encoding="utf-8")
            try:
                fallback = run("--run", "app", "-v")
                assert fallback.stdout == "installed-ok\n" and "fresh command-private support" in fallback.stderr
                assert "Default cache storage is unavailable; preparing fresh command-private support." in fallback.stderr
                assert analysis_count(fallback, "_dea_preparation") == 1 and analysis_count(fallback, "app") == 2
                assert not marker.exists() and sentinel.read_text(encoding="utf-8") == "retain this obstruction"
                run("--prepare-stdlib", expected=1)
                run("--run", "--no-auto-prepare", "app", expected=1)
            finally:
                if blocked.is_dir():
                    shutil.rmtree(blocked)
                blocked.write_bytes(original_interface)
            unrelated = cache / "caller-owned.txt"
            unrelated.write_text("retain this sibling", encoding="utf-8")
            shutil.rmtree(cache / "v1")
            rebuilt = run("--run", "app")
            assert rebuilt.stdout == "installed-ok\n" and unrelated.read_text(encoding="utf-8") == "retain this sibling"
            run("--prepare-stdlib", "--stdlib-cache", str(home), expected=1)
            assert not (home / "v1").exists() and not (root / "ignored-build").exists()
            assert snapshot(home) == originals, "preparation modified installed inputs"
        finally:
            for path, mode in modes.items():
                if os.name != "nt" or path.is_file():
                    path.chmod(mode)
        shutil.rmtree(home)
        moved = root / "moved explicit profile"
        profile.rename(moved)
        before = snapshot(moved)
        ignored_cache = root / "must-not-create-cache"
        env.update(L1_CC="missing-profile-compiler", L1_CFLAGS="-ffast-math", L1_SYSTEM="missing-system",
                   L1_RUNTIME_INCLUDE="missing-include", L1_RUNTIME_LIB="missing-runtime",
                   L1_STDLIB_CACHE=str(ignored_cache))
        selected = run("--run", "app", "--profile", str(moved))
        assert selected.stdout == "installed-ok\n" and "Preparing " not in selected.stderr
        assert before == snapshot(moved), "installed explicit consumer modified the moved profile"
        assert not ignored_cache.exists() and not (root / "ignored-build").exists()
    print("installed semantic inputs, moved explicit profiles, cold cache and read-only ownership: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
