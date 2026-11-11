#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from l0_backend import Backend
from l0_driver import L0Driver
import pytest


_SUPPLIED_INT_C = """

/**
 * Read one runtime integer independently of Dea constant evaluation.
 *
 * @return The integer supplied on standard input.
 */
l0_int supplied_int(void) {
    int value;
    if (scanf("%d", &value) != 1) {
        abort();
    }
    return (l0_int)value;
}
"""


@pytest.mark.parametrize("mode", ("checked", "check-basic", "unchecked"))
def test_runtime_negation_boundaries_and_single_evaluation(
    mode, analyze_single, compile_and_run, tmp_path
):
    """Preserve runtime negation values, byte promotion, and one evaluation."""
    result = analyze_single(
        "negation",
        """
        module negation;
        import std.io;
        extern func supplied_int() -> int;
        let calls: int = 0;
        let minimum: int = -2147483648;
        func negate(value: int) -> int { return -value; }
        func negate_byte(value: byte) -> int { return -value; }
        func next_value() -> int { calls = calls + 1; return 17; }
        func main() -> int {
            for (let i = 0; i < 5; i = i + 1) {
                printl_i(negate(supplied_int()));
            }
            printl_i(negate_byte(0 as byte));
            printl_i(negate_byte(1 as byte));
            printl_i(negate_byte(255 as byte));
            printl_i(-next_value());
            printl_i(calls);
            printl_i(minimum);
            if (!false) { printl_i(-1); }
            return 0;
        }
        """,
    )
    assert not result.has_errors(), result.diagnostics
    result.context.rt_check_basic = mode == "check-basic"
    result.context.rt_unchecked = mode == "unchecked"
    generated = Backend(result).generate()
    assert "return (_rt_isub(0, value));" in generated
    success, stdout, stderr = compile_and_run(
        generated + _SUPPLIED_INT_C, tmp_path, "-2147483647 -1 0 1 2147483647\n"
    )
    assert success, stderr
    assert stdout.splitlines() == [
        "2147483647", "1", "0", "-1", "-2147483647", "0", "-1", "-255",
        "-17", "1", "-2147483648", "-1",
    ]


@pytest.mark.parametrize("mode", ("checked", "check-basic", "unchecked"))
def test_runtime_minimum_negation_is_a_defined_failure(
    mode, analyze_single, compile_and_run, tmp_path
):
    """Reject runtime INT32_MIN negation independently of pointer checking."""
    result = analyze_single(
        "negation",
        """
        module negation;
        extern func supplied_int() -> int;
        func negate(value: int) -> int { return -value; }
        func main() -> int { return negate(supplied_int()); }
        """,
    )
    assert not result.has_errors(), result.diagnostics
    result.context.rt_check_basic = mode == "check-basic"
    result.context.rt_unchecked = mode == "unchecked"
    success, _, stderr = compile_and_run(
        Backend(result).generate() + _SUPPLIED_INT_C, tmp_path, "-2147483648\n"
    )
    assert not success
    assert "Software Failure: integer subtraction overflow" in stderr


def test_arithmetic_overflow_aborts(tmp_path, write_l0_file, search_paths, compile_and_run):
    write_l0_file(
        "overflow",
        """
        module overflow;

        import std.io;

        func main() -> int {
            let max: int = 2147483647;
            let y: int = max + 1;
            printl_i(y);
            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("overflow")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert "Software Failure: integer addition overflow" in stderr.strip().splitlines()[-1]


def test_nested_control_flow_executes(tmp_path, write_l0_file, search_paths, compile_and_run):
    write_l0_file(
        "control",
        """
        module control;

        import std.io;

        enum Flag { Yes(); No(); }

        func inner(v: int) -> int {
            if (v > 10) {
                match (Yes()) {
                    Yes() => { return 1; }
                    No() => { return -1; }
                }
            } else {
                return 0;
            }
        }

        func main() -> int {
            let res: int = 0;
            if (true) {
                if (false) {
                    res = -10;
                } else {
                    res = inner(20);
                }
            } else {
                res = inner(5);
            }
            printl_i(res);
            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("control")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip().splitlines()[-1] == "1"
