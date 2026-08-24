#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import json

from conftest import has_error_code


CLOSE_FAILURE_HARNESS = r"""
#include <stdio.h>
#include <sys/stat.h>

static int close_should_fail = 0;
static int close_calls = 0;
static int stat_calls = 0;
static int remove_calls = 0;
static int injected_close(FILE *stream);
#if defined(_WIN32)
static int injected_stat(const char *path, struct _stat64 *buffer);
#else
static int injected_stat(const char *path, struct stat *buffer);
#endif
static int injected_remove(const char *path);

#define DEA_RUNTIME_FCLOSE injected_close
#define DEA_RUNTIME_FILE_INFO_STAT injected_stat
#define DEA_RUNTIME_REMOVE injected_remove
#define SIPHASH_IMPLEMENTATION
#include "l0_runtime.h"

static int injected_close(FILE *stream) {
    int actual = fclose(stream);
    close_calls += 1;
    if (actual != 0) return actual;
    return close_should_fail ? EOF : 0;
}

#if defined(_WIN32)
static int injected_stat(const char *path, struct _stat64 *buffer) {
#else
static int injected_stat(const char *path, struct stat *buffer) {
#endif
    (void)path;
    (void)buffer;
    stat_calls += 1;
    return -1;
}

static int injected_remove(const char *path) {
    (void)path;
    remove_calls += 1;
    return -1;
}

int main(void) {
    char path_bytes[] = %(path)s;
    char payload_bytes[] = "x";
    l0_string path = L0_STRING_CONST(path_bytes, (l0_int)(sizeof(path_bytes) - 1));
    l0_string payload = L0_STRING_CONST(payload_bytes, 1);

    struct l0_sys_rt_RtFileInfo info = rt_file_info(L0_STRING_EMPTY);
    if (info.exists || info.size.has_value) return 2;
    if (rt_delete_file(L0_STRING_EMPTY)) return 3;
    if (stat_calls != 0 || remove_calls != 0) return 9;

    close_should_fail = 0;
    if (!rt_write_file_all(path, L0_STRING_EMPTY)) return 4;
    close_should_fail = 1;
    if (rt_write_file_all(path, L0_STRING_EMPTY)) return 5;
    close_should_fail = 0;
    if (!rt_write_file_all(path, payload)) return 6;
    close_should_fail = 1;
    if (rt_write_file_all(path, payload)) return 7;
    if (close_calls != 4) return 8;

    remove(path_bytes);
    return 0;
}
"""


def test_l0_runtime_filesystem_boundaries_and_close_failures(compile_and_run, tmp_path):
    path = json.dumps((tmp_path / "close-failure-probe.txt").as_posix())
    success, _stdout, stderr = compile_and_run(
        CLOSE_FAILURE_HARNESS % {"path": path}, tmp_path, strict_c99=True
    )
    assert success, stderr


def test_shared_stdlib_path_and_fs_helpers_runtime(
    codegen_single, compile_and_run, tmp_path
):
    file_path = (tmp_path / "shared-stdlib-fs-path.txt").as_posix()
    missing_path = (tmp_path / "shared-stdlib-fs-path-missing.txt").as_posix()

    c_code, _ = codegen_single(
        "shared_stdlib_path_fs_helpers",
        f"""
        module shared_stdlib_path_fs_helpers;

        import std.fs;
        import std.io;
        import std.path;
        import std.string;

        func bool_to_int(v: bool) -> int {{
            if (v) {{
                return 1;
            }}
            return 0;
        }}

        func main() -> int {{
            let empty = stat("");
            if (empty.exists || empty.size != null) {{
                return 8;
            }}
            if (delete_file("") != null) {{
                return 9;
            }}
            if (write_file("", "") != null) {{
                return 10;
            }}

            printl_i(bool_to_int(is_sep('/' as byte)));
            printl_i(bool_to_int(is_sep('\\\\' as byte)));
            printl_i(bool_to_int(is_absolute("/tmp/demo.l0")));
            printl_i(bool_to_int(is_absolute("C:\\\\tmp\\\\demo.l0")));
            printl_i(bool_to_int(!is_absolute("demo.l0")));
            printl_i(bool_to_int(has_parent("src/demo.l0")));
            printl_s(basename("src/demo.l0"));
            printl_s(parent("src/demo.l0"));
            printl_s(stem("src/demo.name.l0"));
            printl_s(join("src", "demo.l0"));
            printl_i(bool_to_int(has_extension("src/demo.l0", ".l0")));
            printl_i(bool_to_int(has_extension("src/demo.l0", "l0")));
            printl_i(bool_to_int(!has_extension(".gitignore", "gitignore")));

            let missing = stat("{missing_path}");
            printl_i(bool_to_int(!missing.exists));

            let wrote = write_file("{file_path}", "abc");
            if (wrote == null) {{
                return 11;
            }}

            let info = stat("{file_path}");
            printl_i(bool_to_int(info.exists));
            printl_i(bool_to_int(info.is_file));
            printl_i(bool_to_int(!info.is_dir));
            printl_i(bool_to_int(is_dir(".")));

            let size = file_size("{file_path}");
            if (size == null) {{
                return 12;
            }}
            printl_i(size as int);

            let mtime = mtime_sec("{file_path}");
            if (mtime == null) {{
                printl_i(-1);
            }} else {{
                printl_i(bool_to_int((mtime as int) >= 0));
            }}

            let deleted = delete_file("{file_path}");
            if (deleted == null) {{
                return 13;
            }}
            printl_i(bool_to_int(!exists("{file_path}")));
            return 0;
        }}
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.splitlines() == [
        "1",
        "1",
        "1",
        "1",
        "1",
        "1",
        "demo.l0",
        "src",
        "demo.name",
        "src/demo.l0",
        "1",
        "1",
        "1",
        "1",
        "1",
        "1",
        "1",
        "1",
        "3",
        "1",
        "1",
    ]


def test_shared_safe_byte_array_stdio_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "shared_safe_byte_array_stdio_runtime",
        """
        module shared_safe_byte_array_stdio_runtime;

        import std.array;
        import std.io;

        func main() -> int {
            with (
                let stdout_buf = ba_create(3) => ba_free(stdout_buf),
                let stderr_buf = ba_create(3) => ba_free(stderr_buf),
                let probe_buf = ba_create(1) => ba_free(probe_buf)
            ) {
                ba_set(stdout_buf, 0, 65 as byte);
                ba_set(stdout_buf, 1, 0 as byte);
                ba_set(stdout_buf, 2, 66 as byte);

                ba_set(stderr_buf, 0, 88 as byte);
                ba_set(stderr_buf, 1, 0 as byte);
                ba_set(stderr_buf, 2, 89 as byte);

                let wrote_stdout = write_stdout_some(stdout_buf, 0, 3);
                if (wrote_stdout == null || (wrote_stdout as int) != 3) {
                    return 11;
                }

                let wrote_stderr = write_stderr_all(stderr_buf, 0, 3);
                if (wrote_stderr == null) {
                    return 12;
                }

                let nread = read_stdin_some(probe_buf, 0, 1);
                if (nread == null) {
                    return 13;
                }
                if ((nread as int) != 0) {
                    return 14;
                }
            }
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout == "A\x00B"
    assert stderr == "X\x00Y"


def test_shared_stdlib_raw_stdio_signature_removed(analyze_single):
    result = analyze_single(
        "shared_stdlib_raw_stdio_signature_removed",
        """
        module shared_stdlib_raw_stdio_signature_removed;

        import std.io;
        import sys.memory;

        func main() -> int {
            with (let buf = rt_calloc(3, 1) as void* => rt_free(buf)) {
                let wrote = write_stdout_some(buf as byte*, 3);
                if (wrote == null) {
                    return 1;
                }
            }
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0183")


def test_shared_file_helpers_removed_from_std_io(analyze_single):
    result = analyze_single(
        "shared_file_helpers_removed_from_std_io",
        """
        module shared_file_helpers_removed_from_std_io;

        import std.io;

        func main() -> int {
            let text = read_file("missing.txt");
            if (text == null) {
                return 1;
            }
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0189")


def test_shared_rt_file_exists_removed(analyze_single):
    result = analyze_single(
        "shared_rt_file_exists_removed",
        """
        module shared_rt_file_exists_removed;

        import sys.rt;

        func main() -> int {
            let found = rt_file_exists("missing.txt");
            if (found) {
                return 1;
            }
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0189")


def test_shared_unsafe_raw_stdio_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "shared_unsafe_raw_stdio_runtime",
        """
        module shared_unsafe_raw_stdio_runtime;

        import sys.memory;

        func main() -> int {
            with (
                let stdout_buf = rt_calloc(3, 1) as void* => rt_free(stdout_buf),
                let stderr_buf = rt_calloc(3, 1) as void* => rt_free(stderr_buf),
                let probe_buf = rt_calloc(1, 1) as void* => rt_free(probe_buf)
            ) {
                let out0 = rt_array_element(stdout_buf, 1, 0) as byte*;
                let out1 = rt_array_element(stdout_buf, 1, 1) as byte*;
                let out2 = rt_array_element(stdout_buf, 1, 2) as byte*;
                *out0 = 67 as byte;
                *out1 = 0 as byte;
                *out2 = 68 as byte;

                let err0 = rt_array_element(stderr_buf, 1, 0) as byte*;
                let err1 = rt_array_element(stderr_buf, 1, 1) as byte*;
                let err2 = rt_array_element(stderr_buf, 1, 2) as byte*;
                *err0 = 90 as byte;
                *err1 = 0 as byte;
                *err2 = 87 as byte;

                let wrote_stdout = rt_stdout_write(stdout_buf as byte*, 3);
                if (wrote_stdout != 3) {
                    return 21;
                }

                let wrote_stderr = rt_stderr_write(stderr_buf as byte*, 3);
                if (wrote_stderr != 3) {
                    return 22;
                }

                let nread = rt_stdin_read(probe_buf as byte*, 1);
                if (nread != 0) {
                    return 23;
                }
            }
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout == "C\x00D"
    assert stderr == "Z\x00W"
