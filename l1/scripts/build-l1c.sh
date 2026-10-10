#!/usr/bin/env bash
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
MONOREPO_ROOT="$(cd -- "${REPO_ROOT}/.." && pwd -P)"
PYTHON_BIN="${PYTHON:-}"

if [ -z "${PYTHON_BIN}" ] && [ -x "${MONOREPO_ROOT}/.venv/bin/python" ]; then
    PYTHON_BIN="${MONOREPO_ROOT}/.venv/bin/python"
fi
if [ -z "${PYTHON_BIN}" ] && [ -x "${MONOREPO_ROOT}/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="${MONOREPO_ROOT}/.venv/Scripts/python.exe"
fi
if [ -z "${PYTHON_BIN}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        PYTHON_BIN="python"
    fi
fi

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/build_l1c.py" "$@"

