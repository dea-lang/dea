#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for Stage 2 `--build` and `--run`."""

from __future__ import annotations

import difflib
import os
import shutil
from pathlib import Path

from tool_test_common import (
    BUILD_TESTS_ROOT,
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_file,
    assert_no_file,
    assert_text_equals,
    build_stage2,
    c_output_path,
    clean_env,
    is_windows_host,
    make_temp_dir,
    native_path,
    normalize_text_file,
    read_text,
    repo_relative,
    repo_l0_env,
    run,
    stage2_launcher_path,
    write_text,
)


def fail(message: str, work_dir: Path, bootstrap_dir: Path | None) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_build_run_test: FAIL: {message}")
    print(f"l0c_build_run_test: work={work_dir}")
    if bootstrap_dir is not None:
        print(f"l0c_build_run_test: bootstrap={bootstrap_dir}")
    return 1


def prepare_windows_runtime_bin(dst: Path) -> None:
    """Copy toolchain runtime DLLs for the Windows no-compiler probe."""

    if not is_windows_host():
        return

    toolchain_bin: Path | None = None
    for candidate in ("gcc", "clang", "cc", "tcc"):
        compiler_path = shutil.which(candidate)
        if compiler_path is not None:
            toolchain_bin = Path(compiler_path).parent
            break
    if toolchain_bin is None:
        raise ToolTestFailure("expected a host C compiler on PATH while preparing Windows runtime DLLs")

    for dll_path in toolchain_bin.glob("*.dll"):
        shutil.copy2(dll_path, dst / dll_path.name)


def normalize_diff_input(src: Path, dst: Path) -> None:
    """Normalize runtime output for text diffing."""

    normalize_text_file(src, dst)


def no_compiler_env(empty_bin: Path) -> dict[str, str]:
    """Return an environment with compiler names hidden from PATH."""

    env = clean_env(path=str(empty_bin))
    env["L0_HOME"] = str(REPO_ROOT / "compiler")
    env.pop("L0_CC", None)
    env.pop("CC", None)
    env.pop("Path", None)
    env["PATH"] = str(empty_bin)
    return env


def debug_no_cc_probe(work_dir: Path, stage2_native: str) -> str:
    """Return diagnostic text for the no-compiler probe."""

    isolated_bin = work_dir / "empty-bin"
    lines = [
        "l0c_build_run_test: no-compiler probe diagnostics:",
        f"l0c_build_run_test: stage2_native={stage2_native}",
        f"l0c_build_run_test: isolated_bin={isolated_bin}",
    ]
    if isolated_bin.is_dir():
        lines.append("l0c_build_run_test: isolated bin listing:")
        lines.extend(f"  {path.name}" for path in sorted(isolated_bin.iterdir()))
    log_path = work_dir / "no_cc.log"
    if log_path.is_file():
        lines.append(f"l0c_build_run_test: ----- {log_path} -----")
        lines.extend(read_text(log_path).splitlines()[:200])
    return "\n".join(lines)


def last_non_empty_line(text: str) -> str:
    """Return the last non-empty logical line from captured text."""

    for line in reversed(text.splitlines()):
        if line.strip():
            return line
    return ""


def main() -> int:
    """Program entrypoint."""

    fixture_root = REPO_ROOT / "compiler" / "stage2_l0" / "tests" / "fixtures" / "driver"
    work_dir = make_temp_dir("l0_stage2_build_run_test.", BUILD_TESTS_ROOT)
    bootstrap_dir: Path | None = None
    try:
        bootstrap_dir = make_temp_dir("l0_stage2_buildrun.", BUILD_TESTS_ROOT)
        build_stage2(repo_relative(bootstrap_dir))
        l0c = stage2_launcher_path(bootstrap_dir / "bin" / "l0c-stage2")
        stage2_native = native_path(bootstrap_dir / "bin" / "l0c-stage2.native")

        ok_main_bin = work_dir / ("ok_main.bin.exe" if is_windows_host() else "ok_main.bin")
        byte_main_bin = work_dir / ("byte_main.bin.exe" if is_windows_host() else "byte_main.bin")

        run(
            [
                l0c,
                "--build",
                "--keep-c",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(ok_main_bin),
                "ok_main",
            ],
        )
        assert_file(ok_main_bin)
        assert_file(c_output_path(ok_main_bin))
        ok_result = run([ok_main_bin])
        (work_dir / "ok_main.stdout").write_text(ok_result.stdout, encoding="utf-8")
        assert_text_equals(work_dir / "ok_main.stdout", "")

        argv_out = work_dir / "argv.out"
        argv_result = run(
            [
                stage2_native,
                "--run",
                "--project-root",
                native_path(fixture_root),
                "argv_dump",
                "--",
                "two words",
                "rock'n'roll",
            ],
            env=repo_l0_env(),
        )
        argv_out.write_text(argv_result.stdout + argv_result.stderr, encoding="utf-8")
        argv_expected = work_dir / "argv.expected"
        write_text(argv_expected, "3\ntwo words\nrock'n'roll\n")
        argv_tail = work_dir / "argv.tail"
        write_text(argv_tail, "\n".join(read_text(argv_out).splitlines()[-3:]) + "\n")
        argv_tail_normalized = work_dir / "argv.tail.normalized"
        normalize_diff_input(argv_tail, argv_tail_normalized)
        if read_text(argv_expected) != read_text(argv_tail_normalized):
            diff = "".join(
                difflib.unified_diff(
                    read_text(argv_expected).splitlines(keepends=True),
                    read_text(argv_tail_normalized).splitlines(keepends=True),
                    fromfile=str(argv_expected),
                    tofile=str(argv_tail_normalized),
                )
            )
            (work_dir / "argv.diff").write_text(diff, encoding="utf-8")
            raise ToolTestFailure(f"argv forwarding output mismatch\n{diff}")

        demo_result = run([l0c, "--run", "--project-root", "examples", "demo", "--", "add", "2", "3"])
        (work_dir / "demo.stdout").write_text(demo_result.stdout, encoding="utf-8")
        (work_dir / "demo.stderr").write_text(demo_result.stderr, encoding="utf-8")
        write_text(work_dir / "demo.tail", last_non_empty_line(demo_result.stdout))
        assert_text_equals(work_dir / "demo.tail", "= 5")

        exit_result = run(
            [l0c, "--run", "--project-root", native_path(fixture_root), "exit_seven"],
            expected_returncode=None,
        )
        (work_dir / "exit_seven.out").write_text(exit_result.stdout + exit_result.stderr, encoding="utf-8")
        if exit_result.returncode == 0:
            raise ToolTestFailure("expected exit_seven to return a non-zero exit code")
        if exit_result.returncode != 7:
            raise ToolTestFailure("expected --run exit code 7")

        run(
            [
                l0c,
                "--run",
                "--keep-c",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(work_dir / "kept-name"),
                "ok_main",
            ]
        )
        assert_file(work_dir / "kept-name.c")

        run_warn = run(
            [
                l0c,
                "--run",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(work_dir / "ignored-output"),
                "ok_main",
            ]
        )
        (work_dir / "run_warn.log").write_text(run_warn.stdout + run_warn.stderr, encoding="utf-8")
        assert_contains(work_dir / "run_warn.log", "L0C-0017")
        assert_no_file(work_dir / "ignored-output")

        # A compile warning must surface during `--run` (on stderr) without
        # becoming fatal and without corrupting the program's stdout.
        dup_run = run(
            [l0c, "--run", "--project-root", native_path(fixture_root), "dup_import_main"],
        )
        (work_dir / "dup_run.stdout").write_text(dup_run.stdout, encoding="utf-8")
        (work_dir / "dup_run.stderr").write_text(dup_run.stderr, encoding="utf-8")
        # Warning on stderr, program output intact on stdout, exit code 0
        # (the `run` helper already asserts the 0 exit code).
        assert_contains(work_dir / "dup_run.stderr", "[RES-0036] duplicated 'import std.io'")
        assert_contains(work_dir / "dup_run.stdout", "dup-import-ok")
        assert_text_equals(work_dir / "dup_run.stdout", "dup-import-ok\n")

        # The same warning must also surface during `--build` (stderr).
        dup_build_bin = work_dir / ("dup_build.bin.exe" if is_windows_host() else "dup_build.bin")
        dup_build = run(
            [
                l0c,
                "--build",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(dup_build_bin),
                "dup_import_main",
            ],
        )
        (work_dir / "dup_build.stderr").write_text(dup_build.stderr, encoding="utf-8")
        assert_file(dup_build_bin)
        assert_contains(work_dir / "dup_build.stderr", "[RES-0036] duplicated 'import std.io'")

        # `--gen` must surface the warning on stderr while emitting C on stdout.
        dup_gen = run(
            [l0c, "--gen", "--project-root", native_path(fixture_root), "dup_import_main"],
        )
        (work_dir / "dup_gen.stdout").write_text(dup_gen.stdout, encoding="utf-8")
        (work_dir / "dup_gen.stderr").write_text(dup_gen.stderr, encoding="utf-8")
        assert_contains(work_dir / "dup_gen.stderr", "[RES-0036] duplicated 'import std.io'")
        assert_contains(work_dir / "dup_gen.stdout", "Generated by l0c")

        empty_bin = work_dir / "empty-bin"
        empty_bin.mkdir()
        prepare_windows_runtime_bin(empty_bin)
        no_cc = run(
            [stage2_native, "--build", "--project-root", native_path(fixture_root), "ok_main"],
            env=no_compiler_env(empty_bin),
            expected_returncode=None,
        )
        (work_dir / "no_cc.log").write_text(no_cc.stdout + no_cc.stderr, encoding="utf-8")
        if no_cc.returncode == 0:
            raise ToolTestFailure(
                "expected no-compiler build to fail\n" + debug_no_cc_probe(work_dir, stage2_native)
            )
        if "L0C-0009" not in read_text(work_dir / "no_cc.log"):
            raise ToolTestFailure(
                f"expected 'L0C-0009' in {work_dir / 'no_cc.log'}\n"
                + debug_no_cc_probe(work_dir, stage2_native)
            )

        compile_fail = run(
            [l0c, "--build", "--c-compiler", "false", "--project-root", native_path(fixture_root), "ok_main"],
            expected_returncode=None,
        )
        (work_dir / "compile_fail.log").write_text(
            compile_fail.stdout + compile_fail.stderr, encoding="utf-8"
        )
        if compile_fail.returncode == 0:
            raise ToolTestFailure("expected explicit failing compiler to fail")
        assert_contains(work_dir / "compile_fail.log", "L0C-0010")

        runtime_lib_missing = run(
            [
                l0c,
                "--build",
                "--runtime-lib",
                native_path(work_dir / "missing-lib"),
                "--project-root",
                native_path(fixture_root),
                "ok_main",
            ],
            expected_returncode=None,
        )
        (work_dir / "runtime_lib_missing.log").write_text(
            runtime_lib_missing.stdout + runtime_lib_missing.stderr, encoding="utf-8"
        )
        if runtime_lib_missing.returncode == 0:
            raise ToolTestFailure("expected missing runtime-lib directory to fail")
        assert_contains(work_dir / "runtime_lib_missing.log", "L0C-0014")

        (work_dir / "empty-lib").mkdir()
        runtime_lib_empty = run(
            [
                l0c,
                "--build",
                "--runtime-lib",
                native_path(work_dir / "empty-lib"),
                "--project-root",
                native_path(fixture_root),
                "ok_main",
            ],
        )
        (work_dir / "runtime_lib_empty.log").write_text(
            runtime_lib_empty.stdout + runtime_lib_empty.stderr, encoding="utf-8"
        )
        if "L0C-0015" in read_text(work_dir / "runtime_lib_empty.log"):
            raise ToolTestFailure(f"did not expect retired L0C-0015 in {work_dir / 'runtime_lib_empty.log'}")

        no_main = run(
            [l0c, "--build", "--project-root", native_path(fixture_root), "no_main"],
            expected_returncode=None,
        )
        (work_dir / "no_main.log").write_text(no_main.stdout + no_main.stderr, encoding="utf-8")
        if no_main.returncode == 0:
            raise ToolTestFailure("expected missing-main build to fail")
        assert_contains(work_dir / "no_main.log", "L0C-0012")

        byte_main = run(
            [
                l0c,
                "--build",
                "--keep-c",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(byte_main_bin),
                "byte_main",
            ],
        )
        (work_dir / "byte_main.log").write_text(byte_main.stdout + byte_main.stderr, encoding="utf-8")
        assert_contains(work_dir / "byte_main.log", "L0C-0013")
        assert_file(byte_main_bin)
        assert_file(c_output_path(byte_main_bin))
    except ToolTestFailure as exc:
        return fail(str(exc), work_dir, bootstrap_dir)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if bootstrap_dir is not None:
            shutil.rmtree(bootstrap_dir, ignore_errors=True)
        for name in ("a.out", "a.exe", "a.out.c", "a.exe.c"):
            try:
                os.remove(REPO_ROOT / name)
            except FileNotFoundError:
                pass

    print("l0c_build_run_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
