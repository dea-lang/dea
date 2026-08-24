#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Logical vector and Stage 2 token-vector bounds regressions."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from test_runner_common import STAGE2_COMPILER_SUPPORT_SOURCE, source_tree_l0c_command


REPO_ROOT = Path(__file__).resolve().parents[4]
L0_ROOT = REPO_ROOT / "l0"
VECTOR_BOUNDS_MESSAGE = "Index out of bounds in vector access"


def run_source(
    module_name: str,
    source: str,
    *,
    project_roots: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Compile and run one temporary L0 source module."""

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l0").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )
        command = [
            *source_tree_l0c_command(),
            "--c-source",
            STAGE2_COMPILER_SUPPORT_SOURCE,
            "--project-root",
            str(project_root),
        ]
        for root in project_roots:
            command.extend(["--project-root", root])
        command.extend(["--run", module_name])
        return subprocess.run(
            command,
            cwd=L0_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def require_bounds_failure(
    module_name: str,
    body: str,
    *,
    imports: str = "import std.vector;",
    project_roots: tuple[str, ...] = (),
) -> None:
    """Require one source module to fail at the vector logical boundary."""

    completed = run_source(
        module_name,
        f"""
        module {module_name};

        {imports}

        func main() -> int {{
            {body}
            return 0;
        }}
        """,
        project_roots=project_roots,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode == 0:
        sys.stderr.write(output)
        raise AssertionError(f"{module_name} unexpectedly accepted a non-element slot")
    if VECTOR_BOUNDS_MESSAGE not in output:
        sys.stderr.write(output)
        raise AssertionError(
            f"{module_name} did not fail with {VECTOR_BOUNDS_MESSAGE!r}"
        )


def test_vector_bounds() -> None:
    """Exercise logical bounds independently of backing-array capacity."""

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
        require_bounds_failure(module_name, body)


def test_token_vector_bounds() -> None:
    """Exercise Stage 2 token access through the shared vector invariant."""

    imports = """
        import std.vector;
        import tokens;
    """
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
            body,
            imports=imports,
            project_roots=("compiler/stage2_l0/src",),
        )


def main() -> int:
    test_vector_bounds()
    test_token_vector_bounds()
    print("vector_logical_bounds_test: all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
