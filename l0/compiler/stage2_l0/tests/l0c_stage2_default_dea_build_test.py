#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for isolated default Dea build artifact shape."""

from __future__ import annotations

import shutil

from tool_test_common import (
    BUILD_TESTS_ROOT,
    ToolTestFailure,
    assert_file,
    assert_no_file,
    build_stage2,
    clean_env,
    make_temp_dir,
    resolve_tool,
    run,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_default_dea_build_test: FAIL: {message}")
    return 1


def main() -> int:
    """Program entrypoint."""

    test_dea_build = make_temp_dir("l0_stage2_default_dea_build.", BUILD_TESTS_ROOT)
    try:
        build_stage2(test_dea_build)
        l0c = resolve_tool(test_dea_build / "bin", "l0c-stage2")
        native = resolve_tool(test_dea_build / "bin", "l0c-stage2.native")
        assert_file(l0c)
        assert_file(native)
        assert_no_file(test_dea_build / "bin" / "l0c-stage2.c")
        run([l0c, "--check", "--project-root", "examples", "hello"], env=clean_env())
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        shutil.rmtree(test_dea_build, ignore_errors=True)

    print("l0c_stage2_default_dea_build_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
