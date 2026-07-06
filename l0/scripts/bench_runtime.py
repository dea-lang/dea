#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Benchmark the checked L0 runtime allocation tracker.

Compiles ``scripts/bench_runtime_harness.c`` against the shared header runtime
once per quarantine-retention setting (plus an ``L0_RT_UNCHECKED`` baseline)
for each requested C compiler, runs the scenarios best-of-N, and prints one
table per compiler. Wall-clock numbers are informational; the deterministic
memory invariants live in the test suite, not here.

Example:
    python scripts/bench_runtime.py --cc "tcc clang gcc-16" --scale 5
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


L0_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = L0_ROOT / "compiler" / "shared" / "runtime"
HARNESS = L0_ROOT / "scripts" / "bench_runtime_harness.c"

SCENARIOS = ("tight", "window", "ramp", "strings")
WALL_KEYS = {
    "tight": ("tight.wall_ms",),
    "window": ("window.wall_ms",),
    "ramp": ("ramp.grow_wall_ms", "ramp.free_wall_ms", "ramp.settle_wall_ms"),
    "strings": ("strings.wall_ms",),
}
DEFAULT_COMPILERS = ("tcc", "clang", "gcc-16")
DEFAULT_SETTINGS = (0, 256, 1024, 4096, 16384, 65536)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cc",
        default="",
        help="Space- or comma-separated C compilers (default: available among tcc, clang, gcc-16)",
    )
    parser.add_argument("--scale", type=int, default=5, help="Scenario scale multiplier (default: 5)")
    parser.add_argument("--runs", type=int, default=3, help="Runs per cell; best wall time wins (default: 3)")
    parser.add_argument(
        "--settings",
        default=",".join(str(v) for v in DEFAULT_SETTINGS),
        help="Comma-separated _RT_QUARANTINE_MAX_COUNT values",
    )
    return parser.parse_args()


def resolve_compilers(spec: str) -> list[str]:
    if spec.strip():
        requested = [word for word in re.split(r"[,\s]+", spec.strip()) if word]
        missing = [cc for cc in requested if shutil.which(cc) is None]
        if missing:
            raise SystemExit(f"bench_runtime: compiler(s) not found on PATH: {', '.join(missing)}")
        return requested
    found = [cc for cc in DEFAULT_COMPILERS if shutil.which(cc) is not None]
    skipped = [cc for cc in DEFAULT_COMPILERS if shutil.which(cc) is None]
    if skipped:
        print(f"bench_runtime: skipping unavailable compiler(s): {', '.join(skipped)}", file=sys.stderr)
    if not found:
        raise SystemExit("bench_runtime: no C compiler found; pass --cc explicitly")
    return found


def compile_variant(cc: str, define: str, out_path: Path) -> None:
    command = [cc, "-std=c99", "-O2", f"-I{RUNTIME_DIR}", str(HARNESS), "-o", str(out_path)]
    if define:
        command.insert(3, define)
    subprocess.run(command, check=True, capture_output=True, text=True)


def run_scenario(exe: Path, scenario: str, scale: int) -> dict[str, float]:
    completed = subprocess.run(
        [str(exe), scenario, str(scale)],
        capture_output=True,
        text=True,
        check=True,
    )
    values: dict[str, float] = {}
    for line in completed.stdout.split():
        key, _, value = line.partition("=")
        if value:
            values[key] = float(value)
    return values


def bench_cell(exe: Path, scenario: str, scale: int, runs: int) -> dict[str, float]:
    best: dict[str, float] | None = None
    for _ in range(runs):
        values = run_scenario(exe, scenario, scale)
        wall = sum(values.get(key, 0.0) for key in WALL_KEYS[scenario])
        values["_wall"] = wall
        if best is None or wall < best["_wall"]:
            best = values
    assert best is not None
    return best


def format_row(label: str, cells: dict[str, dict[str, float]]) -> str:
    def wall(scenario: str) -> str:
        return f"{cells[scenario]['_wall']:9.0f}"

    ramp = cells["ramp"]
    rss_mib = ramp.get("max_rss_kib", 0.0) / 1024.0
    cap_peak = int(ramp.get("ramp.table_cap_peak", 0))
    chunks = int(ramp.get("ramp.rec_pool_chunks_peak", 0))
    return (
        f"{label:>10} | {wall('tight')} | {wall('window')} | {wall('ramp')} | {wall('strings')} |"
        f" {rss_mib:10.1f} | {cap_peak:9d} | {chunks:7d}"
    )


def main() -> int:
    args = parse_args()
    compilers = resolve_compilers(args.cc)
    settings = [int(word) for word in args.settings.split(",") if word.strip()]

    print(f"bench_runtime: scale={args.scale} runs={args.runs} (wall in ms, best of {args.runs})")
    header = (
        f"{'setting':>10} | {'tight':>9} | {'window':>9} | {'ramp':>9} | {'strings':>9} |"
        f" {'rampRSSMiB':>10} | {'rampCap':>9} | {'chunks':>7}"
    )

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        for cc in compilers:
            cc_version = subprocess.run([cc, "--version"], capture_output=True, text=True, check=False)
            print(f"\n=== {cc} ({cc_version.stdout.splitlines()[0] if cc_version.stdout else 'unknown'}) ===")
            print(header)
            print("-" * len(header))

            variants: list[tuple[str, str]] = [("unchecked", "-DL0_RT_UNCHECKED")]
            variants.extend((str(n), f"-D_RT_QUARANTINE_MAX_COUNT={n}") for n in settings)
            for label, define in variants:
                exe = work_dir / f"bench_{cc.replace('/', '_')}_{label}"
                compile_variant(cc, define, exe)
                cells = {
                    scenario: bench_cell(exe, scenario, args.scale, args.runs)
                    for scenario in SCENARIOS
                }
                print(format_row(label, cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
