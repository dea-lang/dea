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

typedef int8_t   l0_tiny; /**< Reserved for future L0 language use. */
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

/** Heap-allocated L0 string header. */
typedef struct {
    l0_int refcount;
    l0_int len;
    char bytes[];
} _l0_h_string;

#define L0_STRING_K_STATIC 0
#define L0_STRING_K_HEAP   1

#define DEA_STRING_K_STATIC L0_STRING_K_STATIC
#define DEA_STRING_K_HEAP   L0_STRING_K_HEAP

/** Unified L0 string value: static bytes or one heap string header. */
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

/** Typed empty static string value. */
#define L0_STRING_EMPTY \
    ((l0_string){ \
        .kind = L0_STRING_K_STATIC, \
        .data = { .s_str = { .len = 0, .bytes = NULL } } \
    })

/** Static string initializer for constant byte storage. */
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

/** Runtime time snapshot returned through the L0 `sys.rt` boundary. */
#ifndef L0_DEFINED_l0_sys_rt_RtTimeParts
#define L0_DEFINED_l0_sys_rt_RtTimeParts
struct l0_sys_rt_RtTimeParts {
    l0_int sec;
    l0_int nsec;
};
#endif

/** Runtime filesystem metadata returned through the L0 `sys.rt` boundary. */
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

/**
 * Return the length of a string in bytes.
 *
 * @param str String value.
 * @return String length.
 */
dea_int rt_strlen(dea_string str);

/**
 * Return the byte at a string index.
 *
 * @param s String value.
 * @param index Byte index.
 * @return Byte at `index`.
 */
dea_byte rt_string_get(dea_string s, dea_int index);

/**
 * Return a pointer to the raw byte data of a string.
 *
 * The returned storage is runtime-managed and read-only to checked generated
 * L0 code. It must not be passed to `drop` or `rt_free`.
 *
 * @param s String value.
 * @return Pointer to the first byte.
 */
dea_byte *rt_string_bytes_ptr(dea_string s);

/**
 * Return whether two strings contain equal bytes.
 *
 * @param a First string.
 * @param b Second string.
 * @return Nonzero when the strings are equal.
 */
dea_bool rt_string_equals(dea_string a, dea_string b);

/**
 * Compare two strings lexicographically by byte value.
 *
 * @param a First string.
 * @param b Second string.
 * @return Negative when `a < b`, zero when equal, or positive when `a > b`.
 */
dea_int rt_string_compare(dea_string a, dea_string b);

/**
 * Concatenate two strings.
 *
 * @param a First string.
 * @param b Second string.
 * @return Newly allocated concatenated string.
 */
dea_string rt_string_concat(dea_string a, dea_string b);

/**
 * Return a byte slice of a string.
 *
 * @param s Source string.
 * @param start Inclusive start index.
 * @param end Exclusive end index.
 * @return Newly allocated string slice.
 */
dea_string rt_string_slice(dea_string s, dea_int start, dea_int end);

/**
 * Create a string from one byte.
 *
 * @param b Byte value.
 * @return Newly allocated one-byte string.
 */
dea_string rt_string_from_byte(dea_byte b);

/**
 * Create a string from a byte array.
 *
 * @param bytes Pointer to the byte array.
 * @param len Number of bytes.
 * @return Newly allocated string containing the provided bytes.
 */
dea_string rt_string_from_byte_array(dea_byte *bytes, dea_int len);

/**
 * Increment the reference count of a heap string.
 *
 * This is a no-op for static or non-reference-counted strings.
 *
 * @param s String to retain.
 */
void rt_string_retain(dea_string s);

/**
 * Decrement the reference count of a heap string and free it at zero.
 *
 * This is a no-op for static or non-reference-counted strings.
 *
 * @param s String to release.
 */
void rt_string_release(dea_string s);

/**
 * Execute a system command and return its normalized status.
 *
 * @param cmd Command string.
 * @return Command exit code, `128 + signal` for signal termination, or a
 *         negative value when the shell could not be launched.
 */
dea_int rt_system(dea_string cmd);

/**
 * Return the value of an environment variable.
 *
 * @param name Environment variable name.
 * @return Variable value, or an empty optional when it is unset or invalid.
 */
dea_opt_string rt_get_env_var(dea_string name);

/**
 * Return the number of process arguments.
 *
 * @return Argument count.
 */
dea_int rt_get_argc(void);

/**
 * Return the current process identifier.
 *
 * @return Process identifier.
 */
dea_int rt_get_pid(void);

/**
 * Return one process argument.
 *
 * @param i Argument index.
 * @return Static string view of the selected argument.
 */
dea_string rt_get_argv(dea_int i);

/**
 * Capture current Unix wall time.
 *
 * @param out Time record to populate.
 * @return Nonzero on success.
 */
dea_bool rt_time_unix(struct l0_sys_rt_RtTimeParts *out);

/**
 * Capture current monotonic time.
 *
 * @param out Time record to populate.
 * @return Nonzero on success.
 */
dea_bool rt_time_monotonic(struct l0_sys_rt_RtTimeParts *out);

/**
 * Return whether the runtime supports a monotonic clock.
 *
 * @return Nonzero when supported.
 */
dea_bool rt_time_monotonic_supported(void);

/**
 * Return the local UTC offset for a Unix timestamp.
 *
 * @param unix_sec Unix timestamp in seconds.
 * @return Offset in seconds, or an empty optional on error.
 */
dea_opt_int rt_time_local_offset_sec(dea_int unix_sec);

/**
 * Return whether local time is in daylight-saving time.
 *
 * @param unix_sec Unix timestamp in seconds.
 * @return DST state, or an empty optional on error.
 */
dea_opt_bool rt_time_local_is_dst(dea_int unix_sec);

/**
 * Read an entire file into a string.
 *
 * @param path File path.
 * @return File contents, or an empty optional on error.
 */
dea_opt_string rt_read_file_all(dea_string path);

/**
 * Write a string completely to a file.
 *
 * @param path File path.
 * @param data String contents.
 * @return Nonzero on success.
 */
dea_bool rt_write_file_all(dea_string path, dea_string data);

/**
 * Return basic metadata for a path.
 *
 * @param path Filesystem path.
 * @return File metadata with optional size and timestamp fields.
 */
struct l0_sys_rt_RtFileInfo rt_file_info(dea_string path);

/**
 * Delete a file.
 *
 * @param path File path.
 * @return Nonzero on success.
 */
dea_bool rt_delete_file(dea_string path);

/**
 * Read bytes from standard input.
 *
 * @param buf Destination buffer.
 * @param capacity Maximum number of bytes to read.
 * @return Bytes read, zero on EOF, or `-1` on error.
 */
dea_int rt_stdin_read(dea_byte *buf, dea_int capacity);

/**
 * Write bytes to standard output.
 *
 * @param buf Source buffer.
 * @param len Maximum number of bytes to write.
 * @return Bytes written, or `-1` on error.
 */
dea_int rt_stdout_write(dea_byte *buf, dea_int len);

/**
 * Write bytes to standard error.
 *
 * @param buf Source buffer.
 * @param len Maximum number of bytes to write.
 * @return Bytes written, or `-1` on error.
 */
dea_int rt_stderr_write(dea_byte *buf, dea_int len);

/** Flush the standard output buffer. */
void rt_flush_stdout(void);

/** Flush the standard error buffer. */
void rt_flush_stderr(void);

/**
 * Print a string to standard output without a newline.
 *
 * @param s String to print.
 */
void rt_print(dea_string s);

/**
 * Print a string to standard error without a newline.
 *
 * @param s String to print.
 */
void rt_print_stderr(dea_string s);

/** Print a newline to standard output. */
void rt_println(void);

/** Print a newline to standard error. */
void rt_println_stderr(void);

/**
 * Print an integer to standard output.
 *
 * @param x Integer to print.
 */
void rt_print_int(dea_int x);

/**
 * Print an integer to standard error.
 *
 * @param x Integer to print.
 */
void rt_print_int_stderr(dea_int x);

/**
 * Print a boolean to standard output.
 *
 * @param x Boolean to print.
 */
void rt_print_bool(dea_bool x);

/**
 * Print a boolean to standard error.
 *
 * @param x Boolean to print.
 */
void rt_print_bool_stderr(dea_bool x);

/**
 * Read one line from standard input.
 *
 * @return Line without the trailing newline, or an empty optional at EOF.
 */
dea_opt_string rt_read_line(void);

/**
 * Read one byte from standard input.
 *
 * @return Byte value, or `-1` at EOF or on error.
 */
dea_int rt_read_char(void);

/**
 * Abort execution with a message.
 *
 * @param message Abort message.
 */
void rt_abort(dea_string message);

/**
 * Exit the process with a status code.
 *
 * @param code Exit status.
 */
void rt_exit(dea_int code);

/**
 * Seed the runtime pseudo-random number generator.
 *
 * @param seed Integer seed.
 */
void rt_srand(dea_int seed);

/**
 * Return a pseudo-random integer below an upper bound.
 *
 * @param max Exclusive upper bound.
 * @return Random integer in `[0, max)`.
 */
dea_int rt_rand(dea_int max);

/**
 * Return the current C runtime error number.
 *
 * @return Current `errno` value.
 */
dea_int rt_errno(void);

/**
 * Allocate raw memory.
 *
 * @param bytes Number of bytes to allocate; must be positive.
 * @return Allocated pointer, or `NULL` on allocation failure.
 */
void *rt_alloc(dea_int bytes);

/**
 * Resize a raw runtime allocation.
 *
 * If `ptr` is `NULL`, this behaves like `rt_alloc`. Checked builds reject
 * pointers owned by `new`, ARC strings, static strings, or foreign storage.
 *
 * @param ptr Existing raw allocation, or `NULL`.
 * @param new_bytes New positive size in bytes.
 * @return Resized pointer, or `NULL` on allocation failure.
 */
void *rt_realloc(void *ptr, dea_int new_bytes);

/**
 * Free a raw runtime allocation.
 *
 * @param ptr Pointer returned by `rt_alloc`, `rt_calloc`, or `rt_realloc`.
 */
void rt_free(void *ptr);

/**
 * Allocate zero-initialized raw memory.
 *
 * @param count Positive element count.
 * @param elem_size Positive element size in bytes.
 * @return Allocated pointer, or `NULL` on allocation failure.
 */
void *rt_calloc(dea_int count, dea_int elem_size);

/**
 * Fill a memory region with one byte value.
 *
 * @param dest Destination pointer.
 * @param value Byte value, converted as by C `memset`.
 * @param bytes Number of bytes.
 * @return `dest`.
 */
void *rt_memset(void *dest, dea_int value, dea_int bytes);

/**
 * Copy bytes between non-overlapping memory regions.
 *
 * @param dest Destination pointer.
 * @param src Source pointer.
 * @param bytes Number of bytes.
 * @return `dest`.
 */
void *rt_memcpy(void *dest, void *src, dea_int bytes);

/**
 * Compare two memory regions.
 *
 * @param a First pointer.
 * @param b Second pointer.
 * @param bytes Number of bytes.
 * @return Negative, zero, or positive according to byte ordering.
 */
dea_int rt_memcmp(void *a, void *b, dea_int bytes);

/**
 * Return a pointer to an array element.
 *
 * @param array_data Array base pointer.
 * @param element_size Positive element size in bytes.
 * @param index Non-negative element index.
 * @return Pointer to the selected element.
 */
void *rt_array_element(void *array_data, dea_int element_size, dea_int index);

/**
 * Register externally owned storage with the checked pointer runtime.
 *
 * Repeating an identical live registration is a no-op. Registration does not
 * transfer ownership; unregister the range before its external lifetime ends.
 *
 * @param ptr Exact storage base pointer.
 * @param bytes Positive accessible extent in bytes.
 * @param read_only Whether checked writes must be rejected.
 */
void rt_register_foreign(void *ptr, dea_int bytes, dea_bool read_only);

/**
 * Remove a foreign-storage registration without freeing its payload.
 *
 * @param ptr Exact base pointer passed to `rt_register_foreign`.
 */
void rt_unregister_foreign(void *ptr);

/**
 * Hash a boolean value.
 *
 * @param value Boolean value.
 * @return 32-bit hash.
 */
dea_int rt_hash_bool(dea_bool value);

/**
 * Hash a byte value.
 *
 * @param value Byte value.
 * @return 32-bit hash.
 */
dea_int rt_hash_byte(dea_byte value);

/**
 * Hash an integer value.
 *
 * @param value Integer value.
 * @return 32-bit hash.
 */
dea_int rt_hash_int(dea_int value);

/**
 * Hash a string value.
 *
 * @param value String value.
 * @return 32-bit hash.
 */
dea_int rt_hash_string(dea_string value);

/**
 * Hash raw bytes.
 *
 * @param data Data pointer.
 * @param size Number of bytes.
 * @return 32-bit hash.
 */
dea_int rt_hash_data(void *data, dea_int size);

/**
 * Hash an optional boolean value.
 *
 * @param opt Optional boolean.
 * @return 32-bit hash.
 */
dea_int rt_hash_opt_bool(dea_opt_bool opt);

/**
 * Hash an optional byte value.
 *
 * @param opt Optional byte.
 * @return 32-bit hash.
 */
dea_int rt_hash_opt_byte(dea_opt_byte opt);

/**
 * Hash an optional integer value.
 *
 * @param opt Optional integer.
 * @return 32-bit hash.
 */
dea_int rt_hash_opt_int(dea_opt_int opt);

/**
 * Hash an optional string value with presence-sensitive domain separation.
 *
 * @param opt Optional string.
 * @return 32-bit hash.
 */
dea_int rt_hash_opt_string(dea_opt_string opt);

/**
 * Hash a pointer address.
 *
 * @param ptr Non-null pointer.
 * @return 32-bit hash.
 */
dea_int rt_hash_ptr(void *ptr);

/**
 * Hash an optional pointer address.
 *
 * @param opt Non-null optional pointer representation.
 * @return 32-bit hash.
 */
dea_int rt_hash_opt_ptr(void *opt);

#endif /* DEA_RT_H */
