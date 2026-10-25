#ifndef DEA_RT_H
#define DEA_RT_H

/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

/**
 * @file dea_rt.h
 * Public L0 C runtime interface.
 *
 * This header contains the declaration-only C interoperability surface for
 * Dea/L0. Additional C translation units should include this header rather
 * than `l0_runtime.h`, whose implementation definitions are owned by the
 * single generated L0 translation unit.
 *
 * The `dea_*` names and public signatures that do not mention level-mangled
 * records form the source-compatible subset shared with L1. The existing
 * `l0_*` names remain available for L0-specific C code. This source
 * compatibility does not make L0 and L1 runtime binaries interchangeable.
 *
 * @since L0 2.1.0
 */

#include <stddef.h>
#include <stdint.h>

/* =========================================================================
 * L0 ABI types and cross-level Dea aliases
 * ========================================================================= */

typedef uint8_t  l0_bool;

/**
 * Reserved for future L0 language use.
 */

typedef int8_t   l0_tiny;
typedef int16_t  l0_short;
typedef int32_t  l0_int;
typedef int64_t  l0_long;

typedef uint8_t  l0_byte;
typedef uint16_t l0_ushort;
typedef uint32_t l0_uint;
typedef uint64_t l0_ulong;

typedef float    l0_float;
typedef double   l0_double;

typedef l0_bool   dea_bool;
typedef l0_tiny   dea_tiny;
typedef l0_short  dea_short;
typedef l0_int    dea_int;
typedef l0_long   dea_long;
typedef l0_byte   dea_byte;
typedef l0_ushort dea_ushort;
typedef l0_uint   dea_uint;
typedef l0_ulong  dea_ulong;
typedef l0_float  dea_float;
typedef l0_double dea_double;

/**
 * Heap-allocated L0 string header.
 */
typedef struct {
    l0_int refcount;
    l0_int len;
    char bytes[];
} _l0_h_string;

#define L0_STRING_K_STATIC 0
#define L0_STRING_K_HEAP   1

#define DEA_STRING_K_STATIC L0_STRING_K_STATIC
#define DEA_STRING_K_HEAP   L0_STRING_K_HEAP

/**
 * Unified L0 string value: static bytes or one heap string header.
 */
typedef struct {
    unsigned int kind : 1;
    unsigned int : 0;
    union {
        struct {
            l0_int len;
            const char *bytes;
        } s_str;
        _l0_h_string *h_str;
    } data;
} l0_string;

typedef l0_string dea_string;

/**
 * Typed empty static string value.
 */
#define L0_STRING_EMPTY \
    ((l0_string){ \
        .kind = L0_STRING_K_STATIC, \
        .data = { .s_str = { .len = 0, .bytes = NULL } } \
    })

/**
 * Static string initializer for constant byte storage.
 */
#define L0_STRING_CONST(str_data, str_len) \
    { .kind = L0_STRING_K_STATIC, .data.s_str = { .len = (str_len), .bytes = (str_data) } }

#define DEA_STRING_EMPTY L0_STRING_EMPTY
#define DEA_STRING_CONST(str_data, str_len) L0_STRING_CONST((str_data), (str_len))

/* =========================================================================
 * Optional ABI wrappers
 * ========================================================================= */

#ifndef L0_OPT_BOOL_DEFINED
#define L0_OPT_BOOL_DEFINED
typedef struct { l0_bool has_value; l0_bool value; } l0_opt_bool;
#endif

#ifndef L0_OPT_BYTE_DEFINED
#define L0_OPT_BYTE_DEFINED
typedef struct { l0_bool has_value; l0_byte value; } l0_opt_byte;
#endif

#ifndef L0_OPT_INT_DEFINED
#define L0_OPT_INT_DEFINED
typedef struct { l0_bool has_value; l0_int value; } l0_opt_int;
#endif

#ifndef L0_OPT_STRING_DEFINED
#define L0_OPT_STRING_DEFINED
typedef struct { l0_bool has_value; l0_string value; } l0_opt_string;
#endif

#ifndef DEA_OPT_BOOL_DEFINED
#define DEA_OPT_BOOL_DEFINED
typedef l0_opt_bool dea_opt_bool;
#endif

#ifndef DEA_OPT_BYTE_DEFINED
#define DEA_OPT_BYTE_DEFINED
typedef l0_opt_byte dea_opt_byte;
#endif

#ifndef DEA_OPT_INT_DEFINED
#define DEA_OPT_INT_DEFINED
typedef l0_opt_int dea_opt_int;
#endif

#ifndef DEA_OPT_STRING_DEFINED
#define DEA_OPT_STRING_DEFINED
typedef l0_opt_string dea_opt_string;
#endif

#define L0_OPT_STRING_NULL \
    ((l0_opt_string){ \
        .has_value = 0, \
        .value = { \
            .kind = L0_STRING_K_STATIC, \
            .data = { .s_str = { .len = 0, .bytes = NULL } } \
        } \
    })

#define L0_OPT_STRING_EMPTY \
    ((l0_opt_string){ \
        .has_value = 1, \
        .value = { \
            .kind = L0_STRING_K_STATIC, \
            .data = { .s_str = { .len = 0, .bytes = NULL } } \
        } \
    })

#define DEA_OPT_STRING_NULL  L0_OPT_STRING_NULL
#define DEA_OPT_STRING_EMPTY L0_OPT_STRING_EMPTY

/**
 * Runtime time snapshot returned through the L0 `sys.rt` boundary.
 */
#ifndef L0_DEFINED_l0_sys_rt_RtTimeParts
#define L0_DEFINED_l0_sys_rt_RtTimeParts
struct l0_sys_rt_RtTimeParts {
    l0_int sec;
    l0_int nsec;
};
#endif

/**
 * Runtime filesystem metadata returned through the L0 `sys.rt` boundary.
 */
#ifndef L0_DEFINED_l0_sys_rt_RtFileInfo
#define L0_DEFINED_l0_sys_rt_RtFileInfo
struct l0_sys_rt_RtFileInfo {
    l0_bool exists;
    l0_bool is_file;
    l0_bool is_dir;
    l0_opt_int size;
    l0_opt_int mtime_sec;
    l0_opt_int mtime_nsec;
};
#endif

/* =========================================================================
 * Public runtime function declarations
 * ========================================================================= */

/* Return the length of a string in bytes. */
dea_int rt_strlen(dea_string str);

/* Return the byte at a string index. */
dea_byte rt_string_get(dea_string s, dea_int index);

/* Return a pointer to the raw byte data of a string. */
dea_byte *rt_string_bytes_ptr(dea_string s);

/* Return whether two strings contain equal bytes. */
dea_bool rt_string_equals(dea_string a, dea_string b);

/* Compare two strings lexicographically by byte value. */
dea_int rt_string_compare(dea_string a, dea_string b);

/* Concatenate two strings. */
dea_string rt_string_concat(dea_string a, dea_string b);

/* Return a byte slice of a string. */
dea_string rt_string_slice(dea_string s, dea_int start, dea_int end);

/* Create a string from one byte. */
dea_string rt_string_from_byte(dea_byte b);

/* Create a string from a byte array. */
dea_string rt_string_from_byte_array(dea_byte *bytes, dea_int len);

/* Increment the reference count of a heap string. */
void rt_string_retain(dea_string s);

/* Decrement the reference count of a heap string and free it at zero. */
void rt_string_release(dea_string s);

/* Execute a system command and return its normalized status. */
dea_int rt_system(dea_string cmd);

/* Return the value of an environment variable. */
dea_opt_string rt_get_env_var(dea_string name);

/* Return the number of process arguments. */
dea_int rt_get_argc(void);

/* Return the current process identifier. */
dea_int rt_get_pid(void);

/* Return one process argument. */
dea_string rt_get_argv(dea_int i);

/* Capture current Unix wall time. */
dea_bool rt_time_unix(struct l0_sys_rt_RtTimeParts *out);

/* Capture current monotonic time. */
dea_bool rt_time_monotonic(struct l0_sys_rt_RtTimeParts *out);

/* Return whether the runtime supports a monotonic clock. */
dea_bool rt_time_monotonic_supported(void);

/* Return the local UTC offset for a Unix timestamp. */
dea_opt_int rt_time_local_offset_sec(dea_int unix_sec);

/* Return whether local time is in daylight-saving time. */
dea_opt_bool rt_time_local_is_dst(dea_int unix_sec);

/* Read an entire file into a string. */
dea_opt_string rt_read_file_all(dea_string path);

/* Write a string completely to a file. */
dea_bool rt_write_file_all(dea_string path, dea_string data);

/* Return basic metadata for a path. */
struct l0_sys_rt_RtFileInfo rt_file_info(dea_string path);

/* Delete a file. */
dea_bool rt_delete_file(dea_string path);

/* Read bytes from standard input. */
dea_int rt_stdin_read(dea_byte *buf, dea_int capacity);

/* Write bytes to standard output. */
dea_int rt_stdout_write(dea_byte *buf, dea_int len);

/* Write bytes to standard error. */
dea_int rt_stderr_write(dea_byte *buf, dea_int len);

/* Flush the standard output buffer. */
void rt_flush_stdout(void);

/* Flush the standard error buffer. */
void rt_flush_stderr(void);

/* Print a string to standard output without a newline. */
void rt_print(dea_string s);

/* Print a string to standard error without a newline. */
void rt_print_stderr(dea_string s);

/* Print a newline to standard output. */
void rt_println(void);

/* Print a newline to standard error. */
void rt_println_stderr(void);

/* Print an integer to standard output. */
void rt_print_int(dea_int x);

/* Print an integer to standard error. */
void rt_print_int_stderr(dea_int x);

/* Print a boolean to standard output. */
void rt_print_bool(dea_bool x);

/* Print a boolean to standard error. */
void rt_print_bool_stderr(dea_bool x);

/* Read one line from standard input. */
dea_opt_string rt_read_line(void);

/* Read one byte from standard input. */
dea_int rt_read_char(void);

/* Abort execution with a message. */
void rt_abort(dea_string message);

/* Exit the process with a status code. */
void rt_exit(dea_int code);

/* Seed the runtime pseudo-random number generator. */
void rt_srand(dea_int seed);

/* Return a pseudo-random integer below an upper bound. */
dea_int rt_rand(dea_int max);

/* Return the current C runtime error number. */
dea_int rt_errno(void);

/* Allocate raw memory. */
void *rt_alloc(dea_int bytes);

/* Resize a raw runtime allocation. */
void *rt_realloc(void *ptr, dea_int new_bytes);

/* Free a raw runtime allocation. */
void rt_free(void *ptr);

/* Allocate zero-initialized raw memory. */
void *rt_calloc(dea_int count, dea_int elem_size);

/* Fill a memory region with one byte value. */
void *rt_memset(void *dest, dea_int value, dea_int bytes);

/* Copy bytes between non-overlapping memory regions. */
void *rt_memcpy(void *dest, void *src, dea_int bytes);

/* Return a candidate address's offset within a half-open byte span. */
dea_int _rt_byte_span_offset(void *base, dea_int span_bytes, void *candidate);

/* Return whether two positive half-open byte spans overlap. */
dea_bool _rt_byte_spans_overlap(void *first, dea_int first_bytes, void *second, dea_int second_bytes);

/* Compare two memory regions. */
dea_int rt_memcmp(void *a, void *b, dea_int bytes);

/* Return a pointer to an array element. */
void *rt_array_element(void *array_data, dea_int element_size, dea_int index);

/* Register externally owned storage with the checked pointer runtime. */
void rt_register_foreign(void *ptr, dea_int bytes, dea_bool read_only);

/* Remove a foreign-storage registration without freeing its payload. */
void rt_unregister_foreign(void *ptr);

/* Hash a boolean value. */
dea_int rt_hash_bool(dea_bool value);

/* Hash a byte value. */
dea_int rt_hash_byte(dea_byte value);

/* Hash an integer value. */
dea_int rt_hash_int(dea_int value);

/* Hash a string value. */
dea_int rt_hash_string(dea_string value);

/* Hash raw bytes. */
dea_int rt_hash_data(void *data, dea_int size);

/* Hash an optional boolean value. */
dea_int rt_hash_opt_bool(dea_opt_bool opt);

/* Hash an optional byte value. */
dea_int rt_hash_opt_byte(dea_opt_byte opt);

/* Hash an optional integer value. */
dea_int rt_hash_opt_int(dea_opt_int opt);

/* Hash an optional string value with presence-sensitive domain separation. */
dea_int rt_hash_opt_string(dea_opt_string opt);

/* Hash a pointer address. */
dea_int rt_hash_ptr(void *ptr);

/* Hash an optional pointer address. */
dea_int rt_hash_opt_ptr(void *opt);

/* DEA_RT_H */
#endif
