/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

#if defined(_WIN32)
#include <windows.h>
#endif

/* =========================================================================
 * Runtime support for OS/process interaction: shell exec, environment, args,
 * process identifier, errno, and process exit.
 * ========================================================================= */

/* -------------------------------------------------------------------------
 * Argument handling internal state
 * ------------------------------------------------------------------------- */

static int _rt_argc = 0;
static char** _rt_argv = NULL;

/**
 * Initialize command-line arguments.
 *
 * @param argc Number of arguments.
 * @param argv Argument vector.
 */
void _rt_init_args(int argc, char** argv) {
#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)
    _rt_trace_init();
#endif
    _rt_argc = argc;
    _rt_argv = argv;
}

/* -------------------------------------------------------------------------
 * System interaction and environment
 * ------------------------------------------------------------------------- */

/**
 * Execute a system command and return its normalized status.
 * Returns the command exit code, `128 + signal` when terminated by a signal,
 * or a negative value on error launching the shell.
 *
 * @param cmd Command string.
 * @return Normalized status.
 *
 * Dea signature: `extern func rt_system(cmd: string) -> int;`
 */
dea_int rt_system(dea_string cmd) {
    char *c = _rt_string_bytes(cmd);
#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)
    _rt_trace_flush_pending();
#endif
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
 * Get an environment variable as a Dea optional string.
 * Returns null (empty optional) if the variable is not set.
 *
 * @param name Variable name.
 * @return Optional string value.
 *
 * Dea signature: `extern func rt_get_env_var(name: string) -> string?;`
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
 * Dea signature: `extern func rt_get_pid() -> int;`
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
 * Get the number of command-line arguments.
 *
 * @return Argument count.
 *
 * Dea signature: `extern func rt_get_argc() -> int;`
 */
dea_int rt_get_argc(void) {
    return (dea_int)_rt_argc;
}

/**
 * Get the command-line argument at the given index.
 * Panics if index is out of bounds.
 *
 * @param i Index.
 * @return Argument string.
 *
 * Dea signature: `extern func rt_get_argv(i: int) -> string;`
 */
dea_string rt_get_argv(dea_int i) {
    if (i < 0 || i >= _rt_argc) {
        _rt_panic_fmt("rt_get_argv: index %d out of bounds (argc=%d)", (int)i, _rt_argc);
    }
    return _rt_dea_string_from_const_literal(_rt_argv[i]);
}

/**
 * Exit the program with the given exit code.
 *
 * @param code Exit code.
 *
 * Dea signature: `extern func rt_exit(code: int) -> void;`
 */
void rt_exit(dea_int code) {
    exit((int)code);
}

/**
 * Get the current C standard library `errno` value from `<errno.h>`.
 *
 * @return the current `errno` value.
 */
dea_int rt_errno(void) {
    return (dea_int)errno;
}

/**
 * Normalize a C library error without assuming that errno aliases differ.
 *
 * @param code Saved C library error code.
 * @return Stable `sys.os` error-kind transport tag.
 */
static dea_int _rt_os_errno_kind(dea_int code) {
    if (code == ENOENT) return DEA_OS_ERROR_NOT_FOUND;
    if (code == EACCES || code == EPERM) return DEA_OS_ERROR_PERMISSION_DENIED;
#ifdef EROFS
    if (code == EROFS) return DEA_OS_ERROR_PERMISSION_DENIED;
#endif
    if (code == EEXIST) return DEA_OS_ERROR_ALREADY_EXISTS;
    if (code == EINVAL) return DEA_OS_ERROR_INVALID_INPUT;
#ifdef ENAMETOOLONG
    if (code == ENAMETOOLONG) return DEA_OS_ERROR_INVALID_INPUT;
#endif
    if (code == EBADF) return DEA_OS_ERROR_INVALID_HANDLE;
    if (code == EINTR) return DEA_OS_ERROR_INTERRUPTED;
    if (code == EAGAIN) return DEA_OS_ERROR_WOULD_BLOCK;
#ifdef EWOULDBLOCK
    if (code == EWOULDBLOCK) return DEA_OS_ERROR_WOULD_BLOCK;
#endif
    if (code == EPIPE) return DEA_OS_ERROR_BROKEN_PIPE;
#ifdef ETIMEDOUT
    if (code == ETIMEDOUT) return DEA_OS_ERROR_TIMED_OUT;
#endif
#ifdef ENOSYS
    if (code == ENOSYS) return DEA_OS_ERROR_UNSUPPORTED;
#endif
#ifdef ENOTSUP
    if (code == ENOTSUP) return DEA_OS_ERROR_UNSUPPORTED;
#endif
#ifdef EOPNOTSUPP
    if (code == EOPNOTSUPP) return DEA_OS_ERROR_UNSUPPORTED;
#endif
#ifdef ESPIPE
    if (code == ESPIPE) return DEA_OS_ERROR_NOT_SEEKABLE;
#endif
    if (code == ENOMEM) return DEA_OS_ERROR_OUT_OF_MEMORY;
    if (code == EMFILE) return DEA_OS_ERROR_RESOURCE_EXHAUSTED;
#ifdef ENFILE
    if (code == ENFILE) return DEA_OS_ERROR_RESOURCE_EXHAUSTED;
#endif
#ifdef EBUSY
    if (code == EBUSY) return DEA_OS_ERROR_RESOURCE_EXHAUSTED;
#endif
#ifdef ENOBUFS
    if (code == ENOBUFS) return DEA_OS_ERROR_RESOURCE_EXHAUSTED;
#endif
    if (code == EIO) return DEA_OS_ERROR_IO_ERROR;
#ifdef ENXIO
    if (code == ENXIO) return DEA_OS_ERROR_IO_ERROR;
#endif
#ifdef EISDIR
    if (code == EISDIR) return DEA_OS_ERROR_IS_DIRECTORY;
#endif
    if (code == ENOTDIR) return DEA_OS_ERROR_NOT_DIRECTORY;
#ifdef ENOTEMPTY
    if (code == ENOTEMPTY) return DEA_OS_ERROR_DIRECTORY_NOT_EMPTY;
#endif
    if (code == ENOSPC) return DEA_OS_ERROR_NO_SPACE;
#ifdef EDQUOT
    if (code == EDQUOT) return DEA_OS_ERROR_NO_SPACE;
#endif
    if (code == EFBIG) return DEA_OS_ERROR_FILE_TOO_LARGE;
    return DEA_OS_ERROR_OTHER;
}

/**
 * Capture a supplied errno code as a self-contained OS error.
 *
 * @param native_code Saved errno value, including unknown values.
 * @return Normalized error retaining the original code and Errno domain.
 */
struct __deaM3sys2osS9RtOsError rt_os_error_from_errno(dea_int native_code) {
    return (struct __deaM3sys2osS9RtOsError){
        .kind = _rt_os_errno_kind(native_code),
        .domain = DEA_OS_DOMAIN_ERRNO,
        .native_code = native_code,
    };
}

/**
 * Normalize stable Win32 system-error numbers on every supported host.
 *
 * Numeric cases are WinError.h values, not the host's errno constants. Keeping
 * the table host-independent permits portable mapping probes without pretending
 * to exercise native Windows operations or message rendering.
 *
 * @param code Saved Win32 error code.
 * @return Stable `sys.os` error-kind transport tag.
 */
static dea_int _rt_os_win32_kind(dea_long code) {
    switch (code) {
    case 2: /* ERROR_FILE_NOT_FOUND */
    case 3: /* ERROR_PATH_NOT_FOUND */
    case 15: /* ERROR_INVALID_DRIVE */
    case 53: /* ERROR_BAD_NETPATH */
    case 67: /* ERROR_BAD_NET_NAME */
    case 1168: /* ERROR_NOT_FOUND */
        return DEA_OS_ERROR_NOT_FOUND;
    case 5: /* ERROR_ACCESS_DENIED */
    case 19: /* ERROR_WRITE_PROTECT */
    case 65: /* ERROR_NETWORK_ACCESS_DENIED */
        return DEA_OS_ERROR_PERMISSION_DENIED;
    case 80: /* ERROR_FILE_EXISTS */
    case 183: /* ERROR_ALREADY_EXISTS */
        return DEA_OS_ERROR_ALREADY_EXISTS;
    case 87: /* ERROR_INVALID_PARAMETER */
    case 123: /* ERROR_INVALID_NAME */
    case 131: /* ERROR_NEGATIVE_SEEK */
    case 161: /* ERROR_BAD_PATHNAME */
    case 1113: /* ERROR_NO_UNICODE_TRANSLATION */
    case 206: /* ERROR_FILENAME_EXCED_RANGE */
        return DEA_OS_ERROR_INVALID_INPUT;
    case 6: /* ERROR_INVALID_HANDLE */
        return DEA_OS_ERROR_INVALID_HANDLE;
    case 995: /* ERROR_OPERATION_ABORTED */
        return DEA_OS_ERROR_INTERRUPTED;
    case 231: /* ERROR_PIPE_BUSY */
        return DEA_OS_ERROR_WOULD_BLOCK;
    case 109: /* ERROR_BROKEN_PIPE */
    case 232: /* ERROR_NO_DATA */
    case 233: /* ERROR_PIPE_NOT_CONNECTED */
        return DEA_OS_ERROR_BROKEN_PIPE;
    case 121: /* ERROR_SEM_TIMEOUT */
    case 258: /* WAIT_TIMEOUT */
    case 1460: /* ERROR_TIMEOUT */
        return DEA_OS_ERROR_TIMED_OUT;
    case 1: /* ERROR_INVALID_FUNCTION */
    case 50: /* ERROR_NOT_SUPPORTED */
    case 120: /* ERROR_CALL_NOT_IMPLEMENTED */
        return DEA_OS_ERROR_UNSUPPORTED;
    case 132: /* ERROR_SEEK_ON_DEVICE */
        return DEA_OS_ERROR_NOT_SEEKABLE;
    case 8: /* ERROR_NOT_ENOUGH_MEMORY */
    case 14: /* ERROR_OUTOFMEMORY */
        return DEA_OS_ERROR_OUT_OF_MEMORY;
    case 4: /* ERROR_TOO_MANY_OPEN_FILES */
    case 32: /* ERROR_SHARING_VIOLATION */
    case 33: /* ERROR_LOCK_VIOLATION */
    case 1450: /* ERROR_NO_SYSTEM_RESOURCES */
    case 1816: /* ERROR_NOT_ENOUGH_QUOTA */
        return DEA_OS_ERROR_RESOURCE_EXHAUSTED;
    case 23: /* ERROR_CRC */
    case 29: /* ERROR_WRITE_FAULT */
    case 30: /* ERROR_READ_FAULT */
    case 31: /* ERROR_GEN_FAILURE */
    case 1117: /* ERROR_IO_DEVICE */
        return DEA_OS_ERROR_IO_ERROR;
    case 267: /* ERROR_DIRECTORY */
        return DEA_OS_ERROR_NOT_DIRECTORY;
    case 145: /* ERROR_DIR_NOT_EMPTY */
        return DEA_OS_ERROR_DIRECTORY_NOT_EMPTY;
    case 39: /* ERROR_HANDLE_DISK_FULL */
    case 112: /* ERROR_DISK_FULL */
        return DEA_OS_ERROR_NO_SPACE;
    case 223: /* ERROR_FILE_TOO_LARGE */
        return DEA_OS_ERROR_FILE_TOO_LARGE;
    default:
        return DEA_OS_ERROR_OTHER;
    }
}

/**
 * Capture a supplied Win32 code without truncating its unsigned DWORD range.
 *
 * @param native_code Saved native code, including unknown values.
 * @return Normalized error retaining the original code and Win32 domain.
 */
struct __deaM3sys2osS9RtOsError rt_os_error_from_win32(dea_long native_code) {
    return (struct __deaM3sys2osS9RtOsError){
        .kind = _rt_os_win32_kind(native_code),
        .domain = DEA_OS_DOMAIN_WIN32,
        .native_code = native_code,
    };
}

/**
 * Name a normalized category for diagnostic fallbacks.
 *
 * @param kind Stable error-kind tag, including unknown values.
 * @return Static category name; unrecognized tags use Other.
 */
static const char *_rt_os_kind_name(dea_int kind) {
    switch (kind) {
    case DEA_OS_ERROR_NOT_FOUND: return "NotFound";
    case DEA_OS_ERROR_PERMISSION_DENIED: return "PermissionDenied";
    case DEA_OS_ERROR_ALREADY_EXISTS: return "AlreadyExists";
    case DEA_OS_ERROR_INVALID_INPUT: return "InvalidInput";
    case DEA_OS_ERROR_INVALID_HANDLE: return "InvalidHandle";
    case DEA_OS_ERROR_INTERRUPTED: return "Interrupted";
    case DEA_OS_ERROR_WOULD_BLOCK: return "WouldBlock";
    case DEA_OS_ERROR_BROKEN_PIPE: return "BrokenPipe";
    case DEA_OS_ERROR_TIMED_OUT: return "TimedOut";
    case DEA_OS_ERROR_UNSUPPORTED: return "Unsupported";
    case DEA_OS_ERROR_NOT_SEEKABLE: return "NotSeekable";
    case DEA_OS_ERROR_OUT_OF_MEMORY: return "OutOfMemory";
    case DEA_OS_ERROR_RESOURCE_EXHAUSTED: return "ResourceExhausted";
    case DEA_OS_ERROR_IO_ERROR: return "IoError";
    case DEA_OS_ERROR_IS_DIRECTORY: return "IsDirectory";
    case DEA_OS_ERROR_NOT_DIRECTORY: return "NotDirectory";
    case DEA_OS_ERROR_DIRECTORY_NOT_EMPTY: return "DirectoryNotEmpty";
    case DEA_OS_ERROR_NO_SPACE: return "NoSpace";
    case DEA_OS_ERROR_FILE_TOO_LARGE: return "FileTooLarge";
    default: return "Other";
    }
}

/**
 * Render an OS error using its saved domain and code, never ambient error state.
 *
 * @param error Captured error to describe.
 * @return Owned diagnostic string; wording may depend on the host locale.
 */
dea_string rt_os_error_message(struct __deaM3sys2osS9RtOsError error) {
    char fallback[128];
    if (error.domain == DEA_OS_DOMAIN_ERRNO) {
        if (error.native_code > 0 && error.native_code <= INT32_MAX &&
            _rt_os_errno_kind((dea_int)error.native_code) != DEA_OS_ERROR_OTHER) {
            const char *message = strerror((int)error.native_code);
            if (message != NULL && message[0] != '\0') {
                return _rt_new_dea_string(message);
            }
        }
        snprintf(fallback, sizeof(fallback), "%s (Errno error %" PRId64 ")",
                 _rt_os_kind_name(error.kind), (int64_t)error.native_code);
    } else if (error.domain == DEA_OS_DOMAIN_WIN32) {
#if defined(_WIN32)
        if (error.native_code > 0 && (uint64_t)error.native_code <= UINT32_MAX) {
            WCHAR *message = NULL;
            DWORD length = FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
                                          FORMAT_MESSAGE_IGNORE_INSERTS,
                                          NULL, (DWORD)error.native_code, 0, (LPWSTR)&message, 0, NULL);
            if (message != NULL) {
                while (length > 0 && (message[length - 1] == L'\r' || message[length - 1] == L'\n')) {
                    length -= 1;
                }
                if (length > 0 && length <= INT32_MAX) {
                    int bytes = WideCharToMultiByte(CP_UTF8, 0, message, (int)length, NULL, 0, NULL, NULL);
                    if (bytes > 0) {
                        dea_string result = _rt_alloc_string((dea_int)bytes);
                        int converted = WideCharToMultiByte(CP_UTF8, 0, message, (int)length,
                                                            _rt_string_bytes(result), bytes, NULL, NULL);
                        LocalFree(message);
                        if (converted == bytes) return result;
                        _rt_free_string(result);
                        message = NULL;
                    }
                }
                if (message != NULL) LocalFree(message);
            }
        }
#endif
        snprintf(fallback, sizeof(fallback), "%s (Win32 error %" PRId64 ")",
                 _rt_os_kind_name(error.kind), (int64_t)error.native_code);
    } else if (error.domain == DEA_OS_DOMAIN_RUNTIME) {
        snprintf(fallback, sizeof(fallback), "%s (Runtime error %" PRId64 ")",
                 _rt_os_kind_name(error.kind), (int64_t)error.native_code);
    } else {
        snprintf(fallback, sizeof(fallback), "%s (OS error domain %" PRId32 ": code %" PRId64 ")",
                 _rt_os_kind_name(error.kind), (int32_t)error.domain, (int64_t)error.native_code);
    }
    return _rt_new_dea_string(fallback);
}
