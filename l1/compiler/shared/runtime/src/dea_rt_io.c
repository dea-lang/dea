/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for file I/O and metadata, stdin/stdout/stderr stream I/O,
 * formatted printing of dea values (strings, integers, floats, booleans),
 * stream flushing, and line/char reading.
 * ========================================================================= */

/**
 * Read entire file contents into a string.
 * Returns empty optional on error (file not found, read error, allocation failure).
 *
 * @param path File path.
 * @return Optional string containing file contents.
 *
 * Dea signature: `extern func rt_read_file_all(path: string) -> string?;`
 */
dea_opt_string rt_read_file_all(dea_string path) {

    dea_int path_len = rt_strlen(path);

    if (path_len == 0) {
        return DEA_OPT_STRING_NULL;
    }

    char *path_cstr = _rt_string_bytes(path);
    struct stat st;

    if (stat(path_cstr, &st) != 0) {
        return DEA_OPT_STRING_NULL;
    }
    if (!S_ISREG(st.st_mode)) {
        return DEA_OPT_STRING_NULL;
    }
    if (st.st_size < 0 || (uint64_t)st.st_size > INT32_MAX) {
        return DEA_OPT_STRING_NULL;
    }

    FILE *file = fopen(path_cstr, "rb");
    if (file == NULL) {
        return DEA_OPT_STRING_NULL;
    }

    size_t size = (size_t)st.st_size;

    dea_string result = _rt_alloc_string((dea_int)size);
    char *buffer = _rt_string_bytes(result);

    /* Read file contents */
    size_t bytes_read = fread(buffer, 1, size, file);
    fclose(file);

    if (bytes_read != size) {
        _rt_free_string(result);
        return DEA_OPT_STRING_NULL;
    }

    return (dea_opt_string){ .has_value = 1, .value = result };
}

/**
 * Write string data to a file.
 * Returns 1 (true) on success, 0 (false) on error.
 *
 * @param path File path.
 * @param data Data string.
 * @return 1 on success, 0 on failure.
 *
 * Dea signature: `extern func rt_write_file_all(path: string, data: string) -> bool;`
 */
dea_bool rt_write_file_all(dea_string path, dea_string data) {
    dea_int path_len = rt_strlen(path);
    if (path_len == 0) {
        return 0;
    }

    /* Ensure path is null-terminated for fopen */
    char *path_cstr = _rt_string_bytes(path);
    FILE *file = fopen(path_cstr, "wb");
    if (file == NULL) {
        return 0;
    }

    dea_int data_len = rt_strlen(data);
    char *data_b = _rt_string_bytes(data);
    if (data_len > 0) {
        size_t written = fwrite(data_b, 1, (size_t)data_len, file);
        int close_result = fclose(file);

        if (written != (size_t)data_len || close_result != 0) {
            return 0;
        }
    } else {
        fclose(file);
    }

    return 1;
}

/**
 * Return basic metadata for a path.
 *
 * @param path File path.
 * @return Metadata record with nullable size and mtime fields.
 *
 * Dea signature: `extern func rt_file_info(path: string) -> RtFileInfo;`
 */
struct __deaM3sys2rtS10RtFileInfo rt_file_info(dea_string path) {
    struct __deaM3sys2rtS10RtFileInfo out = {
        .exists = 0,
        .is_file = 0,
        .is_dir = 0,
        .size = { .has_value = 0 },
        .mtime_sec = { .has_value = 0 },
        .mtime_nsec = { .has_value = 0 },
    };
    char *c = _rt_string_bytes(path);
#if defined(_WIN32)
    struct _stat64 st;
    if (_stat64(c, &st) != 0) {
        return out;
    }

    out.exists = 1;
    out.is_file = (st.st_mode & _S_IFREG) ? 1 : 0;
    out.is_dir = (st.st_mode & _S_IFDIR) ? 1 : 0;

    if (st.st_size >= 0 && (__int64)(dea_int)st.st_size == st.st_size) {
        out.size = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_size };
    }
    if ((time_t)(dea_int)st.st_mtime == st.st_mtime) {
        out.mtime_sec = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_mtime };
    }
    return out;
#else
    struct stat st;
    if (stat(c, &st) != 0) {
        return out;
    }

    out.exists = 1;
    out.is_file = S_ISREG(st.st_mode) ? 1 : 0;
    out.is_dir = S_ISDIR(st.st_mode) ? 1 : 0;

    if (st.st_size >= 0 && (off_t)(dea_int)st.st_size == st.st_size) {
        out.size = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_size };
    }
    if ((time_t)(dea_int)st.st_mtime == st.st_mtime) {
        out.mtime_sec = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_mtime };
#if defined(__APPLE__)
        if ((long)(dea_int)st.st_mtimespec.tv_nsec == st.st_mtimespec.tv_nsec) {
            out.mtime_nsec = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_mtimespec.tv_nsec };
        }
#elif defined(_POSIX_C_SOURCE) && _POSIX_C_SOURCE >= 200809L
        if ((long)(dea_int)st.st_mtim.tv_nsec == st.st_mtim.tv_nsec) {
            out.mtime_nsec = (dea_opt_int){ .has_value = 1, .value = (dea_int)st.st_mtim.tv_nsec };
        }
#endif
    }
    return out;
#endif
}

/**
 * Delete the file at the given path.
 * Returns 1 (true) on success, 0 (false) on error.
 *
 * @param path File path.
 * @return 1 on success, 0 on failure.
 *
 * Dea signature: `extern func rt_delete_file(path: string) -> bool;`
 */
dea_bool rt_delete_file(dea_string path) {
    char *c = _rt_string_bytes(path);
    int result = remove(c);
    return result == 0;
}

/**
 * Write raw bytes to one standard stream.
 *
 * @param stream Target stream.
 * @param buf Source bytes.
 * @param len Maximum number of bytes to write.
 * @return Bytes written, or `-1` on error.
 */
dea_int _rt_stream_write_some(FILE *stream, const dea_byte *buf, dea_int len) {
    if (len < 0) {
        return -1;
    }
    if (len == 0) {
        return 0;
    }
    if (buf == NULL) {
        return -1;
    }

    clearerr(stream);
    size_t written = fwrite(buf, 1, (size_t)len, stream);
    if (written == 0 && ferror(stream)) {
        return -1;
    }
    return (dea_int)written;
}

/**
 * Read raw bytes from standard input.
 *
 * @param buf Destination bytes.
 * @param capacity Maximum number of bytes to read.
 * @return Bytes read, `0` on EOF, or `-1` on error.
 *
 * Dea signature: `extern func rt_stdin_read(buf: byte*, capacity: int) -> int;`
 */
dea_int rt_stdin_read(dea_byte *buf, dea_int capacity) {
    if (capacity < 0) {
        return -1;
    }
    if (capacity == 0) {
        return 0;
    }
    if (buf == NULL) {
        return -1;
    }

    clearerr(stdin);
    size_t nread = fread(buf, 1, (size_t)capacity, stdin);
    if (nread == 0 && ferror(stdin)) {
        return -1;
    }
    return (dea_int)nread;
}

/**
 * Write raw bytes to standard output.
 *
 * @param buf Source bytes.
 * @param len Maximum number of bytes to write.
 * @return Bytes written, or `-1` on error.
 *
 * Dea signature: `extern func rt_stdout_write(buf: byte*, len: int) -> int;`
 */
dea_int rt_stdout_write(dea_byte *buf, dea_int len) {
    return _rt_stream_write_some(stdout, buf, len);
}

/**
 * Write raw bytes to standard error.
 *
 * @param buf Source bytes.
 * @param len Maximum number of bytes to write.
 * @return Bytes written, or `-1` on error.
 *
 * Dea signature: `extern func rt_stderr_write(buf: byte*, len: int) -> int;`
 */
dea_int rt_stderr_write(dea_byte *buf, dea_int len) {
    return _rt_stream_write_some(stderr, buf, len);
}

/* =========================================================================
 * Printing to stdout/stderr
 * ========================================================================= */

/**
 * Flush stdout. */
void rt_flush_stdout(void) {
    fflush(stdout);
}

/**
 * Flush stderr.
 *

 * Dea signature: `extern func rt_flush_stdout() -> void;`
 *
 * Dea signature: `extern func rt_flush_stderr() -> void;`
 */
void rt_flush_stderr(void) {
    fflush(stderr);
}

/**
 * Internal helper to print a dea_string to a given stream.
 *
 * @param s String to print.
 * @param stream Target stream.
 */
void _rt_print(dea_string s, FILE *stream){
    dea_int s_len = rt_strlen(s);
    char *s_data = _rt_string_bytes(s);
    if (s_len > 0 && s_data != NULL) {
        fwrite(s_data, 1, (size_t)s_len, stream);
    }
}

/**
 * Print a string to stdout.
 *
 * @param s String to print.
 *
 * Dea signature: `extern func rt_print(s: string) -> void;`
 */
void rt_print(dea_string s) {
    _rt_print(s, stdout);
}

/**
 * Print a string to stderr.
 *
 * @param s String to print.
 *
 * Dea signature: `extern func rt_print_stderr(s: string) -> void;`
 */
void rt_print_stderr(dea_string s) {
    _rt_print(s, stderr);
}

/**
 * Print a newline to stdout. */
void rt_println(void) {
    fputc('\n', stdout);
}

/**
 * Print a newline to stderr.
 *

 * Dea signature: `extern func rt_println() -> void;`
 *
 * Dea signature: `extern func rt_println_stderr() -> void;`
 */
void rt_println_stderr(void) {
    fputc('\n', stderr);
}

/**
 * Print an integer to stdout.
 *
 * @param x Integer value.
 *
 * Dea signature: `extern func rt_print_int(x: int) -> void;`
 */
void rt_print_int(dea_int x) {
    printf("%d", (int)x);
}

/**
 * Print an unsigned integer to stdout.
 *
 * @param x Unsigned integer value.
 *
 * Dea signature: `extern func rt_print_uint(x: uint) -> void;`
 */
void rt_print_uint(dea_uint x) {
    printf("%" PRIu32, (uint32_t)x);
}

/**
 * Print a long integer to stdout.
 *
 * @param x Long integer value.
 *
 * Dea signature: `extern func rt_print_long(x: long) -> void;`
 */
void rt_print_long(dea_long x) {
    printf("%" PRId64, (int64_t)x);
}

/**
 * Print an unsigned long integer to stdout.
 *
 * @param x Unsigned long integer value.
 *
 * Dea signature: `extern func rt_print_ulong(x: ulong) -> void;`
 */
void rt_print_ulong(dea_ulong x) {
    printf("%" PRIu64, (uint64_t)x);
}

/**
 * Print a float to stdout.
 *
 * @param x Float value.
 *
 * Dea signature: `extern func rt_print_float(x: float) -> void;`
 */
void rt_print_float(dea_float x) {
    printf("%.9g", (double)x);
}

/**
 * Print a double to stdout.
 *
 * @param x Double value.
 *
 * Dea signature: `extern func rt_print_double(x: double) -> void;`
 */
void rt_print_double(dea_double x) {
    printf("%.17g", (double)x);
}

/**
 * Print an integer to stderr.
 *
 * @param x Integer value.
 *
 * Dea signature: `extern func rt_print_int_stderr(x: int) -> void;`
 */
void rt_print_int_stderr(dea_int x) {
    fprintf(stderr, "%d", (int)x);
}

/**
 * Print an unsigned integer to stderr.
 *
 * @param x Unsigned integer value.
 *
 * Dea signature: `extern func rt_print_uint_stderr(x: uint) -> void;`
 */
void rt_print_uint_stderr(dea_uint x) {
    fprintf(stderr, "%" PRIu32, (uint32_t)x);
}

/**
 * Print a long integer to stderr.
 *
 * @param x Long integer value.
 *
 * Dea signature: `extern func rt_print_long_stderr(x: long) -> void;`
 */
void rt_print_long_stderr(dea_long x) {
    fprintf(stderr, "%" PRId64, (int64_t)x);
}

/**
 * Print an unsigned long integer to stderr.
 *
 * @param x Unsigned long integer value.
 *
 * Dea signature: `extern func rt_print_ulong_stderr(x: ulong) -> void;`
 */
void rt_print_ulong_stderr(dea_ulong x) {
    fprintf(stderr, "%" PRIu64, (uint64_t)x);
}

/**
 * Print a float to stderr.
 *
 * @param x Float value.
 *
 * Dea signature: `extern func rt_print_float_stderr(x: float) -> void;`
 */
void rt_print_float_stderr(dea_float x) {
    fprintf(stderr, "%.9g", (double)x);
}

/**
 * Print a double to stderr.
 *
 * @param x Double value.
 *
 * Dea signature: `extern func rt_print_double_stderr(x: double) -> void;`
 */
void rt_print_double_stderr(dea_double x) {
    fprintf(stderr, "%.17g", (double)x);
}

/**
 * Print a bool to stdout.
 *
 * @param x Boolean value.
 *
 * Dea signature: `extern func rt_print_bool(x: bool) -> void;`
 */
void rt_print_bool(dea_bool x) {
    printf("%s", x ? "true" : "false");
}

/**
 * Print a bool to stderr.
 *
 * @param x Boolean value.
 *
 * Dea signature: `extern func rt_print_bool_stderr(x: bool) -> void;`
 */
void rt_print_bool_stderr(dea_bool x) {
    fprintf(stderr, "%s", x ? "true" : "false");
}

/* =========================================================================
 * Reading from stdin
 * ========================================================================= */

/**
 * Read a line from stdin into a dynamically allocated buffer.
 * Returns None on EOF (no characters read).
 * *
 * Ownership: on Some(s), s.data is heap-allocated and must be freed by calling
 * rt_string_release(s) (directly or indirectly via stdlib).
 *
 * @return Optional string containing the line.
 *
 * Dea signature: `extern func rt_read_line() -> string?;`
 */
dea_opt_string rt_read_line(void) {
    size_t capacity = 128;
    size_t length = 0;

    dea_string s = _rt_alloc_string(capacity);
    char *s_data = _rt_string_bytes(s);

    int c;
    while ((c = fgetc(stdin)) != EOF && c != '\n') {
        if (length + 1 >= capacity) {
            capacity = capacity * 2;
            s = _rt_realloc_string(s, (dea_int)capacity);
            s_data = _rt_string_bytes(s);
        }
        s_data[length++] = (char)c;
    }

    /* EOF with no data => None */
    if (c == EOF && length == 0) {
        _rt_free_string(s);
        return DEA_OPT_STRING_NULL;
    }

    if (length > INT32_MAX) {
        _rt_free_string(s);
        _rt_panic("rt_read_line: line too long for dea_int");
    }

    /* Empty line => Some(empty string) without allocating owned storage. */
    if (length == 0) {
        _rt_free_string(s);
        return DEA_OPT_STRING_EMPTY;
    }

    /* Trim string to actual length */
    if ((size_t)length < capacity) {
        s = _rt_realloc_string(s, (dea_int)length);
    }

    return (dea_opt_string){ .has_value = 1, .value = s };
}


/**
 * Read one character from stdin.
 * Returns -1 on EOF or error.
 *
 * @return Character value or -1.
 *
 * Dea signature: `extern func rt_read_char() -> int;`
 */
dea_int rt_read_char(void) {
    int c = fgetc(stdin);
    if (c == EOF) {
        return -1;
    }
    return (dea_int)c;
}
