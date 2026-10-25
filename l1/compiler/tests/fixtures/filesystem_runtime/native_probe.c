/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file native_probe.c
 * Direct runtime path and directory boundary regressions.
 */
#ifndef _WIN32
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#endif
#include "dea_rt.h"
#include "path_arguments.h"
#if defined(_WIN32)
#include <windows.h>
#else
#include <dirent.h>
#include <fcntl.h>
#endif

#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "filesystem line %d: %s\n", __LINE__, #x); return 1; } } while (0)
typedef struct __deaM3sys2fsS10RtFsStatus Status;
typedef struct __deaM3sys2fsS8RtFsPath PathResult;
typedef struct __deaM3sys2fsS9RtDirNext Next;

/**
 * Borrow argv bytes for the duration of one runtime call.
 *
 * @param s NUL-terminated fixture path bytes borrowed for the operation.
 * @return A non-owning Dea string valid while s remains alive.
 */
static dea_string text(const char *s) { return (dea_string)DEA_STRING_CONST((char *)s, (dea_int)strlen(s)); }

/**
 * Exercise every path boundary with an embedded NUL and with empty input.
 *
 * @param path Empty or embedded-NUL input required to fail validation.
 * @param valid Valid comparison path used for multi-path operations.
 * @return Zero when every invalid-input check passes, otherwise one.
 */
static int invalid_paths(dea_string path, dea_string valid) {
    REQUIRE(!rt_fs_metadata(path, 0).ok);
    REQUIRE(!rt_fs_metadata(path, 1).ok);
    REQUIRE(!rt_fs_same_file(path, valid).ok);
    REQUIRE(!rt_fs_same_file(valid, path).ok);
    REQUIRE(!rt_fs_absolute(path).ok);
    REQUIRE(!rt_fs_canonicalize(path).ok);
    REQUIRE(!rt_fs_set_current_dir(path).ok);
    REQUIRE(!rt_fs_create_dir(path, 0).ok);
    REQUIRE(!rt_fs_create_dir(path, 1).ok);
    REQUIRE(!rt_fs_remove_file(path).ok);
    REQUIRE(!rt_fs_remove_dir(path, 0).ok);
    REQUIRE(!rt_fs_remove_dir(path, 1).ok);
    REQUIRE(!rt_fs_rename(path, valid, 0).ok);
    REQUIRE(!rt_fs_rename(valid, path, 1).ok);
    REQUIRE(!rt_fs_copy_file(path, valid).ok);
    REQUIRE(!rt_fs_copy_file(valid, path).ok);
    REQUIRE(!rt_dir_open(path).ok);
    REQUIRE(!rt_read_file_all(path).has_value);
    REQUIRE(!rt_write_file_all(path, text("bad")));
    REQUIRE(!rt_file_info(path).exists);
    REQUIRE(!rt_delete_file(path));
    return 0;
}

/**
 * Check names are copied, EOF repeats, and the valid cursor is consumed on close.
 *
 * @param path Directory to enumerate through a native runtime cursor.
 * @param expected Required number of entries excluding dot entries.
 * @return Zero when all cursor lifetime checks pass, otherwise one.
 */
static int cursor(dea_string path, int expected) {
    struct __deaM3sys2fsS9RtDirOpen opened = rt_dir_open(path);
    REQUIRE(opened.ok);
    int count = 0;
    dea_string saved = DEA_STRING_EMPTY;
    for (;;) {
        Next next = rt_dir_next(opened.handle);
        if (next.state == 1) break;
        REQUIRE(next.state == 0);
        REQUIRE(rt_strlen(next.name) > 0);
        REQUIRE(strcmp(_rt_string_bytes(next.name), ".") && strcmp(_rt_string_bytes(next.name), ".."));
        if (!count) { saved = next.name; rt_string_retain(saved); }
        ++count;
        rt_string_release(next.name);
    }
    REQUIRE(count == expected);
    REQUIRE(rt_dir_next(opened.handle).state == 1);
    REQUIRE(rt_dir_close(opened.handle).ok);
    REQUIRE(!count || rt_strlen(saved) > 0);
    rt_string_release(saved);
    return 0;
}

/**
 * Run against Python-owned fixtures; paths include Unicode, spaces, and links.
 *
 * @param argc Number of command-line arguments, including the executable name.
 * @param argv Argument vector containing the Python-owned fixture paths.
 * @return Zero if every probe passes, otherwise one.
 */
int main(int argc, char **argv) {
    REQUIRE(argc == 8);
    argv = fixture_path_arguments(argc, argv);
    REQUIRE(argv != NULL);
    dea_string root = text(argv[1]), target = text(argv[2]), different = text(argv[3]);
    dea_string link = text(argv[4]), hard = text(argv[5]), dangling = text(argv[6]), tree = text(argv[7]);
    char nul_bytes[] = "not-a-path\0tail";
    REQUIRE(invalid_paths((dea_string)DEA_STRING_CONST(nul_bytes, sizeof(nul_bytes) - 1), root) == 0);
    REQUIRE(invalid_paths(DEA_STRING_EMPTY, root) == 0);
    REQUIRE(rt_fs_metadata(target, 1).ok);
    dea_opt_string contents = rt_read_file_all(target);
    REQUIRE(contents.has_value);
    rt_string_release(contents.value);
    REQUIRE(rt_write_file_all(different, text("replacement")));
    REQUIRE(rt_fs_same_file(target, target).ok && rt_fs_same_file(target, target).value);
    REQUIRE(rt_fs_same_file(target, different).ok && !rt_fs_same_file(target, different).value);
    REQUIRE(!rt_fs_same_file(target, text("/does-not-exist-dea-filesystem")).ok);
    REQUIRE(!rt_fs_copy_file(target, hard).ok);
    REQUIRE(!rt_fs_copy_file(target, target).ok);
    REQUIRE(!rt_fs_remove_dir(root, 0).ok);
    REQUIRE(!rt_fs_remove_dir(text("."), 1).ok);
    REQUIRE(!rt_fs_remove_dir(text(".."), 1).ok);
#if defined(_WIN32)
    REQUIRE(!rt_fs_remove_dir(text("C:.."), 1).ok);
    REQUIRE(!rt_fs_remove_dir(text("C:\\"), 1).ok);
    REQUIRE(!rt_fs_remove_dir(text("\\\\server\\share"), 1).ok);
    char bad_utf8[] = {(char)0xff, 0};
    REQUIRE(!rt_fs_absolute(text(bad_utf8)).ok);
#else
    REQUIRE(!rt_fs_remove_dir(text("/"), 1).ok);
#endif
    if (strcmp(argv[4], "-")) {
        REQUIRE(rt_fs_metadata(link, 0).file_type == 3);
        REQUIRE(rt_fs_metadata(link, 1).file_type == 1);
        REQUIRE(rt_fs_same_file(target, link).ok && rt_fs_same_file(target, link).value);
        REQUIRE(rt_fs_same_file(target, hard).ok && rt_fs_same_file(target, hard).value);
        REQUIRE(rt_fs_metadata(dangling, 0).ok);
        REQUIRE(!rt_fs_metadata(dangling, 1).ok);
        REQUIRE(!rt_fs_same_file(dangling, dangling).ok);
        REQUIRE(!rt_fs_remove_dir(link, 0).ok);

        /* Replacing a link removes its entry, leaving its followed target untouched. */
        REQUIRE(rt_fs_rename(different, link, 1).ok);
        REQUIRE(rt_fs_metadata(target, 1).ok);
        REQUIRE(rt_fs_metadata(link, 0).file_type == 1);
        REQUIRE(rt_fs_remove_file(dangling).ok);
    }
    REQUIRE(cursor(root, 4) == 0);
    REQUIRE(rt_fs_remove_dir(tree, 1).ok);
    REQUIRE(rt_fs_metadata(target, 1).ok);

    /* Missing lookup errors survive unrelated successful operations. */
    struct __deaM3sys2fsS12RtFsMetadata missing = rt_fs_metadata(text("/does-not-exist-dea-filesystem"), 1);
    REQUIRE(!missing.ok && missing.error.kind == DEA_OS_ERROR_NOT_FOUND);
    REQUIRE(rt_fs_metadata(root, 1).ok);
    REQUIRE(missing.error.native_code != 0 && missing.error.domain != DEA_OS_DOMAIN_RUNTIME);
    size_t cap = strlen(argv[1]) + 64;
    char *partial = (char *)malloc(cap);
    REQUIRE(partial != NULL);
    REQUIRE(snprintf(partial, cap, "%s/created/../target/child", argv[1]) > 0);
    REQUIRE(!rt_fs_create_dir(text(partial), 1).ok);
    REQUIRE(snprintf(partial, cap, "%s/created", argv[1]) > 0);
#if defined(_WIN32)

    /* GetFullPathNameW removes created/.. before prefix creation starts. */
    REQUIRE(!rt_fs_metadata(text(partial), 1).ok);
#else
    REQUIRE(rt_fs_metadata(text(partial), 1).file_type == 2);
#endif
    free(partial);
    fixture_free_arguments(argc, argv);
    return 0;
}
