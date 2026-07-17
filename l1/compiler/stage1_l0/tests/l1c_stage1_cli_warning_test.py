#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage: warnings must surface in --gen, --sym, and --type modes."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
DRIVER_FIXTURES = L1_ROOT / "compiler" / "stage1_l0" / "tests" / "fixtures" / "driver"


class CliWarningFailure(RuntimeError):
    """Raised when one CLI-warning regression fails."""


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def read_text(path: Path) -> str:
    """Read one text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def stage1_compiler() -> Path:
    """Return the repo-local Stage 1 compiler path."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise CliWarningFailure(f"{message}\nartifacts={artifact_dir}")


def run_mode(mode: str, artifact_dir: Path) -> tuple[int, str, str]:
    """Run l1c-stage1 in one mode against the dup_import_main fixture."""

    compiler = stage1_compiler()
    if not compiler.is_file():
        fail(f"missing repo-local Stage 1 compiler: {compiler}", artifact_dir)

    stdout_path = artifact_dir / f"{mode.lstrip('-')}.stdout.log"
    stderr_path = artifact_dir / f"{mode.lstrip('-')}.stderr.log"

    result = subprocess.run(
        [str(compiler), mode, "--project-root", str(DRIVER_FIXTURES), "dup_import_main"],
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(result.stdout if result.stdout is not None else b"")
    stderr_path.write_bytes(result.stderr if result.stderr is not None else b"")
    return result.returncode, read_text(stdout_path), read_text(stderr_path)


def assert_warning_surfaced(mode: str, artifact_dir: Path) -> None:
    """Assert that RES-0036 appears in stderr and the mode exits cleanly."""

    rc, _stdout, stderr = run_mode(mode, artifact_dir)
    if rc != 0:
        fail(f"{mode} exited with code {rc}; expected success despite warning\nstderr={stderr}", artifact_dir)
    if "[RES-0036]" not in stderr:
        fail(f"{mode} did not surface [RES-0036] warning in stderr\nstderr={stderr}", artifact_dir)


def main() -> int:
    """Program entrypoint."""

    artifact_dir = Path(tempfile.mkdtemp(prefix="l1c_stage1_cli_warning_"))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    try:
        assert_warning_surfaced("--gen", artifact_dir)
        assert_warning_surfaced("--sym", artifact_dir)
        assert_warning_surfaced("--type", artifact_dir)
    except CliWarningFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        print(f"l1c_stage1_cli_warning_test: FAIL: {lines[0]}", file=sys.stderr, flush=True)
        for line in lines[1:]:
            print(f"l1c_stage1_cli_warning_test: {line}", file=sys.stderr, flush=True)
        return 1
    finally:
        if not keep_artifacts:
            import shutil

            shutil.rmtree(artifact_dir, ignore_errors=True)

    print("l1c_stage1_cli_warning_test: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
