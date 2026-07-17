#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native diagnostic-code parity checks against the Python L0 oracle triggers."""

from __future__ import annotations

import argparse
import os
import re
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
ORACLE_TESTS = REPO_ROOT / "l0" / "compiler" / "stage1_py" / "tests"
ORACLE_ROOT = REPO_ROOT / "l0" / "compiler" / "stage1_py"
CODE_RE = re.compile(r"\[([A-Z]+-\d{4})\]")


def load_oracle():
    sys.path.insert(0, str(ORACLE_TESTS))
    sys.path.insert(0, str(ORACLE_ROOT))
    from diagnostics import test_diagnostic_codes as oracle  # type: ignore

    return oracle


def write_multi_module(root: Path, stage: str, mode: str) -> str:
    def w(name: str, text: str) -> None:
        (root / f"{name}.{stage}").write_text(dedent(text), encoding="utf-8")

    if mode == "missing-file":
        return "missing"
    if mode == "module-mismatch":
        w("foo", "module bar;\n")
        return "foo"
    if mode == "import-cycle":
        w("a", "module a;\nimport b;\n")
        w("b", "module b;\nimport a;\n")
        return "a"
    if mode == "bad-encoding":
        (root / f"main.{stage}").write_bytes(b"module main;\nfunc main() -> int { return 0; }\n\xff")
        return "main"
    if mode == "extern-shadow":
        w("helper", "module helper;\nextern func ext_fn(x: int) -> int;\n")
        w("main", "module main;\nimport helper;\nextern func ext_fn(x: int) -> int;\nfunc foo() -> int { return ext_fn(1); }\n")
        return "main"
    if mode == "import-shadow":
        w("helper", "module helper;\nfunc foo() -> int { return 1; }\n")
        w("main", "module main;\nimport helper;\nfunc foo() -> int { return 2; }\n")
        return "main"
    if mode == "ambiguous-import":
        w("a", "module a;\nfunc foo() -> int { return 1; }\n")
        w("b", "module b;\nfunc foo() -> int { return 2; }\n")
        w("main", "module main;\nimport a;\nimport b;\nfunc bar() -> int { return 0; }\n")
        return "main"
    if mode == "duplicate-import":
        w("helper", "module helper;\nfunc foo() -> int { return 1; }\n")
        w("main", "module main;\nimport helper;\nimport helper;\nfunc bar() -> int { return foo(); }\n")
        return "main"
    if mode == "shadow-imported-variant":
        w("colors", "module colors;\nenum Color { Red(); Green(); }\n")
        w("main", "module main;\nimport colors;\nfunc foo() -> int { let Red: int = 1; return Red; }\n")
        return "main"
    if mode == "shadow-ambiguous":
        w("a", "module a;\nenum E1 { Red(); }\n")
        w("b", "module b;\nenum E2 { Red(); }\n")
        w("main", "module main;\nimport a;\nimport b;\nfunc foo() -> int { let Red: int = 1; return Red; }\n")
        return "main"
    if mode == "not-imported-varref":
        w("other", "module other;\nlet bar: int = 1;\n")
        w("main", "module main;\nfunc foo() -> int { let x: int = other::bar; return x; }\n")
        return "main"
    if mode == "ambiguous-varref":
        w("a", "module a;\nlet foo: int = 1;\n")
        w("b", "module b;\nlet foo: int = 2;\n")
        w("main", "module main;\nimport a;\nimport b;\nfunc bar() -> int { let x: int = foo; return x; }\n")
        return "main"
    if mode == "ambiguous-type-body":
        w("a", "module a;\nstruct T { v: int; }\n")
        w("b", "module b;\nstruct T { v: int; }\n")
        w("main", "module main;\nimport a;\nimport b;\nfunc foo() -> int { let x: T = 0; return 0; }\n")
        return "main"
    if mode == "not-imported-sizeof":
        w("other", "module other;\nstruct T { v: int; }\n")
        w("main", "module main;\nfunc foo() -> int { return sizeof(other::T); }\n")
        return "main"
    if mode == "ambiguous-sizeof":
        w("a", "module a;\nstruct T { v: int; }\n")
        w("b", "module b;\nstruct T { v: int; }\n")
        w("main", "module main;\nimport a;\nimport b;\nfunc foo() -> int { return sizeof(T); }\n")
        return "main"
    raise ValueError(f"unknown multi-module trigger: {mode}")


def stage_trigger_source(stage: str, code: str, oracle) -> str | None:
    if code == "TYP-0158":
        return "module main;\nfunc foo() -> int { let x: int = a::B::C::D; return 0; }\n"
    if stage == "l1":
        extra = {
            "LEX-0062": "0x",
            "LEX-0063": "0b",
            "LEX-0064": "0o",
            "LEX-0065": "1e",
            "LEX-0066": "1.0x",
            "LEX-0067": "1.0d",
            "LEX-0068": "123f",
            "TYP-0010": "module main;\nfunc foo(flag: bool) -> int { if (flag) { return 1; } }\n",
            "TYP-0244": "module main;\nimport dea;\nfunc foo() -> int { let f = sizeof; return 0; }\n",
            "TYP-0213": (
                "module main;\n"
                "unsafe func foo(i: int) -> int {\n"
                "    let value: int = 1;\n"
                "    return value[i];\n"
                "}\n"
            ),
            "TYP-0214": (
                "module main;\n"
                "extern func buf() -> int*;\n"
                "func foo(i: int) -> int { return buf()[i]; }\n"
            ),
            "TYP-0215": (
                "module main;\n"
                "extern func raw_bytes() -> void*;\n"
                "unsafe func foo(i: int) -> void {\n"
                "    let value = raw_bytes()[i];\n"
                "}\n"
            ),
            "PAR-0241": "module main; func main() -> int { case (42) { + => { return 1; } _ => { return 0; } } }",
            "PAR-0234": "module main; func main() -> int { case (42) { _ => { return 0; } 1 => { return 1; } } }",
            "PAR-0236": "module main; func main() -> int { case (42) { _ => { return 0; } _ => { return 1; } } }",
            "SIG-0201": "module main;\nconst A: int = B;\nconst B: int = A;\nfunc foo() -> int { return 0; }\n",
            "TYP-0106": "module main;\nstruct Point { x: int; y: int; }\nfunc foo() -> int {\nlet p: Point = Point(1, 2);\ncase (p) {\n_ => { return 0; }\n}\n}\n",
            "TYP-0107": "module main;\nfunc foo() -> int {\nlet x: int = 1;\ncase (x) {\n\"hello\" => { return 1; }\n_ => { return 0; }\n}\n}\n",
            "TYP-0108": "module main;\nfunc foo() -> int {\nlet x: int = 1;\ncase (x) {\n1 => { return 1; }\n1 => { return 1; }\n_ => { return 0; }\n}\n}\n",
            "TYP-0112": "module main;\nlet OK: int = 1;\nfunc foo(x: int) -> int {\ncase (x) {\nOK => { return 1; }\n_ => { return 0; }\n}\n}\n",
            "TYP-0113": "module main;\nstruct Point { x: int; }\nconst ORIGIN: Point = Point(0);\nfunc foo(x: int) -> int {\ncase (x) {\nORIGIN => { return 1; }\n_ => { return 0; }\n}\n}\n",
            "TYP-0815": "module main;\nlet N: int = 3;\nlet xs: int[N] = [1, 2, 3];\n",
            "TYP-0816": "module main;\nconst N: string = \"3\";\nlet xs: int[N] = [1, 2, 3];\n",
            "TYP-0817": "module main;\nconst N: int = 0;\nlet xs: int[N] = [];\n",
        }.get(code)
        if extra is not None:
            return extra
    return (
        oracle.LEX_TRIGGERS.get(code)
        or oracle.PAR_TRIGGERS.get(code)
        or oracle.RES_TRIGGERS.get(code)
        or oracle.SIG_TRIGGERS.get(code)
        or oracle.TYP_TRIGGERS.get(code)
    )


def all_codes(stage: str, oracle) -> list[str]:
    codes: list[str] = []
    for family_codes in oracle.DIAGNOSTIC_CODE_FAMILIES.values():
        codes.extend(family_codes)
    if stage == "l1":
        codes.extend([
            "LEX-0062", "LEX-0063", "LEX-0064", "LEX-0065", "LEX-0066", "LEX-0067", "LEX-0068",
            "SIG-0201",
            "TYP-0112", "TYP-0113", "TYP-0213", "TYP-0214", "TYP-0215", "TYP-0244",
            "TYP-0815", "TYP-0816", "TYP-0817",
        ])
    skip = set(oracle.CLI_ONLY_CODES) | set(oracle.INTERNAL_CODES)
    if stage == "l1":
        skip.add("LEX-0060")
        skip.add("PAR-0226")
        skip.add("PAR-0237")
        skip.add("PAR-0242")
        skip.add("PAR-0243")
        skip.add("PAR-9401")
        skip.add("TYP-0212")
    return [code for code in codes if code not in skip]


def run_compiler(stage: str, compiler: Path, root: Path, target: str) -> tuple[int, str, set[str]]:
    env = os.environ.copy()
    if stage == "l0":
        cwd = REPO_ROOT / "l0"
        env["L0_HOME"] = str(cwd / "compiler")
    else:
        cwd = REPO_ROOT / "l1"
        env["L0_HOME"] = str(REPO_ROOT / "l0" / "compiler")
        env["L1_HOME"] = str(cwd / "compiler")
    completed = subprocess.run(
        [*wrapper_command(compiler), "--project-root", str(root), "--check", target],
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
    return completed.returncode, completed.stdout, set(CODE_RE.findall(completed.stdout))


def check_stage(stage: str, compiler: Path) -> int:
    oracle = load_oracle()
    failures: list[str] = []
    for code in all_codes(stage, oracle):
        with tempfile.TemporaryDirectory(prefix=f"dea-{stage}-diag-") as tmp:
            root = Path(tmp)
            if code in oracle.DRV_TRIGGERS or code in oracle.MULTI_MODULE_TRIGGERS:
                mode = oracle.DRV_TRIGGERS.get(code) or oracle.MULTI_MODULE_TRIGGERS[code]
                target = write_multi_module(root, stage, mode)
            else:
                source = stage_trigger_source(stage, code, oracle)
                if source is None:
                    failures.append(f"{code}: missing parity trigger")
                    continue
                (root / f"main.{stage}").write_text(source, encoding="utf-8")
                target = "main"
            _, output, emitted = run_compiler(stage, compiler, root, target)
            if code not in emitted:
                first = output.splitlines()[0] if output.splitlines() else "<no output>"
                failures.append(f"{code}: emitted {sorted(emitted)}; first output: {first}")
    if failures:
        print(f"{stage}: diagnostic parity failures ({len(failures)})")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"{stage}: diagnostic parity passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["l0", "l1"], required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    return check_stage(args.stage, args.compiler.resolve(strict=True))


if __name__ == "__main__":
    raise SystemExit(main())
