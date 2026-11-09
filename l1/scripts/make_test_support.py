#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Select GNU Make for compiler composition and adapter tests."""

import os
from pathlib import Path
import re
import shutil
import subprocess


def _supports_grouped_targets(executable: str) -> bool:
    """Check the selected executable's GNU Make version.

    Args:
        executable: Resolved executable to inspect.

    Returns:
        Whether the executable successfully identifies as GNU Make 4.3 or newer.
    """
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    version = re.search(r"^GNU Make (\d+)\.(\d+)", result.stdout, re.MULTILINE)
    return result.returncode == 0 and version is not None and tuple(map(int, version.groups())) >= (4, 3)


def find_gnu_make(*, windows: bool | None = None) -> str | None:
    """Select an explicit Make or the first compatible platform-preferred candidate.

    Windows prefers ``make`` so an MSYS2 environment selects its own tool before
    a separately installed native ``gmake``. Other hosts prefer ``gmake`` because
    macOS system Make predates grouped targets. CI can pin the exact executable
    with ``DEA_TEST_MAKE``; an invalid explicit selection never falls back.

    Args:
        windows: Explicit platform policy for portable selection tests.

    Returns:
        An absolute compatible executable path, or None when no implicit
        candidate supports GNU Make 4.3 or newer.

    Raises:
        ValueError: DEA_TEST_MAKE names an unavailable or incompatible executable.
    """
    if windows is None:
        windows = os.name == "nt"
    selected = os.environ.get("DEA_TEST_MAKE")
    candidates = [selected] if selected is not None else (["make", "gmake"] if windows else ["gmake", "make"])
    for candidate in candidates:
        executable = shutil.which(candidate) if candidate else None
        if executable is not None and _supports_grouped_targets(executable):
            return str(Path(executable).absolute())
    if selected is not None:
        raise ValueError(f"DEA_TEST_MAKE={selected!r} must select an executable GNU Make 4.3 or newer")
    return None
