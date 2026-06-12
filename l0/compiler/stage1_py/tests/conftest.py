#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""Pytest configuration and shared fixtures for the Stage 1 L0 compiler tests.

This module provides common setup, tear-down, and utility functions used
across the various test suites, including tools for generating source files,
running the compiler, and executing the resulting C code.
"""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

STAGE1_ROOT = Path(__file__).parent.parent
REPO_ROOT = STAGE1_ROOT.parents[1]
sys.path.insert(0, str(STAGE1_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(1, str(REPO_ROOT))

from l0_driver import L0Driver
from l0_paths import SourceSearchPaths

import shutil

import pytest


def _quiet_progress_enabled(config) -> bool:
    """Return whether the Stage 1 quiet-progress mode is enabled."""
    return bool(config.getoption("--quiet-progress"))


def _quiet_progress_is_quiet_cli(config) -> bool:
    """Return whether quiet-progress is active under pytest quiet mode."""
    return _quiet_progress_enabled(config) and config.option.verbose < 0


def _resolved_xdist_worker_count(config) -> int | None:
    """Return the resolved xdist worker count for quiet controller output."""
    if config.getoption("dist") == "no" or not config.getoption("tx"):
        return None

    numprocesses = config.option.numprocesses
    if numprocesses in {"auto", "logical"}:
        return config.hook.pytest_xdist_auto_num_workers(config=config)

    return int(numprocesses)


def _disable_terminal_progress(config) -> None:
    """Disable pytest's built-in progress meter for quiet-progress mode."""
    if not _quiet_progress_enabled(config):
        return

    terminal_reporter = config.pluginmanager.getplugin("terminalreporter")
    if terminal_reporter is None or not hasattr(terminal_reporter, "_show_progress_info"):
        return

    # Pytest computes progress display mode during terminal reporter startup.
    # Quiet-progress overrides that late-bound state so xdist runs do not emit
    # the final colored/right-aligned percentage line.
    terminal_reporter._show_progress_info = False


def pytest_addoption(parser):
    parser.addoption(
        "--quiet-progress",
        action="store_true",
        default=False,
        help="Suppress per-test progress characters like ...F... while keeping failures and summary",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_report_teststatus(report, config):
    if not _quiet_progress_enabled(config):
        return None

    # Mirror pytest's default categories so summary accounting stays correct,
    # but suppress the noisy progress characters for non-failures.
    if report.when in {"setup", "teardown"}:
        if report.failed:
            return "error", "E", "ERROR"
        if report.skipped:
            return "skipped", "", "SKIPPED"
        return "", "", ""

    if report.when == "call":
        if report.passed:
            return "passed", "", "PASSED"
        if report.failed:
            return "failed", "F", "FAILED"
        if report.skipped:
            return "skipped", "", "SKIPPED"

    return None


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus) -> None:
    del exitstatus

    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    if not _quiet_progress_enabled(session.config) or session.testscollected <= 0:
        return

    terminal_reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if terminal_reporter is None:
        return

    terminal_reporter.ensure_newline()
    terminal_reporter.write("done.", flush=True)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session) -> None:
    _disable_terminal_progress(session.config)


def _compiler_flag_family(compiler: str) -> str:
    """Return the compiler family tag used for test compile helpers."""
    lower = compiler.lower()
    if lower.endswith("tcc") or lower.endswith("tcc.exe"):
        return "tcc"
    if lower.endswith(("gcc", "gcc.exe", "clang", "clang.exe", "cc", "cc.exe")):
        return "gcc"
    if lower.endswith(("cl", "cl.exe")):
        return "msvc"
    return "unknown"


def pytest_configure(config) -> None:
    """Configure pytest environment and print the detected C compiler.

    This hook is executed early in the pytest lifecycle. It finds the appropriate
    C compiler for testing and outputs its path to the terminal. It avoids
    duplicate printing when running under pytest-xdist.

    Args:
        config: The pytest configuration object.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    cc = _find_cc()
    msg = f"[L0] C compiler: {cc}\n"
    worker_count_msg = None
    if _quiet_progress_is_quiet_cli(config):
        worker_count = _resolved_xdist_worker_count(config)
        if worker_count is not None:
            worker_label = "worker" if worker_count == 1 else "workers"
            worker_count_msg = f"[L0] xdist {worker_label}: {worker_count}\n"

    tr = config.pluginmanager.getplugin("terminalreporter")
    if tr is not None:
        tr.write_line(msg.rstrip("\n"))
        if worker_count_msg is not None:
            tr.write_line(worker_count_msg.rstrip("\n"))
    else:
        sys.stderr.write(msg)
        if worker_count_msg is not None:
            sys.stderr.write(worker_count_msg)
        sys.stderr.flush()


def _find_cc() -> str:
    """Find the best available C compiler for testing.

    The search order is:
    1. L0_CC environment variable
    2. Common compiler names in PATH: tcc, gcc, clang, cc
    3. CC environment variable

    Returns:
        The command or path to the selected C compiler.

    Raises:
        RuntimeError: If no suitable C compiler is found on the system.
    """
    from_env = os.environ.get("L0_CC")
    if from_env:
        return from_env
    for candidate in ("tcc", "gcc", "clang", "cc"):
        if shutil.which(candidate):
            return candidate
    from_env = os.environ.get("CC")
    if from_env:
        return from_env
    raise RuntimeError("No C compiler found. Please set L0_CC or CC environment variable.")


@pytest.fixture
def stage1_root() -> Path:
    """Fixture providing the absolute path to the stage 1 compiler root directory.

    Returns:
        Path object pointing to compiler/stage1_py/.
    """
    return STAGE1_ROOT


@pytest.fixture
def runtime_dir(stage1_root: Path) -> Path:
    """Fixture providing the absolute path to the L0 shared C runtime directory.

    Args:
        stage1_root: The path to the stage 1 compiler root.

    Returns:
        Path object pointing to compiler/shared/runtime/.
    """
    return stage1_root.parent / "shared" / "runtime"


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory for an isolated test project.

    This is an alias for the built-in `tmp_path` fixture to provide better
    semantic meaning within the test suite context.

    Args:
        tmp_path: The pytest built-in temporary path fixture.

    Returns:
        Path object to the temporary project directory.
    """
    return tmp_path


@pytest.fixture
def write_l0_file(temp_project: Path):
    """Fixture to write an L0 source file to the temporary project directory.

    Args:
        temp_project: The temporary project directory fixture.

    Returns:
        A callable that takes a module name (e.g., 'app.main') and the source
        code content, writes the file (automatically dedenting the content),
        and returns the Path to the written file.
    """

    def _write(module_name: str, content: str) -> Path:
        parts = module_name.split(".")
        file_path = temp_project.joinpath(*parts).with_suffix(".l0")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(dedent(content), encoding="utf-8", newline="\n")
        return file_path

    return _write


@pytest.fixture
def write_l0_file_to():
    """Fixture to write an L0 source file to a specific root directory.

    Useful for tests that need to explicitly manage multiple search roots,
    such as separate system and project directories.

    Example:
        ```python
        def test_something(write_l0_file_to, tmp_path):
            sys_root = tmp_path / "sys"
            sys_root.mkdir()
            write_l0_file_to(sys_root, "std.io", '''
                module std.io;
                func print() -> void { }
            ''')
        ```

    Returns:
        A callable that takes a root Path, a module name, and source content,
        writes the file, and returns its Path.
    """

    def _write(root: Path, module_name: str, content: str) -> Path:
        parts = module_name.split(".")
        file_path = root.joinpath(*parts).with_suffix(".l0")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(dedent(content), encoding="utf-8", newline="\n")
        return file_path

    return _write


@pytest.fixture
def search_paths(temp_project: Path, stage1_root: Path) -> SourceSearchPaths:
    """Fixture providing pre-configured search paths for a typical test setup.

    Includes the temporary project directory as a project root and the
    standard library source as a system root.

    Args:
        temp_project: The temporary project directory fixture.
        stage1_root: The path to the stage 1 compiler root.

    Returns:
        A configured SourceSearchPaths instance.
    """
    paths = SourceSearchPaths()
    paths.add_project_root(temp_project)
    paths.add_system_root(stage1_root.parent / "shared" / "l0" / "stdlib")
    return paths


@pytest.fixture
def codegen_dir() -> Path:
    """Fixture providing the path to the codegen test fixtures directory.

    Returns:
        Path object pointing to compiler/stage1_py/tests/backend/codegen/.
    """
    return Path(__file__).parent / "backend" / "codegen"


@pytest.fixture
def codegen_search_paths(codegen_dir: Path, stage1_root: Path) -> SourceSearchPaths:
    """Fixture providing search paths for running the codegen test suite.

    Args:
        codegen_dir: The path to the codegen test fixtures.
        stage1_root: The path to the stage 1 compiler root.

    Returns:
        A configured SourceSearchPaths instance.
    """
    paths = SourceSearchPaths()
    paths.add_project_root(codegen_dir)
    paths.add_system_root(stage1_root.parent / "shared" / "l0" / "stdlib")
    return paths


@pytest.fixture
def compile_and_run(runtime_dir: Path):
    """Fixture to compile and execute generated C code.

    Args:
        runtime_dir: The path to the L0 C runtime headers.

    Returns:
        A callable that takes a C code string and a working directory path,
        compiles the code using the configured C compiler, executes the
        resulting binary, and returns a tuple:
        (success_boolean, standard_output_string, standard_error_string).
    """

    def _compile_and_run(c_code: str, work_dir: Path) -> tuple[bool, str, str]:
        cc = _find_cc()
        flag_family = _compiler_flag_family(cc)

        c_file = work_dir / "output.c"
        exe_name = "output.exe" if os.name == "nt" else "output"
        exe_file = work_dir / exe_name

        c_file.write_text(c_code, encoding="utf-8")

        if flag_family == "msvc":
            command = [
                cc,
                str(c_file),
                "/std:c11",
                "/Od",
                f"/I{runtime_dir}",
                f"/Fe:{exe_file}",
            ]
        else:
            command = [
                cc,
                "-std=c99",
                "-Og",
                "-pedantic",
                "-I",
                str(runtime_dir),
                str(c_file),
                "-o",
                str(exe_file),
            ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return False, "", result.stderr

        result = subprocess.run(
            [str(exe_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return result.returncode == 0, result.stdout, result.stderr

    return _compile_and_run


@pytest.fixture
def analyze_single(temp_project: Path, stage1_root: Path):
    """Fixture to analyze a single L0 module from a source string.

    Automatically handles file creation, search path setup (including the stdlib),
    and driver invocation.

    Example:
        ```python
        def test_something(analyze_single):
            result = analyze_single("main", '''
                module main;
                func f() -> int { return 42; }
            ''')
            assert not result.has_errors()
        ```

    Args:
        temp_project: The temporary project directory fixture.
        stage1_root: The path to the stage 1 compiler root.

    Returns:
        A callable that takes a module name and source code string,
        and returns an AnalysisResult.
    """

    def _analyze(module_name: str, src: str):
        parts = module_name.split(".")
        file_path = temp_project.joinpath(*parts).with_suffix(".l0")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(dedent(src), encoding="utf-8", newline="\n")

        driver = L0Driver()
        driver.search_paths.add_system_root(stage1_root.parent / "shared" / "l0" / "stdlib")
        driver.search_paths.add_project_root(temp_project)
        return driver.analyze(module_name)

    return _analyze


@pytest.fixture
def codegen_single(analyze_single):
    """Fixture to analyze and generate C code for a single L0 module.

    Example:
        ```python
        def test_something(codegen_single):
            c_code, diags = codegen_single("main", '''
                module main;
                func f() -> int { return 42; }
            ''')
            assert c_code is not None
        ```

    Args:
        analyze_single: The single-module analysis fixture.

    Returns:
        A callable that takes a module name and source code string,
        and returns a tuple `(c_code, diagnostics)`. If analysis fails,
        `c_code` is None and `diagnostics` contains the errors.
    """

    def _codegen(module_name: str, src: str):
        result = analyze_single(module_name, src)

        if result.has_errors():
            return None, result.diagnostics

        from l0_backend import Backend

        backend = Backend(result)
        c_code = backend.generate()
        return c_code, []

    return _codegen


def has_error_code(diagnostics, code: str) -> bool:
    """Check if a specific diagnostic code is present in a list of diagnostics.

    Args:
        diagnostics: A list of Diagnostic objects.
        code: The error code string to search for (e.g., "TYP-0110" or "[TYP-0110]").

    Returns:
        True if any diagnostic message contains the specified error code.
    """
    if not code.startswith("["):
        code = f"[{code}]"
    return any(code in d.message for d in diagnostics)
