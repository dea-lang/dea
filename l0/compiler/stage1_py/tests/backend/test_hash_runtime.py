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


def test_hash_opt_string_presence_uses_distinct_domains(
    codegen_single, compile_and_run, tmp_path
):
    c_code, _ = codegen_single(
        "hash_opt_string",
        """
        module hash_opt_string;

        import sys.hash;
        import std.io;

        func main() -> int {
            let none: string? = null;
            let empty: string? = "";
            printl_i(rt_hash_opt_string(none));
            printl_i(rt_hash_opt_string(none));
            printl_i(rt_hash_opt_string(empty));
            printl_i(rt_hash_opt_string(empty));
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
    assert lines[0] != lines[2]


def test_hash_present_optional_string_keeps_optional_string_domain(
    codegen_single, compile_and_run, tmp_path
):
    c_code, diagnostics = codegen_single(
        "hash_present_optional_string_domain",
        """
        module hash_present_optional_string_domain;

        extern func hash_present_optional_string_domain(value: string?) -> int;

        func main() -> int {
            let value: string? = "abc";
            return hash_present_optional_string_domain(value);
        }
        """,
    )

    assert c_code is not None, diagnostics
    c_code += r"""
l0_int hash_present_optional_string_domain(l0_opt_string value)
{
    if (!value.has_value) return 1;
    if (rt_hash_opt_string(value) != _rt_hash_string(value.value, _L0_TAG_OPT)) return 2;
    return 0;
}
"""

    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr


def test_hash_zero_length_data_and_optional_scalars_are_deterministic(
    codegen_single, compile_and_run, tmp_path
):
    c_code, diagnostics = codegen_single(
        "hash_edges",
        """
        module hash_edges;

        import sys.hash;
        import sys.memory;

        func main() -> int {
            let left: void* = rt_alloc(1) as void*;
            let right: void* = rt_alloc(1) as void*;
            rt_memset(left, 1, 1);
            rt_memset(right, 2, 1);

            let none_bool: bool? = null;
            let none_byte: byte? = null;
            let none_int: int? = null;
            let data_ok = rt_hash_data(left, 0) == rt_hash_data(right, 0);
            let bool_ok = rt_hash_opt_bool(none_bool) == rt_hash_opt_bool(none_bool);
            let byte_ok = rt_hash_opt_byte(none_byte) == rt_hash_opt_byte(none_byte);
            let int_ok = rt_hash_opt_int(none_int) == rt_hash_opt_int(none_int);
            let ptr_ok = rt_hash_ptr(left) == rt_hash_ptr(left);
            let opt_ptr: void*? = left;
            let opt_ptr_ok = rt_hash_opt_ptr(opt_ptr) == rt_hash_opt_ptr(opt_ptr);

            rt_free(left);
            rt_free(right);
            if (data_ok && bool_ok && byte_ok && int_ok && ptr_ok && opt_ptr_ok) {
                return 0;
            }
            return 1;
        }
        """,
    )

    assert c_code is not None, diagnostics
    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr


def test_hash_optional_scalar_c_abi_ignores_inactive_payload_and_padding(
    codegen_single, compile_and_run, tmp_path
):
    c_code, diagnostics = codegen_single(
        "hash_option_abi",
        """
        module hash_option_abi;

        extern func hash_option_abi_probe() -> int;

        func main() -> int {
            return hash_option_abi_probe();
        }
        """,
    )

    assert c_code is not None, diagnostics
    c_code += r"""
l0_int hash_option_abi_probe(void)
{
    l0_opt_bool bool_a;
    l0_opt_bool bool_b;
    l0_opt_byte byte_a;
    l0_opt_byte byte_b;
    l0_opt_int int_a;
    l0_opt_int int_b;

    memset(&bool_a, 0xA5, sizeof(bool_a));
    memset(&bool_b, 0x5A, sizeof(bool_b));
    bool_a.has_value = 0;
    bool_b.has_value = 0;
    if (rt_hash_opt_bool(bool_a) != rt_hash_opt_bool(bool_b)) return 1;

    memset(&byte_a, 0xA5, sizeof(byte_a));
    memset(&byte_b, 0x5A, sizeof(byte_b));
    byte_a.has_value = 0;
    byte_b.has_value = 0;
    if (rt_hash_opt_byte(byte_a) != rt_hash_opt_byte(byte_b)) return 2;

    memset(&int_a, 0xA5, sizeof(int_a));
    memset(&int_b, 0x5A, sizeof(int_b));
    int_a.has_value = 0;
    int_b.has_value = 0;
    if (rt_hash_opt_int(int_a) != rt_hash_opt_int(int_b)) return 3;

    memset(&int_a, 0xA5, sizeof(int_a));
    memset(&int_b, 0x5A, sizeof(int_b));
    int_a.has_value = 1;
    int_b.has_value = 1;
    int_a.value = 42;
    int_b.value = 42;
    if (rt_hash_opt_int(int_a) != rt_hash_opt_int(int_b)) return 4;
    return 0;
}
"""

    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr


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
