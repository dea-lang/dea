/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file time_faults.c
 * Deterministic clock, wait, and cleanup outcomes for generated L1 consumers.
 */
#include "time_faults.h"

typedef struct __deaM3sys4timeS12RtTimeResult TimeResult;
static int mode, reads, waits, opens, closes;
static dea_long now_sec, maximum_wait_sec, last_deadline_sec;
static dea_int now_nsec, maximum_wait_nsec, last_deadline_nsec;
static int context_token;

/**
 * Return an initialized success sample from the current test clock.
 *
 * @return Success with normalized seconds and nanoseconds.
 */
static TimeResult success(void) {
    TimeResult result = {0};
    result.sec = now_sec;
    result.nsec = now_nsec;
    return result;
}

/**
 * Capture a deterministic error independently of ambient errno.
 *
 * @param state Scheduling transport state to return.
 * @param code Native errno code to capture.
 * @return Initialized failure with the supplied native cause.
 */
static TimeResult failure(int state, int code) {
    TimeResult result = {0};
    result.state = state;
    result.error = rt_os_error_from_errno(code);
    return result;
}

/**
 * Reset the test clock and fault scenario without reading any host clock.
 *
 * @param value Fault scenario used by subsequent injected adapters.
 */
void time_probe_config(dea_int value) {
    mode = value;
    reads = waits = opens = closes = 0;
    now_sec = 4294967296LL;
    now_nsec = 900000000;
    maximum_wait_sec = last_deadline_sec = 0;
    maximum_wait_nsec = last_deadline_nsec = 0;
    if (mode == 3) { now_sec = 0; now_nsec = 0; }
    if (mode == 4) { now_sec = INT64_MAX; }
    if (mode == 14) { now_nsec = 1000000000; }
}

/**
 * Report how many clock samples the current scenario consumed.
 *
 * @return Clock-read count since configuration.
 */
dea_int time_probe_reads(void) { return reads; }

/**
 * Report how many host wait attempts the current scenario consumed.
 *
 * @return Wait-attempt count since configuration.
 */
dea_int time_probe_waits(void) { return waits; }

/**
 * Report wait-context opens since configuration.
 *
 * @return Number of attempted context opens.
 */
dea_int time_probe_opens(void) { return opens; }

/**
 * Report consumed wait contexts since configuration.
 *
 * @return Number of context cleanup attempts.
 */
dea_int time_probe_closes(void) { return closes; }

/**
 * Report the largest requested whole-second wait component.
 *
 * @return Maximum observed relative wait seconds.
 */
dea_long time_probe_max_wait_sec(void) { return maximum_wait_sec; }

/**
 * Report the fractional part of the largest requested wait.
 *
 * @return Nanosecond component of the maximum relative request.
 */
dea_int time_probe_max_wait_nsec(void) { return maximum_wait_nsec; }

/**
 * Report the original absolute deadline passed to the wait adapter.
 *
 * @return Last observed deadline seconds.
 */
dea_long time_probe_deadline_sec(void) { return last_deadline_sec; }

/**
 * Report the original absolute deadline fraction passed to the wait adapter.
 *
 * @return Last observed deadline nanoseconds.
 */
dea_int time_probe_deadline_nsec(void) { return last_deadline_nsec; }

/**
 * Read a deterministic monotonic sample or captured clock failure.
 *
 * @return Current sample, unsupported-clock state, or captured native error.
 */
TimeResult time_probe_clock(void) {
    ++reads;
    if (mode == 1) { TimeResult result = {0}; result.state = 3; return result; }
    if (mode == 2 || (mode == 11 && reads > 1)) { return failure(4, EACCES); }
    errno = ERANGE;
    return success();
}

/**
 * Open a test wait context or report its configured failure.
 *
 * @param context Output receiving a non-NULL token only on success.
 * @return Success or a captured open error.
 */
TimeResult time_probe_open(void **context) {
    ++opens;
    if (mode == 10) { return failure(4, EMFILE); }
    *context = &context_token;
    return success();
}

/**
 * Perform one deterministic wait while retaining the absolute deadline.
 *
 * @param context Live test token from the open adapter.
 * @param sec Original absolute deadline seconds.
 * @param nsec Original absolute deadline nanoseconds.
 * @param remaining_sec Whole seconds requested for this bounded wait.
 * @param remaining_nsec Fraction requested for this bounded wait.
 * @return Success, captured interruption, or captured wait failure.
 */
TimeResult time_probe_wait(void *context, dea_long sec, dea_int nsec,
                           dea_long remaining_sec, dea_int remaining_nsec) {
    if (context != &context_token || remaining_sec < 0 || remaining_nsec < 0
        || remaining_nsec >= 1000000000 || (remaining_sec == 0 && remaining_nsec == 0)) {
        abort();
    }
    ++waits;
    last_deadline_sec = sec;
    last_deadline_nsec = nsec;
    if (remaining_sec > maximum_wait_sec
        || (remaining_sec == maximum_wait_sec && remaining_nsec > maximum_wait_nsec)) {
        maximum_wait_sec = remaining_sec;
        maximum_wait_nsec = remaining_nsec;
    }
    if (mode == 8) { return failure(4, EACCES); }
    if (mode == 6) {
        now_sec = sec;
        now_nsec = nsec;
        return failure(5, EINTR);
    }
    if (mode == 15 && waits == 1) {
        ++now_sec;
        return failure(5, EINTR);
    }
    if (mode == 7 && waits == 1) {

        /* An early successful wakeup must be followed by another read and wait. */
        now_nsec += 1;
        if (now_nsec == 1000000000) { ++now_sec; now_nsec = 0; }
        return success();
    }
    if (mode == 12) {

        /* Suspension advances the clock while the native countdown was paused. */
        now_sec = sec;
        now_nsec = nsec;
        return success();
    }
    now_sec += remaining_sec;
    now_nsec += remaining_nsec;
    if (now_nsec >= 1000000000) { ++now_sec; now_nsec -= 1000000000; }
    return success();
}

/**
 * Consume the test wait context and report its configured cleanup outcome.
 *
 * @param context Live test token consumed exactly once.
 * @return Success or a captured error distinct from the primary operation.
 */
TimeResult time_probe_close(void *context) {
    if (context != &context_token) { abort(); }
    ++closes;
    errno = EBADF;
    if (mode == 8 || mode == 9) { return failure(4, EBADF); }
    return success();
}
