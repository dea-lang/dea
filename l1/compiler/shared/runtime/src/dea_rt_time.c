/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#if !defined(_WIN32)
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#endif

#include "../include/dea_rt.h"
#include <limits.h>

#if defined(_WIN32)
#include <windows.h>
#endif

/* Private compile-time seams support deterministic adapter tests. */
#ifndef DEA_TIME_BOUNDED_WAIT
#if defined(_WIN32) || !defined(__linux__)
#define DEA_TIME_BOUNDED_WAIT 1
#else
#define DEA_TIME_BOUNDED_WAIT 0
#endif
#endif

#ifndef DEA_TIME_READ_CLOCK
#define DEA_TIME_READ_CLOCK _rt_time_read_host
#endif
#ifndef DEA_TIME_OPEN_WAIT
#define DEA_TIME_OPEN_WAIT _rt_time_open_wait
#endif
#ifndef DEA_TIME_WAIT_ONCE
#define DEA_TIME_WAIT_ONCE _rt_time_wait_once
#endif
#ifndef DEA_TIME_CLOSE_WAIT
#define DEA_TIME_CLOSE_WAIT _rt_time_close_wait
#endif

#if defined(_WIN32)
#ifndef DEA_TIME_QUERY_COUNTER
#define DEA_TIME_QUERY_COUNTER QueryPerformanceCounter
#endif
#ifndef DEA_TIME_QUERY_FREQUENCY
#define DEA_TIME_QUERY_FREQUENCY QueryPerformanceFrequency
#endif
#ifndef DEA_TIME_CREATE_TIMER
#define DEA_TIME_CREATE_TIMER CreateWaitableTimerW
#endif
#ifndef DEA_TIME_SET_TIMER
#define DEA_TIME_SET_TIMER SetWaitableTimer
#endif
#ifndef DEA_TIME_WAIT_TIMER
#define DEA_TIME_WAIT_TIMER WaitForSingleObject
#endif
#ifndef DEA_TIME_CLOSE_TIMER
#define DEA_TIME_CLOSE_TIMER CloseHandle
#endif
#else
#ifndef DEA_TIME_CLOCK_GETTIME
#define DEA_TIME_CLOCK_GETTIME clock_gettime
#endif
#ifndef DEA_TIME_CLOCK_NANOSLEEP
#define DEA_TIME_CLOCK_NANOSLEEP clock_nanosleep
#endif
#ifndef DEA_TIME_NANOSLEEP
#define DEA_TIME_NANOSLEEP nanosleep
#endif
#endif

/**
 * Convert native time seconds to a representable Dea long.
 *
 * Signedness and width are checked before narrowing; failure preserves output.
 *
 * @param value Native seconds value to validate and convert.
 * @param out Non-NULL output receiving seconds only when conversion succeeds.
 * @return True when the value fits; false without writing output otherwise.
 */
dea_bool _rt_time_to_dea_long_sec(time_t value, dea_long *out) {
    if ((time_t)-1 < (time_t)0) {
        if (sizeof(time_t) > sizeof(dea_long) &&
            (value < (time_t)INT64_MIN || value > (time_t)INT64_MAX)) return 0;
    } else if (value > (time_t)INT64_MAX) {
        return 0;
    }
    *out = (dea_long)value;
    return 1;
}

/**
 * Convert Dea long seconds to a representable native time value.
 *
 * @param value Signed seconds to validate and convert.
 * @param out Non-NULL output receiving seconds only when conversion succeeds.
 * @return True when the value fits; false without writing output otherwise.
 */
dea_bool _rt_time_to_time_t(dea_long value, time_t *out) {
    unsigned bits = (unsigned)(sizeof(time_t) * CHAR_BIT);
    if ((time_t)-1 < (time_t)0) {
        if (sizeof(time_t) < sizeof(dea_long)) {
            uintmax_t maximum = (UINTMAX_C(1) << (bits - 1)) - 1;
            if (value < -(intmax_t)maximum - 1 || value > (intmax_t)maximum) return 0;
        }
    } else {
        if (value < 0) return 0;
        if (sizeof(time_t) < sizeof(dea_long) &&
            (uintmax_t)value > (UINTMAX_C(1) << bits) - 1) return 0;
    }
    *out = (time_t)value;
    return 1;
}

/**
 * Internal helper to convert long to dea_int nanoseconds.
 *
 * @param value Nanoseconds to validate and convert.
 * @param out Receives the value only when it is in range.
 * @return Nonzero for values from zero through 999999999; otherwise zero.
 */
dea_bool _rt_time_to_dea_int_nsec(long value, dea_int *out) {
    if (value < 0 || value > 999999999L) return 0;
    *out = (dea_int)value;
    return 1;
}

/**
 * Internal helper to write time parts to struct.
 *
 * @param out Non-NULL time-parts record to populate.
 * @param sec Whole seconds to store.
 * @param nsec Nanoseconds to store.
 * @return One after storing both fields; a NULL output terminates execution.
 */
dea_bool _rt_time_write_parts(struct __deaM3sys2rtS11RtTimeParts *out, dea_long sec, dea_int nsec) {
    if (out == NULL) _rt_panic("_rt_time_write_parts: out-parameter is null");
    out->sec = sec;
    out->nsec = nsec;
    return 1;
}

/**
 * Capture current unix wall clock into `out`.
 *
 * @param out Non-NULL time parts, initialized to zero before host operations.
 * @return One on success, zero on host or representation failure.
 */
dea_bool rt_time_unix(struct __deaM3sys2rtS11RtTimeParts *out) {
    if (out == NULL) _rt_panic("rt_time_unix: out-parameter is null");
    _rt_time_write_parts(out, 0, 0);
#if defined(CLOCK_REALTIME)
    {
        struct timespec ts;
        if (clock_gettime(CLOCK_REALTIME, &ts) == 0) {
            dea_long sec;
            dea_int nsec;
            if (!_rt_time_to_dea_long_sec(ts.tv_sec, &sec) ||
                !_rt_time_to_dea_int_nsec(ts.tv_nsec, &nsec)) return 0;
            return _rt_time_write_parts(out, sec, nsec);
        }
    }
#endif
    {
        time_t now = time(NULL);
        dea_long sec;
        if (now == (time_t)-1 || !_rt_time_to_dea_long_sec(now, &sec)) return 0;
        return _rt_time_write_parts(out, sec, 0);
    }
}

/**
 * Initialize a scalar scheduling result with no captured host error.
 *
 * @param state Scheduling protocol state.
 * @return Zeroed result carrying the supplied state.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_result(dea_int state) {
    struct __deaM3sys4timeS12RtTimeResult result = {0};
    result.state = state;
    return result;
}

#if !defined(_WIN32)

/**
 * Capture an errno scheduling failure before another host operation runs.
 *
 * @param code Saved errno value, or the positive clock_nanosleep result.
 * @return Captured host failure or interruption with the native error intact.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_errno(int code) {
    struct __deaM3sys4timeS12RtTimeResult result = _rt_time_result(
        code == EINTR ? DEA_TIME_INTERRUPTED : DEA_TIME_HOST);
    result.error = rt_os_error_from_errno(code);
    return result;
}

#endif

#if defined(_WIN32)

/**
 * Capture a Win32 scheduling failure before cleanup changes last-error state.
 *
 * @param code Saved Win32 error code.
 * @return Captured host failure retaining the unsigned native code.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_win32(DWORD code) {
    struct __deaM3sys4timeS12RtTimeResult result = _rt_time_result(DEA_TIME_HOST);
    result.error = rt_os_error_from_win32((dea_long)code);
    return result;
}
#endif

#if defined(_WIN32) || defined(DEA_TIME_TESTING)

/**
 * Scale a proper nonnegative fraction to nanoseconds using integer arithmetic.
 *
 * The doubling recurrence never forms the possibly overflowing product of the
 * numerator and one billion. Inputs satisfy numerator < denominator <= INT64_MAX.
 *
 * @param numerator Proper fraction numerator.
 * @param denominator Positive fraction denominator.
 * @return Floor of the fraction multiplied by one billion, below one billion.
 */
static inline dea_int _rt_time_fraction_nsec(dea_ulong numerator, dea_ulong denominator) {
    dea_ulong remainder = 0;
    dea_ulong quotient = 0;
    dea_ulong bit;
    for (bit = UINT64_C(1) << 29; bit != 0; bit >>= 1) {
        quotient *= 2;
        remainder *= 2;
        if (remainder >= denominator) {
            remainder -= denominator;
            quotient++;
        }
        if ((UINT64_C(1000000000) & bit) != 0) {
            remainder += numerator;
            if (remainder >= denominator) {
                remainder -= denominator;
                quotient++;
            }
        }
    }
    return (dea_int)quotient;
}

#endif

/**
 * Read the selected host monotonic clock without a wall-clock fallback.
 *
 * QPC includes suspended time; POSIX follows CLOCK_MONOTONIC's host semantics.
 *
 * @return A validated reading, unsupported source, or captured host failure.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_read_host(void) {
    struct __deaM3sys4timeS12RtTimeResult result = _rt_time_result(DEA_TIME_OK);
#if defined(_WIN32)
    LARGE_INTEGER counter, frequency;
    if (!DEA_TIME_QUERY_FREQUENCY(&frequency)) return _rt_time_win32(GetLastError());
    if (!DEA_TIME_QUERY_COUNTER(&counter)) return _rt_time_win32(GetLastError());
    if (frequency.QuadPart <= 0) return _rt_time_result(DEA_TIME_UNSUPPORTED);
    if (counter.QuadPart < 0) return _rt_time_result(DEA_TIME_OVERFLOW);
    result.sec = counter.QuadPart / frequency.QuadPart;
    result.nsec = _rt_time_fraction_nsec((dea_ulong)(counter.QuadPart % frequency.QuadPart),
                                        (dea_ulong)frequency.QuadPart);
#elif defined(CLOCK_MONOTONIC)
    struct timespec ts;
    if (DEA_TIME_CLOCK_GETTIME(CLOCK_MONOTONIC, &ts) != 0) {
        int saved = errno;
        if (saved == ENOSYS || saved == ENOTSUP || saved == EINVAL)
            return _rt_time_result(DEA_TIME_UNSUPPORTED);
        result = _rt_time_errno(saved);
        result.state = DEA_TIME_HOST;
        return result;
    }
    if (!_rt_time_to_dea_long_sec(ts.tv_sec, &result.sec) || result.sec < 0 ||
        !_rt_time_to_dea_int_nsec(ts.tv_nsec, &result.nsec)) return _rt_time_result(DEA_TIME_OVERFLOW);
#else
    return _rt_time_result(DEA_TIME_UNSUPPORTED);
#endif
    return result;
}

/**
 * Read the monotonic clock as a structured scheduling result.
 *
 * @return Validated nonnegative time, unsupported clock, or captured failure.
 */
struct __deaM3sys4timeS12RtTimeResult rt_time_monotonic_result(void) {
    struct __deaM3sys4timeS12RtTimeResult result = DEA_TIME_READ_CLOCK();
    if (result.state == DEA_TIME_OK && (result.sec < 0 || result.nsec < 0 || result.nsec >= 1000000000))
        return _rt_time_result(DEA_TIME_OVERFLOW);
    return result;
}

/**
 * Capture current monotonic clock into `out`.
 *
 * @param out Non-NULL time parts, initialized to zero before host operations.
 * @return One on success, zero on unavailable clock or captured failure.
 */
dea_bool rt_time_monotonic(struct __deaM3sys2rtS11RtTimeParts *out) {
    struct __deaM3sys4timeS12RtTimeResult result;
    if (out == NULL) _rt_panic("rt_time_monotonic: out-parameter is null");
    _rt_time_write_parts(out, 0, 0);
    result = rt_time_monotonic_result();
    if (result.state != DEA_TIME_OK) return 0;
    return _rt_time_write_parts(out, result.sec, result.nsec);
}

/**
 * Returns whether a monotonic clock source is available.
 *
 * @return One when the platform supplies a monotonic clock, otherwise zero.
 */
dea_bool rt_time_monotonic_supported(void) {
#if defined(_WIN32) || defined(CLOCK_MONOTONIC)
    return 1;
#else
    return 0;
#endif
}

/**
 * Create private non-inheritable host wait state after a future deadline read.
 *
 * @param context Non-NULL output initialized to NULL before native allocation.
 * @return Success with owned state, or captured host failure without ownership.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_open_wait(void **context) {
    *context = NULL;
#if defined(_WIN32)
    *context = DEA_TIME_CREATE_TIMER(NULL, FALSE, NULL);
    if (*context == NULL) return _rt_time_win32(GetLastError());
#endif
    return _rt_time_result(DEA_TIME_OK);
}

#if defined(_WIN32) || defined(DEA_TIME_TESTING)

/**
 * Convert a normalized bounded duration to a rounded-up Windows timer interval.
 *
 * @param sec Whole seconds, either zero or one.
 * @param nsec Nanoseconds, zero when sec is one.
 * @return Negative relative timer ticks in units of 100 nanoseconds.
 */
static inline dea_long _rt_time_windows_ticks(dea_long sec, dea_int nsec) {
    return -(sec * INT64_C(10000000) + ((dea_long)nsec + 99) / 100);
}

#endif

/**
 * Perform one host wait attempt without restarting an interruption.
 *
 * Linux uses an absolute monotonic wait when its seconds fit native time_t;
 * fallback relative waits are bounded to one second before native conversion.
 *
 * @param context Owned native timer on Windows; unused on POSIX.
 * @param deadline_sec Original deadline whole seconds.
 * @param deadline_nsec Original deadline normalized nanoseconds.
 * @param remaining_sec Nonnegative remaining seconds, bounded on relative paths.
 * @param remaining_nsec Remaining normalized nanoseconds.
 * @return Success wakeup, captured interruption, or captured host failure.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_wait_once(
    void *context, dea_long deadline_sec, dea_int deadline_nsec,
    dea_long remaining_sec, dea_int remaining_nsec) {
#if defined(_WIN32)
    LARGE_INTEGER due;
    DWORD waited;
    (void)deadline_sec;
    (void)deadline_nsec;
    due.QuadPart = _rt_time_windows_ticks(remaining_sec, remaining_nsec);
    if (!DEA_TIME_SET_TIMER((HANDLE)context, &due, 0, NULL, NULL, FALSE))
        return _rt_time_win32(GetLastError());
    waited = DEA_TIME_WAIT_TIMER((HANDLE)context, INFINITE);
    if (waited == WAIT_FAILED) return _rt_time_win32(GetLastError());
    if (waited != WAIT_OBJECT_0) return _rt_time_win32(ERROR_GEN_FAILURE);
#else
    struct timespec request;
    (void)context;
#if defined(__linux__) && defined(CLOCK_MONOTONIC) && !DEA_TIME_BOUNDED_WAIT
    if (_rt_time_to_time_t(deadline_sec, &request.tv_sec)) {
        int code;
        request.tv_nsec = deadline_nsec;
        code = DEA_TIME_CLOCK_NANOSLEEP(CLOCK_MONOTONIC, TIMER_ABSTIME, &request, NULL);
        if (code == 0) return _rt_time_result(DEA_TIME_OK);
        if (code != ENOSYS && code != ENOTSUP) return _rt_time_errno(code);
    }
#endif
    (void)deadline_sec;
    (void)deadline_nsec;
    if (remaining_sec >= 1) {
        remaining_sec = 1;
        remaining_nsec = 0;
    }
    if (!_rt_time_to_time_t(remaining_sec, &request.tv_sec)) return _rt_time_result(DEA_TIME_OVERFLOW);
    request.tv_nsec = remaining_nsec;
    if (DEA_TIME_NANOSLEEP(&request, NULL) != 0) {
        int saved = errno;
        return _rt_time_errno(saved);
    }
#endif
    return _rt_time_result(DEA_TIME_OK);
}

/**
 * Release native wait state and capture any cleanup failure immediately.
 *
 * @param context Owned native timer on Windows; unused on POSIX.
 * @return Success after release, or the captured cleanup failure.
 */
static struct __deaM3sys4timeS12RtTimeResult _rt_time_close_wait(void *context) {
#if defined(_WIN32)
    if (!DEA_TIME_CLOSE_TIMER((HANDLE)context)) return _rt_time_win32(GetLastError());
#else
    (void)context;
#endif
    return _rt_time_result(DEA_TIME_OK);
}

/**
 * Wait for an absolute monotonic deadline with explicit interruption semantics.
 *
 * Early wakeups recheck the original deadline. Relative host waits use at most
 * one second, including Windows suspend-accounting differences. An interruption
 * wins over a simultaneous deadline crossing. Cleanup preserves a primary error.
 *
 * @param sec Nonnegative deadline seconds in the current monotonic clock epoch.
 * @param nsec Normalized deadline nanoseconds, from zero through 999999999.
 * @return Completion, invalid deadline, unsupported clock, or captured failure.
 */
struct __deaM3sys4timeS12RtTimeResult rt_time_sleep_until(dea_long sec, dea_int nsec) {
    struct __deaM3sys4timeS12RtTimeResult result, cleanup;
    void *context = NULL;
    dea_bool opened = 0;
    if (sec < 0 || nsec < 0 || nsec >= 1000000000) return _rt_time_result(DEA_TIME_INVALID);
    for (;;) {
        dea_long remaining_sec;
        dea_int remaining_nsec;
        result = rt_time_monotonic_result();
        if (result.state != DEA_TIME_OK) break;
        if (sec < result.sec || (sec == result.sec && nsec <= result.nsec)) {
            result = _rt_time_result(DEA_TIME_OK);
            break;
        }
        remaining_sec = sec - result.sec;
        remaining_nsec = nsec - result.nsec;
        if (remaining_nsec < 0) {
            remaining_sec--;
            remaining_nsec += 1000000000;
        }
#if DEA_TIME_BOUNDED_WAIT
        if (remaining_sec >= 1) {
            remaining_sec = 1;
            remaining_nsec = 0;
        }
#endif
        if (!opened) {
            result = DEA_TIME_OPEN_WAIT(&context);
            if (result.state != DEA_TIME_OK) break;
            opened = 1;
        }
        result = DEA_TIME_WAIT_ONCE(context, sec, nsec, remaining_sec, remaining_nsec);
        if (result.state != DEA_TIME_OK) break;
    }
    if (opened) {
        cleanup = DEA_TIME_CLOSE_WAIT(context);
        if (result.state == DEA_TIME_OK && cleanup.state != DEA_TIME_OK) result = cleanup;
    }
    if (result.state == DEA_TIME_INTERRUPTED) {
        result.sec = sec;
        result.nsec = nsec;
    }
    return result;
}

/**
 * Returns local UTC offset in seconds for `unix_sec`.
 *
 * Computes the offset by comparing `gmtime` and `localtime` breakdowns
 * directly, avoiding `mktime` which rejects pre-epoch values on some platforms.
 *
 * Dea signature: `extern func rt_time_local_offset_sec(unix_sec: long) -> int?;`
 *
 * @param unix_sec Unix timestamp.
 * @return Optional integer offset.
 */
dea_opt_int rt_time_local_offset_sec(dea_long unix_sec) {
    time_t t;
    if (!_rt_time_to_time_t(unix_sec, &t)) {
        return (dea_opt_int){ .has_value = 0 };
    }

    struct tm *utc_ptr = gmtime(&t);
    if (utc_ptr == NULL) {
        return (dea_opt_int){ .has_value = 0 };
    }
    struct tm utc_tm = *utc_ptr;

    struct tm *local_ptr = localtime(&t);
    if (local_ptr == NULL) {
        return (dea_opt_int){ .has_value = 0 };
    }
    struct tm local_tm = *local_ptr;

    /* Day difference: can only be -1, 0, or +1 for timezone offsets. */
    int day_diff;
    if (local_tm.tm_year > utc_tm.tm_year) {
        day_diff = 1;
    } else if (local_tm.tm_year < utc_tm.tm_year) {
        day_diff = -1;
    } else {
        day_diff = local_tm.tm_yday - utc_tm.tm_yday;
    }

    long long offset = (long long)day_diff * 86400
                     + (long long)(local_tm.tm_hour - utc_tm.tm_hour) * 3600
                     + (long long)(local_tm.tm_min - utc_tm.tm_min) * 60
                     + (long long)(local_tm.tm_sec - utc_tm.tm_sec);
    if (offset < INT32_MIN || offset > INT32_MAX) {
        return (dea_opt_int){ .has_value = 0 };
    }

    return (dea_opt_int){ .has_value = 1, .value = (dea_int)offset };
}

/**
 * Returns whether local time is daylight-saving time for `unix_sec`.
 *
 * Dea signature: `extern func rt_time_local_is_dst(unix_sec: long) -> bool?;`
 *
 * @param unix_sec Unix timestamp.
 * @return Optional boolean.
 */
dea_opt_bool rt_time_local_is_dst(dea_long unix_sec) {
    time_t t;
    if (!_rt_time_to_time_t(unix_sec, &t)) {
        return (dea_opt_bool){ .has_value = 0 };
    }

    struct tm *local_ptr = localtime(&t);
    if (local_ptr == NULL) {
        return (dea_opt_bool){ .has_value = 0 };
    }

    if (local_ptr->tm_isdst < 0) {
        return (dea_opt_bool){ .has_value = 0 };
    }
    return (dea_opt_bool){ .has_value = 1, .value = local_ptr->tm_isdst > 0 ? 1 : 0 };
}
