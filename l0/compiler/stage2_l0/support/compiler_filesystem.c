/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/*
 * Compiler-private filesystem primitives for the L0 Stage 2 driver.
 *
 * Paths cross the FFI as explicit native byte spans. Workspace policy stays
 * in compiler_filesystem.l0; this translation unit only performs bounded
 * actual-host filesystem operations.
 */

#if !defined(_WIN32)
#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 700
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#endif

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <direct.h>
#include <windows.h>
#else
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#ifndef S_ISVTX
#define S_ISVTX 01000
#endif
#endif

/*
 * Filesystem result conventions
 *
 * Mutations return 1 after changing the filesystem, 0 for the documented
 * benign non-change (a create collision or an already absent object), and -1
 * for invalid input or an operating-system error.
 *
 * Path classification returns:
 *   -1  invalid input or operating-system error
 *    0  absent
 *    1  regular file
 *    2  directory
 *    3  another filesystem object; no-follow mode includes symbolic links and
 *       reparse points in this category
 */
enum {
    L0C_FS_ERROR = -1,
    L0C_FS_ABSENT = 0,
    L0C_FS_REGULAR = 1,
    L0C_FS_DIRECTORY = 2,
    L0C_FS_OTHER = 3
};

static int l0c_fs_raw_path_is_valid(
    const uint8_t *path,
    int32_t path_len
) {
    return path != NULL &&
           path_len > 0 &&
           memchr(path, '\0', (size_t)path_len) == NULL;
}

static char *l0c_fs_native_path(
    const uint8_t *path,
    int32_t path_len
) {
    char *native;
    if (!l0c_fs_raw_path_is_valid(path, path_len)) {
        return NULL;
    }
    native = (char *)malloc((size_t)path_len + 1);
    if (native == NULL) {
        return NULL;
    }
    memcpy(native, path, (size_t)path_len);
    native[path_len] = '\0';
    return native;
}

/**
 * Join one trusted parent path and one internal child name.
 *
 * POSIX treats only `/` as a separator, so a trailing `\` remains a literal
 * parent-name byte and receives an inserted `/`. Windows preserves the
 * repository's existing behavior by accepting either `/` or `\` as the
 * parent's trailing separator. The inserted separator is `/` on both hosts.
 *
 * Calling with `output == NULL` and zero capacity queries the required byte
 * length. A sufficiently large non-null buffer receives the exact bytes
 * without a trailing NUL.
 *
 * @return Required byte length, or -1 on invalid input or overflow.
 */
int32_t l0c_fs_join_child(
    const uint8_t *parent,
    int32_t parent_len,
    const uint8_t *child,
    int32_t child_len,
    uint8_t *output,
    int32_t output_capacity
) {
    int add_separator;
    size_t required;
    size_t offset;

    if (!l0c_fs_raw_path_is_valid(parent, parent_len) ||
        !l0c_fs_raw_path_is_valid(child, child_len) ||
        output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        return L0C_FS_ERROR;
    }
#if defined(_WIN32)
    add_separator =
        parent[parent_len - 1] != '/' &&
        parent[parent_len - 1] != '\\';
#else
    add_separator = parent[parent_len - 1] != '/';
#endif
    if (parent_len > INT32_MAX - child_len - add_separator) {
        return L0C_FS_ERROR;
    }
    required =
        (size_t)parent_len + (size_t)child_len +
        (size_t)add_separator;
    if (output != NULL && output_capacity >= (int32_t)required) {
        memcpy(output, parent, (size_t)parent_len);
        offset = (size_t)parent_len;
        if (add_separator) {
            output[offset] = '/';
            offset += 1;
        }
        memcpy(output + offset, child, (size_t)child_len);
    }
    return (int32_t)required;
}

#if defined(_WIN32)

/*
 * The Stage 2 MinGW runtime uses narrow CRT filesystem and process APIs. Keep
 * this support ABI in that same native byte encoding so all operations address
 * the same paths. Directory access control is inherited from the selected
 * temporary parent under the documented trusted-ACL assumption.
 */
static int32_t l0c_fs_path_kind_native(const char *path, int follow) {
    BY_HANDLE_FILE_INFORMATION info;
    DWORD flags = FILE_FLAG_BACKUP_SEMANTICS;
    if (!follow) {
        flags |= FILE_FLAG_OPEN_REPARSE_POINT;
    }
    HANDLE handle = CreateFileA(
        path,
        FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        OPEN_EXISTING,
        flags,
        NULL
    );
    if (handle == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND ||
            error == ERROR_PATH_NOT_FOUND ||
            error == ERROR_DIRECTORY) {
            return L0C_FS_ABSENT;
        }
        return L0C_FS_ERROR;
    }
    if (!GetFileInformationByHandle(handle, &info)) {
        CloseHandle(handle);
        return L0C_FS_ERROR;
    }
    if (!CloseHandle(handle)) {
        return L0C_FS_ERROR;
    }

    if ((info.dwFileAttributes &
         (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE)) != 0) {
        return L0C_FS_OTHER;
    }
    if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
        return L0C_FS_DIRECTORY;
    }
    return L0C_FS_REGULAR;
}

static char *l0c_fs_resolve_temp_parent_native(const char *path) {
    DWORD share = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE;
    HANDLE handle = CreateFileA(
        path,
        FILE_READ_ATTRIBUTES,
        share,
        NULL,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        NULL
    );
    BY_HANDLE_FILE_INFORMATION info;
    DWORD capacity = MAX_PATH;
    char *resolved = NULL;
    DWORD length;
    int attempt;
    if (handle == INVALID_HANDLE_VALUE) {
        return NULL;
    }
    if (!GetFileInformationByHandle(handle, &info) ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0) {
        CloseHandle(handle);
        return NULL;
    }
    for (attempt = 0; attempt < 4; ++attempt) {
        resolved = (char *)malloc((size_t)capacity);
        if (resolved == NULL) {
            break;
        }
        length = GetFinalPathNameByHandleA(
            handle,
            resolved,
            capacity,
            FILE_NAME_NORMALIZED | VOLUME_NAME_DOS
        );
        if (length == 0) {
            free(resolved);
            resolved = NULL;
            break;
        }
        if (length < capacity) {
            break;
        }
        free(resolved);
        resolved = NULL;
        capacity = length;
    }
    if (!CloseHandle(handle) || resolved == NULL) {
        free(resolved);
        return NULL;
    }
    if (length >= 8 && memcmp(resolved, "\\\\?\\UNC\\", 8) == 0) {
        memmove(resolved + 2, resolved + 8, (size_t)length - 7);
        resolved[0] = '\\';
        resolved[1] = '\\';
    } else if (length >= 4 && memcmp(resolved, "\\\\?\\", 4) == 0) {
        memmove(resolved, resolved + 4, (size_t)length - 3);
    }
    return resolved;
}

#else

static int32_t l0c_fs_path_kind_native(const char *path, int follow) {
    struct stat info;
    int status = follow ? stat(path, &info) : lstat(path, &info);
    if (status == 0) {
        if (S_ISREG(info.st_mode)) {
            return L0C_FS_REGULAR;
        }
        if (S_ISDIR(info.st_mode)) {
            return L0C_FS_DIRECTORY;
        }
        return L0C_FS_OTHER;
    }
    if (errno == ENOENT || errno == ENOTDIR) {
        return L0C_FS_ABSENT;
    }
    return L0C_FS_ERROR;
}

static int l0c_fs_posix_component_is_trusted(
    const char *path,
    uid_t effective_uid
) {
    struct stat info;
    if (stat(path, &info) != 0 || !S_ISDIR(info.st_mode)) {
        return 0;
    }
    if (info.st_uid != (uid_t)0 && info.st_uid != effective_uid) {
        return 0;
    }
    if ((info.st_mode & (S_IWGRP | S_IWOTH)) != 0 &&
        (info.st_mode & S_ISVTX) == 0) {
        return 0;
    }
    return 1;
}

static int l0c_fs_posix_trust_chain_is_valid(char *resolved) {
    size_t len = strlen(resolved);
    uid_t effective_uid = geteuid();
    size_t index;

    if (len == 0 || resolved[0] != '/') {
        return 0;
    }
    if (!l0c_fs_posix_component_is_trusted("/", effective_uid)) {
        return 0;
    }
    if (len == 1) {
        return 1;
    }

    while (len > 1 && resolved[len - 1] == '/') {
        resolved[len - 1] = '\0';
        len -= 1;
    }
    for (index = 1; index <= len; index += 1) {
        if (index == len || resolved[index] == '/') {
            char saved = resolved[index];
            resolved[index] = '\0';
            if (!l0c_fs_posix_component_is_trusted(
                    resolved, effective_uid)) {
                resolved[index] = saved;
                return 0;
            }
            resolved[index] = saved;
        }
    }
    return 1;
}

static char *l0c_fs_resolve_temp_parent_native(const char *path) {
    char *resolved = realpath(path, NULL);
    if (resolved == NULL) {
        return NULL;
    }
    if (!l0c_fs_posix_trust_chain_is_valid(resolved)) {
        free(resolved);
        return NULL;
    }
    return resolved;
}

#endif

/**
 * Resolve and validate one selected compiler temporary parent.
 *
 * Calling with `output == NULL` and zero capacity queries the canonical byte
 * length. When a non-null buffer is large enough, the exact bytes are copied
 * without a trailing NUL. A larger returned length asks the caller to retry.
 *
 * POSIX validates the complete resolved owner/sticky-bit directory chain.
 * Windows uses actual-host lexical canonicalization and the documented
 * trusted-parent ACL assumption.
 *
 * @return Canonical byte length, or -1 on invalid input, trust failure, or an
 *     operating-system error.
 */
int32_t l0c_fs_resolve_trusted_temp_parent(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
) {
    char *native;
    char *resolved;
    size_t resolved_len;
    int32_t result;

    if (output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        return L0C_FS_ERROR;
    }
    native = l0c_fs_native_path(path, path_len);
    if (native == NULL) {
        return L0C_FS_ERROR;
    }
    resolved = l0c_fs_resolve_temp_parent_native(native);
    free(native);
    if (resolved == NULL) {
        return L0C_FS_ERROR;
    }

    resolved_len = strlen(resolved);
    if (resolved_len == 0 || resolved_len > (size_t)INT32_MAX) {
        free(resolved);
        return L0C_FS_ERROR;
    }
    result = (int32_t)resolved_len;
    if (output != NULL && output_capacity >= result) {
        memcpy(output, resolved, resolved_len);
    }
    free(resolved);
    return result;
}

/**
 * Create one directory with collision/error distinction.
 *
 * On POSIX, `mode` must contain only permission/special bits through `07777`
 * and is filtered by the process umask in the conventional way. On MinGW,
 * `mode` is validated but ignored because Win32 directory creation has no
 * POSIX mode.
 *
 * @return 1 after creation, 0 when the path already exists, or -1 on error.
 */
int32_t l0c_fs_mkdir(
    const uint8_t *path,
    int32_t path_len,
    int32_t mode
) {
    char *native;
    int32_t result = L0C_FS_ERROR;
    if (mode < 0 || (mode & ~07777) != 0) {
        return result;
    }
    native = l0c_fs_native_path(path, path_len);
    if (native == NULL) {
        return result;
    }

#if defined(_WIN32)
    if (CreateDirectoryA(native, NULL)) {
        result = 1;
    } else {
        DWORD error = GetLastError();
        if (error == ERROR_ALREADY_EXISTS || error == ERROR_FILE_EXISTS) {
            result = 0;
        }
    }
#else
    if (mkdir(native, (mode_t)mode) == 0) {
        result = 1;
    } else if (errno == EEXIST) {
        result = 0;
    }
#endif

    free(native);
    return result;
}

static int32_t l0c_fs_path_kind(
    const uint8_t *path,
    int32_t path_len,
    int follow
) {
    char *native = l0c_fs_native_path(path, path_len);
    int32_t result;
    if (native == NULL) {
        return L0C_FS_ERROR;
    }
    result = l0c_fs_path_kind_native(native, follow);
    free(native);
    return result;
}

/**
 * Classify one path without following symbolic links or reparse points.
 *
 * @return -1 on error, 0 if absent, 1 for a regular file, 2 for a directory,
 *     or 3 for another filesystem object.
 */
int32_t l0c_fs_path_kind_nofollow(
    const uint8_t *path,
    int32_t path_len
) {
    return l0c_fs_path_kind(path, path_len, 0);
}

/**
 * Classify one path after following symbolic links or reparse points.
 *
 * @return -1 on error, 0 if absent or dangling, 1 for a regular file, 2 for a
 *     directory, or 3 for another filesystem object.
 */
int32_t l0c_fs_path_kind_follow(
    const uint8_t *path,
    int32_t path_len
) {
    return l0c_fs_path_kind(path, path_len, 1);
}

/**
 * Remove one regular file without following a substituted object.
 *
 * @return 1 after removal, 0 when absent, or -1 on invalid input, an
 *     unsupported object kind, or an operating-system error.
 */
int32_t l0c_fs_remove_regular_file(
    const uint8_t *path,
    int32_t path_len
) {
    char *native = l0c_fs_native_path(path, path_len);
    int32_t result = L0C_FS_ERROR;
    int32_t kind;
    if (native == NULL) {
        return result;
    }
    kind = l0c_fs_path_kind_native(native, 0);
    if (kind == L0C_FS_ABSENT) {
        result = 0;
    } else if (kind == L0C_FS_REGULAR) {
#if defined(_WIN32)
        if (DeleteFileA(native)) {
            result = 1;
        } else {
            DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND ||
                error == ERROR_PATH_NOT_FOUND) {
                result = 0;
            }
        }
#else
        if (unlink(native) == 0) {
            result = 1;
        } else if (errno == ENOENT) {
            result = 0;
        }
#endif
    }
    free(native);
    return result;
}

/**
 * Remove one empty real directory without accepting a symlink/reparse point.
 *
 * @return 1 after removal, 0 when absent, or -1 on error.
 */
int32_t l0c_fs_remove_empty_dir(
    const uint8_t *path,
    int32_t path_len
) {
    char *native = l0c_fs_native_path(path, path_len);
    int32_t result = L0C_FS_ERROR;
    int32_t kind;
    if (native == NULL) {
        return result;
    }
    kind = l0c_fs_path_kind_native(native, 0);
    if (kind == L0C_FS_ABSENT) {
        result = 0;
    } else if (kind == L0C_FS_DIRECTORY) {
#if defined(_WIN32)
        if (RemoveDirectoryA(native)) {
            result = 1;
        } else {
            DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND ||
                error == ERROR_PATH_NOT_FOUND) {
                result = 0;
            }
        }
#else
        if (rmdir(native) == 0) {
            result = 1;
        } else if (errno == ENOENT) {
            result = 0;
        }
#endif
    }
    free(native);
    return result;
}
