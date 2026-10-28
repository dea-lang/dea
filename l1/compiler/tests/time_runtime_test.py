#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Wide time ABI, deterministic scheduling, native adapters, and traced L1 coverage."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

from os_runtime_test import (
    L1_ROOT, RUNTIME_ROOT, RUNTIME_SOURCES, compiler_path,
    require_success, runtime_c_compiler,
)
from support.driver_inputs import native_driver_args


FIXTURES = L1_ROOT / "compiler/tests/fixtures/time_runtime"


def require_trace(work: Path, name: str, trace_text: str) -> None:
    """Analyze an actual generated L1 program's independent ARC/memory trace.

    Args:
        work: Temporary artifact directory.
        name: Trace artifact basename.
        trace_text: Captured stderr from the generated program.

    Raises:
        AssertionError: Trace events are missing or the ownership checker fails.
    """
    trace = work / f"{name}.trace"
    trace.write_text(trace_text, encoding="utf-8")
    report = require_success([
        sys.executable, str(L1_ROOT / "compiler/scripts/check_trace_log.py"),
        str(trace), "--triage", "--max-details", "5",
    ], timeout=120)
    assert "leaked_object_ptrs=0" in report.stdout, report.stdout
    assert "leaked_string_ptrs=0" in report.stdout, report.stdout
    assert "[l0][arc]" in trace_text, "missing ARC events"
    # The pure scalar injected transport needs no object allocation. The real
    # clock fixture allocates RtTimeParts through the legacy nullable readers.
    if name == "time-real-traced":
        assert "[l0][mem]" in trace_text, "missing allocation events"


def require_real_host(work: Path, cc: str) -> None:
    """Build real-host width, calendar, arithmetic, and short-wait L1 fixtures.

    Args:
        work: Temporary artifact directory.
        cc: Explicit selected C compiler.

    Raises:
        AssertionError: Compilation or a generated time assertion fails.
    """
    compiler = compiler_path()
    for name, flags in (
        ("checked", []), ("unchecked", ["--unchecked"]),
        ("traced", ["--trace-arc", "--trace-memory"]),
    ):
        executable = work / (f"time-real-{name}" + (".exe" if os.name == "nt" else ""))
        require_success([
            str(compiler), "--project-root", str(FIXTURES),
            "--c-compiler", cc, *native_driver_args(compiler, cc),
            *flags, "--build", "time_main", "-o", str(executable),
        ], timeout=240)
        completed = require_success([str(executable)], timeout=60)
        assert completed.stdout == "time_main: PASS\n", completed.stdout
        if name == "traced":
            require_trace(work, f"time-real-{name}", completed.stderr)
        else:
            assert completed.stderr == "", completed.stderr


def require_injected_library(work: Path, cc: str) -> None:
    """Run public L1 scheduling over injected runtime reads, waits, and cleanup.

    Args:
        work: Temporary artifact directory.
        cc: Explicit selected C compiler.

    Raises:
        AssertionError: A scheduling result, native error, or trace is incorrect.
    """
    library = work / "injected-runtime"
    library.mkdir()
    archiver = shutil.which("ar")
    assert archiver, "time failure probes require an archiver"
    compiler = compiler_path()
    for name, defines, flags in (
        ("checked", [], []),
        ("traced", ["-DDEA_TRACE_ARC", "-DDEA_TRACE_MEMORY"], ["--trace-arc", "--trace-memory"]),
    ):
        objects = []
        for source_name in (*RUNTIME_SOURCES, *( ["dea_rt_trace.c"] if name == "traced" else []), "time_faults.c"):
            source = FIXTURES / source_name if source_name == "time_faults.c" else RUNTIME_ROOT / "src" / source_name
            obj = library / f"{name}-{source_name}.o"
            require_success([
                cc, "-std=c99", *defines, "-DDEA_TIME_BOUNDED_WAIT=1",
                f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
                *( ["-include", str(FIXTURES / "time_faults.h")] if source_name == "dea_rt_time.c" else []),
                "-c", str(source), "-o", str(obj),
            ], timeout=120)
            objects.append(str(obj))
        archive = "libdea_rt_traced.a" if name == "traced" else "libdea_rt.a"
        require_success([archiver, "rcs", str(library / archive), *objects], timeout=120)
        executable = work / (f"time-injected-{name}" + (".exe" if os.name == "nt" else ""))
        require_success([
            str(compiler), "--project-root", str(FIXTURES), "--c-compiler", cc,
            "--no-managed-stdlib", "--sys-root", str(L1_ROOT / "compiler/shared/l1/stdlib"),
            "--runtime-include", str(RUNTIME_ROOT / "include"), "--runtime-lib", str(library),
            "--no-auto-prepare", *flags, "--build", "time_failure_main", "-o", str(executable),
        ], timeout=240)
        completed = require_success([str(executable)], timeout=60)
        assert completed.stdout == "time_failure_main: PASS\n", completed.stdout
        if name == "traced":
            require_trace(work, "time-injected-traced", completed.stderr)
        else:
            assert completed.stderr == "", completed.stderr


def require_native_adapters(work: Path, cc: str) -> None:
    """Exercise actual platform adapter code with deterministic native API hooks.

    Args:
        work: Temporary artifact directory.
        cc: Explicit selected C compiler.

    Raises:
        AssertionError: A native wait, conversion, or error invariant fails.
    """
    for bounded in ((0, 1) if sys.platform.startswith("linux") else (1,)):
        executable = work / (f"time-native-{bounded}" + (".exe" if os.name == "nt" else ""))
        require_success([
            cc, "-std=c99", f"-DDEA_TIME_BOUNDED_WAIT={bounded}",
            f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'internal'}",
            f"-I{RUNTIME_ROOT / 'src'}", str(FIXTURES / "native_probe.c"),
            *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES if name != "dea_rt_time.c"),
            "-lm", "-o", str(executable),
        ], timeout=120)
        completed = require_success([str(executable)], timeout=60)
        print(completed.stdout, end="")


def time_conversion_bodies() -> str:
    """Extract the two real conversion definitions for synthetic native widths.

    Returns:
        Unmodified production helper definitions, without their surrounding TU.

    Raises:
        AssertionError: A named conversion definition is missing or incomplete.
    """
    source = (RUNTIME_ROOT / "src/dea_rt_time.c").read_text(encoding="utf-8")
    definitions = []
    for name in ("_rt_time_to_dea_long_sec", "_rt_time_to_time_t"):
        start = source.index(f"dea_bool {name}(")
        opening = source.index("{", start)
        depth = 1
        end = opening + 1
        while depth and end < len(source):
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        assert depth == 0, f"incomplete conversion definition: {name}"
        definitions.append(source[start:end])
    return "\n\n".join(definitions)


def require_time_t_widths(work: Path, cc: str) -> None:
    """Check actual conversion code against signed/unsigned 32/64-bit time types.

    Args:
        work: Temporary artifact directory.
        cc: Explicit selected C compiler.

    Raises:
        AssertionError: Conversion truncates or modifies output after failure.
    """
    bodies = time_conversion_bodies()
    for native_type in ("int32_t", "uint32_t", "int64_t", "uint64_t"):
        source = work / f"time-width-{native_type}.c"
        source.write_text(
            '#include <stdint.h>\n#include <inttypes.h>\n#include <limits.h>\n'
            'typedef uint8_t dea_bool;\ntypedef int64_t dea_long;\n'
            f"#define time_t {native_type}\n" + bodies + r'''
#define REQUIRE(test) do { if (!(test)) return __LINE__; } while (0)
int main(void) {
    dea_long converted = 17;
    time_t native = 17;
    REQUIRE(_rt_time_to_time_t(0, &native) && native == 0);
    REQUIRE(_rt_time_to_dea_long_sec(0, &converted) && converted == 0);
    REQUIRE(_rt_time_to_time_t(2147483647LL, &native));
    REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == 2147483647LL);
    if ((time_t)-1 < 0) {
        REQUIRE(_rt_time_to_time_t(-1, &native) && native == (time_t)-1);
        REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == -1);
    } else {
        native = 17;
        REQUIRE(!_rt_time_to_time_t(-1, &native) && native == 17);
    }
    if (sizeof(time_t) == 4) {
        native = 17;
        REQUIRE(!_rt_time_to_time_t(INT64_MAX, &native) && native == 17);
        REQUIRE(!_rt_time_to_time_t(INT64_MIN, &native) && native == 17);
        if ((time_t)-1 < 0) {
            REQUIRE(!_rt_time_to_time_t(2147483648LL, &native) && native == 17);
            REQUIRE(_rt_time_to_time_t(-2147483648LL, &native));
            REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == -2147483648LL);
        } else {
            REQUIRE(_rt_time_to_time_t(4294967295LL, &native));
            REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == 4294967295LL);
            native = 17;
            REQUIRE(!_rt_time_to_time_t(4294967296LL, &native) && native == 17);
        }
    } else {
        REQUIRE(_rt_time_to_time_t(INT64_MAX, &native));
        REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == INT64_MAX);
        if ((time_t)-1 < 0) {
            REQUIRE(_rt_time_to_time_t(INT64_MIN, &native));
            REQUIRE(_rt_time_to_dea_long_sec(native, &converted) && converted == INT64_MIN);
        } else {
            converted = 17;
            REQUIRE(!_rt_time_to_dea_long_sec((time_t)UINT64_MAX, &converted) && converted == 17);
        }
    }
    return 0;
}
''', encoding="utf-8",
        )
        executable = source.with_suffix(".exe" if os.name == "nt" else "")
        require_success([
            cc, "-std=c99", f"-I{RUNTIME_ROOT / 'include'}", str(source), "-o", str(executable),
        ], timeout=120)
        require_success([str(executable)], timeout=60)
    print("simulated signed/unsigned 32/64-bit time_t conversions: PASS")


def main() -> int:
    """Verify time ABI and scheduling through native and generated L1 consumers.

    Returns:
        Zero after all clock, scheduling, conversion, and ownership checks pass.

    Raises:
        AssertionError: A compiler, runtime, or trace invariant fails.
    """
    cc = runtime_c_compiler()
    version = require_success([cc, "--version"]).stdout.splitlines()[0]
    print(f"Time runtime compiler: {cc}: {version}", flush=True)
    with tempfile.TemporaryDirectory(prefix="l1-time-") as temporary:
        work = Path(temporary)
        require_time_t_widths(work, cc)
        require_native_adapters(work, cc)
        require_real_host(work, cc)
        require_injected_library(work, cc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
