#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native Stage 2 negation boundaries with capability-probed UBSan coverage."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from tool_test_common import resolve_host_c_compiler, resolve_tool


L0_ROOT = Path(__file__).resolve().parents[3]
RUNTIME = L0_ROOT / "compiler/shared/runtime"
SANITIZER_FLAGS = ("-fsanitize=undefined", "-fno-sanitize-recover=all")
SOURCE = """
module negation;
let calls: int = 0;
let minimum: int = -2147483648;
func negate(value: int) -> int { return -value; }
func negate_byte(value: byte) -> int { return -value; }
func next_value() -> int { calls = calls + 1; return 7; }
func single() -> int { return -next_value(); }
func count() -> int { return calls; }
func minimum_literal() -> int { return minimum; }
func invert(value: bool) -> bool { return !value; }
"""
HARNESS = r"""
#include "dea_rt.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
l0_int l0_negation_negate(l0_int);
l0_int l0_negation_negate_byte(l0_byte);
l0_int l0_negation_single(void);
l0_int l0_negation_count(void);
l0_int l0_negation_minimum_literal(void);
l0_bool l0_negation_invert(l0_bool);

/**
 * Exercise separately compiled Dea functions with runtime inputs.
 *
 * @param argc Number of arguments.
 * @param argv Optional signed integer to negate.
 * @return Zero after a correct result, otherwise a failed assertion number.
 */
int main(int argc, char **argv) {
    if (argc > 1) {
        l0_int value = (l0_int)strtol(argv[1], NULL, 10);
        printf("%" PRId32 "\n", l0_negation_negate(value));
        return 0;
    }
    for (int value = 0; value <= 255; ++value) {
        if (l0_negation_negate_byte((l0_byte)value) != -value) {
            return 1;
        }
    }
    if (l0_negation_single() != -7 || l0_negation_count() != 1) {
        return 2;
    }
    if (l0_negation_minimum_literal() != INT32_MIN) {
        return 3;
    }
    if (!l0_negation_invert(0) || l0_negation_invert(1)) {
        return 4;
    }
    puts("semantic checks: PASS");
    return 0;
}
"""


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Capture a bounded compiler or native-program invocation.

    Args:
        command: Executable and arguments without shell interpolation.

    Returns:
        Completed process with decoded output and the actual exit status.

    Raises:
        subprocess.TimeoutExpired: The command exceeds the invocation timeout.
    """
    return subprocess.run(
        command, cwd=L0_ROOT, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
    )


def require_success(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Require successful execution of one bounded command.

    Args:
        command: Executable and arguments to invoke.

    Returns:
        Successful completed process.

    Raises:
        AssertionError: The command exits unsuccessfully.
        subprocess.TimeoutExpired: The command exceeds the invocation timeout.
    """
    result = run(command)
    assert result.returncode == 0, (command, result.stdout, result.stderr)
    return result


def supports_ubsan(work: Path, cc: str, cflags: list[str]) -> bool:
    """Require a real signed-overflow diagnostic before claiming UBSan coverage.

    Args:
        work: Temporary directory for the compiler capability probe.
        cc: Explicitly selected host compiler.
        cflags: Selected compiler flags, preserving native path spelling.

    Returns:
        Whether the selected compiler detects the intentional negation overflow.

    Raises:
        subprocess.TimeoutExpired: Compilation or execution exceeds the timeout.
    """
    source = work / "ubsan_probe.c"
    executable = work / ("ubsan_probe.exe" if os.name == "nt" else "ubsan_probe")
    source.write_text(
        """#include <stdint.h>

/**
 * Trigger intentional signed-negation overflow to detect sanitizer support.
 *
 * @return No defined value because the probe deliberately triggers overflow.
 */
int main(void) { volatile int32_t value = INT32_MIN; return -value; }
""",
        encoding="utf-8",
    )
    compiled = run([cc, *cflags, "-std=c99", *SANITIZER_FLAGS, str(source), "-o", str(executable)])
    if compiled.returncode != 0:
        return False
    result = run([str(executable)])
    return result.returncode != 0 and "runtime error:" in result.stderr and "negation" in result.stderr


def require_matrix(compiler: list[str], work: Path, cc: str) -> None:
    """Check runtime integer/byte negation through a selected L0 compiler.

    Args:
        compiler: L0 compiler invocation, normally the native Stage 2 launcher.
        work: Temporary directory for generated C and separate native callers.
        cc: Explicitly selected host compiler.

    Raises:
        AssertionError: Generation, native compilation, or a semantic check fails.
        subprocess.TimeoutExpired: Compilation or execution exceeds the timeout.
    """
    (work / "negation.l0").write_text(SOURCE, encoding="utf-8")
    harness = work / "harness.c"
    harness.write_text(HARNESS, encoding="utf-8")
    cflags = os.environ.get("L0_CFLAGS", "").split()
    sanitized = supports_ubsan(work, cc, cflags)
    if not sanitized and os.environ.get("L0_REQUIRE_UBSAN") == "1":
        raise AssertionError("selected compiler does not provide working UBSan negation coverage")
    print("negation_runtime_test: UBSan " + ("enabled" if sanitized else "unavailable; native checks retained"))
    for mode, mode_flags in (("checked", []), ("basic", ["--check-basic"]), ("unchecked", ["--unchecked"])):
        generated = work / (mode + ".c")
        require_success([
            *compiler, "--gen", "--no-line-directives", *mode_flags,
            "--project-root", str(work), "-o", str(generated), "negation",
        ])
        assert "return (_rt_isub(0, value));" in generated.read_text(encoding="utf-8")
        for label, extra in (("native", ()), ("ubsan", SANITIZER_FLAGS)):
            if label == "ubsan" and not sanitized:
                continue
            executable = work / (f"{mode}-{label}" + (".exe" if os.name == "nt" else ""))
            require_success([
                cc, *cflags, "-std=c99", "-O1", *extra, "-I", str(RUNTIME),
                str(generated), str(harness), "-o", str(executable),
            ])
            result = require_success([str(executable)])
            assert result.stdout == "semantic checks: PASS\n" and not result.stderr, result
            for value in (-2147483647, -1, 0, 1, 2147483647):
                result = require_success([str(executable), str(value)])
                assert result.stdout == str(-value) + "\n" and not result.stderr, result
            failed = run([str(executable), "-2147483648"])
            assert failed.returncode != 0, failed
            assert "Software Failure: integer subtraction overflow" in failed.stderr, failed
            assert "runtime error:" not in failed.stderr, failed
            print(f"negation_runtime_test: {mode}/{label} PASS")


def main() -> int:
    """Validate the repo-local Stage 2 compiler's runtime negation contract.

    Returns:
        Zero after all applicable native and sanitizer checks pass.

    Raises:
        AssertionError: A compiler is unavailable or a validation check fails.
        subprocess.TimeoutExpired: Compilation or execution exceeds the timeout.
    """
    build = Path(os.environ.get("DEA_BUILD_DIR", "build/dea"))
    if not build.is_absolute():
        build = L0_ROOT / build
    compiler = resolve_tool(build / "bin", "l0c-stage2")
    cc = resolve_host_c_compiler(dict(os.environ))
    assert cc is not None, "no host C compiler available"
    with tempfile.TemporaryDirectory(prefix="l0-negation-") as temporary:
        require_matrix([str(compiler)], Path(temporary), cc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
