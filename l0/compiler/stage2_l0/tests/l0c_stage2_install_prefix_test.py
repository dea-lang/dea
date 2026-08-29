#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for installed Stage 2 prefixes."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from tool_test_common import (
    BUILD_TESTS_ROOT,
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_file,
    assert_not_contains,
    clean_env,
    is_windows_host,
    native_path,
    normalize_text_file,
    read_text,
    run,
    stage2_launcher_path,
    write_text,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_install_prefix_test: FAIL: {message}")
    return 1


def assert_symlink_target(path: Path, expected: str) -> None:
    """Assert that one symlink points to the expected relative target."""

    if not path.is_symlink():
        raise ToolTestFailure(f"expected symlink: {path}")
    target = os.readlink(path)
    if target != expected:
        raise ToolTestFailure(f"expected {path} -> {expected}, got {target}")


def assert_version_report(path: Path) -> None:
    """Assert that one version report has the stable public fields."""

    assert_contains(path, "Dea language / L0 compiler")
    assert_contains(path, "build: ")
    assert_contains(path, "build time: ")
    assert_contains(path, "commit: ")
    assert_contains(path, "host: ")
    assert_contains(path, "compiler: ")
    assert_not_contains(path, "tree: ")
    assert_not_contains(path, "build id: ")
    assert_not_contains(path, "built at: ")
    assert_not_contains(path, "compiler version: ")


def run_prefix_env_probe(prefix_dir: Path, project_dir: Path, env_run_output: Path) -> None:
    """Validate that the installed env activation can run `l0c`."""

    if os.name == "nt":
        cmd_script = prefix_dir / "env-run-probe.cmd"
        cmd_script.write_text(
            "@echo off\r\n"
            f"call \"{prefix_dir / 'bin' / 'l0-env.cmd'}\"\r\n"
            f"if not \"%L0_HOME%\"==\"{prefix_dir}\" exit /b 3\r\n"
            "if defined L0_SYSTEM exit /b 4\r\n"
            "if defined L0_RUNTIME_INCLUDE exit /b 5\r\n"
            f"l0c --run --project-root \"{native_path(project_dir)}\" hello\r\n",
            encoding="utf-8",
        )
        command = ["cmd.exe", "/d", "/s", "/c", str(cmd_script)]
    else:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell is None:
            raise ToolTestFailure("bash or sh is required to validate l0-env.sh activation")
        command = [
            shell,
            "-lc",
            (
                f'. "{prefix_dir / "bin" / "l0-env.sh"}" && '
                f'[ "$L0_HOME" = "{prefix_dir}" ] && '
                '[ -z "${L0_SYSTEM-}" ] && '
                '[ -z "${L0_RUNTIME_INCLUDE-}" ] && '
                f'l0c --run --project-root "{native_path(project_dir)}" hello'
            ),
        ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    env_run_output.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise ToolTestFailure(f"installed env activation probe failed\n{completed.stdout}")


def main() -> int:
    """Program entrypoint."""

    BUILD_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    prefix_dir = Path(tempfile.mkdtemp(prefix="l0_stage2_prefix.", dir=BUILD_TESTS_ROOT)).resolve()
    project_dir = Path(tempfile.mkdtemp(prefix="l0_stage2_project.", dir=BUILD_TESTS_ROOT)).resolve()
    install_log = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_{os.getpid()}.log"
    reinstall_log = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_reinstall_{os.getpid()}.log"
    run_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_run_{os.getpid()}.out"
    ffi_run_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_ffi_run_{os.getpid()}.out"
    env_run_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_env_run_{os.getpid()}.out"
    version_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_version_{os.getpid()}.out"
    native_version_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_native_version_{os.getpid()}.out"
    normalized_version_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_version_normalized_{os.getpid()}.out"
    normalized_native_version_output = BUILD_TESTS_ROOT / f"l0_stage2_install_prefix_native_version_normalized_{os.getpid()}.out"

    try:
        write_text(
            project_dir / "hello.l0",
            """module hello;

import std.io;

func main() -> int {
    printl_s("Hello, World!");
    return 0;
}
""",
        )
        write_text(
            project_dir / "ffi.l0",
            """module ffi;

import std.io;

extern func add_in_c(left: int, right: int) -> int;

func main() -> int {
    printl_i(add_in_c(19, 23));
    return 0;
}
""",
        )
        write_text(
            project_dir / "add.c",
            """#include "dea_rt.h"

dea_int add_in_c(dea_int left, dea_int right)
{
    return left + right;
}
""",
        )

        install = run(["make", f"PREFIX={native_path(prefix_dir)}", "install"], expected_returncode=None)
        install_log.write_text(install.stdout + install.stderr, encoding="utf-8")
        if install.returncode != 0:
            raise ToolTestFailure(f"make PREFIX={prefix_dir} install failed\n{read_text(install_log)}")
        for needle in (
                "installed self-hosted Stage 2 compiler",
                "gen-dea-build-tools: L0_CC=",
                "gen-dea-build-tools: L0_CFLAGS=",
                "stage 1/3: building bootstrap Stage 2 compiler",
                "stage 2/3: self-hosting Stage 2 compiler",
                "stage 3/3: installing self-hosted Stage 2 compiler",
        ):
            assert_contains(install_log, needle)
        assert_file(prefix_dir / "bin" / "l0c-stage2")
        assert_file(prefix_dir / "bin" / "l0c-stage2.native")
        assert_file(prefix_dir / "bin" / "l0-env.sh")
        if is_windows_host():
            assert_file(prefix_dir / "bin" / "l0-env.cmd")
        assert_file(prefix_dir / "shared" / "l0" / "stdlib" / "std" / "fs.l0")
        assert_file(prefix_dir / "shared" / "l0" / "stdlib" / "std" / "io.l0")
        assert_file(prefix_dir / "shared" / "l0" / "stdlib" / "std" / "path.l0")
        assert_file(prefix_dir / "shared" / "runtime" / "dea_rt.h")
        assert_file(prefix_dir / "shared" / "runtime" / "l0_runtime.h")
        if is_windows_host():
            assert_file(prefix_dir / "bin" / "l0c")
        else:
            assert_symlink_target(prefix_dir / "bin" / "l0c", "l0c-stage2")

        leaked_env = os.environ.copy()
        leaked_env["L0_SYSTEM"] = native_path(Path(tempfile.gettempdir()) / f"l0_stage2_missing_stdlib_{os.getpid()}")
        leaked_env["L0_RUNTIME_INCLUDE"] = native_path(
            Path(tempfile.gettempdir()) / f"l0_stage2_missing_runtime_{os.getpid()}"
        )
        reinstall = run(
            ["make", f"PREFIX={native_path(prefix_dir)}", "install"],
            env=leaked_env,
            expected_returncode=None,
        )
        reinstall_log.write_text(reinstall.stdout + reinstall.stderr, encoding="utf-8")
        if reinstall.returncode != 0:
            raise ToolTestFailure(f"make PREFIX={prefix_dir} install failed with leaked L0_* env\n{read_text(reinstall_log)}")
        assert_contains(reinstall_log, "gen-dea-build-tools: L0_CC=")
        assert_contains(reinstall_log, "gen-dea-build-tools: L0_CFLAGS=")

        assert_not_contains(prefix_dir / "bin" / "l0c-stage2", str(REPO_ROOT))
        assert_not_contains(prefix_dir / "bin" / "l0-env.sh", str(REPO_ROOT))

        version = run([stage2_launcher_path(prefix_dir / "bin" / "l0c-stage2"), "--version"], env=clean_env())
        version_output.write_text(version.stdout, encoding="utf-8")
        native_version = run([native_path(prefix_dir / "bin" / "l0c-stage2.native"), "--version"], env=clean_env())
        native_version_output.write_text(native_version.stdout, encoding="utf-8")
        assert_version_report(version_output)
        assert_version_report(native_version_output)
        normalize_text_file(version_output, normalized_version_output)
        normalize_text_file(native_version_output, normalized_native_version_output)
        if read_text(normalized_version_output) != read_text(normalized_native_version_output):
            raise ToolTestFailure("wrapper and native --version output must match")

        run(
            [
                stage2_launcher_path(prefix_dir / "bin" / "l0c-stage2"),
                "--check",
                "--project-root",
                native_path(project_dir),
                "hello",
            ],
            env=clean_env(),
        )
        hello_bin = project_dir / ("hello.exe" if is_windows_host() else "hello")
        run(
            [
                stage2_launcher_path(prefix_dir / "bin" / "l0c-stage2"),
                "--build",
                "--project-root",
                native_path(project_dir),
                "-o",
                native_path(hello_bin),
                "hello",
            ],
            env=clean_env(),
        )
        hello_run = run([hello_bin])
        run_output.write_text(hello_run.stdout, encoding="utf-8")
        assert_contains(run_output, "Hello, World!")

        ffi_run = run(
            [
                stage2_launcher_path(prefix_dir / "bin" / "l0c-stage2"),
                "--run",
                "--project-root",
                native_path(project_dir),
                "--c-source",
                native_path(project_dir / "add.c"),
                "ffi",
            ],
            env=clean_env(),
        )
        ffi_run_output.write_text(ffi_run.stdout, encoding="utf-8")
        assert_contains(ffi_run_output, "42")

        run_prefix_env_probe(prefix_dir, project_dir, env_run_output)
        assert_contains(env_run_output, "Hello, World!")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        shutil.rmtree(prefix_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)
        for path in (
                install_log,
                reinstall_log,
                run_output,
                ffi_run_output,
                env_run_output,
                version_output,
                native_version_output,
                normalized_version_output,
                normalized_native_version_output,
        ):
            path.unlink(missing_ok=True)

    print("l0c_stage2_install_prefix_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
