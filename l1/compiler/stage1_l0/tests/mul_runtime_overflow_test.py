#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Check multiplication overflow with the already-built L1 subject compiler."""

from pathlib import Path
import subprocess

from l1c_stage1_compile_only_test import L1_ROOT, stage1_compiler
from support.driver_inputs import native_driver_args


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mul_runtime"
OVERFLOW_CASES = (
    "mul_overflow_positive",
    "mul_overflow_max_times_two",
    "mul_overflow_large",
    "mul_overflow_negative",
    "mul_underflow_mixed",
    "mul_int32_min_times_minus_one",
)


def main() -> int:
    """Require every overflow fixture to fail through the runtime panic path.

    Returns:
        Zero after all six positive, negative, and mixed-sign cases pass.

    Raises:
        AssertionError: If a fixture succeeds or fails before the expected panic.
    """

    compiler = stage1_compiler()
    for name in OVERFLOW_CASES:
        result = subprocess.run(
            [str(compiler), *native_driver_args(compiler), "--run",
             "--project-root", str(FIXTURES), name],
            cwd=L1_ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False,
        )
        assert result.returncode != 0 and "Software Failure: integer multiplication overflow" in result.stderr, (
            name, result.returncode, result.stdout, result.stderr,
        )
        print(f"{name}: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
