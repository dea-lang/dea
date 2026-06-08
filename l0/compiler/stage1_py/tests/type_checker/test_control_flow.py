"""
Tests for control flow edge cases: break/continue validation and loop codegen.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code


# ============================================================================
# Break/continue outside loop detection
# ============================================================================


def test_typechecker_break_outside_loop(analyze_single):
    """Test that break outside loop is rejected."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            break;
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0110")
    assert not has_error_code(result.diagnostics, "TYP-0030")


def test_typechecker_continue_outside_loop(analyze_single):
    """Test that continue outside loop is rejected."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            continue;
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0120")
    assert not has_error_code(result.diagnostics, "TYP-0030")


def test_break_inside_while_loop_ok(analyze_single):
    """Test that break inside while loop is accepted."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            while (true) {
                break;
            }
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_continue_inside_while_loop_ok(analyze_single):
    """Test that continue inside while loop is accepted."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let i: int = 0;
            while (i < 10) {
                i = i + 1;
                continue;
            }
            return i;
        }
        """,
    )

    assert not result.has_errors()


def test_break_inside_for_loop_ok(analyze_single):
    """Test that break inside for loop is accepted."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            for (let i: int = 0; i < 10; i = i + 1) {
                break;
            }
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_continue_inside_for_loop_ok(analyze_single):
    """Test that continue inside for loop is accepted."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            for (let i: int = 0; i < 10; i = i + 1) {
                continue;
            }
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_unreachable_warning_after_unconditional_continue(analyze_single):
    """Unconditional continue should mark the following statement unreachable."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            while (true) {
                continue;
                let x: int = 0;
            }
            return 0;
        }
        """,
    )

    assert not result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0030")


def test_for_loop_variable_scope_does_not_leak_to_siblings(analyze_single):
    """Oracle pin: loop variables are loop-scoped; sibling reuse is not shadowing."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let total = 0;
            for (let i: int = 0; i < 3; i = i + 1) {
                total = total + i;
            }
            while (0 < 1) {
                for (let i: int = 0; i < 3; i = i + 1) {
                    total = total + i;
                }
                break;
            }
            return total;
        }
        """,
    )

    assert not result.has_errors()
    assert not any("TYP-0021" in d.message for d in result.diagnostics)


def test_for_loop_genuine_nested_shadow_warns(analyze_single):
    """A genuinely nested loop variable shadows the outer one exactly once."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let total = 0;
            for (let i: int = 0; i < 3; i = i + 1) {
                for (let i: int = 0; i < 2; i = i + 1) {
                    total = total + i;
                }
            }
            return total;
        }
        """,
    )

    assert not result.has_errors()
    assert sum("TYP-0021" in d.message for d in result.diagnostics) == 1


def test_no_unreachable_warning_after_conditional_continue(analyze_single):
    """Conditional continue should not mark following statements unreachable."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let x: int = 0;
            for (x = 0; x < 5; x = x + 1) {
                if (x != 0) continue;
                if (x != 0) break;
                x = x + 1;
            }
            return x;
        }
        """,
    )

    assert not has_error_code(result.diagnostics, "TYP-0030")


def test_break_in_with_inline_cleanup_outside_loop(analyze_single):
    """Invalid inline cleanup break should not poison later reachability."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            with (let x: int = 0 => break) {
            }
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0110")
    assert not has_error_code(result.diagnostics, "TYP-0030")


def test_continue_in_with_inline_cleanup_outside_loop(analyze_single):
    """Invalid inline cleanup continue should not poison later reachability."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            with (let x: int = 0 => continue) {
            }
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0120")
    assert not has_error_code(result.diagnostics, "TYP-0030")


# ============================================================================
# Nested loop break/continue
# ============================================================================


def test_codegen_nested_loop_break(codegen_single):
    """Test that break in nested loop generates correct C code."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;
        func f() -> int {
            let result: int = 0;
            while (true) {
                while (true) {
                    result = 1;
                    break;
                }
                result = 2;
                break;
            }
            return result;
        }
        """,
    )

    if c_code is None:
        assert False, f"Analysis failed: {[d.message for d in diags]}"

    # Should have multiple break goto statements
    assert c_code.count("goto __lbrk_") >= 2


def test_break_in_nested_if_inside_loop(analyze_single):
    """Test break inside if inside loop is valid."""
    result = analyze_single(
        "main",
        """
        module main;
        func f(x: int) -> int {
            while (true) {
                if (x > 0) {
                    break;
                }
            }
            return x;
        }
        """,
    )

    assert not result.has_errors()


# ============================================================================
# For loop edge cases
# ============================================================================


def test_codegen_for_loop_empty_clauses(codegen_single):
    """Test for loop with all empty clauses generates correct C."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;
        func f() -> int {
            for (;;) {
                break;
            }
            return 0;
        }
        """,
    )

    if c_code is None:
        assert False, f"Analysis failed: {[d.message for d in diags]}"

    # Should generate while(1) or for(;;) pattern
    assert "while" in c_code or "for" in c_code


def test_for_loop_only_condition(analyze_single):
    """Test for loop with only condition."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let i: int = 0;
            for (; i < 10;) {
                i = i + 1;
            }
            return i;
        }
        """,
    )

    assert not result.has_errors()


def test_codegen_for_loop_continue_runs_update(codegen_single, compile_and_run, tmp_path):
    """Continue in for loop should jump to update and terminate."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;
        import std.io;
        func main() {
            let x = 0;
            for (x = 0; x < 5; x = x + 1) {
                if (x != 0) continue;
                if (x != 0) break;
                printl_i(x);
            }
            printl_s("done");
            printl_i(x);
        }
        """,
    )

    if c_code is None:
        assert False, f"Analysis failed: {[d.message for d in diags]}"

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"Program should exit 0: stderr={stderr}"
    assert stdout == "0\ndone\n5\n"


def test_codegen_break_continue_lower_to_goto(codegen_single):
    """Break/continue should be lowered to goto labels (no C break/continue)."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;
        func f() -> int {
            let x: int = 0;
            for (x = 0; x < 10; x = x + 1) {
                if (x == 1) { continue; }
                if (x == 2) { break; }
            }
            return x;
        }
        """,
    )

    if c_code is None:
        assert False, f"Analysis failed: {[d.message for d in diags]}"

    assert "goto __lbrk_" in c_code
    assert "goto __lcont_" in c_code
    assert "break;" not in c_code
    assert "continue;" not in c_code


def test_for_loop_only_init(analyze_single):
    """Test for loop with only init."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            for (let i: int = 0;;) {
                break;
            }
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_for_loop_only_update(analyze_single):
    """Test for loop with only update."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let i: int = 0;
            for (;; i = i + 1) {
                if (i >= 10) {
                    break;
                }
            }
            return i;
        }
        """,
    )

    assert not result.has_errors()
