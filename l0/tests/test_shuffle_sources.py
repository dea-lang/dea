#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for the monorepo `shuffle-sources` helper."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


L0_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = L0_ROOT.parent
SCRIPT = REPO_ROOT / "scripts" / "shuffle_sources.py"


def fail(message: str) -> None:
    raise SystemExit(f"test_shuffle_sources: FAIL: {message}")


def source_files(root: str, pattern: str, *, excluded_parts: set[str] | None = None) -> set[str]:
    """Return regular source files below one registered root.

    Args:
        root: Repository-relative root directory.
        pattern: Recursive glob pattern to select eligible files.
        excluded_parts: Path components that exclude a matched file.

    Returns:
        Normalized monorepo-relative POSIX paths.
    """
    excluded_parts = excluded_parts or set()
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / root).rglob(pattern)
        if path.is_file() and not (set(path.relative_to(REPO_ROOT).parts) & excluded_parts)
    }


def top_level_source_files(root: str, pattern: str) -> set[str]:
    """Return regular source files directly below one registered root.

    Args:
        root: Repository-relative root directory.
        pattern: Non-recursive glob pattern to select eligible files.

    Returns:
        Normalized monorepo-relative POSIX paths.
    """
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / root).glob(pattern)
        if path.is_file()
    }


def expected_pools() -> dict[str, set[str]]:
    """Build the approved production-source pools from the live tree.

    Returns:
        Source-path sets keyed by level and stage.
    """
    l0_stage1 = source_files(
        "l0/compiler/stage1_py",
        "*.py",
        excluded_parts={"tests", "__pycache__"},
    )
    l0_stage2 = source_files("l0/compiler/stage2_l0/src", "*.l0")
    l0_stage2 |= source_files("l0/compiler/stage2_l0/support", "*.c")
    l0_stage2.add("l0/compiler/stage2_l0/scripts/check_trace_log.py")
    l0_shared = source_files("l0/compiler/shared/l0/stdlib", "*.l0")
    l0_shared |= top_level_source_files("l0/compiler/shared/runtime", "*.h")

    l1_stage1 = source_files("l1/compiler/stage1_l0/src", "*.l0")
    l1_stage1 |= source_files("l1/compiler/stage1_l0/support", "*.c")
    l1_stage2 = source_files("l1/compiler/stage2_l1/src", "*.l1")
    l1_shared = source_files("l1/compiler/shared/l1/stdlib", "*.l1")
    l1_shared |= source_files("l1/compiler/shared/runtime", "*.c")
    l1_shared |= source_files("l1/compiler/shared/runtime", "*.h")

    return {
        "l0-s1": l0_stage1 | l0_shared,
        "l0-s2": l0_stage2 | l0_shared,
        "l0": l0_stage1 | l0_stage2 | l0_shared,
        "l1-s1": l1_stage1 | l1_shared,
        "l1-s2": l1_stage2 | l1_shared,
        "l1": l1_stage1 | l1_stage2 | l1_shared,
        "all": l0_stage1 | l0_stage2 | l0_shared | l1_stage1 | l1_stage2 | l1_shared,
    }


def run_cli(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    """Run the source selector from the requested working directory.

    Args:
        *args: CLI arguments after the script path.
        cwd: Working directory used to invoke the helper.

    Returns:
        Completed command result without raising for a nonzero status.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def require_success(*args: str, cwd: Path = REPO_ROOT) -> list[str]:
    """Run one valid selector command and return its output paths.

    Args:
        *args: CLI arguments after the script path.
        cwd: Working directory used to invoke the helper.

    Returns:
        Output paths, one per standard-output line.
    """
    completed = run_cli(*args, cwd=cwd)
    if completed.returncode != 0:
        fail(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed.stdout.splitlines()


def assert_normalized_source_paths(paths: list[str], pool: set[str], *, context: str) -> None:
    """Validate one selector output against its registered production pool.

    Args:
        paths: Paths emitted by the helper.
        pool: Eligible monorepo-relative source paths.
        context: Label included in failure output.
    """
    if len(paths) != len(set(paths)):
        fail(f"duplicate paths in {context}: {paths!r}")
    unexpected = set(paths) - pool
    if unexpected:
        fail(f"unexpected paths in {context}: {sorted(unexpected)!r}")

    for raw_path in paths:
        if "\\" in raw_path:
            fail(f"non-POSIX path in {context}: {raw_path!r}")
        path = PurePosixPath(raw_path)
        if raw_path != path.as_posix() or path.is_absolute() or "." in path.parts or ".." in path.parts:
            fail(f"non-normalized relative path in {context}: {raw_path!r}")
        source_path = REPO_ROOT.joinpath(*path.parts)
        if not source_path.is_file():
            fail(f"selected path does not exist in {context}: {raw_path!r}")


def assert_full_pool(scope: tuple[str, ...], pool: set[str], *, sentinels: set[str]) -> None:
    """Assert that a full-size scope selection covers exactly its source pool.

    Args:
        scope: Optional level and stage CLI arguments.
        pool: Expected eligible source paths.
        sentinels: Known source paths that must remain eligible.
    """
    if not pool:
        fail(f"expected nonempty source pool for {' '.join(scope) or 'default'}")
    paths = require_success(str(len(pool)), *scope)
    context = " ".join(scope) or "default"
    if len(paths) != len(pool):
        fail(f"expected {len(pool)} paths in {context}, got {len(paths)}")
    assert_normalized_source_paths(paths, pool, context=context)
    if set(paths) != pool:
        missing = sorted(pool - set(paths))
        unexpected = sorted(set(paths) - pool)
        fail(f"wrong full pool for {context}: missing={missing!r}, unexpected={unexpected!r}")
    missing_sentinels = sentinels - set(paths)
    if missing_sentinels:
        fail(f"missing known sources in {context}: {sorted(missing_sentinels)!r}")


def assert_expected_failure(*args: str) -> None:
    """Assert that one invalid selector invocation reports an argparse error.

    Args:
        *args: CLI arguments after the script path.
    """
    completed = run_cli(*args)
    if completed.returncode == 0:
        fail(f"expected command to fail: {' '.join(args)}")
    if completed.returncode != 2:
        fail(f"expected argparse exit status 2 for {' '.join(args)}, got {completed.returncode}")
    if completed.stdout:
        fail(f"unexpected standard output from invalid command {' '.join(args)}: {completed.stdout!r}")
    if "error:" not in completed.stderr.lower():
        fail(f"expected argparse-style error for {' '.join(args)}: {completed.stderr!r}")


def main() -> int:
    """Exercise valid scope selection and invalid CLI inputs."""
    pools = expected_pools()
    l0_stage1_sentinel = "l0/compiler/stage1_py/l0_c_emitter.py"
    l0_stage2_sentinel = "l0/compiler/stage2_l0/src/analysis.l0"
    l0_stage2_support_sentinel = (
        "l0/compiler/stage2_l0/support/compiler_filesystem.c"
    )
    l0_shared_sentinel = "l0/compiler/shared/l0/stdlib/std/io.l0"
    l1_stage1_sentinel = "l1/compiler/stage1_l0/src/analysis.l0"
    l1_stage1_support_sentinel = (
        "l1/compiler/stage1_l0/support/interface_fingerprint.c"
    )
    l1_shared_sentinel = "l1/compiler/shared/l1/stdlib/std/io.l1"

    for sentinel in (
        l0_stage1_sentinel,
        l0_stage2_sentinel,
        l0_stage2_support_sentinel,
        l0_shared_sentinel,
        l1_stage1_sentinel,
        l1_stage1_support_sentinel,
        l1_shared_sentinel,
    ):
        if sentinel not in pools["all"]:
            fail(f"known source unexpectedly absent from test pool: {sentinel}")

    default_paths = require_success("3")
    if len(default_paths) != 3:
        fail(f"expected three default paths, got {len(default_paths)}")
    assert_normalized_source_paths(default_paths, pools["all"], context="default")

    assert_full_pool(
        ("l0", "s1"),
        pools["l0-s1"],
        sentinels={l0_stage1_sentinel, l0_shared_sentinel},
    )
    assert_full_pool(
        ("L0", "S2"),
        pools["l0-s2"],
        sentinels={
            l0_stage2_sentinel,
            l0_stage2_support_sentinel,
            l0_shared_sentinel,
        },
    )
    assert_full_pool(
        ("l1", "s1"),
        pools["l1-s1"],
        sentinels={
            l1_stage1_sentinel,
            l1_stage1_support_sentinel,
            l1_shared_sentinel,
        },
    )
    assert_full_pool(("L1", "S2"), pools["l1-s2"], sentinels={l1_shared_sentinel})

    l1_paths = require_success("1", "l1")
    if len(l1_paths) != 1:
        fail(f"expected one L1 path, got {len(l1_paths)}")
    assert_normalized_source_paths(l1_paths, pools["l1"], context="L1")

    with tempfile.TemporaryDirectory(prefix="shuffle-sources.") as temporary_directory:
        outside_paths = require_success("1", "L0", "S1", cwd=Path(temporary_directory))
    if len(outside_paths) != 1:
        fail(f"expected one path outside the repository root, got {len(outside_paths)}")
    assert_normalized_source_paths(outside_paths, pools["l0-s1"], context="outside repository root")

    assert_expected_failure("0")
    assert_expected_failure("-1")
    assert_expected_failure("not-a-number")
    assert_expected_failure("1", "L2")
    assert_expected_failure("1", "L0", "S3")
    assert_expected_failure("1", "S1")
    assert_expected_failure("1", "L0", "S1", "extra")
    assert_expected_failure(str(len(pools["l0-s1"]) + 1), "L0", "S1")

    print("test_shuffle_sources: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
