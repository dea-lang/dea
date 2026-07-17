#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dist_tools_lib import source_tree_stage1_command


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "compiler" / "stage2_l0" / "tests" / "fixtures" / "backend_golden"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n") + "\n"


def discover_cases(root: Path) -> list[Path]:
    cases: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "entry_module.txt").is_file():
            cases.append(child)
    return cases


def selected_cases(root: Path, requested: list[str]) -> list[Path]:
    cases = discover_cases(root)
    if not requested:
        return cases

    by_name = {case.name: case for case in cases}
    missing = [name for name in requested if name not in by_name]
    if missing:
        raise SystemExit(f"unknown backend golden case(s): {', '.join(missing)}")
    return [by_name[name] for name in requested]


def entry_module(case_dir: Path) -> str:
    return (case_dir / "entry_module.txt").read_text(encoding="utf-8").strip()


def golden_path(case_dir: Path) -> Path:
    return case_dir / f"{case_dir.name}.golden.c"


def generate_stage1_golden(case_dir: Path) -> str:
    module = entry_module(case_dir)
    cmd = [
        *source_tree_stage1_command(REPO_ROOT),
        "--gen",
        "--no-line-directives",
        "--project-root",
        str(case_dir),
        module,
    ]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"[refresh-goldens] Stage 1 generation failed for case '{case_dir.name}'\n")
        if proc.stdout:
            sys.stderr.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise SystemExit(1)
    return normalize_text(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh or check Stage 2 backend golden C fixtures.")
    parser.add_argument("cases", nargs="*", help="Optional fixture case names to refresh/check.")
    parser.add_argument("--check", action="store_true", help="Fail instead of rewriting when a golden is stale.")
    args = parser.parse_args()

    stale: list[str] = []
    for case_dir in selected_cases(FIXTURE_ROOT, args.cases):
        expected = generate_stage1_golden(case_dir)
        path = golden_path(case_dir)
        current = normalize_text(path.read_text(encoding="utf-8")) if path.exists() else None

        if current == expected:
            print(f"{case_dir.name}: OK")
            continue

        if args.check:
            stale.append(case_dir.name)
            print(f"{case_dir.name}: STALE")
            continue

        path.write_text(expected, encoding="utf-8")
        print(f"{case_dir.name}: UPDATED")

    if stale:
        sys.stderr.write("stale backend golden case(s): " + ", ".join(stale) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
