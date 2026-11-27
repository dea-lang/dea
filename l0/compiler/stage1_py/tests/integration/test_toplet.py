"""
Tests for top-level let declarations.

Tests the full pipeline: parsing, name resolution, type inference,
type checking, and code generation for module-level let bindings.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from l0_ast import LetDecl, Module
from l0_backend import Backend
from l0_driver import L0Driver
from l0_lexer import Lexer
from l0_parser import Parser

STAGE1_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = STAGE1_ROOT.parent / "shared" / "runtime"
STDLIB_PATH = STAGE1_ROOT.parent / "shared" / "l0" / "stdlib"
STATIC_FIXTURES = STAGE1_ROOT.parents[1] / "tests" / "fixtures" / "static_initializers"


def test_static_initializer_intrinsics(search_paths, compile_and_run, tmp_path):
    """Generate and execute file-scope constructors, sizes and enum tag constants."""
    search_paths.add_project_root(STATIC_FIXTURES)
    result = L0Driver(search_paths=search_paths).analyze("valid")
    assert not result.has_errors(), result.diagnostics
    success, _, stderr = compile_and_run(Backend(result).generate(), tmp_path, strict_c99=True)
    assert success, stderr


def test_non_static_initializer_diagnostics(search_paths):
    """Diagnose each runtime operation at its source location during checking."""
    search_paths.add_project_root(STATIC_FIXTURES)
    result = L0Driver(search_paths=search_paths).analyze("invalid")
    errors = [d for d in result.diagnostics if d.kind == "error"]
    lines = (STATIC_FIXTURES / "invalid.l0").read_text(encoding="utf-8").splitlines()
    assert all(d.message == "[TYP-0054] A top-level let initializer must be static." for d in errors)
    assert [lines[d.line - 1][d.column - 1:] for d in errors] == [
        "make_ptr();", "new int(1));", "provider::value();", "external_value();", "value()));",
        "choice);", "value()));", "choice;", "1 + 2;",
    ]


def test_static_initializer_type_errors(search_paths):
    """Report earlier inference, name, arity and type errors without a staticness cascade."""
    search_paths.add_project_root(STATIC_FIXTURES)
    result = L0Driver(search_paths=search_paths).analyze("type_errors")
    codes = [d.message.split()[0] for d in result.diagnostics if d.kind == "error"]
    assert sorted(codes) == ["[SIG-0030]", "[TYP-0183]", "[TYP-0189]", "[TYP-0310]"]


def write_tmp(tmp_path, name: str, src: str):
    """Helper to write a temporary L0 source file."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(src))
    return path


def _check_c_compiler_available():
    """Check if a C compiler (gcc or clang) is available."""
    for compiler in ["gcc", "clang", "cc"]:
        try:
            subprocess.run(
                [compiler, "--version"],
                capture_output=True,
                check=False,
                timeout=2,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


# ============================================================================
# Parser tests
# ============================================================================


def test_parse_toplet_int():
    """Test parsing top-level let with int type."""
    src = dedent("""
        module test;
        let x: int = 42;
    """)
    lexer = Lexer.from_source(src)
    parser = Parser(lexer.tokenize(), "test.l0")
    module = parser.parse_module()

    assert isinstance(module, Module)
    assert len(module.decls) == 1
    assert isinstance(module.decls[0], LetDecl)
    assert module.decls[0].name == "x"


def test_parse_toplet_type_inference():
    """Test parsing top-level let with type inference."""
    src = dedent("""
        module test;
        let x = 42;
    """)
    lexer = Lexer.from_source(src)
    parser = Parser(lexer.tokenize(), "test.l0")
    module = parser.parse_module()

    assert isinstance(module, Module)
    assert len(module.decls) == 1
    assert isinstance(module.decls[0], LetDecl)
    assert module.decls[0].name == "x"
    assert module.decls[0].type is None  # Type inference


def test_parse_toplet_string():
    """Test parsing top-level let with string type."""
    src = dedent("""
        module test;
        let greeting: string = "Hello";
    """)
    lexer = Lexer.from_source(src)
    parser = Parser(lexer.tokenize(), "test.l0")
    module = parser.parse_module()

    assert isinstance(module, Module)
    assert len(module.decls) == 1
    assert isinstance(module.decls[0], LetDecl)
    assert module.decls[0].name == "greeting"


# ============================================================================
# Type checking tests
# ============================================================================


def test_typecheck_toplet_primitives(tmp_path):
    """Test type checking for top-level let with primitive types."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let x: int = 42;
        let s: string = "hello";
        let b: bool = true;
        let opt: int? = null;

        func main() -> int {
            return x;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()
    assert ("test", "x") in result.let_types
    assert ("test", "s") in result.let_types
    assert ("test", "b") in result.let_types
    assert ("test", "opt") in result.let_types


def test_typecheck_toplet_type_inference(tmp_path):
    """Test type inference for top-level let declarations."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let x = 42;
        let s = "hello";
        let b = true;

        func main() -> int {
            return x;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()
    # Check inferred types
    from l0_types import BuiltinType
    assert result.let_types[("test", "x")] == BuiltinType("int")
    assert result.let_types[("test", "s")] == BuiltinType("string")
    assert result.let_types[("test", "b")] == BuiltinType("bool")


def test_typecheck_toplet_struct(tmp_path):
    """Test type checking for top-level let with struct types."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        struct Point {
            x: int;
            y: int;
        }

        let origin = Point(0, 0);
        let p: Point = Point(1, 2);

        func main() -> int {
            return origin.x + p.y;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()
    assert ("test", "origin") in result.let_types
    assert ("test", "p") in result.let_types


def test_typecheck_toplet_enum(tmp_path):
    """Test type checking for top-level let with enum types."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        enum Status {
            Ready;
            Running(progress: int);
        }

        let status0 = Ready;
        let status1 = Ready();
        let status2: Status = Running(50);

        func main() -> int {
            match (status1) {
                Ready => { return 0; }
                Running(p) => { return p; }
            }
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()
    assert ("test", "status0") in result.let_types
    assert ("test", "status1") in result.let_types
    assert ("test", "status2") in result.let_types


def test_typecheck_toplet_bare_payload_variant_error(tmp_path):
    """Bare payload variants still require constructor arguments."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        enum Status {
            Ready;
            Running(progress: int);
        }

        let status = Running;

        func main() -> int {
            return 0;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert result.has_errors()
    assert any("[SIG-0030]" in str(diag) for diag in result.diagnostics)


def test_typecheck_toplet_qualified_bare_variant(tmp_path):
    """Top-level let inference supports imported bare zero-arg variants."""
    write_tmp(tmp_path, "colors.l0", """
        module colors;

        enum Color {
            Red;
        }
    """)
    write_tmp(tmp_path, "test.l0", """
        module test;
        import colors;

        let status = colors::Red;

        func main() -> int {
            return ord(status);
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()
    assert ("test", "status") in result.let_types


def test_typecheck_toplet_duplicate_error(tmp_path):
    """Test that duplicate top-level let names are caught."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let x: int = 1;
        let x: int = 2;

        func main() -> int {
            return 0;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert result.has_errors()
    # Check that there's an error about duplicate declaration
    error_messages = [str(d) for d in result.diagnostics]
    assert any("Duplicate" in msg or "duplicate" in msg for msg in error_messages)


# ============================================================================
# Code generation tests
# ============================================================================


def test_codegen_toplet_primitives(tmp_path):
    """Test C code generation for top-level let with primitives."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let x: int = 42;
        let s: string = "hello";
        let b: bool = true;

        func main() -> int {
            return x;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Check for static declarations
    assert "static l0_int l0_test_x = 42;" in c_code
    assert "static l0_bool l0_test_b = true;" in c_code
    assert "static l0_string l0_test_s" in c_code
    assert 'L0_STRING_CONST("hello", 5)' in c_code


def test_codegen_toplet_string_mutation_releases_previous_value(tmp_path):
    """Top-level string reassignment must release the previous value."""
    write_tmp(tmp_path, "test.l0", """
        module test;
        import std.string;

        let greeting: string = "hi";

        func main() -> int {
            greeting = concat_s("a", "b");
            greeting = concat_s(greeting, "c");
            return len_s(greeting);
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    assert "static l0_string l0_test_greeting" in c_code
    assert c_code.count("rt_string_release(l0_test_greeting);") >= 2


def test_codegen_toplet_struct(tmp_path):
    """Test C code generation for top-level let with struct."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        struct Point {
            x: int;
            y: int;
        }

        let origin = Point(0, 0);

        func main() -> int {
            return origin.x;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Check for static struct initialization
    assert "static struct l0_test_Point l0_test_origin" in c_code
    assert ".x = 0" in c_code
    assert ".y = 0" in c_code


def test_codegen_toplet_enum(tmp_path):
    """Test C code generation for top-level let with enum."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        enum Status {
            Ready;
            Running(progress: int);
        }

        let status0 = Ready;
        let status1 = Ready();
        let status2 = Running(75);

        func main() -> int {
            match (status1) {
                Ready => { return 0; }
                Running(p) => { return p; }
            }
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Check for static enum initialization
    assert "static struct l0_test_Status l0_test_status0" in c_code
    assert "static struct l0_test_Status l0_test_status1" in c_code
    assert "static struct l0_test_Status l0_test_status2" in c_code
    assert ".tag = l0_test_Status_Ready" in c_code
    assert ".tag = l0_test_Status_Running" in c_code


# ============================================================================
# End-to-end execution tests (requires C compiler)
# ============================================================================


@pytest.mark.skipif(not _check_c_compiler_available(), reason="C compiler not available")
def test_execute_toplet_primitives(tmp_path):
    """Test execution of top-level let with primitives."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let result: int = 42;

        func main() -> int {
            return result;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Compile and run
    c_file = tmp_path / "test.c"
    c_file.write_text(c_code)

    exe_path = tmp_path / "test_exe"

    compile_result = subprocess.run(
        ["gcc", "-std=c99", "-I", str(RUNTIME_PATH), str(c_file), "-o", str(exe_path)],
        capture_output=True,
        text=True
    )

    assert compile_result.returncode == 0, f"Compilation failed: {compile_result.stderr}"

    run_result = subprocess.run([str(exe_path)], capture_output=True, text=True)
    assert run_result.returncode == 42


@pytest.mark.skipif(not _check_c_compiler_available(), reason="C compiler not available")
def test_execute_toplet_mutation(tmp_path):
    """Test mutation of top-level let."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        let counter: int = 0;

        func increment() -> void {
            counter = counter + 1;
        }

        func main() -> int {
            increment();
            increment();
            increment();
            return counter;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Compile and run
    c_file = tmp_path / "test.c"
    c_file.write_text(c_code)

    exe_path = tmp_path / "test_exe"

    compile_result = subprocess.run(
        ["gcc", "-std=c99", "-I", str(RUNTIME_PATH), str(c_file), "-o", str(exe_path)],
        capture_output=True,
        text=True
    )

    assert compile_result.returncode == 0

    run_result = subprocess.run([str(exe_path)], capture_output=True, text=True)
    assert run_result.returncode == 3


@pytest.mark.skipif(not _check_c_compiler_available(), reason="C compiler not available")
def test_execute_toplet_string_mutation(tmp_path):
    """Test ARC-safe mutation of a top-level string."""
    write_tmp(tmp_path, "test.l0", """
        module test;
        import std.string;

        let greeting: string = "hi";

        func main() -> int {
            greeting = concat_s("a", "b");
            greeting = concat_s(greeting, "c");
            return len_s(greeting);
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    driver.search_paths.add_system_root(STDLIB_PATH)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    c_file = tmp_path / "test.c"
    c_file.write_text(c_code)

    exe_path = tmp_path / "test_exe"

    compile_result = subprocess.run(
        ["gcc", "-std=c99", "-I", str(RUNTIME_PATH), str(c_file), "-o", str(exe_path)],
        capture_output=True,
        text=True
    )

    assert compile_result.returncode == 0

    run_result = subprocess.run([str(exe_path)], capture_output=True, text=True)
    assert run_result.returncode == 3


@pytest.mark.skipif(not _check_c_compiler_available(), reason="C compiler not available")
def test_execute_toplet_struct(tmp_path):
    """Test execution with top-level struct let."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        struct Point {
            x: int;
            y: int;
        }

        let position = Point(10, 20);

        func main() -> int {
            return position.x + position.y;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Compile and run
    c_file = tmp_path / "test.c"
    c_file.write_text(c_code)

    exe_path = tmp_path / "test_exe"

    compile_result = subprocess.run(
        ["gcc", "-std=c99", "-I", str(RUNTIME_PATH), str(c_file), "-o", str(exe_path)],
        capture_output=True,
        text=True
    )

    assert compile_result.returncode == 0

    run_result = subprocess.run([str(exe_path)], capture_output=True, text=True)
    assert run_result.returncode == 30


@pytest.mark.skipif(not _check_c_compiler_available(), reason="C compiler not available")
def test_execute_toplet_nested_struct(tmp_path):
    """Test execution with nested struct initialization."""
    write_tmp(tmp_path, "test.l0", """
        module test;

        struct Point {
            x: int;
            y: int;
        }

        struct Rectangle {
            top_left: Point;
            bottom_right: Point;
        }

        let rect = Rectangle(Point(0, 0), Point(10, 20));

        func main() -> int {
            return rect.bottom_right.x + rect.bottom_right.y;
        }
    """)

    driver = L0Driver()
    driver.search_paths.add_project_root(tmp_path)
    result = driver.analyze("test")

    assert not result.has_errors()

    backend = Backend(result)
    c_code = backend.generate()

    # Compile and run
    c_file = tmp_path / "test.c"
    c_file.write_text(c_code)

    exe_path = tmp_path / "test_exe"

    compile_result = subprocess.run(
        ["gcc", "-std=c99", "-I", str(RUNTIME_PATH), str(c_file), "-o", str(exe_path)],
        capture_output=True,
        text=True
    )

    assert compile_result.returncode == 0

    run_result = subprocess.run([str(exe_path)], capture_output=True, text=True)
    assert run_result.returncode == 30
