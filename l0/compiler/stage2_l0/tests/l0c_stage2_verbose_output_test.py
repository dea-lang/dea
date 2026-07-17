#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for Stage 2 verbose output."""

from __future__ import annotations

import os
import re
import shutil

from tool_test_common import (
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_empty,
    assert_matches,
    assert_not_contains,
    build_stage2,
    clean_env,
    is_windows_host,
    make_temp_dir,
    native_path,
    run_to_files,
    stage2_launcher_path,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_verbose_output_test: FAIL: {message}")
    return 1


def main() -> int:
    """Program entrypoint."""

    fixture_root = REPO_ROOT / "compiler" / "stage2_l0" / "tests" / "fixtures" / "driver"
    tmp_dir = make_temp_dir("l0c-stage2-verbose-test.")
    try:
        dea_build_dir = tmp_dir / "dea"
        build_stage2(dea_build_dir)
        l0c = stage2_launcher_path(dea_build_dir / "bin" / "l0c-stage2")

        if is_windows_host():
            system_root_expected = f"{native_path(REPO_ROOT / 'compiler')}/shared/l0/stdlib"
        else:
            system_root_expected = str(REPO_ROOT / "compiler" / "shared" / "l0" / "stdlib")
        fixture_root_expected = native_path(fixture_root)
        examples_root_expected = native_path(REPO_ROOT / "examples")
        expected_exe = "a.exe" if is_windows_host() else "a.out"

        v_stdout = tmp_dir / "v.stdout"
        v_stderr = tmp_dir / "v.stderr"
        run_to_files(
            [l0c, "-v", "--build", "--project-root", fixture_root_expected, "ok_main"],
            v_stdout,
            v_stderr,
            env=clean_env(),
        )
        assert_empty(v_stdout)
        assert_contains(v_stderr, "Dea language / L0 compiler")
        assert_contains(v_stderr, f"System root(s): '{system_root_expected}'")
        assert_contains(v_stderr, f"Project root(s): '{fixture_root_expected}'")
        assert_contains(v_stderr, "Starting analysis for entry module 'ok_main'")
        assert_contains(v_stderr, "Building compilation unit module 'ok_main'")
        assert_contains(v_stderr, "Resolving module-level names...")
        assert_contains(v_stderr, "Resolving type signatures...")
        assert_contains(v_stderr, "Resolving local scopes...")
        assert_contains(v_stderr, "Type-checking expressions...")
        assert_contains(v_stderr, "Analysis complete: 0 total diagnostic(s), 0 error(s)")
        assert_contains(v_stderr, "Generating C code...")
        assert_contains(v_stderr, "Generated C code: ")
        assert_contains(v_stderr, "Using C compiler: ")
        assert_contains(v_stderr, "Detected compiler flag family: ")
        assert_contains(v_stderr, "Adding optimization flag: ")
        assert_contains(v_stderr, "Compiling:")
        assert_matches(v_stderr, rf" -o {re.escape(expected_exe)}")
        assert_contains(v_stderr, f"Built executable: {expected_exe}")
        assert_not_contains(v_stderr, "Loading module 'ok_main'")
        assert_not_contains(v_stderr, "Preparing optional wrapper types")
        assert_not_contains(v_stderr, "already loaded (cache hit)")

        vvv_stdout = tmp_dir / "vvv.stdout"
        vvv_stderr = tmp_dir / "vvv.stderr"
        run_to_files(
            [l0c, "-vvv", "--build", "--project-root", fixture_root_expected, "ok_main"],
            vvv_stdout,
            vvv_stderr,
            env=clean_env(),
        )
        assert_empty(vvv_stdout)
        assert_contains(vvv_stderr, "Loading module 'ok_main'")
        assert_contains(vvv_stderr, f"Resolved 'ok_main' to {fixture_root_expected}/ok_main.l0")
        assert_contains(vvv_stderr, f"Lexing {fixture_root_expected}/ok_main.l0")
        assert_contains(vvv_stderr, f"Lexed 21 token(s) from {fixture_root_expected}/ok_main.l0")
        assert_contains(vvv_stderr, f"Parsing {fixture_root_expected}/ok_main.l0")
        assert_contains(vvv_stderr, f"Parsed module 'ok_main' from {fixture_root_expected}/ok_main.l0")
        assert_contains(vvv_stderr, "Loading module 'ok_dep1'")
        assert_contains(vvv_stderr, f"Lexed 18 token(s) from {fixture_root_expected}/ok_dep1.l0")
        assert_contains(vvv_stderr, "Loading module 'ok_leaf'")
        assert_contains(vvv_stderr, f"Lexed 15 token(s) from {fixture_root_expected}/ok_leaf.l0")
        assert_contains(vvv_stderr, "Loading module 'ok_dep2'")
        assert_contains(vvv_stderr, f"Lexed 15 token(s) from {fixture_root_expected}/ok_dep2.l0")
        assert_contains(vvv_stderr, "Module 'ok_dep1' already loaded (cache hit)")
        assert_contains(vvv_stderr, "Module 'ok_leaf' already loaded (cache hit)")
        assert_contains(vvv_stderr, "Module 'ok_dep2' already loaded (cache hit)")
        assert_contains(vvv_stderr, "Compilation unit contains 4 module(s): ok_dep1, ok_dep2, ok_leaf, ok_main")
        assert_contains(vvv_stderr, "Name resolution produced 0 diagnostic(s)")
        assert_contains(vvv_stderr, "Signature resolution found 4 function(s), 0 struct(s), 0 enum(s), 0 let(s)")
        assert_contains(vvv_stderr, "Local scope resolution processed 4 function(s)")
        assert_contains(vvv_stderr, "Expression type checking produced 0 diagnostic(s)")
        assert_contains(vvv_stderr, "Preparing optional wrapper types")
        assert_contains(vvv_stderr, "Emitting header and forward declarations")
        assert_not_contains(vvv_stderr, "Generating module 'ok_main'")
        assert_not_contains(vvv_stderr, "already loaded (cached)")

        path_stdout = tmp_dir / "path.stdout"
        path_stderr = tmp_dir / "path.stderr"
        run_to_files(
            [l0c, "-vvv", native_path(REPO_ROOT / "examples" / "demo.l0")],
            path_stdout,
            path_stderr,
            env=clean_env(),
        )
        assert_empty(path_stdout)
        assert_contains(path_stderr, f"Project root(s): '{examples_root_expected}'")

        run_stdout = tmp_dir / "run.stdout"
        run_stderr = tmp_dir / "run.stderr"
        run_to_files(
            [l0c, "-v", "--run", "--project-root", fixture_root_expected, "ok_main"],
            run_stdout,
            run_stderr,
            env=clean_env(),
        )
        assert_empty(run_stdout)
        assert_contains(run_stderr, "Running: ")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        # The compiler writes the default executable in the repo root.
        for name in ("a.out", "a.exe", "a.out.c", "a.exe.c"):
            try:
                os.remove(REPO_ROOT / name)
            except FileNotFoundError:
                pass
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("l0c_stage2_verbose_output_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
