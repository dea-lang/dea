/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file native_probe.c
 * Deterministic native time adapter errors, conversions, and timer lifecycle.
 */
#define _POSIX_C_SOURCE 200809L
#define DEA_TIME_TESTING 1
#include "dea_rt.h"
#if defined(_WIN32)
#include <windows.h>
#endif

static int mode, clock_calls, wait_calls;
#if defined(_WIN32)
static int close_calls;
#endif
static dea_long requested_sec;
#if !defined(_WIN32)
static dea_int requested_nsec;
#endif

#define REQUIRE(condition) do { if (!(condition)) { \
    fprintf(stderr, "time native probe line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

#if defined(_WIN32)

/**
 * Return deterministic QPC frequency or a captured native failure.
 *
 * @param out Frequency output populated only for success.
 * @return Nonzero for success, zero with last-error set for failure.
 */
static BOOL probe_frequency(LARGE_INTEGER *out) {
    if (mode == 1) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    out->QuadPart = mode == 3 ? 0 : INT64_MAX;
    return TRUE;
}

/**
 * Return a deterministic QPC count or a captured native failure.
 *
 * @param out Counter output populated only for success.
 * @return Nonzero for success, zero with last-error set for failure.
 */
static BOOL probe_counter(LARGE_INTEGER *out) {
    ++clock_calls;
    if (mode == 2) { SetLastError(ERROR_INVALID_HANDLE); return FALSE; }
    out->QuadPart = mode == 4 ? -1 : INT64_MAX - 1;
    return TRUE;
}

/**
 * Require a private unnamed timer with default non-inherited security.
 *
 * @param security Required NULL security attributes.
 * @param manual Required false auto-reset timer choice.
 * @param name Required NULL timer name.
 * @return A fake live timer or NULL with the configured native error.
 */
static HANDLE probe_create(LPSECURITY_ATTRIBUTES security, BOOL manual, LPCWSTR name) {
    if (security != NULL || manual || name != NULL) { abort(); }
    if (mode == 5) { SetLastError(ERROR_NOT_ENOUGH_MEMORY); return NULL; }
    return (HANDLE)(uintptr_t)1;
}

/**
 * Inspect the rounded-up relative timer duration and one-shot parameters.
 *
 * @param timer Fake live timer.
 * @param due Required negative relative 100-nanosecond interval.
 * @param period Required zero one-shot period.
 * @param callback Required NULL completion callback.
 * @param argument Required NULL callback argument.
 * @param resume Required false wake-from-suspend request.
 * @return Nonzero for success, zero with the configured native error.
 */
static BOOL probe_set(HANDLE timer, const LARGE_INTEGER *due, LONG period,
                      PTIMERAPCROUTINE callback, LPVOID argument, BOOL resume) {
    if (timer != (HANDLE)(uintptr_t)1 || due->QuadPart >= 0 || due->QuadPart < -10000000
        || period != 0 || callback != NULL || argument != NULL || resume) { abort(); }
    requested_sec = due->QuadPart;
    if (mode == 6) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    return TRUE;
}

/**
 * Inspect a non-alertable infinite native timer wait and inject failure.
 *
 * @param timer Fake live timer.
 * @param timeout Required infinite timeout.
 * @return Native completion or configured wait failure.
 */
static DWORD probe_wait(HANDLE timer, DWORD timeout) {
    if (timer != (HANDLE)(uintptr_t)1 || timeout != INFINITE) { abort(); }
    ++wait_calls;
    if (mode == 7) { SetLastError(ERROR_INVALID_HANDLE); return WAIT_FAILED; }
    if (mode == 8) { return WAIT_TIMEOUT; }
    return WAIT_OBJECT_0;
}

/**
 * Consume a timer and inject an independent cleanup error.
 *
 * @param timer Fake live timer consumed exactly once.
 * @return Nonzero for success, zero with the configured cleanup error.
 */
static BOOL probe_close(HANDLE timer) {
    if (timer != (HANDLE)(uintptr_t)1) { abort(); }
    ++close_calls;
    if (mode == 9) { SetLastError(ERROR_INVALID_HANDLE); return FALSE; }
    return TRUE;
}

#define DEA_TIME_QUERY_FREQUENCY probe_frequency
#define DEA_TIME_QUERY_COUNTER probe_counter
#define DEA_TIME_CREATE_TIMER probe_create
#define DEA_TIME_SET_TIMER probe_set
#define DEA_TIME_WAIT_TIMER probe_wait
#define DEA_TIME_CLOSE_TIMER probe_close

#else

/**
 * Return a deterministic monotonic sample or a configured native read failure.
 *
 * @param clock Required monotonic source.
 * @param out Sample output populated only on success.
 * @return Zero for success, negative one with captured errno for failure.
 */
static int probe_clock(clockid_t clock, struct timespec *out) {
    if (clock != CLOCK_MONOTONIC) { abort(); }
    ++clock_calls;
    if (mode == 1) { errno = EACCES; return -1; }
    if (mode == 2) { errno = EINTR; return -1; }
    if (mode == 3) { errno = ENOSYS; return -1; }
    if (mode == 4) { errno = ENOTSUP; return -1; }
    out->tv_sec = mode == 5 ? (time_t)-1 : (time_t)4294967296LL;
    out->tv_nsec = mode == 6 ? 1000000000L : 900000000L;
    return 0;
}

/**
 * Return a deterministic relative wait result while inspecting its bounded size.
 *
 * @param request Required positive normalized request at most one second.
 * @param unused Required NULL remaining-interval output.
 * @return Zero for success, negative one with the configured errno for failure.
 */
static int probe_sleep(const struct timespec *request, struct timespec *unused) {
    if (unused != NULL || request->tv_sec < 0 || request->tv_sec > 1
        || request->tv_nsec < 0 || request->tv_nsec >= 1000000000L
        || (request->tv_sec == 1 && request->tv_nsec != 0)) { abort(); }
    ++wait_calls;
    requested_sec = request->tv_sec;
    requested_nsec = (dea_int)request->tv_nsec;
    if (mode == 7) { errno = EINTR; return -1; }
    if (mode == 8) { errno = EACCES; return -1; }
    return 0;
}

#if defined(__linux__) && !DEA_TIME_BOUNDED_WAIT

/**
 * Return an absolute wait status independent of an unrelated errno value.
 *
 * @param clock Required monotonic source.
 * @param flags Required absolute-time flag.
 * @param request Original normalized absolute deadline.
 * @param unused Required NULL remaining-interval output.
 * @return Native positive error code or zero for successful wakeup.
 */
static int probe_absolute(clockid_t clock, int flags, const struct timespec *request,
                           struct timespec *unused) {
    if (clock != CLOCK_MONOTONIC || flags != TIMER_ABSTIME || unused != NULL) { abort(); }
    ++wait_calls;
    requested_sec = request->tv_sec;
    requested_nsec = (dea_int)request->tv_nsec;
    errno = EDOM;
    if (mode == 7) { return EINTR; }
    if (mode == 8) { return EACCES; }
    if (mode == 9) { return ENOSYS; }
    return 0;
}
#endif

#define DEA_TIME_CLOCK_GETTIME probe_clock
#define DEA_TIME_CLOCK_NANOSLEEP probe_absolute
#define DEA_TIME_NANOSLEEP probe_sleep

#endif

#include "dea_rt_time.c"

typedef char TimePartsSecondsWidth[
    sizeof(((struct __deaM3sys2rtS11RtTimeParts *)0)->sec) == sizeof(dea_long) ? 1 : -1];
typedef char TimePartsNanosWidth[
    sizeof(((struct __deaM3sys2rtS11RtTimeParts *)0)->nsec) == sizeof(dea_int) ? 1 : -1];
typedef char TimePartsNanosOffset[
    offsetof(struct __deaM3sys2rtS11RtTimeParts, nsec) == sizeof(dea_long) ? 1 : -1];

/**
 * Verify proper-fraction scaling without multiplying a full QPC value.
 *
 * @return Zero after every integer scaling and timer-rounding boundary succeeds.
 */
static int conversions(void) {
    dea_ulong denominators[] = {1, 3, 1000000000, UINT64_C(1000000001), INT64_MAX};
    struct __deaM3sys2rtS11RtTimeParts parts = {0};
    dea_int nanos = 17;
    size_t i;
    REQUIRE(_rt_time_write_parts(&parts, INT64_MAX, 999999999));
    REQUIRE(parts.sec == INT64_MAX && parts.nsec == 999999999);
    REQUIRE(!_rt_time_to_dea_int_nsec(-1, &nanos) && nanos == 17);
    REQUIRE(!_rt_time_to_dea_int_nsec(1000000000L, &nanos) && nanos == 17);
    REQUIRE(_rt_time_to_dea_int_nsec(999999999L, &nanos) && nanos == 999999999);
    REQUIRE(_rt_time_fraction_nsec(0, 1) == 0);
    REQUIRE(_rt_time_fraction_nsec(1, 3) == 333333333);
    REQUIRE(_rt_time_fraction_nsec(2, 3) == 666666666);
    for (i = 0; i < sizeof(denominators) / sizeof(denominators[0]); ++i) {
        dea_ulong denominator = denominators[i];
        REQUIRE(_rt_time_fraction_nsec(denominator - 1, denominator) >= 0);
        REQUIRE(_rt_time_fraction_nsec(denominator - 1, denominator) <= 999999999);
    }
    REQUIRE(_rt_time_fraction_nsec(INT64_MAX - 1, INT64_MAX) == 999999999);
    REQUIRE(_rt_time_windows_ticks(0, 1) == -1);
    REQUIRE(_rt_time_windows_ticks(0, 99) == -1);
    REQUIRE(_rt_time_windows_ticks(0, 100) == -1);
    REQUIRE(_rt_time_windows_ticks(0, 101) == -2);
    REQUIRE(_rt_time_windows_ticks(0, 999999999) == -10000000);
    REQUIRE(_rt_time_windows_ticks(1, 0) == -10000000);
    return 0;
}

/**
 * Verify the selected platform's native clock, wait, and resource adapters.
 *
 * @return Zero after native error capture and timer lifecycle checks succeed.
 */
static int adapters(void) {
    struct __deaM3sys4timeS12RtTimeResult result;
    void *context = NULL;
    mode = 0;
    result = rt_time_monotonic_result();
    REQUIRE(result.state == DEA_TIME_OK && result.sec >= 0 && result.nsec >= 0
            && result.nsec < 1000000000);
#if defined(_WIN32)
    REQUIRE(result.sec == 0 && result.nsec == 999999999);
    mode = 1; result = rt_time_monotonic_result();
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_ACCESS_DENIED);
    mode = 2; result = rt_time_monotonic_result();
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_INVALID_HANDLE);
    mode = 3; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_UNSUPPORTED);
    mode = 4; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_OVERFLOW);
    mode = 5; REQUIRE(_rt_time_open_wait(&context).state == DEA_TIME_HOST && context == NULL);
    mode = 0; REQUIRE(_rt_time_open_wait(&context).state == DEA_TIME_OK && context != NULL);
    REQUIRE(_rt_time_wait_once(context, INT64_MAX, 999999999, 0, 1).state == DEA_TIME_OK);
    REQUIRE(requested_sec == -1 && wait_calls == 1);
    mode = 6; result = _rt_time_wait_once(context, INT64_MAX, 999999999, 1, 0);
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_ACCESS_DENIED);
    mode = 7; result = _rt_time_wait_once(context, INT64_MAX, 999999999, 1, 0);
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_INVALID_HANDLE);
    mode = 8; result = _rt_time_wait_once(context, INT64_MAX, 999999999, 1, 0);
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_GEN_FAILURE);
    mode = 9; result = _rt_time_close_wait(context);
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == ERROR_INVALID_HANDLE);
    REQUIRE(close_calls == 1);
    puts("native Windows QPC and timer adapters: PASS");
#else
    mode = 1; result = rt_time_monotonic_result();
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == EACCES);
    mode = 2; result = rt_time_monotonic_result();
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == EINTR
            && result.error.kind == DEA_OS_ERROR_INTERRUPTED);
    mode = 3; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_UNSUPPORTED);
    mode = 4; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_UNSUPPORTED);
    mode = 5; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_OVERFLOW);
    mode = 6; REQUIRE(rt_time_monotonic_result().state == DEA_TIME_OVERFLOW);
    mode = 0; REQUIRE(_rt_time_open_wait(&context).state == DEA_TIME_OK);
    mode = 7; result = _rt_time_wait_once(context, 4294967300LL, 100, 3, 0);
    REQUIRE(result.state == DEA_TIME_INTERRUPTED && result.error.native_code == EINTR);
    mode = 8; result = _rt_time_wait_once(context, 4294967300LL, 100, 3, 0);
    REQUIRE(result.state == DEA_TIME_HOST && result.error.native_code == EACCES);
    mode = 0; wait_calls = 0;
    REQUIRE(_rt_time_wait_once(context, 4294967300LL, 100, 3, 0).state == DEA_TIME_OK);
#if defined(__linux__) && !DEA_TIME_BOUNDED_WAIT
    REQUIRE(requested_sec == 4294967300LL && requested_nsec == 100 && wait_calls == 1);
    mode = 9; wait_calls = 0;
    REQUIRE(_rt_time_wait_once(context, 4294967300LL, 100, INT64_MAX, 999999999).state == DEA_TIME_OK);
    REQUIRE(requested_sec == 1 && requested_nsec == 0 && wait_calls == 2);
#else
    REQUIRE(requested_sec == 1 && requested_nsec == 0 && wait_calls == 1);
#endif
    REQUIRE(_rt_time_close_wait(context).state == DEA_TIME_OK);
    puts("native POSIX clock and wait adapters: PASS");
#endif
    return 0;
}

/**
 * Execute integer conversion and native adapter probes.
 *
 * @return Zero on success, one with a failed assertion on stderr otherwise.
 */
int main(void) {
    REQUIRE(conversions() == 0);
    REQUIRE(adapters() == 0);
    return 0;
}
