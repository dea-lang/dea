/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * White-box benchmark and memory-invariant harness for the shared L1 archive
 * runtime allocation tracker.
 *
 * The harness includes the runtime compilation units directly (compile with
 * `-I` at `compiler/shared/runtime/src`) so it can observe tracker internals
 * (table capacity, quarantine counters, record-pool chunks) that generated
 * programs cannot reach. The checked binary honors the
 * `DEA_RT_QUARANTINE_MAX_BYTES` / `DEA_RT_QUARANTINE_MAX_COUNT` environment
 * overrides, so one binary serves the whole retention matrix. Scenarios:
 *
 *   tight    N uniform 32-byte alloc/free pairs (allocator-reuse and
 *            quarantine-retention sensitivity).
 *   window   Rotating 4096-slot live window with mixed sizes, including
 *            periodic large blocks so the quarantine byte cap is exercised.
 *            Uniform sizes would mask tracker effects because the C allocator
 *            returns the same address each iteration.
 *   ramp     Grow a large mixed-size live set, hold it, free it all, then
 *            churn until the tracker table contracts (memory-intensive).
 *   cached   Warm one pointer-check site per live allocation, then time only
 *            cache-hit pointer validation sweeps.
 *   strings  Heap-string churn; lazily registered ARC storage stays out of
 *            the tracker.
 *
 * Output is `scenario.key=value` lines plus one process-wide `max_rss_kib`.
 * Scenario and scale come from argv ("harness <scenario> <scale>") or from
 * the BENCH_SCENARIO / BENCH_SCALE defines.
 */

#ifndef BENCH_SCENARIO
#define BENCH_SCENARIO "all"
#endif
#ifndef BENCH_SCALE
#define BENCH_SCALE 1
#endif

#include "dea_rt_alloc.c"
#include "dea_rt_string.c"
#include "dea_rt_panic.c"

#include <time.h>

#if defined(_WIN32)
static long bench_max_rss_kib(void) {
    return 0;
}
#else
#include <sys/resource.h>
static long bench_max_rss_kib(void) {
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage) != 0) {
        return 0;
    }
#if defined(__APPLE__)
    return (long)(usage.ru_maxrss / 1024);
#else
    return (long)usage.ru_maxrss;
#endif
}
#endif

static double bench_ms_since(clock_t start) {
    return (double)(clock() - start) * 1000.0 / CLOCKS_PER_SEC;
}

static unsigned bench_rng_next(unsigned *rng) {
    *rng = *rng * 1664525u + 1013904223u;
    return *rng;
}

static volatile uintptr_t bench_cached_sink = 0;

static void bench_print_tracker_stats(const char *scenario) {
#ifndef DEA_RT_UNCHECKED
    printf("%s.table_cap=%zu\n", scenario, _rt_alloc_table_cap);
    printf("%s.live_cnt=%zu\n", scenario, _rt_alloc_table_cnt);
    printf("%s.quarantine_bytes=%zu\n", scenario, _rt_quarantine_bytes);
    printf("%s.quarantine_count=%zu\n", scenario, _rt_quarantine_count);
    printf("%s.rec_pool_chunks=%zu\n", scenario, _rt_rec_pool_chunks);
#else
    (void)scenario;
#endif
}

static int bench_tight(long scale) {
    long pairs = 1000000L * scale;
    clock_t start = clock();
    for (long i = 0; i < pairs; i++) {
        void *p = rt_alloc(32);
        if (p == NULL) return 2;
        rt_free(p);
    }
    printf("tight.wall_ms=%.0f\n", bench_ms_since(start));
    printf("tight.ops=%ld\n", pairs);
    bench_print_tracker_stats("tight");
    return 0;
}

static int bench_window(long scale) {
    enum { WINDOW = 4096 };
    static void *live[WINDOW];
    long ops = 500000L * scale;
    unsigned rng = 12345;
    size_t q_bytes_peak = 0;
    size_t q_count_peak = 0;
    size_t cap_peak = 0;

    clock_t start = clock();
    for (long i = 0; i < ops; i++) {
        int slot = (int)(i % WINDOW);
        if (live[slot] != NULL) {
            rt_free(live[slot]);
        }
        unsigned draw = bench_rng_next(&rng);
        dea_int size = (dea_int)(8 + (draw >> 20 & 1023));
        if (i % 13 == 0) {
            /* Periodic large blocks so the quarantine byte cap binds. */
            size = (dea_int)(32768 + (draw & 0xFFFF));
        }
        live[slot] = rt_alloc(size);
        if (live[slot] == NULL) return 2;
#ifndef DEA_RT_UNCHECKED
        if (_rt_quarantine_bytes > q_bytes_peak) q_bytes_peak = _rt_quarantine_bytes;
        if (_rt_quarantine_count > q_count_peak) q_count_peak = _rt_quarantine_count;
        if (_rt_alloc_table_cap > cap_peak) cap_peak = _rt_alloc_table_cap;
#endif
    }
    printf("window.wall_ms=%.0f\n", bench_ms_since(start));
    printf("window.ops=%ld\n", ops);
    printf("window.q_bytes_peak=%zu\n", q_bytes_peak);
    printf("window.q_count_peak=%zu\n", q_count_peak);
    printf("window.table_cap_peak=%zu\n", cap_peak);
    bench_print_tracker_stats("window");
    for (int slot = 0; slot < WINDOW; slot++) {
        if (live[slot] != NULL) {
            rt_free(live[slot]);
            live[slot] = NULL;
        }
    }
    return 0;
}

static int bench_ramp(long scale) {
    long live_peak = 100000L * scale;
    void **live = (void**)malloc((size_t)live_peak * sizeof(void*));
    unsigned rng = 67890;
    if (live == NULL) return 2;

    clock_t start = clock();
    for (long i = 0; i < live_peak; i++) {
        unsigned draw = bench_rng_next(&rng);
        live[i] = rt_alloc((dea_int)(8 + (draw >> 20 & 1023)));
        if (live[i] == NULL) return 2;
    }
    printf("ramp.grow_wall_ms=%.0f\n", bench_ms_since(start));
    printf("ramp.live_peak=%ld\n", live_peak);
#ifndef DEA_RT_UNCHECKED
    printf("ramp.table_cap_peak=%zu\n", _rt_alloc_table_cap);
    printf("ramp.cnt_peak=%zu\n", _rt_alloc_table_cnt);
    printf("ramp.rec_pool_chunks_peak=%zu\n", _rt_rec_pool_chunks);
#endif

    start = clock();
    for (long i = 0; i < live_peak; i++) {
        rt_free(live[i]);
    }
    printf("ramp.free_wall_ms=%.0f\n", bench_ms_since(start));
    free(live);

    /* Churn with mixed sizes until tombstone purges rebuild the table at a
     * contracted size; uniform sizes would reuse addresses and never drift. */
    start = clock();
    for (long i = 0; i < live_peak * 2; i++) {
        unsigned draw = bench_rng_next(&rng);
        void *p = rt_alloc((dea_int)(8 + (draw >> 20 & 1023)));
        if (p == NULL) return 2;
        rt_free(p);
    }
    printf("ramp.settle_wall_ms=%.0f\n", bench_ms_since(start));
    bench_print_tracker_stats("ramp");
    return 0;
}

static int bench_cached(long scale) {
    long live_count = 65536L * scale;
    long sweeps = 64;
    void **live = (void**)calloc((size_t)live_count, sizeof(void*));
    _rt_ptr_site *sites = (_rt_ptr_site*)calloc((size_t)live_count, sizeof(_rt_ptr_site));
    unsigned rng = 24680;
    if (live == NULL || sites == NULL) {
        free(live);
        free(sites);
        return 2;
    }

    for (long i = 0; i < live_count; i++) {
        unsigned draw = bench_rng_next(&rng);
        dea_int size = (dea_int)(16 + (draw >> 20 & 255));
        live[i] = rt_alloc(size);
        if (live[i] == NULL) {
            for (long j = 0; j < i; j++) {
                rt_free(live[j]);
            }
            free(live);
            free(sites);
            return 2;
        }
        _rt_check_ptr_site(&sites[i], live[i], 1, 1, _RT_ACCESS_READ, "<bench>", 0);
    }

    uintptr_t acc = 0;
    clock_t start = clock();
    for (long sweep = 0; sweep < sweeps; sweep++) {
        for (long i = 0; i < live_count; i++) {
            acc ^= (uintptr_t)_rt_check_ptr_site(&sites[i], live[i], 1, 1, _RT_ACCESS_READ, "<bench>", 0);
        }
    }
    bench_cached_sink ^= acc;
    printf("cached.wall_ms=%.0f\n", bench_ms_since(start));
    printf("cached.ops=%ld\n", live_count * sweeps);
    printf("cached.live=%ld\n", live_count);
    printf("cached.sink=%lu\n", (unsigned long)bench_cached_sink);
    bench_print_tracker_stats("cached");

    for (long i = 0; i < live_count; i++) {
        rt_free(live[i]);
    }
    free(live);
    free(sites);
    return 0;
}

static int bench_strings(long scale) {
    long pairs = 1000000L * scale;
    clock_t start = clock();
    for (long i = 0; i < pairs; i++) {
        dea_string s = _rt_alloc_string(24);
        _rt_free_string(s);
    }
    printf("strings.wall_ms=%.0f\n", bench_ms_since(start));
    printf("strings.ops=%ld\n", pairs);
    bench_print_tracker_stats("strings");
    return 0;
}

int main(int argc, char **argv) {
    const char *scenario = BENCH_SCENARIO;
    long scale = BENCH_SCALE;
    if (argc > 1) scenario = argv[1];
    if (argc > 2) scale = strtol(argv[2], NULL, 10);
    if (scale <= 0) scale = 1;

    printf("record.hot_bytes=%zu\n", sizeof(_rt_alloc_record));
    printf("record.cold_bytes=%zu\n", sizeof(_rt_alloc_record_cold));

    int run_all = strcmp(scenario, "all") == 0;
    int rc = 0;
    int matched = 0;

    if (run_all || strcmp(scenario, "tight") == 0) {
        matched = 1;
        rc = bench_tight(scale);
        if (rc != 0) return rc;
    }
    if (run_all || strcmp(scenario, "window") == 0) {
        matched = 1;
        rc = bench_window(scale);
        if (rc != 0) return rc;
    }
    if (run_all || strcmp(scenario, "ramp") == 0) {
        matched = 1;
        rc = bench_ramp(scale);
        if (rc != 0) return rc;
    }
    if (run_all || strcmp(scenario, "cached") == 0) {
        matched = 1;
        rc = bench_cached(scale);
        if (rc != 0) return rc;
    }
    if (run_all || strcmp(scenario, "strings") == 0) {
        matched = 1;
        rc = bench_strings(scale);
        if (rc != 0) return rc;
    }
    if (!matched) {
        fprintf(stderr, "unknown scenario: %s\n", scenario);
        return 2;
    }

    printf("max_rss_kib=%ld\n", bench_max_rss_kib());
    return 0;
}
