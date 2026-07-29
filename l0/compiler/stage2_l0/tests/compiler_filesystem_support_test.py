#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Direct ABI coverage for the L0 Stage 2 compiler filesystem support."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L0_ROOT = REPO_ROOT / "l0"
STAGE2_SUPPORT = (
    L0_ROOT / "compiler" / "stage2_l0" / "support" / "compiler_filesystem.c"
)


def resolve_c_compiler() -> str:
    """Return one configured or available C compiler."""

    for configured in (
        os.environ.get("L0_RUNTIME_CC", "").strip(),
        os.environ.get("L0_CC", "").strip(),
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
    raise AssertionError(
        "compiler filesystem support test requires a C compiler"
    )


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
        str(STAGE2_SUPPORT),
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=L0_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"C compilation exited with {completed.returncode}:\n"
            f"{completed.stdout}"
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

int32_t l0c_fs_resolve_trusted_temp_parent(
    const uint8_t *path,
    int32_t path_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l0c_fs_join_child(
    const uint8_t *parent,
    int32_t parent_len,
    const uint8_t *child,
    int32_t child_len,
    uint8_t *output,
    int32_t output_capacity
);
int32_t l0c_fs_mkdir(
    const uint8_t *path,
    int32_t path_len,
    int32_t mode
);
int32_t l0c_fs_path_kind_nofollow(
    const uint8_t *path,
    int32_t path_len
);
int32_t l0c_fs_path_kind_follow(
    const uint8_t *path,
    int32_t path_len
);
int32_t l0c_fs_remove_regular_file(
    const uint8_t *path,
    int32_t path_len
);
int32_t l0c_fs_remove_empty_dir(
    const uint8_t *path,
    int32_t path_len
);

static int32_t path_len(const char *path) {
    size_t len = strlen(path);
    return len <= INT32_MAX ? (int32_t)len : -1;
}

static int32_t path_kind(const char *path) {
    return l0c_fs_path_kind_nofollow(
        (const uint8_t *)path,
        path_len(path)
    );
}

static int32_t path_kind_follow(const char *path) {
    return l0c_fs_path_kind_follow(
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

static int write_marker(const char *path) {
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) return 0;
    if (fwrite("marker", 1, 6, stream) != 6) {
        fclose(stream);
        return 0;
    }
    return fclose(stream) == 0;
}

static int resolved_matches(const char *input, const char *expected) {
    int32_t required = l0c_fs_resolve_trusted_temp_parent(
        (const uint8_t *)input,
        path_len(input),
        NULL,
        0
    );
    uint8_t *buffer;
    int32_t actual;
    int matches;
    if (required <= 0) return 0;
    buffer = (uint8_t *)malloc((size_t)required);
    if (buffer == NULL) return 0;
    actual = l0c_fs_resolve_trusted_temp_parent(
        (const uint8_t *)input,
        path_len(input),
        buffer,
        required
    );
    matches = actual == required &&
              (size_t)required == strlen(expected) &&
              memcmp(buffer, expected, (size_t)required) == 0;
    free(buffer);
    return matches;
}

static int joined_matches(
    const char *parent,
    const char *child,
    const char *expected
) {
    int32_t required = l0c_fs_join_child(
        (const uint8_t *)parent,
        path_len(parent),
        (const uint8_t *)child,
        path_len(child),
        NULL,
        0
    );
    uint8_t *buffer;
    int32_t actual;
    int matches;
    if (required <= 0) return 0;
    buffer = (uint8_t *)malloc((size_t)required);
    if (buffer == NULL) return 0;
    actual = l0c_fs_join_child(
        (const uint8_t *)parent,
        path_len(parent),
        (const uint8_t *)child,
        path_len(child),
        buffer,
        required
    );
    matches = actual == required &&
              (size_t)required == strlen(expected) &&
              memcmp(buffer, expected, (size_t)required) == 0;
    free(buffer);
    return matches;
}

int main(int argc, char **argv) {
    char workspace[4096];
    char child[4096];
    char non_directory_descendant[4096];
    char missing[4096];
    static const uint8_t embedded_nul[] = { 'a', '\0', 'b' };

    if (argc < 3) return 1;
    if (!resolved_matches(argv[1], argv[2])) return 2;
    if (path_kind_follow(argv[1]) != 2) return 3;
#if defined(_WIN32)
    if (!joined_matches("parent\\", "child", "parent\\child")) return 4;
#else
    if (!joined_matches("parent\\", "child", "parent\\/child")) return 4;
#endif
    if (!joined_matches("parent/", "child", "parent/child")) return 5;
    if (!joined_matches("parent", "child", "parent/child")) return 6;
    if (!make_path(
            workspace,
            sizeof(workspace),
            argv[2],
            "workspace"
        )) return 7;
    if (!make_path(child, sizeof(child), workspace, "child")) return 8;
    if (!make_path(
            non_directory_descendant,
            sizeof(non_directory_descendant),
            child,
            "descendant"
        )) return 9;
    if (!make_path(missing, sizeof(missing), workspace, "missing")) return 10;

    if (l0c_fs_mkdir(
            (const uint8_t *)workspace,
            path_len(workspace),
            0700
        ) != 1) return 11;
    if (l0c_fs_mkdir(
            (const uint8_t *)workspace,
            path_len(workspace),
            0700
        ) != 0) return 12;
    if (path_kind(workspace) != 2) return 13;
    if (path_kind(missing) != 0) return 14;
    if (path_kind_follow(missing) != 0) return 15;

#if !defined(_WIN32)
    {
        struct stat info;
        if (stat(workspace, &info) != 0) return 16;
        if ((info.st_mode & 0777) != 0700) return 17;
    }
#endif

    if (!write_marker(child)) return 20;
    if (path_kind(child) != 1) return 21;
    if (path_kind(non_directory_descendant) != 0) return 22;
    if (path_kind_follow(non_directory_descendant) != 0) return 23;
    if (l0c_fs_remove_regular_file(
            (const uint8_t *)child,
            path_len(child)
        ) != 1) return 24;
    if (path_kind(child) != 0) return 25;
    if (l0c_fs_remove_regular_file(
            (const uint8_t *)child,
            path_len(child)
        ) != 0) return 26;
    if (l0c_fs_remove_empty_dir(
            (const uint8_t *)workspace,
            path_len(workspace)
        ) != 1) return 27;
    if (l0c_fs_remove_empty_dir(
            (const uint8_t *)workspace,
            path_len(workspace)
        ) != 0) return 28;

    if (argc >= 4 && strcmp(argv[3], "-") != 0) {
        if (path_kind(argv[3]) != 3) return 30;
        if (path_kind_follow(argv[3]) != 1) return 31;
        if (l0c_fs_remove_regular_file(
                (const uint8_t *)argv[3],
                path_len(argv[3])
            ) != -1) return 32;
        if (path_kind(argv[3]) != 3) return 33;
    }

#if !defined(_WIN32)
    if (argc < 6) return 40;
    if (l0c_fs_resolve_trusted_temp_parent(
            (const uint8_t *)argv[4],
            path_len(argv[4]),
            NULL,
            0
        ) <= 0) return 41;
    if (l0c_fs_resolve_trusted_temp_parent(
            (const uint8_t *)argv[5],
            path_len(argv[5]),
            NULL,
            0
        ) != -1) return 42;
    if (argc >= 7 &&
        l0c_fs_resolve_trusted_temp_parent(
            (const uint8_t *)argv[6],
            path_len(argv[6]),
            NULL,
            0
        ) != -1) return 43;
    if (argc >= 8 &&
        strcmp(argv[7], "-") != 0 &&
        path_kind_follow(argv[7]) != -1) return 44;
#endif

    if (l0c_fs_path_kind_nofollow(embedded_nul, 3) != -1) return 50;
    if (l0c_fs_path_kind_follow(embedded_nul, 3) != -1) return 51;
    if (l0c_fs_mkdir(embedded_nul, 3, 0700) != -1) return 52;
    if (l0c_fs_mkdir(
            (const uint8_t *)argv[2],
            path_len(argv[2]),
            010000
        ) != -1) return 53;
    if (l0c_fs_path_kind_nofollow(NULL, 0) != -1) return 54;
    if (l0c_fs_path_kind_follow(NULL, 0) != -1) return 55;
    if (l0c_fs_resolve_trusted_temp_parent(
            embedded_nul, 3, NULL, 0) != -1) return 56;
    if (l0c_fs_join_child(
            embedded_nul,
            3,
            (const uint8_t *)"child",
            5,
            NULL,
            0
        ) != -1) return 57;
    return 0;
}
'''


def main() -> int:
    """Compile and execute the direct filesystem ABI harness."""

    compiler = resolve_c_compiler()
    with tempfile.TemporaryDirectory(
        prefix="l0_compiler_filesystem_support_test."
    ) as raw_temp:
        temp_dir = Path(raw_temp)
        harness = temp_dir / "filesystem_harness.c"
        harness.write_text(harness_source(), encoding="utf-8")
        executable = temp_dir / (
            "filesystem_harness.exe"
            if os.name == "nt"
            else "filesystem_harness"
        )
        compile_harness(compiler, harness, executable)

        trusted_parent = temp_dir / "trusted-parent"
        trusted_parent.mkdir(mode=0o700)
        selected_parent = trusted_parent
        link_argument = "-"

        file_target = temp_dir / "file-target"
        file_alias = temp_dir / "file-alias"
        file_target.write_bytes(b"target")
        try:
            file_alias.symlink_to(file_target)
        except OSError:
            pass
        else:
            link_argument = str(file_alias)

        if os.name == "nt":
            trust_arguments: list[str] = []
            inspection_ancestor: Path | None = None
        else:
            selected_parent = temp_dir / "trusted-parent-alias"
            selected_parent.symlink_to(
                trusted_parent,
                target_is_directory=True,
            )

            sticky_parent = temp_dir / "sticky-parent"
            sticky_parent.mkdir()
            sticky_parent.chmod(0o1777)

            unsafe_parent = temp_dir / "unsafe-parent"
            unsafe_parent.mkdir()
            unsafe_parent.chmod(0o777)

            unsafe_ancestor = temp_dir / "unsafe-ancestor"
            unsafe_ancestor.mkdir()
            unsafe_ancestor.chmod(0o777)
            nested_parent = unsafe_ancestor / "nested-parent"
            nested_parent.mkdir(mode=0o700)

            inspection_ancestor = temp_dir / "inspection-denied"
            inspection_ancestor.mkdir(mode=0o700)
            inspection_parent = inspection_ancestor / "candidate"
            inspection_parent.mkdir(mode=0o700)
            inspection_ancestor.chmod(0)
            inspection_argument = "-"
            try:
                os.stat(inspection_parent)
            except PermissionError:
                inspection_argument = str(inspection_parent)
            except OSError:
                inspection_ancestor.chmod(0o700)
                raise

            trust_arguments = [
                str(sticky_parent),
                str(unsafe_parent),
                str(nested_parent),
                inspection_argument,
            ]

        previous_umask: int | None = None
        if os.name != "nt":
            previous_umask = os.umask(0o077)
        try:
            completed = subprocess.run(
                [
                    str(executable),
                    str(selected_parent),
                    str(trusted_parent.resolve()),
                    link_argument,
                    *trust_arguments,
                ],
                cwd=L0_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                check=False,
            )
        finally:
            if previous_umask is not None:
                os.umask(previous_umask)
            if inspection_ancestor is not None:
                inspection_ancestor.chmod(0o700)
        if completed.returncode != 0:
            raise AssertionError(
                "filesystem support harness exited with "
                f"{completed.returncode}:\n{completed.stdout}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
