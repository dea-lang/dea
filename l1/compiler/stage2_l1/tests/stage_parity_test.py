#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Compare observable Stage 1 and Stage 2 behavior using identical inputs."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile

L1_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(L1_ROOT / "compiler/stage1_l0/tests"))
from support.driver_inputs import native_driver_args


def main() -> int:
    """Exercise frontend, diagnostics, CLI, native output, and exit-status parity."""
    build = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build.is_absolute():
        build = L1_ROOT / build
    oracle = Path(os.environ.get("L1_TEST_ORACLE", str(build / "bin/l1c-stage1")))
    subject = Path(os.environ.get("L1_TEST_COMPILER", str(build / "bin/l1c-stage2")))
    root = L1_ROOT / "compiler/stage1_l0/tests/fixtures/driver"

    def invoke(compiler: Path, args: list[str]) -> tuple[int, bytes, bytes]:
        """Capture only documented observable output; preserve every diagnostic byte."""
        if os.name == "nt" and compiler.suffix != ".native" and compiler.with_suffix(".cmd").exists():
            compiler = compiler.with_suffix(".cmd")
        result = subprocess.run([str(compiler), *args], cwd=L1_ROOT, capture_output=True)
        return result.returncode, result.stdout, result.stderr

    for args in (["--help"], ["--version"], ["--unknown-stage-parity-option"]):
        left, right = invoke(oracle, args), invoke(subject, args)
        left = tuple(v.replace(b"(Stage 1)", b"(Stage 2)") if isinstance(v, bytes) else v for v in left)
        assert left == right, (args, left, right)
    for module in ("ok_main", "invalid_chars", "mismatch", "dup_import_main", "const_main", "variadic_main", "real_basic_main"):
        for mode in ("--check", "--tok", "--ast", "--type", "--sym"):
            args = [mode, "--project-root", str(root), module]
            left, right = invoke(oracle, args), invoke(subject, args)
            assert left == right, (args, left, right)
    for module in ("ok_main", "exit_seven", "real_basic_main", "const_main", "variadic_main", "pointer_identity_main"):
        results = []
        for compiler in (oracle, subject):
            results.append(invoke(compiler, ["--run", *native_driver_args(compiler), "--project-root", str(root), module]))
        assert results[0] == results[1], (module, results)
    # One module path keeps module identity and interface fingerprints comparable.
    with tempfile.TemporaryDirectory(prefix="l1-bigint-parity-") as directory:
        source = Path(directory) / "phase1_bigints.l1"
        spellings = (
            ("-9223372036854775808", "18446744073709551615", "-0000"),
            ("-0x8000000000000000", "0x0000ffffffffffffffff", "-0x0000"),
            ("-0o1000000000000000000000", "0o0001777777777777777777777", "-0o0000"),
            ("-0b1" + "0" * 63, "0b000" + "1" * 64, "-0b0000"),
        )
        canonical = None
        for minimum, maximum, zero in spellings:
            source.write_text(
                "module phase1_bigints;\nexport *;\n"
                f"const minimum: long = {minimum};\n"
                f"const maximum: ulong = {maximum};\n"
                f"const zero: long = {zero};\n"
            )
            args = ["--emit-interface", str(source)]
            left, right = invoke(oracle, args), invoke(subject, args)
            assert left == right, (args, minimum, maximum, left, right)
            assert left[0] == 0 and left[1], (args, left)
            if canonical is None:
                canonical = left
            assert left == canonical, (minimum, maximum, left, canonical)
        for literal in (
            "18446744073709551616", "-9223372036854775809",
            "0x10000000000000000", "-0x8000000000000001",
            "0o2000000000000000000000", "-0o1000000000000000000001",
            "0b1" + "0" * 64, "-0b1" + "0" * 62 + "1",
            "0b102", "0o8", "0xg",
        ):
            type_name = "long" if literal.startswith("-") else "ulong"
            source.write_text(
                "module phase1_bigints;\nexport *;\n"
                f"const invalid: {type_name} = {literal};\n"
            )
            for mode in ("--check", "--emit-interface"):
                args = [mode, str(source)]
                left, right = invoke(oracle, args), invoke(subject, args)
                assert left == right, (args, literal, left, right)
                assert left[0] != 0 and left[2], (args, literal, left)
    print("stage_parity_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
