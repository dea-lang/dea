#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for L1 Stage 1 trace-runner helper behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_DIR = SCRIPT_DIR.parent / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

import test_runner_common as common
import run_trace_tests
import run_tests as normal_runner


def test_normal_runner_ci_only_selection() -> str | None:
    """Require default exclusion, explicit selectors, and CI-inclusive discovery to compose correctly."""

    expected_ci_only = {
        "l1c_stage1_arc_trace_regression_test.py",
        "l1c_stage1_installed_preparation_test.py",
        "l1c_stage1_preparation_test.py",
        "preparation_ownership_test.py",
        "slice_trace_test",
        "math_runtime_compile_test",
        "mul_runtime_compile_test",
        "preparation_identity_test.py",
    }
    if common.CI_ONLY_NORMAL_STAGE1_TESTS != expected_ci_only:
        return f"unexpected Stage 1 CI-only normal test classification: {common.CI_ONLY_NORMAL_STAGE1_TESTS}"
    discovered = normal_runner.discover_stage1_l0_tests()
    normal = normal_runner.select_cases(discovered, [])
    included = normal_runner.select_cases(discovered, [], include_ci_only=True)
    if len(included) != len(discovered) or expected_ci_only.intersection(case.name for case in normal):
        return "actual discovery did not preserve the complete CI union"
    for name in expected_ci_only:
        if [case.name for case in normal_runner.select_cases(discovered, [name])] != [name]:
            return f"CI-only case is not directly selectable: {name}"
    if not {"mul_runtime_overflow_test.py", "l1c_stage1_managed_preparation_test.py"}.issubset(
        case.name for case in normal
    ):
        return "local discovery lost overflow or representative managed preparation coverage"
    if not any(
        case.name == "l1c_stage1_arc_trace_regression_test.py"
        for case in normal_runner.discover_stage1_l0_tests()
    ):
        return "shared ARC regression is not discovered by the Stage 1 normal runner"

    cases = [
        common.TestCase(0, "array_test", Path("array_test.l0"), "l0"),
        common.TestCase(1, "slice_trace_test", Path("slice_trace_test.l0"), "l0"),
    ]
    default_cases = normal_runner.select_cases(cases, [])
    if [case.name for case in default_cases] != ["array_test"]:
        return f"default selection did not exclude CI-only cases: {[case.name for case in default_cases]}"

    explicit_cases = normal_runner.select_cases(cases, ["slice_trace_test"])
    if [case.name for case in explicit_cases] != ["slice_trace_test"]:
        return f"explicit selection did not run the CI-only case: {[case.name for case in explicit_cases]}"
    included_selector_cases = normal_runner.select_cases(cases, ["array_test"], include_ci_only=True)
    if [case.name for case in included_selector_cases] != ["array_test"]:
        return f"CI-inclusive mode ignored explicit selectors: {[case.name for case in included_selector_cases]}"

    try:
        normal_runner.select_cases(cases, ["missing_test"])
    except ValueError:
        pass
    else:
        return "invalid selectors did not raise ValueError"

    included_cases = normal_runner.select_cases(cases, [], include_ci_only=True)
    if [case.name for case in included_cases] != ["array_test", "slice_trace_test"]:
        return f"CI-inclusive selection missed cases: {[case.name for case in included_cases]}"

    if not normal_runner.parse_args(["--include-ci-only"]).include_ci_only:
        return "--include-ci-only was not parsed"
    help_output = io.StringIO()
    try:
        with redirect_stdout(help_output):
            normal_runner.parse_args(["--help"])
    except SystemExit as exc:
        if exc.code != 0:
            return f"runner help exited with unexpected status: {exc.code}"
    else:
        return "--help did not exit"
    if "--include-ci-only" not in help_output.getvalue():
        return "runner help does not expose --include-ci-only"
    return None


def test_trace_selection_ignores_normal_cost_classification() -> str | None:
    """Retain CI-only trace cases and the independent slow-trace opt-in policy."""

    names = {case.name for case in run_trace_tests.select_trace_cases([])}
    if not {"slice_trace_test", "mul_runtime_compile_test"}.issubset(names) or "math_runtime_compile_test" in names:
        return f"incorrect default trace selection: {sorted(names)}"
    explicit = run_trace_tests.select_trace_cases(["math_runtime_compile_test"])
    if [case.name for case in explicit] != ["math_runtime_compile_test"]:
        return "explicit selection did not include the slow CI-only trace case"
    if "math_runtime_compile_test" not in {
        case.name for case in run_trace_tests.select_trace_cases([], include_slow=True)
    }:
        return "slow-inclusive trace selection missed a CI-only normal case"
    return None


def test_trace_main_selection_and_slow_logging() -> str | None:
    """Exercise aggregate and explicit selection through the complete runner path."""

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        result = run_trace_tests.TraceResult(0, "sample", "TRACE_OK", "", "", "", root / "trace", 0, 0, 0, 0)
        for argv in ([], ["math_runtime_compile_test"], ["--include-slow"]):
            args = run_trace_tests.parse_args(argv)
            output = io.StringIO()
            with (
                patch.object(run_trace_tests, "parse_args", return_value=args),
                patch.object(run_trace_tests, "resolve_trace_job_count", return_value=1),
                patch.object(run_trace_tests, "require_repo_stage1_test_env", return_value=(sys.executable, root, root, {})),
                patch.object(run_trace_tests, "resolve_artifact_dir", return_value=(root, False)),
                patch.object(run_trace_tests, "run_one", return_value=result) as run_one,
                redirect_stdout(output),
            ):
                if run_trace_tests.main() != 0:
                    return f"trace runner main failed for {argv}"
            selected = {call.args[1] for call in run_one.call_args_list}
            if not argv and not {"slice_trace_test", "mul_runtime_compile_test"}.issubset(selected):
                return "aggregate trace main lost CI-only normal cases"
            if argv == ["math_runtime_compile_test"] and selected != {"math_runtime_compile_test"}:
                return "explicit trace main ignored the slow selector"
            if argv == ["--include-slow"] and "math_runtime_compile_test" not in selected:
                return "slow-inclusive trace main lost the slow case"
            if ("Skipping slow trace tests by default" in output.getvalue()) != (not argv):
                return f"incorrect slow-case logging for {argv}"
    return None


def test_native_support_selection() -> str | None:
    """Require ordinary and trace tests to share explicit support dependencies."""

    for name, requires_preparation in (
        ("array_test", False), ("preparation_test", True), ("l1c_lib_test", True),
        ("link_driver_test", True),
        ("mul_runtime_test", False),
        ("mul_runtime_compile_test", True),
    ):
        path = common.TESTS_DIR / f"{name}.l0"
        args = common.stage1_test_support_args(path)
        selected = [Path(arg).name for arg in args[1::2]]
        if ("preparation_support.c" in selected) != requires_preparation:
            return f"incorrect preparation support for {name}: {args}"
        if not {"interface_fingerprint.c", "compiler_support.c"}.issubset(selected):
            return f"missing common native support for {name}: {args}"
        case = common.TestCase(0, name, path, "l0")
        normal = common.build_normal_test_command(case, common.REPO_ROOT / "build/dea")
        if normal[-len(args)-1:-1] != args:
            return f"normal runner did not use declared support for {name}: {normal}"
    return None


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l1c_stage1_trace_runner_common_test: FAIL: {message}")
    return 1


def test_resolve_trace_job_count_matches_normal_default_policy() -> str | None:
    """Return one failure message, or `None` when trace jobs match the normal default."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    old_cpu_count = os.cpu_count
    try:
        os.environ.pop("L1_TRACE_TEST_JOBS", None)
        os.environ.pop("L1_TEST_JOBS", None)
        os.cpu_count = lambda: 64
        jobs = common.resolve_trace_job_count()
        normal_jobs = common.resolve_job_count()
        if jobs != normal_jobs:
            return (
                "expected trace runner default jobs to match normal jobs, "
                f"got trace={jobs} normal={normal_jobs}"
            )
    finally:
        os.cpu_count = old_cpu_count
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_trace_job_count_honors_trace_override_first() -> str | None:
    """Return one failure message, or `None` when the trace override wins."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    try:
        os.environ["L1_TRACE_TEST_JOBS"] = "3"
        os.environ["L1_TEST_JOBS"] = "9"
        jobs = common.resolve_trace_job_count()
        if jobs != 3:
            return f"expected L1_TRACE_TEST_JOBS to win, got {jobs}"
    finally:
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_trace_job_count_falls_back_to_normal_override() -> str | None:
    """Return one failure message, or `None` when the normal override still applies."""

    old_trace_jobs = os.environ.get("L1_TRACE_TEST_JOBS")
    old_jobs = os.environ.get("L1_TEST_JOBS")
    try:
        os.environ.pop("L1_TRACE_TEST_JOBS", None)
        os.environ["L1_TEST_JOBS"] = "5"
        jobs = common.resolve_trace_job_count()
        if jobs != 5:
            return f"expected L1_TEST_JOBS fallback to win, got {jobs}"
    finally:
        if old_trace_jobs is None:
            os.environ.pop("L1_TRACE_TEST_JOBS", None)
        else:
            os.environ["L1_TRACE_TEST_JOBS"] = old_trace_jobs
        if old_jobs is None:
            os.environ.pop("L1_TEST_JOBS", None)
        else:
            os.environ["L1_TEST_JOBS"] = old_jobs
    return None


def test_resolve_artifact_dir_prefers_cli_and_keeps_explicit_dirs() -> str | None:
    """Return one failure message, or `None` when explicit artifact dirs are preserved."""

    old_artifact_dir = os.environ.get(run_trace_tests.TRACE_ARTIFACT_DIR_ENV)
    base_dir = Path(tempfile.mkdtemp(prefix="l1_trace_runner_common_test."))
    try:
        env_dir = base_dir / "env-artifacts"
        cli_dir = base_dir / "cli-artifacts"
        os.environ[run_trace_tests.TRACE_ARTIFACT_DIR_ENV] = str(env_dir)
        args = run_trace_tests.parse_args(["--artifact-dir", str(cli_dir)])
        artifact_dir, cleanup = run_trace_tests.resolve_artifact_dir(args)
        if artifact_dir != cli_dir.resolve(strict=False):
            return f"expected CLI artifact dir to win, got {artifact_dir}"
        if cleanup:
            return "expected explicit artifact dir to disable cleanup"
        if not cli_dir.is_dir():
            return f"expected CLI artifact dir to be created: {cli_dir}"
    finally:
        if old_artifact_dir is None:
            os.environ.pop(run_trace_tests.TRACE_ARTIFACT_DIR_ENV, None)
        else:
            os.environ[run_trace_tests.TRACE_ARTIFACT_DIR_ENV] = old_artifact_dir
        shutil.rmtree(base_dir, ignore_errors=True)
    return None


def _grandchild_writer_command(tag: str) -> list[str]:
    """Return one Python command that leaves a delayed grandchild writing to inherited stdio."""

    child_code = textwrap.dedent(
        f"""\
        import subprocess
        import sys
        grandchild = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys,time; time.sleep(0.1); "
                "sys.stdout.write({tag!r} + ' late stdout\\\\n'); sys.stdout.flush(); "
                "sys.stderr.write({tag!r} + ' late stderr\\\\n'); sys.stderr.flush()",
            ],
            stdout=None,
            stderr=None,
            close_fds=False,
        )
        sys.stdout.write({tag!r} + " early stdout\\n")
        sys.stdout.flush()
        sys.stderr.write({tag!r} + " early stderr\\n")
        sys.stderr.flush()
        """
    )
    return [sys.executable, "-c", child_code]


def test_run_captured_binary_output_waits_for_inherited_grandchild_writers() -> str | None:
    """Return one failure message, or `None` when late inherited writes are captured fully."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        completed = common.run_captured_binary_output(
            _grandchild_writer_command("solo"),
            cwd=Path.cwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if completed.returncode != 0:
            return f"expected delayed grandchild writer command to succeed, got rc={completed.returncode}"
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        for expected in ("solo early stdout", "solo late stdout"):
            if expected not in stdout_text:
                return f"missing stdout line {expected!r} in {stdout_text!r}"
        for expected in ("solo early stderr", "solo late stderr"):
            if expected not in stderr_text:
                return f"missing stderr line {expected!r} in {stderr_text!r}"
    return None


def test_run_captured_binary_output_supports_parallel_calls() -> str | None:
    """Return one failure message, or `None` when multiple delayed captures complete in parallel."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        root = Path(tmp_dir)

        def run_one(index: int) -> tuple[int, str, str, int]:
            tag = f"case-{index}"
            stdout_path = root / f"{tag}.stdout.log"
            stderr_path = root / f"{tag}.stderr.log"
            completed = common.run_captured_binary_output(
                _grandchild_writer_command(tag),
                cwd=Path.cwd(),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            return (
                completed.returncode,
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"),
                index,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = [future.result() for future in [executor.submit(run_one, index) for index in range(4)]]

        for returncode, stdout_text, stderr_text, index in results:
            if returncode != 0:
                return f"parallel capture case {index} failed with rc={returncode}"
            tag = f"case-{index}"
            for expected in (f"{tag} early stdout", f"{tag} late stdout"):
                if expected not in stdout_text:
                    return f"parallel capture case {index} missing stdout line {expected!r}"
            for expected in (f"{tag} early stderr", f"{tag} late stderr"):
                if expected not in stderr_text:
                    return f"parallel capture case {index} missing stderr line {expected!r}"
    return None


def test_run_captured_binary_output_streams_large_artifacts_without_result_copies() -> str | None:
    """Return one failure message, or `None` when large output stays file-backed."""

    with tempfile.TemporaryDirectory(prefix="l1_trace_runner_common.") as tmp_dir:
        stdout_path = Path(tmp_dir) / "stdout.log"
        stderr_path = Path(tmp_dir) / "stderr.log"
        stdout_size = common.CAPTURE_CHUNK_SIZE * 8 + 3
        stderr_size = common.CAPTURE_CHUNK_SIZE * 5 + 1
        completed = common.run_captured_binary_output(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.stdout.buffer.write(b'x' * {stdout_size}); "
                    f"sys.stderr.buffer.write(b'y' * {stderr_size})"
                ),
            ],
            cwd=Path.cwd(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if completed.returncode != 0:
            return f"expected large capture to succeed, got rc={completed.returncode}"
        if hasattr(completed, "stdout") or hasattr(completed, "stderr"):
            return "capture result unexpectedly retained stdout/stderr payloads"
        if completed.stdout_bytes != stdout_size or stdout_path.stat().st_size != stdout_size:
            return f"unexpected streamed stdout size: result={completed.stdout_bytes} file={stdout_path.stat().st_size}"
        if completed.stderr_bytes != stderr_size or stderr_path.stat().st_size != stderr_size:
            return f"unexpected streamed stderr size: result={completed.stderr_bytes} file={stderr_path.stat().st_size}"
    return None


def main() -> int:
    """Program entrypoint."""

    checks = [
        test_normal_runner_ci_only_selection,
        test_trace_selection_ignores_normal_cost_classification,
        test_trace_main_selection_and_slow_logging,
        test_native_support_selection,
        test_resolve_trace_job_count_matches_normal_default_policy,
        test_resolve_trace_job_count_honors_trace_override_first,
        test_resolve_trace_job_count_falls_back_to_normal_override,
        test_resolve_artifact_dir_prefers_cli_and_keeps_explicit_dirs,
        test_run_captured_binary_output_waits_for_inherited_grandchild_writers,
        test_run_captured_binary_output_supports_parallel_calls,
        test_run_captured_binary_output_streams_large_artifacts_without_result_copies,
    ]
    for check in checks:
        message = check()
        if message is not None:
            return fail(message)

    print("l1c_stage1_trace_runner_common_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
