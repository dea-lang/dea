/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file path_probe.c
 * Actual pure path helpers under simulated Windows and POSIX semantics.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
#if defined(DEA_FS_PATH_TEST_WINDOWS)
#ifndef _WIN32
#define _WIN32 1
#endif
typedef wchar_t FsChar;
#define FS_TEXT(s) L##s
#define FS_SEP L'\\'
#define FS_COMPARE wcscmp
#else
#ifdef _WIN32
#undef _WIN32
#endif
typedef char FsChar;
#define FS_TEXT(s) s
#define FS_SEP '/'
#define FS_COMPARE strcmp
#endif
#define DEA_OS_ERROR_FILE_TOO_LARGE 19
#define DEA_OS_ERROR_OUT_OF_MEMORY 12
typedef struct FsError { int kind; } FsError;

/**
 * Supply the scalar error constructor used by production spelling helpers.
 *
 * @param kind Runtime error-kind tag.
 * @return The scalar test error carrying the supplied tag.
 */
static FsError fs_error(int kind) { FsError out = {kind}; return out; }
#include "dea_rt_fs_path.h"
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "path probe line %d: %s\n", __LINE__, #x); return 1; } } while (0)

/**
 * Check joining preserves the namespace and root already present in the parent.
 *
 * @param parent Parent directory spelling to join.
 * @param expected Required spelling after appending the child name.
 * @return Zero when joining preserves the expected spelling, otherwise one.
 */
static int joined(const FsChar *parent, const FsChar *expected) {
    FsError error = {0};
    FsChar *actual = fs_join(parent, FS_TEXT("child"), &error);
    REQUIRE(actual != NULL && !error.kind);
    REQUIRE(FS_COMPARE(actual, expected) == 0);
    free(actual);
    return 0;
}

/**
 * Check trimming cannot remove the separator that makes a root absolute.
 *
 * @param path Native path spelling copied before trimming.
 * @param expected Required spelling after trailing-separator trimming.
 * @return Zero when trimming preserves the expected spelling, otherwise one.
 */
static int trimmed(const FsChar *path, const FsChar *expected) {
    size_t bytes = (fs_length(path) + 1) * sizeof(FsChar);
    FsChar *copy = (FsChar *)malloc(bytes);
    REQUIRE(copy != NULL);
    memcpy(copy, path, bytes);
    fs_trim_entry(copy);
    REQUIRE(FS_COMPARE(copy, expected) == 0);
    free(copy);
    return 0;
}

/**
 * Exercise rooted, relative, device, UNC, dot, space, and literal-backslash cases.
 * @return Zero when all path-spelling checks pass, otherwise one.
 */
int main(void) {
#if defined(DEA_FS_PATH_TEST_WINDOWS)
    const FsChar *roots[] = {
        L"C:", L"C:\\", L"\\", L"/", L"C:\\\\",
        L"\\\\server\\share", L"\\\\server\\share\\", L"\\\\server\\\\share",
        L"\\\\server\\\\share\\\\", L"//server//share/", L"\\\\\\server\\share",
        L"\\\\?\\UNC\\server\\share", L"\\\\?\\unc\\server\\share\\",
        L"\\\\.\\UNC\\server\\share", L"\\\\.\\uNc\\server\\share\\", L"//./UNC/server/share", L"/\\?/uNc/server/share/",
        L"\\\\?\\C:\\", L"\\\\.\\C:\\", L"\\\\?\\Volume{example}\\",
    };
    for (size_t i = 0; i < sizeof(roots) / sizeof(roots[0]); ++i) {
        REQUIRE(fs_delete_root(roots[i]));
        REQUIRE(fs_root_length(roots[i]) == fs_length(roots[i]));
        REQUIRE(trimmed(roots[i], roots[i]) == 0);
    }
    const FsChar *invalid[] = {
        L"\\\\server", L"\\\\?\\UNC\\server", L"\\\\?\\C:",
        L"\\\\?\\GLOBALROOT\\Device\\HarddiskVolume1\\",
        L"\\\\?\\GLOBALROOT\\Device\\HarddiskVolume1\\child", L"\\\\.\\PhysicalDrive0",
        L".", L"..", L"C:.", L"C:..", L"C:\\child\\.. ", L"\\\\.\\C:\\child\\.. ", L". ", L"...", L" ",
    };
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) REQUIRE(fs_delete_root(invalid[i]));
    const FsChar *children[] = {
        L"relative", L"C:relative", L"C:\\child", L"\\child", L"\\\\server\\share\\child",
        L"\\\\?\\UNC\\server\\share\\child", L"\\\\.\\unc\\server\\share\\child",
        L"\\\\?\\C:\\child", L"\\\\?\\Volume{example}\\child", L"\\\\?\\C:\\. ",
    };
    for (size_t i = 0; i < sizeof(children) / sizeof(children[0]); ++i) REQUIRE(!fs_delete_root(children[i]));
    REQUIRE(joined(L"C:", L"C:child") == 0);
    REQUIRE(joined(L"\\", L"\\child") == 0);
    REQUIRE(joined(L"C:\\", L"C:\\child") == 0);
    REQUIRE(joined(L"C:/", L"C:/child") == 0);
    REQUIRE(joined(L"\\\\?\\C:\\", L"\\\\?\\C:\\child") == 0);
    REQUIRE(joined(L"\\\\.\\UNC\\server\\share\\", L"\\\\.\\UNC\\server\\share\\child") == 0);
    REQUIRE(joined(L"space caf\u00e9", L"space caf\u00e9\\child") == 0);
    REQUIRE(trimmed(L"C:\\child\\\\", L"C:\\child") == 0);
    REQUIRE(fs_root_length(L"\\\\.\\uNc\\server\\share\\child") == fs_length(L"\\\\.\\uNc\\server\\share\\"));
#else
    REQUIRE(joined("/", "/child") == 0);
    REQUIRE(joined("//", "//child") == 0);
    REQUIRE(joined("C:", "C:/child") == 0);
    REQUIRE(joined("literal\\", "literal\\/child") == 0);
    REQUIRE(joined("space caf\xc3\xa9", "space caf\xc3\xa9/child") == 0);
    REQUIRE(fs_delete_root("/") && fs_delete_root("//") && fs_delete_root("."));
    REQUIRE(fs_delete_root("a/..") && fs_delete_root("a/./"));
    REQUIRE(!fs_delete_root("literal\\") && !fs_delete_root("a/\\.."));
    REQUIRE(!fs_delete_root("different") && !fs_delete_root(" . "));
    REQUIRE(trimmed("a///", "a") == 0);
    REQUIRE(trimmed("//", "//") == 0);
#endif
    return 0;
}
