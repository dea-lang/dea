#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Fast subprocess regressions for opt-in child fixture trace handling."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_trace_tests as runner
from dea_tooling import bootstrap
from support import driver_inputs
from test_runner_common import ChildTraceFixture


def require(condition: bool, message: str) -> None:
    """Raise an assertion with one focused failure message."""

    if not condition:
        raise AssertionError(message)


def test_selection_and_commands(root: Path) -> None:
    """Require explicit child selection and platform-aware build commands."""

    fixtures = runner.select_child_fixtures([])
    require([case.name for case in fixtures] == ["math_int_trace_main", "wide_math_main"], "wrong default children")
    require(
        [case.name for case in runner.select_child_fixtures(["wide_math_main.l1", "wide_math_main"])]
        == ["wide_math_main"], "child selector did not deduplicate",
    )
    for name in ("unknown", "math_runtime_compile_test", "wide_math_main.l0"):
        try:
            runner.select_child_fixtures([name])
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unknown child selector {name}")

    build_dir = root / "custom build with spaces"
    compiler = build_dir / "bin" / "l1c-stage1"
    expected = runner.child_build_command(fixtures[0], build_dir, root / "child output")
    require(expected[0] == str(compiler), "child build ignored custom compiler location")
    require(expected[-1] == fixtures[0].name, "child build did not select fixture module")
    require(expected[expected.index("--output") + 1] == str(root / "child output"), "output path changed")
    require(expected[expected.index("--project-root") + 1] == str(fixtures[0].path.parent), "project root changed")
    require("--trace-memory" in expected and "--trace-arc" in expected, "trace flags missing")
    require(runner.child_executable_path(root, "sample", windows=False) == root / "sample",
            "POSIX executable name changed")
    require(runner.child_executable_path(root, "sample", windows=True) == root / "sample.exe",
            "Windows executable suffix missing")
    original_windows = bootstrap.is_windows_host
    try:
        bootstrap.is_windows_host = lambda: True
        command = bootstrap.wrapper_command(compiler)
        require(command == [str(compiler.with_suffix(".cmd"))] if compiler.with_suffix(".cmd").is_file()
                else command == [str(compiler)], "unexpected Windows fallback")
        compiler.with_suffix(".cmd").parent.mkdir(parents=True, exist_ok=True)
        compiler.with_suffix(".cmd").write_text("@echo off\n", encoding="utf-8")
        require(bootstrap.wrapper_command(compiler) == [str(compiler.with_suffix(".cmd"))], "Windows .cmd ignored")
    finally:
        bootstrap.is_windows_host = original_windows

    parsed = runner.parse_args(["--children", "wide_math_main.l1"])
    require(parsed.children and parsed.tests == ["wide_math_main.l1"], "child CLI parsing failed")
    rejected = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "run_trace_tests.py"), "--children", "--include-slow"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    require(rejected.returncode == 2, "incompatible CLI modes were accepted")


def test_native_driver_commands(root: Path) -> None:
    """Check source opt-out and runtime controls in native helper commands.

    Args:
        root: Temporary directory for command paths; no compilation is performed.
    """
    fixtures = runner.select_child_fixtures([])
    build_dir = root / "custom build with spaces"
    compiler = build_dir / "bin" / "l1c-stage1"
    original_resolver = driver_inputs.resolve_host_c_compiler
    try:
        driver_inputs.resolve_host_c_compiler = lambda: "clang"
        clang_args = runner.child_build_command(fixtures[0], build_dir, root / "child output")
        require("--runtime-lib" in clang_args, "archive runtime selection missing")
        require(clang_args[clang_args.index("--runtime-lib") + 1] == str(build_dir / "lib"),
                "custom runtime library path changed")
        require("--no-auto-prepare" in clang_args, "archive input enabled automatic preparation")
        require("--no-managed-stdlib" in clang_args, "source imports did not disable managed providers")
        link_args = driver_inputs.native_driver_args(compiler, source=False)
        require("--no-managed-stdlib" not in link_args and "--sys-root" not in link_args,
                "standalone link received source provider controls")
        driver_inputs.resolve_host_c_compiler = lambda: "tcc"
        tcc_args = runner.child_build_command(fixtures[0], build_dir, root / "child output")
        require("--no-managed-stdlib" not in tcc_args, "TinyCC source provider policy changed")
        require("--runtime-lib" not in tcc_args and "--no-auto-prepare" not in tcc_args,
                "TinyCC did not retain automatic native input selection")
    finally:
        driver_inputs.resolve_host_c_compiler = original_resolver


def test_child_phases(root: Path) -> None:
    """Run controlled build and child subprocesses through every failure phase."""

    child_source = textwrap.dedent('''\
        #!/usr/bin/env python3
        import os
        import sys
        mode = os.environ.get('CHILD_TRACE_STUB_MODE', 'healthy')
        print('child stdout marker')
        if mode not in ('empty', 'mem_only'):
            print('[l0][arc] op=retain ptr=0x1 kind=static action=skip', file=sys.stderr)
        if mode in ('healthy', 'leak', 'mem_only'):
            print('[l0][mem] op=new_alloc ptr=0x2 bytes=16 action=ok', file=sys.stderr)
        if mode in ('healthy', 'mem_only'):
            print('[l0][mem] op=drop ptr=0x2 action=free', file=sys.stderr)
        if mode == 'childfail':
            sys.exit(7)
    ''')
    stub = root / "stub compiler.py"
    stub.write_text(textwrap.dedent('''\
        import os
        from pathlib import Path
        import sys

        mode = os.environ.get("CHILD_TRACE_STUB_MODE", "healthy")
        print("build stdout marker")
        print("[l0][mem] op=new_alloc ptr=0x999 bytes=4 action=ok", file=sys.stderr)
        if mode == "buildfail":
            sys.exit(9)
        if mode == "missingexe":
            sys.exit(0)
        target = Path(sys.argv[sys.argv.index("--output") + 1])
        target.write_text(CHILD_SOURCE)
        target.chmod(0o755)
    ''').replace("CHILD_SOURCE", repr(child_source)), encoding="utf-8")

    original_wrapper = runner.wrapper_command
    original_native = runner.native_driver_args
    original_capture = runner.run_captured_binary_output
    try:
        runner.wrapper_command = lambda compiler: [sys.executable, str(stub)]
        runner.native_driver_args = lambda compiler: ["--native-marker"]

        def capture(command: list[str], **kwargs):
            # Only the fake child is a standalone script named as an executable.
            # Build commands already start with the real Python interpreter.
            if os.name == "nt" and len(command) == 1 and command[0].endswith(".exe"):
                command = [sys.executable, *command]
            return original_capture(command, **kwargs)

        runner.run_captured_binary_output = capture
        fixture_root = root / "fixture source with spaces"
        fixture_root.mkdir()
        source = fixture_root / "sample.l1"
        source.write_text("module sample;\n", encoding="utf-8")
        fixture = ChildTraceFixture(0, "sample", source, "math_runtime_compile_test", frozenset({"mem", "arc"}))
        build_dir = root / "custom build with spaces"

        for mode, expected in (
            ("healthy", "TRACE_OK"), ("buildfail", "BUILD_FAIL"),
            ("missingexe", "RUN_FAIL"), ("childfail", "RUN_FAIL"),
            ("empty", "TRACE_FAIL"), ("arc_only", "TRACE_FAIL"), ("mem_only", "TRACE_FAIL"),
            ("leak", "TRACE_FAIL"),
        ):
            case_root = root / mode
            case_root.mkdir()
            env = os.environ.copy()
            env["CHILD_TRACE_STUB_MODE"] = mode
            result = runner.run_child_fixture(fixture, case_root, build_dir, 5, Path(sys.executable), env)
            require(result.status == expected, f"{mode}: expected {expected}, got {result.status}: {result.detail}")
            case_dir = case_root / "sample"
            require((case_dir / "build.stderr.log").is_file(), f"{mode}: build artifact missing")
            require("--native-marker" in runner.child_build_command(fixture, build_dir, case_dir / "sample"),
                    "native input helper was bypassed")
            if mode != "buildfail":
                require((case_dir / "child.stdout.log").is_file() or mode == "missingexe",
                        f"{mode}: child stdout artifact missing")
            if mode == "healthy":
                require("build stdout marker" in (case_dir / "build.stdout.log").read_text(), "build capture missing")
                require("child stdout marker" in (case_dir / "child.stdout.log").read_text(), "child capture missing")
                require("0x999" not in (case_dir / "child.stderr.log").read_text(), "build trace mixed into child")
                require(result.mem_events == 2 and result.arc_events == 1, "healthy family counts incorrect")
            if mode == "leak":
                require("object leak balance" in result.report_text, "analyzer leak was not reported")
            if mode == "arc_only":
                require("mem" in result.detail, "missing memory events not reported")
            if mode == "mem_only":
                require("arc" in result.detail, "missing ARC events not reported")

        env = os.environ.copy()
        env["CHILD_TRACE_STUB_MODE"] = "healthy"
        missing_python = root / "missing analyzer"
        analyzer_result = runner.run_child_fixture(
            fixture, root / "analyzer launch", build_dir, 5, missing_python, env,
        )
        require(analyzer_result.status == "TRACE_FAIL" and "launch failed" in analyzer_result.detail,
                "analyzer launch failure was hidden")
        runner.wrapper_command = lambda compiler: [str(root / "missing compiler")]
        launch_result = runner.run_child_fixture(
            fixture, root / "build launch", build_dir, 5, Path(sys.executable), env,
        )
        require(launch_result.status == "BUILD_FAIL" and "launch failed" in launch_result.detail,
                "build launch failure was hidden")
        runner.wrapper_command = lambda compiler: [sys.executable, str(stub)]

        second = ChildTraceFixture(1, "second", source, "math_runtime_compile_test", frozenset({"mem", "arc"}))
        parallel_root = root / "parallel"
        parallel_root.mkdir()
        require(
            runner.run_children([fixture, second], parallel_root, build_dir, 2, 5, Path(sys.executable), env) == 0,
            "parallel child fixture execution failed",
        )
        require(len(list(parallel_root.glob("children.*/**/child.stderr.log"))) == 2,
                "parallel children did not receive separate trace artifacts")

        retain_root = root / "retain"
        retain_root.mkdir()
        env = os.environ.copy()
        env["CHILD_TRACE_STUB_MODE"] = "buildfail"
        status = runner.run_children([fixture], retain_root, build_dir, 2, 5, Path(sys.executable), env)
        require(status == 1, "child aggregate hid build failure")
        require(list(retain_root.glob("children.*/sample/build.stderr.log")), "child failure artifacts removed")
    finally:
        runner.wrapper_command = original_wrapper
        runner.native_driver_args = original_native
        runner.run_captured_binary_output = original_capture


def test_main_status_and_failure_retention(root: Path) -> None:
    """Cover child selection status and top-level failure artifact retention."""

    original_parse_args = runner.parse_args
    original_resolve_jobs = runner.resolve_trace_job_count
    original_require_env = runner.require_repo_stage1_test_env
    original_resolve_artifacts = runner.resolve_artifact_dir
    original_run_children = runner.run_children
    build_dir = root / "main build"
    repo_env = os.environ.copy()
    try:
        unknown_args = original_parse_args(["--children", "unknown"])
        runner.parse_args = lambda argv=None: unknown_args
        runner.resolve_trace_job_count = lambda: 1
        runner.require_repo_stage1_test_env = lambda context: (
            Path(sys.executable), Path("l1c-stage1"), build_dir, repo_env,
        )
        require(runner.main() == 2, "unknown child selector did not return status 2")

        retained_root = root / "retained main failure"
        retained_root.mkdir()
        failure_args = original_parse_args(["--children", "wide_math_main"])
        runner.parse_args = lambda argv=None: failure_args
        runner.resolve_artifact_dir = lambda args: (retained_root, True)

        def fail_children(*args, **kwargs) -> int:
            (retained_root / "failure.marker").write_text("retained\n", encoding="utf-8")
            return 1

        runner.run_children = fail_children
        require(runner.main() == 1, "child aggregate failure did not reach main")
        require((retained_root / "failure.marker").is_file(),
                "main removed child failure artifacts")
    finally:
        runner.parse_args = original_parse_args
        runner.resolve_trace_job_count = original_resolve_jobs
        runner.require_repo_stage1_test_env = original_require_env
        runner.resolve_artifact_dir = original_resolve_artifacts
        runner.run_children = original_run_children


def main() -> int:
    """Run standalone fast child runner regressions."""

    try:
        with tempfile.TemporaryDirectory(prefix="l1_child_trace_runner.") as directory:
            root = Path(directory)
            test_selection_and_commands(root)
            test_native_driver_commands(root)
            test_child_phases(root)
            test_main_status_and_failure_retention(root)
    except (AssertionError, OSError) as exc:
        print(f"l1c_stage1_child_trace_runner_test: FAIL: {exc}")
        return 1
    print("l1c_stage1_child_trace_runner_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
