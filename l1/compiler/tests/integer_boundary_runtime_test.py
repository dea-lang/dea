#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise generated integer boundaries separately from constant evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from l1c_compile_only_test import stage1_compiler, resolve_host_c_compiler


LEVEL_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = LEVEL_ROOT / "compiler/shared/runtime"
FIXTURES = Path(__file__).resolve().parent / "fixtures/integer_boundary"
SANITIZER_FLAGS = ("-fsanitize=undefined", "-fno-sanitize-recover=all")
SANITIZER_REPORT = re.compile(r"runtime error:|UndefinedBehaviorSanitizer", re.IGNORECASE)
MODES = (
    ("default", (), ()),
    ("basic", ("--check-basic",), ("-DDEA_RT_CHECK_BASIC",)),
    ("unchecked", ("--unchecked",), ("-DDEA_RT_UNCHECKED",)),
)


@dataclass(frozen=True)
class Case:
    """One native call with a Python-computed result or required Dea failure."""

    operation: str
    left: int
    right: int = 0
    expected: int | None = None
    error: str | None = None


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Capture one compiler or native process without interpreting failure codes.

    Args:
        command: Executable and structured arguments.
        cwd: Per-case working directory.
        env: Optional complete environment for sanitizer execution.

    Returns:
        Captured process result.

    Raises:
        subprocess.TimeoutExpired: The process exceeds the bounded test timeout.
    """
    return subprocess.run(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=240,
    )


def require_success(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Require a successful tool invocation and retain useful failure diagnostics.

    Args:
        command: Executable and structured arguments.
        cwd: Per-case working directory.

    Returns:
        Successful captured process result.

    Raises:
        AssertionError: The tool failed or emitted a sanitizer report.
    """
    result = run(command, cwd=cwd)
    assert result.returncode == 0 and not SANITIZER_REPORT.search(result.stderr), (
        command, result.returncode, result.stdout, result.stderr,
    )
    return result


def signatures() -> dict[str, tuple[str, tuple[str, ...]]]:
    """Return fixture signatures for a header naming the generated functions.

    Returns:
        Source function names mapped to return and parameter types.
    """
    result = {
        "neg_" + kind: (kind, (kind,))
        for kind in ("tiny", "short", "int", "long", "byte", "ushort", "uint", "ulong", "float", "double")
    }
    result.update({
        direction + "_" + kind: (kind, (kind, kind))
        for kind in ("int", "uint", "long", "ulong")
        for direction in ("left", "right")
    })
    result.update({
        "left_mixed_uint_int": ("long", ("uint", "int")),
        "right_mixed_uint_int": ("long", ("uint", "int")),
        "left_narrow": ("int", ("tiny", "short")),
        "left_narrow_unsigned": ("int", ("byte", "ushort")),
        "left_mixed_ulong_byte": ("ulong", ("ulong", "byte")),
        "left_once": ("int", ("int", "int")),
        "right_once": ("int", ("int", "int")),
        "neg_once": ("int", ("int",)),
    })
    return result


def write_names(generated: Path, destination: Path) -> None:
    """Name generated functions without duplicating type-component ABI spellings.

    Args:
        generated: Complete standalone C from the owning compiler.
        destination: Temporary C header included only by the separate caller.

    Raises:
        AssertionError: A fixture function is absent or ambiguous in generated C.
    """
    text = generated.read_text(encoding="utf-8")
    lines = ["/* Generated test-only declarations for independently compiled calls. */"]
    for name, (result, arguments) in signatures().items():
        pattern = rf"\b__deaM6boundsN{len(name)}{re.escape(name)}F[0-9A-Za-z_]+\b"
        symbols = set(re.findall(pattern, text))
        assert len(symbols) == 1, (name, symbols)
        lines.append(f"#define {name} {symbols.pop()}")
        lines.append(f"dea_{result} {name}({', '.join('dea_' + arg for arg in arguments)});")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cases() -> list[Case]:
    """Construct mathematical expectations without executing boundary C arithmetic.

    Returns:
        Runtime negation, shift, and normalization cases.
    """
    result: list[Case] = []
    for kind, width in (("tiny", 8), ("short", 16), ("int", 32), ("long", 64)):
        low, high = -(1 << (width - 1)), (1 << (width - 1)) - 1
        for value in (low, low + 1, -1, 0, 1, high):
            result.append(Case("neg_" + kind, value, expected=-value if value != low else None,
                               error="overflow" if value == low else None))
    # Unsigned unary behavior is preserved by the signed-negation repair.
    for kind, width in (("byte", 8), ("ushort", 16), ("uint", 32), ("ulong", 64)):
        mask = (1 << width) - 1
        for value in (0, 1, mask):
            result.append(Case("neg_" + kind, value, expected=(-value) & mask))
    for kind, width in (("int", 32), ("long", 64)):
        low, high = -(1 << (width - 1)), (1 << (width - 1)) - 1
        for direction in ("left", "right"):
            for value in (low, low + 1, -1, 0, 1, high):
                for count in (-1, 0, width - 1, width, width + 1):
                    name = direction + "_" + kind
                    if not 0 <= count < width:
                        result.append(Case(name, value, count, error="shift"))
                    else:
                        answer = value << count if direction == "left" else value >> count
                        result.append(Case(name, value, count, expected=answer if low <= answer <= high else None,
                                           error=None if low <= answer <= high else "overflow"))
    for kind, width in (("uint", 32), ("ulong", 64)):
        mask = (1 << width) - 1
        for direction in ("left", "right"):
            for value in (0, 1, 1 << (width - 1), mask):
                # The all-ones count is the unsigned-domain analogue of a converted -1.
                for count in (0, width - 1, width, width + 1, mask):
                    name = direction + "_" + kind
                    if count >= width:
                        result.append(Case(name, value, count, error="shift"))
                    else:
                        answer = ((value << count) & mask) if direction == "left" else value >> count
                        result.append(Case(name, value, count, expected=answer))
    result.extend((
        Case("left_mixed_uint_int", (1 << 32) - 1, 31, expected=((1 << 32) - 1) << 31),
        Case("left_mixed_uint_int", 1, 32, expected=1 << 32),
        Case("left_mixed_uint_int", 1, -1, error="shift"),
        Case("left_mixed_uint_int", (1 << 32) - 1, 32, error="overflow"),
        Case("right_mixed_uint_int", (1 << 32) - 1, 32, expected=0),
        Case("left_narrow", -1, 31, expected=-(1 << 31)),
        Case("left_narrow", 1, 30, expected=1 << 30),
        Case("left_narrow", 1, 31, error="overflow"),
        Case("left_narrow", 1, -1, error="shift"),
        Case("left_narrow", 1, 32, error="shift"),
        Case("left_narrow_unsigned", 255, 23, expected=255 << 23),
        Case("left_narrow_unsigned", 255, 24, error="overflow"),
        Case("left_narrow_unsigned", 1, 32, error="shift"),
        Case("left_mixed_ulong_byte", 1, 63, expected=1 << 63),
        Case("left_mixed_ulong_byte", (1 << 64) - 1, 63, expected=1 << 63),
        Case("left_mixed_ulong_byte", 1, 64, error="shift"),
    ))
    return result


def check_constants(compiler: Path, work: Path) -> None:
    """Keep the existing constant-evaluation subset distinct from runtime semantics.

    Args:
        compiler: Owning level's selected compiler.
        work: Temporary output directory.

    Raises:
        AssertionError: A supported constant fails or an invalid constant is accepted.
    """
    common = [str(compiler), "--check", "--no-managed-stdlib", "--project-root", str(FIXTURES)]
    require_success([*common, "constants_valid"], cwd=work)
    for name in ("constants_invalid_negation", "constants_invalid_shift"):
        result = run([*common, name], cwd=work)
        assert result.returncode != 0 and "error:" in result.stderr, (name, result)
    print("L1 integer boundaries: constant checks PASS", flush=True)


def compile_matrix(
    compiler: Path, cc: str, cflags: list[str], work: Path, instrumentation: tuple[str, ...],
) -> None:
    """Compile and run each runtime mode with separately compiled test operands.

    Args:
        compiler: Owning level's selected compiler.
        cc: Explicitly selected host C compiler.
        cflags: Host flags split with the compiler's whitespace word convention.
        work: Temporary root for this instrumentation selection.
        instrumentation: Empty for ordinary native execution, or UBSan flags.

    Raises:
        AssertionError: Generation, compilation, linking, or a runtime expectation fails.
    """
    work.mkdir()
    for mode, cli_flags, defines in MODES:
        directory = work / mode
        directory.mkdir()
        generated = directory / "bounds.c"
        require_success([
            str(compiler), "--gen", "--no-managed-stdlib", "--no-line-directives", *cli_flags,
            "--project-root", str(FIXTURES), "-o", str(generated), "bounds",
        ], cwd=directory)
        write_names(generated, directory / "probe_names.h")
        flags = [*cflags, "-std=c99", "-O1", *instrumentation, *defines]
        includes = ["-I", str(directory), "-I", str(RUNTIME_ROOT / "include"),
                    "-I", str(RUNTIME_ROOT / "internal")]
        objects = []
        # Every runtime unit is instrumented; a prebuilt archive would hide helper UB.
        sources = [generated, FIXTURES / "probe.c", *sorted((RUNTIME_ROOT / "src").glob("*.c"))]
        for number, source in enumerate(sources):
            output = directory / f"unit-{number}.o"
            require_success([cc, *flags, *includes, "-c", str(source), "-o", str(output)], cwd=directory)
            objects.append(str(output))
        executable = directory / ("bounds.exe" if os.name == "nt" else "bounds")
        # TinyCC's macOS signing helper requires a relative output in paths with spaces.
        require_success([cc, *flags, *objects, "-lm", "-o", executable.name], cwd=directory)
        env = os.environ.copy()
        if instrumentation:
            env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=0"
        for case in cases():
            arguments = [str(executable), case.operation, str(case.left), str(case.right)]
            result = run(arguments, cwd=directory, env=env)
            assert not SANITIZER_REPORT.search(result.stderr), (mode, case, result.stderr)
            if case.error is not None:
                assert result.returncode != 0 and "Software Failure:" in result.stderr and case.error in result.stderr, (
                    mode, case, result.returncode, result.stdout, result.stderr,
                )
            else:
                assert result.returncode == 0 and result.stdout == f"{case.expected}\n", (
                    mode, case, result.returncode, result.stdout, result.stderr,
                )
        for operation in ("once", "float"):
            result = run([str(executable), operation], cwd=directory, env=env)
            assert result.returncode == 0 and result.stdout == "ok\n" and not SANITIZER_REPORT.search(result.stderr), (
                mode, operation, result.returncode, result.stdout, result.stderr,
            )
        label = "UBSan" if instrumentation else "native"
        print(f"L1 integer boundaries: {label} {mode} PASS ({len(cases())} cases plus evaluation/float checks)", flush=True)


def ubsan_available(cc: str, cflags: list[str], work: Path) -> bool:
    """Require an actual sanitizer finding from a deliberate signed-overflow probe.

    Args:
        cc: The same selected compiler used by ordinary native coverage.
        cflags: Explicit native compiler flags.
        work: Temporary root retaining capability diagnostics on a later failure.

    Returns:
        Whether both valid execution and deliberate UB detection work.
    """
    source = work / "ubsan-capability.c"
    source.write_text(r'''
#include <stdint.h>
#include <limits.h>

/**
 * Demonstrate working signed-overflow instrumentation.
 *
 * @param argc Any extra argument selects the defined control run.
 * @param argv Unused argument vector.
 * @return Zero for the control; the deliberate fault must terminate in UBSan.
 */
int main(int argc, char **argv) {
    volatile int32_t value = INT32_MAX;
    (void)argv;
    if (argc > 1) return 0;
    return value + 1;
}
''', encoding="utf-8")
    executable = work / ("ubsan-capability.exe" if os.name == "nt" else "ubsan-capability")
    compiled = run([cc, *cflags, "-std=c99", "-O1", *SANITIZER_FLAGS, str(source), "-o", executable.name], cwd=work)
    (work / "ubsan-capability-build.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    if compiled.returncode != 0:
        print("L1 integer boundaries: UBSan SKIP (selected compiler cannot build the capability probe)", flush=True)
        return False
    control = run([str(executable), "control"], cwd=work)
    fault = run([str(executable)], cwd=work)
    (work / "ubsan-capability-run.log").write_text(control.stderr + fault.stderr, encoding="utf-8")
    if control.returncode != 0 or fault.returncode == 0 or not SANITIZER_REPORT.search(fault.stderr):
        print("L1 integer boundaries: UBSan SKIP (working instrumentation was not demonstrated)", flush=True)
        return False
    print("L1 integer boundaries: UBSan capability PASS (deliberate overflow detected)", flush=True)
    return True


def main() -> int:
    """Run mandatory native checks and capability-gated sanitizer coverage.

    Returns:
        Zero when every applicable check succeeds.

    Raises:
        AssertionError: A semantic or sanitizer regression fails; artifacts are retained.
    """
    compiler = stage1_compiler()
    cc = resolve_host_c_compiler()
    # Preserve native backslashes exactly as the compiler's word splitter does.
    # Disable optional LTO so the caller remains independent of generated code.
    cflags = [flag for flag in os.environ.get("L1_CFLAGS", "").split() if not flag.startswith("-flto")]
    work = Path(tempfile.mkdtemp(prefix="l1 integer boundaries "))
    try:
        banner = require_success([cc, "--version"], cwd=work).stdout.splitlines()
        print(f"L1 integer boundary compiler: {cc}: {banner[0] if banner else 'version unavailable'}", flush=True)
        check_constants(compiler, work)
        compile_matrix(compiler, cc, cflags, work / "native", ())
        if ubsan_available(cc, cflags, work):
            compile_matrix(compiler, cc, cflags, work / "ubsan", SANITIZER_FLAGS)
    except BaseException:
        print(f"L1 integer boundaries: retained artifacts at {work}", flush=True)
        raise
    shutil.rmtree(work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
