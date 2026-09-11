#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise automatic preparation, completed-corruption recovery and concurrent misses."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

from l1c_stage1_managed_preparation_test import invoke, toolchain_fixture
from l1c_stage1_compile_only_test import L1_ROOT, stage1_compiler, resolve_deterministic_host_c_compiler


def statistics(result: subprocess.CompletedProcess[str]) -> dict:
    """Read one native context's operation counts from debug output."""
    reports = re.findall(r"^Preparation statistics: (.*)$", result.stderr, re.MULTILINE)
    assert len(reports) == 1, result.stderr
    return json.loads(reports[0])


def main() -> int:
    """Verify consuming commands can recover without replacing completed persistent state."""
    cc = resolve_deterministic_host_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="l1-preparation-integration-") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        call = partial(invoke, root, env, compiler=compiler)
        cache = root / "cache with spaces and 'quotes'"
        headers = root / "runtime headers and 'quotes'"
        shutil.copytree(Path(env["L1_BUILD_DIR"]) / "include", headers)
        common = ("--c-compiler", cc, "--stdlib-cache", str(cache), "--runtime-include", str(headers),
                  "--c-options=-O1 -DREPAIR_OPTIONS=1 -fPIC", "--check-basic")
        source = root / "app.l1"
        source.write_text('module app; import std.io; func main() { printl_s("prepared-ok"); }\n')
        disabled = call("--run", *common, "--no-auto-prepare", "app", expected=1)
        assert "L1C-2159" in disabled.stderr and "--prepare-stdlib" in disabled.stderr
        assert not list(cache.glob("v1/native/*/manifest.json"))
        cold = call("--run", *common, "app", "-vvv")
        count = len(list((L1_ROOT / "compiler/shared/l1/stdlib").rglob("*.l1")))
        assert cold.stdout == "prepared-ok\n" and statistics(cold)["module_compiles"] == count
        marker = next(cache.glob("v1/native/*/manifest.json"))
        entry = marker.parent
        warm = call("--run", *common, "--no-auto-prepare", "app")
        assert warm.stdout == "prepared-ok\n" and warm.stderr == ""
        damaged = entry / "modules/std/io.o"
        data = damaged.read_bytes()
        damaged.write_bytes(b"!" + data[1:])
        rejected = call("--prepare-stdlib", *common, expected=1)
        assert "L1C-2153" in rejected.stderr and "--force" in rejected.stderr
        noauto = call("--run", *common, "--no-auto-prepare", "app", expected=1)
        assert "L1C-2159" in noauto.stderr and "externally serialize" in noauto.stderr
        manifest_bytes = marker.read_bytes()
        recovered = call("--run", *common, "app")
        assert recovered.stdout == "prepared-ok\n"
        assert "fresh command-private support" in recovered.stderr and "--force" in recovered.stderr
        assert "external serialization" in recovered.stderr
        assert marker.read_bytes() == manifest_bytes and damaged.read_bytes() != data
        shadow = entry / "generated/std/dea_rt.h"
        shadow.write_text("#error stale preparation scratch must never supply native headers\n")
        guidance = next(line.split("repair with ", 1)[1] for line in recovered.stderr.splitlines()
                        if line.startswith("Using fresh command-private support; repair with "))
        if guidance.startswith("literal argv "):
            repair_args, _ = json.JSONDecoder().raw_decode(guidance[len("literal argv "):])
        else:
            repair_args = shlex.split(guidance)
        assert repair_args[0] == "l1c" and "--force" in repair_args
        assert str(cache) in repair_args and "--check-basic" in repair_args
        assert "--c-options=-O1 -DREPAIR_OPTIONS=1 -fPIC" in repair_args
        forced = call(*repair_args[1:], "-vvv")
        assert list(cache.glob("v1/native/*/manifest.json")) == [marker]
        assert not shadow.exists()
        assert statistics(forced)["module_compiles"] == count and statistics(forced)["identity_content_reads"] > 0
        assert call("--run", *common, "--no-auto-prepare", "app").stdout == "prepared-ok\n"
        # Two same-key preparations of an incomplete entry must publish just once.
        marker.unlink()
        damaged.unlink()
        command = [str(compiler), "--prepare-stdlib", *common, "-vvv"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            runs = [executor.submit(subprocess.run, command, cwd=root, env=env, capture_output=True,
                                    text=True, timeout=600) for _ in range(2)]
            results = [future.result() for future in runs]
        for result in results:
            assert result.returncode == 0, result.stderr
        assert sum(statistics(result)["module_compiles"] for result in results) == count
        assert marker.is_file()
        # A malformed completion marker is completed corruption, never an ordinary miss.
        marker.write_text("unfinished JSON")
        malformed = call("--prepare-stdlib", *common, expected=1)
        assert "L1C-2153" in malformed.stderr and marker.read_text() == "unfinished JSON"
        if os.name != "nt":
            wrapper = root / "failing-cc"
            wrapper.write_text('#!/bin/sh\nfor word do\n if [ "$word" = -c ]; then\n'
                               '  echo "intentional native failure" >&2\n  exit 42\n fi\ndone\nexec ' +
                               shlex.quote(cc) + ' "$@"\n')
            wrapper.chmod(0o755)
            failure = call("--run", "--c-compiler", str(wrapper), "--stdlib-cache", str(root / "failed"),
                             "app", expected=1)
            assert "intentional native failure" in failure.stderr and "L1C-2156" in failure.stderr
            assert not list((root / "failed").glob("v1/native/*/manifest.json"))
    print("automatic native preparation, private recovery and concurrent misses: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
