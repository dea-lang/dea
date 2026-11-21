/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_temp.h
 * Pinned, result-owned temporary objects. Native spellings serve diagnostics only
 * after parent resolution. The file wrapper and retained identity have independent lifetimes.
 */
#ifndef DEA_RT_TEMP_H
#define DEA_RT_TEMP_H

typedef struct __deaM3sys2fsS10RtTempOpen TempOpen;
typedef struct __deaM3sys2fsS13RtTempCleanup TempCleanup;
enum TempOperation { TEMP_OK, TEMP_PARENT, TEMP_ENTROPY, TEMP_CREATE, TEMP_VERIFY,
                     TEMP_ENUMERATE, TEMP_REMOVE, TEMP_CLOSE };
#if defined(_WIN32)
typedef HANDLE TempHandle;
#define TEMP_INVALID INVALID_HANDLE_VALUE
#else
typedef int TempHandle;
#define TEMP_INVALID (-1)
#endif

typedef struct TempOwner {
    TempHandle parent;
    TempHandle object;
    FsChar *path;
    FsChar name[37];
    dea_bool directory;
} TempOwner;

/**
 * Record the first failure and its affected spelling without losing progress.
 *
 * @param result Accumulating cleanup report.
 * @param op Operation which failed.
 * @param path Diagnostic spelling of the affected entry.
 * @param error Immediately captured cause.
 */
static void temp_failure(TempCleanup *result, int op, const FsChar *path, FsError error) {
    if (result->operation != TEMP_OK) return;
    result->operation = op;
    result->error = error;
    FsError conversion = {0};
    result->path = fs_string(path, &conversion);
}

/**
 * Release a retained descriptor or handle, capturing the first close error.
 *
 * @param handle Native resource to consume, possibly invalid.
 * @return Captured close outcome.
 */
static FsError temp_close(TempHandle handle) {
    if (handle != TEMP_INVALID) {
#if defined(_WIN32)
        if (!CloseHandle(handle)) return fs_native_error();
#else
        if (close(handle) != 0) return fs_native_error();
#endif
    }
    return fs_error(0);
}

/**
 * Keep the first failure encountered while unwinding an unsuccessful creation.
 *
 * @param out Creation report retaining the primary cause.
 * @param op Cleanup operation attempted.
 * @param error Captured cleanup outcome.
 */
static void temp_rollback(TempOpen *out, int op, FsError error) {
    if (!fs_status(error).ok && !out->rollback_operation) {
        out->rollback_operation = op;
        out->rollback = error;
    }
}

#if defined(_WIN32)
#include "dea_rt_temp_windows.h"
#else
#include "dea_rt_temp_posix.h"
#endif

/**
 * Resolve the selected spelling and retain the validated directory.
 *
 * @param selected Borrowed optional explicit parent.
 * @param handle Receives the pinned directory on success.
 * @param error Receives the cause of any selection or inspection failure.
 * @return Owned absolute spelling if available, also on inspection failure.
 */
static FsChar *temp_parent(dea_opt_string selected, TempHandle *handle, FsError *error) {
    FsChar *native = selected.has_value ? fs_path(selected.value, error) : temp_default(error);
    if (!native) return NULL;
    dea_string spelling = fs_string(native, error);
    free(native);
    if (!fs_status(*error).ok) return NULL;
    FsPath absolute = rt_fs_absolute(spelling);
    rt_string_release(spelling);
    if (!absolute.ok) { *error = absolute.error; return NULL; }
    native = fs_path(absolute.value, error);
    rt_string_release(absolute.value);
    if (native) *handle = temp_open_parent(native, error);
    return native;
}

/**
 * Inspect the selected system temporary directory.
 *
 * @return Validated absolute spelling or captured discovery failure.
 */
FsPath rt_temp_parent(void) {
    FsError error = {0};
    TempHandle handle = TEMP_INVALID;
    FsChar *path = temp_parent((dea_opt_string){0}, &handle, &error);
    if (handle != TEMP_INVALID) error = temp_close(handle);
    return fs_path_result(path, error);
}

/**
 * Encode exactly 128 bits of host entropy as a single filename component.
 *
 * @param name Destination for the terminated ASCII component.
 * @return First entropy failure or success.
 */
static FsError temp_name(FsChar name[37]) {
    static const char digits[] = "0123456789abcdef";
    unsigned char bytes[16];
    FileIo fill = rt_entropy_fill(bytes, (dea_int)sizeof(bytes));
    if (fill.state != DEA_IO_OK) return fill.error;
    name[0] = 'd'; name[1] = 'e'; name[2] = 'a'; name[3] = '-';
    for (size_t i = 0; i < sizeof(bytes); ++i) {
        name[4 + 2 * i] = digits[bytes[i] >> 4];
        name[5 + 2 * i] = digits[bytes[i] & 15];
    }
    name[36] = 0;
    return fs_error(0);
}

/**
 * Create an exclusive private object under a trusted directory.
 *
 * All fallible path construction precedes the exclusive create. Only a collision
 * from that operation is retried. An already-open object is never reopened by path
 * to build a public file wrapper.
 *
 * @param parent Explicit directory, or absent for host discovery.
 * @param directory Select a directory instead of a read/write file.
 * @return Owned native state or primary and rollback diagnostics.
 */
TempOpen rt_temp_create(dea_opt_string parent, dea_bool directory) {
    TempOpen out = {0};
    out.path = DEA_STRING_EMPTY;
    out.operation = TEMP_PARENT;
    TempHandle pinned = TEMP_INVALID;
    FsChar *base = temp_parent(parent, &pinned, &out.error);
    if (pinned == TEMP_INVALID) {
        if (parent.has_value) { out.path = parent.value; rt_string_retain(out.path); }
        else if (base) { FsError ignored = {0}; out.path = fs_string(base, &ignored); }
        free(base);
        return out;
    }
    out.operation = TEMP_CREATE;
    TempOwner *owner = rt_alloc((dea_int)sizeof(*owner));
    DeaFile *file = directory ? NULL : rt_alloc((dea_int)sizeof(*file));
    if (!owner || (!directory && !file)) {
        out.error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY);
    } else {
        *owner = (TempOwner){.parent = pinned, .object = TEMP_INVALID, .directory = directory};
        if (file) memset(file, 0, sizeof(*file));
        for (unsigned attempt = 0; attempt < 32; ++attempt) {
            out.operation = TEMP_ENTROPY;
            out.error = temp_name(owner->name);
            if (!fs_status(out.error).ok) break;
            out.operation = TEMP_CREATE;
            owner->path = fs_join(base, owner->name, &out.error);
            if (!owner->path) break;
            out.path = fs_string(owner->path, &out.error);
            if (!fs_status(out.error).ok) break;
            int collision = 0;
            out.error = temp_exclusive(owner, file, &collision, &out);
            if (fs_status(out.error).ok) {
                out.owner = owner;
                out.file_handle = file;
                out.operation = TEMP_OK;
                free(base);
                return out;
            }
            if (!collision || attempt == 31) break;
            free(owner->path);
            owner->path = NULL;
            rt_string_release(out.path);
            out.path = DEA_STRING_EMPTY;
        }
        free(owner->path);
    }
    if (rt_strlen(out.path) == 0) {
        FsError ignored = {0};
        out.path = fs_string(base, &ignored);
    }
    if (owner) rt_free(owner);
    if (file) rt_free(file);
    temp_rollback(&out, TEMP_CLOSE, temp_close(pinned));
    free(base);
    return out;
}

/**
 * Remove the original object and release its native cleanup owner.
 *
 * @param raw Live native cleanup owner to consume exactly once.
 * @return Removed-entry count and any residual failure.
 */
TempCleanup rt_temp_remove(void *raw) {
    TempCleanup out = {0};
    out.path = DEA_STRING_EMPTY;
    TempOwner *owner = _rt_check_ptr_site(NULL, raw, (dea_int)sizeof(TempOwner),
        _RT_ALIGNOF(TempOwner), _RT_ACCESS_WRITE, __FILE__, __LINE__);
    temp_remove_owned(owner, &out);
    FsError object_close = temp_close(owner->object);
    FsError parent_close = temp_close(owner->parent);
    if (!fs_status(object_close).ok) temp_failure(&out, TEMP_CLOSE, owner->path, object_close);
    if (!fs_status(parent_close).ok) temp_failure(&out, TEMP_CLOSE, owner->path, parent_close);
    free(owner->path);
    rt_free(owner);
    return out;
}

#endif
