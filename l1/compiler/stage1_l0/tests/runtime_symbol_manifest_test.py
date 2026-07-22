#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Lock the exported L1 runtime archive symbol surface."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
MANIFEST_PATH = L1_ROOT / "compiler" / "shared" / "runtime" / "dea_rt.symbols"
TRACED_MANIFEST_PATH = L1_ROOT / "compiler" / "shared" / "runtime" / "dea_rt_traced.symbols"

# nm prefix convention: macOS prepends one underscore beyond the C-source name;
# Linux/ELF and x86_64 mingw do not. Revisit if a Windows CI lane covers 32-bit
# __cdecl exports later.
_NM_LEADING_UNDERSCORE = sys.platform in ("darwin",)


def build_dir() -> Path:
    raw = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if raw.is_absolute():
        return raw
    return (L1_ROOT / raw).resolve()


def runtime_archive(archive_name: str) -> Path:
    return build_dir() / "lib" / archive_name


def _normalize_symbol(symbol: str) -> str:
    if _NM_LEADING_UNDERSCORE and symbol.startswith("_"):
        return symbol[1:]
    return symbol


def runtime_symbols(archive_name: str) -> list[str]:
    archive = runtime_archive(archive_name)
    if not archive.is_file():
        raise AssertionError(f"missing runtime archive: {archive}")

    completed = subprocess.run(
        ["nm", "-g", str(archive)],
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"nm failed for {archive}")

    symbols: set[str] = set()
    for raw_line in completed.stdout.splitlines():
        parts = raw_line.split()
        if len(parts) < 3 or parts[1] != "T":
            continue
        symbols.add(_normalize_symbol(parts[2]))

    return sorted(symbols)


def expected_symbols(manifest_path: Path) -> list[str]:
    return [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    actual = runtime_symbols("libdea_rt.a")
    expected = expected_symbols(MANIFEST_PATH)
    assert actual == expected, (
        "runtime symbol manifest mismatch:\n"
        f"expected={expected}\n"
        f"actual={actual}\n"
    )

    traced_actual = runtime_symbols("libdea_rt_traced.a")
    traced_expected = expected_symbols(TRACED_MANIFEST_PATH)
    assert traced_actual == traced_expected, (
        "traced runtime symbol manifest mismatch:\n"
        f"expected={traced_expected}\n"
        f"actual={traced_actual}\n"
    )

    check_basic_actual = runtime_symbols("libdea_rt_check_basic.a")
    assert check_basic_actual == expected, (
        "check-basic runtime symbol manifest mismatch:\n"
        f"expected={expected}\n"
        f"actual={check_basic_actual}\n"
    )

    unchecked_actual = runtime_symbols("libdea_rt_unchecked.a")
    assert unchecked_actual == expected, (
        "unchecked runtime symbol manifest mismatch:\n"
        f"expected={expected}\n"
        f"actual={unchecked_actual}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
