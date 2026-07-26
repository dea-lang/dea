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
int32_t l1c_fs_remove_empty_dir(
    const uint8_t *path,
    int32_t path_len
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
    static const uint8_t embedded_nul[] = { 'a', '\0', 'b' };

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

    if (argc >= 5) {
        if (path_kind(argv[2]) != 3) return 40;
        if (path_kind_follow(argv[2]) != 2) return 41;
        if (l1c_fs_mkdir(
                (const uint8_t *)argv[2],
                path_len(argv[2]),
                0700
            ) != 0) return 42;

        if (path_kind(argv[3]) != 3) return 43;
        if (path_kind_follow(argv[3]) != 1) return 44;

        if (path_kind(argv[4]) != 3) return 45;
        if (path_kind_follow(argv[4]) != 0) return 46;
        if (l1c_fs_mkdir(
                (const uint8_t *)argv[4],
                path_len(argv[4]),
                0700
            ) != 0) return 47;
    }

    if (argc >= 6) {
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

    remove(source_collision);
    remove(destination);
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

        directory_target = temp_dir / "directory-target"
        directory_alias = temp_dir / "directory-alias"
        file_target = temp_dir / "file-target"
        file_alias = temp_dir / "file-alias"
        dangling_alias = temp_dir / "dangling-directory-alias"
        loop_a = temp_dir / "loop-a"
        loop_b = temp_dir / "loop-b"
        directory_target.mkdir()
        file_target.write_bytes(b"target")
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
            link_arguments: list[str] = []
        else:
            link_arguments = [
                str(directory_alias),
                str(file_alias),
                str(dangling_alias),
            ]
            try:
                loop_a.symlink_to(loop_b, target_is_directory=True)
                loop_b.symlink_to(loop_a, target_is_directory=True)
            except OSError:
                loop_a.unlink(missing_ok=True)
                loop_b.unlink(missing_ok=True)
            else:
                link_arguments.append(str(loop_a))

        previous_umask: int | None = None
        if os.name != "nt":
            previous_umask = os.umask(0o077)
        try:
            completed = subprocess.run(
                [str(executable), str(temp_dir), *link_arguments],
                cwd=L1_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
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
