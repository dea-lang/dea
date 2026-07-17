#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""On-demand whole-compiler `--gen` comparison for Stage 1 vs Stage 2."""

from __future__ import annotations

import difflib
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from test_runner_common import require_repo_stage2_test_env, source_tree_l0c_command

REPO_ROOT = SCRIPT_DIR.parent.parent.parent
BUILD_TESTS_DIR = REPO_ROOT / "build" / "tests"


class CodegenCompareFailure(RuntimeError):
    """Raised when the Stage 1 vs Stage 2 whole-compiler comparison fails."""


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise CodegenCompareFailure(f"{message}\nartifacts={artifact_dir}")


def read_text(path: Path) -> str:
    """Read one UTF-8 text file with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def read_bytes(path: Path) -> bytes:
    """Read one binary file."""

    return path.read_bytes()


def shell_join(command: list[str]) -> str:
    """Render one command for failure messages."""

    return " ".join(shlex.quote(part) for part in command)


def stage2_wrapper_command(wrapper_path: Path) -> list[str]:
    """Return the command used to invoke one generated Stage 2 wrapper."""

    if os.name == "nt":
        cmd_path = wrapper_path.with_suffix(".cmd")
        if cmd_path.is_file():
            return [str(cmd_path)]
    return [str(wrapper_path)]


def stage2_bootstrap_build_command() -> list[str]:
    """Return the command used to build one repo-local Stage 2 bootstrap artifact."""

    return [sys.executable, str(REPO_ROOT / "scripts" / "build_stage2_l0c.py")]


def first_lines(text: str, limit: int) -> str:
    """Return at most `limit` lines from `text`."""

    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit]) + "\n..."


def format_duration(seconds: float) -> str:
    """Render one wall-clock duration for human-readable progress output."""

    return f"{seconds:.2f}s"


def notice(message: str) -> None:
    """Print one progress line with the test prefix."""

    print(f"l0c_stage1_stage2_codegen_compare: {message}", flush=True)


def run_logged(
        name: str,
        command: list[str],
        *,
        env: dict[str, str],
        artifact_dir: Path,
        cwd: Path = REPO_ROOT,
        expected_returncode: int = 0,
) -> tuple[Path, float]:
    """Run one subprocess, capture combined output, and return wall time."""

    log_path = artifact_dir / f"{name}.log"
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.monotonic() - start
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != expected_returncode:
        fail(
            "\n".join(
                [
                    f"{name} failed (rc={completed.returncode})",
                    f"command={shell_join(command)}",
                    f"log={log_path}",
                    first_lines(completed.stdout, 80),
                ]
            ).rstrip(),
            artifact_dir,
        )
    return log_path, elapsed


def run_codegen(
        name: str,
        command: list[str],
        *,
        env: dict[str, str],
        artifact_dir: Path,
        output_path: Path,
) -> tuple[Path, Path, float]:
    """Run one `--gen` command and capture raw output plus stderr."""

    stderr_path = artifact_dir / f"{name}.stderr.log"
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.monotonic() - start
    stderr_text = completed.stderr.decode("utf-8", errors="replace")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    if completed.returncode != 0:
        fail(
            "\n".join(
                [
                    f"{name} failed (rc={completed.returncode})",
                    f"command={shell_join(command)}",
                    f"stderr={stderr_path}",
                    first_lines(stderr_text, 80),
                ]
            ).rstrip(),
            artifact_dir,
        )
    output_path.write_bytes(completed.stdout)
    return output_path, stderr_path, elapsed


def sha256_hex(path: Path) -> str:
    """Return the SHA-256 digest for one file."""

    return hashlib.sha256(read_bytes(path)).hexdigest()


def artifact_summary(path: Path) -> str:
    """Return a compact summary for one artifact."""

    return f"{path} size={path.stat().st_size} sha256={sha256_hex(path)[:16]}"


def short_unified_diff(left: Path, right: Path, artifact_dir: Path) -> str:
    """Write and return a short unified diff for one text mismatch."""

    diff_path = artifact_dir / "stage1_stage2_codegen.diff"
    head: list[str] = []
    diff_count = 0
    with diff_path.open("w", encoding="utf-8") as handle:
        for line in difflib.unified_diff(
                read_text(left).splitlines(),
                read_text(right).splitlines(),
                fromfile=str(left),
                tofile=str(right),
                n=3,
                lineterm="",
        ):
            handle.write(line + "\n")
            if diff_count < 80:
                head.append(line)
            diff_count += 1

    if diff_count == 0:
        return f"diff={diff_path} (files differ but no text diff was produced)"
    if diff_count > 80:
        return f"diff={diff_path}\n" + "\n".join(head) + "\n..."
    return f"diff={diff_path}\n" + "\n".join(head)


def assert_same_text(left: Path, right: Path, artifact_dir: Path) -> None:
    """Compare two generated text artifacts byte-for-byte and fail with a compact diff."""

    if read_bytes(left) == read_bytes(right):
        return

    fail(
        "\n".join(
            [
                "Stage 1 vs Stage 2 whole-compiler generated C mismatch",
                artifact_summary(left),
                artifact_summary(right),
                short_unified_diff(left, right, artifact_dir),
            ]
        ),
        artifact_dir,
    )


def main() -> int:
    """Program entrypoint."""

    BUILD_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path(tempfile.mkdtemp(prefix="l0_stage1_stage2_codegen_compare.", dir=BUILD_TESTS_DIR))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    total_start = time.monotonic()

    try:
        _, _, _, repo_env = require_repo_stage2_test_env("l0c_stage1_stage2_codegen_compare.py")

        bootstrap_dir = artifact_dir / "stage2-bootstrap"
        bootstrap_dir_rel = os.path.relpath(bootstrap_dir, REPO_ROOT)
        bootstrap_env = repo_env.copy()
        bootstrap_env["DEA_BUILD_DIR"] = bootstrap_dir_rel

        stage2_wrapper = bootstrap_dir / "bin" / "l0c-stage2"
        stage1_output = artifact_dir / "l0c.stage1.generated.c"
        stage2_output = artifact_dir / "l0c.stage2.generated.c"

        notice("building Stage 2 bootstrap compiler from Stage 1")
        _, bootstrap_elapsed = run_logged(
            "bootstrap_build",
            stage2_bootstrap_build_command(),
            env=bootstrap_env,
            artifact_dir=artifact_dir,
        )
        notice(f"built Stage 2 bootstrap compiler in {format_duration(bootstrap_elapsed)}: {stage2_wrapper}")

        if not stage2_wrapper.is_file():
            fail("bootstrap build did not produce the expected Stage 2 wrapper", artifact_dir)

        gen_args = ["--gen", "--no-line-directives", "--project-root", "compiler/stage2_l0/src", "l0c"]

        notice("generating whole-compiler C with Stage 1")
        _, _, stage1_elapsed = run_codegen(
            "stage1_codegen",
            [*source_tree_l0c_command(), *gen_args],
            env=repo_env,
            artifact_dir=artifact_dir,
            output_path=stage1_output,
        )
        notice(f"generated Stage 1 whole-compiler C in {format_duration(stage1_elapsed)}: {stage1_output}")

        notice("generating whole-compiler C with Stage 2")
        _, _, stage2_elapsed = run_codegen(
            "stage2_codegen",
            [*stage2_wrapper_command(stage2_wrapper), *gen_args],
            env=repo_env,
            artifact_dir=artifact_dir,
            output_path=stage2_output,
        )
        notice(f"generated Stage 2 whole-compiler C in {format_duration(stage2_elapsed)}: {stage2_output}")

        notice("comparing exact Stage 1 and Stage 2 generated C outputs")
        assert_same_text(stage1_output, stage2_output, artifact_dir)

        total_elapsed = time.monotonic() - total_start
        notice(f"PASS (total wall time: {format_duration(total_elapsed)})")
        if keep_artifacts:
            notice(f"artifacts={artifact_dir}")
        return 0
    except RuntimeError as exc:
        keep_artifacts = True
        print(f"l0c_stage1_stage2_codegen_compare: FAIL: {exc}")
        return 2
    except CodegenCompareFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l0c_stage1_stage2_codegen_compare: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l0c_stage1_stage2_codegen_compare: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
