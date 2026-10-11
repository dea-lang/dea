#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for canonical compiler cleanup-policy ICE paths."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[3]
L2_ROOT = REPO_ROOT / "l2"
SCRIPTS_ROOT = L2_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_l2c import build_support_objects, resolve_bootstrap, bootstrap_environment  # noqa: E402
from dea_tooling.bootstrap import wrapper_command  # noqa: E402


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
    """Return the explicit canonical compiler compiler used for L2 implementation tests."""

    return resolve_bootstrap()


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise CleanupPolicyIceFailure(f"{message}\nartifacts={artifact_dir}")


def write_case_source(artifact_dir: Path, case_name: str, source: str) -> Path:
    """Write one temporary L2 implementation source file for one regression case."""

    case_dir = artifact_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "main.l1"
    source_path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return source_path


def run_ice_case(case_name: str, source: str, expected_ice: str, artifact_dir: Path) -> None:
    """Run one canonical compiler program that should fail with one expected ICE code."""

    compiler = bootstrap_compiler()
    if not compiler.is_file():
        fail(f"missing L2 bootstrap compiler: {compiler}", artifact_dir)

    source_path = write_case_source(artifact_dir, case_name, source)
    stdout_path = artifact_dir / f"{case_name}.stdout.log"
    stderr_path = artifact_dir / f"{case_name}.stderr.log"

    run_result = subprocess.run(
        [
            *wrapper_command(compiler),
            "--project-root",
            "compiler/src",
            "--run",
            *build_support_objects(artifact_dir / "support", dict(os.environ), preparation=False),
            str(source_path),
        ],
        cwd=L2_ROOT,
        env=bootstrap_environment(dict(os.environ)),
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
        import c_emitter.state;
        import c_emitter.lifetime;
        import driver.state;
        import sem_context;
        import signatures.tables;
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
        import c_emitter.state;
        import c_emitter.lifetime;
        import driver.state;
        import sem_context;
        import signatures.tables;
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

    artifact_dir = Path(tempfile.mkdtemp(prefix="l2_compiler_cleanup_policy_ice."))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"

    checks = [
        test_missing_enum_info_ice,
        test_missing_struct_info_ice,
    ]

    try:
        for check in checks:
            check(artifact_dir)
        print("l2c_cleanup_policy_ice_test: PASS")
        return 0
    except CleanupPolicyIceFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l2c_cleanup_policy_ice_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l2c_cleanup_policy_ice_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
