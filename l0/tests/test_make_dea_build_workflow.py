#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for the Make Dea build and install-prefix workflows."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_TESTS_ROOT = REPO_ROOT / "build" / "tests"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dist_tools_lib import Stage2BuildProvenance, format_build_time_utc, format_commit_for_version, render_stage2_build_info_module


def fail(message: str) -> None:
    raise SystemExit(f"test_make_dea_build_workflow: FAIL: {message}")


def is_windows_host() -> bool:
    return os.name == "nt"


def run_checked(command: list[str], *, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        fail(
            f"command failed ({proc.returncode}): {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.stdout + proc.stderr


def run_expected_fail(command: list[str], expected: str, *, extra_env: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode == 0:
        fail(f"expected command to fail: {' '.join(command)}")
    combined = proc.stdout + proc.stderr
    if expected not in combined:
        fail(
            f"expected {expected!r} in failing output for {' '.join(command)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def assert_exists(path: Path) -> None:
    if not path.exists():
        fail(f"expected path: {path}")


def assert_missing(path: Path) -> None:
    if path.exists() or path.is_symlink():
        fail(f"did not expect path: {path}")


def assert_symlink_target(path: Path, expected: str) -> None:
    if not path.is_symlink():
        fail(f"expected symlink: {path}")
    target = os.readlink(path)
    if target != expected:
        fail(f"expected {path} -> {expected}, got {target}")


def assert_same_text(path: Path, expected_path: Path) -> None:
    if path.read_text(encoding="utf-8") != expected_path.read_text(encoding="utf-8"):
        fail(f"expected {path} to match {expected_path}")


def launcher_path(base: Path) -> str:
    if is_windows_host():
        cmd_path = base.with_suffix(".cmd")
        if cmd_path.is_file():
            return str(cmd_path)
    return str(base)


def stage2_bootstrap_build_command() -> list[str]:
    return [sys.executable, "./scripts/build_stage2_l0c.py"]


def make_command(dea_build_rel: str, *targets: str, dry_run: bool = False) -> list[str]:
    command = ["make", "--no-print-directory"]
    if dry_run:
        command.append("-n")
    command.append(f"DEA_BUILD_DIR={dea_build_rel}")
    command.extend(targets)
    return command


def prefix_command(prefix: Path, *targets: str, dry_run: bool = False) -> list[str]:
    command = ["make", "--no-print-directory"]
    if dry_run:
        command.append("-n")
    command.append(f"PREFIX={prefix}")
    command.extend(targets)
    return command


def assert_output_contains(text: str, expected: str) -> None:
    if expected not in text:
        fail(f"expected {expected!r} in output:\n{text}")


def assert_output_not_contains(text: str, unexpected: str) -> None:
    if unexpected in text:
        fail(f"did not expect {unexpected!r} in output:\n{text}")


def normalize_path_text(value: str | Path) -> str:
    """Return one path-like value with forward slashes for stable comparisons."""

    if isinstance(value, Path):
        return value.as_posix()
    return value.replace("\\", "/")


def msys_source_path(path: Path) -> str:
    """Return the path text expected in MSYS2 bash `source` hints."""

    if not is_windows_host():
        return normalize_path_text(path)

    proc = subprocess.run(
        ["cygpath", "-u", str(path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(
            f"failed to convert Windows path with cygpath: {path}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc.stdout.strip()


def assert_version_report(text: str) -> None:
    for expected in (
        "Dea language / L0 compiler",
        "build: ",
        "build time: ",
        "commit: ",
        "host: ",
        "compiler: ",
    ):
        assert_output_contains(text, expected)
    for unexpected in ("tree: ", "build id: ", "built at: ", "compiler version: "):
        assert_output_not_contains(text, unexpected)


def assert_provenance_helper_contract() -> None:
    timestamp = datetime(2026, 3, 12, 23, 55, 56, tzinfo=timezone.utc)
    if format_build_time_utc(timestamp) != "2026-03-12 23:55:56+00:00":
        fail("format_build_time_utc must use the fixed `+00:00` rendering")
    if format_commit_for_version("abc123", "clean") != "abc123":
        fail("clean commit formatting must not add a suffix")
    if format_commit_for_version("abc123", "dirty") != "abc123+dirty":
        fail("dirty commit formatting must append +dirty")

    rendered = render_stage2_build_info_module(
        Stage2BuildProvenance(
            commit_full="f8174b779f339af1f159765880b92f3b5c40490b",
            commit_short="f8174b7",
            tree_state="dirty",
            build_id="f8174b7-20260312T235556Z",
            build_time="2026-03-12 23:55:56+00:00",
            host="Darwin 24.6.0 x86_64",
            compiler_banner="gcc-15 (Homebrew GCC 15.2.0_1) 15.2.0",
            release_version="1.1.0.dev0",
            source_url="https://github.com/googlielmo/dea-lang",
            has_embedded_version=True,
        )
    )
    for expected in (
        "build: ",
        "build time: ",
        "commit: ",
        "host: ",
        "compiler: ",
        "+dirty",
        "Darwin 24.6.0 x86_64",
        "1.1.0.dev0",
    ):
        assert_output_contains(rendered, expected)
    for unexpected in ("tree: ", "build id: ", "built at: ", "compiler version: "):
        assert_output_not_contains(rendered, unexpected)


def clean_runtime_env(*, extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for name in ("L0_HOME", "L0_SYSTEM", "L0_RUNTIME_INCLUDE", "L0_RUNTIME_LIB"):
        env.pop(name, None)
    if extra_env:
        env.update(extra_env)
    return env


def cmd_quote(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


def run_cmd_activated(env_script: Path, command: str, *, extra_env: dict[str, str] | None = None) -> str:
    driver_fd, driver_text = tempfile.mkstemp(
        prefix="make_dea_build_cmd.",
        suffix=".cmd",
        dir=BUILD_TESTS_ROOT,
        text=True,
    )
    driver_path = Path(driver_text)
    try:
        with os.fdopen(driver_fd, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("@echo off\n")
            handle.write(f"call {cmd_quote(str(env_script))}\n")
            handle.write("if errorlevel 1 exit /b %ERRORLEVEL%\n")
            handle.write(f"{command}\n")
        return run_checked(
            ["cmd.exe", "/d", "/c", str(driver_path)],
            extra_env=clean_runtime_env(extra_env=extra_env),
        )
    finally:
        driver_path.unlink(missing_ok=True)


def source_env_and_check(dea_build_dir: Path) -> None:
    env_script = dea_build_dir / "bin" / "l0-env.sh"
    command = [
        "bash",
        "-lc",
        f"source {shlex.quote(str(env_script))} && l0c --check -P examples hello",
    ]
    run_checked(command)


def tempdir_prefix(base: str) -> str:
    return f"{base} " if is_windows_host() else f"{base}_"


def make_hello_project(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "hello.l0").write_text(
        """module hello;

import std.io;

func main() -> int {
    printl_s("Hello, World!");
    return 0;
}
""",
        encoding="utf-8",
    )


def main() -> int:
    BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    assert_provenance_helper_contract()
    dea_build_dir = Path(tempfile.mkdtemp(prefix=tempdir_prefix("make_dea_build"), dir=BUILD_TESTS_ROOT))
    prefix_dir = Path(tempfile.mkdtemp(prefix=tempdir_prefix("make_prefix"))).resolve(strict=False)
    project_dir = Path(tempfile.mkdtemp(prefix=tempdir_prefix("make_project"), dir=BUILD_TESTS_ROOT))
    dea_build_rel = os.path.relpath(dea_build_dir, REPO_ROOT)
    alias_path = dea_build_dir / "bin" / "l0c"
    alias_cmd_path = dea_build_dir / "bin" / "l0c.cmd"
    stage1_path = dea_build_dir / "bin" / "l0c-stage1"
    stage1_cmd_path = dea_build_dir / "bin" / "l0c-stage1.cmd"
    stage2_path = dea_build_dir / "bin" / "l0c-stage2"
    stage2_cmd_path = dea_build_dir / "bin" / "l0c-stage2.cmd"
    native_path = dea_build_dir / "bin" / "l0c-stage2.native"
    env_path = dea_build_dir / "bin" / "l0-env.sh"
    env_cmd_path = dea_build_dir / "bin" / "l0-env.cmd"
    prefix_alias_path = prefix_dir / "bin" / "l0c"
    prefix_alias_cmd_path = prefix_dir / "bin" / "l0c.cmd"
    prefix_stage2_path = prefix_dir / "bin" / "l0c-stage2"
    prefix_stage2_cmd_path = prefix_dir / "bin" / "l0c-stage2.cmd"
    prefix_native_path = prefix_dir / "bin" / "l0c-stage2.native"
    prefix_env_path = prefix_dir / "bin" / "l0-env.sh"
    prefix_env_cmd_path = prefix_dir / "bin" / "l0-env.cmd"
    expected_source_hint = f"source {dea_build_dir}/bin/l0-env.sh"
    expected_windows_source_hint = f"source {msys_source_path(env_path)}"
    expected_prefix_windows_source_hint = f"source {msys_source_path(prefix_env_path)}"
    expected_windows_hint = "l0-env.cmd"

    try:
        make_hello_project(project_dir)
        help_output = run_checked(["make", "help"])
        for target in (
            "install-dev-stages",
            "install",
            "dist",
            "use-dev-stage1",
            "use-dev-stage2",
            "test-stage1",
            "test-stage2",
            "test-stage2-trace",
            "check-examples",
            "test-dist",
            "triple-test",
            "test-all",
            "docs",
            "docs-pdf",
            "clean-dea-build",
        ):
            assert_output_contains(help_output, target)
        assert_output_contains(help_output, "PREFIX=<required>")

        print_dea_build_output = run_checked(make_command(dea_build_rel, "print-dea-build-dir"))
        if print_dea_build_output.strip() != dea_build_rel:
            fail(f"expected print-dea-build-dir to return {dea_build_rel!r}, got {print_dea_build_output!r}")

        run_checked(make_command(dea_build_rel, "install-dev-stage1"))
        assert_exists(stage1_path)
        assert_exists(env_path)
        if is_windows_host():
            assert_exists(stage1_cmd_path)
            assert_exists(env_cmd_path)
        assert_missing(alias_path)
        stable_env_text = env_path.read_text(encoding="utf-8")
        stable_env_cmd_text = env_cmd_path.read_text(encoding="utf-8") if is_windows_host() else None

        if not is_windows_host():
            run_expected_fail(
                ["bash", str(env_path)],
                expected_source_hint,
            )

        run_checked(make_command(dea_build_rel, "install-dev-stage2"))
        assert_exists(stage2_path)
        assert_exists(native_path)
        assert_exists(env_path)
        if is_windows_host():
            assert_exists(stage2_cmd_path)
            assert_exists(env_cmd_path)
        assert_missing(alias_path)
        repo_wrapper_version = run_checked([launcher_path(stage2_path), "--version"])
        repo_native_version = run_checked([str(native_path), "--version"])
        assert_version_report(repo_wrapper_version)
        if repo_native_version != repo_wrapper_version:
            fail("expected repo-local wrapper/native --version output to match")
        if env_path.read_text(encoding="utf-8") != stable_env_text:
            fail("expected l0-env.sh to remain stable after install-dev-stage2")
        if is_windows_host() and env_cmd_path.read_text(encoding="utf-8") != stable_env_cmd_text:
            fail("expected l0-env.cmd to remain stable after install-dev-stage2")

        run_checked(make_command(dea_build_rel, "install-dev-stages"))
        assert_exists(stage1_path)
        assert_exists(stage2_path)
        assert_exists(native_path)
        assert_exists(env_path)
        if is_windows_host():
            assert_exists(stage1_cmd_path)
            assert_exists(stage2_cmd_path)
            assert_exists(env_cmd_path)
        assert_missing(alias_path)
        if env_path.read_text(encoding="utf-8") != stable_env_text:
            fail("expected l0-env.sh to remain stable after install-dev-stages")
        if is_windows_host() and env_cmd_path.read_text(encoding="utf-8") != stable_env_cmd_text:
            fail("expected l0-env.cmd to remain stable after install-dev-stages")

        use_stage1_output = run_checked(make_command(dea_build_rel, "use-dev-stage1"))
        if is_windows_host():
            assert_exists(alias_path)
            assert_exists(alias_cmd_path)
            assert_same_text(alias_path, stage1_path)
            assert_same_text(alias_cmd_path, stage1_cmd_path)
            assert_output_contains(use_stage1_output, expected_windows_source_hint)
            assert_output_contains(use_stage1_output, expected_windows_hint)
        else:
            assert_symlink_target(alias_path, "l0c-stage1")
            assert_output_contains(use_stage1_output, expected_source_hint)

        run_checked(make_command(dea_build_rel, "install-dev-stages"))
        if is_windows_host():
            assert_same_text(alias_path, stage1_path)
            assert_same_text(alias_cmd_path, stage1_cmd_path)
            stage1_env_output = run_cmd_activated(
                env_cmd_path,
                "echo L0_HOME=%L0_HOME% && l0c --check -P examples hello",
            )
            assert_output_contains(
                normalize_path_text(stage1_env_output),
                f"L0_HOME={normalize_path_text(REPO_ROOT / 'compiler')}",
            )
        else:
            assert_symlink_target(alias_path, "l0c-stage1")
            source_env_and_check(dea_build_dir)

        use_stage2_output = run_checked(make_command(dea_build_rel, "use-dev-stage2"))
        if is_windows_host():
            assert_exists(alias_path)
            assert_exists(alias_cmd_path)
            assert_same_text(alias_path, stage2_path)
            assert_same_text(alias_cmd_path, stage2_cmd_path)
            assert_output_contains(use_stage2_output, expected_windows_source_hint)
            assert_output_contains(use_stage2_output, expected_windows_hint)
        else:
            assert_symlink_target(alias_path, "l0c-stage2")
            assert_output_contains(use_stage2_output, expected_source_hint)
        run_checked(make_command(dea_build_rel, "use-dev-stage2"))
        if is_windows_host():
            assert_same_text(alias_path, stage2_path)
            assert_same_text(alias_cmd_path, stage2_cmd_path)
            stage2_env_output = run_cmd_activated(
                env_cmd_path,
                "call "
                + cmd_quote(str(env_cmd_path))
                + " && echo PATH=%PATH% && echo L0_HOME=%L0_HOME% && l0c --check -P examples hello",
            )
            normalized_stage2_env_output = normalize_path_text(stage2_env_output)
            assert_output_contains(
                normalized_stage2_env_output,
                f"L0_HOME={normalize_path_text(REPO_ROOT / 'compiler')}",
            )
            if normalized_stage2_env_output.lower().count(normalize_path_text(env_cmd_path.parent).lower()) != 1:
                fail("expected l0-env.cmd to prepend the repo-local bin directory to PATH only once")
        else:
            assert_symlink_target(alias_path, "l0c-stage2")
            source_env_and_check(dea_build_dir)

        install_prefix_output = run_checked(prefix_command(prefix_dir, "install"))
        assert_exists(prefix_stage2_path)
        assert_exists(prefix_native_path)
        assert_exists(prefix_env_path)
        if is_windows_host():
            assert_exists(prefix_stage2_cmd_path)
            assert_exists(prefix_env_cmd_path)
        assert_exists(prefix_dir / "shared" / "l0" / "stdlib" / "std" / "io.l0")
        assert_exists(prefix_dir / "shared" / "runtime" / "l0_runtime.h")
        if is_windows_host():
            assert_exists(prefix_alias_path)
            assert_exists(prefix_alias_cmd_path)
            assert_same_text(prefix_alias_path, prefix_stage2_path)
            assert_same_text(prefix_alias_cmd_path, prefix_stage2_cmd_path)
            assert_output_contains(install_prefix_output, expected_prefix_windows_source_hint)
            assert_output_contains(install_prefix_output, expected_windows_hint)
        else:
            assert_symlink_target(prefix_alias_path, "l0c-stage2")
        assert_output_contains(install_prefix_output, "installed self-hosted Stage 2 compiler")
        prefix_wrapper_version = run_checked([launcher_path(prefix_stage2_path), "--version"])
        prefix_native_version = run_checked([str(prefix_native_path), "--version"])
        assert_version_report(prefix_wrapper_version)
        if prefix_native_version != prefix_wrapper_version:
            fail("expected installed wrapper/native --version output to match")
        if is_windows_host():
            prefix_env_output = run_cmd_activated(
                prefix_env_cmd_path,
                f"echo L0_HOME=%L0_HOME% && l0c --run -P {cmd_quote(str(project_dir))} hello",
            )
            assert_output_contains(
                normalize_path_text(prefix_env_output),
                f"L0_HOME={normalize_path_text(prefix_dir)}",
            )
            assert_output_contains(prefix_env_output, "Hello, World!")

        run_expected_fail(
            ["make", "DEA_BUILD_DIR=/tmp/l0-dev", "install-dev-stage1"],
            "DEA_BUILD_DIR must resolve to a subdirectory inside the repository",
        )
        run_expected_fail(
            ["make", "DEA_BUILD_DIR=.", "install-dev-stage1"],
            "DEA_BUILD_DIR must resolve to a subdirectory inside the repository",
        )
        run_expected_fail(
            ["make", "install"],
            "make install: PREFIX is required; example: make PREFIX=/tmp/l0-install L0_CC=gcc install",
        )
        run_expected_fail(
            ["make", "PREFIX=.", "install"],
            "PREFIX must not resolve to the repository root",
        )
        run_expected_fail(
            ["python3", "./scripts/gen_dist_tools.py", "write-env-script", "--dea-build-dir", "/tmp/l0-dev"],
            "DEA_BUILD_DIR must resolve to a subdirectory inside the repository",
        )
        run_expected_fail(
            stage2_bootstrap_build_command(),
            "DEA_BUILD_DIR must resolve to a subdirectory inside the repository",
            extra_env={"DEA_BUILD_DIR": "."},
        )

        dry_run_expectations = {
            "install": "gen_dist_tools.py install-prefix --prefix",
            "dist": "gen_dist_tools.py make-dist",
            "test-stage1": "pytest -n auto",
            "test-stage2": "./compiler/stage2_l0/scripts/run_tests.py",
            "test-stage2-trace": "./compiler/stage2_l0/scripts/run_trace_tests.py",
            "check-examples": "../scripts/check_examples.py",
            "test-dist": "./tests/test_make_dist_workflow.py",
            "triple-test": "./compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py",
            "test-all": "./compiler/stage2_l0/scripts/run_trace_tests.py",
            "docs": "./scripts/gen_docs.py",
            "docs-pdf": "./scripts/gen_docs.py --strict --pdf",
        }
        for target, expected in dry_run_expectations.items():
            output = run_checked(make_command(dea_build_rel, target, dry_run=True))
            assert_output_contains(output, expected)
            if target in {"test-stage2", "test-stage2-trace", "triple-test", "check-examples"}:
                assert_output_contains(output, "./scripts/build_stage2_l0c.py")
            if target == "test-all":
                assert_output_contains(output, "../scripts/check_examples.py")
                assert_output_contains(output, "./tests/test_make_dea_build_workflow.py")

        run_checked(make_command(dea_build_rel, "clean-dea-build"))
        if dea_build_dir.exists():
            fail(f"expected clean-dea-build to remove {dea_build_dir}")
    finally:
        shutil.rmtree(dea_build_dir, ignore_errors=True)
        shutil.rmtree(prefix_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)

    print("test_make_dea_build_workflow: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
