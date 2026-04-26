/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

dea_bool _rt_time_to_dea_int_sec(time_t value, dea_int *out) {
    long long sec = (long long)value;
    if (sec < INT32_MIN || sec > INT32_MAX) {
        return 0;
    }
    *out = (dea_int)sec;
    return 1;
}

/**
 * Internal helper to convert long to dea_int nanoseconds.
 */
dea_bool _rt_time_to_dea_int_nsec(long value, dea_int *out) {
    long long nsec = (long long)value;
    if (nsec < 0 || nsec > 999999999LL) {
        return 0;
    }
    *out = (dea_int)nsec;
    return 1;
}

/**
 * Internal helper to write time parts to struct.
 */
dea_bool _rt_time_write_parts(struct dea_sys_rt_RtTimeParts *out, dea_int sec, dea_int nsec) {
    if (out == NULL) {
        _rt_panic("_rt_time_write_parts: out-parameter is null");
    }
    out->sec = sec;
    out->nsec = nsec;
    return 1;
}

/**
 * Capture current unix wall clock into `out`.
 *
 * @param out Pointer to RtTimeParts.
 * @return 1 on success, 0 on failure.
 *
 * L0 signature: `extern func rt_time_unix(out: RtTimeParts*) -> bool;`
 */
dea_bool rt_time_unix(struct dea_sys_rt_RtTimeParts *out) {
    if (out == NULL) {
        _rt_panic("rt_time_unix: out-parameter is null");
    }

#if defined(CLOCK_REALTIME)
    struct timespec ts;
    if (clock_gettime(CLOCK_REALTIME, &ts) == 0) {
        dea_int sec = 0;
        dea_int nsec = 0;
        if (!_rt_time_to_dea_int_sec(ts.tv_sec, &sec)) {
            return 0;
        }
        if (!_rt_time_to_dea_int_nsec(ts.tv_nsec, &nsec)) {
            return 0;
        }
        return _rt_time_write_parts(out, sec, nsec);
    }
#endif

    time_t now = time(NULL);
    if (now == (time_t)-1) {
        return 0;
    }

    dea_int sec = 0;
    if (!_rt_time_to_dea_int_sec(now, &sec)) {
        return 0;
    }
    return _rt_time_write_parts(out, sec, 0);
}

/**
 * Capture current monotonic clock into `out`.
 *
 * @param out Pointer to RtTimeParts.
 * @return 1 on success, 0 on failure.
 *
 * L0 signature: `extern func rt_time_monotonic(out: RtTimeParts*) -> bool;`
 */
dea_bool rt_time_monotonic(struct dea_sys_rt_RtTimeParts *out) {
    if (out == NULL) {
        _rt_panic("rt_time_monotonic: out-parameter is null");
    }

#if defined(CLOCK_MONOTONIC)
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }

    dea_int sec = 0;
    dea_int nsec = 0;
    if (!_rt_time_to_dea_int_sec(ts.tv_sec, &sec)) {
        return 0;
    }
    if (!_rt_time_to_dea_int_nsec(ts.tv_nsec, &nsec)) {
        return 0;
    }
    return _rt_time_write_parts(out, sec, nsec);
#else
    (void)out;
    return 0;
#endif
}

/**
 * Returns whether a monotonic clock source is available.
 *
 * @return 1 if supported, 0 otherwise.
 *
 * L0 signature: `extern func rt_time_monotonic_supported() -> bool;`
 */
dea_bool rt_time_monotonic_supported(void) {
#if defined(CLOCK_MONOTONIC)
    return 1;
#else
    return 0;
#endif
}

/**
 * Returns local UTC offset in seconds for `unix_sec`.
 *
 * Computes the offset by comparing `gmtime` and `localtime` breakdowns
 * directly, avoiding `mktime` which rejects pre-epoch values on some platforms.
 *
 * @param unix_sec Unix timestamp.
 * @return Optional integer offset.
 *
 * L0 signature: `extern func rt_time_local_offset_sec(unix_sec: int) -> int?;`
 */
dea_opt_int rt_time_local_offset_sec(dea_int unix_sec) {
    time_t t = (time_t)unix_sec;
    if ((dea_int)t != unix_sec) {
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
 * @param unix_sec Unix timestamp.
 * @return Optional boolean.
 *
 * L0 signature: `extern func rt_time_local_is_dst(unix_sec: int) -> bool?;`
 */
dea_opt_bool rt_time_local_is_dst(dea_int unix_sec) {
    time_t t = (time_t)unix_sec;
    if ((dea_int)t != unix_sec) {
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
