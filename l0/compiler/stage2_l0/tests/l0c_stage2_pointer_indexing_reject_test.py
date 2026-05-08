#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for native Stage 2 pointer-indexing rejection."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import textwrap

from tool_test_common import ToolTestFailure, make_temp_dir, read_text, repo_l0_env, resolve_tool, run, write_text


SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_DIR = SCRIPT_DIR.parent
REPO_ROOT = STAGE_DIR.parent.parent
def stage2_compiler() -> Path:
    """Return the repo-local native Stage 2 compiler path."""

    build_dir = Path(os.environ.get("DEA_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = REPO_ROOT / build_dir
    return resolve_tool(build_dir / "bin", "l0c-stage2")


def write_case_source(case_dir: Path, elem_type: str) -> Path:
    """Write one temporary source file for one pointer-indexing rejection case."""

    source_path = case_dir / "main.l0"
    write_text(
        source_path,
        textwrap.dedent(
            f"""
            module main;

            func main() -> int {{
                let p: {elem_type}* = new {elem_type};
                let v = p[0];
                return 0;
            }}
            """
        ).lstrip(),
    )
    return source_path


def assert_rejected(elem_type: str, artifact_dir: Path) -> None:
    """Assert that native Stage 2 rejects one raw-pointer indexing program."""

    case_dir = artifact_dir / elem_type
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = write_case_source(case_dir, elem_type)
    stdout_path = case_dir / "stdout.log"
    stderr_path = case_dir / "stderr.log"

    completed = run(
        [stage2_compiler(), "--gen", source_path],
        cwd=REPO_ROOT,
        env=repo_l0_env(),
        expected_returncode=None,
    )
    write_text(stdout_path, completed.stdout)
    write_text(stderr_path, completed.stderr)

    if completed.returncode == 0:
        raise ToolTestFailure(f"{elem_type}* pointer indexing unexpectedly succeeded; artifacts={case_dir}")
    if "[TYP-0212]" not in completed.stderr:
        raise ToolTestFailure(
            f"{elem_type}* pointer indexing missing [TYP-0212] in stderr; stderr={read_text(stderr_path)!r}; artifacts={case_dir}"
        )
    if "indexing is not yet supported" not in completed.stderr:
        raise ToolTestFailure(
            f"{elem_type}* pointer indexing missing updated wording in stderr; stderr={read_text(stderr_path)!r}; artifacts={case_dir}"
        )


def main() -> int:
    """Program entrypoint."""

    artifact_dir = make_temp_dir("l0_stage2_pointer_indexing_reject.")
    keep_artifacts = False
    try:
        for elem_type in ("int", "byte", "string"):
            assert_rejected(elem_type, artifact_dir)
        print("l0c_stage2_pointer_indexing_reject_test: PASS")
        return 0
    except ToolTestFailure as exc:
        keep_artifacts = True
        print(f"l0c_stage2_pointer_indexing_reject_test: FAIL: {exc}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
