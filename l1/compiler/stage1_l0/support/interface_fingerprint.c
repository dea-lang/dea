/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/*
 * L1 compiler support linked beside the L0-generated Stage 1 translation
 * unit. The generated unit owns the SipHash implementation. This unit
 * supplies the fixed-key, allocation-free interface-fingerprint ABI plus
 * small compiler-private filesystem operations whose paths cross the FFI as
 * explicit native path byte spans.
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
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#ifndef S_ISVTX
#define S_ISVTX 01000
#endif
#endif

#include "../../shared/runtime/internal/dea_interface_fingerprint.h"

void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    _dea_l1_interface_fingerprint_sip13_hex(data, len, out_hex);
}

/* Return actual-host Darwin identity without consulting CLI test overrides. */
int32_t l1c_fs_host_is_darwin(void) {
#if defined(__APPLE__)
    return 1;
#else
    return 0;
#endif
}

/*
 * Filesystem result conventions
 *
 * Mutations return 1 after changing the filesystem, 0 for the documented
 * benign non-change (a create/rename collision or an already absent
 * directory), and -1 for invalid input or an operating-system error.
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
    L1C_FS_ERROR = -1,
    L1C_FS_ABSENT = 0,
    L1C_FS_REGULAR = 1,
    L1C_FS_DIRECTORY = 2,
    L1C_FS_OTHER = 3
};

static int l1c_fs_raw_path_is_valid(const uint8_t *path, int32_t path_len) {
    return path != NULL &&
           path_len > 0 &&
           memchr(path, '\0', (size_t)path_len) == NULL;
}

static char *l1c_fs_native_path(const uint8_t *path, int32_t path_len) {
    char *native;
    if (!l1c_fs_raw_path_is_valid(path, path_len)) {
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

#if defined(_WIN32)

/*
 * The Stage 1 MinGW runtime uses narrow CRT filesystem and process APIs. Keep
 * this support ABI in that same native byte encoding so classification and
 * mutation address the same paths as read_file, write_file, and system.
 * Directory access control is inherited from the caller-selected parent.
 */
static int32_t l1c_fs_path_kind_native(const char *path, int follow) {
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
            return L1C_FS_ABSENT;
        }
        return L1C_FS_ERROR;
    }
    if (!GetFileInformationByHandle(handle, &info)) {
        CloseHandle(handle);
        return L1C_FS_ERROR;
    }
    if (!CloseHandle(handle)) {
        return L1C_FS_ERROR;
    }

    if ((info.dwFileAttributes &
         (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DEVICE)) != 0) {
        return L1C_FS_OTHER;
    }
    if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
        return L1C_FS_DIRECTORY;
    }
    return L1C_FS_REGULAR;
}

static int32_t l1c_fs_same_file_native(
    const char *left,
    const char *right
) {
    BY_HANDLE_FILE_INFORMATION left_info;
    BY_HANDLE_FILE_INFORMATION right_info;
    DWORD share = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE;
    HANDLE left_handle = CreateFileA(
        left,
        FILE_READ_ATTRIBUTES,
        share,
        NULL,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        NULL
    );
    HANDLE right_handle;
    int32_t result = L1C_FS_ERROR;
    if (left_handle == INVALID_HANDLE_VALUE) {
        return result;
    }
    right_handle = CreateFileA(
        right,
        FILE_READ_ATTRIBUTES,
        share,
        NULL,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        NULL
    );
    if (right_handle != INVALID_HANDLE_VALUE &&
        GetFileInformationByHandle(left_handle, &left_info) &&
        GetFileInformationByHandle(right_handle, &right_info)) {
        result =
            left_info.dwVolumeSerialNumber == right_info.dwVolumeSerialNumber &&
            left_info.nFileIndexHigh == right_info.nFileIndexHigh &&
            left_info.nFileIndexLow == right_info.nFileIndexLow;
    }
    if (right_handle != INVALID_HANDLE_VALUE && !CloseHandle(right_handle)) {
        result = L1C_FS_ERROR;
    }
    if (!CloseHandle(left_handle)) {
        result = L1C_FS_ERROR;
    }
    return result;
}

static char *l1c_fs_canonical_existing_windows(
    const char *path,
    int require_directory
) {
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
    DWORD capacity = MAX_PATH;
    BY_HANDLE_FILE_INFORMATION info;
    char *resolved = NULL;
    DWORD length;
    int attempt;
    if (handle == INVALID_HANDLE_VALUE) {
        return NULL;
    }
    if (require_directory &&
        (!GetFileInformationByHandle(handle, &info) ||
         (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0)) {
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

static char *l1c_fs_canonical_existing_native(const char *path) {
    return l1c_fs_canonical_existing_windows(path, 0);
}

static char *l1c_fs_resolve_temp_parent_native(const char *path) {
    return l1c_fs_canonical_existing_windows(path, 1);
}

#else

static int32_t l1c_fs_path_kind_native(const char *path, int follow) {
    struct stat info;
    int status = follow ? stat(path, &info) : lstat(path, &info);
    if (status == 0) {
        if (S_ISREG(info.st_mode)) {
            return L1C_FS_REGULAR;
        }
        if (S_ISDIR(info.st_mode)) {
            return L1C_FS_DIRECTORY;
        }
        return L1C_FS_OTHER;
    }
    if (errno == ENOENT || errno == ENOTDIR) {
        return L1C_FS_ABSENT;
    }
    return L1C_FS_ERROR;
}

static int32_t l1c_fs_same_file_native(
    const char *left,
    const char *right
) {
    struct stat left_info;
    struct stat right_info;
    if (stat(left, &left_info) != 0 || stat(right, &right_info) != 0) {
        return L1C_FS_ERROR;
    }
    return left_info.st_dev == right_info.st_dev &&
           left_info.st_ino == right_info.st_ino;
}

static int l1c_fs_temp_component_is_trusted(
    const char *path,
    uid_t effective_uid
) {
    struct stat info;
    mode_t writable_mask = (mode_t)(S_IWGRP | S_IWOTH);
    if (stat(path, &info) != 0 || !S_ISDIR(info.st_mode)) {
        return 0;
    }
    if (info.st_uid != (uid_t)0 && info.st_uid != effective_uid) {
        return 0;
    }
    if ((info.st_mode & writable_mask) != 0 &&
        (info.st_mode & (mode_t)S_ISVTX) == 0) {
        return 0;
    }
    return 1;
}

static int l1c_fs_temp_hierarchy_is_trusted(char *resolved) {
    uid_t effective_uid = geteuid();
    char *cursor;
    if (resolved[0] != '/' ||
        !l1c_fs_temp_component_is_trusted("/", effective_uid)) {
        return 0;
    }
    cursor = resolved + 1;
    for (;;) {
        if (*cursor == '/' || *cursor == '\0') {
            char saved = *cursor;
            *cursor = '\0';
            if (resolved[1] != '\0' &&
                !l1c_fs_temp_component_is_trusted(
                    resolved, effective_uid)) {
                *cursor = saved;
                return 0;
            }
            *cursor = saved;
            if (saved == '\0') {
                break;
            }
        }
        ++cursor;
    }
    return 1;
}

static char *l1c_fs_canonical_existing_native(const char *path) {
    return realpath(path, NULL);
}

static char *l1c_fs_resolve_temp_parent_native(const char *path) {
    char *resolved = l1c_fs_canonical_existing_native(path);
    if (resolved == NULL) {
        return NULL;
    }
    if (!l1c_fs_temp_hierarchy_is_trusted(resolved)) {
        free(resolved);
        return NULL;
    }
    return resolved;
}

#endif

static char *l1c_fs_join_search_component(
    const char *component,
    size_t component_len,
    const char *name,
    char separator
) {
    size_t name_len = strlen(name);
    int needs_separator =
        component_len > 0 &&
        component[component_len - 1] != separator &&
        (separator != '\\' || component[component_len - 1] != '/');
    size_t total;
    char *joined;
    if (component_len > SIZE_MAX - name_len - (size_t)needs_separator - 1) {
        return NULL;
    }
    total = component_len + (size_t)needs_separator + name_len;
    joined = (char *)malloc(total + 1);
    if (joined == NULL) {
        return NULL;
    }
    memcpy(joined, component, component_len);
    if (needs_separator) {
        joined[component_len] = separator;
    }
    memcpy(
        joined + component_len + (size_t)needs_separator,
        name,
        name_len + 1
    );
    return joined;
}

#if defined(_WIN32)

static char *l1c_fs_windows_absolute_regular(const char *candidate) {
    DWORD required;
    DWORD actual;
    char *absolute;
    if (l1c_fs_path_kind_native(candidate, 1) != L1C_FS_REGULAR) {
        return NULL;
    }
    required = GetFullPathNameA(candidate, 0, NULL, NULL);
    if (required == 0) {
        return NULL;
    }
    absolute = (char *)malloc((size_t)required);
    if (absolute == NULL) {
        return NULL;
    }
    actual = GetFullPathNameA(candidate, required, absolute, NULL);
    if (actual == 0 || actual >= required) {
        free(absolute);
        return NULL;
    }
    return absolute;
}

static char *l1c_fs_windows_append_extension(
    const char *candidate,
    const char *extension,
    size_t extension_len
) {
    size_t candidate_len = strlen(candidate);
    char *extended;
    if (candidate_len > SIZE_MAX - extension_len - 1) {
        return NULL;
    }
    extended = (char *)malloc(candidate_len + extension_len + 1);
    if (extended == NULL) {
        return NULL;
    }
    memcpy(extended, candidate, candidate_len);
    memcpy(extended + candidate_len, extension, extension_len);
    extended[candidate_len + extension_len] = '\0';
    return extended;
}

static int l1c_fs_windows_basename_has_extension(const char *candidate) {
    const char *base = candidate;
    const char *slash = strrchr(candidate, '/');
    const char *backslash = strrchr(candidate, '\\');
    if (slash != NULL) {
        base = slash + 1;
    }
    if (backslash != NULL && backslash + 1 > base) {
        base = backslash + 1;
    }
    return strrchr(base, '.') != NULL;
}

static char *l1c_fs_windows_try_executable(const char *candidate) {
    const char *pathext;
    const char *cursor;
    char *resolved;
    if (l1c_fs_windows_basename_has_extension(candidate)) {
        return l1c_fs_windows_absolute_regular(candidate);
    }

    pathext = getenv("PATHEXT");
    if (pathext == NULL) {
        pathext = ".COM;.EXE;.BAT;.CMD";
    }
    cursor = pathext;
    for (;;) {
        const char *delimiter = strchr(cursor, ';');
        size_t extension_len = delimiter == NULL
            ? strlen(cursor)
            : (size_t)(delimiter - cursor);
        if (extension_len > 0) {
            char *extended = l1c_fs_windows_append_extension(
                candidate, cursor, extension_len);
            if (extended == NULL) {
                return NULL;
            }
            resolved = l1c_fs_windows_absolute_regular(extended);
            free(extended);
            if (resolved != NULL) {
                return resolved;
            }
        }
        if (delimiter == NULL) {
            break;
        }
        cursor = delimiter + 1;
    }
    return NULL;
}

static char *l1c_fs_resolve_executable_native(const char *name) {
    const char *path;
    const char *cursor;
    char *resolved;
    if (strchr(name, '/') != NULL || strchr(name, '\\') != NULL) {
        return NULL;
    }

    if (NeedCurrentDirectoryForExePathA(name)) {
        resolved = l1c_fs_windows_try_executable(name);
        if (resolved != NULL) {
            return resolved;
        }
    }
    path = getenv("PATH");
    if (path == NULL) {
        return NULL;
    }
    cursor = path;
    for (;;) {
        const char *delimiter = strchr(cursor, ';');
        size_t component_len = delimiter == NULL
            ? strlen(cursor)
            : (size_t)(delimiter - cursor);
        char *candidate = l1c_fs_join_search_component(
            cursor, component_len, name, '\\');
        if (candidate == NULL) {
            return NULL;
        }
        resolved = l1c_fs_windows_try_executable(candidate);
        free(candidate);
        if (resolved != NULL) {
            return resolved;
        }
        if (delimiter == NULL) {
            break;
        }
        cursor = delimiter + 1;
    }
    return NULL;
}

#else

static char *l1c_fs_default_exec_path(void) {
    size_t required = confstr(_CS_PATH, NULL, 0);
    char *path;
    if (required == 0) {
        return NULL;
    }
    path = (char *)malloc(required);
    if (path == NULL || confstr(_CS_PATH, path, required) == 0) {
        free(path);
        return NULL;
    }
    return path;
}

static char *l1c_fs_posix_absolute_spelling(const char *path) {
    char *cwd;
    char *absolute;
    if (path[0] == '/') {
        return strdup(path);
    }
    cwd = getcwd(NULL, 0);
    if (cwd == NULL) {
        return NULL;
    }
    absolute = l1c_fs_join_search_component(
        cwd, strlen(cwd), path, '/');
    free(cwd);
    return absolute;
}

static char *l1c_fs_resolve_executable_native(const char *name) {
    const char *configured_path;
    const char *cursor;
    char *default_path = NULL;
    if (strchr(name, '/') != NULL) {
        return NULL;
    }

    configured_path = getenv("PATH");
    if (configured_path == NULL) {
        default_path = l1c_fs_default_exec_path();
        configured_path = default_path;
    }
    if (configured_path == NULL) {
        return NULL;
    }

    cursor = configured_path;
    for (;;) {
        const char *delimiter = strchr(cursor, ':');
        size_t component_len = delimiter == NULL
            ? strlen(cursor)
            : (size_t)(delimiter - cursor);
        char *candidate = l1c_fs_join_search_component(
            cursor, component_len, name, '/');
        if (candidate == NULL) {
            free(default_path);
            return NULL;
        }
        if (l1c_fs_path_kind_native(candidate, 1) == L1C_FS_REGULAR &&
            access(candidate, X_OK) == 0) {
            char *resolved = l1c_fs_posix_absolute_spelling(candidate);
            free(candidate);
            free(default_path);
            return resolved;
        }
        free(candidate);
        if (delimiter == NULL) {
            break;
        }
        cursor = delimiter + 1;
    }
    free(default_path);
    return NULL;
}

#endif

static int32_t l1c_fs_path_kind(
    const uint8_t *path,
    int32_t path_len,
    int follow
) {
    char *native = l1c_fs_native_path(path, path_len);
    int32_t result;
    if (native == NULL) {
        return L1C_FS_ERROR;
    }
    result = l1c_fs_path_kind_native(native, follow);
    free(native);
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
int32_t l1c_fs_mkdir(
    const uint8_t *path,
    int32_t path_len,
    int32_t mode
) {
    if (mode < 0 || (mode & ~07777) != 0) {
        return L1C_FS_ERROR;
    }

#if defined(_WIN32)
    char *native = l1c_fs_native_path(path, path_len);
    int32_t result = L1C_FS_ERROR;
    if (native == NULL) {
        return result;
    }
    if (CreateDirectoryA(native, NULL)) {
        result = 1;
    } else {
        DWORD error = GetLastError();
        if (error == ERROR_ALREADY_EXISTS || error == ERROR_FILE_EXISTS) {
            result = 0;
        }
    }
    free(native);
    return result;
#else
    char *native = l1c_fs_native_path(path, path_len);
    int32_t result = L1C_FS_ERROR;
    if (native == NULL) {
        return result;
    }
    if (mkdir(native, (mode_t)mode) == 0) {
        result = 1;
    } else if (errno == EEXIST) {
        result = 0;
    }
    free(native);
    return result;
#endif
}

/**
 * Classify one path without following symbolic links or reparse points.
 *
 * @return -1 on error, 0 if absent, 1 for a regular file, 2 for a directory,
 *     or 3 for another filesystem object.
 */
int32_t l1c_fs_path_kind_nofollow(
    const uint8_t *path,
    int32_t path_len
) {
    return l1c_fs_path_kind(path, path_len, 0);
}

/**
 * Classify one path after following symbolic links or reparse points.
 *
 * @return -1 on error, 0 if absent or dangling, 1 for a regular file, 2 for a
 *     directory, or 3 for another filesystem object.
 */
int32_t l1c_fs_path_kind_follow(
    const uint8_t *path,
    int32_t path_len
) {
    return l1c_fs_path_kind(path, path_len, 1);
}

/**
 * Join one parent path and fixed child name using actual-host separators.
 *
 * The inserted separator remains `/`, matching the compiler's previous
 * lexical join behavior and Win32 API support. POSIX recognizes only `/` as
 * an existing trailing separator; Windows recognizes both `/` and `\\`.
 *
 * The return value is the joined byte length without a trailing NUL. When
 * `output` is null or too small, no bytes are copied and the required length
 * is still returned.
 *
 * @return Positive joined byte length, or -1 on invalid input/overflow.
 */
int32_t l1c_fs_join_child(
    const uint8_t *parent,
    int32_t parent_len,
    const uint8_t *child,
    int32_t child_len,
    uint8_t *output,
    int32_t output_capacity
) {
    int add_separator;
    size_t length;
    size_t cursor;
    if (!l1c_fs_raw_path_is_valid(parent, parent_len) ||
        !l1c_fs_raw_path_is_valid(child, child_len) ||
        output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        return L1C_FS_ERROR;
    }
#if defined(_WIN32)
    add_separator =
        parent[parent_len - 1] != (uint8_t)'/' &&
        parent[parent_len - 1] != (uint8_t)'\\';
#else
    add_separator = parent[parent_len - 1] != (uint8_t)'/';
#endif
    if (parent_len > INT32_MAX - child_len - add_separator) {
        return L1C_FS_ERROR;
    }
    length = (size_t)parent_len + (size_t)child_len +
        (size_t)add_separator;
    if (output != NULL && output_capacity >= (int32_t)length) {
        memcpy(output, parent, (size_t)parent_len);
        cursor = (size_t)parent_len;
        if (add_separator) {
            output[cursor] = (uint8_t)'/';
            ++cursor;
        }
        memcpy(output + cursor, child, (size_t)child_len);
    }
    return (int32_t)length;
}

/**
 * Compare the followed filesystem identities of two existing paths.
 *
 * @return 1 when both names address the same file, 0 when distinct, or -1 on
 *     invalid input or an operating-system error.
 */
int32_t l1c_fs_same_file(
    const uint8_t *left,
    int32_t left_len,
    const uint8_t *right,
    int32_t right_len
) {
    char *left_native = l1c_fs_native_path(left, left_len);
    char *right_native = l1c_fs_native_path(right, right_len);
    int32_t result = L1C_FS_ERROR;
    if (left_native != NULL && right_native != NULL) {
        result = l1c_fs_same_file_native(left_native, right_native);
    }
    free(left_native);
    free(right_native);
    return result;
}

/**
 * Resolve and validate one selected compiler temporary parent.
 *
 * POSIX validates every component of the canonical hierarchy from the
 * filesystem root: each directory must be owned by root or the effective
 * user, and group- or other-writable directories must carry the sticky bit.
 * Windows canonicalizes the selected directory and relies on the documented
 * trusted-parent ACL assumption.
 *
 * The return value is the canonical byte length excluding a trailing NUL.
 * When `output` is null or too small, no bytes are copied and the required
 * length is still returned so the caller can allocate and retry.
 *
 * @return Positive canonical byte length, or -1 on validation/error.
 */
int32_t l1c_fs_resolve_trusted_temp_parent(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
) {
    char *native = l1c_fs_native_path(path, path_len);
    char *resolved;
    size_t length;
    int32_t result;
    if (native == NULL || output_capacity < 0) {
        free(native);
        return L1C_FS_ERROR;
    }
    resolved = l1c_fs_resolve_temp_parent_native(native);
    free(native);
    if (resolved == NULL) {
        return L1C_FS_ERROR;
    }
    length = strlen(resolved);
    if (length == 0 || length > (size_t)INT32_MAX) {
        free(resolved);
        return L1C_FS_ERROR;
    }
    result = (int32_t)length;
    if (output != NULL && output_capacity >= result) {
        memcpy(output, resolved, length);
    }
    free(resolved);
    return result;
}

/**
 * Resolve one path against the process current working directory.
 *
 * The path need not exist. The result is intended only to preserve the
 * invocation-directory meaning of a compiler or include path while a driver
 * runs the host compiler from private staging.
 *
 * @return Positive absolute byte length, or -1 on validation/error.
 */
int32_t l1c_fs_absolute_path(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
) {
    char *native = l1c_fs_native_path(path, path_len);
    char *absolute = NULL;
    size_t length;
    int32_t result;
    if (native == NULL || output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        free(native);
        return L1C_FS_ERROR;
    }

#if defined(_WIN32)
    {
        DWORD required = GetFullPathNameA(native, 0, NULL, NULL);
        if (required > 0) {
            absolute = (char *)malloc((size_t)required);
            if (absolute != NULL &&
                (GetFullPathNameA(native, required, absolute, NULL) == 0 ||
                 strlen(absolute) >= (size_t)required)) {
                free(absolute);
                absolute = NULL;
            }
        }
    }
#else
    if (native[0] == '/') {
        absolute = strdup(native);
    } else {
        char *cwd = getcwd(NULL, 0);
        if (cwd != NULL) {
            size_t cwd_len = strlen(cwd);
            size_t native_len = strlen(native);
            if (cwd_len <= SIZE_MAX - native_len - 2) {
                absolute = (char *)malloc(cwd_len + native_len + 2);
                if (absolute != NULL) {
                    memcpy(absolute, cwd, cwd_len);
                    absolute[cwd_len] = '/';
                    memcpy(absolute + cwd_len + 1, native, native_len + 1);
                }
            }
            free(cwd);
        }
    }
#endif

    free(native);
    if (absolute == NULL) {
        return L1C_FS_ERROR;
    }
    length = strlen(absolute);
    if (length == 0 || length > (size_t)INT32_MAX) {
        free(absolute);
        return L1C_FS_ERROR;
    }
    result = (int32_t)length;
    if (output != NULL && output_capacity >= result) {
        memcpy(output, absolute, length);
    }
    free(absolute);
    return result;
}

/**
 * Resolve one existing path through filesystem aliases.
 *
 * This canonical spelling is used only to classify a selected compiler. The
 * driver still invokes the executable through its originally selected alias
 * so argv[0]-sensitive compiler behavior is preserved.
 *
 * @return Positive canonical byte length, or -1 on validation/error.
 */
int32_t l1c_fs_canonical_existing_path(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
) {
    char *native = l1c_fs_native_path(path, path_len);
    char *resolved = NULL;
    size_t length;
    int32_t result;
    if (native == NULL || output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        free(native);
        return L1C_FS_ERROR;
    }
    resolved = l1c_fs_canonical_existing_native(native);
    free(native);
    if (resolved == NULL) {
        return L1C_FS_ERROR;
    }
    length = strlen(resolved);
    if (length == 0 || length > (size_t)INT32_MAX) {
        free(resolved);
        return L1C_FS_ERROR;
    }
    result = (int32_t)length;
    if (output != NULL && output_capacity >= result) {
        memcpy(output, resolved, length);
    }
    free(resolved);
    return result;
}

/**
 * Resolve one bare executable name through the process PATH.
 *
 * Empty and relative PATH components retain their meaning in the current
 * invocation directory. The returned path is absolute so a later working-
 * directory change cannot select a different executable, but the selected
 * executable's alias spelling is retained for argv[0]-sensitive drivers.
 *
 * @return Positive absolute byte length, or -1 when no executable is found.
 */
int32_t l1c_fs_resolve_executable(
    const uint8_t *name,
    int32_t name_len,
    uint8_t *output,
    int32_t output_capacity
) {
    char *native = l1c_fs_native_path(name, name_len);
    char *resolved = NULL;
    size_t length;
    int32_t result;
    if (native == NULL || output_capacity < 0 ||
        (output == NULL && output_capacity != 0)) {
        free(native);
        return L1C_FS_ERROR;
    }
    resolved = l1c_fs_resolve_executable_native(native);
    free(native);
    if (resolved == NULL) {
        return L1C_FS_ERROR;
    }
    length = strlen(resolved);
    if (length == 0 || length > (size_t)INT32_MAX) {
        free(resolved);
        return L1C_FS_ERROR;
    }
    result = (int32_t)length;
    if (output != NULL && output_capacity >= result) {
        memcpy(output, resolved, length);
    }
    free(resolved);
    return result;
}

/**
 * Move one regular file to an absent destination on the same filesystem.
 *
 * The destination must be absent. POSIX checks that condition before a true
 * `rename`; the compile transaction's trusted-parent and single-writer
 * assumptions exclude a competing creator between those operations. Win32
 * `MoveFileExA` without replacement flags enforces the absent-destination
 * condition itself. Directories and non-regular source objects are rejected.
 *
 * @return 1 after the move, 0 when the destination exists, or -1 on error.
 */
int32_t l1c_fs_rename_absent(
    const uint8_t *source,
    int32_t source_len,
    const uint8_t *destination,
    int32_t destination_len
) {
#if defined(_WIN32)
    char *source_native = l1c_fs_native_path(source, source_len);
    char *destination_native =
        l1c_fs_native_path(destination, destination_len);
    int32_t result = L1C_FS_ERROR;
    if (source_native == NULL || destination_native == NULL) {
        free(source_native);
        free(destination_native);
        return result;
    }
    if (l1c_fs_path_kind_native(source_native, 0) != L1C_FS_REGULAR) {
        free(source_native);
        free(destination_native);
        return result;
    }
    if (MoveFileExA(source_native, destination_native, 0)) {
        result = 1;
    } else {
        DWORD error = GetLastError();
        if (error == ERROR_ALREADY_EXISTS || error == ERROR_FILE_EXISTS) {
            result = 0;
        }
    }
    free(source_native);
    free(destination_native);
    return result;
#else
    char *source_native = l1c_fs_native_path(source, source_len);
    char *destination_native =
        l1c_fs_native_path(destination, destination_len);
    struct stat source_info;
    struct stat destination_info;
    int32_t result = L1C_FS_ERROR;
    if (source_native == NULL || destination_native == NULL) {
        free(source_native);
        free(destination_native);
        return result;
    }
    if (lstat(source_native, &source_info) != 0 ||
        !S_ISREG(source_info.st_mode)) {
        free(source_native);
        free(destination_native);
        return result;
    }
    if (lstat(destination_native, &destination_info) == 0) {
        result = 0;
    } else if (errno == ENOENT &&
               rename(source_native, destination_native) == 0) {
        result = 1;
    }
    free(source_native);
    free(destination_native);
    return result;
#endif
}

/**
 * Remove one regular file without accepting a symbolic link/reparse point.
 *
 * @return 1 after removal, 0 when the path is absent, or -1 on error.
 */
int32_t l1c_fs_remove_regular_file(
    const uint8_t *path,
    int32_t path_len
) {
#if defined(_WIN32)
    char *native = l1c_fs_native_path(path, path_len);
    int32_t result = L1C_FS_ERROR;
    int32_t kind;
    if (native == NULL) {
        return result;
    }
    kind = l1c_fs_path_kind_native(native, 0);
    if (kind == L1C_FS_ABSENT) {
        result = 0;
    } else if (kind == L1C_FS_REGULAR) {
        if (DeleteFileA(native)) {
            result = 1;
        } else {
            DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND ||
                error == ERROR_PATH_NOT_FOUND) {
                result = 0;
            }
        }
    }
    free(native);
    return result;
#else
    char *native = l1c_fs_native_path(path, path_len);
    struct stat info;
    int32_t result = L1C_FS_ERROR;
    if (native == NULL) {
        return result;
    }
    if (lstat(native, &info) != 0) {
        if (errno == ENOENT) {
            result = 0;
        }
    } else if (S_ISREG(info.st_mode)) {
        if (unlink(native) == 0) {
            result = 1;
        } else if (errno == ENOENT) {
            result = 0;
        }
    }
    free(native);
    return result;
#endif
}

/**
 * Remove one empty real directory without accepting a symlink/reparse point.
 *
 * @return 1 after removal, 0 when the path is absent, or -1 on error.
 */
int32_t l1c_fs_remove_empty_dir(
    const uint8_t *path,
    int32_t path_len
) {
#if defined(_WIN32)
    char *native = l1c_fs_native_path(path, path_len);
    int32_t result = L1C_FS_ERROR;
    int32_t kind;
    if (native == NULL) {
        return result;
    }
    kind = l1c_fs_path_kind_native(native, 0);
    if (kind == L1C_FS_ABSENT) {
        result = 0;
    } else if (kind == L1C_FS_DIRECTORY) {
        if (RemoveDirectoryA(native)) {
            result = 1;
        } else {
            DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND ||
                error == ERROR_PATH_NOT_FOUND) {
                result = 0;
            }
        }
    }
    free(native);
    return result;
#else
    char *native = l1c_fs_native_path(path, path_len);
    struct stat info;
    int32_t result = L1C_FS_ERROR;
    if (native == NULL) {
        return result;
    }
    if (lstat(native, &info) != 0) {
        if (errno == ENOENT) {
            result = 0;
        }
    } else if (S_ISDIR(info.st_mode)) {
        if (rmdir(native) == 0) {
            result = 1;
        } else if (errno == ENOENT) {
            result = 0;
        }
    }
    free(native);
    return result;
#endif
}

static void l1c_process_free_words(char **words, int32_t count) {
    int32_t i;
    if (words == NULL) {
        return;
    }
    for (i = 0; i < count; i += 1) {
        free(words[i]);
    }
    free(words);
}

static char **l1c_process_copy_words(
    const uint8_t *const *words,
    const int32_t *lengths,
    int32_t count
) {
    char **copied;
    int32_t i;
    if (words == NULL || lengths == NULL || count <= 0) {
        return NULL;
    }
    copied = (char **)calloc((size_t)count + 1u, sizeof(char *));
    if (copied == NULL) {
        return NULL;
    }
    for (i = 0; i < count; i += 1) {
        if (words[i] == NULL || lengths[i] < 0 ||
            memchr(words[i], '\0', (size_t)lengths[i]) != NULL) {
            l1c_process_free_words(copied, count);
            return NULL;
        }
        copied[i] = (char *)malloc((size_t)lengths[i] + 1u);
        if (copied[i] == NULL) {
            l1c_process_free_words(copied, count);
            return NULL;
        }
        memcpy(copied[i], words[i], (size_t)lengths[i]);
        copied[i][lengths[i]] = '\0';
    }
    return copied;
}

#if defined(_WIN32)
static int l1c_process_append_char(
    char **buffer,
    size_t *length,
    size_t *capacity,
    char value
) {
    if (*length + 1u >= *capacity) {
        size_t next = *capacity == 0u ? 64u : *capacity * 2u;
        char *grown = (char *)realloc(*buffer, next);
        if (grown == NULL) {
            return 0;
        }
        *buffer = grown;
        *capacity = next;
    }
    (*buffer)[*length] = value;
    *length += 1u;
    return 1;
}

static int l1c_process_append_quoted_word(
    char **buffer,
    size_t *length,
    size_t *capacity,
    const char *word
) {
    size_t i;
    size_t slashes = 0u;
    if (!l1c_process_append_char(buffer, length, capacity, '"')) {
        return 0;
    }
    for (i = 0u; word[i] != '\0'; i += 1u) {
        size_t slash_i;
        if (word[i] == '\\') {
            slashes += 1u;
            continue;
        }
        if (word[i] == '"') {
            for (slash_i = 0u; slash_i < slashes * 2u + 1u;
                 slash_i += 1u) {
                if (!l1c_process_append_char(
                        buffer, length, capacity, '\\')) {
                    return 0;
                }
            }
        } else {
            for (slash_i = 0u; slash_i < slashes; slash_i += 1u) {
                if (!l1c_process_append_char(
                        buffer, length, capacity, '\\')) {
                    return 0;
                }
            }
        }
        slashes = 0u;
        if (!l1c_process_append_char(
                buffer, length, capacity, word[i])) {
            return 0;
        }
    }
    for (i = 0u; i < slashes * 2u; i += 1u) {
        if (!l1c_process_append_char(buffer, length, capacity, '\\')) {
            return 0;
        }
    }
    return l1c_process_append_char(buffer, length, capacity, '"');
}

static char *l1c_process_windows_command_line(
    char **words,
    int32_t count
) {
    char *buffer = NULL;
    size_t length = 0u;
    size_t capacity = 0u;
    int32_t i;
    for (i = 0; i < count; i += 1) {
        if (i > 0 && !l1c_process_append_char(
                &buffer, &length, &capacity, ' ')) {
            free(buffer);
            return NULL;
        }
        if (!l1c_process_append_quoted_word(
                &buffer, &length, &capacity, words[i])) {
            free(buffer);
            return NULL;
        }
    }
    if (!l1c_process_append_char(
            &buffer, &length, &capacity, '\0')) {
        free(buffer);
        return NULL;
    }
    return buffer;
}
#endif

/**
 * Launch one exact executable/argument vector and wait for its status.
 *
 * @return 1 after launch and wait, 0 when the executable could not be
 * launched, or -1 for invalid input and process-management failures.
 */
int32_t l1c_process_run(
    const uint8_t *const *words,
    const int32_t *lengths,
    int32_t count,
    int32_t *status_out
) {
    char **argv;
    if (status_out == NULL) {
        return -1;
    }
    argv = l1c_process_copy_words(words, lengths, count);
    if (argv == NULL || argv[0][0] == '\0') {
        l1c_process_free_words(argv, count);
        return -1;
    }

#if defined(_WIN32)
    {
        STARTUPINFOA startup;
        PROCESS_INFORMATION process;
        DWORD child_status;
        char *command_line = l1c_process_windows_command_line(argv, count);
        BOOL created;
        if (command_line == NULL) {
            l1c_process_free_words(argv, count);
            return -1;
        }
        memset(&startup, 0, sizeof(startup));
        memset(&process, 0, sizeof(process));
        startup.cb = sizeof(startup);
        created = CreateProcessA(
            argv[0], command_line, NULL, NULL, TRUE, 0, NULL, NULL,
            &startup, &process);
        free(command_line);
        if (!created) {
            l1c_process_free_words(argv, count);
            return 0;
        }
        if (WaitForSingleObject(process.hProcess, INFINITE) != WAIT_OBJECT_0 ||
            !GetExitCodeProcess(process.hProcess, &child_status)) {
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            l1c_process_free_words(argv, count);
            return -1;
        }
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        *status_out = (int32_t)child_status;
    }
#else
    {
        int exec_pipe[2];
        int child_status;
        int exec_error = 0;
        ssize_t read_count;
        pid_t child;
        pid_t waited;
        if (pipe(exec_pipe) != 0) {
            l1c_process_free_words(argv, count);
            return -1;
        }
        if (fcntl(exec_pipe[1], F_SETFD, FD_CLOEXEC) == -1) {
            close(exec_pipe[0]);
            close(exec_pipe[1]);
            l1c_process_free_words(argv, count);
            return -1;
        }
        child = fork();
        if (child < 0) {
            close(exec_pipe[0]);
            close(exec_pipe[1]);
            l1c_process_free_words(argv, count);
            return -1;
        }
        if (child == 0) {
            close(exec_pipe[0]);
            execv(argv[0], argv);
            exec_error = errno;
            while (write(exec_pipe[1], &exec_error,
                         sizeof(exec_error)) < 0 && errno == EINTR) {
            }
            _exit(127);
        }
        close(exec_pipe[1]);
        do {
            read_count = read(exec_pipe[0], &exec_error,
                              sizeof(exec_error));
        } while (read_count < 0 && errno == EINTR);
        close(exec_pipe[0]);
        do {
            waited = waitpid(child, &child_status, 0);
        } while (waited < 0 && errno == EINTR);
        if (waited < 0) {
            l1c_process_free_words(argv, count);
            return -1;
        }
        if (read_count > 0) {
            l1c_process_free_words(argv, count);
            return 0;
        }
        if (read_count < 0) {
            l1c_process_free_words(argv, count);
            return -1;
        }
        if (WIFEXITED(child_status)) {
            *status_out = (int32_t)WEXITSTATUS(child_status);
        } else if (WIFSIGNALED(child_status)) {
            *status_out = (int32_t)(128 + WTERMSIG(child_status));
        } else {
            *status_out = (int32_t)child_status;
        }
    }
#endif

    l1c_process_free_words(argv, count);
    return 1;
}
