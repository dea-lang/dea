#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Direct ABI coverage for the L1 Stage 1 compiler filesystem support."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_INCLUDE = RUNTIME_ROOT / "include"
RUNTIME_INTERNAL = RUNTIME_ROOT / "internal"
STAGE1_SUPPORT = (
    L1_ROOT / "compiler" / "stage1_l0" / "support" / "interface_fingerprint.c"
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
        f"-I{RUNTIME_INCLUDE}",
        f"-I{RUNTIME_INTERNAL}",
        str(source),
        str(STAGE1_SUPPORT),
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

    return r'''#define SIPHASH_IMPLEMENTATION
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "dea_siphash.h"

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


def main() -> int:
    """Compile and execute the direct filesystem ABI harness."""

    compiler = resolve_c_compiler()
    with tempfile.TemporaryDirectory(
        prefix="l1_compiler_filesystem_support_test."
    ) as raw_temp:
        temp_dir = Path(raw_temp)
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
                    str(trusted_parent.resolve()),
                    str(unsafe_parent.resolve()),
                    str(sticky_parent.resolve()),
                    str(nested_parent.resolve()),
                    resolver_name,
                    str(resolver_expected),
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
