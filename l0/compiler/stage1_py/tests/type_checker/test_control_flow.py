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


def test_for_header_loop_control_requires_outer_loop(analyze_single):
    """Header loop control is outside the loop being initialized."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            for (break; true; continue) {
            }
            return 0;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0110")
    assert has_error_code(result.diagnostics, "TYP-0120")


def test_for_header_loop_control_accepts_outer_loop(analyze_single):
    """An enclosing loop makes init/update loop control valid."""
    result = analyze_single(
        "main",
        """
        module main;
        func f() -> int {
            let outer: int = 0;
            while (outer < 2) {
                outer = outer + 1;
                for (continue; false; break) {
                }
            }
            return outer;
        }
        """,
    )

    assert not result.has_errors()


def test_loop_body_revival_is_not_definite_after_zero_iterations(analyze_single):
    """A loop body cannot revive a dropped value on the zero-iteration path."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            drop p;
            while (false) {
                p = new Box(2);
            }
            return p.value;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0150")


def test_loop_fixed_point_rejects_second_iteration_use_after_drop(analyze_single):
    """Backedge liveness is applied to uses at the next iteration head."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            let i: int = 0;
            while (i < 2) {
                i = i + p.value;
                drop p;
            }
            return 0;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0150")


def test_loop_fixed_point_rechecks_condition_liveness(analyze_single):
    """The settled loop head applies liveness to condition variable uses."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            while (p.value > 0) {
                drop p;
            }
            return 0;
        }
        """,
    )

    assert sum("TYP-0150" in diag.message for diag in result.diagnostics) == 1


def test_loop_replay_emits_semantic_condition_diagnostics_once(analyze_single):
    """Condition semantics and intrinsic metadata are not replayed at convergence."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            while (sizeof(int)) {
                drop p;
            }
            let q: Box* = new Box(2);
            for (let i: int = 0; sizeof(void); i = i + 1) {
                drop q;
            }
            return 0;
        }
        """,
    )

    messages = [diag.message for diag in result.diagnostics]
    assert sum("TYP-0080" in message for message in messages) == 1
    assert sum("TYP-0090" in message for message in messages) == 1
    assert sum("TYP-0240" in message for message in messages) == 1


def test_assignment_rhs_cannot_read_dropped_target(analyze_single):
    """Revival happens after evaluating the assignment RHS."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            drop p;
            p = p;
            return 0;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0150")


def test_unreachable_assignment_after_break_cannot_revive_loop_liveness(analyze_single):
    """Unreachable statements after break cannot affect post-loop liveness."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            while (true) {
                drop p;
                break;
                p = new Box(2);
            }
            return p.value;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0030")
    assert has_error_code(result.diagnostics, "TYP-0150")


def test_unreachable_assignment_after_continue_cannot_revive_loop_liveness(analyze_single):
    """Unreachable statements after continue cannot affect backedge liveness."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            let i: int = 0;
            while (i < 2) {
                i = i + 1;
                drop p;
                continue;
                p = new Box(2);
            }
            return p.value;
        }
        """,
    )

    assert has_error_code(result.diagnostics, "TYP-0030")
    assert has_error_code(result.diagnostics, "TYP-0150")


def test_returning_loop_exit_does_not_poison_post_loop_liveness(analyze_single):
    """A returned path does not reach statements after the loop."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f(flag: bool) -> int {
            let p: Box* = new Box(1);
            while (flag) {
                drop p;
                return 0;
            }
            return p.value;
        }
        """,
    )

    assert not has_error_code(result.diagnostics, "TYP-0150")
    assert not has_error_code(result.diagnostics, "TYP-0062")


def test_for_header_break_does_not_apply_unexecuted_body_liveness(analyze_single):
    """A for-header break exits before the for body can mutate liveness."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        func f() -> int {
            let p: Box* = new Box(1);
            while (true) {
                for (break; false;) {
                    drop p;
                }
            }
            return p.value;
        }
        """,
    )

    assert not has_error_code(result.diagnostics, "TYP-0150")
    assert not has_error_code(result.diagnostics, "TYP-0062")


def test_alternative_branches_isolate_and_meet_liveness(analyze_single):
    """Sibling mutations are isolated and only reachable fallthrough states meet."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        enum Choice { A; B; }

        func match_sibling(choice: Choice) -> int {
            let p: Box* = new Box(1);
            drop p;
            match (choice) {
                A => { p = new Box(2); }
                B => { return p.value; }
            }
            return 0;
        }

        func match_partial_revival(choice: Choice) -> int {
            let p: Box* = new Box(1);
            drop p;
            match (choice) {
                A => { p = new Box(2); }
                B => { null; }
            }
            return p.value;
        }

        func match_partial_drop(choice: Choice) -> int {
            let p: Box* = new Box(1);
            match (choice) {
                A => { drop p; }
                B => { let seen: int = p.value; }
            }
            return p.value;
        }

        func case_partial_revival(tag: int) -> int {
            let p: Box* = new Box(1);
            drop p;
            case (tag) {
                0 => { p = new Box(2); }
                _ => { null; }
            }
            return p.value;
        }
        """,
    )

    assert sum("TYP-0150" in diag.message for diag in result.diagnostics) == 4


def test_returning_alternatives_do_not_poison_liveness_meet(analyze_single):
    """Returning alternatives are excluded and complete revival is accepted."""
    result = analyze_single(
        "main",
        """
        module main;
        struct Box { value: int; }
        enum Choice { A; B; }

        func returning_arm(choice: Choice) -> int {
            let p: Box* = new Box(1);
            drop p;
            match (choice) {
                A => { return 0; }
                B => { p = new Box(2); }
            }
            return p.value;
        }

        func every_arm_revives(choice: Choice) -> int {
            let p: Box* = new Box(1);
            drop p;
            match (choice) {
                A => { p = new Box(2); }
                B => { p = new Box(3); }
            }
            return p.value;
        }

        func sibling_drop_isolated(choice: Choice) -> int {
            let p: Box* = new Box(1);
            match (choice) {
                A => { drop p; return 0; }
                B => { return p.value; }
            }
        }

        func unreachable_wildcard_is_dead(choice: Choice) -> int {
            let p: Box* = new Box(1);
            drop p;
            match (choice) {
                A => { p = new Box(2); }
                B => { p = new Box(3); }
                _ => { let dead: int = p.value; }
            }
            return p.value;
        }

        func unreachable_wildcard_cannot_break(choice: Choice) -> int {
            let p: Box* = new Box(1);
            while (true) {
                match (choice) {
                    A => { return 0; }
                    B => { return 1; }
                    _ => { drop p; break; }
                }
            }
            return p.value;
        }

        func exhaustive_case_stops(tag: int) -> int {
            let p: Box* = new Box(1);
            while (true) {
                case (tag) {
                    0 => { continue; }
                    _ => { drop p; break; }
                }
                return p.value;
            }
            return 0;
        }
        """,
    )

    assert not has_error_code(result.diagnostics, "TYP-0150")
    assert not has_error_code(result.diagnostics, "TYP-0062")


def test_loops_do_not_satisfy_required_return_policy(analyze_single):
    """Conservative return analysis does not treat loop bodies as proof."""
    result = analyze_single(
        "main",
        """
        module main;
        func infinite_while() -> int {
            while (true) {
                return 1;
            }
        }
        func infinite_for() -> int {
            for (;;) {
                return 2;
            }
        }
        func conditional(flag: bool) -> int {
            while (flag) {
                return 3;
            }
        }
        """,
    )

    assert sum("TYP-0010" in d.message for d in result.diagnostics) == 3


def test_with_header_and_cleanup_returns_satisfy_function_flow(analyze_single):
    """All established with-return forms participate in definite return."""
    result = analyze_single(
        "main",
        """
        module main;
        func header() -> int {
            with (return 1 => null) {
            }
        }
        func inline_cleanup() -> int {
            with (let marker: int = 0 => return 2) {
            }
        }
        func cleanup_block() -> int {
            with (let marker: int = 0) {
            } cleanup {
                return 3;
            }
        }
        func main() -> int { return 0; }
        """,
    )

    assert not has_error_code(result.diagnostics, "TYP-0010")


def test_with_registered_cleanup_loop_control_overrides_header_return(analyze_single):
    """Registered break/continue cleanup overrides a pending with-header return."""
    result = analyze_single(
        "main",
        """
        module main;
        func break_cleanup_overrides_header_return() -> int {
            while (true) {
                with (let marker: int = 0 => break, return 1 => null) {
                }
                return 2;
            }
            return 3;
        }
        func continue_cleanup_overrides_header_return() -> int {
            let i: int = 0;
            while (i < 1) {
                i = i + 1;
                with (let marker: int = 0 => continue, return 1 => null) {
                }
                return 2;
            }
            return 3;
        }
        func main() -> int { return 0; }
        """,
    )

    assert not result.has_errors()
    assert sum("TYP-0030" in d.message for d in result.diagnostics) == 2
    assert not has_error_code(result.diagnostics, "TYP-0031")
    assert not has_error_code(result.diagnostics, "TYP-0010")


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
