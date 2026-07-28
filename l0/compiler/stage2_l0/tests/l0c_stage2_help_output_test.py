#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for Stage 2 help/version output."""

from __future__ import annotations

import shutil
from pathlib import Path

from tool_test_common import (
    REPO_ROOT,
    ToolTestFailure,
    assert_contains,
    assert_empty,
    assert_not_contains,
    build_stage2,
    clean_env,
    make_temp_dir,
    read_text,
    resolve_tool,
    run_to_files,
)


def fail(message: str) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_stage2_help_output_test: FAIL: {message}")
    return 1


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


def main() -> int:
    """Program entrypoint."""

    tmp_dir = make_temp_dir("l0c-stage2-help-test.")
    try:
        dea_build_dir = tmp_dir / "dea"
        build_stage2(dea_build_dir)
        l0c = resolve_tool(dea_build_dir / "bin", "l0c-stage2")
        native = resolve_tool(dea_build_dir / "bin", "l0c-stage2.native")

        help_stdout = tmp_dir / "help.stdout"
        help_stderr = tmp_dir / "help.stderr"
        run_to_files([l0c, "--help"], help_stdout, help_stderr, env=clean_env())
        assert_contains(help_stdout, "usage: l0c [-h]")
        assert_contains(help_stdout, "Dea language / L0 compiler")
        assert_contains(help_stdout, "  -h, --help            show this help message and exit")
        assert_contains(help_stdout, "  -V, --version         show compiler version and exit")
        assert_contains(help_stdout, "  -Vl, --log")
        assert_contains(help_stdout, "  -Rp, --project-root PROJECT_ROOT")
        assert_contains(help_stdout, "  -Rs, --sys-root SYS_ROOT")
        assert_contains(help_stdout, "  -c, --compile")
        assert_contains(help_stdout, "  -Gc, --gen, --codegen")
        assert_contains(help_stdout, "  -Gk, --keep-c")
        assert_contains(help_stdout, "  -Sb, --check-basic")
        assert_contains(help_stdout, "  -Su, --unchecked")
        assert_contains(help_stdout, "  -Va, --trace-arc")
        assert_contains(help_stdout, "  -Vm, --trace-memory")
        assert_contains(help_stdout, "  -I, --interface-path INTERFACE_PATH")
        assert_contains(help_stdout, "  --c-compiler, -Cc C_COMPILER")
        assert_contains(help_stdout, "  --c-options, -Co C_OPTIONS")
        assert_contains(help_stdout, "  --runtime-include, -Ri RUNTIME_INCLUDE")
        assert_contains(help_stdout, "  --runtime-lib, -Rl RUNTIME_LIB")
        assert_contains(help_stdout, "  -g                    Request debug information")
        assert_contains(help_stdout, "  -S                    Request assembly output")
        assert_contains(help_stdout, "  -L LIBRARY_PATH       Add an external-library search path")
        assert_contains(help_stdout, "  -l LIBRARY            Link an external library")
        assert_contains(help_stdout, "Namespaced value options accept a separate value or '=VALUE'; only -v may be")
        assert_not_contains(help_stdout, "  -l, --log")
        assert_not_contains(help_stdout, "  -P, --project-root")
        assert_not_contains(help_stdout, "  -S, --sys-root")
        assert_not_contains(help_stdout, "  --gen, -g, --codegen")
        assert_not_contains(help_stdout, "  --c-compiler, -c C_COMPILER")
        assert_not_contains(help_stdout, "  --c-options, -C C_OPTIONS")
        assert_not_contains(help_stdout, "  --runtime-include, -I RUNTIME_INCLUDE")
        assert_not_contains(help_stdout, "  --runtime-lib, -L RUNTIME_LIB")
        assert_not_contains(help_stdout, "commit: ")
        assert_empty(help_stderr)

        version_stdout = tmp_dir / "version.stdout"
        version_stderr = tmp_dir / "version.stderr"
        run_to_files([l0c, "--version"], version_stdout, version_stderr, env=clean_env())
        assert_version_report(version_stdout)
        assert_empty(version_stderr)

        short_version_stdout = tmp_dir / "short-version.stdout"
        short_version_stderr = tmp_dir / "short-version.stderr"
        run_to_files([l0c, "-V"], short_version_stdout, short_version_stderr, env=clean_env())
        assert_version_report(short_version_stdout)
        assert_empty(short_version_stderr)
        if read_text(version_stdout) != read_text(short_version_stdout):
            raise ToolTestFailure("-V and --version output must match")

        native_version_stdout = tmp_dir / "native-version.stdout"
        native_version_stderr = tmp_dir / "native-version.stderr"
        run_to_files([native, "--version"], native_version_stdout, native_version_stderr, env=clean_env())
        assert_version_report(native_version_stdout)
        assert_empty(native_version_stderr)
        if read_text(version_stdout) != read_text(native_version_stdout):
            raise ToolTestFailure("wrapper and native --version output must match")

        verbose_stdout = tmp_dir / "verbose.stdout"
        verbose_stderr = tmp_dir / "verbose.stderr"
        run_to_files(
            [l0c, "-v", "--check", "--project-root", "examples", "hello"],
            verbose_stdout,
            verbose_stderr,
            env=clean_env(),
        )
        assert_contains(verbose_stderr, "Dea language / L0 compiler")

        verbose_fail_stdout = tmp_dir / "verbose-fail.stdout"
        verbose_fail_stderr = tmp_dir / "verbose-fail.stderr"
        completed = run_to_files(
            [l0c, "-v"],
            verbose_fail_stdout,
            verbose_fail_stderr,
            env=clean_env(),
            expected_returncode=None,
        )
        if completed.returncode != 2:
            raise ToolTestFailure(f"expected -v without target exit code 2, got {completed.returncode}")
        assert_empty(verbose_fail_stdout)
        assert_contains(verbose_fail_stderr, "Dea language / L0 compiler")
        assert_contains(verbose_fail_stderr, "usage: l0c [-h] [-V]")
        assert_contains(verbose_fail_stderr, "error: [L0C-2021] missing required target module/file name")

        noargs_stdout = tmp_dir / "noargs.stdout"
        noargs_stderr = tmp_dir / "noargs.stderr"
        completed = run_to_files(
            [l0c],
            noargs_stdout,
            noargs_stderr,
            env=clean_env(),
            expected_returncode=None,
        )
        if completed.returncode != 2:
            raise ToolTestFailure(f"expected no-args exit code 2, got {completed.returncode}")
        assert_empty(noargs_stdout)
        assert_contains(noargs_stderr, "usage: l0c [-h] [-V]")
        assert_contains(noargs_stderr, "error: [L0C-2021] missing required target module/file name")
    except ToolTestFailure as exc:
        return fail(str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("l0c_stage2_help_output_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
