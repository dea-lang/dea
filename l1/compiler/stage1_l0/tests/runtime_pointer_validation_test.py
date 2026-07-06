#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Runtime pointer validation regressions for L1 generated programs."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def compiler_path() -> Path:
    """Return the repo-local L1 Stage 1 compiler launcher."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def run_source(module_name: str, source: str) -> subprocess.CompletedProcess[str]:
    """Compile and run one temporary L1 source module."""

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l1").write_text(source, encoding="utf-8")
        return subprocess.run(
            [
                str(compiler_path()),
                "-P",
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


def require_failure(module_name: str, source: str, stderr_needle: str) -> None:
    """Run one fixture and assert it fails with the expected runtime message."""

    completed = run_source(module_name, source)
    if completed.returncode == 0:
        sys.stderr.write(completed.stdout)
        raise AssertionError(f"{module_name} unexpectedly succeeded")
    if stderr_needle not in completed.stderr:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{module_name} stderr did not contain {stderr_needle!r}")


def main() -> int:
    require_failure(
        "pointer_index_oob",
        """
        module pointer_index_oob;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int));
            let raw: void* = raw_opt as void*;
            let p: int* = raw as int*;
            return p[1];
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "pointer index outside allocation",
    )

    require_failure(
        "pointer_index_negative",
        """
        module pointer_index_negative;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int));
            let raw: void* = raw_opt as void*;
            let p: int* = raw as int*;
            return p[-1];
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "negative pointer index",
    )

    require_failure(
        "misaligned_pointer",
        """
        module misaligned_pointer;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int) + 1);
            let raw: void* = raw_opt as void*;
            let p: int* = rt_array_element(raw, 1, 1) as int*;
            return *p;
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "misaligned pointer access",
    )

    require_failure(
        "stale_slice_backing",
        """
        module stale_slice_backing;

        func main() -> int {
            let heap: int[2]* = new int[2]([10, 20]);
            let s: int[] = *heap;
            drop heap;
            return s[0];
        }
        """,
        "use after drop/free",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
