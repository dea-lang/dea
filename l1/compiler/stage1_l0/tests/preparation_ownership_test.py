#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Trace native selection with deterministic automatic and runtime-override inputs."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile

TESTS_DIR = Path(__file__).resolve().parent
RUNNER_DIR = TESTS_DIR.parent / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from run_trace_tests import run_one
from test_runner_common import require_repo_stage1_test_env


def main() -> int:
    """Run both optional-string ownership paths and retain artifacts on failure."""

    python, _, build_dir, env = require_repo_stage1_test_env("preparation_ownership_test")
    # Set these after sanitization: ordinary runners deliberately remove runtime
    # overrides, and an ambient L1_CC would bypass automatic executable discovery.
    env.pop("L1_CC", None)
    env["L1_RUNTIME_LIB"] = str(build_dir / "lib")
    artifacts = Path(tempfile.mkdtemp(prefix="l1_preparation_ownership."))
    result = run_one(0, "preparation_test", TESTS_DIR / "preparation_test.l0", artifacts, 5, python, env)
    if result.status != "TRACE_OK":
        print(f"preparation_ownership_test: FAIL: {result.status}\n{result.failure_excerpt}{result.report_text}")
        print(f"Artifacts: {artifacts}")
        return 1
    for field in ("errors=0", "leaked_object_ptrs=0", "leaked_string_ptrs=0"):
        assert field in result.report_text, (field, result.report_text, artifacts)
    shutil.rmtree(artifacts)
    print("preparation_ownership_test: PASS: automatic compiler and runtime override have balanced ownership")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
