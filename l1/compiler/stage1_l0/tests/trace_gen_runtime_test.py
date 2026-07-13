#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end traced `--gen` coverage for runtime helper rewrites."""

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
    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def write_fixture(root: Path) -> None:
    (root / "trace_gen_main.l1").write_text(
        """module trace_gen_main;
import sys.rt;

struct Box {
    value: int;
}

func main() {
    let a = "a";
    let b = "b";
    let c = rt_string_concat(a, b);
    rt_string_release(c);
    let op = a + b;
    rt_string_release(op);

    let p: Box* = new Box(1);
    drop p;
}
""",
        encoding="utf-8",
    )


def require_trace_gen_rewrite() -> None:
    with tempfile.TemporaryDirectory(prefix="l1_trace_gen_runtime_test.") as temp_dir:
        fixture_root = Path(temp_dir)
        write_fixture(fixture_root)
        output_path = fixture_root / "trace_gen_main.c"

        completed = subprocess.run(
            [
                str(compiler_path()),
                "--gen",
                "--trace-arc",
                "--trace-memory",
                "--output",
                str(output_path),
                "-P",
                str(fixture_root),
                "trace_gen_main",
            ],
            cwd=L1_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise AssertionError(f"traced --gen exited with {completed.returncode}")

        assert "warning: [L1C-0019]" in completed.stderr, completed.stderr
        c_text = output_path.read_text(encoding="utf-8")
        assert "dea_string c = _rt_string_concat_impl(a, b, __FILE__, __LINE__);" in c_text
        assert "_rt_string_release_impl(c, __FILE__, __LINE__);" in c_text
        assert "dea_string op = _rt_string_concat_impl(a, b, __FILE__, __LINE__);" in c_text
        assert "_rt_string_release_impl(op, __FILE__, __LINE__);" in c_text
        assert "_rt_alloc_obj_impl((dea_int)sizeof(struct __deaM14trace_gen_mainS3Box), __FILE__, __LINE__);" in c_text
        assert (
            "_rt_drop_begin_impl((void*)(p), "
            "(dea_int)(sizeof(struct __deaM14trace_gen_mainS3Box))"
        ) in c_text
        assert "_rt_drop_finish_impl((void*)(" in c_text


def main() -> int:
    require_trace_gen_rewrite()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
