# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Explicit subject selection for integration tests shared by the L2 compiler."""

import os
from pathlib import Path


def selected_compiler(default: Path) -> Path:
    """Return the runner-selected compiler, or the existing canonical compiler default."""
    override = os.environ.get("L2_TEST_COMPILER")
    return Path(override).resolve() if override else default


def selected_native(default: Path) -> Path:
    """Return the selected native artifact for isolated toolchain fixtures."""
    override = os.environ.get("L2_TEST_COMPILER")
    if not override:
        return default
    selected = Path(override).resolve()
    if selected.suffix == ".native":
        return selected
    return selected.with_suffix(".native")
