#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Focused tests for native L0 compiler runtime build flags."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_stage2_l0c import compiler_runtime_build_env


@pytest.mark.parametrize(
    ("source_env", "expected_cflags"),
    [
        pytest.param(
            {},
            "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256",
            id="absent-env-uses-compiler-defaults",
        ),
        pytest.param(
            {
                "L0_COMPILER_RT_CHECK_BASIC": "",
                "L0_COMPILER_RT_QUARANTINE_MAX_COUNT": "",
            },
            "",
            id="empty-compiler-defaults-select-full-with-runtime-default-quarantine",
        ),
        pytest.param(
            {"L0_COMPILER_RT_CHECK_BASIC": ""},
            "-D_RT_QUARANTINE_MAX_COUNT=256",
            id="empty-basic-default-selects-full-checked",
        ),
        pytest.param(
            {"L0_COMPILER_RT_CHECK_BASIC": "", "L0_RT_CHECK_BASIC": "1"},
            "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256",
            id="explicit-basic-overrides-empty-compiler-default",
        ),
        pytest.param(
            {"L0_RT_UNCHECKED": "1"},
            "-DL0_RT_UNCHECKED -D_RT_QUARANTINE_MAX_COUNT=256",
            id="explicit-unchecked-overrides-basic-default",
        ),
        pytest.param(
            {"L0_RT_UNCHECKED": "1", "L0_RT_CHECK_BASIC": "1"},
            "-DL0_RT_UNCHECKED -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256",
            id="conflicting-explicit-modes-remain-visible",
        ),
        pytest.param(
            {
                "L0_CFLAGS": "-O3 -DL0_RT_UNCHECKED=1 -D_RT_QUARANTINE_MAX_COUNT=17",
                "L0_RT_CHECK_BASIC": "1",
                "L0_RT_QUARANTINE_MAX_COUNT": "99",
            },
            "-O3 -DL0_RT_UNCHECKED=1 -D_RT_QUARANTINE_MAX_COUNT=17",
            id="raw-joined-defines-win-without-duplication",
        ),
        pytest.param(
            {
                "L0_CFLAGS": "-O2 -D L0_RT_CHECK_BASIC -D _RT_QUARANTINE_MAX_COUNT=7",
                "L0_RT_UNCHECKED": "1",
                "L0_RT_QUARANTINE_MAX_COUNT": "99",
            },
            "-O2 -D L0_RT_CHECK_BASIC -D _RT_QUARANTINE_MAX_COUNT=7",
            id="raw-split-defines-win-without-duplication",
        ),
        pytest.param(
            {
                "L0_CFLAGS": "-O2 -D_RT_QUARANTINE_MAX_COUNT=7",
                "L0_RT_QUARANTINE_MAX_BYTES": "8192",
            },
            "-O2 -D_RT_QUARANTINE_MAX_COUNT=7 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_BYTES=8192",
            id="raw-count-does-not-suppress-mode-or-byte-limit",
        ),
        pytest.param(
            {
                "L0_CFLAGS": "-O2 -D_RT_QUARANTINE_MAX_BYTES=4096",
                "L0_RT_QUARANTINE_MAX_COUNT": "8",
            },
            "-O2 -D_RT_QUARANTINE_MAX_BYTES=4096 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=8",
            id="raw-byte-limit-does-not-suppress-mode-or-count-limit",
        ),
        pytest.param(
            {
                "L0_RT_QUARANTINE_MAX_BYTES": "8192",
                "L0_RT_QUARANTINE_MAX_COUNT": "32",
                "L0_COMPILER_RT_QUARANTINE_MAX_COUNT": "64",
            },
            "-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_BYTES=8192 -D_RT_QUARANTINE_MAX_COUNT=32",
            id="user-quarantine-values-override-compiler-count-default",
        ),
    ],
)
def test_compiler_runtime_build_env(source_env: dict[str, str], expected_cflags: str) -> None:
    """Resolve mode and quarantine flags with documented precedence."""

    result = compiler_runtime_build_env(source_env)

    assert result.get("L0_CFLAGS", "") == expected_cflags


def test_compiler_runtime_build_env_is_idempotent() -> None:
    """Applying compiler defaults twice does not duplicate flags."""

    once = compiler_runtime_build_env({"L0_CFLAGS": "-O2"})

    assert compiler_runtime_build_env(once) == once


def test_compiler_runtime_build_env_does_not_mutate_source() -> None:
    """Flag composition leaves the caller-owned environment unchanged."""

    source = {
        "L0_CFLAGS": "-O2",
        "L0_RT_QUARANTINE_MAX_BYTES": "1024",
    }
    original = source.copy()

    result = compiler_runtime_build_env(source)

    assert source == original
    assert result is not source
    assert result["L0_CFLAGS"] == (
        "-O2 -DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_BYTES=1024 "
        "-D_RT_QUARANTINE_MAX_COUNT=256"
    )
