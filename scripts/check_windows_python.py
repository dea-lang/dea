#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Reject accidental exchange of native tooling and MSYS2 test interpreters."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import sysconfig


def validate_family(family: str, *, os_name: str, platform: str, prefix: Path,
                    base_prefix: Path, root: Path) -> None:
    """Validate the interpreter family and the MSYS2 temporary environment.

    Args:
        family: Required native or MSYS2 interpreter family.
        os_name: Interpreter operating-system identity.
        platform: Interpreter sysconfig platform identity.
        prefix: Interpreter environment prefix.
        base_prefix: Interpreter base installation prefix.
        root: Checkout that must not contain the MSYS2 test environment.

    Raises:
        ValueError: The selected interpreter violates the environment boundary.
    """
    mingw = platform.startswith("mingw")
    if os_name != "nt" or mingw != (family == "msys2"):
        raise ValueError(f"expected {family} Windows Python, found {os_name}/{platform}")
    if family == "msys2":
        if "ucrt" not in platform:
            raise ValueError("Stage 1 compatibility coverage requires UCRT64 Python")
        if prefix == base_prefix or prefix.is_relative_to(root):
            raise ValueError("MSYS2 tests require a separate virtual environment outside the checkout")


def main() -> int:
    """Validate the running interpreter and report its explicit identity.

    Returns:
        Zero for a compatible interpreter, or one for a rejected selection.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=("native", "msys2"))
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 14):
            raise ValueError("Python 3.14+ is required")
        validate_family(args.family, os_name=os.name, platform=sysconfig.get_platform(),
                        prefix=Path(sys.prefix).resolve(), base_prefix=Path(sys.base_prefix).resolve(),
                        root=Path(__file__).resolve().parents[1])
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{args.family} Python: {sys.executable}; {sys.version.split()[0]}; {sysconfig.get_platform()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
