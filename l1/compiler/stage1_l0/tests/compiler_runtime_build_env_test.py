#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for native L1 compiler runtime build flags."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
SCRIPTS_ROOT = L1_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from build_stage1_l1c import (  # noqa: E402
    L1_COMPILER_RT_CHECK_BASIC_ENV,
    L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV,
    L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV,
    L1_COMPILER_RT_UNCHECKED_ENV,
    compiler_runtime_build_env,
)


@dataclass(frozen=True)
class BuildEnvCase:
    """One compiler runtime environment composition case."""

    name: str
    source: dict[str, str]
    expected_cflags: str | None


def require_build_env_cases() -> None:
    """Require compiler mode and quarantine flags to resolve independently."""

    cases = (
        BuildEnvCase(
            "absent values use basic and q256 defaults",
            {},
            "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "empty basic selects full checked mode",
            {L1_COMPILER_RT_CHECK_BASIC_ENV: ""},
            "-D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "explicit basic preserves raw optimization flags",
            {"L0_CFLAGS": "-O2", L1_COMPILER_RT_CHECK_BASIC_ENV: "1"},
            "-O2 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "unchecked suppresses the basic default",
            {L1_COMPILER_RT_CHECK_BASIC_ENV: "1", L1_COMPILER_RT_UNCHECKED_ENV: "1"},
            "-DL0_RT_UNCHECKED -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "raw basic mode takes precedence",
            {
                "L0_CFLAGS": "-O1 -DL0_RT_CHECK_BASIC=1",
                L1_COMPILER_RT_UNCHECKED_ENV: "1",
            },
            "-O1 -DL0_RT_CHECK_BASIC=1 -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "raw unchecked mode takes precedence",
            {"L0_CFLAGS": "-D L0_RT_UNCHECKED", L1_COMPILER_RT_CHECK_BASIC_ENV: "1"},
            "-D L0_RT_UNCHECKED -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "conflicting raw modes remain visible",
            {"L0_CFLAGS": "-DL0_RT_CHECK_BASIC -DL0_RT_UNCHECKED"},
            "-DL0_RT_CHECK_BASIC -DL0_RT_UNCHECKED -D_RT_QUARANTINE_MAX_COUNT=256",
        ),
        BuildEnvCase(
            "compiler quarantine dimensions are independent",
            {
                L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV: "8192",
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV: "17",
            },
            "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_BYTES=8192 -D_RT_QUARANTINE_MAX_COUNT=17",
        ),
        BuildEnvCase(
            "raw byte limit suppresses only the compiler byte limit",
            {
                "L0_CFLAGS": "-O2 -D_RT_QUARANTINE_MAX_BYTES=4096",
                L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV: "8192",
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV: "17",
            },
            "-O2 -D_RT_QUARANTINE_MAX_BYTES=4096 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=17",
        ),
        BuildEnvCase(
            "raw count suppresses only the compiler count limit",
            {
                "L0_CFLAGS": "-D_RT_QUARANTINE_MAX_COUNT=33",
                L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV: "2048",
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV: "17",
            },
            "-D_RT_QUARANTINE_MAX_COUNT=33 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_BYTES=2048",
        ),
        BuildEnvCase(
            "empty quarantine defaults disable compiler tuning",
            {
                L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV: "",
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV: "",
            },
            "-DL0_RT_CHECK_BASIC",
        ),
        BuildEnvCase(
            "empty mode and tuning defaults preserve absent cflags",
            {
                L1_COMPILER_RT_CHECK_BASIC_ENV: "",
                L1_COMPILER_RT_QUARANTINE_MAX_BYTES_ENV: "",
                L1_COMPILER_RT_QUARANTINE_MAX_COUNT_ENV: "",
            },
            None,
        ),
        BuildEnvCase(
            "similarly named raw macros do not suppress exact defaults",
            {
                "L0_CFLAGS": (
                    "-DNOT_L0_RT_CHECK_BASIC "
                    "-D_RT_QUARANTINE_MAX_COUNT_EXTRA=9"
                ),
            },
            (
                "-DNOT_L0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT_EXTRA=9 "
                "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256"
            ),
        ),
    )

    for case in cases:
        source_before = dict(case.source)
        result = compiler_runtime_build_env(case.source)
        if case.source != source_before:
            raise AssertionError(f"{case.name}: source environment was mutated")
        if result is case.source:
            raise AssertionError(f"{case.name}: helper returned the source mapping")

        actual_cflags = result.get("L0_CFLAGS")
        if actual_cflags != case.expected_cflags:
            raise AssertionError(
                f"{case.name}: expected L0_CFLAGS={case.expected_cflags!r}, got {actual_cflags!r}"
            )
        if compiler_runtime_build_env(result) != result:
            raise AssertionError(f"{case.name}: repeated composition duplicated compiler flags")


def require_make_help_parity() -> None:
    """Require Make help to separate and uniquely list the public flag families."""

    completed = subprocess.run(
        ["make", "help"],
        cwd=L1_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(f"make help exited with {completed.returncode}:\n{completed.stdout}")

    for heading in (
        "Compiler construction variables:",
        "Generated L1 program variables:",
        "Runtime archive variables:",
        "Test variables:",
    ):
        if heading not in completed.stdout:
            raise AssertionError(f"make help omitted section {heading!r}")

    for variable in (
        "L1_COMPILER_RT_CHECK_BASIC",
        "L1_COMPILER_RT_UNCHECKED",
        "L1_COMPILER_RT_QUARANTINE_MAX_BYTES",
        "L1_COMPILER_RT_QUARANTINE_MAX_COUNT",
        "L0_CFLAGS",
        "L1_CFLAGS",
    ):
        occurrences = completed.stdout.count(variable)
        if occurrences != 1:
            raise AssertionError(f"make help listed {variable} {occurrences} times, expected once")


def require_make_preserves_environment_cflags() -> None:
    """Require the Stage 1 recipe to inherit raw C flags without Make expansion."""

    literal_cflags = "-Wl,-rpath,$ORIGIN/lib"
    env = os.environ.copy()
    env["L0_CFLAGS"] = literal_cflags
    completed = subprocess.run(
        [
            "make",
            "--dry-run",
            "--old-file=venv",
            "--old-file=runtime",
            "--old-file=_ensure-bootstrap-l0-stage2",
            "build-stage1",
        ],
        cwd=L1_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"make --dry-run build-stage1 exited with {completed.returncode}:\n{completed.stdout}"
        )
    if "./scripts/build_stage1_l1c.py" not in completed.stdout:
        raise AssertionError("make --dry-run omitted the build-stage1 recipe")
    if "L0_CFLAGS=" in completed.stdout:
        raise AssertionError(
            "build-stage1 must inherit L0_CFLAGS instead of reinjecting it into the recipe:\n"
            f"{completed.stdout}"
        )
    if "$ORIGIN/lib" in completed.stdout or "RIGIN/lib" in completed.stdout:
        raise AssertionError(
            "build-stage1 exposed or mangled the literal $ORIGIN environment value:\n"
            f"{completed.stdout}"
        )


def main() -> int:
    """Run native compiler build-environment regressions."""

    require_build_env_cases()
    require_make_help_parity()
    require_make_preserves_environment_cflags()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
