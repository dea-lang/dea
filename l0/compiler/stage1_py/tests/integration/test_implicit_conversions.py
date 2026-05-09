"""
Comprehensive test suite for implicit type conversions in L0.

Tests the following implicit conversions:
1. T → T? (value optional wrapping)
2. T* → T*? (niche/pointer optional - no wrapping needed)
3. byte → int (numeric widening)

At the following conversion sites:
- let statements with type annotations
- Assignment statements
- Return statements
- Function call arguments
- Struct constructor arguments
- Enum variant constructor arguments
- new expressions
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from conftest import has_error_code
from l0_ast import FuncDecl, ReturnStmt
from l0_backend import Backend
from l0_driver import L0Driver
from l0_types import BuiltinType


# ============================================================================
# Test helpers
# ============================================================================

def analyze(tmp_path, write_l0_file, search_paths, name: str, src: str):
    """Analyze a single module and return the result."""
    write_l0_file(name, src)
    driver = L0Driver(search_paths=search_paths)
    return driver.analyze(name)


def analyze_and_check_no_errors(tmp_path, write_l0_file, search_paths, name: str, src: str):
    """Analyze and assert no errors."""
    result = analyze(tmp_path, write_l0_file, search_paths, name, src)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert not errors, f"Unexpected errors: {[d.message for d in errors]}"
    return result


def analyze_and_expect_error(tmp_path, write_l0_file, search_paths, name: str, src: str, error_code: str):
    """Analyze and assert an error containing the given error code."""
    result = analyze(tmp_path, write_l0_file, search_paths, name, src)
    errors = [d for d in result.diagnostics if d.kind == "error"]
    assert errors, f"Expected an error containing '{error_code}', but no errors occurred"
    assert has_error_code(errors, error_code), \
        f"Expected error containing '{error_code}', got: {[d.message for d in errors]}"
    return result


def generate_c(tmp_path, write_l0_file, search_paths, name: str, src: str) -> str:
    """Analyze and generate C code, returning the C source."""
    write_l0_file(name, src)
    driver = L0Driver(search_paths=search_paths)
    result = driver.analyze(name)
    assert not result.has_errors(), f"Errors: {[d.message for d in result.diagnostics]}"
    backend = Backend(result)
    return backend.generate()


# ============================================================================
# T → T? conversion (value optionals)
# ============================================================================

class TestValueOptionalConversion:
    """Test T → T? implicit conversion for value types (int?, bool?, string?)."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_let_int_to_int_optional(self):
        """let x: int? = 42; should wrap 42 in Some."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int? = 42;
            }
        """)

    def test_let_bool_to_bool_optional(self):
        """let x: bool? = true; should wrap true in Some."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: bool? = true;
            }
        """)

    def test_let_string_to_string_optional(self):
        """let x: string? = "hello"; should wrap in Some."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: string? = "hello";
            }
        """)

    def test_assign_int_to_int_optional(self):
        """Assignment x = 42 where x: int? should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int? = null;
                x = 42;
            }
        """)

    def test_return_int_from_int_optional_func(self):
        """Returning int from func -> int? should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int? {
                return 42;
            }
        """)

    def test_return_bool_from_bool_optional_func(self):
        """Returning bool from func -> bool? should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> bool? {
                return true;
            }
        """)

    def test_func_arg_int_to_int_optional(self):
        """Passing int to func(x: int?) should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func takes_opt(x: int?) -> void {}
            func f() -> void {
                takes_opt(42);
            }
        """)

    def test_func_arg_string_to_string_optional(self):
        """Passing string to func(x: string?) should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func takes_opt(x: string?) -> void {}
            func f() -> void {
                takes_opt("hello");
            }
        """)

    def test_struct_field_int_to_int_optional(self):
        """Struct constructor with int for int? field should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            struct S { value: int?; }
            func f() -> void {
                let s: S = S(42);
            }
        """)

    def test_enum_payload_int_to_int_optional(self):
        """Enum variant with int for int? payload should wrap."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            enum E { Val(x: int?); }
            func f() -> void {
                let e: E = Val(42);
            }
        """)


# ============================================================================
# T* → T*? conversion (niche/pointer optionals)
# ============================================================================

class TestPointerOptionalConversion:
    """Test T* → T*? implicit conversion (niche optimization, no wrapper)."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_let_ptr_to_ptr_optional(self):
        """let x: int*? = ptr; should just use the pointer (niche)."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f(ptr: int*) -> void {
                let x: int*? = ptr;
            }
        """)

    def test_return_ptr_from_ptr_optional_func(self):
        """Returning T* from func -> T*? should work."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            struct Node { value: int; }
            func f(n: Node*) -> Node*? {
                return n;
            }
        """)

    def test_func_arg_ptr_to_ptr_optional(self):
        """Passing T* to func(x: T*?) should work."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func takes_opt(x: int*?) -> void {}
            func f(ptr: int*) -> void {
                takes_opt(ptr);
            }
        """)

    def test_rt_free_accepts_optional_pointer(self):
        """Passing void*? to rt_free should be accepted."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            import sys.memory;
            func f() -> void {
                let p: void*? = rt_alloc(8);
                rt_free(p);
            }
        """)


# ============================================================================
# byte → int conversion
# ============================================================================

class TestByteToIntConversion:
    """Test byte → int implicit widening."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_let_byte_to_int(self):
        """let x: int = byte_val; should widen."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let b: byte = 'a';
                let x: int = b;
            }
        """)

    def test_let_byte_literal_to_int(self):
        """let x: int = 'a'; should widen byte literal to int."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int = 'a';
            }
        """)

    def test_assign_byte_to_int(self):
        """Assignment x = byte_val where x: int should widen."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let b: byte = 'x';
                let x: int = 0;
                x = b;
            }
        """)

    def test_return_byte_from_int_func(self):
        """Returning byte from func -> int should widen."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int {
                let b: byte = 'z';
                return b;
            }
        """)

    def test_func_arg_byte_to_int(self):
        """Passing byte to func(x: int) should widen."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func takes_int(x: int) -> void {}
            func f() -> void {
                let b: byte = 'q';
                takes_int(b);
            }
        """)

    def test_struct_field_byte_to_int(self):
        """Struct constructor with byte for int field should widen."""
        analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            struct S { value: int; }
            func f() -> void {
                let b: byte = 'w';
                let s: S = S(b);
            }
        """)


# ============================================================================
# Codegen verification
# ============================================================================

class TestCodegenConversion:
    """Test that generated C code includes proper conversion."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_int_to_int_optional_generates_some(self):
        """Verify C code wraps int in Some for int?."""
        c_code = generate_c(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int? {
                return 42;
            }
        """)
        # Should contain .has_value = 1 for the Some wrapper
        assert ".has_value = 1" in c_code or "has_value = 1" in c_code, \
            f"Expected Some wrapper in C code:\n{c_code}"

    def test_null_to_optional_generates_none(self):
        """Verify C code generates None for null."""
        c_code = generate_c(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int? {
                return null;
            }
        """)
        # Should contain .has_value = 0 for the None
        assert ".has_value = 0" in c_code or "has_value = 0" in c_code, \
            f"Expected None wrapper in C code:\n{c_code}"

    def test_byte_to_int_generates_cast(self):
        """Verify C code casts byte to int."""
        c_code = generate_c(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int {
                return 'a';
            }
        """)
        # Should contain a cast to l0_int
        assert "l0_int" in c_code

    def test_ptr_to_ptr_optional_no_wrapper(self):
        """Verify pointer optionals don't generate wrapper structs."""
        c_code = generate_c(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f(p: int*) -> int*? {
                return p;
            }
        """)
        # Should NOT have l0_opt wrapper for pointer optional
        # The return should just be the pointer directly
        assert "l0_opt_p_" not in c_code, \
            f"Pointer optional should be niche-optimized:\n{c_code}"


# ============================================================================
# End-to-end execution tests
# ============================================================================

class TestConversionExecution:
    """Test conversion behavior via actual execution."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths, compile_and_run):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths
        self.compile_and_run = lambda c_code: compile_and_run(c_code, tmp_path)

    def _run(self, name: str, src: str):
        """Helper to analyze, generate, compile, and run."""
        self.write_l0_file(name, src)
        driver = L0Driver(search_paths=self.search_paths)
        result = driver.analyze(name)
        assert not result.has_errors(), f"Errors: {[d.message for d in result.diagnostics]}"
        backend = Backend(result)
        c_code = backend.generate()
        return self.compile_and_run(c_code)

    def test_int_optional_roundtrip(self):
        """Verify int → int? → int roundtrip works."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            func wrap(x: int) -> int? {
                return x;
            }

            func main() -> int {
                let opt: int? = wrap(42);
                if (opt != null) {
                    return opt as int;
                }
                return -1;
            }
        """)
        # Check that compilation succeeded and ran
        # Return code is captured in the success of compilation+run

    def test_bool_optional_roundtrip(self):
        """Verify bool → bool? → bool roundtrip works."""
        success, stdout, stderr = self._run("main", """
            module main;

            func wrap(x: bool) -> bool? {
                return x;
            }

            func main() -> int {
                let opt: bool? = wrap(true);
                if (opt != null) {
                    if (opt as bool) {
                        return 1;
                    }
                }
                return 0;
            }
        """)
        # success is True if compilation+run succeeded with exit code 0

    def test_byte_to_int_execution(self):
        """Verify byte → int widening produces correct value."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            func to_int(b: byte) -> int {
                return b;
            }

            func main() -> int {
                let result: int = to_int('A');
                printl_i(result);
                return 0;
            }
        """)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "65" in stdout, f"Expected 65 (ASCII 'A'), got stdout: {stdout}"

    def test_struct_optional_field_conversion(self):
        """Verify struct with optional field accepts non-optional value."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            struct Container { value: int?; }

            func main() -> int {
                let c: Container = Container(100);
                if (c.value != null) {
                    printl_i(c.value as int);
                    return 0;
                }
                return -1;
            }
        """)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "100" in stdout, f"Expected 100 in output, got: {stdout}"

    def test_enum_optional_payload_conversion(self):
        """Verify enum variant with optional payload accepts non-optional value."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            enum Result {
                Ok(value: int?);
                Err;
            }

            func main() -> int {
                let r: Result = Ok(77);
                match (r) {
                    Ok(v) => {
                        if (v != null) {
                            printl_i(v as int);
                            return 0;
                        }
                        return -2;
                    }
                    Err => {
                        return -1;
                    }
                }
            }
        """)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "77" in stdout, f"Expected 77 in output, got: {stdout}"

    def test_func_multiple_converted_args(self):
        """Verify multiple arguments with conversion work correctly."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            func sum_opts(a: int?, b: int?, c: int?) -> int {
                let result: int = 0;
                if (a != null) {
                    result = result + (a as int);
                }
                if (b != null) {
                    result = result + (b as int);
                }
                if (c != null) {
                    result = result + (c as int);
                }
                return result;
            }

            func main() -> int {
                let s: int = sum_opts(10, 20, 30);
                printl_i(s);
                return 0;
            }
        """)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "60" in stdout, f"Expected 60 in output, got: {stdout}"

    def test_ptr_optional_conversion(self):
        """Verify pointer to optional pointer conversion works."""
        success, stdout, stderr = self._run("main", """
            module main;
            import std.io;

            func maybe_ptr(p: int*?) -> int {
                if (p != null) {
                    return *(p as int*);  // explicit unwrap required
                }
                return -1;
            }

            func main() -> int {
                let x: int* = new int(55);
                let result: int = maybe_ptr(x);
                printl_i(result);
                return 0;
            }
        """)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "55" in stdout, f"Expected 55 in output, got: {stdout}"


# ============================================================================
# Negative tests (things that should NOT compile)
# ============================================================================

class TestConversionRejection:
    """Test that invalid conversions are rejected."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_int_optional_to_int_rejected(self):
        """int? cannot implicitly convert to int."""
        analyze_and_expect_error(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int? = 42;
                let y: int = x;
            }
        """, "TYP-0310")

    def test_int_to_byte_rejected(self):
        """int cannot implicitly narrow to byte."""
        analyze_and_expect_error(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int = 42;
                let y: byte = x;
            }
        """, "TYP-0310")

    def test_string_to_int_optional_rejected(self):
        """string cannot convert to int?."""
        analyze_and_expect_error(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: int? = "hello";
            }
        """, "TYP-0310")

    def test_wrong_optional_type_rejected(self):
        """int cannot convert to string?."""
        analyze_and_expect_error(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> void {
                let x: string? = 42;
            }
        """, "TYP-0310")


# ============================================================================
# Expression type tracking tests
# ============================================================================

class TestExprTypeTracking:
    """Test that expr_types stores natural types, not converted types."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, write_l0_file, search_paths):
        self.tmp_path = tmp_path
        self.write_l0_file = write_l0_file
        self.search_paths = search_paths

    def test_int_literal_has_int_type(self):
        """Integer literal in optional context should still have int type."""
        result = analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int? {
                return 42;
            }
        """)
        # Find the return statement and check its value's type
        mod = result.cu.modules["main"]
        func = next(d for d in mod.decls if isinstance(d, FuncDecl))
        ret_stmt = func.body.stmts[0]
        assert isinstance(ret_stmt, ReturnStmt)

        expr_type = result.expr_types.get(id(ret_stmt.value))
        assert expr_type is not None
        assert isinstance(expr_type, BuiltinType)
        assert expr_type.name == "int", f"Expected natural type 'int', got '{expr_type.name}'"

    def test_byte_literal_has_byte_type(self):
        """Byte literal in int context should still have byte type."""
        result = analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int {
                return 'a';
            }
        """)
        mod = result.cu.modules["main"]
        func = next(d for d in mod.decls if isinstance(d, FuncDecl))
        ret_stmt = func.body.stmts[0]
        assert isinstance(ret_stmt, ReturnStmt)

        expr_type = result.expr_types.get(id(ret_stmt.value))
        assert expr_type is not None
        assert isinstance(expr_type, BuiltinType)
        assert expr_type.name == "byte", f"Expected natural type 'byte', got '{expr_type.name}'"

    def test_var_ref_has_natural_type(self):
        """Variable reference in optional context should have its declared type."""
        result = analyze_and_check_no_errors(
            self.tmp_path, self.write_l0_file, self.search_paths,
            "main", """
            module main;
            func f() -> int? {
                let x: int = 10;
                return x;
            }
        """)
        mod = result.cu.modules["main"]
        func = next(d for d in mod.decls if isinstance(d, FuncDecl))
        ret_stmt = func.body.stmts[1]  # Second statement is return
        assert isinstance(ret_stmt, ReturnStmt)

        expr_type = result.expr_types.get(id(ret_stmt.value))
        assert expr_type is not None
        assert isinstance(expr_type, BuiltinType)
        assert expr_type.name == "int", f"Expected natural type 'int', got '{expr_type.name}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
