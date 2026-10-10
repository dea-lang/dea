#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Check L2's owned diagnostic contract without importing a sibling compiler."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import tempfile
from l2c_compile_only_test import subject_compiler, L2_ROOT


def main() -> int:
    """Run the retained diagnostic code and wording scenarios against canonical L2."""
    cases = json.loads((Path(__file__).parent / "fixtures/diagnostics.json").read_text())
    failures = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="l2-diagnostic-") as temporary:
            root = Path(temporary)
            for name, contents in case["files"].items():
                (root / name).write_text(contents, encoding="utf-8")
            for name, contents in case.get("binary_files", {}).items():
                (root / name).write_bytes(bytes.fromhex(contents))
            result = subprocess.run([str(subject_compiler()), "--project-root", str(root), "--check", case["target"]],
                                    cwd=L2_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if (case["expected"] not in result.stdout + result.stderr or
                    (case.get("requires_failure") and result.returncode == 0)):
                failures.append(f"{case['name']}: {result.stdout + result.stderr}")
    if failures:
        raise AssertionError("\n".join(failures))
    print(f"diagnostic_contract_test: {len(cases)} scenarios passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
