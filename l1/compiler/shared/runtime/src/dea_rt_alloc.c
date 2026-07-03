/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for memory allocation (alloc, realloc, free, calloc), raw
 * memory operations (memset, memcpy, memcmp, array element addressing),
 * managed object lifecycle (alloc_obj, drop), and the internal allocation
 * tracking table.
 * ========================================================================= */

/**
 * Allocate memory of the given size in bytes.
 * Returns NULL on allocation failure or if bytes is zero.
 * Panics if bytes is negative, or too large to fit in size_t (platform-dependent).
 *
 * @param bytes Size in bytes.
 * @return Pointer to allocated memory or NULL.
 *
 * Dea signature: `extern func rt_alloc(bytes: int) -> void*?;`
 */
#ifdef DEA_TRACE_MEMORY
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

    _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=ok loc=\"%s\":%d", (int)bytes, ptr, _loc_file, _loc_line);
    return ptr;
}
#define rt_alloc(bytes) _rt_alloc_impl((bytes), __FILE__, __LINE__)
#else
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

    _RT_TRACE_MEM("op=alloc bytes=%d ptr=%p action=ok", (int)bytes, ptr);
    return ptr;
}
#endif

/**
 * Reallocate memory to a new size.
 * Returns NULL on failure.
 * Panics if new_bytes is negative or too large to fit in size_t (platform-dependent).
 * If ptr is NULL, behaves like rt_alloc.
 *
 * @param ptr Pointer to memory, or NULL to allocate fresh.
 * @param new_bytes New size.
 * @return Pointer to reallocated memory or NULL.
 *
 * Dea signature: `unsafe extern func rt_realloc(ptr: void*?, new_bytes: int) -> void*?;`
 */
#ifdef DEA_TRACE_MEMORY
void *_rt_realloc_impl(void *ptr, dea_int new_bytes, const char *_loc_file, int _loc_line) {
    /* zero-size allocations are not allowed */
    if (new_bytes <= 0) {
        _rt_panic("rt_realloc: invalid allocation size");
    }

    if ((uint64_t)new_bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_realloc: allocation size overflow (%d bytes requested)", (int)new_bytes);
    }

    volatile uintptr_t old_ptr_addr = (uintptr_t)ptr;
    size_t new_size = (size_t)new_bytes;
    void *new_ptr = realloc((void*)old_ptr_addr, new_size);

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
void *rt_realloc(void *ptr, dea_int new_bytes) {
    /* zero-size allocations are not allowed */
    if (new_bytes <= 0) {
        _rt_panic("rt_realloc: invalid allocation size");
    }

    if ((uint64_t)new_bytes > SIZE_MAX) {
        _rt_panic_fmt("rt_realloc: allocation size overflow (%d bytes requested)", (int)new_bytes);
    }

    volatile uintptr_t old_ptr_addr = (uintptr_t)ptr;
    size_t new_size = (size_t)new_bytes;
    void *new_ptr = realloc((void*)old_ptr_addr, new_size);

    if (new_ptr == NULL) {
        /* Real failure! original pointer is still valid */
        _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=fail", (void*)old_ptr_addr, (int)new_bytes, (void*)new_ptr);
        return NULL;
    }

    _RT_TRACE_MEM("op=realloc old_ptr=%p bytes=%d new_ptr=%p action=ok", (void*)old_ptr_addr, (int)new_bytes, new_ptr);
    return new_ptr;
}
#endif

/**
 * Free previously allocated memory.
 *
 * @param ptr Pointer to free.
 *
 * Dea signature: `unsafe extern func rt_free(ptr: void*?) -> void;`
 */
#ifdef DEA_TRACE_MEMORY
void _rt_free_impl(void *ptr, const char *_loc_file, int _loc_line) {
    /* free(NULL) is a no-op in C */
    _RT_TRACE_MEM("op=free ptr=%p action=call loc=\"%s\":%d", ptr, _loc_file, _loc_line);
    free(ptr);
}
#define rt_free(ptr) _rt_free_impl((ptr), __FILE__, __LINE__)
#else
void rt_free(void *ptr) {
    /* free(NULL) is a no-op in C */
    _RT_TRACE_MEM("op=free ptr=%p action=call", ptr);
    free(ptr);
}
#endif

/**
 * Allocate zeroed memory for an array of elements.
 * Returns NULL on allocation failure or if count/elem_size is negative.
 *
 * @param count Number of elements.
 * @param elem_size Element size.
 * @return Pointer to zeroed memory or NULL.
 *
 * Dea signature: `extern func rt_calloc(count: int, elem_size: int) -> void*?;`
 */
#ifdef DEA_TRACE_MEMORY
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
    return ptr;
}
#define rt_calloc(count, elem_size) _rt_calloc_impl((count), (elem_size), __FILE__, __LINE__)
#else
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
    return ptr;
}
#endif

/**
 * Set memory to a specific byte value.
 * Returns destination pointer.
 *
 * @param dest Destination pointer.
 * @param value Byte value.
 * @param bytes Number of bytes.
 * @return dest.
 *
 * Dea signature: `unsafe extern func rt_memset(dest: void*, value: int, bytes: int) -> void*;`
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
 * @param dest Destination.
 * @param src Source.
 * @param bytes Number of bytes.
 * @return dest.
 *
 * Dea signature: `unsafe extern func rt_memcpy(dest: void*, src: void*, bytes: int) -> void*;`
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
 * Compare two memory regions.
 * Returns 0 if equal, <0 if a < b, >0 if a > b.
 *
 * @param a First region.
 * @param b Second region.
 * @param bytes Number of bytes.
 * @return Comparison result.
 *
 * Dea signature: `unsafe extern func rt_memcmp(a: void*, b: void*, bytes: int) -> int;`
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
 * @param array_data Pointer to array data.
 * @param element_size Size of one element.
 * @param index Element index.
 * @return Pointer to the element.
 *
 * Dea signature: `unsafe extern func rt_array_element(array_data: void*, element_size: int, index: int) -> void*;`
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

    size_t offset = (size_t)index * (size_t)element_size;
    return (void *)((uintptr_t)array_data + offset);
}

/* =========================================================================
 * Runtime support for `new` & `drop`
 * ========================================================================= */

/**
 * Internal allocation tracker for `new` / `drop`.
 *
 * Uses an open-addressing hash table of `void*` pointers for O(1) amortized
 * insert/lookup/remove.  The goal is to make misuse of `drop` (double-free /
 * invalid pointer) a defined runtime panic instead of C undefined behavior.
 */

/** Sentinel value for a deleted slot (tombstone). */
#define _RT_ALLOC_TOMBSTONE ((void*)(uintptr_t)1)

/** Initial hash-table capacity (must be a power of two). */
#define _RT_ALLOC_INIT_CAP 256

static void  **_rt_alloc_table     = NULL;
static size_t  _rt_alloc_table_cap = 0;
static size_t  _rt_alloc_table_cnt = 0; /* live (non-tombstone) entries */

/**
 * Hash a pointer value to a table index (self-contained MurmurHash3 fmix).
 */
size_t _rt_alloc_hash(void *ptr, size_t cap) {
    uint64_t v = (uint64_t)(uintptr_t)ptr;
    uint32_t x = (uint32_t)(v ^ (v >> 32));
    x ^= x >> 16; x *= 0x85ebca6bu;
    x ^= x >> 13; x *= 0xc2b2ae35u;
    x ^= x >> 16;
    return (size_t)(x & (uint32_t)(cap - 1));
}

/**
 * Grow the allocation hash table by 2x and re-insert all live entries.
 */
void _rt_alloc_table_grow(void) {
    size_t old_cap = _rt_alloc_table_cap;
    void **old_tbl = _rt_alloc_table;
    size_t new_cap = old_cap == 0 ? _RT_ALLOC_INIT_CAP : old_cap * 2;

    void **new_tbl = (void**)calloc(new_cap, sizeof(void*));
    if (new_tbl == NULL) {
        _rt_panic("new: out of memory (alloc tracker grow)");
    }

    /* Re-insert live entries (skip NULL and TOMBSTONE). */
    for (size_t i = 0; i < old_cap; i++) {
        void *p = old_tbl[i];
        if (p != NULL && p != _RT_ALLOC_TOMBSTONE) {
            size_t idx = _rt_alloc_hash(p, new_cap);
            while (new_tbl[idx] != NULL) {
                idx = (idx + 1) & (new_cap - 1);
            }
            new_tbl[idx] = p;
        }
    }

    free(old_tbl);
    _rt_alloc_table     = new_tbl;
    _rt_alloc_table_cap = new_cap;
}

/**
 * Insert a pointer into the allocation hash table.
 */
void _rt_alloc_table_insert(void *ptr) {
    /* Grow if load factor exceeds ~70%. */
    if (_rt_alloc_table_cap == 0 ||
        (_rt_alloc_table_cnt + 1) * 10 > _rt_alloc_table_cap * 7) {
        _rt_alloc_table_grow();
    }

    size_t idx = _rt_alloc_hash(ptr, _rt_alloc_table_cap);
    while (_rt_alloc_table[idx] != NULL &&
           _rt_alloc_table[idx] != _RT_ALLOC_TOMBSTONE) {
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
    _rt_alloc_table[idx] = ptr;
    _rt_alloc_table_cnt++;
}

/**
 * Remove a pointer from the allocation hash table.
 *
 * @return 1 if found and removed, 0 if not found.
 */
int _rt_alloc_table_remove(void *ptr) {
    if (_rt_alloc_table_cap == 0) return 0;

    size_t idx = _rt_alloc_hash(ptr, _rt_alloc_table_cap);
    while (_rt_alloc_table[idx] != NULL) {
        if (_rt_alloc_table[idx] == ptr) {
            _rt_alloc_table[idx] = _RT_ALLOC_TOMBSTONE;
            _rt_alloc_table_cnt--;
            return 1;
        }
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
    return 0;
}

/**
 * Check whether a pointer is present in the allocation hash table.
 *
 * @return 1 if found, 0 if not found.
 */
static int _rt_alloc_table_contains(void *ptr) {
    if (_rt_alloc_table_cap == 0) return 0;

    size_t idx = _rt_alloc_hash(ptr, _rt_alloc_table_cap);
    while (_rt_alloc_table[idx] != NULL) {
        if (_rt_alloc_table[idx] == ptr) {
            return 1;
        }
        idx = (idx + 1) & (_rt_alloc_table_cap - 1);
    }
    return 0;
}

/**
 * Allocate a single zero-initialized object for L0 `new`.
 * Panics on failure, and registers the returned pointer for `_rt_drop`.
 *
 * @param bytes Allocation size.
 * @return Pointer to allocated object.
 */
#ifdef DEA_TRACE_MEMORY
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

    _rt_alloc_table_insert(ptr);

    _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=ok loc=\"%s\":%d", (int)bytes, ptr, _loc_file, _loc_line);
    return ptr;
}
#define _rt_alloc_obj(bytes) _rt_alloc_obj_impl((bytes), __FILE__, __LINE__)
#else
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

    _rt_alloc_table_insert(ptr);

    _RT_TRACE_MEM("op=new_alloc bytes=%d ptr=%p action=ok", (int)bytes, ptr);
    return ptr;
}
#endif

/**
 * Validate a heap-allocated object before generated cleanup dereferences it.
 * Does not unregister or free the pointer.
 *
 * @param ptr Pointer to validate.
 */
#ifdef DEA_TRACE_MEMORY
void _rt_drop_precheck_impl(void *ptr, const char *_loc_file, int _loc_line) {
    if (ptr == NULL) {
        return; /* covers drop of null optional pointers (T*?) */
    }

    if (!_rt_alloc_table_contains(ptr)) {
        _RT_TRACE_MEM("op=drop ptr=%p action=panic-not-found loc=\"%s\":%d", ptr, _loc_file, _loc_line);
        _rt_panic("drop: pointer not allocated by 'new'");
    }
}
#define _rt_drop_precheck(ptr) _rt_drop_precheck_impl((ptr), __FILE__, __LINE__)
#else
void _rt_drop_precheck(void *ptr) {
    if (ptr == NULL) {
        return; /* covers drop of null optional pointers (T*?) */
    }

    if (!_rt_alloc_table_contains(ptr)) {
        _RT_TRACE_MEM("op=drop ptr=%p action=panic-not-found", ptr);
        _rt_panic("drop: pointer not allocated by 'new'");
    }
}
#endif

/**
 * Drop a heap-allocated object created by `new`.
 * Frees the memory and unregisters it from the allocation tracker.
 * A NULL pointer is a no-op.
 * Panics on invalid pointers (not previously allocated by `new`).
 *
 * @param ptr Pointer to drop.
 */
#ifdef DEA_TRACE_MEMORY
void _rt_drop_impl(void *ptr, const char *_loc_file, int _loc_line) {
    if (ptr == NULL) {
        _RT_TRACE_MEM("op=drop ptr=%p action=noop-null loc=\"%s\":%d", ptr, _loc_file, _loc_line);
        return; /* covers drop of null optional pointers (T*?) */
    }

    if (!_rt_alloc_table_remove(ptr)) {
        _RT_TRACE_MEM("op=drop ptr=%p action=panic-not-found loc=\"%s\":%d", ptr, _loc_file, _loc_line);
        _rt_panic("drop: pointer not allocated by 'new'");
    }

    _RT_TRACE_MEM("op=drop ptr=%p action=free loc=\"%s\":%d", ptr, _loc_file, _loc_line);
    _rt_free_impl(ptr, _loc_file, _loc_line);
}
#define _rt_drop(ptr) _rt_drop_impl((ptr), __FILE__, __LINE__)
#else
void _rt_drop(void *ptr) {
    if (ptr == NULL) {
        _RT_TRACE_MEM("op=drop ptr=%p action=noop-null", ptr);
        return; /* covers drop of null optional pointers (T*?) */
    }

    if (!_rt_alloc_table_remove(ptr)) {
        _RT_TRACE_MEM("op=drop ptr=%p action=panic-not-found", ptr);
        _rt_panic("drop: pointer not allocated by 'new'");
    }

    _RT_TRACE_MEM("op=drop ptr=%p action=free", ptr);
    free(ptr);
}
#endif

#if defined(DEA_TRACE_MEMORY)
#undef rt_alloc
void *rt_alloc(dea_int bytes) {
    return _rt_alloc_impl(bytes, "<runtime>", 0);
}

#undef rt_realloc
void *rt_realloc(void *ptr, dea_int new_bytes) {
    return _rt_realloc_impl(ptr, new_bytes, "<runtime>", 0);
}

#undef rt_free
void rt_free(void *ptr) {
    _rt_free_impl(ptr, "<runtime>", 0);
}

#undef rt_calloc
void *rt_calloc(dea_int count, dea_int elem_size) {
    return _rt_calloc_impl(count, elem_size, "<runtime>", 0);
}

#undef _rt_alloc_obj
void *_rt_alloc_obj(dea_int bytes) {
    return _rt_alloc_obj_impl(bytes, "<runtime>", 0);
}

#undef _rt_drop_precheck
void _rt_drop_precheck(void *ptr) {
    _rt_drop_precheck_impl(ptr, "<runtime>", 0);
}

#undef _rt_drop
void _rt_drop(void *ptr) {
    _rt_drop_impl(ptr, "<runtime>", 0);
}
#endif
