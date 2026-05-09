#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz


def test_string_search_helpers_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "string_search_helpers",
        """
        module string_search_helpers;

        import std.io;
        import std.string;

        func bool_to_int(v: bool) -> int {
            if (v) {
                return 1;
            }
            return 0;
        }

        func main() -> int {
            printl_i(find_s("banana", "ana"));
            printl_i(find_s("banana", "xyz"));
            printl_i(find_s("banana", ""));

            printl_i(find_from_s("banana", "ana", 0));
            printl_i(find_from_s("banana", "ana", 2));
            printl_i(find_from_s("banana", "ana", 4));
            printl_i(find_from_s("banana", "", 6));
            printl_i(find_from_s("banana", "", 7));

            printl_i(bool_to_int(contains_s("banana", "nan")));
            printl_i(bool_to_int(contains_s("banana", "zzz")));

            printl_i(bool_to_int(starts_with_s("banana", "ban")));
            printl_i(bool_to_int(starts_with_s("banana", "ana")));
            printl_i(bool_to_int(starts_with_s("banana", "")));

            printl_i(bool_to_int(ends_with_s("banana", "ana")));
            printl_i(bool_to_int(ends_with_s("banana", "ban")));
            printl_i(bool_to_int(ends_with_s("banana", "")));
            printl_i(bool_to_int(ends_with_s("abcabc", "abc")));

            printl_i(find_last_s("banana", "ana"));
            printl_i(find_last_s("banana", "ban"));
            printl_i(find_last_s("banana", ""));
            printl_i(find_last_s("banana", "zzz"));
            printl_i(find_last_s("aaaa", "aa"));

            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip().splitlines() == [
        "1",
        "-1",
        "0",
        "1",
        "3",
        "-1",
        "6",
        "-1",
        "1",
        "0",
        "1",
        "0",
        "1",
        "1",
        "0",
        "1",
        "1",
        "3",
        "0",
        "6",
        "-1",
        "2",
    ]


def test_string_byte_conversions_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "string_byte_conversions",
        """
        module string_byte_conversions;

        import std.io;
        import std.string;
        import sys.memory;

        func main() -> int {
            let one: string = byte_to_s(65 as byte);
            printl_i(len_s(one));
            printl_i(char_at_s(one, 0) as int);

            let raw: void* = rt_calloc(3, 1) as void*;
            let b0: byte* = rt_array_element(raw, 1, 0) as byte*;
            let b1: byte* = rt_array_element(raw, 1, 1) as byte*;
            let b2: byte* = rt_array_element(raw, 1, 2) as byte*;
            *b0 = 88 as byte;
            *b1 = 89 as byte;
            *b2 = 90 as byte;

            let many: string = bytes_to_s(raw as byte*, 3);
            printl_i(len_s(many));
            printl_i(char_at_s(many, 0) as int);
            printl_i(char_at_s(many, 1) as int);
            printl_i(char_at_s(many, 2) as int);
            rt_free(raw);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip().splitlines() == [
        "1",
        "65",
        "3",
        "88",
        "89",
        "90",
    ]


def test_std_io_stale_errno_does_not_cause_false_failures(
    codegen_single, compile_and_run, tmp_path
):
    missing_path = (tmp_path / "definitely-missing-for-errno-probe.txt").as_posix()
    valid_path = (tmp_path / "io-errno-probe.txt").as_posix()

    c_code, _ = codegen_single(
        "std_io_errno_probe",
        f"""
        module std_io_errno_probe;

        import std.fs;
        import std.io;
        import std.string;
        import sys.rt;

        func main() -> int {{
            // Seed errno with a failing file probe before std.fs calls.
            let missing = rt_file_info("{missing_path}");
            if (missing.exists) {{
                return 11;
            }}

            let w = write_file("{valid_path}", "ok");
            if (w == null) {{
                printl_s("write-null");
                return 12;
            }}

            let rd = read_file("{valid_path}");
            if (rd == null) {{
                printl_s("read-null");
                return 13;
            }}

            if (!eq_s(rd as string, "ok")) {{
                printl_s("mismatch");
                return 14;
            }}

            printl_s("ok");
            return 0;
        }}
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip() == "ok"


def test_string_text_helpers_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "string_text_helpers",
        """
        module string_text_helpers;

        import std.io;
        import std.string;
        import std.text;
        import std.vector;

        func bool_to_int(v: bool) -> int {
            if (v) {
                return 1;
            }
            return 0;
        }

        func emit_vec(v: VectorString*) {
            printl_i(vs_size(v));
            for (let i = 0; i < vs_size(v); i = i + 1) {
                printl_s(concat3_s("[", vs_get(v, i), "]"));
            }
        }

        func main() -> int {
            printl_i(bool_to_int(is_empty_s("")));
            printl_i(bool_to_int(is_empty_s("x")));
            printl_s(trim_s(" \\t hi \\n"));

            with (let p1 = split_s("a,,b", ",") => vs_free(p1)) {
                emit_vec(p1);
            }

            with (let p2 = split_s("a--b----c", "--") => vs_free(p2)) {
                emit_vec(p2);
            }

            with (let p3 = split_s("", ",") => vs_free(p3)) {
                emit_vec(p3);
            }

            with (let lines = lines_s("a\\r\\n\\r\\nb\\n") => vs_free(lines)) {
                emit_vec(lines);
            }

            with (let parts = vs_create(3) => vs_free(parts)) {
                vs_push(parts, "x");
                vs_push(parts, "");
                vs_push(parts, "z");
                printl_s(join_s(parts, ":"));
            }

            printl_s(replace_s("banana", "na", "X"));
            printl_s(replace_s("aaaa", "aa", "b"));
            printl_s(replace_s("abc", "q", "w"));
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip().splitlines() == [
        "1",
        "0",
        "hi",
        "3",
        "[a]",
        "[]",
        "[b]",
        "4",
        "[a]",
        "[b]",
        "[]",
        "[c]",
        "1",
        "[]",
        "3",
        "[a]",
        "[]",
        "[b]",
        "x::z",
        "baXX",
        "bb",
        "abc",
    ]


def test_split_s_empty_separator_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "split_empty_separator_panics",
        """
        module split_empty_separator_panics;

        import std.text;

        func main() -> int {
            split_s("abc", "");
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: split_s: separator must be non-empty"


def test_replace_s_empty_old_pattern_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "replace_empty_old_panics",
        """
        module replace_empty_old_panics;

        import std.text;

        func main() -> int {
            replace_s("abc", "", "x");
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: replace_s: old pattern must be non-empty"
