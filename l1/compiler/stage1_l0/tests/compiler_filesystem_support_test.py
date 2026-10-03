#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Direct ABI coverage for the common L1 compiler filesystem support."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
COMMON_SUPPORT = (
    L1_ROOT / "compiler" / "stage1_l0" / "support" / "compiler_support.c"
)


def resolve_c_compiler() -> str:
    """Return one configured or available C compiler."""

    for configured in (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    ):
        if configured:
            resolved = shutil.which(configured)
            if resolved is None:
                raise AssertionError(
                    f"configured C compiler was not found: {configured}"
                )
            return resolved

    for candidate in ("clang", "gcc", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise AssertionError("compiler filesystem support test requires a C compiler")


def compile_harness(compiler: str, source: Path, output: Path) -> None:
    """Compile the direct support-ABI harness."""

    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        str(source),
        str(COMMON_SUPPORT),
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"C compilation exited with {completed.returncode}:\n{completed.stdout}"
        )


def harness_source() -> str:
    """Return the strict-C99 filesystem ABI harness source."""

    return r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#if defined(_WIN32)
#define PATH_SEPARATOR "\\"
#else
#define PATH_SEPARATOR "/"
#endif

int32_t l1c_fs_mkdir(
    const uint8_t *path,
    int32_t path_len,
    int32_t mode
);
int32_t l1c_fs_path_kind_nofollow(
    const uint8_t *path,
    int32_t path_len
);
int32_t l1c_fs_path_kind_follow(
    const uint8_t *path,
    int32_t path_len
);
int32_t l1c_fs_rename_absent(
    const uint8_t *source,
    int32_t source_len,
    const uint8_t *destination,
    int32_t destination_len
);
int32_t l1c_fs_remove_regular_file(
    const uint8_t *path,
    int32_t path_len
);
int32_t l1c_fs_remove_empty_dir(
    const uint8_t *path,
    int32_t path_len
);
int32_t l1c_fs_join_child(
    const uint8_t *parent,
    int32_t parent_len,
    const uint8_t *child,
    int32_t child_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l1c_fs_resolve_trusted_temp_parent(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l1c_fs_absolute_path(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l1c_fs_canonical_existing_path(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l1c_fs_resolve_executable(
    const uint8_t *name,
    int32_t name_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l1c_fs_host_is_darwin(void);
int32_t l1c_fs_same_file(
    const uint8_t *left,
    int32_t left_len,
    const uint8_t *right,
    int32_t right_len
);
int32_t l1c_process_run(
    const uint8_t *const *words,
    const int32_t *lengths,
    int32_t count,
    int32_t *status_out
);

static int32_t path_len(const char *path) {
    size_t len = strlen(path);
    return len <= INT32_MAX ? (int32_t)len : -1;
}

static int32_t path_kind(const char *path) {
    return l1c_fs_path_kind_nofollow(
        (const uint8_t *)path,
        path_len(path)
    );
}

static int32_t path_kind_follow(const char *path) {
    return l1c_fs_path_kind_follow(
        (const uint8_t *)path,
        path_len(path)
    );
}

static int make_path(
    char *out,
    size_t out_size,
    const char *root,
    const char *leaf
) {
    int written = snprintf(
        out,
        out_size,
        "%s%s%s",
        root,
        PATH_SEPARATOR,
        leaf
    );
    return written >= 0 && (size_t)written < out_size;
}

static int write_marker(const char *path, const char *marker) {
    FILE *stream = fopen(path, "wb");
    size_t len = strlen(marker);
    if (stream == NULL) return 0;
    if (fwrite(marker, 1, len, stream) != len) {
        fclose(stream);
        return 0;
    }
    return fclose(stream) == 0;
}

static int joined_child_matches(
    const char *parent,
    const char *child,
    const char *expected
) {
    uint8_t output[128];
    int32_t required = l1c_fs_join_child(
        (const uint8_t *)parent,
        path_len(parent),
        (const uint8_t *)child,
        path_len(child),
        NULL,
        0
    );
    int32_t actual;
    if (required <= 0 || required >= (int32_t)sizeof(output)) return 0;
    actual = l1c_fs_join_child(
        (const uint8_t *)parent,
        path_len(parent),
        (const uint8_t *)child,
        path_len(child),
        output,
        (int32_t)sizeof(output) - 1
    );
    if (actual != required) return 0;
    output[actual] = '\0';
    return strcmp((const char *)output, expected) == 0;
}

static int marker_matches(const char *path, const char *marker) {
    char buffer[32];
    FILE *stream = fopen(path, "rb");
    size_t expected_len = strlen(marker);
    size_t actual_len;
    int trailing;
    if (stream == NULL || expected_len > sizeof(buffer)) return 0;
    actual_len = fread(buffer, 1, sizeof(buffer), stream);
    trailing = fgetc(stream);
    if (fclose(stream) != 0) return 0;
    return actual_len == expected_len &&
           trailing == EOF &&
           memcmp(buffer, marker, expected_len) == 0;
}

int main(int argc, char **argv) {
    char workspace[4096];
    char empty_dir[4096];
    char missing[4096];
    char source[4096];
    char source_collision[4096];
    char destination[4096];
    char removable[4096];
    char notdir_parent[4096];
    char notdir_child[4096];
    uint8_t resolved[4096];
    static const uint8_t embedded_nul[] = { 'a', '\0', 'b' };

    if (argc >= 5 && strcmp(argv[1], "--process-child") == 0) {
        if (strcmp(argv[3], "two words") != 0) return 124;
        if (strcmp(argv[4], "quote\"slash\\") != 0) return 125;
        return atoi(argv[2]);
    }

    {
        static const uint8_t child_mode[] = "--process-child";
        static const uint8_t child_status[] = "127";
        static const uint8_t spaced[] = "two words";
        static const uint8_t quoted[] = "quote\"slash\\";
        const uint8_t *child_words[] = {
            (const uint8_t *)argv[0],
            child_mode,
            child_status,
            spaced,
            quoted
        };
        int32_t child_lengths[] = {
            path_len(argv[0]),
            (int32_t)(sizeof(child_mode) - 1u),
            (int32_t)(sizeof(child_status) - 1u),
            (int32_t)(sizeof(spaced) - 1u),
            (int32_t)(sizeof(quoted) - 1u)
        };
        int32_t process_status = -1;
        if (l1c_process_run(
                child_words,
                child_lengths,
                5,
                &process_status
            ) != 1 || process_status != 127) return 568;
    }

    {
        static const uint8_t missing_process[] =
            "missing-l1c-process-run-executable";
        const uint8_t *missing_words[] = { missing_process };
        int32_t missing_lengths[] = {
            (int32_t)(sizeof(missing_process) - 1u)
        };
        int32_t process_status = -1;
        if (l1c_process_run(
                missing_words,
                missing_lengths,
                1,
                &process_status
            ) != 0) return 569;
        missing_words[0] = embedded_nul;
        missing_lengths[0] = 3;
        if (l1c_process_run(
                missing_words,
                missing_lengths,
                1,
                &process_status
            ) != -1) return 570;
    }

#if defined(__APPLE__)
    if (l1c_fs_host_is_darwin() != 1) return 567;
#else
    if (l1c_fs_host_is_darwin() != 0) return 567;
#endif

    if (argc < 2) return 1;
    if (!make_path(workspace, sizeof(workspace), argv[1], "workspace")) return 2;
    if (!make_path(empty_dir, sizeof(empty_dir), workspace, "empty")) return 3;
    if (!make_path(missing, sizeof(missing), workspace, "missing")) return 4;
    if (!make_path(source, sizeof(source), workspace, "source")) return 5;
    if (!make_path(
            source_collision,
            sizeof(source_collision),
            workspace,
            "source-collision"
        )) return 6;
    if (!make_path(
            destination,
            sizeof(destination),
            workspace,
            "destination"
        )) return 7;
    if (!make_path(
            removable,
            sizeof(removable),
            workspace,
            "removable"
        )) return 8;
    if (!make_path(
            notdir_parent,
            sizeof(notdir_parent),
            workspace,
            "notdir-parent"
        )) return 9;
    if (!make_path(
            notdir_child,
            sizeof(notdir_child),
            notdir_parent,
            "child"
        )) return 91;

    if (l1c_fs_mkdir(
            (const uint8_t *)workspace,
            path_len(workspace),
            0700
        ) != 1) return 10;
    if (l1c_fs_mkdir(
            (const uint8_t *)workspace,
            path_len(workspace),
            0700
        ) != 0) return 11;
    if (path_kind(workspace) != 2) return 12;
    if (path_kind(missing) != 0) return 13;
    if (path_kind_follow(workspace) != 2) return 14;
    if (path_kind_follow(missing) != 0) return 15;

#if !defined(_WIN32)
    {
        struct stat info;
        if (stat(workspace, &info) != 0) return 16;
        if ((info.st_mode & 0777) != 0700) return 17;
    }
#endif

    if (!write_marker(notdir_parent, "file")) return 18;
    if (path_kind(notdir_child) != 0) return 19;
    if (path_kind_follow(notdir_child) != 0) return 191;

    if (!write_marker(source, "source")) return 20;
    if (path_kind(source) != 1) return 21;
    if (path_kind_follow(source) != 1) return 22;
    if (l1c_fs_rename_absent(
            (const uint8_t *)source,
            path_len(source),
            (const uint8_t *)destination,
            path_len(destination)
        ) != 1) return 23;
    if (path_kind(source) != 0) return 24;
    if (path_kind(destination) != 1) return 25;
    if (!marker_matches(destination, "source")) return 26;

    if (!write_marker(source_collision, "collision")) return 27;
    if (l1c_fs_rename_absent(
            (const uint8_t *)source_collision,
            path_len(source_collision),
            (const uint8_t *)destination,
            path_len(destination)
        ) != 0) return 28;
    if (path_kind(source_collision) != 1) return 29;
    if (path_kind(destination) != 1) return 30;
    if (!marker_matches(source_collision, "collision")) return 31;
    if (!marker_matches(destination, "source")) return 32;

    if (l1c_fs_rename_absent(
            (const uint8_t *)workspace,
            path_len(workspace),
            (const uint8_t *)missing,
            path_len(missing)
        ) != -1) return 33;

    if (l1c_fs_mkdir(
            (const uint8_t *)empty_dir,
            path_len(empty_dir),
            0700
        ) != 1) return 34;
    if (l1c_fs_remove_empty_dir(
            (const uint8_t *)empty_dir,
            path_len(empty_dir)
        ) != 1) return 35;
    if (l1c_fs_remove_empty_dir(
            (const uint8_t *)empty_dir,
            path_len(empty_dir)
        ) != 0) return 36;
    if (l1c_fs_remove_empty_dir(
            (const uint8_t *)destination,
            path_len(destination)
        ) != -1) return 37;
    if (l1c_fs_remove_empty_dir(
            (const uint8_t *)workspace,
            path_len(workspace)
        ) != -1) return 38;

    if (argc >= 8 && strcmp(argv[2], "-") != 0) {
        if (path_kind(argv[2]) != 3) return 40;
        if (path_kind_follow(argv[2]) != 2) return 41;
        if (l1c_fs_mkdir(
                (const uint8_t *)argv[2],
                path_len(argv[2]),
                0700
            ) != 0) return 42;

        if (path_kind(argv[3]) != 3) return 43;
        if (path_kind_follow(argv[3]) != 1) return 44;
        if (l1c_fs_remove_regular_file(
                (const uint8_t *)argv[3],
                path_len(argv[3])
            ) != -1) return 441;
        if (path_kind_follow(argv[3]) != 1) return 442;

        if (path_kind(argv[4]) != 3) return 45;
        if (path_kind_follow(argv[4]) != 0) return 46;
        if (l1c_fs_mkdir(
                (const uint8_t *)argv[4],
                path_len(argv[4]),
                0700
            ) != 0) return 47;
    }

    if (argc >= 8 && strcmp(argv[5], "-") != 0) {
        if (path_kind(argv[5]) != 3) return 48;
        if (path_kind_follow(argv[5]) != -1) return 49;
    }

    if (l1c_fs_path_kind_nofollow(embedded_nul, 3) != -1) return 50;
    if (l1c_fs_mkdir(embedded_nul, 3, 0700) != -1) return 51;
    if (l1c_fs_mkdir(
            (const uint8_t *)missing,
            path_len(missing),
            010000
        ) != -1) return 52;
    if (l1c_fs_path_kind_nofollow(NULL, 0) != -1) return 53;
    if (l1c_fs_path_kind_follow(embedded_nul, 3) != -1) return 54;
    if (l1c_fs_path_kind_follow(NULL, 0) != -1) return 55;

    if (!joined_child_matches(
            "parent/",
            "child",
            "parent/child"
        )) return 551;
#if defined(_WIN32)
    if (!joined_child_matches(
            "parent\\",
            "child",
            "parent\\child"
        )) return 552;
#else
    if (!joined_child_matches(
            "parent\\",
            "child",
            "parent\\/child"
        )) return 552;
#endif
    if (l1c_fs_join_child(
            embedded_nul,
            3,
            (const uint8_t *)"child",
            5,
            NULL,
            0
        ) != -1) return 553;

    {
        static const char relative[] = "compiler-probe";
        int32_t required = l1c_fs_absolute_path(
            (const uint8_t *)relative,
            path_len(relative),
            NULL,
            0
        );
        int32_t actual;
        size_t suffix_len = strlen(relative);
        if (required <= (int32_t)suffix_len ||
            required >= (int32_t)sizeof(resolved)) return 554;
        actual = l1c_fs_absolute_path(
            (const uint8_t *)relative,
            path_len(relative),
            resolved,
            (int32_t)sizeof(resolved) - 1
        );
        if (actual != required) return 555;
        resolved[actual] = '\0';
        if (strcmp(
                (const char *)resolved + actual - suffix_len,
                relative
            ) != 0) return 556;
        if (l1c_fs_absolute_path(embedded_nul, 3, NULL, 0) != -1)
            return 557;
    }

    if (argc >= 12) {
        int32_t required = l1c_fs_resolve_executable(
            (const uint8_t *)argv[10],
            path_len(argv[10]),
            NULL,
            0
        );
        int32_t actual;
        if (required <= 0 || required >= (int32_t)sizeof(resolved)) return 558;
        actual = l1c_fs_resolve_executable(
            (const uint8_t *)argv[10],
            path_len(argv[10]),
            resolved,
            (int32_t)sizeof(resolved) - 1
        );
        if (actual != required) return 559;
        resolved[actual] = '\0';
        if (l1c_fs_same_file(
                resolved,
                actual,
                (const uint8_t *)argv[11],
                path_len(argv[11])
            ) != 1) return 560;
#if !defined(_WIN32)
        if (actual <= path_len(argv[10]) ||
            strcmp(
                (const char *)resolved + actual - path_len(argv[10]),
                argv[10]
            ) != 0) return 5601;
#endif
        if (l1c_fs_resolve_executable(
                (const uint8_t *)"missing-compiler-probe",
                22,
                NULL,
                0
            ) != -1) return 561;
        if (l1c_fs_resolve_executable(embedded_nul, 3, NULL, 0) != -1)
            return 562;

        required = l1c_fs_canonical_existing_path(
            resolved,
            actual,
            NULL,
            0
        );
        if (required <= 0 || required >= (int32_t)sizeof(resolved)) return 563;
        actual = l1c_fs_canonical_existing_path(
            resolved,
            actual,
            resolved,
            (int32_t)sizeof(resolved) - 1
        );
        if (actual != required) return 564;
        resolved[actual] = '\0';
        if (l1c_fs_same_file(
                resolved,
                actual,
                (const uint8_t *)argv[11],
                path_len(argv[11])
            ) != 1) return 565;
        if (l1c_fs_canonical_existing_path(
                embedded_nul,
                3,
                NULL,
                0
            ) != -1) return 566;
    }

    if (!write_marker(removable, "remove")) return 56;
    if (l1c_fs_remove_regular_file(
            (const uint8_t *)removable,
            path_len(removable)
        ) != 1) return 57;
    if (l1c_fs_remove_regular_file(
            (const uint8_t *)removable,
            path_len(removable)
        ) != 0) return 58;
    if (l1c_fs_remove_regular_file(
            (const uint8_t *)workspace,
            path_len(workspace)
        ) != -1) return 59;

    if (argc >= 10) {
        int32_t required = l1c_fs_resolve_trusted_temp_parent(
            (const uint8_t *)argv[6],
            path_len(argv[6]),
            NULL,
            0
        );
        int32_t actual;
        if (required <= 0 || required >= (int32_t)sizeof(resolved)) return 61;
        actual = l1c_fs_resolve_trusted_temp_parent(
            (const uint8_t *)argv[6],
            path_len(argv[6]),
            resolved,
            (int32_t)sizeof(resolved) - 1
        );
        if (actual != required) return 62;
        resolved[actual] = '\0';
        if (strcmp((const char *)resolved, argv[6]) != 0) return 63;
#if defined(_WIN32)
        if (l1c_fs_resolve_trusted_temp_parent(
                (const uint8_t *)argv[7],
                path_len(argv[7]),
                NULL,
                0
            ) <= 0) return 64;
#else
        if (l1c_fs_resolve_trusted_temp_parent(
                (const uint8_t *)argv[7],
                path_len(argv[7]),
                NULL,
                0
            ) != -1) return 64;
        if (l1c_fs_resolve_trusted_temp_parent(
                (const uint8_t *)argv[8],
                path_len(argv[8]),
                NULL,
                0
            ) <= 0) return 65;
        if (l1c_fs_resolve_trusted_temp_parent(
                (const uint8_t *)argv[9],
                path_len(argv[9]),
                NULL,
                0
            ) != -1) return 66;
#endif
    }

    remove(source_collision);
    remove(destination);
    remove(notdir_parent);
    if (l1c_fs_remove_empty_dir(
            (const uint8_t *)workspace,
            path_len(workspace)
        ) != 1) return 60;
    return 0;
}
'''



def test_portable_snapshot(compiler: str, temp_dir: Path) -> None:
    """Check real paths, bounded fields, and snapshot lifetime on every host.

    Args:
        compiler: Selected host C compiler executable.
        temp_dir: Owned directory for the harness and its fixtures.

    Raises:
        AssertionError: If compilation or the snapshot contract fails.
    """
    directory = temp_dir / "snapshot-parent"
    directory.mkdir()
    regular = temp_dir / "snapshot-file"
    regular.write_bytes(b"marker")
    source = temp_dir / "portable_snapshot.c"
    source.write_text(r'''#define _XOPEN_SOURCE 700
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include "SUPPORT_PATH"
static void check_field(uint8_t *report, int field, const char *expected) {
    uint8_t bytes[4096];
    int32_t length = l1c_fs_temp_parent_field(report, field, NULL, 0);
    assert(length == (int32_t)strlen(expected));
    assert(length < (int32_t)sizeof(bytes));
    memset(bytes, 0x5a, sizeof(bytes));
    if (length > 0) {
        assert(l1c_fs_temp_parent_field(report, field, bytes, length - 1) == length);
        assert(bytes[0] == 0x5a);
    }
    assert(l1c_fs_temp_parent_field(report, field, bytes, length) == length);
    assert(memcmp(bytes, expected, (size_t)length) == 0);
    assert(bytes[length] == 0x5a);
    assert(l1c_fs_temp_parent_field(report, field, NULL, 1) == -1);
    assert(l1c_fs_temp_parent_field(report, field, bytes, -1) == -1);
}
int main(int argc, char **argv) {
    uint8_t *report;
    uint8_t canonical[4096];
    int32_t length;
    int field;
    assert(argc == 4);
    report = l1c_fs_inspect_temp_parent((const uint8_t *)argv[1], (int32_t)strlen(argv[1]));
    assert(report != NULL && l1c_fs_temp_parent_status(report) == 0);
    length = l1c_fs_resolve_trusted_temp_parent((const uint8_t *)argv[1],
        (int32_t)strlen(argv[1]), canonical, sizeof(canonical) - 1);
    assert(length > 0 && length < (int32_t)sizeof(canonical));
    canonical[length] = 0;
    /* Query after removal proves the snapshot does not inspect again. */
    assert(l1c_fs_remove_empty_dir((const uint8_t *)argv[1], (int32_t)strlen(argv[1])) == 1);
    check_field(report, 0, (const char *)canonical);
    for (field = 1; field <= 4; ++field) check_field(report, field, "");
    assert(l1c_fs_temp_parent_field(report, -1, NULL, 0) == -1);
    assert(l1c_fs_temp_parent_field(report, 5, NULL, 0) == -1);
    l1c_fs_temp_parent_free(report);
    for (field = 2; field <= 3; ++field) {
        report = l1c_fs_inspect_temp_parent((const uint8_t *)argv[field], (int32_t)strlen(argv[field]));
        assert(report != NULL && l1c_fs_temp_parent_status(report) != 0);
#if defined(_WIN32)
        if (field == 2) {
            assert(l1c_fs_temp_parent_status(report) == 3);
            check_field(report, 3, "");
            check_field(report, 4, "");
        } else {
            assert(l1c_fs_temp_parent_status(report) == 2);
            check_field(report, 3, "CreateFileA");
            assert(l1c_fs_temp_parent_field(report, 4, NULL, 0) > 0);
        }
#endif
        l1c_fs_temp_parent_free(report);
    }
    assert(l1c_fs_inspect_temp_parent(NULL, 0) == NULL);
    assert(l1c_fs_inspect_temp_parent((const uint8_t *)"a\0b", 3) == NULL);
    assert(l1c_fs_temp_parent_status(NULL) == 6);
    assert(l1c_fs_temp_parent_field(NULL, 0, NULL, 0) == -1);
    l1c_fs_temp_parent_free(NULL);
    return 0;
}
'''.replace("SUPPORT_PATH", COMMON_SUPPORT.as_posix()), encoding="utf-8")
    compile_snapshot_harness(compiler, source, [str(directory), str(regular), str(temp_dir / "missing" / "child")])


def test_windows_snapshot(compiler: str, temp_dir: Path) -> None:
    """Inject Win32 failures and prove cleanup cannot replace their evidence.

    Args:
        compiler: Selected host C compiler executable.
        temp_dir: Owned directory for the harness and executable.

    Raises:
        AssertionError: If compilation or captured failure details differ.
    """
    if os.name != "nt":
        return
    source = temp_dir / "windows_snapshot.c"
    source.write_text(r'''#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
static int scenario;
static int closes;
static HANDLE WINAPI fake_CreateFileA(LPCSTR name, DWORD access, DWORD share,
    LPSECURITY_ATTRIBUTES security, DWORD disposition, DWORD flags, HANDLE template_file) {
    (void)name; (void)access; (void)share; (void)security;
    (void)disposition; (void)flags; (void)template_file;
    if (scenario == 1 || scenario == 9) {
        SetLastError(scenario == 1 ? ERROR_ACCESS_DENIED : ERROR_PATH_NOT_FOUND);
        return INVALID_HANDLE_VALUE;
    }
    return (HANDLE)(uintptr_t)42;
}
static BOOL WINAPI fake_GetFileInformationByHandle(HANDLE handle, LPBY_HANDLE_FILE_INFORMATION info) {
    (void)handle;
    if (scenario == 2) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    memset(info, 0, sizeof(*info));
    info->dwFileAttributes = scenario == 3 ? FILE_ATTRIBUTE_NORMAL : FILE_ATTRIBUTE_DIRECTORY;
    return TRUE;
}
static DWORD WINAPI fake_GetFinalPathNameByHandleA(HANDLE handle, LPSTR path, DWORD capacity, DWORD flags) {
    (void)handle; (void)flags;
    if (scenario == 4 || scenario == 8) { SetLastError((DWORD)0xffffffffu); return 0; }
    if (scenario == 7) return capacity + 1;
    strcpy(path, "C:\\trusted");
    return (DWORD)strlen(path);
}
static BOOL WINAPI fake_CloseHandle(HANDLE handle) {
    (void)handle;
    ++closes;
    /* Even successful cleanup may overwrite the thread's last error. */
    SetLastError(ERROR_INVALID_HANDLE);
    return scenario != 5 && scenario != 8 && scenario != 3 && scenario != 2;
}
static void *fake_malloc(size_t size) {
    if (scenario == 6 && size == MAX_PATH) return NULL;
    return malloc(size);
}
#define CreateFileA fake_CreateFileA
#define GetFileInformationByHandle fake_GetFileInformationByHandle
#define GetFinalPathNameByHandleA fake_GetFinalPathNameByHandleA
#define CloseHandle fake_CloseHandle
#define malloc fake_malloc
#include "SUPPORT_PATH"
#undef CreateFileA
#undef GetFileInformationByHandle
#undef GetFinalPathNameByHandleA
#undef CloseHandle
#undef malloc
static void check_field(uint8_t *report, int field, const char *expected) {
    uint8_t bytes[128];
    int32_t length = l1c_fs_temp_parent_field(report, field, NULL, 0);
    assert(length == (int32_t)strlen(expected));
    memset(bytes, 0x5a, sizeof(bytes));
    if (length > 0) {
        assert(l1c_fs_temp_parent_field(report, field, bytes, length - 1) == length);
        assert(bytes[0] == 0x5a);
    }
    assert(l1c_fs_temp_parent_field(report, field, bytes, length) == length);
    assert(memcmp(bytes, expected, (size_t)length) == 0 && bytes[length] == 0x5a);
}
int main(void) {
    const int statuses[] = {0, 2, 2, 3, 1, 7, 6, 8, 1, 2};
    const char *operations[] = {"", "CreateFileA", "GetFileInformationByHandle", "",
        "GetFinalPathNameByHandleA", "CloseHandle", "", "", "GetFinalPathNameByHandleA", "CreateFileA"};
    const char *errors[] = {"", "5", "5", "", "4294967295", "6", "", "", "4294967295", "3"};
    for (scenario = 0; scenario < 10; ++scenario) {
        uint8_t *report;
        closes = 0;
        report = l1c_fs_inspect_temp_parent((const uint8_t *)"C:\\selected", 11);
        assert(report != NULL);
        assert(l1c_fs_temp_parent_status(report) == statuses[scenario]);
        assert(closes == (scenario == 1 || scenario == 9 ? 0 : 1));
        check_field(report, 0, scenario == 0 ? "C:\\trusted" : "C:\\selected");
        check_field(report, 3, operations[scenario]);
        check_field(report, 4, errors[scenario]);
        l1c_fs_temp_parent_free(report);
    }
    return 0;
}
'''.replace("SUPPORT_PATH", COMMON_SUPPORT.as_posix()), encoding="utf-8")
    compile_snapshot_harness(compiler, source, [])


def compile_snapshot_harness(compiler: str, source: Path, arguments: list[str]) -> None:
    """Build and run a harness that includes the native support implementation.

    Args:
        compiler: Selected host C compiler executable.
        source: Generated harness source path.
        arguments: Fixture paths passed to the executable.

    Raises:
        AssertionError: If compilation or execution fails.
    """
    executable = source.with_suffix(".exe" if os.name == "nt" else "")
    built = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
         str(source), "-o", str(executable)],
        capture_output=True, text=True, check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    executed = subprocess.run([str(executable), *arguments], capture_output=True, text=True, check=False)
    assert executed.returncode == 0, f"{source.name}: {executed.returncode}\n{executed.stdout}{executed.stderr}"


def test_posix_trust_snapshot(compiler: str, temp_dir: Path) -> None:
    """Exercise synthetic ownership and stable bounded fields without host chown.

    Args:
        compiler: Selected host C compiler executable.
        temp_dir: Owned directory for the harness and executable.

    Raises:
        AssertionError: If the native snapshot contract fails.
    """
    if os.name == "nt":
        return
    source = temp_dir / "trust_snapshot.c"
    executable = temp_dir / "trust_snapshot"
    harness = r'''#define _XOPEN_SOURCE 700
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
static int scenario;
static int inspections;
static const char *rejected = "/";
static uid_t fake_geteuid(void) { return 1000; }
static char *fake_realpath(const char *path, char *output) {
    char *result;
    (void)output;
    if (scenario == 1) { errno = EACCES; return NULL; }
    result = (char *)malloc(strlen(path) + 1);
    assert(result != NULL);
    strcpy(result, path);
    return result;
}
static int fake_stat(const char *path, struct stat *info) {
    ++inspections;
    memset(info, 0, sizeof(*info));
    info->st_mode = S_IFDIR | 0755;
    info->st_uid = 0;
    if (strcmp(path, rejected) != 0) return 0;
    if (scenario == 2) { errno = EACCES; return -1; }
    if (scenario == 3) info->st_mode = S_IFREG | 0644;
    if (scenario == 4) info->st_uid = 65534;
    if (scenario == 5) info->st_mode = S_IFDIR | 0777;
    if (scenario == 7) info->st_uid = 1000;
    if (scenario == 8) info->st_mode = S_IFDIR | 01777;
    if (scenario == 9) info->st_uid = (uid_t)UINT32_MAX;
    return 0;
}
#define stat(...) fake_stat(__VA_ARGS__)
#define geteuid fake_geteuid
#define realpath fake_realpath
#include "SUPPORT_PATH"
#undef stat
#undef geteuid
#undef realpath
int main(void) {
    const char *components[] = {"/", "/trusted", "/trusted/parent"};
    const uint8_t path[] = "/trusted/parent";
    int index;
    for (index = 0; index < 3; ++index) {
        rejected = components[index];
        for (scenario = 0; scenario <= 9; ++scenario) {
            uint8_t *report = l1c_fs_inspect_temp_parent(path, sizeof(path) - 1);
            uint8_t bytes[128];
            const char *expected = scenario >= 2 && scenario <= 5 ? rejected : (const char *)path;
            int saved_inspections = inspections;
            int32_t length;
            assert(report != NULL);
            if (scenario == 9) expected = rejected;
            assert(l1c_fs_temp_parent_status(report) ==
                (scenario == 9 ? 4 : (scenario <= 5 ? scenario : 0)));
            length = l1c_fs_temp_parent_field(report, 0, NULL, 0);
            assert(length == (int32_t)strlen(expected));
            memset(bytes, 0x5a, sizeof(bytes));
            assert(l1c_fs_temp_parent_field(report, 0, bytes, length - 1) == length);
            assert(bytes[0] == 0x5a);
            assert(l1c_fs_temp_parent_field(report, 0, bytes, length) == length);
            assert(memcmp(bytes, expected, (size_t)length) == 0);
            assert(bytes[length] == 0x5a);
            assert(l1c_fs_temp_parent_field(report, 0, NULL, 1) == -1);
            assert(l1c_fs_temp_parent_field(report, 0, bytes, -1) == -1);
            assert(l1c_fs_temp_parent_field(report, 5, bytes, 128) == -1);
            if (scenario == 4 || scenario == 9) {
                const char *uid = scenario == 4 ? "65534" : "4294967295";
                length = l1c_fs_temp_parent_field(report, 1, bytes, 128);
                assert(length == (int32_t)strlen(uid));
                assert(memcmp(bytes, uid, (size_t)length) == 0);
                assert(l1c_fs_temp_parent_field(report, 2, bytes, 128) == 4);
                assert(memcmp(bytes, "1000", 4) == 0);
            }
            assert(inspections == saved_inspections);
            l1c_fs_temp_parent_free(report);
        }
    }
    assert(l1c_fs_inspect_temp_parent(NULL, 0) == NULL);
    assert(l1c_fs_temp_parent_field(NULL, 0, NULL, 0) == -1);
    l1c_fs_temp_parent_free(NULL);
    return 0;
}
'''
    source.write_text(harness.replace("SUPPORT_PATH", COMMON_SUPPORT.as_posix()), encoding="utf-8")
    built = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
         str(source), "-o", str(executable)],
        capture_output=True, text=True, check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    executed = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
    assert executed.returncode == 0, executed.stdout + executed.stderr


def native_spelling(path: Path) -> str:
    """Return host separators, including when MSYS2 Python uses POSIX spelling.

    Args:
        path: Fixture path to compare with native canonicalization.

    Returns:
        Path text using the host filesystem API's separators.
    """
    return str(path).replace("/", "\\") if os.name == "nt" else str(path)


def main() -> int:
    """Compile and execute the direct filesystem ABI harness."""

    compiler = resolve_c_compiler()
    with tempfile.TemporaryDirectory(
        prefix="l1_compiler_filesystem_support_test."
    ) as raw_temp:
        temp_dir = Path(raw_temp)
        test_portable_snapshot(compiler, temp_dir)
        test_windows_snapshot(compiler, temp_dir)
        test_posix_trust_snapshot(compiler, temp_dir)
        harness = temp_dir / "filesystem_harness.c"
        harness.write_text(harness_source(), encoding="utf-8")
        executable = temp_dir / (
            "filesystem_harness.exe" if os.name == "nt" else "filesystem_harness"
        )
        compile_harness(compiler, harness, executable)
        resolver_name = executable.name
        resolver_expected = executable.resolve()
        if os.name != "nt":
            resolver_alias = temp_dir / "filesystem-harness-alias"
            resolver_alias.symlink_to(executable.name)
            resolver_name = resolver_alias.name

        directory_target = temp_dir / "directory-target"
        directory_alias = temp_dir / "directory-alias"
        file_target = temp_dir / "file-target"
        file_alias = temp_dir / "file-alias"
        dangling_alias = temp_dir / "dangling-directory-alias"
        loop_a = temp_dir / "loop-a"
        loop_b = temp_dir / "loop-b"
        directory_target.mkdir()
        file_target.write_bytes(b"target")
        trusted_parent = temp_dir / "trusted-parent"
        unsafe_parent = temp_dir / "unsafe-parent"
        trusted_parent.mkdir(mode=0o700)
        unsafe_parent.mkdir(mode=0o700)
        if os.name == "nt":
            sticky_parent = trusted_parent
            nested_parent = unsafe_parent
        else:
            unsafe_parent.chmod(0o777)
            sticky_parent = temp_dir / "sticky-parent"
            sticky_parent.mkdir()
            sticky_parent.chmod(0o1777)

            unsafe_ancestor = temp_dir / "unsafe-ancestor"
            unsafe_ancestor.mkdir()
            unsafe_ancestor.chmod(0o777)
            nested_parent = unsafe_ancestor / "nested-parent"
            nested_parent.mkdir(mode=0o700)
        try:
            directory_alias.symlink_to(
                directory_target,
                target_is_directory=True,
            )
            file_alias.symlink_to(file_target)
            dangling_alias.symlink_to(
                temp_dir / "absent-directory-target",
                target_is_directory=True,
            )
        except OSError:
            for link in (
                directory_alias,
                file_alias,
                dangling_alias,
            ):
                link.unlink(missing_ok=True)
            link_arguments = ["-", "-", "-", "-"]
        else:
            link_arguments = [
                str(directory_alias),
                str(file_alias),
                str(dangling_alias),
                "-",
            ]
            try:
                loop_a.symlink_to(loop_b, target_is_directory=True)
                loop_b.symlink_to(loop_a, target_is_directory=True)
            except OSError:
                loop_a.unlink(missing_ok=True)
                loop_b.unlink(missing_ok=True)
            else:
                link_arguments[3] = str(loop_a)

        previous_umask: int | None = None
        if os.name != "nt":
            previous_umask = os.umask(0o077)
        try:
            runtime_env = os.environ.copy()
            runtime_env["PATH"] = os.pathsep + runtime_env.get("PATH", "")
            completed = subprocess.run(
                [
                    str(executable),
                    str(temp_dir),
                    *link_arguments,
                    native_spelling(trusted_parent.resolve()),
                    native_spelling(unsafe_parent.resolve()),
                    native_spelling(sticky_parent.resolve()),
                    native_spelling(nested_parent.resolve()),
                    resolver_name,
                    native_spelling(resolver_expected),
                ],
                cwd=temp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=runtime_env,
                check=False,
            )
        finally:
            if previous_umask is not None:
                os.umask(previous_umask)
        if completed.returncode != 0:
            raise AssertionError(
                "filesystem support harness exited with "
                f"{completed.returncode}:\n{completed.stdout}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
