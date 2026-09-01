#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""AddressSanitizer observability for L1 checked-runtime quarantine payloads."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
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


def asan_compilers() -> list[str]:
    """Return distinct GNU-compatible compiler candidates for ASan probes."""

    candidates = [
        os.environ.get("L1_ASAN_CC", "").strip(),
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = shutil.which(candidate)
        if path is None:
            continue
        name = Path(path).name.lower().removesuffix(".exe")
        if "gcc" not in name and "clang" not in name and name != "cc":
            continue
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key)
            resolved.append(path)
    return resolved


def compile_probe(work_dir: Path) -> tuple[Path, str] | None:
    """Compile the quarantine probe with the first ASan-capable compiler."""

    source = work_dir / "quarantine_asan_probe.c"
    executable = work_dir / (
        "quarantine_asan_probe.exe" if os.name == "nt" else "quarantine_asan_probe"
    )
    support_source = work_dir / "asan_support.c"
    support_executable = work_dir / (
        "asan_support.exe" if os.name == "nt" else "asan_support"
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
    support_source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    unsupported: list[str] = []
    failures: list[str] = []
    for compiler in asan_compilers():
        support = subprocess.run(
            [compiler, "-fsanitize=address", str(support_source), "-o", str(support_executable)],
            cwd=L1_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if support.returncode != 0:
            unsupported.append(f"{compiler}: {support.stderr.strip()}")
            continue
        support_env = os.environ.copy()
        support_env["ASAN_OPTIONS"] = "detect_leaks=0"
        try:
            support_run = subprocess.run(
                [str(support_executable)],
                cwd=L1_ROOT,
                capture_output=True,
                text=True,
                env=support_env,
                check=False,
            )
        except OSError as error:
            unsupported.append(f"{compiler}: ASan runtime did not launch: {error}")
            continue
        if support_run.returncode != 0:
            detail = support_run.stderr.strip() or support_run.stdout.strip()
            unsupported.append(
                f"{compiler}: ASan runtime exited {support_run.returncode}: {detail}"
            )
            continue
        command = [
            compiler,
            "-std=c99",
            "-O0",
            "-g",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            f"-I{RUNTIME_ROOT / 'include'}",
            f"-I{RUNTIME_ROOT / 'internal'}",
            str(source),
            *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
            "-lm",
            "-o",
            str(executable),
        ]
        completed = subprocess.run(command, cwd=L1_ROOT, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            return executable, compiler
        failures.append(f"{compiler}: {completed.stderr.strip()}")

    if failures:
        raise AssertionError("ASan quarantine probe did not compile: " + " | ".join(failures))
    if unsupported:
        print("runtime_quarantine_asan_test: SKIP: " + " | ".join(unsupported))
        return None
    print("runtime_quarantine_asan_test: SKIP: no GNU-compatible C compiler found")
    return None


def require_asan_failure(executable: Path, quarantine_count: int, expected_error: str) -> None:
    """Run one retention configuration and require its ASan lifetime failure."""

    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "abort_on_error=1:detect_leaks=0:halt_on_error=1"
    run_env["DEA_RT_QUARANTINE_MAX_COUNT"] = str(quarantine_count)
    run_env.pop("DEA_RT_QUARANTINE_MAX_BYTES", None)
    completed = subprocess.run(
        [str(executable)],
        cwd=L1_ROOT,
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
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
        executable, _compiler = compiled
        require_asan_failure(executable, 4096, "use-after-poison")
        require_asan_failure(executable, 0, "heap-use-after-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
