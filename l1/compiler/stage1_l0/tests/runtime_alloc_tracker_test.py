#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Allocation tracker churn coverage for the shared L1 runtime.

Compiles a white-box C harness that includes ``dea_rt_alloc.c`` directly, so
the test can observe tracker internals that generated programs cannot reach.
It guards the resize policy (sustained alloc/free churn must not ratchet the
table capacity up with the lifetime number of frees) and the
``DEA_RT_QUARANTINE_MAX_*`` environment overrides of the prebuilt archive
runtime.

The workload uses a rotating window of live blocks with mixed sizes. Uniform
sizes with immediate frees do not reproduce the ratcheting because the C
allocator reuses the same address, and each insert then reclaims the
tombstone its own address left behind.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_SRC = REPO_ROOT / "l1" / "compiler" / "shared" / "runtime" / "src"
RUNTIME_INCLUDE = REPO_ROOT / "l1" / "compiler" / "shared" / "runtime" / "include"
RUNTIME_INTERNAL = REPO_ROOT / "l1" / "compiler" / "shared" / "runtime" / "internal"
BENCH_HARNESS = REPO_ROOT / "l1" / "scripts" / "bench_runtime_harness.c"

CHURN_HARNESS = """
#include "{alloc_c}"
#include "{panic_c}"

/* Linker stubs for the panic string path, which this harness never takes. */
char *_rt_string_bytes(dea_string s) {{ (void)s; return (char*)""; }}
dea_int rt_strlen(dea_string str) {{ (void)str; return 0; }}

int main(void) {{
    static void *live[CHURN_WINDOW];
    unsigned rng = 12345;
    for (int i = 0; i < 300000; i++) {{
        int slot = i % CHURN_WINDOW;
        if (live[slot] != NULL) {{
            rt_free(live[slot]);
        }}
        rng = rng * 1664525u + 1013904223u;
        live[slot] = rt_alloc((dea_int)(8 + (rng >> 20 & 1023)));
        if (live[slot] == NULL) return 2;
    }}
    printf("cap=%zu cnt=%zu quarantined=%zu\\n",
           _rt_alloc_table_cap, _rt_alloc_table_cnt, _rt_quarantine_count);
    return 0;
}}
"""


def resolve_cc() -> str:
    from_env = os.environ.get("L1_CC", "").strip()
    if from_env:
        return from_env
    for candidate in ("tcc", "gcc", "clang", "cc"):
        if shutil.which(candidate):
            return candidate
    raise AssertionError("no C compiler found: set L1_CC")


def build_harness(work_dir: Path, cc: str, window: int) -> Path:
    c_file = work_dir / f"churn_{window}.c"
    exe_file = work_dir / f"churn_{window}"
    c_file.write_text(
        CHURN_HARNESS.format(
            alloc_c=(RUNTIME_SRC / "dea_rt_alloc.c").as_posix(),
            panic_c=(RUNTIME_SRC / "dea_rt_panic.c").as_posix(),
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [
            cc,
            "-std=c99",
            f"-DCHURN_WINDOW={window}",
            f"-I{RUNTIME_INCLUDE}",
            f"-I{RUNTIME_INTERNAL}",
            str(c_file),
            "-o",
            str(exe_file),
        ],
        check=True,
    )
    return exe_file


def run_harness(exe_file: Path, extra_env: dict[str, str]) -> dict[str, int]:
    env = dict(os.environ)
    env.update(extra_env)
    completed = subprocess.run(
        [str(exe_file)],
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"churn harness exited with {completed.returncode}")
    return {key: int(value) for key, value in (pair.split("=") for pair in completed.stdout.split())}


def build_bench_harness(work_dir: Path, cc: str) -> Path:
    exe_file = work_dir / "bench_harness"
    subprocess.run(
        [
            cc,
            "-std=c99",
            f"-I{RUNTIME_SRC}",
            f"-I{RUNTIME_INCLUDE}",
            f"-I{RUNTIME_INTERNAL}",
            str(BENCH_HARNESS),
            "-o",
            str(exe_file),
        ],
        check=True,
    )
    return exe_file


def run_bench_scenario(exe_file: Path, scenario: str) -> dict[str, int]:
    completed = subprocess.run(
        [str(exe_file), scenario, "1"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"bench harness {scenario} exited with {completed.returncode}")
    stats: dict[str, int] = {}
    for token in completed.stdout.split():
        key, _, value = token.partition("=")
        if value:
            stats[key] = int(float(value))
    return stats


def check_memory_invariants(work_dir: Path, cc: str) -> None:
    exe_file = build_bench_harness(work_dir, cc)

    # Ramp: table capacity and record-pool memory stay bounded by the peak
    # live set, and the table contracts again after free-all plus settle
    # churn. Only deterministic tracker-internal bounds, never wall-clock.
    stats = run_bench_scenario(exe_file, "ramp")
    live_peak = stats["ramp.live_peak"]
    assert stats["ramp.cnt_peak"] == live_peak, stats
    assert stats["ramp.table_cap_peak"] <= 262144, stats
    assert stats["ramp.rec_pool_chunks_peak"] <= live_peak // 256 + 2, stats
    assert stats["ramp.live_cnt"] <= 4096 + 8, stats
    assert stats["ramp.table_cap"] <= 32768, stats
    assert stats["ramp.quarantine_count"] <= 4096, stats
    assert stats["ramp.quarantine_bytes"] <= 16 * 1024 * 1024, stats
    assert stats["ramp.rec_pool_chunks"] == stats["ramp.rec_pool_chunks_peak"], stats

    # Window: periodic large blocks make the quarantine byte cap bind; both
    # caps must hold at every post-operation sample point.
    stats = run_bench_scenario(exe_file, "window")
    assert stats["window.q_bytes_peak"] <= 16 * 1024 * 1024, stats
    assert stats["window.q_count_peak"] <= 4096, stats
    assert stats["window.table_cap_peak"] <= 32768, stats


def main() -> int:
    cc = resolve_cc()
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)

        # The live set is one 4096-slot window plus the bounded quarantine
        # (default count cap 4096), so a live-count-sized table stays at or
        # below 32768 slots. The former doubling policy ratcheted past
        # 131072 slots for the same workload.
        stats = run_harness(build_harness(work_dir, cc, window=4096), {})
        assert stats["quarantined"] <= 4096, stats
        assert stats["cnt"] <= 4096 + 4096, stats
        assert 256 <= stats["cap"] <= 32768, stats

        # Environment overrides retune the prebuilt archive runtime without
        # recompiling; a tiny retention keeps the table at its initial size.
        small_window = build_harness(work_dir, cc, window=8)
        stats = run_harness(small_window, {"DEA_RT_QUARANTINE_MAX_COUNT": "16"})
        assert stats["quarantined"] <= 16, stats
        assert stats["cnt"] <= 8 + 16, stats
        assert stats["cap"] == 256, stats

        # Padded values from templated configs keep strtoull()'s tolerance
        # for leading whitespace; the override must still apply.
        stats = run_harness(small_window, {"DEA_RT_QUARANTINE_MAX_COUNT": " 16"})
        assert stats["quarantined"] <= 16, stats
        assert stats["cnt"] <= 8 + 16, stats
        assert stats["cap"] == 256, stats

        # Invalid negative overrides must fall back to the default instead of
        # wrapping through strtoull() into an effectively unbounded limit.
        stats = run_harness(small_window, {"DEA_RT_QUARANTINE_MAX_COUNT": "-1"})
        assert stats["quarantined"] <= 4096, stats
        assert stats["cnt"] <= 8 + 4096, stats

        check_memory_invariants(work_dir, cc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
