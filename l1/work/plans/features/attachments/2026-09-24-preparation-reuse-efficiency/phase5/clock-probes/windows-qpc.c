/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file Frozen production-function extraction for simulated clock correctness evidence. */
#include <stdint.h>
#include <stddef.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define _WIN32 1
typedef struct { int64_t QuadPart; } LARGE_INTEGER;
static int counter_ok = 1, frequency_ok = 1;
static int64_t counter_value = 0, frequency_value = 10000000;
static int QueryPerformanceCounter(LARGE_INTEGER *p) { p->QuadPart = counter_value; return counter_ok; }
static int QueryPerformanceFrequency(LARGE_INTEGER *p) { p->QuadPart = frequency_value; return frequency_ok; }
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

int main(void) {
    if (check_snapshot(1,0,0)) return 1;
    counter_ok = 0; if (check_snapshot(0,0,0)) return 2; counter_ok = 1;
    frequency_ok = 0; if (check_snapshot(0,0,0)) return 3; frequency_ok = 1;
    counter_value = -1; if (check_snapshot(0,0,0)) return 4;
    counter_value = 4; frequency_value = 0; if (check_snapshot(0,0,0)) return 5;
    frequency_value = -1; if (check_snapshot(0,0,0)) return 6;
    frequency_value = 3; if (check_snapshot(1,1,333333333)) return 7;
    counter_value = INT64_MAX; frequency_value = 1; if (check_snapshot(0,0,0)) return 8;
    counter_value = (int64_t)INT32_MAX * 10000000 + 9999999; frequency_value = 10000000;
    if (check_snapshot(1,INT32_MAX,999999900)) return 9;
    counter_value = INT64_MAX; frequency_value = INT64_MAX; if (check_snapshot(1,1,0)) return 10;
    puts("simulated Windows QPC range/failure/unaligned-output preservation: PASS"); return 0;
}
