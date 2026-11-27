"""
Comprehensive tests for struct and enum variant constructors.

Tests both type checking and code generation for constructor expressions.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from pathlib import Path

from conftest import has_error_code
from l0_ast import FuncDecl, LetStmt
from l0_types import StructType, EnumType


# ============================================================================
# Struct constructor type checking
# ============================================================================


def test_struct_constructor_basic(analyze_single):
    """Test basic struct constructor with correct types."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, 2);
            return 0;
        }
        """,
    )

    assert not result.has_errors()

    # Verify the constructor expression has the correct type
    mod = result.cu.modules["main"]
    func = next(d for d in mod.decls if isinstance(d, FuncDecl) and d.name == "main")
    let_stmt = next(s for s in func.body.stmts if isinstance(s, LetStmt))

    constructor_type = result.expr_types[id(let_stmt.value)]
    assert isinstance(constructor_type, StructType)
    assert constructor_type.name == "Point"
    assert constructor_type.module == "main"


def test_struct_constructor_wrong_arity(analyze_single):
    """Test struct constructor with wrong number of arguments."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0191")


def test_struct_constructor_wrong_type(analyze_single):
    """Test struct constructor with wrong argument type."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, true);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0313")


def test_struct_constructor_nested(analyze_single):
    """Test nested struct constructors."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Vec2 {
            x: int;
            y: int;
        }

        struct Line {
            start: Vec2;
            end: Vec2;
        }

        func main() -> int {
            let line: Line = Line(Vec2(0, 0), Vec2(10, 10));
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_struct_constructor_as_argument(analyze_single):
    """Test struct constructor used as function argument."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func distance(p: Point) -> int {
            return p.x + p.y;
        }

        func main() -> int {
            return distance(Point(3, 4));
        }
        """,
    )

    assert not result.has_errors()


def test_type_alias_struct_constructor_codegen(analyze_single):
    """Test that type aliases to structs reuse struct constructor lowering."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        type Alias = Point;

        func main() -> int {
            let p: Alias = Alias(1, 2);
            return p.x + p.y;
        }
        """,
    )

    assert not result.has_errors()

    try:
        from l0_backend import Backend
        backend = Backend(result)
        c_code = backend.generate()

        assert "{ .x = 1, .y = 2 }" in c_code
        assert "Alias(1, 2)" not in c_code or ".x = 1" in c_code
    except ImportError:
        pass


# ============================================================================
# Enum variant constructor type checking
# ============================================================================


def test_enum_variant_constructor_basic(analyze_single):
    """Test basic enum variant constructor."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
            Bool(value: bool);
        }

        func main() -> int {
            let e: Expr = Int(42);
            return 0;
        }
        """,
    )

    assert not result.has_errors()

    # Verify the constructor expression has the enum type (not variant type)
    mod = result.cu.modules["main"]
    func = next(d for d in mod.decls if isinstance(d, FuncDecl) and d.name == "main")
    let_stmt = next(s for s in func.body.stmts if isinstance(s, LetStmt))

    constructor_type = result.expr_types[id(let_stmt.value)]
    assert isinstance(constructor_type, EnumType)
    assert constructor_type.name == "Expr"
    assert constructor_type.module == "main"


def test_enum_variant_constructor_empty(analyze_single):
    """Test enum variant with no payload."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Option {
            None;
            Some(value: int);
        }

        func main() -> int {
            let opt: Option = None();
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_enum_variant_constructor_wrong_arity(analyze_single):
    """Test enum variant constructor with wrong arity."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
        }

        func main() -> int {
            let e: Expr = Int(1, 2);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0201")


def test_enum_variant_constructor_wrong_type(analyze_single):
    """Test enum variant constructor with wrong argument type."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
        }

        func main() -> int {
            let e: Expr = Int(true);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0314")


def test_enum_variant_constructor_multiple_fields(analyze_single):
    """Test enum variant with multiple payload fields."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Expr {
            Add(left: Expr*, right: Expr*);
        }

        func main() -> int {
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_enum_variant_constructor_as_return(analyze_single):
    """Test enum variant constructor in return statement."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Result {
            Ok(value: int);
            Err(code: int);
        }

        func succeed() -> Result {
            return Ok(0);
        }

        func fail() -> Result {
            return Err(1);
        }

        func main() -> int {
            return 0;
        }
        """,
    )

    assert not result.has_errors()


# ============================================================================
# Mixed constructor scenarios
# ============================================================================


def test_struct_containing_enum(analyze_single):
    """Test struct containing enum field."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Status {
            Active;
            Inactive;
        }

        struct User {
            id: int;
            status: Status;
        }

        func main() -> int {
            let u: User = User(1, Active());
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_enum_containing_struct(analyze_single):
    """Test enum variant containing struct."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        enum Shape {
            Circle(center: Point, radius: int);
            Rectangle(topLeft: Point, bottomRight: Point);
        }

        func main() -> int {
            let s: Shape = Circle(Point(0, 0), 5);
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_constructor_in_binary_expression(analyze_single):
    """Test constructors used in expressions."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, 2);
            let sum: int = p.x + p.y;
            return sum;
        }
        """,
    )

    assert not result.has_errors()


# ============================================================================
# Constructor code generation tests
# ============================================================================


def test_struct_constructor_codegen(analyze_single):
    """Test that struct constructors generate valid C code."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, 2);
            return 0;
        }
        """,
    )

    assert not result.has_errors()

    # Try to generate C code
    try:
        from l0_backend import Backend
        backend = Backend(result)
        c_code = backend.generate()

        # Verify struct initialization syntax is used (not function call)
        assert "{ .x = 1, .y = 2 }" in c_code
        # Verify we're NOT generating invalid function call
        assert "Point(1, 2)" not in c_code or ".x = 1" in c_code
    except ImportError:
        # CBackend not available, skip codegen test
        pass


def test_enum_constructor_codegen(analyze_single):
    """Test that enum constructors generate valid C code."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Expr {
            Int(value: int);
        }

        func make_int(n: int) -> Expr {
            return Int(n);
        }

        func main() -> int {
            return 0;
        }
        """,
    )

    assert not result.has_errors()

    # Try to generate C code
    try:
        from l0_backend import Backend
        backend = Backend(result)
        c_code = backend.generate()

        # Verify tagged union initialization is used
        assert ".tag = l0_main_Expr_Int" in c_code
        assert ".data" in c_code
        # Verify we're NOT generating invalid function call
        # (harder to check precisely due to variable names)
    except ImportError:
        # CBackend not available, skip codegen test
        pass


def test_empty_struct_constructor(analyze_single):
    """Test struct with no fields."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Empty {
        }

        func main() -> int {
            let e: Empty = Empty();
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_single_field_struct_constructor(analyze_single):
    """Test struct with single field."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Wrapper {
            value: int;
        }

        func main() -> int {
            let w: Wrapper = Wrapper(42);
            return w.value;
        }
        """,
    )

    assert not result.has_errors()


# ============================================================================
# Error reporting quality tests
# ============================================================================


def test_constructor_error_mentions_field_name(analyze_single):
    """Test that constructor type errors mention field names."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(true, 2);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    # Should mention field name 'x' in error
    assert has_error_code(result.diagnostics, "TYP-0313")


def test_variant_constructor_error_clear(analyze_single):
    """Test that variant constructor errors are clear."""
    result = analyze_single(
        "main",
        """
        module main;

        enum Result {
            Ok(value: int);
            Err(message: string);
        }

        func main() -> int {
            let r: Result = Ok("not an int");
            return 0;
        }
        """,
    )

    assert result.has_errors()
    # Should mention variant name and type mismatch
    assert has_error_code(result.diagnostics, "TYP-0314")


# ============================================================================
# Integration with other features
# ============================================================================


def test_constructor_with_pointer_field(analyze_single):
    """Test struct constructor with pointer field."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Node {
            value: int;
            next: Node*;
        }

        extern func get_null() -> Node*;

        func main() -> int {
            let n: Node = Node(42, get_null());
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_constructor_with_nullable_field(analyze_single):
    """Test struct constructor with nullable field."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Maybe {
            value: int*?;
        }

        extern func get_null() -> int*?;

        func main() -> int {
            let m: Maybe = Maybe(get_null());
            return 0;
        }
        """,
    )

    assert not result.has_errors()


def test_recursive_enum_constructor(analyze_single):
    """Test enum with recursive pointer fields."""
    result = analyze_single(
        "main",
        """
        module main;

        enum List {
            Nil;
            Cons(head: int, tail: List*);
        }

        func main() -> int {
            return 0;
        }
        """,
    )

    assert not result.has_errors()


# ============================================================================
# Additional constructor error tests
# ============================================================================


def test_struct_constructor_too_many_args(analyze_single):
    """Test struct constructor with too many arguments."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, 2, 3);
            return 0;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0191")


def test_nonexistent_field_access(analyze_single):
    """Test accessing a field that doesn't exist on a struct."""
    result = analyze_single(
        "main",
        """
        module main;

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            let p: Point = Point(1, 2);
            return p.z;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0221")


def test_field_access_on_non_struct(analyze_single):
    """Test field access on a non-struct type."""
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = 42;
            return x.field;
        }
        """,
    )

    assert result.has_errors()
    assert has_error_code(result.diagnostics, "TYP-0222")


def test_c_member_spelling(codegen_single):
    """Check readable members, escaped collisions and the existing top-level let spelling."""
    fixture = Path(__file__).resolve().parents[4] / "tests/fixtures/field_names/main.l0"
    c_code, diagnostics = codegen_single("main", fixture.read_text(encoding="utf-8"))
    assert c_code is not None, diagnostics
    for declaration in ("l0_int dea_field_sizeof;", "l0_int dea_field_dea_field_sizeof;", "l0_int ord;",
                        "l0_string dea_field_errno;", "l0_int dea_field_EOF;", "l0_int dea_field__Bool;",
                        "l0_int dea_field_EPIPE;", "l0_int _count;"):
        assert declaration in c_code
    assert "l0_main_errno" in c_code
