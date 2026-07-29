#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Print a random selection of Dea compiler production source files."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import random


@dataclass(frozen=True)
class SourceGroup:
    """One dynamically discovered production-source group.

    Attributes:
        level: Canonical language-level name such as ``l0``.
        stage: Compiler stage number, or ``None`` for level-shared sources.
        patterns: Repository-root-relative glob patterns for eligible files.
    """

    level: str
    stage: int | None
    patterns: tuple[str, ...]


SOURCE_GROUPS = (
    SourceGroup("l0", 1, ("l0/compiler/stage1_py/**/*.py",)),
    SourceGroup(
        "l0",
        2,
        (
            "l0/compiler/stage2_l0/src/**/*.l0",
            "l0/compiler/stage2_l0/support/**/*.c",
            "l0/compiler/stage2_l0/scripts/check_trace_log.py",
        ),
    ),
    SourceGroup(
        "l0",
        None,
        (
            "l0/compiler/shared/l0/stdlib/**/*.l0",
            "l0/compiler/shared/runtime/*.h",
        ),
    ),
    SourceGroup(
        "l1",
        1,
        (
            "l1/compiler/stage1_l0/src/**/*.l0",
            "l1/compiler/stage1_l0/support/**/*.c",
        ),
    ),
    SourceGroup("l1", 2, ("l1/compiler/stage2_l1/src/**/*.l1",)),
    SourceGroup(
        "l1",
        None,
        (
            "l1/compiler/shared/l1/stdlib/**/*.l1",
            "l1/compiler/shared/runtime/**/*.c",
            "l1/compiler/shared/runtime/**/*.h",
        ),
    ),
)
SUPPORTED_LEVELS = frozenset(group.level for group in SOURCE_GROUPS)
STAGE_ALIASES = {"s1": 1, "s2": 2}
EXCLUDED_PATH_PARTS = frozenset({"tests", "fixtures", "__pycache__", "build", "dist"})


def repository_root() -> Path:
    """Return the monorepo root derived from this script's location.

    Returns:
        Absolute path to the Dea monorepo root.
    """

    return Path(__file__).resolve().parents[1]


def parse_count(value: str) -> int:
    """Parse one strictly positive source-count argument.

    Args:
        value: Raw command-line count text.

    Returns:
        Parsed positive count.

    Raises:
        argparse.ArgumentTypeError: If ``value`` is not a positive integer.
    """

    try:
        count = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("COUNT must be a positive integer") from error
    if count <= 0:
        raise argparse.ArgumentTypeError("COUNT must be a positive integer")
    return count


def parse_level(value: str) -> str:
    """Normalize one language-level argument.

    Args:
        value: Raw command-line level text.

    Returns:
        Canonical lowercase level name.

    Raises:
        argparse.ArgumentTypeError: If the level is unsupported.
    """

    level = value.casefold()
    if level not in SUPPORTED_LEVELS:
        expected = ", ".join(sorted(name.upper() for name in SUPPORTED_LEVELS))
        raise argparse.ArgumentTypeError(f"LEVEL must be one of: {expected}")
    return level


def parse_stage(value: str) -> int:
    """Normalize one compiler-stage argument.

    Args:
        value: Raw command-line stage text.

    Returns:
        Numeric compiler stage.

    Raises:
        argparse.ArgumentTypeError: If the stage is unsupported.
    """

    stage = STAGE_ALIASES.get(value.casefold())
    if stage is None:
        expected = ", ".join(alias.upper() for alias in STAGE_ALIASES)
        raise argparse.ArgumentTypeError(f"STAGE must be one of: {expected}")
    return stage


def group_matches_scope(group: SourceGroup, level: str | None, stage: int | None) -> bool:
    """Return whether one source group belongs to the requested scope.

    Args:
        group: Candidate source group.
        level: Optional canonical level filter.
        stage: Optional stage filter.

    Returns:
        ``True`` when ``group`` belongs to the requested scope.
    """

    if level is not None and group.level != level:
        return False
    if stage is None:
        return True
    return group.stage is None or group.stage == stage


def is_excluded(relative_path: Path) -> bool:
    """Return whether one candidate path lives below an excluded directory.

    Args:
        relative_path: Repository-root-relative candidate path.

    Returns:
        ``True`` when the path is not a production source.
    """

    return any(part in EXCLUDED_PATH_PARTS for part in relative_path.parts)


def discover_sources(repo_root: Path, *, level: str | None = None, stage: int | None = None) -> list[Path]:
    """Dynamically discover production sources for one optional scope.

    Args:
        repo_root: Monorepo root to scan.
        level: Optional canonical level filter.
        stage: Optional compiler-stage filter. Shared sources are included when
            a stage is supplied.

    Returns:
        Sorted, deduplicated repository-root-relative source paths.

    Raises:
        ValueError: If the scope uses an unsupported level or stage, or gives
            a stage without a level.
    """

    if level is not None and level not in SUPPORTED_LEVELS:
        raise ValueError(f"unsupported level: {level}")
    if stage is not None and stage not in STAGE_ALIASES.values():
        raise ValueError(f"unsupported stage: {stage}")
    if stage is not None and level is None:
        raise ValueError("a stage scope requires a level")

    sources: set[Path] = set()
    for group in SOURCE_GROUPS:
        if not group_matches_scope(group, level, stage):
            continue
        for pattern in group.patterns:
            for path in repo_root.glob(pattern):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(repo_root)
                if not is_excluded(relative_path):
                    sources.add(relative_path)
    return sorted(sources, key=Path.as_posix)


def choose_sources(sources: Sequence[Path], count: int) -> list[Path]:
    """Choose distinct source paths with a fresh system-random sample.

    Args:
        sources: Eligible source paths.
        count: Number of paths to select.

    Returns:
        Randomly ordered, distinct selected paths.
    """

    return random.SystemRandom().sample(sources, count)


def scope_label(level: str | None, stage: int | None) -> str:
    """Return a concise display label for one source scope.

    Args:
        level: Optional canonical level filter.
        stage: Optional compiler-stage filter.

    Returns:
        Human-readable scope label.
    """

    if level is None:
        return "all levels"
    if stage is None:
        return level.upper()
    return f"{level.upper()} S{stage}"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for source selection.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Without a scope, select from every supported level. A stage scope "
            "also includes production sources shared by its level."
        ),
    )
    parser.add_argument("count", metavar="COUNT", type=parse_count, help="Number of distinct files to print.")
    parser.add_argument(
        "level",
        metavar="LEVEL",
        nargs="?",
        type=parse_level,
        help="Optional language level: L0 or L1.",
    )
    parser.add_argument(
        "stage",
        metavar="STAGE",
        nargs="?",
        type=parse_stage,
        help="Optional compiler stage for LEVEL: S1 or S2.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the source-selection command-line interface.

    Args:
        argv: Optional command-line arguments excluding the program name.

    Returns:
        Process-style exit code.
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    sources = discover_sources(repository_root(), level=args.level, stage=args.stage)
    if args.count > len(sources):
        parser.error(
            f"requested {args.count} source file(s) for {scope_label(args.level, args.stage)}, "
            f"but only {len(sources)} eligible source file(s) were found"
        )
    for source in choose_sources(sources, args.count):
        print(source.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
