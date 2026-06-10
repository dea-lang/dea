#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end regression for isolated Stage 2 bootstrap artifacts."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

from tool_test_common import (
    BUILD_TESTS_ROOT,
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_file,
    assert_no_file,
    build_stage2,
    c_output_path,
    clean_env,
    is_windows_host,
    make_temp_dir,
    native_path,
    read_text,
    repo_relative,
    run,
    stage2_launcher_path,
    write_text,
)


QUALIFIED_EXPR = """module qualified_expr;

import std.unit;

func main() -> int {
    let maybe = std.unit::present();
    if (maybe != null) {
        return 0;
    }
    return 1;
}
"""

CONTROL_FLOW_COND = """module control_flow_cond;

import std.string;

extern func rt_print_int(x: int) -> void;
extern func rt_println() -> void;

func next_value(i: int) -> string {
    if (i == 0) {
        return concat_s("x", "");
    }
    return concat_s("", "");
}

func main() -> int {
    let i: int = 0;
    while (i < 3 && len_s(next_value(i)) > 0) {
        rt_print_int(i);
        rt_println();
        i = i + 1;
    }
    rt_print_int(i);
    rt_println();
    return 0;
}
"""

LOGICAL_EXPR = """module logical_expr;

import std.string;

extern func rt_print_int(x: int) -> void;
extern func rt_println() -> void;

func tick(n: int) -> string {
    rt_print_int(n);
    rt_println();
    return concat_s("x", "");
}

func main() -> int {
    let a: bool = false && len_s(tick(7)) > 0;
    let b: bool = true || len_s(tick(8)) > 0;
    let c: bool = false || len_s(tick(9)) > 0;
    let d: bool = true && len_s(tick(10)) > 0;

    if (a) {
        rt_print_int(1);
        rt_println();
    }
    if (b && c && d) {
        rt_print_int(2);
        rt_println();
    }
    return 0;
}
"""


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_bootstrap_test: FAIL: {message}")
    return 1


def main() -> int:
    """Program entrypoint."""

    bootstrap_dir: Path | None = None
    alt_dea_build: Path | None = None
    probe_root: Path | None = None
    outside_dea_build = Path(tempfile.mkdtemp(prefix="l0_stage2_outside_dea_build."))
    try:
        bootstrap_dir = make_temp_dir("l0_stage2_bootstrap.", BUILD_TESTS_ROOT)
        build_stage2(repo_relative(bootstrap_dir))
        l0c = stage2_launcher_path(bootstrap_dir / "bin" / "l0c-stage2")

        assert_file(bootstrap_dir / "bin" / "l0c-stage2")
        assert_file(bootstrap_dir / "bin" / "l0c-stage2.native")
        assert_no_file(bootstrap_dir / "bin" / "l0c-stage2.c")

        run([l0c, "--check", "-P", "examples", "hello"], env=clean_env())
        run([l0c, "--check", "-P", "examples", "newdrop"], env=clean_env())
        run([l0c, "--check", "-P", "examples", "hamurabi"], env=clean_env())

        probe_root = make_temp_dir("l0_stage2_probe.", BUILD_TESTS_ROOT)
        write_text(probe_root / "qualified_expr.l0", QUALIFIED_EXPR)
        write_text(probe_root / "control_flow_cond.l0", CONTROL_FLOW_COND)
        write_text(probe_root / "logical_expr.l0", LOGICAL_EXPR)
        run([l0c, "--check", "-P", native_path(probe_root), "qualified_expr"], env=clean_env())

        cond_output = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_cond_{os.getpid()}.out"
        cond_result = run([l0c, "--run", "-P", native_path(probe_root), "control_flow_cond"], env=clean_env())
        cond_output.write_text(cond_result.stdout, encoding="utf-8")
        assert_contains(cond_output, "0")
        assert_contains(cond_output, "1")
        if any(line == "2" for line in read_text(cond_output).splitlines()):
            raise ToolTestFailure("expected control_flow_cond loop to stop after i=1")

        logic_output = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_logic_{os.getpid()}.out"
        logic_result = run([l0c, "--run", "-P", native_path(probe_root), "logical_expr"], env=clean_env())
        logic_output.write_text(logic_result.stdout, encoding="utf-8")
        assert_contains(logic_output, "9")
        assert_contains(logic_output, "10")
        assert_contains(logic_output, "2")
        if any(line == "7" for line in read_text(logic_output).splitlines()):
            raise ToolTestFailure("expected logical_expr to short-circuit false && RHS")
        if any(line == "8" for line in read_text(logic_output).splitlines()):
            raise ToolTestFailure("expected logical_expr to short-circuit true || RHS")

        gen_output = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_gen_{os.getpid()}.c"
        gen_result = run(
            [l0c, "--gen", "--no-line-directives", "-P", "examples", "hello"],
            env=clean_env(),
        )
        gen_output.write_text(gen_result.stdout, encoding="utf-8")
        gen_output.unlink(missing_ok=True)

        hello_output = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_hello_{os.getpid()}"
        if is_windows_host():
            hello_output = hello_output.with_suffix(".exe")
        run(
            [
                l0c,
                "--build",
                "--keep-c",
                "-P",
                "examples",
                "-o",
                native_path(hello_output),
                "hello",
            ],
            env=clean_env(),
        )
        assert_file(hello_output)
        assert_file(c_output_path(hello_output))
        hello_run = run([hello_output])
        hello_out = Path(f"{hello_output}.out")
        hello_out.write_text(hello_run.stdout, encoding="utf-8")
        assert_contains(hello_out, "Hello, world! This is Dea/L0.")

        run_output = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_run_{os.getpid()}.out"
        run_result = run([l0c, "--run", "-P", "examples", "hello"], env=clean_env())
        run_output.write_text(run_result.stdout, encoding="utf-8")
        assert_contains(run_output, "Hello, world! This is Dea/L0.")

        alt_dea_build = make_temp_dir("l0_stage2_bootstrap_keepc.", BUILD_TESTS_ROOT)
        build_stage2(repo_relative(alt_dea_build), keep_c=True)
        assert_file(alt_dea_build / "bin" / "l0c-stage2")
        assert_file(alt_dea_build / "bin" / "l0c-stage2.native")
        assert_file(alt_dea_build / "bin" / "l0c-stage2.c")

        outside_env = os.environ.copy()
        outside_env["DEA_BUILD_DIR"] = str(outside_dea_build)
        outside = run(
            [sys.executable, REPO_ROOT / "scripts" / "build_stage2_l0c.py"],
            env=outside_env,
            expected_returncode=None,
        )
        outside_log = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_outside_{os.getpid()}.log"
        outside_log.write_text(outside.stdout + outside.stderr, encoding="utf-8")
        if outside.returncode == 0:
            raise ToolTestFailure("expected outside-repo DEA_BUILD_DIR rejection")

        repo_root_env = os.environ.copy()
        repo_root_env["DEA_BUILD_DIR"] = "."
        repo_root = run(
            [sys.executable, REPO_ROOT / "scripts" / "build_stage2_l0c.py"],
            env=repo_root_env,
            expected_returncode=None,
        )
        repo_root_log = BUILD_TESTS_ROOT / f"l0_stage2_bootstrap_repo_root_{os.getpid()}.log"
        repo_root_log.write_text(repo_root.stdout + repo_root.stderr, encoding="utf-8")
        if repo_root.returncode == 0:
            raise ToolTestFailure("expected repo-root DEA_BUILD_DIR rejection")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        if bootstrap_dir is not None:
            shutil.rmtree(bootstrap_dir, ignore_errors=True)
        if alt_dea_build is not None:
            shutil.rmtree(alt_dea_build, ignore_errors=True)
        if probe_root is not None:
            shutil.rmtree(probe_root, ignore_errors=True)
        shutil.rmtree(outside_dea_build, ignore_errors=True)
        for path in BUILD_TESTS_ROOT.glob(f"l0_stage2_bootstrap*_{os.getpid()}*"):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    print("l0c_stage2_bootstrap_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
