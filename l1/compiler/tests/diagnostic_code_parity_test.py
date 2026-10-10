#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Check the independently owned L1 diagnostic-code contract fixtures."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from support.compiler_subject import selected_compiler


REPO_ROOT = Path(__file__).resolve().parents[3]
L1_ROOT = REPO_ROOT / "l1"


def main() -> int:
    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    compiler = selected_compiler(build_dir / "bin" / "l1c")
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "diagnostic_parity.py"),
         "--stage", "l1", "--compiler", str(compiler)],
        cwd=REPO_ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
