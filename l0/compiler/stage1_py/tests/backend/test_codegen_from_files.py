"""
Test L0 code generation backend.

This test module calls the L0 driver and codegen classes.

Includes both programmatic tests and tests that load .l0 files from
tests/backend/codegen/ directory.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from pathlib import Path

import pytest

from l0_backend import Backend
# Import L0 modules directly
from l0_driver import L0Driver

# Test file discovery
CODEGEN_TEST_DIR = Path(__file__).parent / "codegen"


def find_codegen_test_files():
    """Find all .l0 test files in tests/backend/codegen/ directory."""
    if not CODEGEN_TEST_DIR.exists():
        return []
    return sorted(CODEGEN_TEST_DIR.glob("test_*.l0"))


def get_expected_output(test_file: Path) -> str:
    """Read expected output for a test file."""
    expected_file = test_file.with_suffix(".expected")
    if expected_file.exists():
        return expected_file.read_text()
    return ""


class TestCodeGen:
    """Test code generation for all cases."""

    @pytest.fixture(autouse=True)
    def _setup(self, temp_project: Path, write_l0_file, search_paths, compile_and_run):
        self.temp_path = temp_project
        self.write_l0_file = write_l0_file
        self._search_paths = search_paths
        self.compile_and_run = lambda c_code: compile_and_run(c_code, temp_project)

    def getSourceSearchPaths(self):
        return self._search_paths

    def test_simple_main(self):
        """Test generating code for a simple main function."""
        self.write_l0_file("hello", """
            module hello;
            
            import std.io;
            
            func main() -> int {
                printl_i(42);
                return 0;
            }
        """)

        # Setup driver
        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        # Analyze
        result = driver.analyze("hello")

        # Should have no errors
        assert not result.has_errors(), f"Analysis failed: {result.diagnostics}"

        # Generate C code
        backend = Backend(result)
        c_code = backend.generate()

        # Verify C code structure
        assert "#include <stdint.h>" in c_code
        assert "#include \"l0_runtime.h\"" in c_code
        assert "l0_hello_main" in c_code  # Mangled function name
        assert "int main(" in c_code  # C main wrapper

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "42" in stdout

    def test_struct_codegen(self):
        """Test struct definition and usage."""
        self.write_l0_file("point", """
            module point;

            import std.io;

            struct Point {
                x: int;
                y: int;
            }

            func main() -> int {
                let p: Point = Point(10, 20);
                printl_i(p.x);
                printl_i(p.y);
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("point")
        assert not result.has_errors(), f"Analysis failed: {result.diagnostics}"

        backend = Backend(result)
        c_code = backend.generate()

        # Verify struct definition
        assert "struct l0_point_Point" in c_code
        assert "l0_int x;" in c_code
        assert "l0_int y;" in c_code

        # Verify struct constructor (designated initializers)
        assert ".x = " in c_code
        assert ".y = " in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "10" in stdout
        assert "20" in stdout

    def test_enum_codegen(self):
        """Test enum (tagged union) definition and match."""
        self.write_l0_file("option", """
            module option;

            import std.io;

            enum Option {
                Some(value: int);
                None();
            }

            func get_value(opt: Option) -> int {
                match (opt) {
                    Some(v) => {
                        return v;
                    }
                    None() => {
                        return 0;
                    }
                }
            }

            func main() -> int {
                let opt1: Option = Some(42);
                let opt2: Option = None();

                printl_i(get_value(opt1));
                printl_i(get_value(opt2));

                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("option")
        assert not result.has_errors(), f"Analysis failed: {result.diagnostics}"

        backend = Backend(result)
        c_code = backend.generate()

        # Verify enum tag definition
        assert "enum l0_option_Option_tag" in c_code
        assert "l0_option_Option_Some" in c_code
        assert "l0_option_Option_None" in c_code

        # Verify tagged union struct
        assert "struct l0_option_Option" in c_code
        assert ".tag" in c_code

        # Verify match lowering to switch
        assert "switch ((_scrutinee).tag)" in c_code
        assert "case l0_option_Option_Some:" in c_code
        assert "case l0_option_Option_None:" in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "42" in stdout
        assert "0" in stdout

    def test_function_mangling(self):
        """Test that functions are mangled correctly."""
        self.write_l0_file("mangling", """
            module mangling;

            import std.io;

            func helper(x: int) -> int {
                return x + 1;
            }

            func main() -> int {
                printl_i(helper(41));
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("mangling")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify function names are mangled
        assert "l0_mangling_helper" in c_code
        assert "l0_mangling_main" in c_code

        # Verify extern functions are NOT mangled
        assert "printl_i" in c_code
        assert "l0_mangling_printl_i" not in c_code

        # Verify C main wrapper exists
        assert "int main(" in c_code
        assert "int l0_exit_code = (int) l0_mangling_main();" in c_code
        assert "return l0_exit_code;" in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "42" in stdout

    def test_all_statement_types(self):
        """Test that all statement types generate correctly."""
        self.write_l0_file("statements", """
            module statements;
            
            import std.io;
            
            func main() -> int {
                let x: int = 10;
                x = 20;
                
                if (x > 15) {
                    printl_i(1);
                } else {
                    printl_i(0);
                }
                
                let i: int = 0;
                while (i < 3) {
                    printl_i(i);
                    i = i + 1;
                }
                
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("statements")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify statement types
        assert "l0_int x = 10;" in c_code  # let
        assert " = 20;" in c_code  # assignment
        assert "if (" in c_code  # if statement
        assert "else" in c_code  # else
        assert "while (" in c_code  # while loop

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"

        # Verify output
        lines = stdout.strip().split("\n")
        assert "1" in lines[0]  # if branch taken
        assert "0" in lines[1]  # first iteration
        assert "1" in lines[2]  # second iteration
        assert "2" in lines[3]  # third iteration

    def test_all_expression_types(self):
        """Test that all expression types generate correctly."""
        self.write_l0_file("expressions", """
            module expressions;

            import std.io;
            
            func main() -> int {
                let lit: int = 42;
                let unary: int = -lit;
                let binary: int = 10 + 20;
                let cmp: bool = 10 < 20;
                let and: bool = true && false;
                let or: bool = true || false;
                
                if (cmp) {
                    printl_i(binary);
                }
                
                if (or) {
                    printl_i(1);
                }
                
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("expressions")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify expression types
        assert "42" in c_code  # integer literal
        assert "(_rt_isub(0, lit))" in c_code  # checked unary minus
        assert "_rt_iadd(10, 20)" in c_code or "10 + 20" in c_code  # binary
        assert "(10 < 20)" in c_code or "10 < 20" in c_code  # comparison
        assert "l0_bool l0_cond_" in c_code  # structured logical short-circuit lowering
        assert "__cond_true_" in c_code
        assert "__cond_false_" in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "30" in stdout
        assert "1" in stdout

    def test_match_wildcard(self):
        """Test match with wildcard pattern."""
        self.write_l0_file("wildcard", """
            module wildcard;

            import std.io;
 
            enum Result {
                Ok(value: int);
                Err(code: int);
            }

            func process(r: Result) -> int {
                match (r) {
                    Ok(v) => {
                        return v;
                    }
                    _ => {
                        return 0;
                    }
                }
            }
            
            func main() -> int {
                let r1: Result = Ok(42);
                let r2: Result = Err(1);
                
                printl_i(process(r1));
                printl_i(process(r2));
                
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("wildcard")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify wildcard becomes default
        assert "default:" in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "42" in stdout
        assert "0" in stdout

    def test_nested_struct(self):
        """Test nested struct definitions."""
        self.write_l0_file("nested", """
            module nested;
            
            import std.io;

            struct Point {
                x: int;
                y: int;
            }
            
            struct Line {
                start: Point;
                end: Point;
            }
                        
            func main() -> int {
                let line: Line = Line(Point(0, 0), Point(10, 10));
                printl_i(line.start.x);
                printl_i(line.end.x);
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("nested")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify both structs are defined
        assert "struct l0_nested_Point" in c_code
        assert "struct l0_nested_Line" in c_code

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "0" in stdout
        assert "10" in stdout

    def test_type_error_prevents_codegen(self):
        """Test that type errors prevent code generation."""
        self.write_l0_file("type_error", """
            module type_error;
            
            func main() -> int {
                let x: int = true;
                return x;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("type_error")

        # Should have errors
        assert result.has_errors(), "Type error should be detected"

        # Should not be able to generate code
        with pytest.raises(ValueError, match="Cannot generate code with semantic errors"):
            backend = Backend(result)
            backend.generate()

    def test_empty_variant(self):
        """Test enum variant with no payload."""
        self.write_l0_file("empty_variant", """
            module empty_variant;
            
            import std.io;

            enum Flag {
                On();
                Off();
            }

            func main() -> int {
                let f1: Flag = On();
                let f2: Flag = Off();
                
                match (f1) {
                    On() => {
                        printl_i(1);
                    }
                    Off() => {
                        printl_i(0);
                    }
                }
                
                match (f2) {
                    On() => {
                        printl_i(1);
                    }
                    Off() => {
                        printl_i(0);
                    }
                }
                
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("empty_variant")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Compile and run
        success, stdout, stderr = self.compile_and_run(c_code)
        assert success, f"Compilation/execution failed: {stderr}"
        assert "1" in stdout
        assert "0" in stdout


class TestCodeGenErrorHandling:
    """Test error handling in code generation."""

    def test_missing_compilation_unit(self):
        """Test that codegen fails gracefully without a compilation unit."""
        from l0_analysis import AnalysisResult

        result = AnalysisResult(cu=None)

        with pytest.raises(ValueError, match="Cannot generate code without a compilation unit"):
            backend = Backend(result)
            backend.generate()

    def test_analysis_errors_prevent_codegen(self):
        """Test that analysis errors prevent code generation."""
        from l0_analysis import AnalysisResult
        from l0_diagnostics import Diagnostic
        from l0_compilation import CompilationUnit
        from l0_ast import Module

        # Create a mock result with errors
        result = AnalysisResult(
            cu=CompilationUnit(
                entry_module=Module("test", [], []),
                modules={"test": Module("test", [], [])}
            )
        )
        result.diagnostics.append(
            Diagnostic(kind="error", message="Test error")
        )

        with pytest.raises(ValueError, match="Cannot generate code with semantic errors"):
            backend = Backend(result)
            backend.generate()


class TestCodeGenStringHandling:
    """Test string literal handling in generated code."""

    @pytest.fixture(autouse=True)
    def _setup(self, temp_project: Path, write_l0_file, search_paths):
        self.temp_path = temp_project
        self.write_l0_file = write_l0_file
        self._search_paths = search_paths

    def getSourceSearchPaths(self):
        return self._search_paths

    def test_string_literal_basic(self):
        """Test basic string literal generation."""
        self.write_l0_file("strings", """
            module strings;
            
            extern func puts(s: string) -> int;
            
            func main() -> int {
                puts("Hello");
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("strings")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # String literals should lower to static string macro values.
        assert 'L0_STRING_CONST("Hello", 5)' in c_code
        assert '"Hello"' in c_code

    def test_string_with_escapes(self):
        """Test string literals with escape sequences."""
        self.write_l0_file("escapes", """
            module escapes;
            
            extern func puts(s: string) -> int;
            
            func main() -> int {
                puts("Line1\\nLine2");
                return 0;
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)

        result = driver.analyze("escapes")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Escape sequence is decoded to bytes, then re-encoded for C output.
        assert 'L0_STRING_CONST("Line1\\nLine2", 11)' in c_code

    def test_string_literal_semantics_match_const_and_non_const_paths(self):
        """Top-level and expression literal paths should produce identical string bytes/len."""
        self.write_l0_file("string_paths", """
            module string_paths;

            let G: string = "A\\nB";

            func f() -> string {
                return "A\\nB";
            }
        """)

        search_paths = self.getSourceSearchPaths()
        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze("string_paths")
        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Top-level static initializer uses decoded length 3 for A LF B.
        assert '= L0_STRING_CONST("A\\nB", 3);' in c_code
        # Expression-literal path uses the same decoded-byte semantics.
        assert 'return ((l0_string)L0_STRING_CONST("A\\nB", 3));' in c_code


class TestCodeGenFromFiles:
    """
    Test code generation using actual .l0 files from tests/backend/codegen/.

    This combines the benefits of:
    - Direct API calls (fast, debuggable)
    - Real test files with expected output (comprehensive)
    """

    @pytest.fixture(autouse=True)
    def _setup(self, codegen_search_paths):
        self._codegen_search_paths = codegen_search_paths

    def getSourceSearchPathsFromFiles(self):
        return self._codegen_search_paths

    @pytest.mark.parametrize("test_file", find_codegen_test_files(), ids=lambda p: p.stem)
    def test_codegen_from_file(self, test_file: Path, tmp_path: Path, compile_and_run):
        """
        Test code generation for .l0 files in tests/backend/codegen/.

        This test:
        1. Loads the .l0 file using L0Driver
        2. Analyzes it
        3. Generates C code using CBackend
        4. Compiles and runs the C code
        5. Verifies output matches .expected file
        """
        # Extract module name from file
        module_name = test_file.stem

        # Setup search paths
        search_paths = self.getSourceSearchPathsFromFiles()

        # Analyze module
        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze(module_name)

        # Check for errors
        if result.has_errors():
            error_msgs = "\n".join(d.format() for d in result.diagnostics if d.kind == "error")
            pytest.fail(f"Analysis failed for {test_file.name}:\n{error_msgs}")

        # Generate C code
        backend = Backend(result)
        c_code = backend.generate()

        # Compile and run
        success, stdout, stderr = compile_and_run(c_code, tmp_path)

        if not success:
            pytest.fail(
                f"Compilation/execution failed for {test_file.name}:\n"
                f"stderr: {stderr}\n"
                f"\nGenerated C code:\n{c_code}"
            )

        # Verify output
        expected_output = get_expected_output(test_file)
        actual_output = stdout

        # Compare outputs (normalize line endings)
        expected_lines = expected_output.strip().split("\n") if expected_output else []
        actual_lines = actual_output.strip().split("\n") if actual_output else []

        assert actual_lines == expected_lines, (
            f"Output mismatch for {test_file.name}:\n"
            f"Expected:\n{expected_output}\n"
            f"Actual:\n{actual_output}"
        )

    def test_struct_file_contents(self):
        """Verify test_struct.l0 generates correct C structures."""
        test_file = CODEGEN_TEST_DIR / "test_struct.l0"
        if not test_file.exists():
            pytest.skip("test_struct.l0 not found")

        search_paths = self.getSourceSearchPathsFromFiles()

        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze("test_struct")

        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify struct definitions
        assert "struct l0_test_struct_Point" in c_code
        assert "struct l0_test_struct_Line" in c_code
        assert "l0_int x;" in c_code
        assert "l0_int y;" in c_code

    def test_enum_file_contents(self):
        """Verify test_enum.l0 generates correct tagged unions."""
        test_file = CODEGEN_TEST_DIR / "test_enum.l0"
        if not test_file.exists():
            pytest.skip("test_enum.l0 not found")

        search_paths = self.getSourceSearchPathsFromFiles()

        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze("test_enum")

        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify enum tag definition
        assert "enum l0_test_enum_Expr_tag" in c_code

        # Verify tagged union struct
        assert "struct l0_test_enum_Expr" in c_code

        # Verify variants
        assert "l0_test_enum_Expr_Int" in c_code
        assert "l0_test_enum_Expr_Add" in c_code
        assert "l0_test_enum_Expr_Mul" in c_code

    def test_match_file_contents(self):
        """Verify test_match.l0 generates correct switch statements."""
        test_file = CODEGEN_TEST_DIR / "test_match.l0"
        if not test_file.exists():
            pytest.skip("test_match.l0 not found")

        search_paths = self.getSourceSearchPathsFromFiles()

        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze("test_match")

        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify switch statement
        assert "switch ((_scrutinee).tag)" in c_code

        # Verify case labels
        assert "case l0_test_match_Result_Ok:" in c_code
        assert "case l0_test_match_Result_Err:" in c_code

        # Verify wildcard becomes default
        assert "default:" in c_code

        # Verify switch exits
        assert "break;" in c_code


    def test_statements_file_contents(self):
        """Verify test_statements.l0 generates all statement types."""
        test_file = CODEGEN_TEST_DIR / "test_statements.l0"
        if not test_file.exists():
            pytest.skip("test_statements.l0 not found")

        search_paths = self.getSourceSearchPathsFromFiles()

        driver = L0Driver(search_paths=search_paths)
        result = driver.analyze("test_statements")

        assert not result.has_errors()

        backend = Backend(result)
        c_code = backend.generate()

        # Verify mangled function names
        assert "l0_test_statements_test_let" in c_code
        assert "l0_test_statements_test_assign" in c_code
        assert "l0_test_statements_test_if" in c_code
        assert "l0_test_statements_test_while" in c_code

        # Verify statement types present
        assert "if (" in c_code
        assert "while (" in c_code
        assert "return " in c_code


class TestCodeGenFileDiscovery:
    """Test that we can discover and validate test files."""

    @pytest.fixture(autouse=True)
    def _setup(self, codegen_search_paths):
        self._codegen_search_paths = codegen_search_paths

    def getSourceSearchPathsFromFiles(self):
        return self._codegen_search_paths

    def test_find_test_files(self):
        """Verify that test files are discovered correctly."""
        test_files = find_codegen_test_files()

        if not test_files:
            pytest.skip("No test files found in tests/backend/codegen/")

        # Verify we found expected test files
        file_names = {f.name for f in test_files}

        expected_files = {
            "test_struct.l0",
            "test_statements.l0",
            "test_expressions.l0",
            "test_constructors.l0",
            "test_match.l0",
            "test_edge_cases.l0",
        }

        # Check that expected files exist
        found = file_names & expected_files
        assert len(found) > 0, f"Expected to find some test files, found: {file_names}"

    def test_expected_files_exist(self):
        """Verify that .expected files exist for test files."""
        test_files = find_codegen_test_files()

        if not test_files:
            pytest.skip("No test files found")

        missing_expected = []
        for test_file in test_files:
            expected_file = test_file.with_suffix(".expected")
            if not expected_file.exists():
                missing_expected.append(test_file.name)

        assert not missing_expected, (
            f"Missing .expected files for: {', '.join(missing_expected)}"
        )

    def test_all_test_files_are_valid_l0(self):
        """Verify that all test files can be parsed."""
        test_files = find_codegen_test_files()

        if not test_files:
            pytest.skip("No test files found")

        search_paths = self.getSourceSearchPathsFromFiles()
        driver = L0Driver(search_paths=search_paths)

        parse_errors = []
        for test_file in test_files:
            module_name = test_file.stem
            try:
                result = driver.analyze(module_name)
                # Don't require no errors, just that it parses
                if result.cu is None:
                    parse_errors.append((test_file.name, "Failed to create compilation unit"))
            except Exception as e:
                parse_errors.append((test_file.name, str(e)))

        assert not parse_errors, (
                f"Parse errors:\n" +
                "\n".join(f"  {name}: {err}" for name, err in parse_errors)
        )
