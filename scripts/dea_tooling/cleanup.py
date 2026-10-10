#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Validate and remove level-owned development artifacts without a bootstrap."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePath
import shutil
import sys


# These namespaces contain repository inputs, never disposable build trees.
PROTECTED_ROOTS = frozenset({
    "compiler", "docker", "docs", "examples", "scripts", "tests", "work",
    "tools", "editors", "l0", "l1", "l2",
})


def validate_relative_directory(relative: PurePath) -> None:
    """Reject root, traversal, hidden, and source-owned build namespaces.

    Args:
        relative: Host-native or synthetic relative path inside one level.

    Raises:
        ValueError: The path is not a disposable build namespace.
    """
    parts = relative.parts
    if (relative.anchor or not parts or ".." in parts
            or parts[0].startswith(".") or parts[0].casefold() in PROTECTED_ROOTS):
        raise ValueError(f"unsafe build directory: {relative}")


def validate_build_directory(root: Path, text: str) -> Path:
    """Validate a cleanup directory without following directory aliases.

    Args:
        root: Owning language-level directory.
        text: Explicit absolute or level-relative build directory.

    Returns:
        Absolute validated path within the level.

    Raises:
        ValueError: The directory is empty, outside the level, protected, or aliased.
        OSError: Filesystem inspection fails.
    """
    if not text.strip():
        raise ValueError("build directory must not be empty")
    root = root.resolve()
    raw = Path(text)
    if ".." in raw.parts:
        raise ValueError(f"build directory must not contain parent traversal: {text}")
    path = raw if raw.is_absolute() else root / raw
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"build directory must be inside {root}: {text}") from exc
    validate_relative_directory(relative)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"build directory must not traverse an alias: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"build directory must be a directory: {current}")
    return path


def remove_path(path: Path) -> None:
    """Remove a generated entry, unlinking aliases and tolerating absence only.

    Args:
        path: Validated generated entry to remove.

    Raises:
        OSError: Deletion fails for any reason other than an absent entry.
    """
    try:
        if path.is_symlink():
            path.unlink()
        elif path.is_junction():
            path.rmdir()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except FileNotFoundError:
        # rmtree can fail on a missing descendant; suppress only an absent root.
        if path.exists() or path.is_symlink():
            raise


def clean_level(root: Path, mode: str, build_dir: str) -> None:
    """Preflight the complete operation, then remove only its generated entries.

    Args:
        root: Owning language-level directory.
        mode: clean, clean-all, clean-build, or clean-runtime.
        build_dir: Selected build directory for nonstandard cleanup modes.

    Raises:
        ValueError: A cleanup path or mode is invalid.
        OSError: Inspection or deletion fails.
    """
    root = root.resolve()
    selected = None
    if mode not in {"clean", "clean-all", "clean-build", "clean-runtime"}:
        raise ValueError(f"unknown cleanup mode: {mode}")
    if mode != "clean":
        selected = validate_build_directory(root, build_dir)
    operations = []
    if mode in {"clean", "clean-all"}:
        standard = validate_build_directory(root, "build")
        if standard.exists():
            operations.append((f"contents of {str(standard)!r} (including hidden entries)",
                               sorted(standard.iterdir())))
        # Source directories are never removed. Reject aliases in parents of
        # transient files so a checkout symlink cannot redirect their cleanup.
        for relative in (".", "compiler", "compiler/tests", "compiler/stage2_l0",
                         "compiler/stage2_l0/tests"):
            parent = root
            for part in Path(relative).parts:
                parent /= part
                if parent.is_symlink() or parent.is_junction():
                    raise ValueError(f"temporary-file parent must not be an alias: {parent}")
                if parent.exists() and not parent.is_dir():
                    raise ValueError(f"temporary-file parent must be a directory: {parent}")
            for name in ("a.out", "a.exe"):
                executable = parent / name
                if executable.is_dir() and not executable.is_symlink():
                    raise ValueError(f"temporary executable must not be a directory: {executable}")
                operations.append((repr(str(executable)), [executable]))
            if relative.endswith("tests"):
                # Preserve unexpected directories matching the old file glob.
                temporary = sorted(p for p in parent.glob(".tmp*") if p.is_symlink() or p.is_file())
                operations.append((f"files matching {str(parent / '.tmp*')!r}", temporary))
    if mode in {"clean-all", "clean-build"}:
        operations.append((repr(str(selected)), [selected]))
    elif mode == "clean-runtime":
        for name in ("runtime", "lib"):
            entry = selected / name
            operations.append((repr(str(entry)), [entry]))
        include = selected / "include"
        if include.is_symlink() or include.is_junction():
            raise ValueError(f"runtime include directory must not be an alias: {include}")
        if include.exists() and not include.is_dir():
            raise ValueError(f"runtime include directory must be a directory: {include}")
        for name in ("dea_rt.h", "l1_real.h"):
            entry = include / name
            operations.append((repr(str(entry)), [entry]))
    removed = False
    for description, entries in operations:
        existing = []
        for entry in entries:
            try:
                entry.lstat()
            except FileNotFoundError:
                continue
            existing.append(entry)
        if not existing:
            continue
        print(f"cleanup: removing {description}", flush=True)
        for entry in existing:
            remove_path(entry)
        removed = True
    if not removed:
        print("cleanup: nothing to remove", flush=True)


def main() -> int:
    """Run the cleanup CLI and report filesystem failures as a nonzero exit.

    Returns:
        Zero on success, one on validation or deletion failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("clean", "clean-all", "clean-build", "clean-runtime"))
    parser.add_argument("--build-variable", required=True)
    args = parser.parse_args()
    try:
        clean_level(Path.cwd(), args.mode, os.environ.get(args.build_variable, ""))
    except (ValueError, OSError) as exc:
        print(f"cleanup: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
