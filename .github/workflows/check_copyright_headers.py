# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Check tracked C/shell/L0/Python source files for a copyright notice."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

COPYRIGHT_RE = re.compile(r"Copyright\s*\(c\)\s*\d{4}(?:-\d{4})?\b")
SHELL_SHEBANG_RE = re.compile(r"^#!.*\b(?:bash|sh|zsh)\b")
TARGET_SUFFIXES = {".c", ".h", ".l0", ".l1", ".py", ".sh"}
MAX_SCAN_LINES = 80
EXCLUDED_PREFIXES = (
    "tools/",
    "editors/tree-sitter-dea/src/",
    "l0/compiler/stage2_l0/tests/fixtures/backend_golden/",
    "l1/compiler/stage1_l0/tests/fixtures/backend_golden/",
)


def _tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=False,
    )
    files = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        files.append(repo_root / raw.decode("utf-8"))
    return files


def _read_head(path: Path, max_lines: int) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = []
            for _ in range(max_lines):
                line = f.readline()
                if line == "":
                    break
                lines.append(line)
    except OSError:
        return ""
    return "".join(lines)


def _is_shell_script(path: Path) -> bool:
    if path.suffix == ".sh":
        return True
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return False
    return bool(SHELL_SHEBANG_RE.search(first))


def _is_target_source(path: Path) -> bool:
    if path.suffix in TARGET_SUFFIXES:
        return True
    return _is_shell_script(path)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    missing: list[str] = []
    scanned = 0

    for path in _tracked_files(repo_root):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path.startswith(EXCLUDED_PREFIXES):
            continue
        if not _is_target_source(path):
            continue
        scanned += 1
        head = _read_head(path, MAX_SCAN_LINES)
        if not COPYRIGHT_RE.search(head):
            missing.append(rel_path)

    if missing:
        print("Missing copyright notice in:")
        for path in sorted(missing):
            print(f"  - {path}")
        print(f"\nChecked {scanned} files. Missing: {len(missing)}.")
        return 1

    print(f"Checked {scanned} files. All have copyright notices.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
