/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Argument handling
 * ========================================================================= */

static int _rt_argc = 0;
static char** _rt_argv = NULL;

/**
 * Initialize command-line arguments.
 *
 * @param argc Number of arguments.
 * @param argv Argument vector.
 */
void _rt_init_args(int argc, char** argv) {
    _rt_argc = argc;
    _rt_argv = argv;
}

/* =========================================================================
 * Panic mechanism
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

/* =========================================================================
 * System interaction and environment
 * ========================================================================= */

/**
 * Execute a system command and return its normalized status.
 * Returns the command exit code, `128 + signal` when terminated by a signal,
 * or a negative value on error launching the shell.
 *
 * @param cmd Command string.
 * @return Normalized status.
 *
 * L0 signature: `extern func rt_system(cmd: string) -> int;`
 */
dea_int rt_system(dea_string cmd) {
    char *c = _rt_string_bytes(cmd);
    int status = system(c);
#if defined(_WIN32)
    return (dea_int)status;
#else
    if (status < 0) {
        return (dea_int)status;
    }
    if (WIFEXITED(status)) {
        return (dea_int)WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return (dea_int)(128 + WTERMSIG(status));
    }
    return (dea_int)status;
#endif
}

/**
 * Get an environment variable as an L0 optional string.
 * Returns null (empty optional) if the variable is not set.
 *
 * @param name Variable name.
 * @return Optional string value.
 *
 * L0 signature: `extern func rt_get_env_var(name: string) -> string?;`
 */
dea_opt_string rt_get_env_var(dea_string name) {
    if (rt_strlen(name) == 0) {
        return DEA_OPT_STRING_NULL;
    }

    /* Get the underlying null-terminated char[] */
    char *c_name = _rt_string_bytes(name);
    if (c_name == NULL) {
        return DEA_OPT_STRING_NULL;
    }

    /* Get environment variable */
    char *c_value = getenv(c_name);

    if (c_value == NULL) {
        return DEA_OPT_STRING_NULL;
    }

    /* Convert value to L0 string*? */
    dea_string result = _rt_new_dea_string(c_value);
    return (dea_opt_string){ .has_value = 1, .value = result };
}

/**
 * Get the number of command-line arguments.
 *
 * @return Argument count.
 *
 * L0 signature: `extern func rt_get_argc() -> int;`
 */
dea_int rt_get_argc(void) {
    return (dea_int)_rt_argc;
}

/**
 * Convert a native process identifier into `dea_int`.
 *
 * @param value Native process identifier.
 * @param out Output location.
 * @return 1 when `value` fits in `dea_int`, otherwise 0.
 */
dea_bool _rt_pid_to_dea_int(intmax_t value, dea_int *out) {
    if (value < 0 || value > INT32_MAX) {
        return 0;
    }
    *out = (dea_int)value;
    return 1;
}

/**
 * Get the current process identifier.
 *
 * @return Process identifier.
 *
 * L0 signature: `extern func rt_get_pid() -> int;`
 */
dea_int rt_get_pid(void) {
    dea_int out = 0;
#if defined(_WIN32)
    if (!_rt_pid_to_dea_int((intmax_t)_getpid(), &out)) {
        _rt_panic("rt_get_pid: process identifier does not fit in dea_int");
    }
#else
    if (!_rt_pid_to_dea_int((intmax_t)getpid(), &out)) {
        _rt_panic("rt_get_pid: process identifier does not fit in dea_int");
    }
#endif
    return out;
}

/**
 * Get the command-line argument at the given index.
 * Panics if index is out of bounds.
 *
 * @param i Index.
 * @return Argument string.
 *
 * L0 signature: `extern func rt_get_argv(i: int) -> string;`
 */
dea_string rt_get_argv(dea_int i) {
    if (i < 0 || i >= _rt_argc) {
        _rt_panic_fmt("rt_get_argv: index %d out of bounds (argc=%d)", (int)i, _rt_argc);
    }
    return _rt_dea_string_from_const_literal(_rt_argv[i]);
}

void rt_abort(dea_string message) {
    if (rt_strlen(message) == 0) {
        _rt_panic(NULL);
    } else {
        _rt_panic_fmt("%s", _rt_string_bytes(message));
    }
    abort();
}

/**
 * Exit the program with the given exit code.
 *
 * @param code Exit code.
 *
 * L0 signature: `extern func rt_exit(code: int) -> void;`
 */
void rt_exit(dea_int code) {
    exit((int)code);
}

dea_int rt_errno(void) {
    return (dea_int)errno;
}
