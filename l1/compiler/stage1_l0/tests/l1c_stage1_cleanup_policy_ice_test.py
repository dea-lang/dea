#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for Stage 1 cleanup-policy ICE paths."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


class CleanupPolicyIceFailure(RuntimeError):
    """Raised when one cleanup-policy ICE regression fails."""


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


def bootstrap_compiler() -> Path:
    """Return the upstream L0 bootstrap compiler used for L1 `.l0` implementation tests."""

    override = os.environ.get("L1_BOOTSTRAP_L0C")
    if override:
        return resolve_tool(Path(override))
    return resolve_tool(REPO_ROOT / "l0" / "build" / "dea" / "bin" / "l0c-stage2")


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise CleanupPolicyIceFailure(f"{message}\nartifacts={artifact_dir}")


def write_case_source(artifact_dir: Path, case_name: str, source: str) -> Path:
    """Write one temporary L0 implementation source file for one regression case."""

    case_dir = artifact_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "main.l0"
    source_path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return source_path


def run_ice_case(case_name: str, source: str, expected_ice: str, artifact_dir: Path) -> None:
    """Run one Stage 1 program that should fail with one expected ICE code."""

    compiler = bootstrap_compiler()
    if not compiler.is_file():
        fail(f"missing L1 bootstrap compiler: {compiler}", artifact_dir)

    source_path = write_case_source(artifact_dir, case_name, source)
    stdout_path = artifact_dir / f"{case_name}.stdout.log"
    stderr_path = artifact_dir / f"{case_name}.stderr.log"

    run_result = subprocess.run(
        [str(compiler), "--project-root", "compiler/stage1_l0/src", "--run", str(source_path)],
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(run_result.stdout if run_result.stdout is not None else b"")
    stderr_path.write_bytes(run_result.stderr if run_result.stderr is not None else b"")

    stdout_text = read_text(stdout_path)
    stderr_text = read_text(stderr_path)
    if run_result.returncode == 0:
        fail(f"{case_name} expected failure with {expected_ice}, but exited 0", artifact_dir)
    if expected_ice not in stderr_text:
        fail(f"{case_name} missing expected ICE {expected_ice} in stderr", artifact_dir)
    if stdout_text != "":
        fail(f"{case_name} expected empty stdout, got {stdout_text!r}", artifact_dir)


def empty_result_helper() -> str:
    """Return shared helper source for one empty analysis result."""

    return """
    func empty_result() -> AnalysisResult* {
        let result = new AnalysisResult(
            dr_state_create("", null),
            diag_create(),
            null,
            null,
            null,
            spm_create(),
            sim_create(),
            spm_create()
        );
        result.signatures = sig_make_tables();
        return result;
    }
    """


def test_missing_enum_info_ice(artifact_dir: Path) -> None:
    """Missing enum cleanup metadata must raise `ICE-1080`."""

    run_ice_case(
        "missing_enum_info_ice",
        f"""
        module main;

        import std.hashmap;
        import std.vector;

        import ast;
        import c_emitter;
        import driver;
        import sem_context;
        import signatures;
        import types;
        import util.diag;

        {empty_result_helper()}

        func main() -> int {{
            let emitter = cem_create();
            let result = empty_result();
            cem_set_analysis(emitter, result);
            cem_emit_enum_cleanup(emitter, "p", type_new_enum("main", "Missing"));
            return 0;
        }}
        """,
        "[ICE-1080]",
        artifact_dir,
    )


def test_missing_struct_info_ice(artifact_dir: Path) -> None:
    """Missing struct cleanup metadata must raise `ICE-1270`."""

    run_ice_case(
        "missing_struct_info_ice",
        f"""
        module main;

        import std.hashmap;
        import std.vector;

        import ast;
        import c_emitter;
        import driver;
        import sem_context;
        import signatures;
        import types;
        import util.diag;

        {empty_result_helper()}

        func main() -> int {{
            let emitter = cem_create();
            let result = empty_result();
            cem_set_analysis(emitter, result);
            cem_emit_struct_cleanup(emitter, "p", type_new_struct("main", "Missing"));
            return 0;
        }}
        """,
        "[ICE-1270]",
        artifact_dir,
    )


def main() -> int:
    """Program entrypoint."""

    artifact_dir = Path(tempfile.mkdtemp(prefix="l1_stage1_cleanup_policy_ice."))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    checks = [
        test_missing_enum_info_ice,
        test_missing_struct_info_ice,
    ]

    try:
        for check in checks:
            check(artifact_dir)
        print("l1c_stage1_cleanup_policy_ice_test: PASS")
        return 0
    except CleanupPolicyIceFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l1c_stage1_cleanup_policy_ice_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l1c_stage1_cleanup_policy_ice_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
