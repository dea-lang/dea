#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Check native type-resolution diagnostic messages against expected wording."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from dea_tooling.bootstrap import wrapper_command


REPO_ROOT = Path(__file__).resolve().parents[1]

CASES = {
    "sig-0010-not-a-type": {
        "files": {
            "main": """\
                module main;
                func bar() -> int { return 0; }
                func foo() -> int { return 1 as bar; }
            """,
        },
        "expected": "[SIG-0010] symbol 'bar' in module 'main' is not a type (kind=FUNC)",
    },
    "sig-0018-qualified-type-path": {
        "files": {
            "color": """\
                module color;
                enum Color { Red(); }
            """,
            "main": """\
                module main;
                import color;
                func foo(x: color::Color::Red) -> int { return 0; }
            """,
        },
        "expected": "[SIG-0018] nested symbol path 'color::Color::Red': paths must have the form 'module::symbol' (did you mean 'color::Red'?)",
    },
    "typ-0158-nested-symbol-path": {
        "files": {
            "color": """\
                module color;
                enum Color { Red(); }
            """,
            "main": """\
                module main;
                import color;
                func foo() -> int { let x: int = color::Color::Red; return 0; }
            """,
        },
        "expected": "[TYP-0158] nested symbol path 'color::Color::Red': paths must have the form 'module::symbol' (did you mean 'color::Red'?)",
    },
    "sig-0019-ambiguous-type": {
        "files": {
            "a": """\
                module a;
                struct T { value: int; }
            """,
            "b": """\
                module b;
                struct T { value: int; }
            """,
            "main": """\
                module main;
                import a;
                import b;
                func foo(x: T) -> int { return 0; }
            """,
        },
        "expected": "[SIG-0019] ambiguous type 'T' (imported from modules 'a', 'b'); use 'a::T' or 'b::T' to disambiguate",
    },
    "sig-0020-alias-cycle": {
        "files": {
            "main": """\
                module main;
                type A = B;
                type B = A;
                func foo(x: A) -> int { return 0; }
            """,
        },
        "expected": "[SIG-0020] cyclic type alias involving 'A' in module 'main'",
    },
    "par-9401-array-type-syntax": {
        "files": {
            "main": """\
                module main;
                func foo() -> int {
                    let x: int[] = 0;
                    return x;
                }
            """,
        },
        "expected": "[PAR-9401] array types not yet supported",
    },
    "typ-0211-nullable-indexing": {
        "files": {
            "main": """\
                module main;
                extern func maybe_buf() -> int*?;
                func foo(i: int) -> int {
                    let buf: int*? = maybe_buf();
                    return buf[i];
                }
            """,
        },
        "expected": {
            "l0": "[TYP-0211] cannot index into nullable type 'int*?'; indexing is not yet supported",
        },
    },
    "typ-0212-pointer-indexing": {
        "files": {
            "main": """\
                module main;
                extern func buf() -> int*;
                func foo(i: int) -> int { return buf()[i]; }
            """,
        },
        "expected": {
            "l0": "[TYP-0212] cannot index into expression of type 'int*'; indexing is not yet supported",
        },
    },
}


def write_case(root: Path, stage: str, files: dict[str, str]) -> None:
    for module_name, source in files.items():
        (root / f"{module_name}.{stage}").write_text(dedent(source), encoding="utf-8")


def run_case(stage: str, compiler: Path, case_name: str, expected: str, files: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory(prefix=f"dea-{stage}-{case_name}-") as tmp:
        root = Path(tmp)
        write_case(root, stage, files)
        env = os.environ.copy()
        if stage == "l0":
            cwd = REPO_ROOT / "l0"
            env["L0_HOME"] = str(cwd / "compiler")
        else:
            cwd = REPO_ROOT / "l1"
            env["L0_HOME"] = str(REPO_ROOT / "l0" / "compiler")
            env["L1_HOME"] = str(cwd / "compiler")
        completed = subprocess.run(
            [*wrapper_command(compiler), "-P", str(root), "--check", "main"],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = completed.stdout
        if completed.returncode == 0:
            raise AssertionError(f"{case_name}: expected failure, compiler succeeded")
        if expected not in output:
            raise AssertionError(
                f"{case_name}: missing expected message\nexpected: {expected}\noutput:\n{output}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["l0", "l1"], required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    for case_name, spec in CASES.items():
        expected_spec = spec["expected"]
        if isinstance(expected_spec, dict):
            if args.stage not in expected_spec:
                continue
            expected = expected_spec[args.stage]
        else:
            expected = expected_spec
        files = spec.get("files_by_stage", {}).get(args.stage, spec["files"])
        run_case(args.stage, args.compiler.resolve(strict=True), case_name, expected, files)
    print(f"{args.stage}: diagnostic message parity passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
