#ifndef DEA_RT_H
#define DEA_RT_H

/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

/**
 * @file dea_rt.h
 * Public L1 runtime header.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <stddef.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <sys/stat.h>

#if defined(_WIN32)
#include <process.h>
#else
#include <unistd.h>
#include <sys/wait.h>
#endif

#ifndef _RT_ALIGNOF
#if defined(__clang__) || (defined(__GNUC__) && !defined(__TINYC__))
#define _RT_ALIGNOF(type) __alignof__(type)
#else
#define _RT_ALIGNOF(type) (sizeof(struct { char _rt_align_c; type _rt_align_v; }) - sizeof(type))
#endif
#endif

#if defined(DEA_RT_CHECK_BASIC) && defined(DEA_RT_UNCHECKED)
#error "DEA_RT_CHECK_BASIC cannot be combined with DEA_RT_UNCHECKED"
#endif

/* =========================================================================
 * Compiler-specific builtins and attributes
 * ========================================================================= */

#if defined(__TINYC__) && __TINYC__ >= 928

/* __builtin_unreachable added in mob branch post-0.9.27 */
#   define DEA_UNREACHABLE(_s) __builtin_unreachable()
#elif defined(__GNUC__) || defined(__clang__)
#   define DEA_UNREACHABLE(_s) __builtin_unreachable()
#else
#   define DEA_UNREACHABLE(_s) rt_panic(_s)
#endif

/* =========================================================================
 * Optional tracing support (compile-time toggles)
 * ========================================================================= */

#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)

/* Select the process-wide trace flush policy before user initialization. */
void _rt_trace_init(void);

/* Flush one completed trace event when the durable policy is active. */
void _rt_trace_event_end(void);

/* Flush pending block-buffered trace bytes at a process boundary. */
void _rt_trace_flush_pending(void);
#endif

#ifdef DEA_TRACE_ARC

/**
 * Trace reference counting operations to stderr.
 */
#define _RT_TRACE_ARC(...) \
    do { \
        fprintf(stderr, "[l0][arc] "); \
        fprintf(stderr, __VA_ARGS__); \
        fprintf(stderr, "\n"); \
        _rt_trace_event_end(); \
    } while (0)

/**
 * Trace reference counting operations with location info.
 */
#define _RT_TRACE_ARC_LOC(loc_file, loc_line, ...) \
    do { \
        fprintf(stderr, "[l0][arc] "); \
        fprintf(stderr, __VA_ARGS__); \
        fprintf(stderr, " loc=\"%s\":%d", loc_file, loc_line); \
        fprintf(stderr, "\n"); \
        _rt_trace_event_end(); \
    } while (0)
#else
#define _RT_TRACE_ARC(...) ((void)0)
#define _RT_TRACE_ARC_LOC(loc_file, loc_line, ...) ((void)0)
#endif

#ifdef DEA_TRACE_MEMORY

/**
 * Trace memory allocation operations to stderr.
 */
#define _RT_TRACE_MEM(...) \
    do { \
        fprintf(stderr, "[l0][mem] "); \
        fprintf(stderr, __VA_ARGS__); \
        fprintf(stderr, "\n"); \
        _rt_trace_event_end(); \
    } while (0)

/**
 * Trace memory allocation operations with location info.
 */
#define _RT_TRACE_MEM_LOC(loc_file, loc_line, ...) \
    do { \
        fprintf(stderr, "[l0][mem] "); \
        fprintf(stderr, __VA_ARGS__); \
        fprintf(stderr, " loc=\"%s\":%d", loc_file, loc_line); \
        fprintf(stderr, "\n"); \
        _rt_trace_event_end(); \
    } while (0)
#else
#define _RT_TRACE_MEM(...) ((void)0)
#define _RT_TRACE_MEM_LOC(loc_file, loc_line, ...) ((void)0)
#endif

/* =========================================================================
 * Core type definitions
 * ========================================================================= */

typedef uint8_t  dea_bool;

typedef int8_t   dea_tiny;
typedef int16_t  dea_short;
typedef int32_t  dea_int;
typedef int64_t  dea_long;

typedef uint8_t  dea_byte;
typedef uint16_t dea_ushort;
typedef uint32_t dea_uint;
typedef uint64_t dea_ulong;

typedef float    dea_float;
typedef double   dea_double;

/**
 * @struct _dea_h_string
 * * Heap-allocated L0 string header.
 *
 * L0 string: length-tracked, reference counted, immutable character sequence.
 * Strings are always length-tracked to prevent out-of-bounds access.
 * A dea_string with len=0 represents an empty string.
 * Data should be NULL for empty strings to maintain consistency, but non-NULL is tolerated.
 * refcount is used for memory management; if refcount == INT32_MAX, the string
 * is not reference counted (e.g. allocated strings).
 * Strings with refcount > 0 are reference counted and should be freed when refcount reaches zero.
 * Strings with refcount == INT32_MAX are not ref-counted, but heap-allocated or empty, and should be freed manually.
 * Strings with refcount == _RT_MEM_SENTINEL have already been freed (double-free detected).
 * Data is null-terminated for C interoperability, but length is authoritative.
 */
typedef struct {

    /**
 * < Reference count for memory management, or INT32_MAX if not reference counted
 */
    dea_int refcount;

    /**
 * < Length in bytes (must be >= 0)
 */
    dea_int len;

    /**
 * < Mutable character data, 0-terminated for C interoperability
 */
    char bytes[];

} _dea_h_string;

#define DEA_STRING_K_STATIC  0
#define DEA_STRING_K_HEAP    1

/**
 * Sentinel value for memory checks.
 */
static const dea_int _RT_MEM_SENTINEL = 0xF00DB10C;

/**
 * @struct dea_string
 * * Unified L0 string type (static or heap-allocated).
 */
typedef struct {

    /**
 * < Kind of string: either DEA_STRING_K_STATIC (0) or DEA_STRING_K_HEAP (1)
 */
    unsigned int kind : 1;

    /**
 * < Align to next unsigned int boundary
 */
    unsigned int : 0;

    union {
        struct {

            /**
 * < Length in bytes (for constant inline strings)
 */
            dea_int len;

            /**
 * < Pointer to character data (may be NULL for empty string)
 */
            const char* bytes;

        /**
 * < Static string structure for constant inline strings
 */
        } s_str;

        /**
 * < Heap-allocated string structure for dynamic strings
 */
        _dea_h_string *h_str;

    } data;
} dea_string;

/**
 * Typed value macro for an empty static string.
 */
#define DEA_STRING_EMPTY \
    ((dea_string){ \
        .kind = DEA_STRING_K_STATIC, \
        .data = { .s_str = { .len = 0, .bytes = NULL } } \
    })

/**
 * String literal construction macro.
 */
#define DEA_STRING_CONST(str_data, str_len) { .kind = DEA_STRING_K_STATIC, .data.s_str = { .len = (str_len), .bytes = (str_data) } }

/* =========================================================================
 * Optional type wrappers (T? as {has_value, value})
 * ========================================================================= */

#ifndef DEA_OPT_BOOL_DEFINED
#define DEA_OPT_BOOL_DEFINED

/**
 * @struct dea_opt_bool
 * Optional boolean wrapper.
 */
typedef struct { dea_bool has_value; dea_bool value; } dea_opt_bool;

/* DEA_OPT_BOOL_DEFINED */
#endif

#ifndef DEA_OPT_TINY_DEFINED
#define DEA_OPT_TINY_DEFINED

/**
 * @struct dea_opt_tiny
 * Optional tiny wrapper.
 */
typedef struct { dea_bool has_value; dea_tiny value; } dea_opt_tiny;

/* DEA_OPT_TINY_DEFINED */
#endif

#ifndef DEA_OPT_BYTE_DEFINED
#define DEA_OPT_BYTE_DEFINED

/**
 * @struct dea_opt_byte
 * Optional byte wrapper.
 */
typedef struct { dea_bool has_value; dea_byte value; } dea_opt_byte;

/* DEA_OPT_BYTE_DEFINED */
#endif

#ifndef DEA_OPT_SHORT_DEFINED
#define DEA_OPT_SHORT_DEFINED

/**
 * @struct dea_opt_short
 * Optional short wrapper.
 */
typedef struct { dea_bool has_value; dea_short value; } dea_opt_short;

/* DEA_OPT_SHORT_DEFINED */
#endif

#ifndef DEA_OPT_INT_DEFINED
#define DEA_OPT_INT_DEFINED

/**
 * @struct dea_opt_int
 * Optional integer wrapper.
 */
typedef struct { dea_bool has_value; dea_int value; } dea_opt_int;

/* DEA_OPT_INT_DEFINED */
#endif

#ifndef DEA_OPT_USHORT_DEFINED
#define DEA_OPT_USHORT_DEFINED

/**
 * @struct dea_opt_ushort
 * Optional ushort wrapper.
 */
typedef struct { dea_bool has_value; dea_ushort value; } dea_opt_ushort;

/* DEA_OPT_USHORT_DEFINED */
#endif

#ifndef DEA_OPT_UINT_DEFINED
#define DEA_OPT_UINT_DEFINED

/**
 * @struct dea_opt_uint
 * Optional uint wrapper.
 */
typedef struct { dea_bool has_value; dea_uint value; } dea_opt_uint;

/* DEA_OPT_UINT_DEFINED */
#endif

#ifndef DEA_OPT_LONG_DEFINED
#define DEA_OPT_LONG_DEFINED

/**
 * @struct dea_opt_long
 * Optional long wrapper.
 */
typedef struct { dea_bool has_value; dea_long value; } dea_opt_long;

/* DEA_OPT_LONG_DEFINED */
#endif

#ifndef DEA_OPT_ULONG_DEFINED
#define DEA_OPT_ULONG_DEFINED

/**
 * @struct dea_opt_ulong
 * Optional ulong wrapper.
 */
typedef struct { dea_bool has_value; dea_ulong value; } dea_opt_ulong;

/* DEA_OPT_ULONG_DEFINED */
#endif

#ifndef DEA_OPT_STRING_DEFINED
#define DEA_OPT_STRING_DEFINED

/**
 * @struct dea_opt_string
 * Optional string wrapper.
 */
typedef struct { dea_bool has_value; dea_string value; } dea_opt_string;

/* DEA_OPT_STRING_DEFINED */
#endif

/**
 * @struct _dea_base_opt
 * Base structure for optional types to access has_value.
 */
typedef struct { dea_bool has_value; } _dea_base_opt;

/**
 * Typed value macro for a null optional string.
 */
#define DEA_OPT_STRING_NULL \
    ((dea_opt_string){ \
        .has_value = 0, \
        .value = { \
            .kind = DEA_STRING_K_STATIC, \
            .data = { .s_str = { .len = 0, .bytes = NULL } } \
        } \
    })

/**
 * Typed value macro for an empty optional string.
 */
#define DEA_OPT_STRING_EMPTY \
    ((dea_opt_string){ \
        .has_value = 1, \
        .value = { \
            .kind = DEA_STRING_K_STATIC, \
            .data = { .s_str = { .len = 0, .bytes = NULL } } \
        } \
    })

/**
 * @struct __deaM3sys2rtS11RtTimeParts
 * * Definition for `sys.rt::RtTimeParts`.
 */
#ifndef DEA_DEFINED___deaM3sys2rtS11RtTimeParts
#define DEA_DEFINED___deaM3sys2rtS11RtTimeParts
struct __deaM3sys2rtS11RtTimeParts {
    dea_int sec;
    dea_int nsec;
};
#endif

/**
 * @struct __deaM3sys2rtS10RtFileInfo
 * * Definition for `sys.rt::RtFileInfo`.
 */
#ifndef DEA_DEFINED___deaM3sys2rtS10RtFileInfo
#define DEA_DEFINED___deaM3sys2rtS10RtFileInfo
struct __deaM3sys2rtS10RtFileInfo {
    dea_bool exists;
    dea_bool is_file;
    dea_bool is_dir;
    dea_opt_long size;
    dea_opt_long mtime_sec;
    dea_opt_int mtime_nsec;
};
#endif

/* =========================================================================
 * Runtime function declarations
 * ========================================================================= */

/* Initialize command-line arguments. */
void _rt_init_args(int argc, char** argv);

/* Abort the program with a message. */
void _rt_panic(const char* message);

/* Abort the program with a formatted message. */
void _rt_panic_fmt(const char* fmt, ...);

/* Terminate execution with an out-of-bounds index diagnostic. */
void _rt_panic_oob(dea_int index, dea_int length);

/* Safe integer division. */
dea_int _rt_idiv(dea_int a, dea_int b);

/* Safe integer modulo. */
dea_int _rt_imod(dea_int a, dea_int b);

/* Safe integer addition with overflow check. */
dea_int _rt_iadd(dea_int a, dea_int b);

/* Safe integer subtraction with overflow check. */
dea_int _rt_isub(dea_int a, dea_int b);

/* Safe integer multiplication with overflow check. */
dea_int _rt_imul(dea_int a, dea_int b);

/* Narrow dea_int to dea_tiny with range check. */
dea_tiny _rt_narrow_dea_tiny(dea_int value);

/* Narrow dea_int to dea_byte with range check. */
dea_byte _rt_narrow_dea_byte(dea_int value);

/* Narrow dea_int to dea_short with range check. */
dea_short _rt_narrow_dea_short(dea_int value);

/* Narrow dea_int to dea_ushort with range check. */
dea_ushort _rt_narrow_dea_ushort(dea_int value);

/* Narrow dea_int to dea_uint with range check. */
dea_uint _rt_narrow_dea_uint(dea_int value);

/* Narrow dea_int to dea_ulong with range check. */
dea_ulong _rt_narrow_dea_ulong(dea_int value);

/* Safe unsigned integer division. */
dea_uint _rt_udiv(dea_uint a, dea_uint b);

/* Safe unsigned integer modulo. */
dea_uint _rt_umod(dea_uint a, dea_uint b);

/* Safe unsigned integer addition with overflow check. */
dea_uint _rt_uadd(dea_uint a, dea_uint b);

/* Safe unsigned integer subtraction with underflow check. */
dea_uint _rt_usub(dea_uint a, dea_uint b);

/* Safe unsigned integer multiplication with overflow check. */
dea_uint _rt_umul(dea_uint a, dea_uint b);

/* Safe 64-bit signed integer division. */
dea_long _rt_ldiv(dea_long a, dea_long b);

/* Safe 64-bit signed integer modulo. */
dea_long _rt_lmod(dea_long a, dea_long b);

/* Safe 64-bit signed integer addition with overflow check. */
dea_long _rt_ladd(dea_long a, dea_long b);

/* Safe 64-bit signed integer subtraction with overflow check. */
dea_long _rt_lsub(dea_long a, dea_long b);

/* Safe 64-bit signed integer multiplication with overflow check. */
dea_long _rt_lmul(dea_long a, dea_long b);

/* Safe 64-bit unsigned integer division. */
dea_ulong _rt_uldiv(dea_ulong a, dea_ulong b);

/* Safe 64-bit unsigned integer modulo. */
dea_ulong _rt_ulmod(dea_ulong a, dea_ulong b);

/* Safe 64-bit unsigned integer addition with overflow check. */
dea_ulong _rt_uladd(dea_ulong a, dea_ulong b);

/* Safe 64-bit unsigned integer subtraction with underflow check. */
dea_ulong _rt_ulsub(dea_ulong a, dea_ulong b);

/* Safe 64-bit unsigned integer multiplication with overflow check. */
dea_ulong _rt_ulmul(dea_ulong a, dea_ulong b);

/* Checked cast from signed 64-bit to dea_tiny. */
dea_tiny _rt_cast_dea_tiny_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_tiny. */
dea_tiny _rt_cast_dea_tiny_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_byte. */
dea_byte _rt_cast_dea_byte_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_byte. */
dea_byte _rt_cast_dea_byte_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_short. */
dea_short _rt_cast_dea_short_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_short. */
dea_short _rt_cast_dea_short_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_ushort. */
dea_ushort _rt_cast_dea_ushort_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_ushort. */
dea_ushort _rt_cast_dea_ushort_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_int. */
dea_int _rt_cast_dea_int_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_int. */
dea_int _rt_cast_dea_int_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_uint. */
dea_uint _rt_cast_dea_uint_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_uint. */
dea_uint _rt_cast_dea_uint_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_long. */
dea_long _rt_cast_dea_long_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_long. */
dea_long _rt_cast_dea_long_from_unsigned(dea_ulong value);

/* Checked cast from signed 64-bit to dea_ulong. */
dea_ulong _rt_cast_dea_ulong_from_signed(dea_long value);

/* Checked cast from unsigned 64-bit to dea_ulong. */
dea_ulong _rt_cast_dea_ulong_from_unsigned(dea_ulong value);

/* Require a non-null optional pointer or terminate with an unwrap diagnostic. */
void *_unwrap_ptr(void *opt, const char *type_name);

/* Unwrap an optional type structure, panicking if it has no value. */
void *_unwrap_opt(void *opt_ptr, const char *type_name);

/* Create a Dea string from a constant C string. */
dea_string _rt_dea_string_from_const_literal(const char *c_str);

/* Initialize a heap-allocated dea_string in the given memory. */
dea_string _rt_init_heap_string(void *mem, dea_int s_len);

/* Allocate a reference-counted heap string of the requested byte length. */
dea_string _rt_alloc_string_impl(dea_int len, const char *_loc_file, int _loc_line);

/* Allocate a reference-counted heap string of the requested byte length. */
dea_string _rt_alloc_string(dea_int len);

/* Release a runtime string reference and free its heap storage at zero references. */
void _rt_free_string_impl(dea_string str, const char *_loc_file, int _loc_line);

/* Release a runtime string reference and free its heap storage at zero references. */
void _rt_free_string(dea_string str);

/* Reallocate a heap string to a new length. */
dea_string _rt_realloc_string(dea_string s, dea_int new_len);

/* Create a new reference counted dea_string from a null-terminated C string. */
dea_string _rt_new_dea_string(const char *c_str);

/* Gets the null-terminated C string underlying a Dea string. */
char *_rt_string_bytes(dea_string s);

/* Get the length of a string. */
dea_int rt_strlen(dea_string str);

/* Bounds-checked character access. */
dea_byte rt_string_get(dea_string a, dea_int index);

/* Return a pointer to the raw byte data of a string. */
dea_byte *rt_string_bytes_ptr(dea_string s);

/* Check if two strings are equal. */
dea_bool rt_string_equals(dea_string a, dea_string b);

/* Compare two strings lexicographically. */
dea_int rt_string_compare(dea_string a, dea_string b);

/* Concatenate two runtime strings into an owned result. */
dea_string _rt_string_concat_impl(dea_string a, dea_string b, const char *_loc_file, int _loc_line);

/* Concatenate two runtime strings into an owned result. */
dea_string rt_string_concat(dea_string a, dea_string b);

/* Create a substring (allocates new memory). */
dea_string rt_string_slice(dea_string s, dea_int start, dea_int end);

/* Create a Dea string from a single character (byte). */
dea_string rt_string_from_byte(dea_byte b);

/* Create a Dea string from a byte array and a length. */
dea_string rt_string_from_byte_array(dea_byte* bytes, dea_int len);

/* Retain one owned reference to a runtime string. */
void _rt_string_retain_impl(dea_string s, const char *_loc_file, int _loc_line);

/* Retain one owned reference to a runtime string. */
void rt_string_retain(dea_string s);

/* Release one runtime string reference and free heap storage at zero references. */
void _rt_string_release_impl(dea_string s, const char *_loc_file, int _loc_line);

/* Release one runtime string reference and free heap storage at zero references. */
void rt_string_release(dea_string s);

/* Execute a system command and return its normalized status. */
dea_int rt_system(dea_string cmd);

/* Get an environment variable as a Dea optional string. */
dea_opt_string rt_get_env_var(dea_string name);

/* Get the number of command-line arguments. */
dea_int rt_get_argc(void);

/* Convert a native process identifier into `dea_int`. */
dea_bool _rt_pid_to_dea_int(intmax_t value, dea_int *out);

/* Get the current process identifier. */
dea_int rt_get_pid(void);

/* Get the command-line argument at the given index. */
dea_string rt_get_argv(dea_int i);

/* Convert native time seconds to a representable Dea integer. */
dea_bool _rt_time_to_dea_int_sec(time_t value, dea_int *out);

/* Internal helper to convert long to dea_int nanoseconds. */
dea_bool _rt_time_to_dea_int_nsec(long value, dea_int *out);

/* Internal helper to write time parts to struct. */
dea_bool _rt_time_write_parts(struct __deaM3sys2rtS11RtTimeParts *out, dea_int sec, dea_int nsec);

/* Capture current unix wall clock into `out`. */
dea_bool rt_time_unix(struct __deaM3sys2rtS11RtTimeParts *out);

/* Capture current monotonic clock into `out`. */
dea_bool rt_time_monotonic(struct __deaM3sys2rtS11RtTimeParts *out);

/* Returns whether a monotonic clock source is available. */
dea_bool rt_time_monotonic_supported(void);

/* Returns local UTC offset in seconds for `unix_sec`. */
dea_opt_int rt_time_local_offset_sec(dea_int unix_sec);

/* Returns whether local time is daylight-saving time for `unix_sec`. */
dea_opt_bool rt_time_local_is_dst(dea_int unix_sec);

/* Read entire file contents into a string. */
dea_opt_string rt_read_file_all(dea_string path);

/* Write string data to a file. */
dea_bool rt_write_file_all(dea_string path, dea_string data);

/* Return basic metadata for a path. */
struct __deaM3sys2rtS10RtFileInfo rt_file_info(dea_string path);

/* Delete the file at the given path. */
dea_bool rt_delete_file(dea_string path);

/* Write raw bytes to one standard stream. */
dea_int _rt_stream_write_some(FILE *stream, const dea_byte *buf, dea_int len);

/* Read raw bytes from standard input. */
dea_int rt_stdin_read(dea_byte *buf, dea_int capacity);

/* Write raw bytes to standard output. */
dea_int rt_stdout_write(dea_byte *buf, dea_int len);

/* Write raw bytes to standard error. */
dea_int rt_stderr_write(dea_byte *buf, dea_int len);

/* Flush stdout. */
void rt_flush_stdout(void);

/* Flush stderr. */
void rt_flush_stderr(void);

/* Print a string to stdout. */
void rt_print(dea_string s);

/* Print a string to stderr. */
void rt_print_stderr(dea_string s);

/* Print a newline to stdout. */
void rt_println(void);

/* Print a newline to stderr. */
void rt_println_stderr(void);

/* Print an integer to stdout. */
void rt_print_int(dea_int x);

/* Print an unsigned integer to stdout. */
void rt_print_uint(dea_uint x);

/* Print a long integer to stdout. */
void rt_print_long(dea_long x);

/* Print an unsigned long integer to stdout. */
void rt_print_ulong(dea_ulong x);

/* Print a float to stdout. */
void rt_print_float(dea_float x);

/* Print a double to stdout. */
void rt_print_double(dea_double x);

/* Print an integer to stderr. */
void rt_print_int_stderr(dea_int x);

/* Print an unsigned integer to stderr. */
void rt_print_uint_stderr(dea_uint x);

/* Print a long integer to stderr. */
void rt_print_long_stderr(dea_long x);

/* Print an unsigned long integer to stderr. */
void rt_print_ulong_stderr(dea_ulong x);

/* Print a float to stderr. */
void rt_print_float_stderr(dea_float x);

/* Print a double to stderr. */
void rt_print_double_stderr(dea_double x);

/* Print a bool to stdout. */
void rt_print_bool(dea_bool x);

/* Print a bool to stderr. */
void rt_print_bool_stderr(dea_bool x);

/* Read one line from stdin without its terminating newline. */
dea_opt_string rt_read_line(void);

/* Read one character from stdin. */
dea_int rt_read_char(void);

/* Abort the program with a panic message. */
void rt_abort(dea_string message);

/* Exit the program with the given exit code. */
void rt_exit(dea_int code);

/* Seed the random number generator. */
void rt_srand(dea_int seed);

/* Generate a random integer in the range [0, max). */
dea_int rt_rand(dea_int max);

/* Get the current C standard library `errno` value from `<errno.h>`. */
dea_int rt_errno(void);

/* =========================================================================
 * Runtime pointer access validation: tracker types and fast path
 * -------------------------------------------------------------------------
 * Checked builds (the default) validate every generated pointer dereference
 * against the allocation tracker. Define DEA_RT_UNCHECKED when compiling
 * generated code and the runtime archive to compile validation out;
 * generated code is identical in both modes.
 * ========================================================================= */

#define _RT_ALLOC_LIVE 1
#define _RT_ALLOC_QUARANTINED 2
#define _RT_ALLOC_POOLED 3
#define _RT_MEM_RAW 0
#define _RT_MEM_NEW 1
#define _RT_MEM_ARC 2
#define _RT_MEM_STATIC 3
#define _RT_MEM_FOREIGN 4
#define _RT_ACCESS_READ 0
#define _RT_ACCESS_WRITE 1
#define _RT_ACCESS_UNTRACKED_OK 2

typedef struct _rt_alloc_record _rt_alloc_record;
typedef struct _rt_alloc_record_cold _rt_alloc_record_cold;
typedef struct _rt_ptr_site _rt_ptr_site;

/**
 * Hot allocation fields read by checked pointer cache hits and allocation
 * tracker mutation paths. Records are pool-allocated and never freed, so a
 * stale record pointer held by a call-site cache stays dereferenceable; the
 * generation counter rejects reuse.
 */
struct _rt_alloc_record {
    void *base;
    size_t size;
    uint64_t generation;
#ifdef DEA_RT_CHECK_BASIC

    /* Sized from the pointer width so the hot layout matches the treap
     * fields of full checked mode on both 32-bit and 64-bit targets. */
    uint8_t tree_pad[2 * sizeof(_rt_alloc_record *)];
#else
    _rt_alloc_record *tree_left;
    _rt_alloc_record *tree_right;
#endif
    _rt_alloc_record *q_next;
#ifdef DEA_RT_CHECK_BASIC
    uint32_t tree_prio_pad;
#else
    uint32_t tree_prio;
#endif
    uint32_t cold_index;
    uint8_t state;
    uint8_t read_only;
    uint8_t mem_kind;
#if UINTPTR_MAX == UINT32_MAX && SIZE_MAX == UINT32_MAX
    uint8_t hot_pad[25];
#else
    uint8_t hot_pad[5];
#endif
};

typedef char _rt_alloc_record_size_check[(sizeof(_rt_alloc_record) == 64) ? 1 : -1];

/**
 * Cold allocation fields used by diagnostics and rare metadata reads.
 */
struct _rt_alloc_record_cold {
    size_t align;

    /* Reserved for a future runtime type-identity initiative. */
    uint32_t type_id;
    int alloc_line;
    int drop_line;
    uint32_t reserved;
    const char *alloc_file;
    const char *drop_file;
};

/**
 * Per-call-site pointer check cache. Generated code declares one static
 * instance per checked access site; a hit validates with one generation
 * compare and one range check, without hashing.
 */
struct _rt_ptr_site {
    _rt_alloc_record *owner;
    uint64_t generation;
};

/* Validate an uncached pointer access under the selected runtime check policy. */
void *_rt_check_ptr_site_slow(_rt_ptr_site *site, void *ptr, dea_int required_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line);

/* Validate and form an indexed pointer under the selected runtime check policy. */
void *_rt_check_index_ptr_site_slow(_rt_ptr_site *site, void *base_ptr, dea_int index, dea_int element_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line);

/* Lazily register ARC-managed string storage as a read-only tracked record in checked builds. */
void _rt_track_arc_bytes(void *ptr, size_t size);

/* Remove any allocation-tracker record for ARC storage without freeing its bytes. */
void _rt_untrack_arc_alloc(void *ptr);

/* Register borrowed immutable static storage in checked builds. */
void _rt_track_static_bytes(const void *ptr, size_t size);

/**
 * Validate one pointer access through a call-site cache.
 *
 * @param site Per-call-site cache slot owned by the generated access site.
 * @param ptr Pointer about to be dereferenced.
 * @param required_size Size in bytes of the access.
 * @param required_align Required alignment, or 0 for no alignment check.
 * @param access_mode `_RT_ACCESS_READ` or `_RT_ACCESS_WRITE`.
 * @param loc_file Source file of the access site.
 * @param loc_line Source line of the access site.
 * @return `ptr` when the access is valid; panics otherwise.
 */
static inline void *_rt_check_ptr_site(_rt_ptr_site *site, void *ptr, dea_int required_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line) {
#ifdef DEA_RT_UNCHECKED
    (void)site; (void)required_size; (void)required_align; (void)access_mode; (void)loc_file; (void)loc_line;
    return ptr;
#else
    _rt_alloc_record *owner = site != NULL ? site->owner : NULL;
    if (owner != NULL && owner->generation == site->generation &&
        owner->state == _RT_ALLOC_LIVE && required_size > 0 &&
        required_align >= 0 &&
        (access_mode == _RT_ACCESS_READ || access_mode == _RT_ACCESS_WRITE) &&
        (access_mode != _RT_ACCESS_WRITE || !owner->read_only)) {
        uintptr_t base = (uintptr_t)owner->base;
        uintptr_t addr = (uintptr_t)ptr;
        if (addr >= base) {
            size_t offset = (size_t)(addr - base);
            if (offset <= owner->size && (size_t)required_size <= owner->size - offset &&
                (required_align <= 1 || (addr % (size_t)required_align) == 0)) {
                return ptr;
            }
        }
    }
    return _rt_check_ptr_site_slow(site, ptr, required_size, required_align, access_mode, loc_file, loc_line);
#endif
}

/**
 * Validate and derive one indexed pointer access through a call-site cache.
 *
 * The checked path validates the base pointer and target byte range before
 * forming the target pointer value, avoiding out-of-object C pointer
 * arithmetic in generated code.
 *
 * @param site Per-call-site cache slot owned by the generated access site.
 * @param base_ptr Base pointer expression before indexing.
 * @param index Element index.
 * @param element_size Size in bytes of one indexed element.
 * @param required_align Required target alignment, or 0 for no alignment check.
 * @param access_mode `_RT_ACCESS_READ` or `_RT_ACCESS_WRITE`.
 * @param loc_file Source file of the access site.
 * @param loc_line Source line of the access site.
 * @return Target pointer when the access is valid; panics otherwise.
 */
static inline void *_rt_check_index_ptr_site(
    _rt_ptr_site *site,
    void *base_ptr,
    dea_int index,
    dea_int element_size,
    dea_int required_align,
    int access_mode,
    const char *loc_file,
    int loc_line
) {
#ifdef DEA_RT_UNCHECKED
    uint64_t offset = (uint64_t)((int64_t)index * (int64_t)element_size);
    (void)site; (void)required_align; (void)access_mode; (void)loc_file; (void)loc_line;
    return (void *)((uintptr_t)base_ptr + (uintptr_t)offset);
#else
    _rt_alloc_record *owner = site != NULL ? site->owner : NULL;
    int index_mode = access_mode & _RT_ACCESS_WRITE;
    int index_flags = access_mode & ~_RT_ACCESS_WRITE;
    if (owner != NULL && owner->generation == site->generation &&
        owner->state == _RT_ALLOC_LIVE && index >= 0 && element_size > 0 &&
        required_align >= 0 &&
        (index_flags == 0 || index_flags == _RT_ACCESS_UNTRACKED_OK) &&
        (index_mode == _RT_ACCESS_READ || index_mode == _RT_ACCESS_WRITE) &&
        (index_mode != _RT_ACCESS_WRITE || !owner->read_only)) {

        /* `dea_int` is 32-bit, so the 64-bit product of two non-negative
         * operands cannot wrap and the SIZE_MAX comparison is exact. */
        uint64_t offset64 = (uint64_t)index * (uint64_t)element_size;
        if (offset64 <= SIZE_MAX) {
            uintptr_t owner_addr = (uintptr_t)owner->base;
            uintptr_t base_addr = (uintptr_t)base_ptr;
            if (base_addr >= owner_addr) {
                size_t base_offset = (size_t)(base_addr - owner_addr);
                if (base_offset < owner->size) {
                    size_t offset = (size_t)offset64;
                    size_t available = owner->size - base_offset;
                    if (offset <= available && (size_t)element_size <= available - offset) {
                        size_t target_offset = base_offset + offset;
                        if (target_offset <= UINTPTR_MAX - owner_addr) {
                            uintptr_t target_addr = owner_addr + target_offset;
                            if (required_align <= 1 || (target_addr % (size_t)required_align) == 0) {
                                return (void *)target_addr;
                            }
                        }
                    }
                }
            }
        }
    }
    return _rt_check_index_ptr_site_slow(site, base_ptr, index, element_size, required_align, access_mode, loc_file, loc_line);
#endif
}

/* Allocate a positive number of raw runtime-owned bytes. */
void *_rt_alloc_impl(dea_int bytes, const char *_loc_file, int _loc_line);

/* Allocate a positive number of raw runtime-owned bytes. */
void *rt_alloc(dea_int bytes);

/* Resize raw runtime-owned storage while preserving it on allocation failure. */
void *_rt_realloc_impl(void *ptr, dea_int new_bytes, const char *_loc_file, int _loc_line);

/* Resize raw runtime-owned storage while preserving it on allocation failure. */
void *rt_realloc(void *ptr, dea_int new_bytes);

/* Release a raw runtime allocation, accepting NULL as a no-op. */
void _rt_free_impl(void *ptr, const char *_loc_file, int _loc_line);

/* Release a raw runtime allocation, accepting NULL as a no-op. */
void rt_free(void *ptr);

/* Allocate a positive count of zero-filled raw runtime-owned elements. */
void *_rt_calloc_impl(dea_int count, dea_int elem_size, const char *_loc_file, int _loc_line);

/* Allocate a positive count of zero-filled raw runtime-owned elements. */
void *rt_calloc(dea_int count, dea_int elem_size);

/* Set memory to a specific byte value. */
void *rt_memset(void *dest, dea_int value, dea_int bytes);

/* Copy memory from source to destination. */
void *rt_memcpy(void *dest, void *src, dea_int bytes);

/* Return a candidate address's byte offset within a half-open byte span. */
dea_int _rt_byte_span_offset(void *base, dea_int span_bytes, void *candidate);

/* Return whether two positive half-open byte spans overlap. */
dea_bool _rt_byte_spans_overlap(void *first, dea_int first_bytes, void *second, dea_int second_bytes);

/* Compare two memory regions. */
dea_int rt_memcmp(void *a, void *b, dea_int bytes);

/* Get a pointer to an element in an array. */
void *rt_array_element(void *array_data, dea_int element_size, dea_int index);

/* Validate foreign storage and register it for checked generated pointer accesses. */
void rt_register_foreign(void *ptr, dea_int bytes, dea_bool read_only);

/* Remove foreign-span registration in checked builds without freeing its storage. */
void rt_unregister_foreign(void *ptr);

/* Validate object storage before its destructor under the selected runtime check policy. */
void *_rt_drop_begin_impl(
    void *ptr,
    dea_int required_size,
    dea_int required_align,
    const char *loc_file,
    int loc_line
);

/* Release object storage after its destructor and record its release location. */
void _rt_drop_finish_impl(void *ptr, const char *loc_file, int loc_line);

/* Validate a derived span against its registered parent in checked builds. */
void *_rt_validate_derived_ptr(
    void *derived,
    void *parent_base,
    dea_int size,
    dea_int align,
    const char *loc_file,
    int loc_line
);

/* Allocate zero-filled object storage owned by a generated new expression. */
void *_rt_alloc_obj_impl(dea_int bytes, const char *_loc_file, int _loc_line);

/* Allocate zero-filled object storage owned by a generated new expression. */
void *_rt_alloc_obj(dea_int bytes);

/* Final mixing function for 32-bit hashes (MurmurHash3 fmix32). */
uint32_t _rt_fmix32(uint32_t x);

/* Fold a 64-bit hash into a 32-bit hash with final mixing. */
uint32_t _rt_fold_u64_to_u32_fmix(uint64_t h);

/* Compute the canonical L1 interface fingerprint digest as lowercase hex. */
void l1c_interface_fingerprint_sip13_hex(const uint8_t *data, int32_t len, uint8_t out_hex[16]);

/* Compiler-facing pointer adapter; input bytes remain read-only. */
void l1c_interface_fingerprint_sip13_hex_bytes(uint8_t *data, int32_t len, uint8_t *out_hex);

/* Hash a boolean value with the runtime bool tag. */
dea_int _rt_hash_bool(dea_bool value, const uint8_t flags);

/* Hash a byte value with the runtime byte tag. */
dea_int _rt_hash_byte(dea_byte value, const uint8_t flags);

/* Hash an integer value with the runtime int tag. */
dea_int _rt_hash_int(dea_int value, const uint8_t flags);

/* Hash a string's byte contents with the runtime string tag. */
dea_int _rt_hash_string(dea_string str, const uint8_t flags);

/* Hash an arbitrary byte sequence with the runtime data tag. */
dea_int _rt_hash_data(void *data, dea_int size, const uint8_t flags);

/* Hash a boolean value. */
dea_int rt_hash_bool(dea_bool value);

/* Hash a byte value. */
dea_int rt_hash_byte(dea_byte value);

/* Hash an integer value. */
dea_int rt_hash_int(dea_int value);

/* Hash a string value. */
dea_int rt_hash_string(dea_string value);

/* Hash raw data. */
dea_int rt_hash_data(void *data, dea_int size);

/* Hash an optional boolean value. */
dea_int rt_hash_opt_bool(dea_opt_bool opt);

/* Hash an optional byte value. */
dea_int rt_hash_opt_byte(dea_opt_byte opt);

/* Hash an optional integer value. */
dea_int rt_hash_opt_int(dea_opt_int opt);

/* Hash an optional string value. */
dea_int rt_hash_opt_string(dea_opt_string opt);

/* Hash a pointer value. */
dea_int rt_hash_ptr(void *ptr);

/* Hash an optional pointer value. */
dea_int rt_hash_opt_ptr(void *opt);

/* =========================================================================
 * Optional real-number helpers
 * ========================================================================= */

#ifdef DEA_USE_SYS_REAL
#include "l1_real.h"
#endif

/* DEA_RT_H */
#endif
