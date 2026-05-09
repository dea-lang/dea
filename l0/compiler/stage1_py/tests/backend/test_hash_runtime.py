#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz


def test_hash_deterministic_outputs(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_deterministic",
        """
        module hash_deterministic;

        import sys.hash;
        import std.io;

        func main() -> int {
            let hash_i_1: int = rt_hash_int(123);
            let hash_i_2: int = rt_hash_int(123);
            let hash_b_1: int = rt_hash_bool(true);
            let hash_b_2: int = rt_hash_bool(true);
            let hash_byte_1: int = rt_hash_byte(0x2A as byte);
            let hash_byte_2: int = rt_hash_byte(0x2A as byte);
            let hash_s_1: int = rt_hash_string("abc");
            let hash_s_2: int = rt_hash_string("abc");

            printl_i(hash_i_1);
            printl_i(hash_i_2);
            printl_i(hash_b_1);
            printl_i(hash_b_2);
            printl_i(hash_byte_1);
            printl_i(hash_byte_2);
            printl_i(hash_s_1);
            printl_i(hash_s_2);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    lines = stdout.strip().splitlines()
    assert lines[0] == lines[1]
    assert lines[2] == lines[3]
    assert lines[4] == lines[5]
    assert lines[6] == lines[7]


def test_hash_opt_string_null_matches_empty(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_opt_string",
        """
        module hash_opt_string;

        import sys.hash;
        import std.io;

        func main() -> int {
            let none: string? = null;
            let empty: string? = "";
            let hash_none: int = rt_hash_opt_string(none);
            let hash_empty: int = rt_hash_opt_string(empty);
            printl_i(hash_none);
            printl_i(hash_empty);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    lines = stdout.strip().splitlines()
    assert lines[0] == lines[1]


def test_hash_data_null_pointer_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_data_null",
        """
        module hash_data_null;

        import sys.hash;

        func main() -> int {
            let ptr: void* = null;
            rt_hash_data(ptr, 1);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: rt_hash_data: null data pointer"


def test_hash_data_negative_size_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_data_negative_size",
        """
        module hash_data_negative_size;

        import sys.hash;
        import sys.memory;

        func main() -> int {
            let ptr: void* = rt_calloc(1, 1) as void*;
            rt_hash_data(ptr, -1);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: rt_hash_data: negative size"


def test_hash_ptr_null_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_ptr_null",
        """
        module hash_ptr_null;

        import sys.hash;

        func main() -> int {
            let ptr: void* = null;
            rt_hash_ptr(ptr);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: rt_hash_ptr: null pointer"


def test_hash_opt_ptr_null_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "hash_opt_ptr_null",
        """
        module hash_opt_ptr_null;

        import sys.hash;

        func main() -> int {
            let ptr: void*? = null;
            rt_hash_opt_ptr(ptr);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: rt_hash_opt_ptr: unwrap of empty optional"
