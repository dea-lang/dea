/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* Keep retained quarantine payloads visible to AddressSanitizer as released
 * storage. The tracker metadata remains accessible; only the user payload is
 * poisoned until eviction hands it back to the C allocator. */
#if defined(__has_feature)
#if __has_feature(address_sanitizer)
#define _RT_HAS_ADDRESS_SANITIZER 1
#endif
#endif
#if defined(__SANITIZE_ADDRESS__)
#define _RT_HAS_ADDRESS_SANITIZER 1
#endif

#if defined(_RT_HAS_ADDRESS_SANITIZER)

/* Mark a byte span inaccessible to AddressSanitizer. */
void __asan_poison_memory_region(void const volatile *addr, size_t size);

/* Mark a byte span accessible to AddressSanitizer. */
void __asan_unpoison_memory_region(void const volatile *addr, size_t size);
#define _RT_ASAN_POISON(addr, size) __asan_poison_memory_region((addr), (size))
#define _RT_ASAN_UNPOISON(addr, size) __asan_unpoison_memory_region((addr), (size))
#else
#define _RT_ASAN_POISON(addr, size) ((void)0)
#define _RT_ASAN_UNPOISON(addr, size) ((void)0)
#endif

/* Register a raw allocation when runtime pointer tracking is enabled. */
static void _rt_track_alloc_record(
    void *ptr,
    size_t size,
    size_t align,
    uint32_t type_id,
    const char *loc_file,
    int loc_line
);

/* Mark a fresh raw allocation as object storage when runtime tracking is enabled. */
static void _rt_promote_new_alloc(void *ptr);

/* Release raw-owned storage, validating its ownership in checked builds. */
static void _rt_release_tracked_alloc(void *ptr, const char *loc_file, int loc_line, const char *op_name);

/* Resize raw-owned storage, preserving the original allocation on failure. */
static void *_rt_realloc_tracked_alloc(void *ptr, dea_int new_bytes, const char *loc_file, int loc_line);

/* =========================================================================
 * Runtime support for memory allocation (alloc, realloc, free, calloc), raw
 * memory operations (memset, memcpy, memcmp, array element addressing),
 * managed object lifecycle (alloc_obj, drop), and the internal allocation
 * tracking table.
 * ========================================================================= */

#ifdef DEA_TRACE_MEMORY

/**
 * Allocate a positive number of raw runtime-owned bytes.
 *
 * The caller owns a successful allocation and releases it exactly once with rt_free, or passes it to
 * rt_realloc. The contents are uninitialized.
 *
 * Nonpositive byte counts and sizes not representable as size_t terminate execution. A native allocation
 * failure returns NULL. Checked builds register successful storage for pointer validation; unchecked
 * builds omit tracking.
 *
 * This source-located entry records the supplied location when tracing is enabled.
 *
 * Dea signature: `extern func rt_alloc(bytes: int) -> void*?;`
 *
 * @param bytes Positive requested storage size in bytes.
 * @param _loc_file Borrowed source filename for trace events and diagnostics.
 * @param _loc_line Source line for trace events and diagnostics.
 * @return Owned raw allocation, or NULL on native allocation failure.
 */
void *_rt_alloc_impl(dea_int bytes, const char *_loc_file, int _loc_line) {

    /* zero-size allocations are not allowed */
    if (bytes <= 0) {
        _rt_panic("rt_alloc: invalid allocation size");
    }

    /* Check for overflow when converting to size_t */
    if ((uint64_t)bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_alloc: allocation size overflow (%d bytes requested)", (int)bytes);
    }

    size_t size = (size_t)bytes;
    void *ptr = malloc(size);

    if (ptr == NULL) {

        /* Allocation failed - return NULL and let caller handle it */
        _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=fail loc=\"%s\":%d", (int)bytes, (void*)ptr, _loc_file, _loc_line);
        return NULL;
    }

    _rt_track_alloc_record(ptr, size, 0, 0, _loc_file, _loc_line);
    _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=ok loc=\"%s\":%d", (int)bytes, ptr, _loc_file, _loc_line);
    return ptr;
}
#define rt_alloc(bytes) _rt_alloc_impl((bytes), __FILE__, __LINE__)
#else

/**
 * Allocate a positive number of raw runtime-owned bytes.
 *
 * The caller owns a successful allocation and releases it exactly once with rt_free, or passes it to
 * rt_realloc. The contents are uninitialized.
 *
 * Nonpositive byte counts and sizes not representable as size_t terminate execution. A native allocation
 * failure returns NULL. Checked builds register successful storage for pointer validation; unchecked
 * builds omit tracking.
 *
 * Dea signature: `extern func rt_alloc(bytes: int) -> void*?;`
 *
 * @param bytes Positive requested storage size in bytes.
 * @return Owned raw allocation, or NULL on native allocation failure.
 */
void *rt_alloc(dea_int bytes) {

    /* zero-size allocations are not allowed */
    if (bytes <= 0) {
        _rt_panic("rt_alloc: invalid allocation size");
    }

    /* Check for overflow when converting to size_t */
    if ((uint64_t)bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_alloc: allocation size overflow (%d bytes requested)", (int)bytes);
    }

    size_t size = (size_t)bytes;
    void *ptr = malloc(size);

    if (ptr == NULL) {

        /* Allocation failed - return NULL and let caller handle it */
        _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=fail", (int)bytes, (void*)ptr);
        return NULL;
    }

    _rt_track_alloc_record(ptr, size, 0, 0, "<runtime>", 0);
    _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=ok", (int)bytes, ptr);
    return ptr;
}
#endif

#ifdef DEA_TRACE_MEMORY

/**
 * Resize raw runtime-owned storage while preserving it on allocation failure.
 *
 * A NULL input requests a fresh allocation. Otherwise ptr must be a live raw allocation base from
 * rt_alloc, rt_calloc, or an earlier successful rt_realloc. Object, ARC, static, and foreign storage
 * cannot be reallocated through this API.
 *
 * Nonpositive or unrepresentable sizes terminate execution. Checked builds also reject unregistered,
 * interior, released, or non-raw pointers. Unchecked builds require a valid C realloc operand and omit
 * tracker validation.
 *
 * On success the result owns the resized storage, preserving the first minimum of the old and new byte
 * extents. Every pointer into the previous allocation expires, even if the native allocator reuses its
 * address. Release the result exactly once with rt_free or resize it again.
 *
 * On native allocation failure NULL is returned and the original allocation and its aliases remain valid.
 * Checked builds quarantine replaced storage to diagnose stale accesses.
 *
 * This source-located entry records the supplied location when tracing is enabled.
 *
 * Dea signature: `unsafe extern func rt_realloc(ptr: void*?, new_bytes: int) -> void*?;`
 *
 * @param ptr Live raw allocation base to resize, or NULL to allocate fresh.
 * @param new_bytes Positive requested new storage size in bytes.
 * @param _loc_file Borrowed source filename for trace events and diagnostics.
 * @param _loc_line Source line for trace events and diagnostics.
 * @return Owned resized allocation, or NULL while preserving the original allocation on failure.
 */
void *_rt_realloc_impl(void *ptr, dea_int new_bytes, const char *_loc_file, int _loc_line) {

    /* zero-size allocations are not allowed */
    if (new_bytes <= 0) {
        _rt_panic("rt_realloc: invalid allocation size");
    }

    if ((uint64_t)new_bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_realloc: allocation size overflow (%d bytes requested)", (int)new_bytes);
    }

    volatile uintptr_t old_ptr_addr = (uintptr_t)ptr;
    void *new_ptr = _rt_realloc_tracked_alloc(ptr, new_bytes, _loc_file, _loc_line);

    if (new_ptr == NULL) {

        /* Real failure! original pointer is still valid */
        _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=fail loc=\"%s\":%d", (void*)old_ptr_addr, (int)new_bytes, (void*)new_ptr, _loc_file, _loc_line);
        return NULL;
    }

    _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=ok loc=\"%s\":%d", (void*)old_ptr_addr, (int)new_bytes, new_ptr, _loc_file, _loc_line);
    return new_ptr;
}
#define rt_realloc(ptr, new_bytes) _rt_realloc_impl((ptr), (new_bytes), __FILE__, __LINE__)
#else

/**
 * Resize raw runtime-owned storage while preserving it on allocation failure.
 *
 * A NULL input requests a fresh allocation. Otherwise ptr must be a live raw allocation base from
 * rt_alloc, rt_calloc, or an earlier successful rt_realloc. Object, ARC, static, and foreign storage
 * cannot be reallocated through this API.
 *
 * Nonpositive or unrepresentable sizes terminate execution. Checked builds also reject unregistered,
 * interior, released, or non-raw pointers. Unchecked builds require a valid C realloc operand and omit
 * tracker validation.
 *
 * On success the result owns the resized storage, preserving the first minimum of the old and new byte
 * extents. Every pointer into the previous allocation expires, even if the native allocator reuses its
 * address. Release the result exactly once with rt_free or resize it again.
 *
 * On native allocation failure NULL is returned and the original allocation and its aliases remain valid.
 * Checked builds quarantine replaced storage to diagnose stale accesses.
 *
 * Dea signature: `unsafe extern func rt_realloc(ptr: void*?, new_bytes: int) -> void*?;`
 *
 * @param ptr Live raw allocation base to resize, or NULL to allocate fresh.
 * @param new_bytes Positive requested new storage size in bytes.
 * @return Owned resized allocation, or NULL while preserving the original allocation on failure.
 */
void *rt_realloc(void *ptr, dea_int new_bytes) {

    /* zero-size allocations are not allowed */
    if (new_bytes <= 0) {
        _rt_panic("rt_realloc: invalid allocation size");
    }

    if ((uint64_t)new_bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_realloc: allocation size overflow (%d bytes requested)", (int)new_bytes);
    }

    void *new_ptr = _rt_realloc_tracked_alloc(ptr, new_bytes, "<runtime>", 0);

    if (new_ptr == NULL) {

        /* Real failure! original pointer is still valid */
        _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=fail", ptr, (int)new_bytes, (void*)new_ptr);
        return NULL;
    }

    _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=ok", ptr, (int)new_bytes, new_ptr);
    return new_ptr;
}
#endif

#ifdef DEA_TRACE_MEMORY

/**
 * Release a raw runtime allocation, accepting NULL as a no-op.
 *
 * A non-NULL ptr must be a live raw allocation base from rt_alloc, rt_calloc, or successful rt_realloc. It
 * must be released exactly once. All pointers into its storage expire after this call.
 *
 * Checked builds reject interior, unregistered, already released, object, ARC, static, and foreign
 * pointers. Released storage enters the bounded quarantine before eventual native deallocation. Unchecked
 * builds call native free and require its normal valid-pointer preconditions.
 *
 * This source-located entry records the supplied location when tracing is enabled.
 *
 * Dea signature: `unsafe extern func rt_free(ptr: void*?) -> void;`
 *
 * @param ptr Live raw allocation base to consume exactly once, or NULL.
 * @param _loc_file Borrowed source filename for trace events and diagnostics.
 * @param _loc_line Source line for trace events and diagnostics.
 */
void _rt_free_impl(void *ptr, const char *_loc_file, int _loc_line) {

    /* free(NULL) is a no-op in C */
    _RT_TRACE_MEM("op=free ptr=%p action=call loc=\"%s\":%d", ptr, _loc_file, _loc_line);
    _rt_release_tracked_alloc(ptr, _loc_file, _loc_line, "rt_free");
}
#define rt_free(ptr) _rt_free_impl((ptr), __FILE__, __LINE__)
#else

/**
 * Release a raw runtime allocation, accepting NULL as a no-op.
 *
 * A non-NULL ptr must be a live raw allocation base from rt_alloc, rt_calloc, or successful rt_realloc. It
 * must be released exactly once. All pointers into its storage expire after this call.
 *
 * Checked builds reject interior, unregistered, already released, object, ARC, static, and foreign
 * pointers. Released storage enters the bounded quarantine before eventual native deallocation. Unchecked
 * builds call native free and require its normal valid-pointer preconditions.
 *
 * Dea signature: `unsafe extern func rt_free(ptr: void*?) -> void;`
 *
 * @param ptr Live raw allocation base to consume exactly once, or NULL.
 */
void rt_free(void *ptr) {

    /* free(NULL) is a no-op in C */
    _RT_TRACE_MEM("op=free ptr=%p action=call", ptr);
    _rt_release_tracked_alloc(ptr, "<runtime>", 0, "rt_free");
}
#endif

#ifdef DEA_TRACE_MEMORY

/**
 * Allocate a positive count of zero-filled raw runtime-owned elements.
 *
 * The caller owns successful storage and releases it exactly once with rt_free, or passes it to
 * rt_realloc.
 *
 * Nonpositive counts or element sizes and products not representable as size_t terminate execution. A
 * native allocation failure returns NULL. Checked builds register the allocation; unchecked builds omit
 * tracking.
 *
 * This source-located entry records the supplied location when tracing is enabled.
 *
 * Dea signature: `extern func rt_calloc(count: int, elem_size: int) -> void*?;`
 *
 * @param count Positive number of elements to allocate.
 * @param elem_size Positive size of one element in bytes.
 * @param _loc_file Borrowed source filename for trace events and diagnostics.
 * @param _loc_line Source line for trace events and diagnostics.
 * @return Owned zero-filled raw allocation, or NULL on native allocation failure.
 */
void *_rt_calloc_impl(dea_int count, dea_int elem_size, const char *_loc_file, int _loc_line) {
    if (count <= 0 || elem_size <= 0) {
        _rt_panic("rt_calloc: invalid count or element size");
    }

    /* Check for overflow in multiplication*/
    if ((uint64_t)count * (uint64_t)elem_size > SIZE_MAX) {
        _rt_panic_fmt("rt_calloc: allocation size overflow (%d elements of size %d requested)",
                     (int)count, (int)elem_size);
    }

    size_t n = (size_t)count;
    size_t size = (size_t)elem_size;

    void *ptr = calloc(n, size);
    _RT_TRACE_MEM(
        "op=calloc count=%d elem_size=%d ptr=%p action=%s loc=\"%s\":%d",
        (int)count, (int)elem_size, ptr, ptr == NULL ? "fail" : "ok", _loc_file, _loc_line
    );
    if (ptr != NULL) {
        _rt_track_alloc_record(ptr, n * size, 0, 0, _loc_file, _loc_line);
    }
    return ptr;
}
#define rt_calloc(count, elem_size) _rt_calloc_impl((count), (elem_size), __FILE__, __LINE__)
#else

/**
 * Allocate a positive count of zero-filled raw runtime-owned elements.
 *
 * The caller owns successful storage and releases it exactly once with rt_free, or passes it to
 * rt_realloc.
 *
 * Nonpositive counts or element sizes and products not representable as size_t terminate execution. A
 * native allocation failure returns NULL. Checked builds register the allocation; unchecked builds omit
 * tracking.
 *
 * Dea signature: `extern func rt_calloc(count: int, elem_size: int) -> void*?;`
 *
 * @param count Positive number of elements to allocate.
 * @param elem_size Positive size of one element in bytes.
 * @return Owned zero-filled raw allocation, or NULL on native allocation failure.
 */
void *rt_calloc(dea_int count, dea_int elem_size) {
    if (count <= 0 || elem_size <= 0) {
        _rt_panic("rt_calloc: invalid count or element size");
    }

    /* Check for overflow in multiplication*/
    if ((uint64_t)count * (uint64_t)elem_size > SIZE_MAX) {
        _rt_panic_fmt("rt_calloc: allocation size overflow (%d elements of size %d requested)",
                     (int)count, (int)elem_size);
    }

    size_t n = (size_t)count;
    size_t size = (size_t)elem_size;

    void *ptr = calloc(n, size);
    _RT_TRACE_MEM(
        "op=calloc count=%d elem_size=%d ptr=%p action=%s",
        (int)count, (int)elem_size, ptr, ptr == NULL ? "fail" : "ok"
    );
    if (ptr != NULL) {
        _rt_track_alloc_record(ptr, n * size, 0, 0, "<runtime>", 0);
    }
    return ptr;
}
#endif

/**
 * Set memory to a specific byte value.
 * Returns destination pointer.
 *
 * Dea signature: `unsafe extern func rt_memset(dest: void*, value: int, bytes: int) -> void*;`
 *
 * @param dest Destination pointer.
 * @param value Byte value.
 * @param bytes Number of bytes.
 * @return dest.
 */
void *rt_memset(void *dest, dea_int value, dea_int bytes) {
    if (bytes < 0) {
        _rt_panic("rt_memset: negative byte count");
    }

    if (bytes == 0 || dest == NULL) {
        return dest;
    }

    size_t n = (size_t)bytes;
    int c = (int)value;
    return memset(dest, c, n);
}

/**
 * Copy memory from source to destination.
 * Returns destination pointer.
 *
 * Dea signature: `unsafe extern func rt_memcpy(dest: void*, src: void*, bytes: int) -> void*;`
 *
 * @param dest Destination.
 * @param src Source.
 * @param bytes Number of bytes.
 * @return dest.
 */
void *rt_memcpy(void *dest, void *src, dea_int bytes) {
    if (bytes < 0) {
        _rt_panic("rt_memcpy: negative byte count");
    }

    if (bytes == 0 || dest == NULL || src == NULL) {
        return dest;
    }

    size_t n = (size_t)bytes;
    return memcpy(dest, src, n);
}

/**
 * Return a candidate address's byte offset within a half-open byte span.
 *
 * NULL pointers, nonpositive extents, exact-end addresses, and disjoint addresses return -1. The helper
 * uses checked integer-address arithmetic and never dereferences either pointer.
 *
 * This implementation-private helper is used by the bundled standard library and is not part of the stable
 * public runtime API.
 *
 * Dea signature: `unsafe extern func _rt_byte_span_offset(base: void*?, span_bytes: int, candidate:
 * void*?) -> int;`
 *
 * @param base Base address of the byte span.
 * @param span_bytes Positive byte extent of the span.
 * @param candidate Address to classify.
 * @return Byte offset within the span, or -1 when not contained.
 */
dea_int _rt_byte_span_offset(void *base, dea_int span_bytes, void *candidate) {
    if (base == NULL || candidate == NULL || span_bytes <= 0) {
        return -1;
    }

    uintptr_t base_addr = (uintptr_t)base;
    uintptr_t candidate_addr = (uintptr_t)candidate;
    if (candidate_addr < base_addr) {
        return -1;
    }

    uintptr_t offset = candidate_addr - base_addr;
    if (offset >= (uintptr_t)span_bytes) {
        return -1;
    }
    return (dea_int)offset;
}

/**
 * Return whether two positive half-open byte spans overlap.
 *
 * Address differences are compared against extents without computing either end address, so classification
 * cannot wrap around UINTPTR_MAX. NULL pointers and nonpositive extents do not overlap. Neither span is
 * dereferenced.
 *
 * This implementation-private helper is used by the bundled standard library and is not part of the stable
 * public runtime API.
 *
 * Dea signature: `unsafe extern func _rt_byte_spans_overlap(first: void*?, first_bytes: int, second:
 * void*?, second_bytes: int) -> bool;`
 *
 * @param first Base address of the first byte span.
 * @param first_bytes Positive byte extent of the first span.
 * @param second Base address of the second byte span.
 * @param second_bytes Positive byte extent of the second span.
 * @return Nonzero when the positive half-open spans overlap; zero otherwise.
 */
dea_bool _rt_byte_spans_overlap(void *first, dea_int first_bytes, void *second, dea_int second_bytes) {
    if (first == NULL || second == NULL || first_bytes <= 0 || second_bytes <= 0) {
        return 0;
    }

    uintptr_t first_addr = (uintptr_t)first;
    uintptr_t second_addr = (uintptr_t)second;
    if (first_addr <= second_addr) {
        return (dea_bool)((second_addr - first_addr) < (uintptr_t)first_bytes);
    }
    return (dea_bool)((first_addr - second_addr) < (uintptr_t)second_bytes);
}

/**
 * Compare two memory regions.
 * Returns 0 if equal, <0 if a < b, >0 if a > b.
 *
 * Dea signature: `unsafe extern func rt_memcmp(a: void*, b: void*, bytes: int) -> int;`
 *
 * @param a First region.
 * @param b Second region.
 * @param bytes Number of bytes.
 * @return Comparison result.
 */
dea_int rt_memcmp(void *a, void *b, dea_int bytes) {
    if (bytes < 0) {
        _rt_panic("rt_memcmp: negative byte count");
    }

    if (bytes == 0 || a == NULL || b == NULL) {
        return 0;
    }

    size_t n = (size_t)bytes;
    int result = memcmp(a, b, n);
    if (result < 0) {
        return -1;
    } else if (result > 0) {
        return 1;
    } else {
        return 0;
    }
}

/**
 * Get a pointer to an element in an array.
 * Panics if array_data is NULL, element_size is non-positive, or index is negative.
 *
 * Dea signature: `unsafe extern func rt_array_element(array_data: void*, element_size: int, index: int) ->
 * void*;`
 *
 * @param array_data Pointer to array data.
 * @param element_size Size of one element.
 * @param index Element index.
 * @return Pointer to the element.
 */
void *rt_array_element(void *array_data, dea_int element_size, dea_int index) {
    if (array_data == NULL) {
        _rt_panic("rt_array_element: null array data pointer");
    }
    if (element_size <= 0) {
        _rt_panic("rt_array_element: invalid element size");
    }
    if (index < 0) {
        _rt_panic("rt_array_element: negative index");
    }

    /* Check for overflow in multiplication */
    if ((uint64_t)index * (uint64_t)element_size > SIZE_MAX) {
        _rt_panic_fmt("rt_array_element: index * element_size overflow (%d * %d)",
                     (int)index, (int)element_size);
    }

    /* One shared entry point serving every container call site: a single
     * static site slot would thrash across unrelated allocations, so skip
     * the per-call-site cache and always take the full lookup. Read mode is
     * used even for element stores: callers only pass container storage,
     * which is runtime-owned writable raw memory, so read-only enforcement
     * never applies here. */
    return _rt_check_index_ptr_site(
        NULL,
        array_data,
        index,
        element_size,
        0,
        _RT_ACCESS_READ,
        __FILE__,
        __LINE__
    );
}

/* =========================================================================
 * Runtime support for `new` & `drop`: allocation tracker implementation
 * -------------------------------------------------------------------------
 * Base-pointer lookup uses an open-addressing hash table (O(1) amortized).
 * Interior pointers resolve through an address-ordered treap keyed by
 * allocation base (O(log n) insert/remove/lookup, no bulk moves). Records
 * come from a never-freed pool so call-site caches may keep record pointers
 * across frees; the generation counter invalidates recycled records.
 * ========================================================================= */

#ifndef DEA_RT_UNCHECKED

#define _RT_ALLOC_TOMBSTONE ((_rt_alloc_record*)(uintptr_t)1)
#ifndef _RT_ALLOC_INIT_CAP
#define _RT_ALLOC_INIT_CAP 256
#endif
#ifndef _RT_QUARANTINE_MAX_BYTES
#define _RT_QUARANTINE_MAX_BYTES ((size_t)16 * 1024 * 1024)
#endif
#ifndef _RT_QUARANTINE_MAX_COUNT
#define _RT_QUARANTINE_MAX_COUNT ((size_t)4096)
#endif
#ifndef _RT_REC_POOL_CHUNK
#define _RT_REC_POOL_CHUNK 256
#endif

static _rt_alloc_record **_rt_alloc_table = NULL;
static size_t _rt_alloc_table_cap = 0;
static size_t _rt_alloc_table_cnt = 0;
static size_t _rt_alloc_table_tombstones = 0;
static uint64_t _rt_alloc_next_generation = 1;

#ifndef DEA_RT_CHECK_BASIC
static _rt_alloc_record *_rt_alloc_tree_root = NULL;
#endif
static _rt_alloc_record *_rt_rec_free_list = NULL;
static _rt_alloc_record_cold **_rt_cold_chunks = NULL;
static size_t _rt_rec_pool_chunks = 0;

static _rt_alloc_record *_rt_quarantine_head = NULL;
static _rt_alloc_record *_rt_quarantine_tail = NULL;
static size_t _rt_quarantine_bytes = 0;
static size_t _rt_quarantine_count = 0;

static size_t _rt_quarantine_max_bytes = _RT_QUARANTINE_MAX_BYTES;
static size_t _rt_quarantine_max_count = _RT_QUARANTINE_MAX_COUNT;
static int _rt_tracker_config_ready = 0;

#if _RT_REC_POOL_CHUNK == 256
#define _rt_rec_cold(rec) (&_rt_cold_chunks[(rec)->cold_index >> 8][(rec)->cold_index & 255u])
#else
#define _rt_rec_cold(rec) (&_rt_cold_chunks[(size_t)(rec)->cold_index / (size_t)_RT_REC_POOL_CHUNK][(size_t)(rec)->cold_index % (size_t)_RT_REC_POOL_CHUNK])
#endif

/**
 * Read a bounded unsigned decimal tracker setting from the environment.
 *
 * @param name Borrowed NUL-terminated name.
 * @param fallback Value used when the environment setting is absent or invalid.
 * @return Parsed size, or fallback for absent, negative, malformed, or overflowing values.
 */
static size_t _rt_env_size(const char *name, size_t fallback) {
    const char *text = getenv(name);
    const char *cursor;
    char *end = NULL;
    unsigned long long value;
    if (text == NULL || *text == '\0') return fallback;

    /* strtoull accepts a leading minus and wraps the value to a huge
     * unsigned limit; reject negatives up front while keeping strtoull's
     * leading-whitespace and '+' tolerance. */
    cursor = text;
    while (*cursor == ' ' || (*cursor >= '\t' && *cursor <= '\r')) cursor++;
    if (*cursor == '-') return fallback;
    errno = 0;
    value = strtoull(text, &end, 10);
    if (errno != 0 || end == NULL || end == text || *end != '\0' || value > SIZE_MAX) {
        return fallback;
    }
    return (size_t)value;
}

/**
 * Read quarantine limits once from the environment. The archive runtime is
 * prebuilt, so `DEA_RT_QUARANTINE_MAX_BYTES` and `DEA_RT_QUARANTINE_MAX_COUNT`
 * let a deployment retune retention without recompiling; zero disables
 * retention entirely.
 */
static void _rt_tracker_config_init(void) {
    if (_rt_tracker_config_ready) return;
    _rt_tracker_config_ready = 1;
    _rt_quarantine_max_bytes = _rt_env_size("DEA_RT_QUARANTINE_MAX_BYTES", _RT_QUARANTINE_MAX_BYTES);
    _rt_quarantine_max_count = _rt_env_size("DEA_RT_QUARANTINE_MAX_COUNT", _RT_QUARANTINE_MAX_COUNT);
}

/**
 * Take one record from the pool, refilling it chunk-wise. Pool memory is
 * never returned to the C allocator, so stale record pointers held by
 * call-site caches remain safe to dereference.
 *
 * @param cold_out Optional output receiving the corresponding cold record.
 * @return Pool record reserved for the caller; allocation failure panics.
 */
static _rt_alloc_record *_rt_rec_new(_rt_alloc_record_cold **cold_out) {
    if (_rt_rec_free_list == NULL) {
        size_t chunk_count = (size_t)_RT_REC_POOL_CHUNK;
        size_t chunk_no = _rt_rec_pool_chunks;
        if (chunk_count == 0) {
            _rt_panic("runtime allocation tracker: invalid record pool chunk size");
        }
        if (chunk_count > (SIZE_MAX - 63u) / sizeof(_rt_alloc_record)) {
            _rt_panic("runtime allocation tracker: record pool size overflow");
        }
        if (chunk_count > SIZE_MAX / sizeof(_rt_alloc_record_cold)) {
            _rt_panic("runtime allocation tracker: cold record pool size overflow");
        }
        if (chunk_no > ((size_t)UINT32_MAX - (chunk_count - 1u)) / chunk_count) {
            _rt_panic("runtime allocation tracker: record pool index overflow");
        }
        if (chunk_no > (SIZE_MAX / sizeof(_rt_alloc_record_cold*)) - 1u) {
            _rt_panic("runtime allocation tracker: cold chunk directory overflow");
        }

        size_t hot_bytes = chunk_count * sizeof(_rt_alloc_record);
        unsigned char *raw = (unsigned char*)malloc(hot_bytes + 63u);
        if (raw == NULL) {
            _rt_panic("runtime allocation tracker: out of memory (hot record pool)");
        }
        size_t off = (size_t)(-(uintptr_t)raw & 63u);
        _rt_alloc_record *chunk = (_rt_alloc_record*)(void*)(raw + off);

        _rt_alloc_record_cold **new_cold_chunks = (_rt_alloc_record_cold**)realloc(
            _rt_cold_chunks,
            (chunk_no + 1u) * sizeof(_rt_alloc_record_cold*)
        );
        if (new_cold_chunks == NULL) {
            _rt_panic("runtime allocation tracker: out of memory (cold chunk directory)");
        }
        _rt_cold_chunks = new_cold_chunks;

        _rt_alloc_record_cold *cold_chunk = (_rt_alloc_record_cold*)malloc(chunk_count * sizeof(_rt_alloc_record_cold));
        if (cold_chunk == NULL) {
            _rt_panic("runtime allocation tracker: out of memory (cold record pool)");
        }
        _rt_cold_chunks[chunk_no] = cold_chunk;
        _rt_rec_pool_chunks++;

        size_t base_index = chunk_no * chunk_count;
        for (size_t i = 0; i < chunk_count; i++) {
            chunk[i].base = NULL;
            chunk[i].size = 0;
            chunk[i].state = _RT_ALLOC_POOLED;
            chunk[i].read_only = 0;
            chunk[i].mem_kind = 0;
            chunk[i].generation = 0;
            chunk[i].cold_index = (uint32_t)(base_index + i);
            chunk[i].q_next = _rt_rec_free_list;
            _rt_rec_free_list = &chunk[i];
        }
    }
    _rt_alloc_record *rec = _rt_rec_free_list;
    _rt_alloc_record_cold *cold = _rt_rec_cold(rec);
    _rt_rec_free_list = rec->q_next;
    if (cold_out != NULL) {
        *cold_out = cold;
    }
    return rec;
}

/**
 * Return an unlinked allocation record to the reusable record pool.
 *
 * @param rec Live tracker record updated by this operation.
 */
static void _rt_rec_recycle(_rt_alloc_record *rec) {
    rec->state = _RT_ALLOC_POOLED;
    rec->generation = 0;
    rec->q_next = _rt_rec_free_list;
    _rt_rec_free_list = rec;
}

/**
 * Map an allocation base address into a power-of-two tracker table.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param cap Power-of-two allocation hash table capacity.
 * @return Bucket index smaller than cap.
 */
static size_t _rt_alloc_hash(void *ptr, size_t cap) {
    uint64_t v = (uint64_t)(uintptr_t)ptr;
    uint32_t x = (uint32_t)(v ^ (v >> 32));
    x ^= x >> 16; x *= 0x85ebca6bu;
    x ^= x >> 13; x *= 0xc2b2ae35u;
    x ^= x >> 16;
    return (size_t)(x & (uint32_t)(cap - 1));
}

/**
 * Rebuild the hash table sized from the live record count. Sizing from the
 * live count (not the old capacity) keeps sustained alloc/free churn from
 * ratcheting the table up: a tombstone-triggered rebuild purges tombstones
 * at a stable or smaller capacity instead of doubling it, and a shrunken
 * live set lets the table contract.
 */
static void _rt_alloc_table_rehash(void) {
    size_t old_cap = _rt_alloc_table_cap;
    _rt_alloc_record **old_tbl = _rt_alloc_table;
    size_t new_cap = _RT_ALLOC_INIT_CAP;
    while (new_cap < _rt_alloc_table_cnt * 2) {
        new_cap *= 2;
    }

    _rt_alloc_record **new_tbl = (_rt_alloc_record**)calloc(new_cap, sizeof(_rt_alloc_record*));
    if (new_tbl == NULL) {
        _rt_panic("runtime allocation tracker: out of memory");
    }

    for (size_t i = 0; i < old_cap; i++) {
        _rt_alloc_record *rec = old_tbl[i];
        if (rec != NULL && rec != _RT_ALLOC_TOMBSTONE) {
            size_t idx = _rt_alloc_hash(rec->base, new_cap);
            while (new_tbl[idx] != NULL) {
                idx = (idx + 1) & (new_cap - 1);
            }
            new_tbl[idx] = rec;
        }
    }

    free(old_tbl);
    _rt_alloc_table = new_tbl;
    _rt_alloc_table_cap = new_cap;
    _rt_alloc_table_tombstones = 0;
}

/**
 * Find the tracker record for an exact allocation base address.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @return Borrowed tracker record, or NULL when no record exists.
 */
static _rt_alloc_record *_rt_alloc_table_lookup(void *ptr) {
    if (_rt_alloc_table_cap == 0 || ptr == NULL) return NULL;

    size_t idx = _rt_alloc_hash(ptr, _rt_alloc_table_cap);
    for (size_t probed = 0; probed < _rt_alloc_table_cap && _rt_alloc_table[idx] != NULL; probed++) {
        _rt_alloc_record *rec = _rt_alloc_table[idx];
        if (rec != _RT_ALLOC_TOMBSTONE && rec->base == ptr) {
            return rec;
        }
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
    return NULL;
}

/**
 * Insert a tracker record, growing or compacting the hash table when needed.
 *
 * @param rec Live tracker record updated by this operation.
 */
static void _rt_alloc_table_insert_record(_rt_alloc_record *rec) {
    if (_rt_alloc_table_cap == 0 ||
        (_rt_alloc_table_cnt + _rt_alloc_table_tombstones + 1) * 10 > _rt_alloc_table_cap * 7) {
        _rt_alloc_table_rehash();
    }

    size_t idx = _rt_alloc_hash(rec->base, _rt_alloc_table_cap);
    while (_rt_alloc_table[idx] != NULL && _rt_alloc_table[idx] != _RT_ALLOC_TOMBSTONE) {
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
    if (_rt_alloc_table[idx] == _RT_ALLOC_TOMBSTONE) {
        _rt_alloc_table_tombstones--;
    }
    _rt_alloc_table[idx] = rec;
    _rt_alloc_table_cnt++;
}

/**
 * Remove a tracker record and reclaim excess table capacity when appropriate.
 *
 * @param target Tracker record to remove.
 */
static void _rt_alloc_table_remove_record(_rt_alloc_record *target) {
    if (_rt_alloc_table_cap == 0) return;

    size_t idx = _rt_alloc_hash(target->base, _rt_alloc_table_cap);
    for (size_t probed = 0; probed < _rt_alloc_table_cap && _rt_alloc_table[idx] != NULL; probed++) {
        if (_rt_alloc_table[idx] == target) {
            _rt_alloc_table[idx] = _RT_ALLOC_TOMBSTONE;
            _rt_alloc_table_cnt--;
            _rt_alloc_table_tombstones++;
            if (_rt_alloc_table_tombstones > _rt_alloc_table_cap / 2 ||
                (_rt_alloc_table_cap > _RT_ALLOC_INIT_CAP &&
                 _rt_alloc_table_cnt < _rt_alloc_table_cap / 4)) {
                _rt_alloc_table_rehash();
            }
            return;
        }
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
}

/**
 * Terminate with the pointer-access failure reason and source location.
 *
 * @param reason Borrowed diagnostic or observation reason.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_panic_invalid_access(const char *reason, void *ptr, const char *loc_file, int loc_line) {
    _rt_panic_fmt(
        "runtime error: %s\n  pointer: %p\n  accessed at: %s:%d",
        reason,
        ptr,
        loc_file ? loc_file : "<unknown>",
        loc_line
    );
}

/**
 * Terminate with the object-drop failure reason and source location.
 *
 * @param reason Borrowed diagnostic or observation reason.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_panic_invalid_drop(const char *reason, void *ptr, const char *loc_file, int loc_line) {
    _rt_panic_fmt(
        "runtime error: invalid drop\n  reason: %s\n  pointer: %p\n  drop at: %s:%d",
        reason,
        ptr,
        loc_file ? loc_file : "<unknown>",
        loc_line
    );
}

/**
 * Terminate with the raw-release operation, failure reason, and source location.
 *
 * @param op_name Borrowed runtime operation name for diagnostics.
 * @param reason Borrowed diagnostic or observation reason.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_panic_invalid_release(
    const char *op_name,
    const char *reason,
    void *ptr,
    const char *loc_file,
    int loc_line
) {
    _rt_panic_fmt(
        "runtime error: invalid %s\n  reason: %s\n  pointer: %p\n  released at: %s:%d",
        op_name ? op_name : "release",
        reason,
        ptr,
        loc_file ? loc_file : "<unknown>",
        loc_line
    );
}

/**
 * Emit the failed object-drop trace event when memory tracing is enabled.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_trace_invalid_drop(void *ptr, const char *loc_file, int loc_line) {
    _RT_TRACE_MEM(
        "op=drop ptr=%p action=panic-not-found loc=\"%s\":%d",
        ptr,
        loc_file ? loc_file : "<unknown>",
        loc_line
    );
}

/**
 * Test a pointer against a required byte alignment.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param align Required storage alignment in bytes.
 * @return Nonzero when aligned; alignment zero or one imposes no restriction.
 */
static int _rt_ptr_is_aligned(void *ptr, size_t align) {
    if (align <= 1) return 1;
    return ((uintptr_t)ptr % align) == 0;
}

/**
 * Check byte-span containment without overflowing pointer or size arithmetic.
 *
 * @param base Base address of the registered byte span.
 * @param total_size Total registered byte extent.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param need_size Required accessible byte extent.
 * @param offset_out Optional output receiving the validated byte offset.
 * @return Nonzero when the requested span fits; optionally writes its offset.
 */
static int _rt_range_contains(void *base, size_t total_size, void *ptr, size_t need_size, size_t *offset_out) {
    uintptr_t b = (uintptr_t)base;
    uintptr_t p = (uintptr_t)ptr;
    if (p < b) return 0;

    size_t offset = (size_t)(p - b);
    if (offset > total_size) return 0;
    if (need_size > total_size - offset) return 0;
    if (offset_out != NULL) {
        *offset_out = offset;
    }
    return 1;
}

#ifndef DEA_RT_CHECK_BASIC

/**
 * Derive a nonzero deterministic treap priority from an allocation address.
 *
 * @param base Base address of the registered byte span.
 * @return Nonzero mixed priority word.
 */
static uint32_t _rt_tree_prio_for(void *base) {
    uint64_t v = (uint64_t)(uintptr_t)base;
    uint32_t x = (uint32_t)(v ^ (v >> 32));
    x ^= x >> 16; x *= 0x85ebca6bu;
    x ^= x >> 13; x *= 0xc2b2ae35u;
    x ^= x >> 16;
    return x | 1u;
}

/**
 * Insert an allocation record into an address-ordered treap subtree.
 *
 * @param node Borrowed treap subtree root, or NULL.
 * @param rec Live tracker record updated by this operation.
 * @return Updated borrowed subtree root.
 */
static _rt_alloc_record *_rt_tree_insert_at(_rt_alloc_record *node, _rt_alloc_record *rec) {
    if (node == NULL) {
        rec->tree_left = NULL;
        rec->tree_right = NULL;
        return rec;
    }
    if ((uintptr_t)rec->base < (uintptr_t)node->base) {
        node->tree_left = _rt_tree_insert_at(node->tree_left, rec);
        if (node->tree_left->tree_prio > node->tree_prio) {
            _rt_alloc_record *pivot = node->tree_left;
            node->tree_left = pivot->tree_right;
            pivot->tree_right = node;
            node = pivot;
        }
    } else {
        node->tree_right = _rt_tree_insert_at(node->tree_right, rec);
        if (node->tree_right->tree_prio > node->tree_prio) {
            _rt_alloc_record *pivot = node->tree_right;
            node->tree_right = pivot->tree_left;
            pivot->tree_left = node;
            node = pivot;
        }
    }
    return node;
}

/**
 * Merge two treaps where every base in `a` is below every base in `b`.
 *
 * @param a Treap whose record bases precede every record base in b.
 * @param b Treap whose record bases follow every record base in a.
 * @return Root of the merged treap, or NULL when both inputs are empty.
 */
static _rt_alloc_record *_rt_tree_merge(_rt_alloc_record *a, _rt_alloc_record *b) {
    if (a == NULL) return b;
    if (b == NULL) return a;
    if (a->tree_prio > b->tree_prio) {
        a->tree_right = _rt_tree_merge(a->tree_right, b);
        return a;
    }
    b->tree_left = _rt_tree_merge(a, b->tree_left);
    return b;
}

/**
 * Remove an exact base address from an allocation treap subtree.
 *
 * @param node Borrowed treap subtree root, or NULL.
 * @param base Base address of the registered byte span.
 * @return Updated borrowed subtree root.
 */
static _rt_alloc_record *_rt_tree_remove_at(_rt_alloc_record *node, void *base) {
    if (node == NULL) return NULL;
    if ((uintptr_t)base < (uintptr_t)node->base) {
        node->tree_left = _rt_tree_remove_at(node->tree_left, base);
    } else if ((uintptr_t)base > (uintptr_t)node->base) {
        node->tree_right = _rt_tree_remove_at(node->tree_right, base);
    } else {
        node = _rt_tree_merge(node->tree_left, node->tree_right);
    }
    return node;
}

/**
 * Assign a priority and insert a tracker record into the allocation treap.
 *
 * @param rec Live tracker record updated by this operation.
 */
static void _rt_alloc_tree_insert(_rt_alloc_record *rec) {
    rec->tree_prio = _rt_tree_prio_for(rec->base);
    _rt_alloc_tree_root = _rt_tree_insert_at(_rt_alloc_tree_root, rec);
}

/**
 * Remove a tracker record from the allocation treap.
 *
 * @param rec Live tracker record updated by this operation.
 */
static void _rt_alloc_tree_remove(_rt_alloc_record *rec) {
    _rt_alloc_tree_root = _rt_tree_remove_at(_rt_alloc_tree_root, rec->base);
}

/**
 * Return the tracked record with the greatest base at or below `ptr`.
 *
 * @param ptr Address used as the inclusive upper bound.
 * @return Tracked record with the greatest eligible base, or NULL.
 */
static _rt_alloc_record *_rt_alloc_tree_glb(void *ptr) {
    _rt_alloc_record *node = _rt_alloc_tree_root;
    _rt_alloc_record *best = NULL;
    uintptr_t target = (uintptr_t)ptr;
    while (node != NULL) {
        if ((uintptr_t)node->base <= target) {
            best = node;
            node = node->tree_right;
        } else {
            node = node->tree_left;
        }
    }
    return best;
}

/**
 * Return the tracked record with the lowest base at or above `ptr`.
 *
 * @param ptr Address used as the inclusive lower bound.
 * @return Tracked record with the lowest eligible base, or NULL.
 */
static _rt_alloc_record *_rt_alloc_tree_lub(void *ptr) {
    _rt_alloc_record *node = _rt_alloc_tree_root;
    _rt_alloc_record *best = NULL;
    uintptr_t target = (uintptr_t)ptr;
    while (node != NULL) {
        if ((uintptr_t)node->base >= target) {
            best = node;
            node = node->tree_left;
        } else {
            node = node->tree_right;
        }
    }
    return best;
}

/**
 * Find a registered allocation containing the complete requested byte span.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param need_size Required accessible byte extent.
 * @return Borrowed containing record, or NULL when no registered span contains the access.
 */
static _rt_alloc_record *_rt_alloc_tree_find_containing(void *ptr, size_t need_size) {
    if (ptr == NULL) return NULL;

    _rt_alloc_record *candidate = _rt_alloc_tree_glb(ptr);
    while (candidate != NULL) {
        if (_rt_range_contains(candidate->base, candidate->size, ptr, need_size, NULL)) {
            return candidate;
        }

        /* Static spans may overlap when the C compiler shares literal
         * suffixes; heap spans never overlap, so only static candidates
         * warrant walking further down the address order. */
        if (candidate->mem_kind != _RT_MEM_STATIC || (uintptr_t)candidate->base == 0) {
            return NULL;
        }
        candidate = _rt_alloc_tree_glb((void*)((uintptr_t)candidate->base - 1));
    }
    return NULL;
}

/* DEA_RT_CHECK_BASIC */
#endif

/**
 * Validate a generated pointer-access size and give zero-size pointees one byte.
 *
 * @param required_size Generated required accessible byte extent.
 * @return Validated positive access size; negative sizes terminate execution.
 */
static size_t _rt_required_size(dea_int required_size) {
    if (required_size < 0) {
        _rt_panic("runtime pointer access: negative required size");
    }
    return required_size == 0 ? 1u : (size_t)required_size;
}

/**
 * Validate and convert a generated pointer-access alignment.
 *
 * @param required_align Generated required byte alignment.
 * @return Nonnegative alignment; negative alignments terminate execution.
 */
static size_t _rt_required_align(dea_int required_align) {
    if (required_align < 0) {
        _rt_panic("runtime pointer access: negative required alignment");
    }
    return (size_t)required_align;
}

/**
 * Require a positive pointer-index element size.
 *
 * @param element_size Positive size of one indexed element in bytes.
 * @return Validated element size; nonpositive sizes terminate execution.
 */
static size_t _rt_index_element_size(dea_int element_size) {
    if (element_size <= 0) {
        _rt_panic("runtime pointer index: invalid element size");
    }
    return (size_t)element_size;
}

/**
 * Compute a nonnegative checked pointer-index byte offset.
 *
 * @param index Requested element index.
 * @param element_size Positive size of one indexed element in bytes.
 * @return Validated offset; negative indices and overflow terminate execution.
 */
static size_t _rt_index_offset(dea_int index, size_t element_size) {
    if (index < 0) {
        _rt_panic("runtime pointer index: negative pointer index");
    }

    /* `dea_int` is 32-bit, so the 64-bit product of two non-negative
     * operands cannot wrap and the SIZE_MAX comparison is exact. */
    if ((uint64_t)index * (uint64_t)element_size > SIZE_MAX) {
        _rt_panic_fmt(
            "runtime pointer index: index * element_size overflow (%d * %d)",
            (int)index,
            (int)element_size
        );
    }
    return (size_t)index * element_size;
}

/**
 * Require a generated pointer access to be either read or write.
 *
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @return Validated access mode; invalid tags terminate execution.
 */
static int _rt_required_access_mode(int access_mode) {
    if (access_mode != _RT_ACCESS_READ && access_mode != _RT_ACCESS_WRITE) {
        _rt_panic("runtime pointer access: invalid access mode");
    }
    return access_mode;
}

/**
 * Remove foreign-index policy bits and validate the underlying access mode.
 *
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @return Validated read or write access mode.
 */
static int _rt_index_access_mode(int access_mode) {
    int mode = access_mode & _RT_ACCESS_WRITE;
    int flags = access_mode & ~_RT_ACCESS_WRITE;
    if ((flags != 0 && flags != _RT_ACCESS_UNTRACKED_OK) ||
        (mode != _RT_ACCESS_READ && mode != _RT_ACCESS_WRITE)) {
        _rt_panic("runtime pointer index: invalid access mode");
    }
    return mode;
}

/**
 * Test whether the generated indexing policy permits an unregistered base.
 *
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @return Nonzero when the foreign-index policy bit is present.
 */
static int _rt_index_allows_untracked(int access_mode) {
    return (access_mode & _RT_ACCESS_UNTRACKED_OK) != 0;
}

/**
 * Panic when a validated access target misses its required alignment.
 *
 * @param ptr Access target to check.
 * @param need_align Required alignment; values below 2 always pass.
 * @param loc_file Source file of the access site.
 * @param loc_line Source line of the access site.
 */
static void _rt_check_ptr_align(void *ptr, size_t need_align, const char *loc_file, int loc_line) {
    if (!_rt_ptr_is_aligned(ptr, need_align)) {
        _rt_panic_invalid_access("misaligned pointer access", ptr, loc_file, loc_line);
    }
}

/**
 * Reject a write through a registered read-only allocation.
 *
 * @param rec Live tracker record updated by this operation.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_check_record_writeable(_rt_alloc_record *rec, void *ptr, int access_mode, const char *loc_file, int loc_line) {
    if (access_mode == _RT_ACCESS_WRITE && rec->read_only) {
        _rt_panic_invalid_access("read-only pointer write", ptr, loc_file, loc_line);
    }
}

/**
 * Cache an allocation owner and generation at a pointer access site.
 *
 * @param site Optional mutable cache for this generated pointer access site.
 * @param owner Borrowed allocation record owning the validated span.
 */
static void _rt_ptr_site_store(_rt_ptr_site *site, _rt_alloc_record *owner) {
    if (site == NULL || owner == NULL) return;
    site->owner = owner;
    site->generation = owner->generation;
}

/**
 * Register a live allocation with its memory kind, permissions, and allocation site.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param size Requested storage size in bytes.
 * @param align Required storage alignment in bytes.
 * @param type_id Reserved runtime type-identity tag.
 * @param mem_kind Runtime ownership category for the allocation.
 * @param read_only Nonzero for immutable borrowed storage.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_track_alloc_record_kind(
    void *ptr,
    size_t size,
    size_t align,
    uint32_t type_id,
    int mem_kind,
    int read_only,
    const char *loc_file,
    int loc_line
) {
    if (ptr == NULL) return;
    _rt_tracker_config_init();
    if (_rt_alloc_table_lookup(ptr) != NULL) {
        _rt_panic_fmt("runtime allocation tracker: duplicate allocation address %p", ptr);
    }

    _rt_alloc_record_cold *cold = NULL;
    _rt_alloc_record *rec = _rt_rec_new(&cold);

    rec->base = ptr;
    rec->size = size == 0 ? 1u : size;
    rec->generation = _rt_alloc_next_generation++;
    if (_rt_alloc_next_generation == 0) _rt_alloc_next_generation = 1;
    rec->state = _RT_ALLOC_LIVE;
    rec->read_only = read_only ? 1u : 0u;
    rec->mem_kind = (uint8_t)mem_kind;
    cold->align = align;
    cold->type_id = type_id;
    cold->alloc_file = loc_file;
    cold->alloc_line = loc_line;
    cold->drop_file = NULL;
    cold->drop_line = 0;
    cold->reserved = 0;
    rec->q_next = NULL;

    _rt_alloc_table_insert_record(rec);
#ifndef DEA_RT_CHECK_BASIC
    _rt_alloc_tree_insert(rec);
#endif
}

/**
 * Register a raw allocation when runtime pointer tracking is enabled.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param size Requested storage size in bytes.
 * @param align Required storage alignment in bytes.
 * @param type_id Reserved runtime type-identity tag.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_track_alloc_record(
    void *ptr,
    size_t size,
    size_t align,
    uint32_t type_id,
    const char *loc_file,
    int loc_line
) {
    _rt_track_alloc_record_kind(ptr, size, align, type_id, _RT_MEM_RAW, 0, loc_file, loc_line);
}

/**
 * Mark a fresh raw allocation as object storage when runtime tracking is enabled.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 */
static void _rt_promote_new_alloc(void *ptr) {
    if (ptr == NULL) return;

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL || rec->state != _RT_ALLOC_LIVE || rec->mem_kind != _RT_MEM_RAW) {
        _rt_panic_fmt("runtime allocation tracker: cannot promote non-raw allocation %p to new", ptr);
    }
    rec->mem_kind = _RT_MEM_NEW;
}

/**
 * Lazily register ARC-managed string storage as a read-only tracked record in checked builds.
 * Idempotent: repeated exposure of the same live block is a no-op, so
 * `rt_string_bytes_ptr` may call this on every invocation.
 *
 * Unchecked builds leave this storage unregistered.
 *
 * @param ptr Base of the live ARC-managed byte storage.
 * @param size Storage extent in bytes.
 */
void _rt_track_arc_bytes(void *ptr, size_t size) {
    if (ptr == NULL) return;
    if (_rt_alloc_table_lookup(ptr) != NULL) return;

    _rt_track_alloc_record_kind(ptr, size, 0, 0, _RT_MEM_ARC, 1, "<runtime>", 0);
}

/**
 * Remove any allocation-tracker record for ARC storage without freeing its bytes.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 */
void _rt_untrack_arc_alloc(void *ptr) {
    if (ptr == NULL) return;

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL) return;

    _rt_alloc_table_remove_record(rec);
#ifndef DEA_RT_CHECK_BASIC
    _rt_alloc_tree_remove(rec);
#endif
    _rt_rec_recycle(rec);
}

/**
 * Register borrowed immutable static storage in checked builds.
 *
 * Unchecked builds leave this storage unregistered.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param size Requested storage size in bytes.
 */
void _rt_track_static_bytes(const void *ptr, size_t size) {
    if (ptr == NULL) return;
    if (_rt_alloc_table_lookup((void*)ptr) != NULL) return;
#ifndef DEA_RT_CHECK_BASIC
    if (_rt_alloc_tree_find_containing((void*)ptr, size == 0 ? 1u : size) != NULL) return;
#endif

    _rt_track_alloc_record_kind((void*)ptr, size, 0, 0, _RT_MEM_STATIC, 1, "<static>", 0);
}

/**
 * Validate foreign storage and register it for checked generated pointer accesses.
 *
 * @param ptr Non-NULL base of externally owned storage.
 * @param bytes Positive storage extent in bytes.
 * @param read_only Whether checked generated writes must be rejected.
 */
void rt_register_foreign(void *ptr, dea_int bytes, dea_bool read_only) {
    if (ptr == NULL) {
        _rt_panic("rt_register_foreign: null pointer");
    }
    if (bytes <= 0) {
        _rt_panic("rt_register_foreign: invalid byte extent");
    }
    if (read_only != 0 && read_only != 1) {
        _rt_panic("rt_register_foreign: invalid read-only flag");
    }

    size_t size = (size_t)bytes;
    uintptr_t base_addr = (uintptr_t)ptr;
    if (size > UINTPTR_MAX - base_addr) {
        _rt_panic("rt_register_foreign: address range overflow");
    }

    _rt_alloc_record *existing = _rt_alloc_table_lookup(ptr);
    if (existing != NULL) {
        if (existing->state == _RT_ALLOC_LIVE && existing->mem_kind == _RT_MEM_FOREIGN &&
            existing->size == size && existing->read_only == (read_only ? 1u : 0u)) {
            return;
        }
        _rt_panic_fmt("rt_register_foreign: conflicting tracked base %p", ptr);
    }

#ifndef DEA_RT_CHECK_BASIC
    if (_rt_alloc_tree_find_containing(ptr, 1) != NULL) {
        _rt_panic_fmt("rt_register_foreign: range overlaps tracked storage at %p", ptr);
    }
    _rt_alloc_record *next = _rt_alloc_tree_lub(ptr);
    if (next != NULL && (uintptr_t)next->base < base_addr + size) {
        _rt_panic_fmt("rt_register_foreign: range overlaps tracked storage at %p", next->base);
    }
#endif

    _rt_track_alloc_record_kind(ptr, size, 0, 0, _RT_MEM_FOREIGN, read_only, "<foreign>", 0);
}

/**
 * Remove foreign-span registration in checked builds without freeing its storage.
 *
 * @param ptr Base of a live registered foreign allocation.
 */
void rt_unregister_foreign(void *ptr) {
    if (ptr == NULL) {
        _rt_panic("rt_unregister_foreign: null pointer");
    }

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL || rec->state != _RT_ALLOC_LIVE || rec->mem_kind != _RT_MEM_FOREIGN) {
        _rt_panic_fmt("rt_unregister_foreign: pointer is not a live foreign base %p", ptr);
    }

    _rt_alloc_table_remove_record(rec);
#ifndef DEA_RT_CHECK_BASIC
    _rt_alloc_tree_remove(rec);
#endif
    _rt_rec_recycle(rec);
}

/**
 * Release oldest quarantined payloads until both retention limits are satisfied.
 */
static void _rt_evict_quarantine(void) {
    while (_rt_quarantine_head != NULL &&
           (_rt_quarantine_bytes > _rt_quarantine_max_bytes ||
            _rt_quarantine_count > _rt_quarantine_max_count)) {
        _rt_alloc_record *rec = _rt_quarantine_head;
        _rt_quarantine_head = rec->q_next;
        if (_rt_quarantine_head == NULL) {
            _rt_quarantine_tail = NULL;
        }

        _rt_quarantine_bytes -= rec->size;
        _rt_quarantine_count--;
        _rt_alloc_table_remove_record(rec);
#ifndef DEA_RT_CHECK_BASIC
        _rt_alloc_tree_remove(rec);
#endif
        _RT_ASAN_UNPOISON(rec->base, rec->size);
        free(rec->base);
        _rt_rec_recycle(rec);
    }
}

/**
 * Mark a live allocation released and retain its payload within quarantine limits.
 *
 * @param rec Live tracker record updated by this operation.
 * @param cold Cold metadata associated with the tracker record.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_quarantine_alloc_record(_rt_alloc_record *rec, _rt_alloc_record_cold *cold, const char *loc_file, int loc_line) {
    rec->state = _RT_ALLOC_QUARANTINED;
    cold->drop_file = loc_file;
    cold->drop_line = loc_line;
    rec->q_next = NULL;
    _RT_ASAN_POISON(rec->base, rec->size);

    if (_rt_quarantine_tail == NULL) {
        _rt_quarantine_head = rec;
        _rt_quarantine_tail = rec;
    } else {
        _rt_quarantine_tail->q_next = rec;
        _rt_quarantine_tail = rec;
    }

    _rt_quarantine_bytes += rec->size;
    _rt_quarantine_count++;
    _rt_evict_quarantine();
}

/**
 * Release raw-owned storage, validating its ownership in checked builds.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @param op_name Borrowed runtime operation name for diagnostics.
 */
static void _rt_release_tracked_alloc(void *ptr, const char *loc_file, int loc_line, const char *op_name) {
    if (ptr == NULL) return;

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL) {
#ifndef DEA_RT_CHECK_BASIC
        if (_rt_alloc_tree_find_containing(ptr, 1) != NULL) {
            _rt_panic_invalid_release(op_name, "pointer is not an allocation base", ptr, loc_file, loc_line);
        }
#endif
        _rt_panic_invalid_release(op_name, "unregistered pointer", ptr, loc_file, loc_line);
    }
    _rt_alloc_record_cold *cold = _rt_rec_cold(rec);
    if (rec->mem_kind != _RT_MEM_RAW) {
        const char *reason = "pointer is not a raw allocation";
        if (rec->mem_kind == _RT_MEM_NEW) reason = "new allocation must be released with drop";
        else if (rec->mem_kind == _RT_MEM_ARC) reason = "ARC-managed memory is not raw-owned";
        else if (rec->mem_kind == _RT_MEM_STATIC) reason = "static memory is not raw-owned";
        else if (rec->mem_kind == _RT_MEM_FOREIGN) reason = "foreign memory is not runtime-owned";
        _rt_panic_invalid_release(op_name, reason, ptr, loc_file, loc_line);
    }
    if (rec->state != _RT_ALLOC_LIVE) {
        _rt_panic_fmt(
            "runtime error: double %s\n  pointer: %p\n  first released at: %s:%d\n  second released at: %s:%d",
            op_name ? op_name : "release",
            ptr,
            cold->drop_file ? cold->drop_file : "<unknown>",
            cold->drop_line,
            loc_file ? loc_file : "<unknown>",
            loc_line
        );
    }

    _rt_quarantine_alloc_record(rec, cold, loc_file, loc_line);
}

/**
 * Resize raw-owned storage, preserving the original allocation on failure.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param new_bytes Requested new allocation size in bytes.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Owned resized storage, or NULL on allocation failure; invalid ownership panics in checked
 * builds.
 */
static void *_rt_realloc_tracked_alloc(void *ptr, dea_int new_bytes, const char *loc_file, int loc_line) {
    size_t new_size = (size_t)new_bytes;
    if (ptr == NULL) {
        void *new_ptr = malloc(new_size);
        if (new_ptr != NULL) {
            _rt_track_alloc_record(new_ptr, new_size, 0, 0, loc_file, loc_line);
        }
        return new_ptr;
    }

    _rt_alloc_record *old_rec = _rt_alloc_table_lookup(ptr);
    _rt_alloc_record_cold *old_cold = old_rec != NULL ? _rt_rec_cold(old_rec) : NULL;
    if (old_rec == NULL || old_rec->state != _RT_ALLOC_LIVE ||
        old_rec->mem_kind != _RT_MEM_RAW) {
        const char *reason = "invalid realloc pointer";
        if (old_rec != NULL && old_rec->mem_kind == _RT_MEM_NEW) {
            reason = "new allocation cannot be reallocated";
        } else if (old_rec != NULL && old_rec->mem_kind == _RT_MEM_FOREIGN) {
            reason = "foreign memory is not runtime-owned";
        }
        _rt_panic_invalid_release("rt_realloc", reason, ptr, loc_file, loc_line);
    }

    void *new_ptr = malloc(new_size);
    if (new_ptr == NULL) {
        return NULL;
    }

    size_t copy_size = old_rec->size < new_size ? old_rec->size : new_size;
    if (copy_size > 0) {
        memcpy(new_ptr, ptr, copy_size);
    }
    _rt_track_alloc_record(new_ptr, new_size, old_cold->align, old_cold->type_id, loc_file, loc_line);
    _rt_quarantine_alloc_record(old_rec, old_cold, loc_file, loc_line);
    return new_ptr;
}

/**
 * Validate an uncached pointer access under the selected runtime check policy.
 *
 * @param site Optional mutable cache for this generated pointer access site.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param required_size Generated required accessible byte extent.
 * @param required_align Generated required byte alignment.
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original pointer; invalid checked accesses terminate execution.
 */
void *_rt_check_ptr_site_slow(_rt_ptr_site *site, void *ptr, dea_int required_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line) {
    if (ptr == NULL) {
        _rt_panic_invalid_access("null pointer access", ptr, loc_file, loc_line);
    }

    size_t need_size = _rt_required_size(required_size);
    size_t need_align = _rt_required_align(required_align);
    int mode = _rt_required_access_mode(access_mode);

    _rt_alloc_record *base = _rt_alloc_table_lookup(ptr);
    if (base != NULL) {
        if (base->state != _RT_ALLOC_LIVE) {
            _rt_alloc_record_cold *base_cold = _rt_rec_cold(base);
            _rt_panic_fmt(
                "runtime error: use after drop/free\n  pointer: %p\n  allocated at: %s:%d\n  released at: %s:%d\n  accessed at: %s:%d",
                ptr,
                base_cold->alloc_file ? base_cold->alloc_file : "<unknown>",
                base_cold->alloc_line,
                base_cold->drop_file ? base_cold->drop_file : "<unknown>",
                base_cold->drop_line,
                loc_file ? loc_file : "<unknown>",
                loc_line
            );
        }
        if (need_size > base->size) {
            _rt_panic_invalid_access("pointer access exceeds allocation size", ptr, loc_file, loc_line);
        }
        _rt_check_ptr_align(ptr, need_align, loc_file, loc_line);
        _rt_check_record_writeable(base, ptr, mode, loc_file, loc_line);
        _rt_ptr_site_store(site, base);
        return ptr;
    }

#ifdef DEA_RT_CHECK_BASIC
    _rt_check_ptr_align(ptr, need_align, loc_file, loc_line);
    return ptr;
#else
    _rt_alloc_record *owner = _rt_alloc_tree_find_containing(ptr, need_size);
    if (owner != NULL) {
        if (owner->state != _RT_ALLOC_LIVE) {
            _rt_panic_invalid_access("stale derived pointer access", ptr, loc_file, loc_line);
        }
        _rt_check_ptr_align(ptr, need_align, loc_file, loc_line);
        _rt_check_record_writeable(owner, ptr, mode, loc_file, loc_line);
        _rt_ptr_site_store(site, owner);
        return ptr;
    }

    if (_rt_alloc_tree_find_containing(ptr, 1) != NULL) {
        _rt_panic_invalid_access("pointer access exceeds allocation size", ptr, loc_file, loc_line);
    }

    _rt_panic_invalid_access("unregistered pointer access", ptr, loc_file, loc_line);
    return ptr;
#endif
}

/**
 * Validate and form an indexed pointer under the selected runtime check policy.
 *
 * @param site Optional mutable cache for this generated pointer access site.
 * @param base_ptr Pointer used as the indexed access base.
 * @param index Requested element index.
 * @param element_size Positive size of one indexed element in bytes.
 * @param required_align Generated required byte alignment.
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Indexed pointer; invalid checked accesses terminate execution.
 */
void *_rt_check_index_ptr_site_slow(_rt_ptr_site *site, void *base_ptr, dea_int index, dea_int element_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line) {
    if (base_ptr == NULL) {
        _rt_panic_invalid_access("null pointer access", base_ptr, loc_file, loc_line);
    }

    size_t elem_size = _rt_index_element_size(element_size);
    size_t index_offset = _rt_index_offset(index, elem_size);
    size_t need_align = _rt_required_align(required_align);
    int mode = _rt_index_access_mode(access_mode);

    _rt_alloc_record *owner = _rt_alloc_table_lookup(base_ptr);
#ifndef DEA_RT_CHECK_BASIC
    if (owner == NULL) {
        owner = _rt_alloc_tree_find_containing(base_ptr, 1);
    }
#endif
    if (owner == NULL) {
#ifdef DEA_RT_CHECK_BASIC
        {
#else
        if (_rt_index_allows_untracked(access_mode)) {
#endif
            uintptr_t base_addr = (uintptr_t)base_ptr;
            if (index_offset > UINTPTR_MAX - base_addr) {
                _rt_panic_invalid_access("pointer index outside allocation", base_ptr, loc_file, loc_line);
            }
            void *target = (void *)(base_addr + index_offset);
            _rt_check_ptr_align(target, need_align, loc_file, loc_line);
            return target;
        }
        _rt_panic_invalid_access("unregistered pointer index base", base_ptr, loc_file, loc_line);
    }
    if (owner->state != _RT_ALLOC_LIVE) {
        _rt_alloc_record_cold *owner_cold = _rt_rec_cold(owner);
        _rt_panic_fmt(
            "runtime error: use after drop/free\n  pointer: %p\n  allocated at: %s:%d\n  released at: %s:%d\n  accessed at: %s:%d",
            base_ptr,
            owner_cold->alloc_file ? owner_cold->alloc_file : "<unknown>",
            owner_cold->alloc_line,
            owner_cold->drop_file ? owner_cold->drop_file : "<unknown>",
            owner_cold->drop_line,
            loc_file ? loc_file : "<unknown>",
            loc_line
        );
    }

    size_t base_offset = 0;
    if (!_rt_range_contains(owner->base, owner->size, base_ptr, 1, &base_offset)) {
        _rt_panic_invalid_access("pointer index base outside allocation", base_ptr, loc_file, loc_line);
    }

    /* Two-step subtraction form: folding this into one containment check on
     * index_offset + elem_size could wrap size_t, so bound each term against
     * the remaining capacity instead. The first comparison guarantees the
     * second subtraction cannot underflow. */
    if (index_offset > owner->size - base_offset ||
        elem_size > owner->size - base_offset - index_offset) {
        _rt_panic_invalid_access("pointer index outside allocation", base_ptr, loc_file, loc_line);
    }

    uintptr_t owner_addr = (uintptr_t)owner->base;
    size_t target_offset = base_offset + index_offset;
    if (target_offset > UINTPTR_MAX - owner_addr) {
        _rt_panic_invalid_access("pointer index outside allocation", base_ptr, loc_file, loc_line);
    }

    void *target = (void *)(owner_addr + target_offset);
    _rt_check_ptr_align(target, need_align, loc_file, loc_line);
    _rt_check_record_writeable(owner, target, mode, loc_file, loc_line);
    _rt_ptr_site_store(site, owner);
    return target;
}

/**
 * Validate object storage before its destructor under the selected runtime check policy.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param required_size Generated required accessible byte extent.
 * @param required_align Generated required byte alignment.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original pointer, including NULL; invalid checked drops terminate execution.
 */
void *_rt_drop_begin_impl(
    void *ptr,
    dea_int required_size,
    dea_int required_align,
    const char *loc_file,
    int loc_line
) {
    if (ptr == NULL) {
        return NULL;
    }

    size_t need_size = _rt_required_size(required_size);
    size_t need_align = _rt_required_align(required_align);

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL) {
#ifndef DEA_RT_CHECK_BASIC
        if (_rt_alloc_tree_find_containing(ptr, 1) != NULL) {
            _rt_trace_invalid_drop(ptr, loc_file, loc_line);
            _rt_panic_invalid_drop("pointer is not an allocation base", ptr, loc_file, loc_line);
        }
#endif
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_invalid_drop("unregistered pointer", ptr, loc_file, loc_line);
    }
    _rt_alloc_record_cold *cold = _rt_rec_cold(rec);
    if (rec->mem_kind != _RT_MEM_NEW) {
        const char *reason = "pointer was not allocated by new";
        if (rec->mem_kind == _RT_MEM_ARC) reason = "ARC-managed memory is not droppable";
        else if (rec->mem_kind == _RT_MEM_STATIC) reason = "static memory is not droppable";
        else if (rec->mem_kind == _RT_MEM_FOREIGN) reason = "foreign memory is not runtime-owned";
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_invalid_drop(reason, ptr, loc_file, loc_line);
    }
    if (rec->state != _RT_ALLOC_LIVE) {
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_fmt(
            "runtime error: double drop\n  pointer: %p\n  first dropped at: %s:%d\n  second dropped at: %s:%d",
            ptr,
            cold->drop_file ? cold->drop_file : "<unknown>",
            cold->drop_line,
            loc_file ? loc_file : "<unknown>",
            loc_line
        );
    }
    if (need_size > rec->size) {
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_invalid_drop("drop pointee exceeds allocation size", ptr, loc_file, loc_line);
    }
    if (!_rt_ptr_is_aligned(ptr, need_align)) {
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_invalid_drop("misaligned drop pointer", ptr, loc_file, loc_line);
    }

    return ptr;
}

/**
 * Release object storage after its destructor and record its release location.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
void _rt_drop_finish_impl(void *ptr, const char *loc_file, int loc_line) {
    if (ptr == NULL) {
        _RT_TRACE_MEM("op=drop ptr=%p action=noop-null loc=\"%s\":%d", ptr, loc_file, loc_line);
        return;
    }

    _rt_alloc_record *rec = _rt_alloc_table_lookup(ptr);
    if (rec == NULL || rec->state != _RT_ALLOC_LIVE || rec->mem_kind != _RT_MEM_NEW) {
        _rt_trace_invalid_drop(ptr, loc_file, loc_line);
        _rt_panic_invalid_drop("drop finish without live drop begin", ptr, loc_file, loc_line);
    }

    _RT_TRACE_MEM("op=drop ptr=%p action=free loc=\"%s\":%d", ptr, loc_file, loc_line);
    _rt_quarantine_alloc_record(rec, _rt_rec_cold(rec), loc_file, loc_line);
}

/**
 * Validate a derived span against its registered parent in checked builds.
 *
 * @param derived Derived pointer being checked.
 * @param parent_base Pointer identifying the parent allocation.
 * @param size Requested storage size in bytes.
 * @param align Required storage alignment in bytes.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original derived pointer; invalid registered spans terminate execution.
 */
void *_rt_validate_derived_ptr(
    void *derived,
    void *parent_base,
    dea_int size,
    dea_int align,
    const char *loc_file,
    int loc_line
) {
    if (derived == NULL || parent_base == NULL) {
        return derived;
    }

    size_t required_size = _rt_required_size(size);
    size_t required_align = _rt_required_align(align);

    _rt_alloc_record *parent = _rt_alloc_table_lookup(parent_base);
#ifndef DEA_RT_CHECK_BASIC
    if (parent == NULL) {
        parent = _rt_alloc_tree_find_containing(parent_base, 1);
    }
#endif
    if (parent == NULL) {

        /* Unregistered parent storage: leave validation to the access site. */
        return derived;
    }
    if (parent->state != _RT_ALLOC_LIVE) {
        _rt_panic_invalid_access("stale derived pointer access", parent_base, loc_file, loc_line);
    }
    if (!_rt_range_contains(parent->base, parent->size, derived, required_size, NULL)) {
        _rt_panic_invalid_access("derived pointer outside parent allocation", derived, loc_file, loc_line);
    }
    if (!_rt_ptr_is_aligned(derived, required_align)) {
        _rt_panic_invalid_access("misaligned derived pointer", derived, loc_file, loc_line);
    }
    return derived;
}

/* DEA_RT_UNCHECKED */
#else

/**
 * Register a raw allocation when runtime pointer tracking is enabled.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param size Requested storage size in bytes.
 * @param align Required storage alignment in bytes.
 * @param type_id Reserved runtime type-identity tag.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
static void _rt_track_alloc_record(
    void *ptr,
    size_t size,
    size_t align,
    uint32_t type_id,
    const char *loc_file,
    int loc_line
) {
    (void)ptr; (void)size; (void)align; (void)type_id; (void)loc_file; (void)loc_line;
}

/**
 * Mark a fresh raw allocation as object storage when runtime tracking is enabled.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 */
static void _rt_promote_new_alloc(void *ptr) {
    (void)ptr;
}

/**
 * Lazily register ARC-managed string storage as a read-only tracked record in checked builds.
 * Idempotent: repeated exposure of the same live block is a no-op, so
 * `rt_string_bytes_ptr` may call this on every invocation.
 *
 * Unchecked builds leave this storage unregistered.
 *
 * @param ptr Base of the live ARC-managed byte storage.
 * @param size Storage extent in bytes.
 */
void _rt_track_arc_bytes(void *ptr, size_t size) {
    (void)ptr; (void)size;
}

/**
 * Remove any allocation-tracker record for ARC storage without freeing its bytes.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 */
void _rt_untrack_arc_alloc(void *ptr) {
    (void)ptr;
}

/**
 * Register borrowed immutable static storage in checked builds.
 *
 * Unchecked builds leave this storage unregistered.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param size Requested storage size in bytes.
 */
void _rt_track_static_bytes(const void *ptr, size_t size) {
    (void)ptr; (void)size;
}

/**
 * Validate foreign storage and register it for checked generated pointer accesses.
 *
 * @param ptr Non-NULL base of externally owned storage.
 * @param bytes Positive storage extent in bytes.
 * @param read_only Whether checked generated writes must be rejected.
 */
void rt_register_foreign(void *ptr, dea_int bytes, dea_bool read_only) {
    if (ptr == NULL) {
        _rt_panic("rt_register_foreign: null pointer");
    }
    if (bytes <= 0) {
        _rt_panic("rt_register_foreign: invalid byte extent");
    }
    if (read_only != 0 && read_only != 1) {
        _rt_panic("rt_register_foreign: invalid read-only flag");
    }
}

/**
 * Remove foreign-span registration in checked builds without freeing its storage.
 *
 * @param ptr Base of a live registered foreign allocation.
 */
void rt_unregister_foreign(void *ptr) {
    if (ptr == NULL) {
        _rt_panic("rt_unregister_foreign: null pointer");
    }
}

/**
 * Release raw-owned storage, validating its ownership in checked builds.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @param op_name Borrowed runtime operation name for diagnostics.
 */
static void _rt_release_tracked_alloc(void *ptr, const char *loc_file, int loc_line, const char *op_name) {
    (void)loc_file; (void)loc_line; (void)op_name;
    free(ptr);
}

/**
 * Resize raw-owned storage, preserving the original allocation on failure.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param new_bytes Requested new allocation size in bytes.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Owned resized storage, or NULL on allocation failure; invalid ownership panics in checked
 * builds.
 */
static void *_rt_realloc_tracked_alloc(void *ptr, dea_int new_bytes, const char *loc_file, int loc_line) {
    (void)loc_file; (void)loc_line;
    return realloc(ptr, (size_t)new_bytes);
}

/* Passthrough so generated code compiled in checked mode still links. */

/**
 * Validate an uncached pointer access under the selected runtime check policy.
 *
 * @param site Optional mutable cache for this generated pointer access site.
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param required_size Generated required accessible byte extent.
 * @param required_align Generated required byte alignment.
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original pointer; invalid checked accesses terminate execution.
 */
void *_rt_check_ptr_site_slow(_rt_ptr_site *site, void *ptr, dea_int required_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line) {
    (void)site; (void)required_size; (void)required_align; (void)access_mode; (void)loc_file; (void)loc_line;
    return ptr;
}

/**
 * Validate and form an indexed pointer under the selected runtime check policy.
 *
 * @param site Optional mutable cache for this generated pointer access site.
 * @param base_ptr Pointer used as the indexed access base.
 * @param index Requested element index.
 * @param element_size Positive size of one indexed element in bytes.
 * @param required_align Generated required byte alignment.
 * @param access_mode Generated read/write access tag and supported indexing policy bits.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Indexed pointer; invalid checked accesses terminate execution.
 */
void *_rt_check_index_ptr_site_slow(_rt_ptr_site *site, void *base_ptr, dea_int index, dea_int element_size, dea_int required_align, int access_mode, const char *loc_file, int loc_line) {
    uint64_t offset = (uint64_t)((int64_t)index * (int64_t)element_size);
    (void)site; (void)required_align; (void)access_mode; (void)loc_file; (void)loc_line;
    return (void *)((uintptr_t)base_ptr + (uintptr_t)offset);
}

/**
 * Validate object storage before its destructor under the selected runtime check policy.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param required_size Generated required accessible byte extent.
 * @param required_align Generated required byte alignment.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original pointer, including NULL; invalid checked drops terminate execution.
 */
void *_rt_drop_begin_impl(
    void *ptr,
    dea_int required_size,
    dea_int required_align,
    const char *loc_file,
    int loc_line
) {
    (void)required_size; (void)required_align; (void)loc_file; (void)loc_line;
    return ptr;
}

/**
 * Release object storage after its destructor and record its release location.
 *
 * @param ptr Pointer whose runtime allocation or access is being handled.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 */
void _rt_drop_finish_impl(void *ptr, const char *loc_file, int loc_line) {
    if (ptr == NULL) {
        _RT_TRACE_MEM("op=drop ptr=%p action=noop-null loc=\"%s\":%d", ptr, loc_file, loc_line);
        return;
    }

    _RT_TRACE_MEM("op=drop ptr=%p action=free loc=\"%s\":%d", ptr, loc_file, loc_line);
    free(ptr);
}

/**
 * Validate a derived span against its registered parent in checked builds.
 *
 * @param derived Derived pointer being checked.
 * @param parent_base Pointer identifying the parent allocation.
 * @param size Requested storage size in bytes.
 * @param align Required storage alignment in bytes.
 * @param loc_file Borrowed source filename used in diagnostics and trace events.
 * @param loc_line Source line used in diagnostics and trace events.
 * @return Original derived pointer; invalid registered spans terminate execution.
 */
void *_rt_validate_derived_ptr(
    void *derived,
    void *parent_base,
    dea_int size,
    dea_int align,
    const char *loc_file,
    int loc_line
) {
    (void)parent_base; (void)size; (void)align; (void)loc_file; (void)loc_line;
    return derived;
}

/* DEA_RT_UNCHECKED */
#endif

#ifdef DEA_TRACE_MEMORY

/**
 * Allocate zero-filled object storage owned by a generated new expression.
 *
 * The returned storage belongs to the generated object lifecycle and must be released through its matching
 * drop path, rather than rt_free or rt_realloc. Checked builds record object ownership.
 *
 * Nonpositive sizes and native allocation failure terminate execution.
 *
 * This source-located entry records the supplied location when tracing is enabled.
 *
 * @param bytes Positive object storage size in bytes.
 * @param _loc_file Borrowed source filename for trace events and diagnostics.
 * @param _loc_line Source line for trace events and diagnostics.
 * @return Owned zero-filled object storage; allocation failure terminates execution.
 */
void *_rt_alloc_obj_impl(dea_int bytes, const char *_loc_file, int _loc_line) {
    if (bytes <= 0) {
        _rt_panic("new: invalid allocation size");
    }

    void *ptr = _rt_calloc_impl(1, bytes, _loc_file, _loc_line);
    if (ptr == NULL) {
        _rt_free_impl(ptr, _loc_file, _loc_line);
        _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=panic-oom loc=\"%s\":%d", (int)bytes, ptr, _loc_file, _loc_line);
        _rt_panic("new: out of memory");
    }

    _rt_promote_new_alloc(ptr);
    _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=ok loc=\"%s\":%d", (int)bytes, ptr, _loc_file, _loc_line);
    return ptr;
}
#define _rt_alloc_obj(bytes) _rt_alloc_obj_impl((bytes), __FILE__, __LINE__)
#else

/**
 * Allocate zero-filled object storage owned by a generated new expression.
 *
 * The returned storage belongs to the generated object lifecycle and must be released through its matching
 * drop path, rather than rt_free or rt_realloc. Checked builds record object ownership.
 *
 * Nonpositive sizes and native allocation failure terminate execution.
 *
 * @param bytes Positive object storage size in bytes.
 * @return Owned zero-filled object storage; allocation failure terminates execution.
 */
void *_rt_alloc_obj(dea_int bytes) {
    if (bytes <= 0) {
        _rt_panic("new: invalid allocation size");
    }

    void *ptr = rt_calloc(1, bytes);
    if (ptr == NULL) {
        rt_free(ptr);
        _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=panic-oom", (int)bytes, ptr);
        _rt_panic("new: out of memory");
    }

    _rt_promote_new_alloc(ptr);
    _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=ok", (int)bytes, ptr);
    return ptr;
}
#endif

#if defined(DEA_TRACE_MEMORY)
#undef rt_alloc

/**
 * Allocate a positive number of raw runtime-owned bytes.
 *
 * The caller owns a successful allocation and releases it exactly once with rt_free, or passes it to
 * rt_realloc. The contents are uninitialized.
 *
 * Nonpositive byte counts and sizes not representable as size_t terminate execution. A native allocation
 * failure returns NULL. Checked builds register successful storage for pointer validation; unchecked
 * builds omit tracking.
 *
 * Dea signature: `extern func rt_alloc(bytes: int) -> void*?;`
 *
 * @param bytes Positive requested storage size in bytes.
 * @return Owned raw allocation, or NULL on native allocation failure.
 */
void *rt_alloc(dea_int bytes) {
    return _rt_alloc_impl(bytes, "<runtime>", 0);
}

#undef rt_realloc

/**
 * Resize raw runtime-owned storage while preserving it on allocation failure.
 *
 * A NULL input requests a fresh allocation. Otherwise ptr must be a live raw allocation base from
 * rt_alloc, rt_calloc, or an earlier successful rt_realloc. Object, ARC, static, and foreign storage
 * cannot be reallocated through this API.
 *
 * Nonpositive or unrepresentable sizes terminate execution. Checked builds also reject unregistered,
 * interior, released, or non-raw pointers. Unchecked builds require a valid C realloc operand and omit
 * tracker validation.
 *
 * On success the result owns the resized storage, preserving the first minimum of the old and new byte
 * extents. Every pointer into the previous allocation expires, even if the native allocator reuses its
 * address. Release the result exactly once with rt_free or resize it again.
 *
 * On native allocation failure NULL is returned and the original allocation and its aliases remain valid.
 * Checked builds quarantine replaced storage to diagnose stale accesses.
 *
 * Dea signature: `unsafe extern func rt_realloc(ptr: void*?, new_bytes: int) -> void*?;`
 *
 * @param ptr Live raw allocation base to resize, or NULL to allocate fresh.
 * @param new_bytes Positive requested new storage size in bytes.
 * @return Owned resized allocation, or NULL while preserving the original allocation on failure.
 */
void *rt_realloc(void *ptr, dea_int new_bytes) {
    return _rt_realloc_impl(ptr, new_bytes, "<runtime>", 0);
}

#undef rt_free

/**
 * Release a raw runtime allocation, accepting NULL as a no-op.
 *
 * A non-NULL ptr must be a live raw allocation base from rt_alloc, rt_calloc, or successful rt_realloc. It
 * must be released exactly once. All pointers into its storage expire after this call.
 *
 * Checked builds reject interior, unregistered, already released, object, ARC, static, and foreign
 * pointers. Released storage enters the bounded quarantine before eventual native deallocation. Unchecked
 * builds call native free and require its normal valid-pointer preconditions.
 *
 * Dea signature: `unsafe extern func rt_free(ptr: void*?) -> void;`
 *
 * @param ptr Live raw allocation base to consume exactly once, or NULL.
 */
void rt_free(void *ptr) {
    _rt_free_impl(ptr, "<runtime>", 0);
}

#undef rt_calloc

/**
 * Allocate a positive count of zero-filled raw runtime-owned elements.
 *
 * The caller owns successful storage and releases it exactly once with rt_free, or passes it to
 * rt_realloc.
 *
 * Nonpositive counts or element sizes and products not representable as size_t terminate execution. A
 * native allocation failure returns NULL. Checked builds register the allocation; unchecked builds omit
 * tracking.
 *
 * Dea signature: `extern func rt_calloc(count: int, elem_size: int) -> void*?;`
 *
 * @param count Positive number of elements to allocate.
 * @param elem_size Positive size of one element in bytes.
 * @return Owned zero-filled raw allocation, or NULL on native allocation failure.
 */
void *rt_calloc(dea_int count, dea_int elem_size) {
    return _rt_calloc_impl(count, elem_size, "<runtime>", 0);
}

#undef _rt_alloc_obj

/**
 * Allocate zero-filled object storage owned by a generated new expression.
 *
 * The returned storage belongs to the generated object lifecycle and must be released through its matching
 * drop path, rather than rt_free or rt_realloc. Checked builds record object ownership.
 *
 * Nonpositive sizes and native allocation failure terminate execution.
 *
 * @param bytes Positive object storage size in bytes.
 * @return Owned zero-filled object storage; allocation failure terminates execution.
 */
void *_rt_alloc_obj(dea_int bytes) {
    return _rt_alloc_obj_impl(bytes, "<runtime>", 0);
}

#endif
