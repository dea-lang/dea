#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Logical L1 vector and Stage 1 token-vector bounds regressions."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from test_runner_common import repo_stage1_command, stage1_support_args


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
VECTOR_BOUNDS_MESSAGE = "Index out of bounds in vector access"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def l1_compiler_path() -> Path:
    """Return the repo-local L1 Stage 1 compiler launcher."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def run_l1_source(module_name: str, source: str) -> subprocess.CompletedProcess[str]:
    """Compile and run one temporary L1 source module."""

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l1").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )
        return subprocess.run(
            [
                str(l1_compiler_path()),
                "--project-root",
                str(project_root),
                "--run",
                module_name,
            ],
            cwd=L1_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def run_stage1_token_source(
    module_name: str, source: str
) -> subprocess.CompletedProcess[str]:
    """Compile and run one L0 harness against the Stage 1 compiler sources."""

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l0").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )
        return subprocess.run(
            [
                *repo_stage1_command(),
                "--project-root",
                str(project_root),
                "--project-root",
                "compiler/stage1_l0/src",
                "--run",
                *stage1_support_args(),
                module_name,
            ],
            cwd=L1_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def require_bounds_failure(
    module_name: str,
    source: str,
    *,
    token_harness: bool = False,
) -> None:
    """Require one source module to fail at the vector logical boundary."""

    if token_harness:
        completed = run_stage1_token_source(module_name, source)
    else:
        completed = run_l1_source(module_name, source)
    output = completed.stdout + completed.stderr
    if completed.returncode == 0:
        sys.stderr.write(output)
        raise AssertionError(f"{module_name} unexpectedly accepted a non-element slot")
    if VECTOR_BOUNDS_MESSAGE not in output:
        sys.stderr.write(output)
        raise AssertionError(
            f"{module_name} did not fail with {VECTOR_BOUNDS_MESSAGE!r}"
        )


def l1_vector_source(module_name: str, body: str) -> str:
    """Return one L1 vector-bound fixture source."""

    return f"""
        module {module_name};

        import std.vector;

        func main() -> int {{
            {body}
            return 0;
        }}
    """


def stage1_token_source(module_name: str, body: str) -> str:
    """Return one L0 Stage 1 token-bound fixture source."""

    return f"""
        module {module_name};

        import std.vector;
        import tokens;

        func main() -> int {{
            {body}
            return 0;
        }}
    """


def test_vector_bounds() -> None:
    """Exercise L1 logical bounds independently of backing-array capacity."""

    cases = {
        "vector_empty_check": """
            let vec = vec_create(sizeof(int), 4);
            vec_check(vec, 0);
        """,
        "vector_negative_get": """
            let vec = vec_create(sizeof(int), 4);
            vec_push_int(vec, 7);
            vec_get(vec, -1);
        """,
        "vector_at_length_get": """
            let vec = vec_create(sizeof(int), 8);
            vec_push_int(vec, 7);
            vec_get(vec, 1);
        """,
        "vector_cleared_get": """
            let vec = vec_create(sizeof(int), 4);
            vec_push_int(vec, 7);
            vec_clear(vec);
            vec_get(vec, 0);
        """,
        "vector_over_reserved_get": """
            let vec = vec_create(sizeof(int), 1);
            vec_reserve(vec, 64);
            vec_get(vec, 0);
        """,
        "vector_over_reserved_zap": """
            let vec = vec_create(sizeof(int), 1);
            vec_reserve(vec, 64);
            vec_zap(vec, 0);
        """,
    }
    for module_name, body in cases.items():
        require_bounds_failure(module_name, l1_vector_source(module_name, body))


def test_token_vector_bounds() -> None:
    """Exercise Stage 1 token access through the shared vector invariant."""

    cases = {
        "token_vector_empty_get": """
            let tv = tv_create();
            tv_get(tv, 0);
        """,
        "token_vector_at_length_get": """
            let tv = tv_create();
            tv_push(tv, Token(TT_EOF, 0, 1, 1));
            tv_get(tv, 1);
        """,
        "token_vector_cleared_get": """
            let tv = tv_create();
            tv_push(tv, Token(TT_EOF, 0, 1, 1));
            vec_clear(tv.vec);
            tv_get(tv, 0);
        """,
        "token_vector_over_reserved_get": """
            let tv = tv_create();
            vec_reserve(tv.vec, 64);
            tv_get(tv, 0);
        """,
    }
    for module_name, body in cases.items():
        require_bounds_failure(
            module_name,
            stage1_token_source(module_name, body),
            token_harness=True,
        )


def main() -> int:
    test_vector_bounds()
    test_token_vector_bounds()
    print("vector_logical_bounds_test: all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
