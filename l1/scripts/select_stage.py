#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Select the repo-local L1 compiler alias without rebuilding either stage."""

import argparse
import os

from build_stage1_l1c import normalize_l1_build_dir, write_relative_alias


def main() -> int:
    """Select an existing explicit stage artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("1", "2"))
    args = parser.parse_args()
    layout = normalize_l1_build_dir(os.environ.get("L1_BUILD_DIR", "build/dea"))
    target = f"l1c-stage{args.stage}"
    if not (layout.bin_dir / target).is_file():
        parser.error(f"missing {target}; run make build-stage{args.stage}")
    write_relative_alias(layout.bin_dir / "l1c", target)
    print(f"Selected {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
