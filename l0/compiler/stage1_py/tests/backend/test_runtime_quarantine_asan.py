# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""AddressSanitizer observability for checked-runtime quarantine payloads."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

MONOREPO_ROOT = Path(__file__).resolve().parents[5]
if str(MONOREPO_ROOT) not in sys.path:
    sys.path.insert(0, str(MONOREPO_ROOT))

from scripts.asan_test_support import (
    ASAN_COMPILE_TIMEOUT_SECONDS,
    ASAN_RUN_TIMEOUT_SECONDS,
    AsanTimeoutError,
    AsanToolchain,
    AsanUnavailableError,
    detect_asan_toolchain,
    run_asan_command,
)


def _compile_asan_probe(
    c_code: str,
    runtime_dir: Path,
    work_dir: Path,
    quarantine_count: int,
) -> tuple[Path, AsanToolchain] | None:
    """Compile one generated probe with the first ASan-capable compiler."""

    executable_suffix = ".exe" if os.name == "nt" else ""
    source = work_dir / f"quarantine-{quarantine_count}.c"
    executable = work_dir / f"quarantine-{quarantine_count}{executable_suffix}"
    source.write_text(c_code, encoding="utf-8")
    try:
        toolchain = detect_asan_toolchain(
            explicit_compiler=os.environ.get("L0_ASAN_CC", ""),
            configured_compilers=(os.environ.get("L0_CC", ""),),
            fallback_compilers=("clang", "gcc", "cc"),
            work_dir=work_dir,
            label="L0 quarantine ASan",
        )
    except AsanUnavailableError as error:
        pytest.fail(str(error))
    if toolchain is None:
        pytest.skip("selected C compiler has no working ASan capability")

    command = [
        toolchain.compiler,
        "-std=c99",
        "-O0",
        "-g",
        *toolchain.link_flags,
        "-fno-omit-frame-pointer",
        f"-D_RT_QUARANTINE_MAX_COUNT={quarantine_count}",
        "-I",
        str(runtime_dir),
        str(source),
        "-o",
        str(executable),
    ]
    try:
        completed = run_asan_command(
            command,
            phase="L0 quarantine ASan fixture compile",
            timeout_seconds=ASAN_COMPILE_TIMEOUT_SECONDS,
        )
    except AsanTimeoutError as error:
        pytest.fail(str(error))
    if completed.returncode != 0:
        pytest.fail(f"ASan quarantine probe did not compile: {completed.stderr.strip()}")
    return executable, toolchain


@pytest.mark.parametrize(
    ("quarantine_count", "expected_error"),
    [(4096, "use-after-poison"), (0, "heap-use-after-free")],
)
def test_checked_quarantine_preserves_asan_lifetime_observability(
    codegen_single,
    runtime_dir: Path,
    tmp_path: Path,
    quarantine_count: int,
    expected_error: str,
) -> None:
    """Retained and immediately evicted payloads remain inaccessible to ASan."""

    c_code, diagnostics = codegen_single(
        "quarantine_asan",
        """
        module quarantine_asan;

        import sys.memory;

        extern func asan_stale_read(ptr: void*) -> int;

        func main() -> int {
            let raw: void* = rt_alloc(8) as void*;
            rt_memset(raw, 90, 8);
            rt_free(raw);
            return asan_stale_read(raw);
        }
        """,
    )
    assert c_code is not None, diagnostics
    c_code += "\nl0_int asan_stale_read(void *ptr) {\n"
    c_code += "    return (l0_int)(*(volatile l0_byte *)ptr);\n"
    c_code += "}\n"

    compiled = _compile_asan_probe(c_code, runtime_dir, tmp_path, quarantine_count)
    assert compiled is not None
    executable, toolchain = compiled
    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "abort_on_error=1:detect_leaks=0:halt_on_error=1"
    try:
        completed = run_asan_command(
            [str(executable)],
            phase=f"L0 quarantine ASan fixture execution ({toolchain.mode})",
            timeout_seconds=ASAN_RUN_TIMEOUT_SECONDS,
            env=run_env,
        )
    except AsanTimeoutError as error:
        pytest.fail(str(error))

    assert completed.returncode != 0
    assert expected_error in completed.stderr
