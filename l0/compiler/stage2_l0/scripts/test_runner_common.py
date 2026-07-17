#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Shared helpers for Stage 2 test runners."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_MAX_JOBS = 12
SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_DIR = SCRIPT_DIR.parent
REPO_ROOT = STAGE_DIR.parent.parent
MONOREPO_ROOT = REPO_ROOT.parent
TESTS_DIR = STAGE_DIR / "tests"
DEA_BUILD_DIR_ENV = "DEA_BUILD_DIR"
TRACE_EXCLUDED_L0_TESTS: set[str] = set()


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
    # MSYS2 MinGW Python creates bin/python.exe, not bin/python.
    exe = REPO_VENV_BIN / "python.exe"
    if exe.is_file():
        return exe
    return REPO_VENV_BIN / "python"


REPO_VENV_PYTHON = _repo_venv_python()


def source_tree_l0c_command() -> list[str]:
    """Return the command used to invoke the source-tree Stage 1 compiler."""

    if os.name == "nt":
        cmd_path = REPO_ROOT / "scripts" / "l0c.cmd"
        if cmd_path.is_file():
            return [str(cmd_path)]
        return [str(REPO_VENV_PYTHON), str(REPO_ROOT / "compiler" / "stage1_py" / "l0c.py")]
    return ["./scripts/l0c"]


def is_windows_host() -> bool:
    """Return whether the current host should follow Windows runner behavior."""

    if os.name == "nt":
        return True
    if os.environ.get("OS") == "Windows_NT":
        return True
    return bool(os.environ.get("MSYSTEM", "").strip())


@dataclass(frozen=True)
class TestCase:
    """One discovered Stage 2 test case."""

    index: int
    name: str
    path: Path
    kind: str


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result."""

    returncode: int
    output: str


def resolve_repo_path(path_text: str) -> Path:
    """Resolve one repo-relative or absolute path text against the repo root."""

    raw_path = Path(path_text)
    if raw_path.is_absolute():
        return raw_path.resolve(strict=False)
    return (REPO_ROOT / raw_path).resolve(strict=False)


def resolve_dea_build_dir_text() -> str:
    """Return the effective repo-local `DEA_BUILD_DIR` text."""

    from_env = os.environ.get(DEA_BUILD_DIR_ENV, "").strip()
    if from_env:
        return from_env

    completed = subprocess.run(
        ["make", "-s", "print-dea-build-dir"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not resolve DEA_BUILD_DIR; `make -s print-dea-build-dir` failed:\n"
            f"{completed.stdout}"
        )

    dea_build_dir_text = completed.stdout.strip()
    if not dea_build_dir_text:
        raise RuntimeError("could not resolve DEA_BUILD_DIR; `make -s print-dea-build-dir` produced no output")
    return dea_build_dir_text


def resolve_dea_build_dir() -> tuple[str, Path]:
    """Return the effective `DEA_BUILD_DIR` text plus resolved path."""

    dea_build_dir_text = resolve_dea_build_dir_text()
    return dea_build_dir_text, resolve_repo_path(dea_build_dir_text)


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


def build_repo_test_env(dea_build_dir_text: str, dea_build_dir: Path) -> dict[str, str]:
    """Return the sanitized repo-local environment for Stage 2 tests."""

    env = os.environ.copy()
    env[DEA_BUILD_DIR_ENV] = dea_build_dir_text
    env["L0_HOME"] = str(REPO_ROOT / "compiler")
    env.pop("L0_SYSTEM", None)
    env.pop("L0_RUNTIME_INCLUDE", None)
    env.pop("L0_RUNTIME_LIB", None)
    env["PATH"] = prepend_path(env.get("PATH", ""), [REPO_VENV_BIN, dea_build_dir / "bin"])
    return env


def build_normal_test_env(case: TestCase, repo_env: dict[str, str]) -> dict[str, str]:
    """Return the repo-local child env for one normal Stage 2 test case."""

    if case.kind == "python":
        return repo_env

    env = repo_env.copy()
    env.pop(DEA_BUILD_DIR_ENV, None)
    return env


def require_repo_stage2_test_env(entrypoint_name: str) -> tuple[Path, str, Path, dict[str, str]]:
    """Return the repo-local Python path, `DEA_BUILD_DIR`, and sanitized env for one entrypoint."""

    if not REPO_VENV_PYTHON.is_file():
        raise RuntimeError(
            f"{entrypoint_name}: missing repo virtual environment at {REPO_VENV_PYTHON}; run `make venv`"
        )

    dea_build_dir_text, dea_build_dir = resolve_dea_build_dir()
    stage2_wrapper = dea_build_dir / "bin" / "l0c-stage2"
    env_script = dea_build_dir / "bin" / "l0-env.sh"
    if not stage2_wrapper.is_file() or not env_script.is_file():
        raise RuntimeError(
            f"{entrypoint_name}: missing repo-local Stage 2 tools under {dea_build_dir}; "
            f"run `make DEA_BUILD_DIR={dea_build_dir_text} install-dev-stage2`"
        )

    return (
        REPO_VENV_PYTHON,
        dea_build_dir_text,
        dea_build_dir,
        build_repo_test_env(dea_build_dir_text, dea_build_dir),
    )


def discover_l0_tests() -> list[TestCase]:
    """Return discovered `.l0` Stage 2 tests in deterministic order."""

    return [
        TestCase(index=index, name=path.stem, path=path, kind="l0")
        for index, path in enumerate(sorted(TESTS_DIR.glob("*.l0")))
    ]


def discover_trace_l0_tests() -> list[TestCase]:
    """Return trace-eligible `.l0` Stage 2 tests in deterministic order."""

    filtered = [case for case in discover_l0_tests() if case.name not in TRACE_EXCLUDED_L0_TESTS]
    return [
        TestCase(index=index, name=case.name, path=case.path, kind=case.kind)
        for index, case in enumerate(filtered)
    ]


def discover_stage2_tests() -> list[TestCase]:
    """Return discovered Stage 2 test cases in deterministic order."""

    cases: list[TestCase] = []
    index = 0

    for path in sorted(TESTS_DIR.glob("*.l0")):
        cases.append(TestCase(index=index, name=path.stem, path=path, kind="l0"))
        index += 1

    for path in sorted(TESTS_DIR.glob("*_test.py")):
        cases.append(TestCase(index=index, name=path.name, path=path, kind="python"))
        index += 1

    return cases


def resolve_job_count() -> int:
    """Return the worker count for the normal Stage 2 test runner."""

    jobs_text = os.environ.get("L0_TEST_JOBS", "").strip()
    if jobs_text:
        try:
            jobs = int(jobs_text)
        except ValueError as exc:
            raise ValueError(f"L0_TEST_JOBS must be a positive integer, got {jobs_text!r}") from exc
        if jobs < 1:
            raise ValueError(f"L0_TEST_JOBS must be a positive integer, got {jobs_text!r}")
        return jobs

    cpu_count = os.cpu_count() or 1
    return max(1, min(cpu_count, DEFAULT_MAX_JOBS))


def resolve_trace_job_count() -> int:
    """Return the worker count for the Stage 2 trace runner."""

    return resolve_job_count()


def run_captured_binary_output(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one subprocess, capture binary stdout/stderr, and optionally write artifacts."""

    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    stdout_bytes = completed.stdout if completed.stdout is not None else b""
    stderr_bytes = completed.stderr if completed.stderr is not None else b""
    if stdout_path is not None:
        stdout_path.write_bytes(stdout_bytes)
    if stderr_path is not None:
        stderr_path.write_bytes(stderr_bytes)
    return completed


def build_normal_test_command(case: TestCase, python_path: Path) -> list[str]:
    """Return the subprocess command for one normal Stage 2 test."""

    if case.kind == "l0":
        return [*source_tree_l0c_command(), "--project-root", "compiler/stage2_l0/src", "--run", str(case.path)]
    if case.kind == "python":
        return [str(python_path), str(case.path)]
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
