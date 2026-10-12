# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Select portable example sources and supporting files for installed L1 packages."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import stat

REQUIRED_EXAMPLES = {
    "examples/hello.l1", "examples/demo.l1", "examples/slices.l1", "examples/hamurabi.l1",
    "examples/make/main.l1", "examples/make/support.l1", "examples/make/Makefile", "examples/make/README.md",
}


def is_example_path(path: str) -> bool:
    """Return whether a canonical package path names shippable example content.

    Args:
        path: Canonical POSIX-style package-relative path.

    Returns:
        Whether the path selects an example source, guide, or Makefile.
    """
    parts = PurePosixPath(path).parts
    return (len(parts) >= 2 and parts[0] == "examples"
            and not any(part.startswith(".") or part in {"build", "__pycache__"} for part in parts[1:])
            and (parts[-1] == "Makefile" or PurePosixPath(path).suffix in {".l1", ".md"}))


def snapshot_examples(root: Path) -> dict[str, bytes]:
    """Capture example sources, Markdown, and Makefiles without local build output.

    Args:
        root: L1 source root containing the examples directory.

    Returns:
        Package-relative names mapped to captured file bytes.

    Raises:
        ValueError: Required examples are absent or selected inputs are not ordinary files/directories.
        OSError: Selected example content cannot be read.
    """
    base = root / "examples"
    if base.is_symlink() or not base.is_dir():
        raise ValueError(f"missing ordinary examples directory: {base}")
    selected = {}
    for current, directories, files in os.walk(base, followlinks=False):
        directories[:] = sorted(name for name in directories
                                if not name.startswith(".") and name not in {"build", "__pycache__"})
        for name in directories:
            if (Path(current) / name).is_symlink():
                raise ValueError(f"linked example directory: {Path(current) / name}")
        for name in sorted(files):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if is_example_path(relative):
                if not stat.S_ISREG(path.lstat().st_mode):
                    raise ValueError(f"example input must be an ordinary file: {path}")
                selected[relative] = path.read_bytes()
    if not REQUIRED_EXAMPLES <= selected.keys():
        raise ValueError(f"missing required examples: {sorted(REQUIRED_EXAMPLES - selected.keys())}")
    return dict(sorted(selected.items()))
