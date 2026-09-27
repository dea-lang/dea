# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Explicit subject selection for integration tests shared by the L1 stages."""

import os
from pathlib import Path


def selected_compiler(default: Path) -> Path:
    """Return the runner-selected compiler, or the existing Stage 1 default."""
    override = os.environ.get("L1_TEST_COMPILER")
    return Path(override).resolve() if override else default


def selected_native(default: Path) -> Path:
    """Return the selected native artifact for isolated toolchain fixtures."""
    override = os.environ.get("L1_TEST_COMPILER")
    if not override:
        return default
    selected = Path(override).resolve()
    if selected.suffix == ".native":
        return selected
    return selected.with_suffix(".native")
