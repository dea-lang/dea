#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Shared helpers for L1 Stage 1 test runners."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

MONOREPO_SCRIPTS_ROOT = Path(__file__).resolve().parents[4] / "scripts"
L1_SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
for scripts_root in (MONOREPO_SCRIPTS_ROOT, L1_SCRIPTS_ROOT):
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))

from dea_tooling.bootstrap import resolve_bootstrap_compiler, wrapper_command
from build_stage1_l1c import stage1_support_args, stage1_support_build_env


DEFAULT_MAX_JOBS = 12
SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_DIR = SCRIPT_DIR.parent
REPO_ROOT = STAGE_DIR.parent.parent
MONOREPO_ROOT = REPO_ROOT.parent
TESTS_DIR = STAGE_DIR / "tests"
L1_BUILD_DIR_ENV = "L1_BUILD_DIR"
DEFAULT_L1_BUILD_DIR = "build/dea"
L1_BOOTSTRAP_L0C_ENV = "L1_BOOTSTRAP_L0C"
TRACE_EXCLUDED_STAGE1_TESTS: set[str] = set()
TRACE_SLOW_STAGE1_TESTS: set[str] = {"math_runtime_compile_test"}


def repo_venv_bin_dir() -> Path:
    """Return the repo-local virtualenv executable directory for the host platform."""

    candidates = [
        MONOREPO_ROOT / ".venv" / "bin",
        MONOREPO_ROOT / ".venv" / "Scripts",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[1] if os.name == "nt" else candidates[0]


REPO_VENV_BIN = repo_venv_bin_dir()


def _repo_venv_python() -> Path:
    """Return the Python executable inside the repo-local virtualenv."""

    if REPO_VENV_BIN.name == "Scripts":
        return REPO_VENV_BIN / "python.exe"
    exe = REPO_VENV_BIN / "python.exe"
    if exe.is_file():
        return exe
    return REPO_VENV_BIN / "python"


REPO_VENV_PYTHON = _repo_venv_python()


@dataclass(frozen=True)
class TestCase:
    """One discovered L1 Stage 1 test case."""

    index: int
    name: str
    path: Path
    kind: str


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result."""

    returncode: int
    output: str


def prepend_path(existing_path: str, entries: list[Path]) -> str:
    """Return `existing_path` with `entries` prepended once each."""

    ordered: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        text = str(entry)
        if text and text not in seen:
            ordered.append(text)
            seen.add(text)

    for entry in existing_path.split(os.pathsep):
        if entry and entry not in seen:
            ordered.append(entry)
            seen.add(entry)

    return os.pathsep.join(ordered)


def resolve_l1_build_dir_text() -> str:
    """Return the effective repo-local L1 build directory text."""

    from_env = os.environ.get(L1_BUILD_DIR_ENV, "").strip()
    if from_env:
        return from_env
    return DEFAULT_L1_BUILD_DIR


def resolve_repo_path(path_text: str) -> Path:
    """Resolve one repo-relative or absolute path text against the repo root."""

    raw_path = Path(path_text)
    if raw_path.is_absolute():
        return raw_path.resolve(strict=False)
    return (REPO_ROOT / raw_path).resolve(strict=False)


def resolve_l1_build_dir() -> tuple[str, Path]:
    """Return the effective `L1_BUILD_DIR` text plus resolved path."""

    build_dir_text = resolve_l1_build_dir_text()
    return build_dir_text, resolve_repo_path(build_dir_text)


def repo_stage1_command() -> list[str]:
    """Return the command used to invoke the upstream `l0c` bootstrap compiler for implementation tests."""

    _, command = resolve_bootstrap_compiler(
        override_text=os.environ.get(L1_BOOTSTRAP_L0C_ENV),
        default_path=MONOREPO_ROOT / "l0" / "build" / "dea" / "bin" / "l0c-stage2",
        env_var_name=L1_BOOTSTRAP_L0C_ENV,
        setup_hint="run `make -C l0 use-dev-stage2`",
    )
    return command


def build_repo_test_env(build_dir_text: str, build_dir: Path) -> dict[str, str]:
    """Return the sanitized repo-local environment for L1 Stage 1 implementation tests."""

    env = os.environ.copy()
    env[L1_BUILD_DIR_ENV] = build_dir_text
    env["L0_HOME"] = str(MONOREPO_ROOT / "l0" / "compiler")
    env["L0_SYSTEM"] = str(MONOREPO_ROOT / "l0" / "compiler" / "shared" / "l0" / "stdlib")
    env.pop("L0_RUNTIME_INCLUDE", None)
    env.pop("L0_RUNTIME_LIB", None)
    env["L1_HOME"] = str(REPO_ROOT / "compiler")
    env.pop("L1_SYSTEM", None)
    env.pop("L1_RUNTIME_INCLUDE", None)
    env.pop("L1_RUNTIME_LIB", None)
    env["PATH"] = prepend_path(env.get("PATH", ""), [REPO_VENV_BIN, build_dir / "bin"])
    return stage1_support_build_env(env)


def require_repo_stage1_test_env(entrypoint_name: str) -> tuple[Path, str, Path, dict[str, str]]:
    """Return the repo-local Python path, build dir, and sanitized env."""

    if not REPO_VENV_PYTHON.is_file():
        raise RuntimeError(
            f"{entrypoint_name}: missing repo virtual environment at {REPO_VENV_PYTHON}; run `make venv`"
        )

    build_dir_text, build_dir = resolve_l1_build_dir()
    stage1_wrapper = build_dir / "bin" / "l1c-stage1"
    env_script = build_dir / "bin" / "l1-env.sh"
    if not stage1_wrapper.is_file() or not env_script.is_file():
        raise RuntimeError(
            f"{entrypoint_name}: missing repo-local L1 Stage 1 tools under {build_dir}; "
            f"run `make L1_BUILD_DIR={build_dir_text} build-stage1`"
        )

    return (
        REPO_VENV_PYTHON,
        build_dir_text,
        build_dir,
        build_repo_test_env(build_dir_text, build_dir),
    )


def discover_stage1_l0_tests() -> list[TestCase]:
    """Return discovered L1 Stage 1 implementation tests in deterministic order."""

    cases: list[TestCase] = []
    index = 0
    for path in sorted(TESTS_DIR.glob("*.l0")):
        cases.append(TestCase(index=index, name=path.stem, path=path, kind="l0"))
        index += 1
    for path in sorted(TESTS_DIR.glob("*_test.py")):
        cases.append(TestCase(index=index, name=path.name, path=path, kind="python"))
        index += 1
    return cases


def discover_trace_l0_tests(*, include_slow: bool = False) -> list[TestCase]:
    """Return trace-eligible `.l0` L1 Stage 1 implementation tests in deterministic order."""

    filtered = [
        case
        for case in discover_stage1_l0_tests()
        if case.kind == "l0"
        and case.name not in TRACE_EXCLUDED_STAGE1_TESTS
        and (include_slow or case.name not in TRACE_SLOW_STAGE1_TESTS)
    ]
    return [
        TestCase(index=index, name=case.name, path=case.path, kind=case.kind)
        for index, case in enumerate(filtered)
    ]


def resolve_job_count() -> int:
    """Return the worker count for the normal L1 Stage 1 test runner."""

    jobs_text = os.environ.get("L1_TEST_JOBS", "").strip()
    if jobs_text:
        try:
            jobs = int(jobs_text)
        except ValueError as exc:
            raise ValueError(f"L1_TEST_JOBS must be a positive integer, got {jobs_text!r}") from exc
        if jobs < 1:
            raise ValueError(f"L1_TEST_JOBS must be a positive integer, got {jobs_text!r}")
        return jobs

    cpu_count = os.cpu_count() or 1
    return max(1, min(cpu_count, DEFAULT_MAX_JOBS))


def resolve_trace_job_count() -> int:
    """Return the worker count for the L1 Stage 1 trace runner."""

    jobs_text = os.environ.get("L1_TRACE_TEST_JOBS", "").strip()
    if jobs_text:
        try:
            jobs = int(jobs_text)
        except ValueError as exc:
            raise ValueError(f"L1_TRACE_TEST_JOBS must be a positive integer, got {jobs_text!r}") from exc
        if jobs < 1:
            raise ValueError(f"L1_TRACE_TEST_JOBS must be a positive integer, got {jobs_text!r}")
        return jobs
    return resolve_job_count()


def build_normal_test_command(case: TestCase, build_dir: Path) -> list[str]:
    """Return the subprocess command for one normal L1 Stage 1 implementation test."""

    if case.kind == "l0":
        return [
            *repo_stage1_command(),
            "--project-root",
            "compiler/stage1_l0/src",
            "--run",
            *stage1_support_args(),
            str(case.path),
        ]
    if case.kind == "python":
        return [str(REPO_VENV_PYTHON), str(case.path)]
    raise ValueError(f"Unsupported test kind: {case.kind}")


def run_combined_output(command: list[str], *, env: dict[str, str] | None = None) -> CommandResult:
    """Run one subprocess and capture stdout/stderr as one stream."""

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return CommandResult(returncode=completed.returncode, output=completed.stdout)


def run_captured_binary_output(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one subprocess, capture binary stdout/stderr, and optionally write artifacts."""
    temp_dir = Path(tempfile.mkdtemp(prefix="l1_trace_capture."))
    tmp_stdout_path = temp_dir / "stdout.bin"
    tmp_stderr_path = temp_dir / "stderr.bin"

    try:
        with tmp_stdout_path.open("wb") as stdout_file:
            with tmp_stderr_path.open("wb") as stderr_file:
                completed = subprocess.run(
                    command,
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    check=False,
                )

        stdout_bytes = tmp_stdout_path.read_bytes()
        stderr_bytes = tmp_stderr_path.read_bytes()
        if stdout_path is not None:
            stdout_path.write_bytes(stdout_bytes)
        if stderr_path is not None:
            stderr_path.write_bytes(stderr_bytes)
        return subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
        )
    finally:
        tmp_stdout_path.unlink(missing_ok=True)
        tmp_stderr_path.unlink(missing_ok=True)
        temp_dir.rmdir()


def print_output_block(text: str) -> None:
    """Print captured output without losing the final line."""

    if not text:
        return

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def first_lines(text: str, limit: int) -> str:
    """Return at most `limit` lines from `text`."""

    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit]) + "\n"


def summarize_failures(results: Iterable[TestCase]) -> str:
    """Return a stable one-line failed-test summary."""

    names = [result.name for result in results]
    if not names:
        return ""
    return " ".join(names)
