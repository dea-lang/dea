/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for the dea_string type: heap allocation and lifecycle,
 * reference counting, and content operations (length, indexing, equality,
 * comparison, concatenation, slicing, byte conversions).
 * ========================================================================= */

/**
 * Create a Dea string from a constant C string.
 * Returns a string with len=0 if c_str is NULL.
 *
 * Note: Does NOT allocate or copy - just wraps the existing C string.
 * Use only for string literals or static const data.
 *
 * @param c_str Constant C string.
 * @return Dea string.
 */
dea_string _rt_dea_string_from_const_literal(const char *c_str) {
    dea_string s;
    if (c_str == NULL) {
        return DEA_STRING_EMPTY;
    } else {
        size_t len = strlen(c_str);
        if (len > INT32_MAX) {
            _rt_panic("_rt_dea_string_from_const_literal: string too long for dea_int");
        }
        s.kind = DEA_STRING_K_STATIC;
        s.data.s_str.len = (dea_int)len;
        s.data.s_str.bytes = c_str;
    }
    return s;
}

/**
 * Initialize a heap-allocated dea_string in the given memory.
 * Character data (bytes[]) is uninitialized; caller must fill it in.
 * Length is assumed to be already validated by the caller.
 * Size of mem MUST be at least sizeof(_dea_h_string) + s_len + 1.
 *
 * The returned string is of kind DEA_STRING_K_HEAP and
 * its data is null-terminated in advance.
 *
 * @param mem Allocated memory block.
 * @param s_len Length of the string.
 * @return Initialized Dea string.
 */
dea_string _rt_init_heap_string(void *mem, dea_int s_len) {
    dea_string s;
    _dea_h_string *hs = (_dea_h_string *)mem;
    hs->refcount = 1;       /* reference counted */
    hs->len = (dea_int)s_len;
    hs->bytes[s_len] = '\0';   /* null-terminate */

    s.kind = DEA_STRING_K_HEAP;
    s.data.h_str = hs;
    return s;
}

/**
 * Allocate a new reference counted dea_string of the given length.
 * Character data (bytes[]) is uninitialized; caller must fill it in.
 * Panics on allocation failure or negative length.
 * Size of allocated memory is: string header + len + 1 for null terminator.
 *
 * The returned string is of kind DEA_STRING_K_HEAP and
 * its data is null-terminated in advance.
 *
 * @param len Length of the string.
 * @return Allocated Dea string.
 */
#ifdef DEA_TRACE_MEMORY
dea_string _rt_alloc_string_impl(dea_int len, const char *_loc_file, int _loc_line) {
    if (len < 0) {
        _rt_panic("_rt_alloc_string: negative length");
    }
    void *mem = malloc(sizeof(_dea_h_string) + len + 1);
    if (mem == NULL) {
        _rt_panic("_rt_alloc_string: out of memory");
    }
    dea_string s = _rt_init_heap_string(mem, len);
    _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=alloc_string len=%d ptr=%p", (int)len, (void*)s.data.h_str);
    return s;
}
#define _rt_alloc_string(len) _rt_alloc_string_impl((len), __FILE__, __LINE__)
#else
dea_string _rt_alloc_string(dea_int len) {
    if (len < 0) {
        _rt_panic("_rt_alloc_string: negative length");
    }
    void *mem = malloc(sizeof(_dea_h_string) + len + 1);
    if (mem == NULL) {
        _rt_panic("_rt_alloc_string: out of memory");
    }
    dea_string s = _rt_init_heap_string(mem, len);
    _RT_TRACE_MEM("op=alloc_string len=%d ptr=%p", (int)len, (void*)s.data.h_str);
    return s;
}
#endif

/**
 * Free a string's allocated data, if applicable.
 * If reference counted, decrements reference count and frees when it reaches zero.
 *
 * @param str Dea string to free.
 */
#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)
void _rt_free_string_impl(dea_string str, const char *_loc_file, int _loc_line) {
    if (str.kind == DEA_STRING_K_STATIC) {
        /* Static string: do nothing */
        _RT_TRACE_ARC_LOC(_loc_file, _loc_line, "op=release kind=static ptr=%p rc_before=-1 rc_after=-1 action=noop", (void*)str.data.s_str.bytes);
        return;
    }
    _dea_h_string *hs = str.data.h_str;
    if (hs == NULL) {
        _RT_TRACE_ARC_LOC(_loc_file, _loc_line, "op=release kind=heap ptr=%p rc_before=-1 rc_after=-1 action=panic-null-ptr", (void*)hs);
        _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=panic-null-ptr", (void*)hs);
        _rt_panic("_rt_free_string: null heap string pointer");
    }
    dea_int rc_before = hs->refcount;
    if (rc_before > 0 && rc_before < INT32_MAX) {
        /* Reference counted string */
        hs->refcount--;
        if (hs->refcount == 0) {
            _RT_TRACE_ARC_LOC(
                _loc_file, _loc_line,
                "op=release kind=heap ptr=%p rc_before=%d rc_after=0 action=free",
                (void*)hs, (int)rc_before
            );
            _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=free", (void*)hs);
            hs->refcount = _RT_MEM_SENTINEL; /* prevent double free */
            _rt_untrack_arc_alloc((void*)hs->bytes);
            free((void*)hs);
        } else {
            _RT_TRACE_ARC_LOC(
                _loc_file, _loc_line,
                "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=keep",
                (void*)hs, (int)rc_before, (int)hs->refcount
            );
            _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=decrement-only", (void*)hs);
        }
        return;
    }
    if (rc_before == INT32_MAX) {
        /* Non-reference counted string: do nothing */
        _RT_TRACE_ARC_LOC(
            _loc_file, _loc_line,
            "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=noop-nonref",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=noop-nonref", (void*)hs);
        return;
    }
    if (rc_before == _RT_MEM_SENTINEL) {
        _RT_TRACE_ARC_LOC(
            _loc_file, _loc_line,
            "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-double-free",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=panic-double-free", (void*)hs);
        _rt_panic("_rt_free_string: double free detected");
    }
    _RT_TRACE_ARC_LOC(
        _loc_file, _loc_line,
        "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-invalid-state",
        (void*)hs, (int)rc_before, (int)rc_before
    );
    _RT_TRACE_MEM_LOC(_loc_file, _loc_line, "op=free_string ptr=%p action=panic-invalid-state", (void*)hs);
    _rt_panic_fmt("_rt_free_string: invalid string refcount state: %d", (int)hs->refcount);
}
#define _rt_free_string(str) _rt_free_string_impl((str), __FILE__, __LINE__)
#else
void _rt_free_string(dea_string str) {
    if (str.kind == DEA_STRING_K_STATIC) {
        /* Static string: do nothing */
        _RT_TRACE_ARC("op=release kind=static ptr=%p rc_before=-1 rc_after=-1 action=noop", (void*)str.data.s_str.bytes);
        return;
    }
    _dea_h_string *hs = str.data.h_str;
    if (hs == NULL) {
        _RT_TRACE_ARC("op=release kind=heap ptr=%p rc_before=-1 rc_after=-1 action=panic-null-ptr", (void*)hs);
        _RT_TRACE_MEM("op=free_string ptr=%p action=panic-null-ptr", (void*)hs);
        _rt_panic("_rt_free_string: null heap string pointer");
    }
    dea_int rc_before = hs->refcount;
    if (rc_before > 0 && rc_before < INT32_MAX) {
        /* Reference counted string */
        hs->refcount--;
        if (hs->refcount == 0) {
            _RT_TRACE_ARC(
                "op=release kind=heap ptr=%p rc_before=%d rc_after=0 action=free",
                (void*)hs, (int)rc_before
            );
            _RT_TRACE_MEM("op=free_string ptr=%p action=free", (void*)hs);
            hs->refcount = _RT_MEM_SENTINEL; /* prevent double free */
            _rt_untrack_arc_alloc((void*)hs->bytes);
            free((void*)hs);
        } else {
            _RT_TRACE_ARC(
                "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=keep",
                (void*)hs, (int)rc_before, (int)hs->refcount
            );
            _RT_TRACE_MEM("op=free_string ptr=%p action=decrement-only", (void*)hs);
        }
        return;
    }
    if (rc_before == INT32_MAX) {
        /* Non-reference counted string: do nothing */
        _RT_TRACE_ARC(
            "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=noop-nonref",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _RT_TRACE_MEM("op=free_string ptr=%p action=noop-nonref", (void*)hs);
        return;
    }
    if (rc_before == _RT_MEM_SENTINEL) {
        _RT_TRACE_ARC(
            "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-double-free",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _RT_TRACE_MEM("op=free_string ptr=%p action=panic-double-free", (void*)hs);
        _rt_panic("_rt_free_string: double free detected");
    }
    _RT_TRACE_ARC(
        "op=release kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-invalid-state",
        (void*)hs, (int)rc_before, (int)rc_before
    );
    _RT_TRACE_MEM("op=free_string ptr=%p action=panic-invalid-state", (void*)hs);
    _rt_panic_fmt("_rt_free_string: invalid string refcount state: %d", (int)hs->refcount);
}
#endif

/**
 * Reallocate a heap string to a new length.
 *
 * @param s Current Dea string.
 * @param new_len New length.
 * @return Updated Dea string.
 */
dea_string _rt_realloc_string(dea_string s, dea_int new_len) {
    if (new_len < 0) {
        _rt_panic("_rt_realloc_string: negative length");
    }
    if (new_len == 0) {
        _rt_free_string(s);
        return DEA_STRING_EMPTY;
    }
    if (s.kind == DEA_STRING_K_STATIC && s.data.s_str.len == 0) {
        /* Reallocating empty static string: allocate new heap string */
        return _rt_alloc_string(new_len);
    }
    if (s.kind != DEA_STRING_K_HEAP || s.data.h_str == NULL) {
        _RT_TRACE_MEM("op=realloc_string old_ptr=%p new_len=%d action=panic-invalid-string", (void*)s.data.h_str, (int)new_len);
        _rt_panic("_rt_realloc_string: string is not heap-allocated");
    }

    /* Use volatile to prevent the compiler from tracking the pointer across realloc
       and complaining about use-after-free when tracing the old pointer value. */
    volatile uintptr_t old_ptr_addr = (uintptr_t)s.data.h_str;
    size_t new_size = sizeof(_dea_h_string) + new_len + 1;
    _rt_untrack_arc_alloc(s.data.h_str->bytes);
    void *new_mem = realloc((void*)old_ptr_addr, new_size);
    if (new_mem == NULL) {
        _RT_TRACE_MEM("op=realloc_string old_ptr=%p new_len=%d action=panic-oom", (void*)old_ptr_addr, (int)new_len);
        _rt_panic("_rt_realloc_string: out of memory");
    }
    _dea_h_string *new_hs = (_dea_h_string *)new_mem;
    new_hs->len = new_len;
    new_hs->bytes[new_len] = '\0'; /* null-terminate */
    s.data.h_str = new_hs;
    _RT_TRACE_MEM(
        "op=realloc_string old_ptr=%p new_ptr=%p new_len=%d action=ok",
        (void*)old_ptr_addr, (void*)new_hs, (int)new_len
    );
    return s;
}

/**
 * Create a new reference counted dea_string from a null-terminated C string.
 * Allocates new memory and copies data.
 *
 * @param c_str Null-terminated C string.
 * @return Dea string.
 */
dea_string _rt_new_dea_string(const char *c_str) {
    if (c_str == NULL) {
        return DEA_STRING_EMPTY;
    }
    size_t len = strlen(c_str);
    if ((uint64_t)len > INT32_MAX) {
        _rt_panic("_rt_new_dea_string: string too long for dea_int");
    }
    dea_string s = _rt_alloc_string((dea_int)len);
    _dea_h_string *hs = s.data.h_str;
    memcpy(hs->bytes, c_str, len + 1);

    return s;
}

/**
 * Gets the null-terminated C string underlying a Dea string.
 * or NULL if not available, e.g. for static empty strings.
 * Useful when interfacing with C APIs that require null-terminated strings.
 *
 * Note: This is an internal helper, not exposed to Dea code.
 *
 * @param s Dea string.
 * @return Pointer to character data.
 */
char *_rt_string_bytes(dea_string s) {
    switch (s.kind) {
        case DEA_STRING_K_STATIC:
            return (char*)s.data.s_str.bytes;
        case DEA_STRING_K_HEAP:
            if (s.data.h_str != NULL) {
                return s.data.h_str->bytes;
            }
            /* fallthrough */
        default:
            _rt_panic_fmt("_rt_string_bytes: invalid string kind: %d or null data", (int)s.kind);
            return NULL; /* Unreachable */
    }
}

/* =========================================================================
 * User string operations
 * ========================================================================= */

/**
 * Get the length of a string.
 *
 * @param str Dea string.
 * @return Length in bytes.
 *
 * Dea signature: `extern func rt_strlen(str: string) -> int;`
 */
dea_int rt_strlen(dea_string str) {
    switch(str.kind) {
    case DEA_STRING_K_STATIC:
        return str.data.s_str.len;
    case DEA_STRING_K_HEAP:
        if (str.data.h_str == NULL) {
            _rt_panic("rt_strlen: string data is null");
            return 0; /* Unreachable */
        }
        return str.data.h_str->len;
    default:
        _rt_panic_fmt("rt_strlen: invalid string kind: %d", (int)str.kind);
        return 0; /* Unreachable */
    }
}

/**
 * Bounds-checked character access.
 * Returns the character at the given index, or panics if out of bounds.
 *
 * @param a Dea string.
 * @param index Index.
 * @return Byte value.
 *
 * Dea signature: `extern func rt_string_get(s: string, index: int) -> byte;`
 */
dea_byte rt_string_get(dea_string a, dea_int index) {
    dea_int a_len = rt_strlen(a);
    if (index < 0 || index >= a_len) {
        _rt_panic_fmt("rt_string_get: index %d out of bounds for string of length %d",
                      (int)index, (int)a_len);
    }
    char *a_data = _rt_string_bytes(a);
    if (a_data == NULL) {
        _rt_panic("rt_string_get: string data is null");
    }
    return (dea_byte)a_data[index];
}

/**
 * Return a pointer to the raw byte data of a string.
 *
 * @param s Dea string.
 * @return Pointer to the first byte.
 *
 * Dea signature: `extern func rt_string_bytes_ptr(s: string) -> byte*;`
 *
 * Heap and static string storage is registered with the pointer access
 * tracker lazily here, at first raw-byte exposure, so the returned pointer
 * stays dereferenceable by checked generated code while strings that never
 * hand out raw bytes stay out of the tracker. Both are runtime-managed:
 * passing the returned pointer to `drop` or `rt_free` is a runtime error.
 */
dea_byte *rt_string_bytes_ptr(dea_string s) {
    char *bytes = _rt_string_bytes(s);
    if (s.kind == DEA_STRING_K_STATIC && bytes != NULL) {
        _rt_track_static_bytes(bytes, (size_t)s.data.s_str.len + 1);
    } else if (s.kind == DEA_STRING_K_HEAP && s.data.h_str != NULL) {
        _dea_h_string *hs = s.data.h_str;
        _rt_track_arc_bytes((void*)hs->bytes, (size_t)hs->len + 1);
    }
    return (dea_byte*)bytes;
}

/**
 * Check if two strings are equal.
 *
 * @param a First string.
 * @param b Second string.
 * @return 1 if equal, 0 otherwise.
 *
 * Dea signature: `extern func rt_string_equals(a: string, b: string) -> bool;`
 */
dea_bool rt_string_equals(dea_string a, dea_string b) {
    dea_int a_len = rt_strlen(a);
    dea_int b_len = rt_strlen(b);
    if (a_len != b_len) {
        return 0;
    }
    if (a_len == 0) {
        return 1;  /* Both empty */
    }
    char *a_data = _rt_string_bytes(a);
    char *b_data = _rt_string_bytes(b);
    if (a_data == NULL || b_data == NULL) {
        _rt_panic("rt_string_equals: invalid state - string data is null");
    }
    return memcmp(a_data, b_data, (size_t)a_len) == 0 ? 1 : 0;
}

/**
 * Compare two strings lexicographically.
 * Returns 0 if equal, <0 if a < b, >0 if a > b.
 *
 * @param a First string.
 * @param b Second string.
 * @return Comparison result.
 *
 * Dea signature: `extern func rt_string_compare(a: string, b: string) -> int;`
 */
dea_int rt_string_compare(dea_string a, dea_string b) {
    dea_int a_len = rt_strlen(a);
    dea_int b_len = rt_strlen(b);

    dea_int min_len = a_len;
    if (b_len < min_len) {
        min_len = b_len;
    }

    if (min_len > 0) {
        char *a_data = _rt_string_bytes(a);
        char *b_data = _rt_string_bytes(b);
        if (a_data == NULL || b_data == NULL) {
            _rt_panic("rt_string_compare: string data is null");
        }

        int result = memcmp(a_data, b_data, (size_t)min_len);
        if (result < 0) {
            return -1;
        }
        if (result > 0) {
            return 1;
        }
    }

    if (a_len < b_len) {
        return -1;
    }
    if (a_len > b_len) {
        return 1;
    }
    return 0;
}

/**
 * Concatenate two strings (allocates new memory).
 * Returns a heap-allocated string containing a + b.
 *
 * @param a First string.
 * @param b Second string.
 * @return Concatenated string.
 *
 * Dea signature: `extern func rt_string_concat(a: string, b: string) -> string;`
 */
#ifdef DEA_TRACE_MEMORY
dea_string _rt_string_concat_impl(dea_string a, dea_string b, const char *_loc_file, int _loc_line) {
    dea_int a_len = rt_strlen(a);
    dea_int b_len = rt_strlen(b);

    /* Check for overflow in total length */
    if (a_len > INT32_MAX - b_len) {
        _rt_panic("rt_string_concat: combined length too large for dea_int");
    }

    dea_int total_len = a_len + b_len;

    if (total_len == 0) {
        return DEA_STRING_EMPTY;
    }

    dea_string s = _rt_alloc_string_impl(total_len, _loc_file, _loc_line); /* result string */
    char *s_data = _rt_string_bytes(s);
    char *a_data = _rt_string_bytes(a);
    char *b_data = _rt_string_bytes(b);
    if (s_data == NULL) {
        _rt_panic("rt_string_concat: result string data is null");
    }
    if (a_data != NULL && a_len > 0) {
        memcpy(s_data, a_data, (size_t)a_len);
    }
    if (b_data != NULL && b_len > 0) {
        memcpy(s_data + a_len, b_data, (size_t)b_len);
    }
    s_data[total_len] = '\0'; /* null-terminate */
    return s;
}
#define rt_string_concat(a, b) _rt_string_concat_impl((a), (b), __FILE__, __LINE__)
#else
dea_string rt_string_concat(dea_string a, dea_string b) {
    dea_int a_len = rt_strlen(a);
    dea_int b_len = rt_strlen(b);

    /* Check for overflow in total length */
    if (a_len > INT32_MAX - b_len) {
        _rt_panic("rt_string_concat: combined length too large for dea_int");
    }

    dea_int total_len = a_len + b_len;

    if (total_len == 0) {
        return DEA_STRING_EMPTY;
    }

    dea_string s = _rt_alloc_string(total_len); /* result string */
    char *s_data = _rt_string_bytes(s);
    char *a_data = _rt_string_bytes(a);
    char *b_data = _rt_string_bytes(b);
    if (s_data == NULL) {
        _rt_panic("rt_string_concat: result string data is null");
    }
    if (a_data != NULL && a_len > 0) {
        memcpy(s_data, a_data, (size_t)a_len);
    }
    if (b_data != NULL && b_len > 0) {
        memcpy(s_data + a_len, b_data, (size_t)b_len);
    }
    s_data[total_len] = '\0'; /* null-terminate */
    return s;
}
#endif

/**
 * Create a substring (allocates new memory).
 * Panics if start/end are out of bounds or start > end.
 *
 * @param s Source string.
 * @param start Start index.
 * @param end End index.
 * @return Slice string.
 *
 * Dea signature: `extern func rt_string_slice(s: string, start: int, end: int) -> string;`
 */
dea_string rt_string_slice(dea_string s, dea_int start, dea_int end) {
    dea_int s_len = rt_strlen(s);
    if (start < 0 || start > s_len) {
        _rt_panic_fmt("rt_string_slice: start %d out of bounds for string of length %d",
                     (int)start, (int)s_len);
    }
    if (end < start || end > s_len) {
        _rt_panic_fmt("rt_string_slice: end %d invalid for start %d, string length %d",
                     (int)end, (int)start, (int)s_len);
    }

    dea_int slice_len = end - start;

    if (slice_len == 0) {
        return DEA_STRING_EMPTY;
    }

    dea_string result = _rt_alloc_string(slice_len);
    char *s_data = _rt_string_bytes(s);
    char *d_data = _rt_string_bytes(result);
    memcpy(d_data, s_data + start, (size_t)slice_len);
    d_data[slice_len] = '\0';

    return result;
}

/**
 * Create a Dea string from a single character (byte).
 * Allocates a new heap string of length 1.
 * Note: Caller must free the returned string using _rt_free_string.
 *
 * @param b Character.
 * @return Dea string.
 *
 * Dea signature: `extern func rt_string_from_byte(b: byte) -> string;`
 */
dea_string rt_string_from_byte(dea_byte b) {
    dea_string s = _rt_alloc_string(1);
    char *s_data = _rt_string_bytes(s);
    s_data[0] = (char)b;
    s_data[1] = '\0'; /* null-terminate */
    return s;
}

/**
 * Create a Dea string from a byte array and a length.
 * Allocates a new heap string of the given length and copies data.
 * The array does not need to be a null-terminated C string: all bytes are copied and a null
 * terminator is added for C interoperability.
 * Panics if len is negative.
 *
 * @param bytes Pointer to bytes.
 * @param len Length.
 * @return Dea string.
 *
 * Dea signature: `extern func rt_string_from_byte_array(bytes: byte*, len: int) -> string;`
 */
dea_string rt_string_from_byte_array(dea_byte* bytes, dea_int len) {
    if (len < 0) {
        _rt_panic("rt_string_from_byte_array: negative length");
    }
    dea_string s = _rt_alloc_string(len);
    char *s_data = _rt_string_bytes(s);
    memcpy(s_data, bytes, (size_t)len);
    return s;
}

/**
 * Increment reference count for heap strings (no-op for static).
 * Panics if the string is heap-allocated but has an invalid refcount state (e.g. double free detected).
 *
 * @param s Dea string.
 *
 * Dea signature: `extern func rt_string_retain(s: string) -> void;`
 */
#ifdef DEA_TRACE_ARC
void _rt_string_retain_impl(dea_string s, const char *_loc_file, int _loc_line) {
    if (s.kind == DEA_STRING_K_STATIC) {
        _RT_TRACE_ARC("op=retain kind=static ptr=%p rc_before=-1 rc_after=-1 action=noop loc=\"%s\":%d", (void*)s.data.s_str.bytes, _loc_file, _loc_line);
        return; /* Static strings are not reference counted */
    }
    _dea_h_string *hs = s.data.h_str;
    if (hs == NULL) {
        _RT_TRACE_ARC("op=retain kind=heap ptr=%p rc_before=-1 rc_after=-1 action=panic-null-ptr loc=\"%s\":%d", (void*)hs, _loc_file, _loc_line);
        _rt_panic("rt_string_retain: null heap string pointer");
    }
    dea_int rc_before = hs->refcount;
    if (rc_before == _RT_MEM_SENTINEL) {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-use-after-free loc=\"%s\":%d",
            (void*)hs, (int)rc_before, (int)rc_before, _loc_file, _loc_line
        );
        _rt_panic("rt_string_retain: use after free");
    }
    if (rc_before > 0 && rc_before < INT32_MAX - 1) {
        hs->refcount++;
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=retain loc=\"%s\":%d",
            (void*)hs, (int)rc_before, (int)hs->refcount, _loc_file, _loc_line
        );
    } else if (rc_before == INT32_MAX - 1) {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-overflow loc=\"%s\":%d",
            (void*)hs, (int)rc_before, (int)rc_before, _loc_file, _loc_line
        );
        _rt_panic_fmt("rt_string_retain: invalid refcount state: %d", (int)hs->refcount);
    } else if (hs->refcount == INT32_MAX) {
        /* Non-refcounted heap string: no-op */
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=noop-nonref loc=\"%s\":%d",
            (void*)hs, (int)rc_before, (int)rc_before, _loc_file, _loc_line
        );
    } else {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-invalid-state loc=\"%s\":%d",
            (void*)hs, (int)rc_before, (int)rc_before, _loc_file, _loc_line
        );
        _rt_panic_fmt("rt_string_retain: invalid refcount state: %d", (int)hs->refcount);
    }
}
#define rt_string_retain(s) _rt_string_retain_impl((s), __FILE__, __LINE__)
#else
void rt_string_retain(dea_string s) {
    if (s.kind == DEA_STRING_K_STATIC) {
        _RT_TRACE_ARC("op=retain kind=static ptr=%p rc_before=-1 rc_after=-1 action=noop", (void*)s.data.s_str.bytes);
        return; /* Static strings are not reference counted */
    }
    _dea_h_string *hs = s.data.h_str;
    if (hs == NULL) {
        _RT_TRACE_ARC("op=retain kind=heap ptr=%p rc_before=-1 rc_after=-1 action=panic-null-ptr", (void*)hs);
        _rt_panic("rt_string_retain: null heap string pointer");
    }
    dea_int rc_before = hs->refcount;
    if (rc_before == _RT_MEM_SENTINEL) {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-use-after-free",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _rt_panic("rt_string_retain: use after free");
    }
    if (rc_before > 0 && rc_before < INT32_MAX - 1) {
        hs->refcount++;
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=retain",
            (void*)hs, (int)rc_before, (int)hs->refcount
        );
    } else if (rc_before == INT32_MAX - 1) {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-overflow",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _rt_panic_fmt("rt_string_retain: invalid refcount state: %d", (int)hs->refcount);
    } else if (hs->refcount == INT32_MAX) {
        /* Non-refcounted heap string: no-op */
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=noop-nonref",
            (void*)hs, (int)rc_before, (int)rc_before
        );
    } else {
        _RT_TRACE_ARC(
            "op=retain kind=heap ptr=%p rc_before=%d rc_after=%d action=panic-invalid-state",
            (void*)hs, (int)rc_before, (int)rc_before
        );
        _rt_panic_fmt("rt_string_retain: invalid refcount state: %d", (int)hs->refcount);
    }
}
#endif

/**
 * Decrement reference count, freeing if zero.
 *
 * @param s Dea string.
 *
 * Dea signature: `extern func rt_string_release(s: string) -> void;`
 */
#ifdef DEA_TRACE_ARC
void _rt_string_release_impl(dea_string s, const char *_loc_file, int _loc_line) {
    _rt_free_string_impl(s, _loc_file, _loc_line);
}
#define rt_string_release(s) _rt_string_release_impl((s), __FILE__, __LINE__)
#else
void rt_string_release(dea_string s) {
    _rt_free_string(s);
}
#endif

#if defined(DEA_TRACE_MEMORY)
#undef _rt_alloc_string
dea_string _rt_alloc_string(dea_int len) {
    return _rt_alloc_string_impl(len, "<runtime>", 0);
}

#undef rt_string_concat
dea_string rt_string_concat(dea_string a, dea_string b) {
    return _rt_string_concat_impl(a, b, "<runtime>", 0);
}
#endif

#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)
#undef _rt_free_string
void _rt_free_string(dea_string str) {
    _rt_free_string_impl(str, "<runtime>", 0);
}
#endif

#if defined(DEA_TRACE_ARC)
#undef rt_string_retain
void rt_string_retain(dea_string s) {
    _rt_string_retain_impl(s, "<runtime>", 0);
}

#undef rt_string_release
void rt_string_release(dea_string s) {
    _rt_string_release_impl(s, "<runtime>", 0);
}
#endif
