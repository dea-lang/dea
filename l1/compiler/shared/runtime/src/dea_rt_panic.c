/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for the failure path: panic primitives, optional unwrap
 * helpers, and the public abort wrapper.
 * ========================================================================= */

/**
 * Abort the program with a message.
 *
 * @param message The panic message.
 */
void _rt_panic(const char* message) {
    if (message == NULL) {
        message = "Guru Meditation";
    }
    fflush(stdout);
    fprintf(stderr, "Software Failure: %s\n", message);
    fflush(stderr);
    abort();
}

/**
 * Abort the program with a formatted message.
 *
 * @param fmt Format string.
 */
void _rt_panic_fmt(const char* fmt, ...) {
    va_list args;
    fflush(stdout);
    fprintf(stderr, "Software Failure: ");
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
    fflush(stderr);
    abort();
}

void _rt_panic_oob(dea_int index, dea_int length) {
    _rt_panic_fmt("array index %d out of bounds for length %d", (int)index, (int)length);
}

void *_unwrap_ptr(void *opt, const char *type_name) {
    if (opt == NULL) {
        _rt_panic_fmt("unwrap of empty optional: '%s'", type_name);
    }
    return opt;
}

/**
 * Unwrap an optional type structure, panicking if it has no value.
 *
 * @param opt_ptr Pointer to the optional structure.
 * @param type_name Name of the type for error reporting.
 * @return Pointer to the optional structure.
 */
void *_unwrap_opt(void *opt_ptr, const char *type_name) {
    _dea_base_opt *base = (_dea_base_opt*)opt_ptr;
    if (!base->has_value) {
        _rt_panic_fmt("unwrap of empty optional: '%s'", type_name);
    }
    return opt_ptr;
}

/**
 * Abort the program with a panic message.
 *
 * @param message Panic message.
 *
 * L0 signature: `extern func rt_abort(message: string) -> void;`
 */
void rt_abort(dea_string message) {
    if (rt_strlen(message) == 0) {
        _rt_panic(NULL);
    } else {
        _rt_panic_fmt("%s", _rt_string_bytes(message));
    }
    abort();
}
