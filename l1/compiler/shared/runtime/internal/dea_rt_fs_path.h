/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_fs_path.h
 * Pure native path spelling helpers. Included after FsChar/FsError/fs_error.
 * The Windows branch can be exercised without pretending to run Win32 APIs.
 */
#ifndef DEA_RT_FS_PATH_H
#define DEA_RT_FS_PATH_H

/** Native string length in code units. */
static size_t fs_length(const FsChar *s) {
#if defined(_WIN32)
    return wcslen(s);
#else
    return strlen(s);
#endif
}

#if defined(_WIN32)
/** Recognize DOS device namespace syntax before host normalization. */
static int fs_device_path(const FsChar *path) {
    return (path[0] == '\\' || path[0] == '/') && (path[1] == '\\' || path[1] == '/') &&
        (path[2] == '?' || path[2] == '.') && (path[3] == '\\' || path[3] == '/');
}

/** Only the canonical question-mark prefix disables Win32 normalization. */
static int fs_verbatim_path(const FsChar *path) {
    return path[0] == '\\' && path[1] == '\\' && path[2] == '?' && path[3] == '\\';
}

/** Compare one ASCII namespace character independently of locale. */
static int fs_ascii_equal(FsChar a, FsChar b) {
    if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
    if (b >= 'A' && b <= 'Z') b += 'a' - 'A';
    return a == b;
}

/** Recognize a DOS drive letter, excluding arbitrary colon-bearing components. */
static int fs_drive_letter(FsChar c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
}
#endif

/** Recognize separators in this namespace; POSIX backslash stays a filename byte. */
static int fs_path_sep(const FsChar *path, FsChar c) {
#if defined(_WIN32)
    return c == '\\' || (!fs_verbatim_path(path) && c == '/');
#else
    (void)path;
    return c == '/';
#endif
}

/**
 * Return the complete native root prefix, or SIZE_MAX for unsupported Windows
 * device namespaces/malformed UNC roots. Count components rather than separators.
 */
static size_t fs_root_length(const FsChar *path) {
    size_t len = fs_length(path);
#if defined(_WIN32)
    size_t start = 0;
    if (fs_device_path(path)) {
        if (len >= 8 && fs_ascii_equal(path[4], 'U') && fs_ascii_equal(path[5], 'N') &&
            fs_ascii_equal(path[6], 'C') && fs_path_sep(path, path[7])) {
            start = 8;
        } else if (len >= 7 && fs_drive_letter(path[4]) && path[5] == ':' && fs_path_sep(path, path[6])) {
            start = 7;
            while (start < len && fs_path_sep(path, path[start])) ++start;
            return start;
        } else if (len >= 12 && fs_ascii_equal(path[4], 'V') && fs_ascii_equal(path[5], 'O') &&
                   fs_ascii_equal(path[6], 'L') && fs_ascii_equal(path[7], 'U') &&
                   fs_ascii_equal(path[8], 'M') && fs_ascii_equal(path[9], 'E') && path[10] == '{') {
            start = 11;
            while (start < len && path[start] != '}') ++start;
            if (start + 1 >= len || !fs_path_sep(path, path[start + 1])) return SIZE_MAX;
            start += 2;
            while (start < len && fs_path_sep(path, path[start])) ++start;
            return start;
        } else {
            return SIZE_MAX;
        }
    } else if (len >= 2 && fs_drive_letter(path[0]) && path[1] == ':') {
        start = 2;
        while (start < len && fs_path_sep(path, path[start])) ++start;
        return start;
    } else if (len >= 2 && fs_path_sep(path, path[0]) && fs_path_sep(path, path[1])) {
        start = 2;
    } else {
        return len && fs_path_sep(path, path[0]) ? 1 : 0;
    }
    /* A UNC root has a nonempty server and share. Win32 collapses separator runs. */
    while (start < len && fs_path_sep(path, path[start])) ++start;
    size_t server = start;
    while (start < len && !fs_path_sep(path, path[start])) ++start;
    if (start == server || start == len) return SIZE_MAX;
    while (start < len && fs_path_sep(path, path[start])) ++start;
    size_t share = start;
    while (start < len && !fs_path_sep(path, path[start])) ++start;
    if (start == share) return SIZE_MAX;
    while (start < len && fs_path_sep(path, path[start])) ++start;
    return start;
#else
    if (!len || path[0] != '/') return 0;
    /* Exactly two leading slashes can name an implementation-defined POSIX root. */
    return len >= 2 && path[1] == '/' && (len == 2 || path[2] != '/') ? 2 : 1;
#endif
}

/** Strip final separators without converting a root or bare drive into another path. */
static void fs_trim_entry(FsChar *path) {
    size_t len = fs_length(path), root = fs_root_length(path);
    if (root == SIZE_MAX) return;
    size_t floor = root ? root : 1;
    while (len > floor && fs_path_sep(path, path[len - 1])) path[--len] = 0;
}

/** Join a directory and one child without changing rooted/drive-relative semantics. */
static FsChar *fs_join(const FsChar *parent, const FsChar *name, FsError *error) {
    size_t a = fs_length(parent), b = fs_length(name);
    size_t separator = a && !fs_path_sep(parent, parent[a - 1]) ? 1 : 0;
#if defined(_WIN32)
    if (a == 2 && fs_drive_letter(parent[0]) && parent[1] == ':') separator = 0;
#endif
    size_t limit = SIZE_MAX / sizeof(FsChar);
    if (a >= limit || b > limit - a - 1 || separator > limit - a - b - 1) {
        *error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return NULL;
    }
    FsChar *out = (FsChar *)malloc((a + b + separator + 1) * sizeof(FsChar));
    if (!out) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
    memcpy(out, parent, a * sizeof(FsChar));
    if (separator) out[a] = FS_SEP;
    memcpy(out + a + separator, name, (b + 1) * sizeof(FsChar));
    return out;
}

/** Reject host roots, final dot/dot-dot, and ambiguous Windows dot/space aliases. */
static int fs_delete_root(const FsChar *path) {
    size_t len = fs_length(path), root = fs_root_length(path);
    if (root == SIZE_MAX || len <= root) return 1;
    while (len > root && fs_path_sep(path, path[len - 1])) --len;
    if (len <= root) return 1;
    size_t start = len;
    while (start > root && !fs_path_sep(path, path[start - 1])) --start;
    if (len - start == 1 && path[start] == '.') return 1;
    if (len - start == 2 && path[start] == '.' && path[start + 1] == '.') return 1;
#if defined(_WIN32)
    if (!fs_verbatim_path(path)) {
        size_t significant = start;
        while (significant < len && (path[significant] == '.' || path[significant] == ' ')) ++significant;
        if (significant == len) return 1;
    }
#endif
    return 0;
}
#endif
