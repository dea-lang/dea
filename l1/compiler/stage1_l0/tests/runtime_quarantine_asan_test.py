#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""AddressSanitizer observability for L1 checked-runtime quarantine payloads."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.asan_test_support import (
    ASAN_COMPILE_TIMEOUT_SECONDS,
    ASAN_RUN_TIMEOUT_SECONDS,
    AsanToolchain,
    detect_asan_toolchain,
    run_asan_command,
)


L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_SOURCES = [
    "dea_rt_panic.c",
    "dea_rt_sys.c",
    "dea_rt_math.c",
    "dea_rt_rand.c",
    "dea_rt_string.c",
    "dea_rt_alloc.c",
    "dea_rt_io.c",
    "dea_rt_hash.c",
    "dea_rt_time.c",
]


def compile_probe(work_dir: Path) -> tuple[Path, AsanToolchain] | None:
    """Compile the quarantine probe with the first ASan-capable compiler."""

    source = work_dir / "quarantine_asan_probe.c"
    executable = work_dir / (
        "quarantine_asan_probe.exe" if os.name == "nt" else "quarantine_asan_probe"
    )
    source.write_text(
        """
#include "dea_rt.h"

int main(void) {
    void *ptr = rt_alloc(8);
    rt_memset(ptr, 0x5A, 8);
    rt_free(ptr);
    return (int)(*(volatile dea_byte *)ptr);
}
""",
        encoding="utf-8",
    )
    toolchain = detect_asan_toolchain(
        explicit_compiler=os.environ.get("L1_ASAN_CC", ""),
        configured_compilers=(
            os.environ.get("L1_RUNTIME_CC", ""),
            os.environ.get("L1_CC", ""),
        ),
        fallback_compilers=("clang", "gcc", "cc"),
        work_dir=work_dir,
        label="L1 quarantine ASan",
        cwd=L1_ROOT,
    )
    if toolchain is None:
        return None

    command = [
        toolchain.compiler,
        "-std=c99",
        "-O0",
        "-g",
        *toolchain.link_flags,
        "-fno-omit-frame-pointer",
        f"-I{RUNTIME_ROOT / 'include'}",
        f"-I{RUNTIME_ROOT / 'internal'}",
        str(source),
        *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm",
        "-o",
        str(executable),
    ]
    completed = run_asan_command(
        command,
        phase="L1 quarantine ASan fixture compile",
        timeout_seconds=ASAN_COMPILE_TIMEOUT_SECONDS,
        cwd=L1_ROOT,
    )
    if completed.returncode != 0:
        raise AssertionError(f"ASan quarantine probe did not compile: {completed.stderr.strip()}")
    return executable, toolchain


def require_asan_failure(
    executable: Path,
    toolchain: AsanToolchain,
    quarantine_count: int,
    expected_error: str,
) -> None:
    """Run one retention configuration and require its ASan lifetime failure."""

    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "abort_on_error=1:detect_leaks=0:halt_on_error=1"
    run_env["DEA_RT_QUARANTINE_MAX_COUNT"] = str(quarantine_count)
    run_env.pop("DEA_RT_QUARANTINE_MAX_BYTES", None)
    completed = run_asan_command(
        [str(executable)],
        phase=f"L1 quarantine ASan fixture execution ({toolchain.mode})",
        timeout_seconds=ASAN_RUN_TIMEOUT_SECONDS,
        cwd=L1_ROOT,
        env=run_env,
    )
    if completed.returncode == 0 or expected_error not in completed.stderr:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(
            f"quarantine count {quarantine_count} did not report {expected_error!r}"
        )


def main() -> int:
    """Compile and run retained plus zero-retention ASan probes."""

    with tempfile.TemporaryDirectory() as tmp:
        compiled = compile_probe(Path(tmp))
        if compiled is None:
            return 0
        executable, toolchain = compiled
        require_asan_failure(executable, toolchain, 4096, "use-after-poison")
        require_asan_failure(executable, toolchain, 0, "heap-use-after-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
