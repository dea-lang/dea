#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz


def test_math_surface_runtime(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_surface_runtime",
        """
        module math_surface_runtime;

        import std.integer;
        import std.io;

        func print_i_opt(x: int?) {
            if (x == null) {
                printl_s("null");
                return;
            }
            printl_i(x as int);
        }

        func main() -> int {
            printl_i(emod(-7, 3));
            printl_i(ediv(-7, 3));
            printl_i(div_floor(7, -3));
            printl_i(div_ceil(7, -3));
            printl_i(div_floor(-7, -3));
            printl_i(div_ceil(-7, -3));

            printl_i(min(5, -2));
            printl_i(max(5, -2));
            printl_i(clamp(20, 0, 10));
            printl_i(clamp(-5, 0, 10));

            printl_i(sign(-9));
            printl_i(sign(0));
            printl_i(sign(9));
            printl_b(is_even(-4));
            printl_b(is_odd(-5));
            printl_b(is_multiple(-2147483648, -1));
            printl_b(is_multiple(21, -7));
            printl_b(is_multiple(22, -7));

            print_i_opt(abs(-2147483648));
            print_i_opt(abs(-17));
            print_i_opt(gcd(-48, 18));
            print_i_opt(gcd(0, 0));
            print_i_opt(gcd(-2147483648, 0));
            print_i_opt(lcm(-21, 6));
            print_i_opt(lcm(-2147483648, 1));
            print_i_opt(pow(-2, 5));
            print_i_opt(pow(0, 0));
            print_i_opt(pow(2, -1));
            print_i_opt(pow(2, 31));
            print_i_opt(isqrt(2147483647));
            print_i_opt(isqrt(-1));

            print_i_opt(align_down(17, 8));
            print_i_opt(align_down(-17, 8));
            print_i_opt(align_down(-2147483648, 3));
            print_i_opt(align_up(17, 8));
            print_i_opt(align_up(-17, 8));
            print_i_opt(align_up(-2147483648, 3));
            print_i_opt(align_up(2147483647, 2));
            printl_b(is_aligned(-16, 8));
            printl_b(is_aligned(-17, 8));
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip().splitlines() == [
        "2",
        "-3",
        "-3",
        "-2",
        "2",
        "3",
        "-2",
        "5",
        "10",
        "0",
        "-1",
        "0",
        "1",
        "true",
        "true",
        "true",
        "true",
        "false",
        "null",
        "17",
        "6",
        "0",
        "null",
        "42",
        "null",
        "-32",
        "1",
        "null",
        "null",
        "46340",
        "null",
        "16",
        "-24",
        "null",
        "24",
        "-16",
        "-2147483646",
        "null",
        "true",
        "false",
    ]


def test_math_emod_zero_divisor_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_emod_zero_divisor_panics",
        """
        module math_emod_zero_divisor_panics;

        import std.integer;

        func main() -> int {
            emod(1, 0);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: emod: divisor must be greater than 0"


def test_math_div_floor_zero_divisor_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_div_floor_zero_divisor_panics",
        """
        module math_div_floor_zero_divisor_panics;

        import std.integer;

        func main() -> int {
            div_floor(1, 0);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: div_floor: divisor must be non-zero"


def test_math_div_ceil_unrepresentable_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_div_ceil_unrepresentable_panics",
        """
        module math_div_ceil_unrepresentable_panics;

        import std.integer;

        func main() -> int {
            div_ceil(-2147483648, -1);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: div_ceil: result must be representable"


def test_math_align_up_zero_alignment_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_align_up_zero_alignment_panics",
        """
        module math_align_up_zero_alignment_panics;

        import std.integer;

        func main() -> int {
            align_up(8, 0);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert stderr.strip().splitlines()[-1] == "Software Failure: align_up: alignment must be greater than 0"


def test_math_clamp_invalid_bounds_panics(codegen_single, compile_and_run, tmp_path):
    c_code, _ = codegen_single(
        "math_clamp_invalid_bounds_panics",
        """
        module math_clamp_invalid_bounds_panics;

        import std.integer;

        func main() -> int {
            clamp(5, 10, 0);
            return 0;
        }
        """,
    )

    if c_code is None:
        return

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert not success
    assert (
        stderr.strip().splitlines()[-1]
        == "Software Failure: clamp: lower bound must be less than or equal to upper bound"
    )
