/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_fs.h
 * Path and directory implementation included only by dea_rt_io.c.
 * Errors are saved before cleanup. Native storage never escapes this boundary.
 */
#ifndef DEA_RT_FS_H
#define DEA_RT_FS_H

#include <limits.h>
#if defined(_WIN32)
#include <windows.h>
#include <wchar.h>
typedef wchar_t FsChar;
#define FS_SEP L'\\'
#else
#include <dirent.h>
#include <fcntl.h>
typedef char FsChar;
#define FS_SEP '/'
#endif

/* Independent host primitive hooks for deterministic failure boundary probes. */
#if !defined(_WIN32)
#ifdef DEA_FS_RENAME
extern int DEA_FS_RENAME(const char *source, const char *destination);
#else
#define DEA_FS_RENAME rename
#endif
#ifdef DEA_FS_CLOSE
extern int DEA_FS_CLOSE(int fd);
#else
#define DEA_FS_CLOSE close
#endif
#ifdef DEA_FS_READDIR
extern struct dirent *DEA_FS_READDIR(DIR *dir);
#else
#define DEA_FS_READDIR readdir
#endif
#ifdef DEA_FS_CLOSEDIR
extern int DEA_FS_CLOSEDIR(DIR *dir);
#else
#define DEA_FS_CLOSEDIR closedir
#endif
#ifdef DEA_FS_READ
extern ssize_t DEA_FS_READ(int fd, void *buffer, size_t size);
#else
#define DEA_FS_READ read
#endif
#ifdef DEA_FS_WRITE
extern ssize_t DEA_FS_WRITE(int fd, const void *buffer, size_t size);
#else
#define DEA_FS_WRITE write
#endif
#endif

typedef struct __deaM3sys2osS9RtOsError FsError;
typedef struct __deaM3sys2fsS10RtFsStatus FsStatus;
typedef struct __deaM3sys2fsS8RtFsBool FsBool;
typedef struct __deaM3sys2fsS8RtFsPath FsPath;
typedef struct __deaM3sys2fsS12RtFsMetadata FsMetadata;
typedef struct __deaM3sys2fsS9RtDirOpen FsDirOpen;
typedef struct __deaM3sys2fsS9RtDirNext FsDirNext;

/** Return a runtime validation error without consulting ambient host state. */
static FsError fs_error(int kind) {
    FsError error = {0};
    error.kind = kind;
    return error;
}

/** Capture the failing host call immediately. */
static FsError fs_native_error(void) {
#if defined(_WIN32)
    return rt_os_error_from_win32((dea_long)GetLastError());
#else
    return rt_os_error_from_errno(errno);
#endif
}

/** Wrap success or a captured failure. */
static FsStatus fs_status(FsError error) {
    FsStatus out = {0};
    out.ok = error.kind == 0 && error.domain == 0 && error.native_code == 0;
    out.error = error;
    return out;
}

/* Pure spelling helpers are shared with portable Windows path regressions. */
#include "dea_rt_fs_path.h"

/** Validate bytes, then produce terminated host storage with no fixed path limit. */
static FsChar *fs_path(dea_string path, FsError *error) {
    dea_int len = rt_strlen(path);
    const char *bytes = _rt_string_bytes(path);
    if (len <= 0 || memchr(bytes, 0, (size_t)len) != NULL) {
        *error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
        return NULL;
    }
#if defined(_WIN32)
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes, len, NULL, 0);
    wchar_t *out;
    if (count == 0) { *error = fs_native_error(); return NULL; }
    out = (wchar_t *)malloc(((size_t)count + 1) * sizeof(wchar_t));
    if (out == NULL) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes, len, out, count)) {
        *error = fs_native_error(); free(out); return NULL;
    }
    out[count] = 0;
#else
    char *out = (char *)malloc((size_t)len + 1);
    if (out == NULL) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
    memcpy(out, bytes, (size_t)len);
    out[len] = 0;
#endif
    return out;
}

/** Copy native output to an owned Dea string, reporting unrepresentable lengths. */
static dea_string fs_string(const FsChar *text, FsError *error) {
#if defined(_WIN32)
    size_t wide_len = wcslen(text);
    int len;
    if (wide_len > INT_MAX) { *error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return DEA_STRING_EMPTY; }
    if (wide_len == 0) return DEA_STRING_EMPTY;
    len = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, (int)wide_len, NULL, 0, NULL, NULL);
    if (len == 0) { *error = fs_native_error(); return DEA_STRING_EMPTY; }
    dea_string out = _rt_alloc_string((dea_int)len);
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, (int)wide_len,
                            _rt_string_bytes(out), len, NULL, NULL)) {
        *error = fs_native_error(); rt_string_release(out); return DEA_STRING_EMPTY;
    }
#else
    size_t len = strlen(text);
    if (len > INT32_MAX) { *error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return DEA_STRING_EMPTY; }
    dea_string out = _rt_alloc_string((dea_int)len);
    memcpy(_rt_string_bytes(out), text, len);
#endif
    return out;
}

#if defined(_WIN32)
/** Open the object itself, optionally following its final reparse point. */
static HANDLE fs_handle(const wchar_t *path, int follow, DWORD access, DWORD share) {
    return CreateFileW(path, access, share, NULL, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | (follow ? 0 : FILE_FLAG_OPEN_REPARSE_POINT), NULL);
}

/** Classify all reparse points conservatively as links. */
static int fs_attributes_type(DWORD attributes) {
    if (attributes & FILE_ATTRIBUTE_REPARSE_POINT) return 3;
    if (attributes & FILE_ATTRIBUTE_DIRECTORY) return 2;
    if (attributes & FILE_ATTRIBUTE_DEVICE) return 4;
    return 1;
}
#endif

/** Query metadata without narrowing persistent extents or timestamps. */
static FsMetadata fs_metadata_native(const FsChar *path, int follow) {
    FsMetadata out = {0};
#if defined(_WIN32)
    BY_HANDLE_FILE_INFORMATION st;
    HANDLE handle = fs_handle(path, follow, FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    if (handle == INVALID_HANDLE_VALUE) { out.error = fs_native_error(); return out; }
    if (!GetFileInformationByHandle(handle, &st)) {
        out.error = fs_native_error(); CloseHandle(handle); return out;
    }
    if (!CloseHandle(handle)) { out.error = fs_native_error(); return out; }
    out.file_type = fs_attributes_type(st.dwFileAttributes);
    uint64_t size = ((uint64_t)st.nFileSizeHigh << 32) | st.nFileSizeLow;
    if (size <= INT64_MAX) out.size = (dea_opt_long){1, (dea_long)size};
    uint64_t ticks = ((uint64_t)st.ftLastWriteTime.dwHighDateTime << 32) | st.ftLastWriteTime.dwLowDateTime;
    /* Divide before subtracting so even pre-epoch times retain their sign. */
    out.mtime_sec = (dea_opt_long){1, (dea_long)(ticks / 10000000) - INT64_C(11644473600)};
    out.mtime_nsec = (dea_opt_int){1, (dea_int)((ticks % 10000000) * 100)};
#else
    struct stat st;
    if ((follow ? stat(path, &st) : lstat(path, &st)) != 0) { out.error = fs_native_error(); return out; }
    out.file_type = S_ISREG(st.st_mode) ? 1 : S_ISDIR(st.st_mode) ? 2 : S_ISLNK(st.st_mode) ? 3 : 4;
    if (st.st_size >= 0 && (off_t)(dea_long)st.st_size == st.st_size)
        out.size = (dea_opt_long){1, (dea_long)st.st_size};
    if ((time_t)(dea_long)st.st_mtime == st.st_mtime) {
        out.mtime_sec = (dea_opt_long){1, (dea_long)st.st_mtime};
#if defined(__APPLE__)
        out.mtime_nsec = (dea_opt_int){1, (dea_int)st.st_mtimespec.tv_nsec};
#else
        out.mtime_nsec = (dea_opt_int){1, (dea_int)st.st_mtim.tv_nsec};
#endif
    }
#endif
    out.ok = 1;
    return out;
}

/** Public metadata transport, with shared input validation. */
FsMetadata rt_fs_metadata(dea_string path, dea_bool follow) {
    FsMetadata out = {0};
    FsChar *native = fs_path(path, &out.error);
    if (native) { if (!follow) fs_trim_entry(native); out = fs_metadata_native(native, follow); free(native); }
    return out;
}

/** Compare followed native identities; a failed lookup is never false success. */
FsBool rt_fs_same_file(dea_string left, dea_string right) {
    FsBool out = {0};
    FsChar *a = fs_path(left, &out.error), *b;
    if (!a) return out;
    b = fs_path(right, &out.error);
    if (!b) { free(a); return out; }
#if defined(_WIN32)
    HANDLE ha = fs_handle(a, 1, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    HANDLE hb = INVALID_HANDLE_VALUE;
    FILE_ID_INFO ia, ib;
    if (ha == INVALID_HANDLE_VALUE) out.error = fs_native_error();
    else if ((hb = fs_handle(b, 1, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)) == INVALID_HANDLE_VALUE)
        out.error = fs_native_error();
    else if (!GetFileInformationByHandleEx(ha, FileIdInfo, &ia, sizeof(ia)) ||
             !GetFileInformationByHandleEx(hb, FileIdInfo, &ib, sizeof(ib))) out.error = fs_native_error();
    else {
        out.ok = 1;
        out.value = ia.VolumeSerialNumber == ib.VolumeSerialNumber &&
            memcmp(&ia.FileId, &ib.FileId, sizeof(ia.FileId)) == 0;
    }
    if (ha != INVALID_HANDLE_VALUE && !CloseHandle(ha) && out.ok) { out.ok = 0; out.error = fs_native_error(); }
    if (hb != INVALID_HANDLE_VALUE && !CloseHandle(hb) && out.ok) { out.ok = 0; out.error = fs_native_error(); }
#else
    struct stat ia, ib;
    if (stat(a, &ia) != 0 || stat(b, &ib) != 0) out.error = fs_native_error();
    else { out.ok = 1; out.value = ia.st_dev == ib.st_dev && ia.st_ino == ib.st_ino; }
#endif
    free(a); free(b);
    return out;
}

/** Obtain current-directory storage, growing when the host reports insufficient space. */
static FsChar *fs_cwd(FsError *error) {
    size_t cap = 256;
    for (;;) {
        FsChar *out = (FsChar *)malloc(cap * sizeof(FsChar));
        if (!out) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
#if defined(_WIN32)
        DWORD n = GetCurrentDirectoryW((DWORD)cap, out);
        if (n > 0 && n < cap) return out;
        if (n == 0) { *error = fs_native_error(); free(out); return NULL; }
#else
        if (getcwd(out, cap)) return out;
        if (errno != ERANGE) { *error = fs_native_error(); free(out); return NULL; }
#endif
        free(out);
        if (cap > INT32_MAX / 2) { *error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return NULL; }
        cap *= 2;
    }
}

/** Convert owned host path storage to its direct result and release it. */
static FsPath fs_path_result(FsChar *native, FsError error) {
    FsPath out = {0};
    out.value = DEA_STRING_EMPTY;
    if (native) { out.value = fs_string(native, &error); free(native); }
    out.error = error;
    out.ok = fs_status(error).ok;
    if (!out.ok) { rt_string_release(out.value); out.value = DEA_STRING_EMPTY; }
    return out;
}

/** Return the working-directory spelling as supplied by the host. */
FsPath rt_fs_current_dir(void) {
    FsError error = {0};
    FsChar *native = fs_cwd(&error);
    return fs_path_result(native, error);
}

/** Anchor at call time. POSIX preserves dots and literal backslashes. */
FsPath rt_fs_absolute(dea_string path) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error), *out = NULL;
    if (!native) return fs_path_result(NULL, error);
#if defined(_WIN32)
    DWORD cap = GetFullPathNameW(native, 0, NULL, NULL);
    if (!cap) error = fs_native_error();
    while (cap) {
        out = (wchar_t *)malloc((size_t)cap * sizeof(wchar_t));
        if (!out) { error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); break; }
        DWORD n = GetFullPathNameW(native, cap, out, NULL);
        if (!n) { error = fs_native_error(); free(out); out = NULL; break; }
        if (n < cap) break;
        free(out); out = NULL; cap = n;
    }
#else
    if (native[0] == '/') { out = native; native = NULL; }
    else {
        FsChar *cwd = fs_cwd(&error);
        if (cwd) { out = fs_join(cwd, native, &error); free(cwd); }
    }
#endif
    free(native);
    return fs_path_result(out, error);
}

/** Resolve existing aliases without equating canonical spelling with identity. */
FsPath rt_fs_canonicalize(dea_string path) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error), *out = NULL;
    if (!native) return fs_path_result(NULL, error);
#if defined(_WIN32)
    HANDLE handle = fs_handle(native, 1, FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    if (handle == INVALID_HANDLE_VALUE) error = fs_native_error();
    else {
        DWORD cap = GetFinalPathNameByHandleW(handle, NULL, 0, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
        if (!cap) error = fs_native_error();
        while (cap) {
            out = (wchar_t *)malloc((size_t)cap * sizeof(wchar_t));
            if (!out) { error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); break; }
            DWORD n = GetFinalPathNameByHandleW(handle, out, cap, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
            if (!n) { error = fs_native_error(); free(out); out = NULL; break; }
            if (n < cap) break;
            free(out); out = NULL; cap = n;
        }
        if (!CloseHandle(handle) && fs_status(error).ok) error = fs_native_error();
    }
#else
    out = realpath(native, NULL);
    if (!out) error = fs_native_error();
#endif
    free(native);
    return fs_path_result(out, error);
}

/** Follow the supplied directory and change the process-global working directory. */
FsStatus rt_fs_set_current_dir(dea_string path) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error);
    if (native) {
#if defined(_WIN32)
        if (!SetCurrentDirectoryW(native)) error = fs_native_error();
#else
        if (chdir(native) != 0) error = fs_native_error();
#endif
        free(native);
    }
    return fs_status(error);
}

/** Create one directory, accepting an existing followed directory only for parents. */
static FsError fs_mkdir(const FsChar *path, int allow_existing) {
    FsError error = {0};
#if defined(_WIN32)
    if (CreateDirectoryW(path, NULL)) return error;
#else
    if (mkdir(path, 0777) == 0) return error;
#endif
    error = fs_native_error();
    if (allow_existing && error.kind == DEA_OS_ERROR_ALREADY_EXISTS) {
        FsMetadata info = fs_metadata_native(path, 1);
        if (!info.ok) return info.error;
        if (info.file_type == 2) return fs_error(0);
        return fs_error(DEA_OS_ERROR_NOT_DIRECTORY);
    }
    return error;
}

/** Create missing prefixes in order; on failure keep successful earlier creations. */
FsStatus rt_fs_create_dir(dea_string path, dea_bool recursive) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error);
    if (!native) return fs_status(error);
    if (recursive) {
        size_t len = fs_length(native), start = 1;
#if defined(_WIN32)
        /* Ordinary paths anchor/normalize once; verbatim paths must retain their components. */
        if (!fs_verbatim_path(native)) {
            FsPath abs = rt_fs_absolute(path);
            free(native); native = NULL;
            if (!abs.ok) return fs_status(abs.error);
            native = fs_path(abs.value, &error); rt_string_release(abs.value);
            if (!native) return fs_status(error);
        }
        len = fs_length(native);
        start = fs_root_length(native);
        if (start == SIZE_MAX) {
            free(native); return fs_status(fs_error(DEA_OS_ERROR_INVALID_INPUT));
        }
#endif
        for (size_t i = start; i < len; ++i) {
            if (!fs_path_sep(native, native[i]) || fs_path_sep(native, native[i - 1])) continue;
            FsChar saved = native[i]; native[i] = 0;
            error = fs_mkdir(native, 1); native[i] = saved;
            if (!fs_status(error).ok) break;
        }
    }
    if (fs_status(error).ok) error = fs_mkdir(native, recursive);
    free(native);
    return fs_status(error);
}

/** Remove a non-directory entry, including a final symbolic link itself. */
FsStatus rt_fs_remove_file(dea_string path) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error);
    if (!native) return fs_status(error);
    fs_trim_entry(native);
#if defined(_WIN32)
    DWORD attrs = GetFileAttributesW(native);
    if (attrs == INVALID_FILE_ATTRIBUTES) error = fs_native_error();
    else if ((attrs & FILE_ATTRIBUTE_DIRECTORY) && !(attrs & FILE_ATTRIBUTE_REPARSE_POINT))
        error = fs_error(DEA_OS_ERROR_IS_DIRECTORY);
    else if ((attrs & FILE_ATTRIBUTE_DIRECTORY) ? !RemoveDirectoryW(native) : !DeleteFileW(native))
        error = fs_native_error();
#else
    if (unlink(native) != 0) error = fs_native_error();
#endif
    free(native); return fs_status(error);
}

#if !defined(_WIN32)
/**
 * Delete relative to an owned parent descriptor. O_NOFOLLOW prevents a raced
 * symbolic link from becoming a traversed directory; unlinkat removes links.
 */
static FsError fs_remove_tree_at(int parent, const char *name, unsigned depth) {
    FsError error = {0};
    struct stat st;
    if (depth > 256) return fs_error(DEA_OS_ERROR_RESOURCE_EXHAUSTED);
    if (fstatat(parent, name, &st, AT_SYMLINK_NOFOLLOW) != 0) return fs_native_error();
    if (!S_ISDIR(st.st_mode)) {
        if (unlinkat(parent, name, 0) != 0) return fs_native_error();
        return error;
    }
    int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return fs_native_error();
    DIR *dir = fdopendir(fd);
    if (!dir) { error = fs_native_error(); close(fd); return error; }
    for (;;) {
        errno = 0;
        struct dirent *entry = DEA_FS_READDIR(dir);
        if (!entry) { if (errno) error = fs_native_error(); break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        error = fs_remove_tree_at(fd, entry->d_name, depth + 1);
        if (!fs_status(error).ok) break;
    }
    if (DEA_FS_CLOSEDIR(dir) != 0 && fs_status(error).ok) error = fs_native_error();
    if (fs_status(error).ok && unlinkat(parent, name, AT_REMOVEDIR) != 0) error = fs_native_error();
    return error;
}
#else
/**
 * Hold every visited directory without FILE_SHARE_DELETE while enumerating it.
 * This blocks replacing the directory entry; callers must exclude in-place
 * reparse-tag and mount changes by other writers.
 * The final entry is opened without following reparse points and deleted by handle.
 */
static FsError fs_remove_tree(const wchar_t *path, unsigned depth) {
    FsError error = {0};
    if (depth > 256) return fs_error(DEA_OS_ERROR_RESOURCE_EXHAUSTED);
    HANDLE handle = fs_handle(path, 0, DELETE | FILE_READ_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE);
    if (handle == INVALID_HANDLE_VALUE) return fs_native_error();
    BY_HANDLE_FILE_INFORMATION info;
    if (!GetFileInformationByHandle(handle, &info)) error = fs_native_error();
    else if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && !(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
        wchar_t *pattern = fs_join(path, L"*", &error);
        if (pattern) {
            WIN32_FIND_DATAW data;
            HANDLE find = FindFirstFileW(pattern, &data);
            if (find == INVALID_HANDLE_VALUE) {
                DWORD code = GetLastError();
                if (code != ERROR_FILE_NOT_FOUND) error = rt_os_error_from_win32(code);
            } else {
                do {
                    if (!wcscmp(data.cFileName, L".") || !wcscmp(data.cFileName, L"..")) continue;
                    wchar_t *child = fs_join(path, data.cFileName, &error);
                    if (child) { error = fs_remove_tree(child, depth + 1); free(child); }
                    if (!fs_status(error).ok) break;
                } while (FindNextFileW(find, &data));
                if (fs_status(error).ok && GetLastError() != ERROR_NO_MORE_FILES) error = fs_native_error();
                if (!FindClose(find) && fs_status(error).ok) error = fs_native_error();
            }
            free(pattern);
        }
    }
    if (fs_status(error).ok) {
        FILE_DISPOSITION_INFO disposition = {TRUE};
        if (!SetFileInformationByHandle(handle, FileDispositionInfo, &disposition, sizeof(disposition))) error = fs_native_error();
    }
    if (!CloseHandle(handle) && fs_status(error).ok) error = fs_native_error();
    return error;
}
#endif

/** Remove one empty real directory or a tree; recursive final links are unlinked. */
FsStatus rt_fs_remove_dir(dea_string path, dea_bool recursive) {
    FsError error = {0};
    FsChar *native = fs_path(path, &error);
    if (!native) return fs_status(error);
    fs_trim_entry(native);
    if (recursive) {
        if (!fs_delete_root(native)) {
            FsMetadata root = fs_metadata_native(native, 0);
            if (!root.ok || (root.file_type != 2 && root.file_type != 3)) {
                error = root.ok ? fs_error(DEA_OS_ERROR_NOT_DIRECTORY) : root.error;
                free(native); return fs_status(error);
            }
        }
        if (fs_delete_root(native)) error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
#if defined(_WIN32)
        else error = fs_remove_tree(native, 0);
#else
        else {
            char *slash = strrchr(native, '/');
            char *name = native;
            int parent = AT_FDCWD;
            if (slash) {
                /* Retain the final parent separator, including an exact // root. */
                name = slash + 1;
                char first = *name; *name = 0;
                parent = open(native, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
                *name = first;
                if (parent < 0) error = fs_native_error();
            }
            if (fs_status(error).ok) error = fs_remove_tree_at(parent, name, 0);
            if (parent != AT_FDCWD && parent >= 0 && close(parent) != 0 && fs_status(error).ok) error = fs_native_error();
        }
#endif
    } else {
        FsMetadata info = fs_metadata_native(native, 0);
        if (!info.ok) error = info.error;
        else if (info.file_type != 2) error = fs_error(DEA_OS_ERROR_NOT_DIRECTORY);
#if defined(_WIN32)
        else if (!RemoveDirectoryW(native)) error = fs_native_error();
#else
        else if (rmdir(native) != 0) error = fs_native_error();
#endif
    }
    free(native); return fs_status(error);
}

/** Native rename has no copy fallback. File replacement rejects real directories. */
FsStatus rt_fs_rename(dea_string source, dea_string destination, dea_bool replace_file) {
    FsError error = {0};
    FsChar *a = fs_path(source, &error), *b;
    if (!a) return fs_status(error);
    b = fs_path(destination, &error);
    if (!b) { free(a); return fs_status(error); }
    fs_trim_entry(a); fs_trim_entry(b);
    if (replace_file) {
        FsMetadata src = fs_metadata_native(a, 0), dst = fs_metadata_native(b, 0);
        if (!src.ok) error = src.error;
        else if (src.file_type == 2 || (dst.ok && dst.file_type == 2)) error = fs_error(DEA_OS_ERROR_IS_DIRECTORY);
        else if (!dst.ok && dst.error.kind != DEA_OS_ERROR_NOT_FOUND) error = dst.error;
    }
    if (fs_status(error).ok) {
#if defined(_WIN32)
        if (!MoveFileExW(a, b, MOVEFILE_REPLACE_EXISTING)) error = fs_native_error();
#else
        if (DEA_FS_RENAME(a, b) != 0) error = fs_native_error();
#endif
    }
    free(a); free(b); return fs_status(error);
}

/** Copy bytes to an exclusively created destination; failures leave partial data. */
FsStatus rt_fs_copy_file(dea_string source, dea_string destination) {
    FsError error = {0};
    FsChar *a = fs_path(source, &error), *b;
    if (!a) return fs_status(error);
    b = fs_path(destination, &error);
    if (!b) { free(a); return fs_status(error); }
#if defined(_WIN32)
    FsMetadata info = fs_metadata_native(a, 1);
    if (!info.ok) error = info.error;
    else if (info.file_type != 1) error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
    else if (!CopyFileW(a, b, TRUE)) error = fs_native_error();
#else
    int in = open(a, O_RDONLY | O_NONBLOCK | O_CLOEXEC), out = -1;
    struct stat st;
    if (in < 0) error = fs_native_error();
    else if (fstat(in, &st) != 0) error = fs_native_error();
    else if (!S_ISREG(st.st_mode)) error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
    else if ((out = open(b, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0666)) < 0) error = fs_native_error();
    else {
        char buffer[65536];
        for (;;) {
            ssize_t count = DEA_FS_READ(in, buffer, sizeof(buffer));
            if (count < 0) { error = fs_native_error(); break; }
            if (!count) break;
            ssize_t offset = 0;
            while (offset < count) {
                ssize_t n = DEA_FS_WRITE(out, buffer + offset, (size_t)(count - offset));
                if (n <= 0) { error = n < 0 ? fs_native_error() : fs_error(DEA_OS_ERROR_IO_ERROR); break; }
                offset += n;
            }
            if (!fs_status(error).ok) break;
        }
    }
    if (out >= 0 && DEA_FS_CLOSE(out) != 0 && fs_status(error).ok) error = fs_native_error();
    if (in >= 0 && DEA_FS_CLOSE(in) != 0 && fs_status(error).ok) error = fs_native_error();
#endif
    free(a); free(b); return fs_status(error);
}

/** Native cursor state owns one host iterator and remembers terminal results. */
typedef struct FsDir {
    int state;
    FsError error;
#if defined(_WIN32)
    HANDLE find;
    WIN32_FIND_DATAW data;
    int first;
#else
    DIR *dir;
#endif
} FsDir;

/** Open a cursor without materializing or sorting entries. */
FsDirOpen rt_dir_open(dea_string path) {
    FsDirOpen out = {0};
    FsChar *native = fs_path(path, &out.error);
    if (!native) return out;
    FsDir *dir = (FsDir *)calloc(1, sizeof(FsDir));
    if (!dir) { out.error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); free(native); return out; }
#if defined(_WIN32)
    FsMetadata info = fs_metadata_native(native, 1);
    if (!info.ok) out.error = info.error;
    else if (info.file_type != 2) out.error = fs_error(DEA_OS_ERROR_NOT_DIRECTORY);
    else {
        FsChar *pattern = fs_join(native, L"*", &out.error);
        if (pattern) {
            dir->find = FindFirstFileW(pattern, &dir->data);
            if (dir->find == INVALID_HANDLE_VALUE) {
                DWORD code = GetLastError();
                if (code == ERROR_FILE_NOT_FOUND) dir->state = 1;
                else out.error = rt_os_error_from_win32(code);
            } else dir->first = 1;
            free(pattern);
        }
    }
#else
    dir->dir = opendir(native);
    if (!dir->dir) out.error = fs_native_error();
    else {
        int fd = dirfd(dir->dir);
        if (fcntl(fd, F_SETFD, FD_CLOEXEC) < 0) { out.error = fs_native_error(); DEA_FS_CLOSEDIR(dir->dir); }
    }
#endif
    free(native);
    if (!fs_status(out.error).ok) { free(dir); return out; }
    out.ok = 1; out.handle = dir; return out;
}

/** Return entry/end/error, copying each name before advancing the host cursor. */
FsDirNext rt_dir_next(void *handle) {
    FsDirNext out = {0};
    out.name = DEA_STRING_EMPTY;
    FsDir *dir = (FsDir *)handle;
    if (!dir) { out.state = 2; out.error = fs_error(DEA_OS_ERROR_INVALID_HANDLE); return out; }
    if (dir->state) { out.state = dir->state; out.error = dir->error; return out; }
    for (;;) {
#if defined(_WIN32)
        if (dir->first) dir->first = 0;
        else if (!FindNextFileW(dir->find, &dir->data)) {
            DWORD code = GetLastError();
            out.state = code == ERROR_NO_MORE_FILES ? 1 : 2;
            if (out.state == 2) out.error = rt_os_error_from_win32(code);
            break;
        }
        if (!wcscmp(dir->data.cFileName, L".") || !wcscmp(dir->data.cFileName, L"..")) continue;
        out.name = fs_string(dir->data.cFileName, &out.error);
        out.file_type = fs_attributes_type(dir->data.dwFileAttributes);
#else
        errno = 0;
        struct dirent *entry = DEA_FS_READDIR(dir->dir);
        if (!entry) {
            out.state = errno ? 2 : 1;
            if (errno) out.error = fs_native_error();
            break;
        }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        out.name = fs_string(entry->d_name, &out.error);
        /* d_type is an optional hint. Never fall back to stat for DT_UNKNOWN. */
#if defined(_DIRENT_HAVE_D_TYPE) || defined(__APPLE__)
        out.file_type = entry->d_type == DT_REG ? 1 : entry->d_type == DT_DIR ? 2 :
            entry->d_type == DT_LNK ? 3 : entry->d_type == DT_UNKNOWN ? 0 : 4;
#endif
#endif
        if (!fs_status(out.error).ok) out.state = 2;
        break;
    }
    if (out.state) { dir->state = out.state; dir->error = out.error; }
    return out;
}

/** Consume a valid cursor exactly once, including when native close fails. */
FsStatus rt_dir_close(void *handle) {
    FsDir *dir = (FsDir *)handle;
    FsError error = {0};
    if (!dir) return fs_status(fs_error(DEA_OS_ERROR_INVALID_HANDLE));
#if defined(_WIN32)
    if (dir->find != INVALID_HANDLE_VALUE && !FindClose(dir->find)) error = fs_native_error();
#else
    if (DEA_FS_CLOSEDIR(dir->dir) != 0) error = fs_native_error();
#endif
    free(dir); return fs_status(error);
}
#endif
