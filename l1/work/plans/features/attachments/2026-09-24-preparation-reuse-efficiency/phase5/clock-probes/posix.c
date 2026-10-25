/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file Frozen production-function extraction for simulated clock correctness evidence.
 */
#include <stdint.h>
#include <stddef.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#undef _WIN32
#define CLOCK_MONOTONIC 1
struct fixture_timespec { int64_t tv_sec, tv_nsec; };
#define timespec fixture_timespec
static int clock_status;
static int64_t clock_seconds, clock_nanoseconds;

/**
 * Supply the controlled POSIX monotonic clock fixture response.
 *
 * @param which Requested fixture clock identifier.
 * @param out Caller-owned output storage; written only as specified by the contract.
 * @return Configured clock status; successful calls write the fixture timespec.
 */
static int clock_gettime(int which, struct fixture_timespec *out) {
    if (which != CLOCK_MONOTONIC) return -1;
    out->tv_sec = clock_seconds; out->tv_nsec = clock_nanoseconds; return clock_status;
}

/**
 * Capture a compiler-private monotonic snapshot as two native int32 values.
 *
 * @param output Caller-owned writable output span, or NULL for a length query.
 * @param capacity Writable output capacity in bytes.
 * @return One after writing both components; zero for an invalid output or unavailable or unrepresentable
 * clock.
 */
int32_t l1c_timing_monotonic(uint8_t *output, int32_t capacity) {
    int32_t parts[2];
    if (output == NULL || capacity < (int32_t)sizeof(parts)) return 0;
#if defined(_WIN32)
    {
        LARGE_INTEGER counter, frequency;
        int64_t seconds, remainder;
        long double nanoseconds;
        if (!QueryPerformanceCounter(&counter) || !QueryPerformanceFrequency(&frequency) ||
            counter.QuadPart < 0 || frequency.QuadPart <= 0) return 0;
        seconds = counter.QuadPart / frequency.QuadPart;
        remainder = counter.QuadPart % frequency.QuadPart;
        if (seconds > INT32_MAX) return 0;
        nanoseconds = (long double)remainder * 1000000000.0L / (long double)frequency.QuadPart;
        if (nanoseconds < 0 || nanoseconds >= 1000000000.0L) return 0;
        parts[0] = (int32_t)seconds;
        parts[1] = (int32_t)nanoseconds;
    }
#elif defined(CLOCK_MONOTONIC)
    {
        struct timespec snapshot;
        if (clock_gettime(CLOCK_MONOTONIC, &snapshot) != 0 || snapshot.tv_sec < 0 ||
            (uintmax_t)snapshot.tv_sec > INT32_MAX || snapshot.tv_nsec < 0 ||
            snapshot.tv_nsec >= 1000000000L) return 0;
        parts[0] = (int32_t)snapshot.tv_sec;
        parts[1] = (int32_t)snapshot.tv_nsec;
    }
#else
    return 0;
#endif
    memcpy(output, parts, sizeof(parts));
    return 1;
}

/**
 * Check a simulated monotonic snapshot against its expected status and components.
 *
 * @param expected Expected success flag from the selected monotonic clock adapter.
 * @param sec Whole seconds in the normalized time value.
 * @param nsec Nanosecond component of the normalized time value.
 * @return Zero on a match; a distinct nonzero code for an invalid-input, status, data, or bounds mismatch.
 */
static int check_snapshot(int expected, int32_t sec, int32_t nsec) {
    uint8_t storage[11], original[11];
    int32_t actual[2];
    int status;
    memset(storage, 0xa5, sizeof(storage)); memcpy(original, storage, sizeof(storage));
    if (l1c_timing_monotonic(NULL, 8) || l1c_timing_monotonic(storage, -1) ||
        l1c_timing_monotonic(storage, 7) || memcmp(storage, original, sizeof(storage))) return 1;
    status = l1c_timing_monotonic(storage + 1, 8);
    if (status != expected) return 2;
    if (!status) return memcmp(storage, original, sizeof(storage)) ? 3 : 0;
    memcpy(actual, storage + 1, sizeof(actual));
    if (actual[0] != sec || actual[1] != nsec || storage[0] != 0xa5 || storage[9] != 0xa5 || storage[10] != 0xa5) return 4;
    return 0;
}

/**
 * Exercise controlled POSIX monotonic-clock success and failure cases.
 * @return Zero when all requested checks succeed; nonzero on a fixture failure.
 */
int main(void) {
    if (check_snapshot(1,0,0)) return 1;
    clock_status = -1; if (check_snapshot(0,0,0)) return 2; clock_status = 0;
    clock_seconds = -1; if (check_snapshot(0,0,0)) return 3;
    clock_seconds = (int64_t)INT32_MAX + 1; if (check_snapshot(0,0,0)) return 4;
    clock_seconds = 1; clock_nanoseconds = -1; if (check_snapshot(0,0,0)) return 5;
    clock_nanoseconds = 1000000000; if (check_snapshot(0,0,0)) return 6;
    clock_seconds = INT32_MAX; clock_nanoseconds = 999999999;
    if (check_snapshot(1,INT32_MAX,999999999)) return 7;
    puts("simulated POSIX range/failure/unaligned-output preservation: PASS"); return 0;
}
