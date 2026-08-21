#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Benchmark standalone-link transitive provenance validation.

The benchmark compiles one L0 harness, constructs each requested graph outside
the timed region, warms validation, and records monotonic samples. Results are
informational and deliberately carry no CI performance threshold.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Sequence


L1_ROOT = Path(__file__).resolve().parents[1]
STAGE1_SCRIPTS = L1_ROOT / "compiler" / "stage1_l0" / "scripts"
if str(STAGE1_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STAGE1_SCRIPTS))

from build_stage1_l1c import stage1_support_args
from test_runner_common import (
    build_repo_test_env,
    repo_stage1_command,
    resolve_l1_build_dir,
)


HARNESS = L1_ROOT / "compiler" / "stage1_l0" / "benchmarks" / "link_provenance_benchmark.l0"
DEFAULT_SHAPES = ("control-chain", "direct-chain", "terminal-chain", "layered-dag")
DEFAULT_SIZES = (250, 500, 1000, 2000, 4000)


def parse_csv_strings(value: str) -> list[str]:
    """Return nonempty comma-separated values.

    Args:
        value: Raw comma-separated text.

    Returns:
        Parsed values in encounter order.
    """

    return [part.strip() for part in value.split(",") if part.strip()]


def parse_csv_ints(value: str) -> list[int]:
    """Return positive comma-separated integers.

    Args:
        value: Raw comma-separated text.

    Returns:
        Parsed positive integers in encounter order.

    Raises:
        argparse.ArgumentTypeError: If an entry is not a positive integer.
    """

    try:
        parsed = [int(part) for part in parse_csv_strings(value)]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc
    if not parsed or any(size < 2 for size in parsed):
        raise argparse.ArgumentTypeError("sizes must contain integers of at least two")
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse benchmark CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shapes",
        default=",".join(DEFAULT_SHAPES),
        help=f"Comma-separated graph shapes (default: {','.join(DEFAULT_SHAPES)})",
    )
    parser.add_argument(
        "--sizes",
        type=parse_csv_ints,
        default=list(DEFAULT_SIZES),
        help="Comma-separated module counts (default: 250,500,1000,2000,4000)",
    )
    parser.add_argument("--warmups", type=int, default=1, help="Warmups per cell (default: 1)")
    parser.add_argument("--runs", type=int, default=7, help="Measured runs per cell (default: 7)")
    parser.add_argument("--json", type=Path, help="Optional path for machine-readable results")
    parser.add_argument("--compare", type=Path, help="Optional prior JSON result to compare")
    args = parser.parse_args()

    args.shapes = parse_csv_strings(args.shapes)
    unknown = [shape for shape in args.shapes if shape not in DEFAULT_SHAPES]
    if not args.shapes or unknown:
        parser.error(f"unknown or empty shape selection: {','.join(unknown) or '<empty>'}")
    if args.warmups < 0:
        parser.error("--warmups must be non-negative")
    if args.runs < 1:
        parser.error("--runs must be positive")
    return args


def compile_harness(executable: Path, env: dict[str, str]) -> None:
    """Compile the benchmark harness once.

    Args:
        executable: Output native executable path.
        env: Sanitized repository build environment.

    Raises:
        RuntimeError: If compilation fails.
    """

    command = [
        *repo_stage1_command(),
        "--project-root",
        "compiler/stage1_l0/src",
        "--build",
        *stage1_support_args(),
        "--output",
        str(executable),
        str(HARNESS),
    ]
    completed = subprocess.run(
        command,
        cwd=L1_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"benchmark harness compilation failed:\n{completed.stdout}")


def parse_samples(stdout: str, shape: str, size: int, runs: int) -> list[int]:
    """Parse nanosecond samples emitted by one harness run.

    Args:
        stdout: Harness standard output.
        shape: Expected graph shape.
        size: Expected module count.
        runs: Expected sample count.

    Returns:
        Monotonic durations in nanoseconds.

    Raises:
        RuntimeError: If output is malformed or incomplete.
    """

    samples: list[int] = []
    for line in stdout.splitlines():
        if not line.startswith("sample="):
            continue
        fields = line.removeprefix("sample=").split(",")
        if len(fields) != 5:
            raise RuntimeError(f"malformed benchmark sample: {line}")
        actual_shape, size_text, iteration_text, sec_text, nsec_text = fields
        try:
            actual_size = int(size_text)
            iteration = int(iteration_text)
            seconds = int(sec_text)
            nanoseconds = int(nsec_text)
        except ValueError as exc:
            raise RuntimeError(f"non-numeric benchmark sample: {line}") from exc
        if actual_shape != shape or actual_size != size:
            raise RuntimeError(f"unexpected benchmark sample identity: {line}")
        if iteration != len(samples):
            raise RuntimeError(f"non-sequential benchmark sample: {line}")
        if seconds < 0 or not 0 <= nanoseconds < 1_000_000_000:
            raise RuntimeError(f"invalid benchmark duration: {line}")
        samples.append(seconds * 1_000_000_000 + nanoseconds)
    if len(samples) != runs:
        raise RuntimeError(f"{shape}/{size}: expected {runs} samples, found {len(samples)}")
    return samples


def run_cell(
    executable: Path,
    env: dict[str, str],
    shape: str,
    size: int,
    warmups: int,
    runs: int,
) -> list[int]:
    """Run and parse one benchmark cell.

    Args:
        executable: Compiled harness path.
        env: Sanitized repository build environment.
        shape: Graph shape name.
        size: Module count.
        warmups: Untimed validation count.
        runs: Measured validation count.

    Returns:
        Measured durations in nanoseconds.

    Raises:
        RuntimeError: If the harness fails.
    """

    completed = subprocess.run(
        [str(executable), shape, str(size), str(warmups), str(runs)],
        cwd=L1_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{shape}/{size}: benchmark harness failed with {completed.returncode}:\n{completed.stdout}"
        )
    return parse_samples(completed.stdout, shape, size, runs)


def summarize(samples: Sequence[int]) -> dict[str, float | int | list[int]]:
    """Return stable summary statistics for one cell.

    Args:
        samples: Nanosecond measurements.

    Returns:
        Raw samples plus minimum, median, and maximum durations.
    """

    return {
        "samples_ns": list(samples),
        "min_ns": min(samples),
        "median_ns": statistics.median(samples),
        "max_ns": max(samples),
    }


def print_results(results: dict[str, dict[int, dict[str, object]]]) -> None:
    """Print medians and adjacent-size doubling ratios.

    Args:
        results: Results grouped by shape and module count.
    """

    print("shape          modules   min_ms median_ms   max_ms doubling")
    print("-------------- ------- --------- --------- --------- --------")
    for shape, cells in results.items():
        previous_median: float | None = None
        for size, cell in cells.items():
            median_ns = float(cell["median_ns"])
            ratio = "-" if previous_median is None else f"{median_ns / previous_median:.2f}x"
            print(
                f"{shape:14} {size:7d} "
                f"{float(cell['min_ns']) / 1_000_000:9.3f} "
                f"{median_ns / 1_000_000:9.3f} "
                f"{float(cell['max_ns']) / 1_000_000:9.3f} {ratio:>8}"
            )
            cell["doubling_ratio"] = None if previous_median is None else median_ns / previous_median
            previous_median = median_ns


def print_comparison(
    baseline_path: Path,
    results: dict[str, dict[int, dict[str, object]]],
) -> None:
    """Print median speedups against one saved benchmark result.

    Args:
        baseline_path: Prior JSON result path.
        results: Current results grouped by shape and module count.

    Raises:
        RuntimeError: If the baseline is unreadable or lacks a current cell.
    """

    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_results = baseline["results"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"cannot read comparison baseline {baseline_path}: {exc}") from exc

    print("\ncomparison      modules baseline_ms current_ms  speedup")
    print("-------------- ------- ----------- ---------- --------")
    for shape, cells in results.items():
        for size, cell in cells.items():
            try:
                baseline_ns = float(baseline_results[shape][str(size)]["median_ns"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"comparison baseline lacks {shape}/{size}") from exc
            current_ns = float(cell["median_ns"])
            speedup = baseline_ns / current_ns
            print(
                f"{shape:14} {size:7d} {baseline_ns / 1_000_000:11.3f} "
                f"{current_ns / 1_000_000:10.3f} {speedup:7.2f}x"
            )


def main() -> int:
    """Compile the harness, run the matrix, and report results."""

    args = parse_args()
    try:
        build_dir_text, build_dir = resolve_l1_build_dir()
        repo_env = build_repo_test_env(build_dir_text, build_dir)
        with tempfile.TemporaryDirectory(prefix="l1-link-provenance-") as temp_dir:
            suffix = ".exe" if os.name == "nt" else ""
            executable = Path(temp_dir) / f"link_provenance_benchmark{suffix}"
            compile_harness(executable, repo_env)
            results: dict[str, dict[int, dict[str, object]]] = {}
            for shape in args.shapes:
                cells: dict[int, dict[str, object]] = {}
                results[shape] = cells
                for size in args.sizes:
                    print(f"bench_link_provenance: running {shape}/{size}", file=sys.stderr, flush=True)
                    cells[size] = summarize(
                        run_cell(executable, repo_env, shape, size, args.warmups, args.runs)
                    )
    except (OSError, RuntimeError) as exc:
        print(f"bench_link_provenance: {exc}", file=sys.stderr)
        return 1

    print_results(results)
    if args.compare is not None:
        try:
            print_comparison(args.compare, results)
        except RuntimeError as exc:
            print(f"bench_link_provenance: {exc}", file=sys.stderr)
            return 1
    document = {
        "schema": 1,
        "warmups": args.warmups,
        "runs": args.runs,
        "shapes": args.shapes,
        "sizes": args.sizes,
        "results": results,
    }
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"bench_link_provenance: wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
