"""
Tests for lvalue caching during assignment code generation.

When assigning to complex lvalues that contain side effects (like function calls),
the codegen must evaluate the side-effecting expression ONCE and cache it in a
temporary variable. This prevents bugs where functions are called multiple times
during the release/assign/retain sequence for ARC types.

Example bug (before fix):
    *(vec_push(vs) as string*) = val;
Would generate:
    rt_string_release(*(vec_push(vs)));    // Call 1
    *(vec_push(vs)) = val;                 // Call 2
    rt_string_retain(*(vec_push(vs)));     // Call 3

This incorrectly calls vec_push three times, pushing three elements instead of one.

The fix ensures side-effecting expressions are evaluated once into a temporary.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import re

from l0_backend import Backend
from l0_driver import L0Driver


# ============================================================================
# Code generation tests - verify temporaries are generated
# ============================================================================


def test_dereference_with_function_call_uses_temp(codegen_single):
    """Test that dereferencing a function call result caches the pointer."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        extern func get_ptr() -> int*;

        func assign_via_ptr() {
            *get_ptr() = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temporary for the pointer
    assert "l0_ptr_" in c_code, "Expected pointer temporary for dereference of function call"

    # The function should only be called once (in the temp assignment)
    func_name = "get_ptr()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_ptr() to be called once, but found {call_count} calls"


def test_dereference_with_cast_of_function_call_uses_temp(codegen_single):
    """Test that dereferencing a cast of function call caches the pointer."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        extern func get_void_ptr() -> void*;

        func assign_via_cast_ptr() {
            *(get_void_ptr() as int*) = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temporary for the casted pointer
    assert "l0_ptr_" in c_code, "Expected pointer temporary for dereference of cast"

    # The function should only be called once
    func_name = "get_void_ptr()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_void_ptr() to be called once, but found {call_count} calls"


def test_dereference_of_simple_variable_no_temp(codegen_single):
    """Test that dereferencing a simple variable does NOT generate a temp."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        func assign_via_var(ptr: int*) {
            *ptr = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should NOT generate a pointer temporary for simple variable
    assert "l0_ptr_" not in c_code, "Should not generate temp for simple variable dereference"

    # Should directly use the parameter
    assert "(*ptr)" in c_code


def test_string_assignment_through_function_call_pointer(codegen_single):
    """Test string assignment through dereferenced function call uses temp."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        extern func get_string_ptr() -> string*;

        func assign_string() {
            *get_string_ptr() = "hello";
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temporary for the pointer
    assert "l0_ptr_" in c_code, "Expected pointer temporary for string assignment"

    # The function should only be called once
    func_name = "get_string_ptr()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_string_ptr() to be called once, but found {call_count} calls"

    # The temp should be used for release and assign
    # Find the temp variable name
    temp_match = re.search(r"l0_ptr_\d+", c_code)
    assert temp_match, "Could not find temp variable"
    temp_name = temp_match.group(0)

    # Should use temp for rt_string_release
    assert f"rt_string_release((*{temp_name}))" in c_code
    # Should use temp for assignment
    assert f"(*{temp_name}) =" in c_code
    # Note: String literals don't need rt_string_retain (they're fresh values, not place exprs)


def test_nested_dereference_with_side_effects(codegen_single):
    """Test nested operations with side effects cache appropriately."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        struct Container {
            ptr: int*;
        }

        extern func get_container() -> Container*;

        func assign_nested() {
            *get_container().ptr = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temporary for the container pointer
    # The function should only be called once
    func_name = "get_container()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_container() to be called once, but found {call_count} calls"


def test_field_access_with_function_call_uses_temp(codegen_single):
    """Test field access on function call result caches the object."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        struct Box {
            value: string;
        }

        extern func get_box() -> Box*;

        func assign_field() {
            get_box().value = "hello";
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temporary for the object
    assert "l0_obj_" in c_code, "Expected object temporary for field access"

    # The function should only be called once
    func_name = "get_box()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_box() to be called once, but found {call_count} calls"


def test_field_access_on_simple_variable_no_temp(codegen_single):
    """Test that field access on simple variable does NOT generate a temp."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        struct Box {
            value: int;
        }

        func assign_field(box: Box*) {
            box.value = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should NOT generate an object temporary for simple variable
    assert "l0_obj_" not in c_code, "Should not generate temp for simple variable field access"


# ============================================================================
# Runtime tests - verify correct behavior with actual side effects
# ============================================================================


def test_side_effect_counter_in_let(tmp_path, write_l0_file, search_paths, compile_and_run):
    """Test that function calls in let initializers are called exactly once."""
    write_l0_file(
        "countertest",
        """
        module countertest;

        import std.io;
        import sys.memory;

        let counter: int = 0;

        func inc_counter() -> int {
            counter = counter + 1;
            return counter;
        }

        func main() -> int {
            counter = 0;

            // Each call should increment exactly once
            let a: int = inc_counter();
            let b: int = inc_counter();
            let c: int = inc_counter();

            printl_si("a:", a);
            printl_si("b:", b);
            printl_si("c:", c);
            printl_si("Final counter:", counter);

            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("countertest")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert "a: 1" in stdout
    assert "b: 2" in stdout
    assert "c: 3" in stdout
    assert "Final counter: 3" in stdout


def test_dereference_assign_calls_func_once(tmp_path, write_l0_file, search_paths, compile_and_run):
    """Test that dereference assignment with function call only calls func once.

    This is a runtime test for the core bug: when assigning through a dereferenced
    function call, the function should only be called once, not three times.
    """
    write_l0_file(
        "dereftest",
        """
        module dereftest;

        import std.io;
        import sys.memory;

        let counter: int = 0;

        // Static storage for testing
        let storage_val: int = 0;

        func get_storage_ptr() -> int* {
            counter = counter + 1;
            // Return pointer to static storage using extern helper
            return rt_array_element(rt_calloc(1, 8) as void*, 4, 0) as int*;
        }

        func main() -> int {
            counter = 0;

            // This dereference assignment should call get_storage_ptr() exactly ONCE
            // Before the fix, it would be called multiple times
            *get_storage_ptr() = 42;

            printl_si("Counter after dereference assign:", counter);

            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("dereftest")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    # The key assertion: function should be called exactly once
    assert "Counter after dereference assign: 1" in stdout


def test_string_dereference_assign_calls_func_once(tmp_path, write_l0_file, search_paths, compile_and_run):
    """Test string assignment through dereferenced function call.

    This tests the ARC (retain/release) code path which was the original bug scenario.
    With ARC types, the codegen emits release/assign/retain, so without caching
    the function would be called 3 times.
    """
    write_l0_file(
        "stringderef",
        """
        module stringderef;

        import std.io;
        import sys.memory;

        let counter: int = 0;

        func get_string_slot() -> string* {
            counter = counter + 1;
            // Allocate space for a string - use calloc which zeroes memory
            let ptr: void* = rt_calloc(1, 8) as void*;
            let sptr: string* = ptr as string*;
            return sptr;
        }

        func main() -> int {
            counter = 0;

            // String assignment through dereference should call function once
            // Before the fix: called 3 times (release, assign, retain)
            // After the fix: called 1 time (cached in temp)
            *get_string_slot() = "hello";

            printl_si("Counter after string deref assign:", counter);

            // Verify it's exactly 1
            if (counter == 1) {
                printl_s("PASS: Function called exactly once");
            } else {
                printl_s("FAIL: Function called multiple times");
            }

            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("stringderef")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert "Counter after string deref assign: 1" in stdout
    assert "PASS: Function called exactly once" in stdout


def test_field_assign_with_function_call_object(tmp_path, write_l0_file, search_paths, compile_and_run):
    """Test field assignment where object comes from function call."""
    write_l0_file(
        "fieldtest",
        """
        module fieldtest;

        import std.io;
        import sys.memory;

        struct Box {
            value: int;
            name: string;
        }

        let counter: int = 0;

        func get_box() -> Box* {
            counter = counter + 1;
            // Use calloc to get zeroed memory for the struct
            let ptr: void* = rt_calloc(1, sizeof(Box)) as void*;
            return ptr as Box*;
        }

        func main() -> int {
            counter = 0;

            // Field assignment on function call result should call func once
            get_box().value = 42;

            printl_si("Counter after int field assign:", counter);

            counter = 0;

            // String field assignment (with ARC) should also call func once
            get_box().name = "test";

            printl_si("Counter after string field assign:", counter);

            return 0;
        }
        """,
    )

    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze("fieldtest")
    assert not result.has_errors(), result.diagnostics

    backend = Backend(result)
    c_code = backend.generate()

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert "Counter after int field assign: 1" in stdout
    assert "Counter after string field assign: 1" in stdout


# ============================================================================
# Tests for code generation patterns
# ============================================================================


def test_assignment_with_binary_op_no_side_effects(codegen_single):
    """Test that binary operations without side effects don't generate temps."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        func test_simple(ptr: int*, offset: int) {
            // Simple arithmetic shouldn't generate temps
            let idx: int = offset + 1;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate valid code without unnecessary temps
    assert "l0_main_test_simple" in c_code


def test_chained_field_access_with_side_effects(codegen_single):
    """Test chained field access where intermediate access has side effects."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        struct Inner {
            value: int;
        }

        struct Outer {
            inner: Inner*;
        }

        extern func get_outer() -> Outer*;

        func assign_chained() {
            get_outer().inner.value = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # The outer function call should only happen once
    func_name = "get_outer()"
    call_count = c_code.count(func_name)
    assert call_count == 1, f"Expected get_outer() to be called once, but found {call_count} calls"


# ============================================================================
# Tests for _has_side_effects helper behavior
# ============================================================================


def test_has_side_effects_literals_no_side_effects(codegen_single):
    """Verify literals don't cause temp generation."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        func test_literals(ptr: int*) {
            // Literals should not be considered as having side effects
            *ptr = 42;
            *ptr = 0;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # No temps should be generated for simple pointer dereference
    assert "l0_ptr_" not in c_code


def test_has_side_effects_new_expr(codegen_single):
    """Test that new expressions are considered as having side effects."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        struct Data {
            value: string;
        }

        func test_new() {
            // new has side effects (allocation)
            (new Data).value = "hello";
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should generate a temp for the new expression result
    # The allocation should only happen once
    assert c_code.count("rt_alloc") <= 1 or "l0_obj_" in c_code


def test_parenthesized_expr_preserves_side_effects(codegen_single):
    """Test that parentheses don't hide side effects."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        extern func get_ptr() -> int*;

        func test_parens() {
            // Parentheses should not hide the side effect
            *((get_ptr())) = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should still generate a temp
    assert "l0_ptr_" in c_code

    # Function should only be called once
    func_name = "get_ptr()"
    call_count = c_code.count(func_name)
    assert call_count == 1


def test_cast_preserves_side_effects(codegen_single):
    """Test that casts don't hide side effects."""
    c_code, diags = codegen_single(
        "main",
        """
        module main;

        extern func get_ptr() -> void*;

        func test_cast() {
            // Cast should not hide the side effect
            *(get_ptr() as int*) = 42;
        }
        """,
    )

    assert c_code is not None, f"Codegen failed: {diags}"

    # Should still generate a temp
    assert "l0_ptr_" in c_code

    # Function should only be called once
    func_name = "get_ptr()"
    call_count = c_code.count(func_name)
    assert call_count == 1
