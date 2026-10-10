#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Run the two-phase Linux L2 isolation gate with an explicit installed L1 prefix."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    """Build isolated implementation and bootstrap-free operation images.

    Returns:
        Docker's validation result.
    """
    prefix_text = os.environ.get("L2_ISOLATION_BOOTSTRAP_PREFIX", "").strip()
    if not prefix_text:
        print("set L2_ISOLATION_BOOTSTRAP_PREFIX to an installed Linux L1 prefix", file=sys.stderr)
        return 2
    prefix = Path(prefix_text).expanduser().resolve()
    if not (prefix / "share/dea/l1/install-manifest.json").is_file():
        print("isolation requires a complete installed Linux L1 prefix", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[2]
    # A separate build context carries only the installed upstream toolchain.
    # The Dockerfile's COPY allowlist excludes all sibling levels and artifacts.
    command = ["docker", "build", "--progress=plain", "--build-context", f"bootstrap={prefix}",
               "--target", "operation", "-f", str(root / "l2/Dockerfile"), "-t", "dea-l2-isolation", str(root)]
    return subprocess.run(command, check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main())
