#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""Allocation tracker churn behavior tests for the shared header runtime.

These tests compile white-box C harnesses that include ``l0_runtime.h``
directly, so they can observe the tracker hash table capacity that generated
programs cannot reach. They guard the resize policy: sustained alloc/free
churn must not ratchet the table capacity up with the lifetime number of
frees.

The workload uses a rotating window of live blocks with mixed sizes. Uniform
sizes with immediate frees do not reproduce the ratcheting because the C
allocator reuses the same address, and each insert then reclaims the
tombstone its own address left behind; mixed sizes over a rotating window
diversify addresses the way a long-running service does.

The memory-invariant tests reuse the benchmark harness at
``l0/scripts/bench_runtime_harness.c`` at suite scale and assert only
deterministic tracker-internal bounds, never wall-clock time.
"""

from pathlib import Path


BENCH_HARNESS_PATH = Path(__file__).resolve().parents[4] / "scripts" / "bench_runtime_harness.c"

CHURN_HARNESS = """
%(defines)s
#ifndef CHURN_WINDOW
#define CHURN_WINDOW 4096
#endif
#define SIPHASH_IMPLEMENTATION
#include "l0_runtime.h"

int main(void) {
    static void *live[CHURN_WINDOW];
    unsigned rng = 12345;
    for (int i = 0; i < 300000; i++) {
        int slot = i %% CHURN_WINDOW;
        if (live[slot] != NULL) {
            rt_free(live[slot]);
        }
        rng = rng * 1664525u + 1013904223u;
        live[slot] = rt_alloc((l0_int)(8 + (rng >> 20 & 1023)));
        if (live[slot] == NULL) return 2;
    }
    printf("cap=%%zu cnt=%%zu quarantined=%%zu\\n",
           _rt_alloc_table_cap, _rt_alloc_table_cnt, _rt_quarantine_count);
    return 0;
}
"""


def _run_churn_harness(compile_and_run, tmp_path, defines: str = ""):
    success, stdout, stderr = compile_and_run(CHURN_HARNESS % {"defines": defines}, tmp_path)
    assert success, stderr
    stats = dict(pair.split("=") for pair in stdout.split())
    return {key: int(value) for key, value in stats.items()}


def test_alloc_free_churn_keeps_table_capacity_bounded(compile_and_run, tmp_path):
    stats = _run_churn_harness(compile_and_run, tmp_path)

    # The live set is one 4096-slot window plus the bounded quarantine
    # (default count cap 4096), so a live-count-sized table stays at or below
    # 32768 slots. The former doubling policy ratcheted past 131072 slots for
    # the same workload.
    assert stats["quarantined"] <= 4096
    assert stats["cnt"] <= 4096 + 4096
    assert 256 <= stats["cap"] <= 32768, stats


def test_check_basic_alloc_free_churn_keeps_table_capacity_bounded(compile_and_run, tmp_path):
    stats = _run_churn_harness(compile_and_run, tmp_path, "#define L0_RT_CHECK_BASIC 1")

    assert stats["quarantined"] <= 4096
    assert stats["cnt"] <= 4096 + 4096
    assert 256 <= stats["cap"] <= 32768, stats


STRING_LAZINESS_HARNESS = """
#define SIPHASH_IMPLEMENTATION
#include "l0_runtime.h"

int main(void) {
    for (int i = 0; i < 100000; i++) {
        l0_string churn = _rt_alloc_string(24);
        _rt_free_string(churn);
    }
    printf("cnt_after_churn=%zu\\n", _rt_alloc_table_cnt);

    l0_string s = _rt_alloc_string(24);
    (void)rt_string_bytes_ptr(s);
    size_t cnt_exposed = _rt_alloc_table_cnt;
    (void)rt_string_bytes_ptr(s);
    printf("cnt_exposed=%zu cnt_reexposed=%zu\\n", cnt_exposed, _rt_alloc_table_cnt);
    _rt_free_string(s);
    printf("cnt_final=%zu\\n", _rt_alloc_table_cnt);
    return 0;
}
"""


def test_string_churn_stays_out_of_tracker_until_bytes_exposure(compile_and_run, tmp_path):
    success, stdout, stderr = compile_and_run(STRING_LAZINESS_HARNESS, tmp_path)
    assert success, stderr
    stats = dict(pair.split("=") for pair in stdout.split())

    # Heap strings register only at first raw-byte exposure, idempotently,
    # and final ARC release removes the record again.
    assert stats["cnt_after_churn"] == "0", stats
    assert stats["cnt_exposed"] == "1", stats
    assert stats["cnt_reexposed"] == "1", stats
    assert stats["cnt_final"] == "0", stats


def _run_bench_scenario(compile_and_run, tmp_path, scenario: str):
    source = BENCH_HARNESS_PATH.read_text(encoding="utf-8")
    prelude = f'#define BENCH_SCENARIO "{scenario}"\n#define BENCH_SCALE 1\n'
    success, stdout, stderr = compile_and_run(prelude + source, tmp_path)
    assert success, stderr
    stats = {}
    for token in stdout.split():
        key, _, value = token.partition("=")
        if value:
            stats[key] = int(float(value))
    return stats


def test_ramp_memory_invariants_hold_under_large_live_set(compile_and_run, tmp_path):
    stats = _run_bench_scenario(compile_and_run, tmp_path, "ramp")

    live_peak = stats["ramp.live_peak"]
    assert stats["ramp.cnt_peak"] == live_peak

    # Table capacity stays within the live-count-sized rehash policy: the
    # smallest power of two at or above twice the live count.
    assert stats["ramp.table_cap_peak"] <= 262144, stats

    # Record-pool memory is peak-driven: one chunk per _RT_REC_POOL_CHUNK
    # records at the peak, with one chunk of slack.
    assert stats["ramp.rec_pool_chunks_peak"] <= live_peak // 256 + 2, stats

    # After free-all plus mixed-size settle churn, the tracker holds only the
    # bounded quarantine and the table contracts back near the live set.
    assert stats["ramp.live_cnt"] <= 4096 + 8, stats
    assert stats["ramp.table_cap"] <= 32768, stats
    assert stats["ramp.quarantine_count"] <= 4096, stats
    assert stats["ramp.quarantine_bytes"] <= 16 * 1024 * 1024, stats
    assert stats["ramp.rec_pool_chunks"] == stats["ramp.rec_pool_chunks_peak"], stats


def test_window_quarantine_caps_hold_with_large_blocks(compile_and_run, tmp_path):
    stats = _run_bench_scenario(compile_and_run, tmp_path, "window")

    # The periodic large blocks make the byte cap bind before the count cap;
    # both caps must hold at every post-operation sample point.
    assert stats["window.q_bytes_peak"] <= 16 * 1024 * 1024, stats
    assert stats["window.q_count_peak"] <= 4096, stats
    assert stats["window.table_cap_peak"] <= 32768, stats


def test_quarantine_count_override_shrinks_retention_and_table(compile_and_run, tmp_path):
    stats = _run_churn_harness(
        compile_and_run,
        tmp_path,
        defines=(
            "#define _RT_QUARANTINE_MAX_COUNT ((size_t)16)\n"
            "#define CHURN_WINDOW 8"
        ),
    )

    assert stats["quarantined"] <= 16
    assert stats["cnt"] <= 8 + 16
    assert stats["cap"] == 256, stats
