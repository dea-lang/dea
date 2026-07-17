#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end regression for Stage 2 `--ast` mode."""

from __future__ import annotations

import shutil

from tool_test_common import (
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_empty,
    assert_line_before,
    assert_matches,
    assert_not_contains,
    build_stage2,
    clean_env,
    make_temp_dir,
    native_path,
    run_to_files,
    stage2_launcher_path,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_ast_test: FAIL: {message}")
    return 1


def main() -> int:
    """Program entrypoint."""

    fixture_root = REPO_ROOT / "compiler" / "stage2_l0" / "tests" / "fixtures" / "driver"
    tmp_dir = make_temp_dir("l0c-stage2-ast-test.")
    try:
        dea_build_dir = tmp_dir / "dea"
        build_stage2(dea_build_dir)
        l0c = stage2_launcher_path(dea_build_dir / "bin" / "l0c-stage2")
        fixture_root_native = native_path(fixture_root)

        ast_stdout = tmp_dir / "ast.stdout"
        ast_stderr = tmp_dir / "ast.stderr"
        run_to_files(
            [l0c, "--ast", "--project-root", fixture_root_native, "ok_leaf"],
            ast_stdout,
            ast_stderr,
            env=clean_env(),
        )
        assert_not_contains(ast_stdout, "L0C-9510")
        assert_contains(ast_stdout, "Module(name='ok_leaf'")
        assert_contains(ast_stdout, "FuncDecl(")
        assert_contains(ast_stdout, "ReturnStmt(")

        all_stdout = tmp_dir / "all.stdout"
        all_stderr = tmp_dir / "all.stderr"
        run_to_files(
            [l0c, "--ast", "--all-modules", "--project-root", fixture_root_native, "ok_main"],
            all_stdout,
            all_stderr,
            env=clean_env(),
        )
        assert_not_contains(all_stdout, "L0C-9510")
        for module in ("ok_dep1", "ok_dep2", "ok_leaf", "ok_main"):
            assert_contains(all_stdout, f"=== Module {module} ===")
            assert_contains(all_stdout, f"Module(name='{module}'")
        assert_line_before(all_stdout, "=== Module ok_dep1 ===", "=== Module ok_dep2 ===")
        assert_line_before(all_stdout, "=== Module ok_dep2 ===", "=== Module ok_leaf ===")
        assert_line_before(all_stdout, "=== Module ok_leaf ===", "=== Module ok_main ===")
        assert_not_contains(ast_stdout, "L0C-9510")
        assert_not_contains(all_stdout, "L0C-9510")

        bad_stdout = tmp_dir / "bad.stdout"
        bad_stderr = tmp_dir / "bad.stderr"
        completed = run_to_files(
            [l0c, "--ast", "--project-root", fixture_root_native, "no_such_module_xyz"],
            bad_stdout,
            bad_stderr,
            env=clean_env(),
            expected_returncode=None,
        )
        if completed.returncode == 0:
            raise ToolTestFailure("bad target should fail")
        assert_not_contains(bad_stderr, "L0C-9510")
        assert_empty(bad_stdout)
        assert_matches(bad_stderr, r"\[.*\]")

        hello_stdout = tmp_dir / "hello.stdout"
        hello_stderr = tmp_dir / "hello.stderr"
        run_to_files(
            [l0c, "--ast", "--project-root", native_path(REPO_ROOT / "examples"), "hello"],
            hello_stdout,
            hello_stderr,
            env=clean_env(),
        )
        assert_contains(hello_stdout, "Module(name='hello'")
        assert_not_contains(hello_stdout, "L0C-9510")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("l0c_ast_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
