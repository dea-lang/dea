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

#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
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
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#endif

#include "../../shared/runtime/internal/dea_interface_fingerprint.h"

void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    _dea_l1_interface_fingerprint_sip13_hex(data, len, out_hex);
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
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
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
    if (errno == ENOENT) {
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
