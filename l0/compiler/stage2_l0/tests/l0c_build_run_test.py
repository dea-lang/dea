#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for Stage 2 `--build` and `--run`."""

from __future__ import annotations

import difflib
import os
import re
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


def workspace_paths(parent: Path, tag: str) -> list[Path]:
    """Return compiler workspaces for one command tag."""

    return sorted(parent.glob(f".l0c-{tag}-workspace-*"))


def assert_no_workspaces(parent: Path, tag: str) -> None:
    """Assert that one command left no workspace behind."""

    leftovers = workspace_paths(parent, tag)
    if leftovers:
        raise ToolTestFailure(
            f"expected no retained {tag} workspace under {parent}: "
            f"{leftovers}"
        )


def retained_workspace(stderr: str) -> Path:
    """Return the retained workspace path named by `L0C-9514`."""

    match = re.search(
        r"L0C-9514[^\n]*retained at '([^']+)'",
        stderr,
    )
    if match is None:
        raise ToolTestFailure(
            f"expected L0C-9514 retained-workspace path in:\n{stderr}"
        )
    return Path(match.group(1))


def logged_workspace(output: str) -> Path:
    """Return the workspace path from verbose compiler output."""

    match = re.search(
        r"Compiler temporary workspace: ([^\r\n]+)",
        output,
    )
    if match is None:
        raise ToolTestFailure(
            f"expected verbose temporary-workspace path in:\n{output}"
        )
    return Path(match.group(1).strip())


def resolve_workspace_test_compiler() -> str:
    """Return a GCC-compatible host compiler for the POSIX wrapper probes."""

    for candidate in ("gcc", "clang", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise ToolTestFailure(
        "workspace lifecycle probes require gcc, clang, or cc"
    )


def write_workspace_compiler_wrapper(path: Path) -> None:
    """Write a POSIX compiler wrapper with controlled workspace effects."""

    write_text(
        path,
        """\
#!/bin/sh
generated=
for argument in "$@"; do
    case "$argument" in
        */generated.c) generated="$argument" ;;
    esac
done
if [ -z "$generated" ]; then
    exit 91
fi
printf '%s\\n' "$generated" > "$L0_WORKSPACE_RECORD"
case "$L0_WORKSPACE_MODE" in
    retain)
        printf '%s\\n' retained > "$(dirname "$generated")/unexpected"
        ;;
    no-output)
        exit 0
        ;;
esac
if [ -n "${TMPDIR:-}" ] && [ ! -d "$TMPDIR" ]; then
    unset TMPDIR
fi
exec "$L0_WORKSPACE_REAL_CC" "$@"
""",
    )
    path.chmod(0o755)


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
        compiler_temp = work_dir / "compiler-temp"
        compiler_temp.mkdir(mode=0o700)
        workspace_env = repo_l0_env()
        workspace_env["TMPDIR"] = native_path(compiler_temp)

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

        c_interop_root = REPO_ROOT / "examples" / "c_interop"
        c_interop_result = run(
            [
                l0c,
                "--run",
                "--project-root",
                native_path(c_interop_root),
                "--c-source",
                native_path(c_interop_root / "c_add.c"),
                "--c-source",
                native_path(c_interop_root / "c_multiply.c"),
                "c_interop",
            ],
        )
        (work_dir / "c_interop.stdout").write_text(
            c_interop_result.stdout,
            encoding="utf-8",
        )
        assert_text_equals(
            work_dir / "c_interop.stdout",
            "C sum: 42\nC product: 42\n",
        )

        workspace_build_bin = work_dir / (
            "workspace-build.exe"
            if is_windows_host()
            else "workspace-build"
        )
        workspace_build = run(
            [
                l0c,
                "-v",
                "--build",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(workspace_build_bin),
                "ok_main",
            ],
            env=workspace_env,
        )
        workspace_build_log = (
            workspace_build.stdout + workspace_build.stderr
        )
        (work_dir / "workspace_build.log").write_text(
            workspace_build_log,
            encoding="utf-8",
        )
        assert_file(workspace_build_bin)
        assert_no_workspaces(compiler_temp, "build")
        assert_contains(
            work_dir / "workspace_build.log",
            "Compiler temporary workspace:",
        )
        assert_contains(
            work_dir / "workspace_build.log",
            "generated.c",
        )

        workspace_run = run(
            [
                l0c,
                "-v",
                "--run",
                "--project-root",
                native_path(fixture_root),
                "ok_main",
            ],
            env=workspace_env,
        )
        (work_dir / "workspace_run.log").write_text(
            workspace_run.stdout + workspace_run.stderr,
            encoding="utf-8",
        )
        assert_no_workspaces(compiler_temp, "run")
        assert_contains(
            work_dir / "workspace_run.log",
            "program",
        )

        invalid_temp = work_dir / "not-a-directory"
        invalid_temp.write_text("not a directory", encoding="utf-8")
        fallback_temp = work_dir / "fallback-temp"
        fallback_temp.mkdir(mode=0o700)
        compiler_wrapper = work_dir / "gcc"
        if not is_windows_host():
            write_workspace_compiler_wrapper(compiler_wrapper)
        fallback_env = workspace_env.copy()
        fallback_env["TMPDIR"] = native_path(invalid_temp)
        fallback_env["TEMP"] = native_path(fallback_temp)
        if not is_windows_host():
            fallback_env["L0_WORKSPACE_REAL_CC"] = (
                resolve_workspace_test_compiler()
            )
            fallback_env["L0_WORKSPACE_RECORD"] = str(
                work_dir / "fallback-workspace-record"
            )
            fallback_env["L0_WORKSPACE_MODE"] = "success"
        fallback_build_bin = work_dir / (
            "fallback-build.exe"
            if is_windows_host()
            else "fallback-build"
        )
        fallback_command = [
            l0c,
            "-v",
            "--build",
            "--project-root",
            native_path(fixture_root),
            "-o",
            native_path(fallback_build_bin),
            "ok_main",
        ]
        if not is_windows_host():
            fallback_command[3:3] = [
                "--c-compiler",
                str(compiler_wrapper),
            ]
        fallback_build = run(
            fallback_command,
            env=fallback_env,
        )
        (work_dir / "fallback_build.log").write_text(
            fallback_build.stdout + fallback_build.stderr,
            encoding="utf-8",
        )
        assert_file(fallback_build_bin)
        assert_contains(
            work_dir / "fallback_build.log",
            str(fallback_temp.resolve()),
        )
        assert_no_workspaces(fallback_temp, "build")

        empty_candidate_env = workspace_env.copy()
        empty_candidate_env["TMPDIR"] = ""
        empty_candidate_env["TEMP"] = native_path(fallback_temp)
        empty_candidate_build_bin = work_dir / (
            "empty-candidate-build.exe"
            if is_windows_host()
            else "empty-candidate-build"
        )
        empty_candidate_build = run(
            [
                l0c,
                "-v",
                "--build",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(empty_candidate_build_bin),
                "ok_main",
            ],
            env=empty_candidate_env,
        )
        (work_dir / "empty_candidate_build.log").write_text(
            empty_candidate_build.stdout + empty_candidate_build.stderr,
            encoding="utf-8",
        )
        assert_file(empty_candidate_build_bin)
        assert_contains(
            work_dir / "empty_candidate_build.log",
            str(fallback_temp.resolve()),
        )
        assert_no_workspaces(fallback_temp, "build")

        if not is_windows_host():
            canonical_temp = work_dir / "canonical-temp"
            canonical_temp.mkdir(mode=0o700)
            selected_alias = work_dir / "canonical-temp-alias"
            selected_alias.symlink_to(
                canonical_temp,
                target_is_directory=True,
            )
            canonical_env = workspace_env.copy()
            canonical_env["TMPDIR"] = str(selected_alias)
            canonical_build_bin = work_dir / "canonical-build"
            canonical_build = run(
                [
                    l0c,
                    "-v",
                    "--build",
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    native_path(canonical_build_bin),
                    "ok_main",
                ],
                env=canonical_env,
            )
            (work_dir / "canonical_build.log").write_text(
                canonical_build.stdout + canonical_build.stderr,
                encoding="utf-8",
            )
            assert_file(canonical_build_bin)
            assert_contains(
                work_dir / "canonical_build.log",
                str(canonical_temp.resolve()),
            )
            assert_no_workspaces(canonical_temp, "build")

            backslash_temp = work_dir / "backslash-temp\\"
            backslash_temp.mkdir(mode=0o700)
            backslash_env = workspace_env.copy()
            backslash_env["TMPDIR"] = str(backslash_temp)
            backslash_build_bin = work_dir / "backslash-build"
            backslash_build = run(
                [
                    l0c,
                    "-v",
                    "--build",
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    native_path(backslash_build_bin),
                    "ok_main",
                ],
                env=backslash_env,
            )
            backslash_log = (
                backslash_build.stdout + backslash_build.stderr
            )
            (work_dir / "backslash_build.log").write_text(
                backslash_log,
                encoding="utf-8",
            )
            assert_file(backslash_build_bin)
            backslash_workspace = logged_workspace(backslash_log)
            if (
                backslash_workspace.parent
                != backslash_temp.resolve()
            ):
                raise ToolTestFailure(
                    "workspace escaped literal-backslash parent: "
                    f"{backslash_workspace}"
                )
            assert_no_workspaces(backslash_temp, "build")

            sticky_temp = work_dir / "sticky-temp"
            sticky_temp.mkdir()
            sticky_temp.chmod(0o1777)
            sticky_env = workspace_env.copy()
            sticky_env["TMPDIR"] = str(sticky_temp)
            sticky_build_bin = work_dir / "sticky-build"
            run(
                [
                    l0c,
                    "--build",
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    native_path(sticky_build_bin),
                    "ok_main",
                ],
                env=sticky_env,
            )
            assert_file(sticky_build_bin)
            assert_no_workspaces(sticky_temp, "build")

            unsafe_temp = work_dir / "unsafe-temp"
            unsafe_temp.mkdir()
            unsafe_temp.chmod(0o777)
            unsafe_env = workspace_env.copy()
            unsafe_env["TMPDIR"] = str(unsafe_temp)
            unsafe_env["TEMP"] = str(compiler_temp)
            unsafe_env["L0_PLATFORM"] = "windows"
            unsafe_build_bin = work_dir / "unsafe-build"
            unsafe_result = run(
                [
                    l0c,
                    "--build",
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    native_path(unsafe_build_bin),
                    "ok_main",
                ],
                env=unsafe_env,
                expected_returncode=None,
            )
            (work_dir / "unsafe_build.log").write_text(
                unsafe_result.stdout + unsafe_result.stderr,
                encoding="utf-8",
            )
            if unsafe_result.returncode == 0:
                raise ToolTestFailure(
                    "expected unsafe temporary parent rejection"
                )
            assert_contains(
                work_dir / "unsafe_build.log",
                "L0C-9513",
            )
            assert_no_file(unsafe_build_bin)
            assert_no_workspaces(unsafe_temp, "build")

            unsafe_ancestor = work_dir / "unsafe-ancestor"
            unsafe_ancestor.mkdir()
            unsafe_ancestor.chmod(0o777)
            nested_temp = unsafe_ancestor / "nested-temp"
            nested_temp.mkdir(mode=0o700)
            ancestor_env = workspace_env.copy()
            ancestor_env["TMPDIR"] = str(nested_temp)
            ancestor_build = run(
                [
                    l0c,
                    "--build",
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    native_path(work_dir / "unsafe-ancestor-build"),
                    "ok_main",
                ],
                env=ancestor_env,
                expected_returncode=None,
            )
            (work_dir / "unsafe_ancestor_build.log").write_text(
                ancestor_build.stdout + ancestor_build.stderr,
                encoding="utf-8",
            )
            if ancestor_build.returncode == 0:
                raise ToolTestFailure(
                    "expected unsafe temporary ancestor rejection"
                )
            assert_contains(
                work_dir / "unsafe_ancestor_build.log",
                "L0C-9513",
            )
            assert_no_workspaces(nested_temp, "build")

            inspection_ancestor = work_dir / "inspection-denied"
            inspection_ancestor.mkdir(mode=0o700)
            inspection_temp = inspection_ancestor / "candidate"
            inspection_temp.mkdir(mode=0o700)
            inspection_compiler = work_dir / "inspection-compiler"
            inspection_record = work_dir / "inspection-compiler-record"
            write_text(
                inspection_compiler,
                """\
#!/bin/sh
printf '%s\\n' invoked > "$L0_INSPECTION_COMPILER_RECORD"
exit 97
""",
            )
            inspection_compiler.chmod(0o755)
            inspection_ancestor.chmod(0)
            inspection_reliable = False
            try:
                os.stat(inspection_temp)
            except PermissionError:
                inspection_reliable = True
            except OSError:
                inspection_ancestor.chmod(0o700)
                raise

            try:
                if inspection_reliable:
                    inspection_env = workspace_env.copy()
                    inspection_env["TMPDIR"] = str(inspection_temp)
                    inspection_env["TEMP"] = str(compiler_temp)
                    inspection_env[
                        "L0_INSPECTION_COMPILER_RECORD"
                    ] = str(inspection_record)
                    inspection_output = work_dir / "inspection-output"
                    inspection_result = run(
                        [
                            l0c,
                            "--build",
                            "--c-compiler",
                            str(inspection_compiler),
                            "--project-root",
                            native_path(fixture_root),
                            "-o",
                            str(inspection_output),
                            "ok_main",
                        ],
                        env=inspection_env,
                        expected_returncode=None,
                    )
                    inspection_log = (
                        inspection_result.stdout +
                        inspection_result.stderr
                    )
                    (work_dir / "inspection_error.log").write_text(
                        inspection_log,
                        encoding="utf-8",
                    )
                    if inspection_result.returncode == 0:
                        raise ToolTestFailure(
                            "inspection-error temporary parent "
                            "unexpectedly succeeded"
                        )
                    assert_contains(
                        work_dir / "inspection_error.log",
                        "L0C-9513",
                    )
                    assert_contains(
                        work_dir / "inspection_error.log",
                        "cannot inspect compiler temporary parent",
                    )
                    assert_no_file(inspection_output)
                    assert_no_file(inspection_record)
                    assert_no_workspaces(compiler_temp, "build")
            finally:
                inspection_ancestor.chmod(0o700)
            if inspection_reliable:
                assert_no_workspaces(inspection_temp, "build")

            wrapper_record = work_dir / "workspace-record"
            wrapper_env = workspace_env.copy()
            wrapper_env["L0_WORKSPACE_REAL_CC"] = (
                resolve_workspace_test_compiler()
            )
            wrapper_env["L0_WORKSPACE_RECORD"] = str(wrapper_record)
            wrapper_env["L0_WORKSPACE_MODE"] = "retain"

            retained_output = work_dir / "retained-output"
            retained_build = run(
                [
                    l0c,
                    "--build",
                    "--c-compiler",
                    str(compiler_wrapper),
                    "--project-root",
                    native_path(fixture_root),
                    "-o",
                    str(retained_output),
                    "ok_main",
                ],
                env=wrapper_env,
                expected_returncode=None,
            )
            if retained_build.returncode != 1:
                raise ToolTestFailure(
                    "cleanup failure after successful build should return 1"
                )
            assert_file(retained_output)
            retained_build_root = retained_workspace(
                retained_build.stderr
            )
            if retained_build_root.parent != compiler_temp.resolve():
                raise ToolTestFailure(
                    "retained build workspace used the wrong parent: "
                    f"{retained_build_root}"
                )
            generated_path = Path(
                wrapper_record.read_text(encoding="utf-8").strip()
            )
            if (
                generated_path.parent != retained_build_root
                or generated_path.name != "generated.c"
            ):
                raise ToolTestFailure(
                    f"unexpected generated-C workspace path: "
                    f"{generated_path}"
                )
            retained_names = sorted(
                path.name for path in retained_build_root.iterdir()
            )
            if retained_names != ["unexpected"]:
                raise ToolTestFailure(
                    "known build children should be removed before "
                    f"retention: {retained_names}"
                )
            shutil.rmtree(retained_build_root)

            retained_run = run(
                [
                    l0c,
                    "--run",
                    "--c-compiler",
                    str(compiler_wrapper),
                    "--project-root",
                    native_path(fixture_root),
                    "exit_seven",
                ],
                env=wrapper_env,
                expected_returncode=None,
            )
            if retained_run.returncode != 7:
                raise ToolTestFailure(
                    "cleanup failure should preserve child exit status 7"
                )
            retained_run_root = retained_workspace(
                retained_run.stderr
            )
            retained_run_names = sorted(
                path.name for path in retained_run_root.iterdir()
            )
            if retained_run_names != ["unexpected"]:
                raise ToolTestFailure(
                    "known run children should be removed before "
                    f"retention: {retained_run_names}"
                )
            shutil.rmtree(retained_run_root)

            wrapper_env["L0_WORKSPACE_MODE"] = "no-output"
            launch_failure = run(
                [
                    l0c,
                    "--run",
                    "--c-compiler",
                    str(compiler_wrapper),
                    "--project-root",
                    native_path(fixture_root),
                    "ok_main",
                ],
                env=wrapper_env,
                expected_returncode=None,
            )
            if launch_failure.returncode == 0:
                raise ToolTestFailure(
                    "expected missing temporary executable launch failure"
                )
            assert_no_workspaces(compiler_temp, "run")

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

        invalid_ignored_output = work_dir / "ignored-invalid-output"
        invalid_run_warn = run(
            [
                l0c,
                "--run",
                "--project-root",
                native_path(fixture_root),
                "-o",
                native_path(invalid_ignored_output),
                "definitely_missing_module",
            ],
            env=workspace_env,
            expected_returncode=None,
        )
        invalid_run_warn_log = (
            invalid_run_warn.stdout + invalid_run_warn.stderr
        )
        (work_dir / "invalid_run_warn.log").write_text(
            invalid_run_warn_log,
            encoding="utf-8",
        )
        if invalid_run_warn.returncode == 0:
            raise ToolTestFailure(
                "missing --run source unexpectedly succeeded"
            )
        assert_contains(
            work_dir / "invalid_run_warn.log",
            "L0C-0017",
        )
        assert_contains(
            work_dir / "invalid_run_warn.log",
            "DRV-0010",
        )
        if invalid_run_warn_log.index(
            "L0C-0017"
        ) > invalid_run_warn_log.index("DRV-0010"):
            raise ToolTestFailure(
                "ignored-output warning must precede source-analysis failure"
            )
        assert_no_file(invalid_ignored_output)
        assert_no_workspaces(compiler_temp, "run")

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
