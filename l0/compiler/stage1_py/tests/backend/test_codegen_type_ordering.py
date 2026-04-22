"""
Comprehensive tests for dependency-based type ordering in code generation.

Tests verify that structs and enums are emitted in the correct order based on
value-type dependencies, regardless of declaration order in source.
"""

#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from l0_backend import Backend
from l0_driver import L0Driver


# ============================================================================
# Test 1 & 2: Basic dependency cases (already covered by existing tests)
# ============================================================================


def test_struct_depends_on_enum(codegen_single):
    """Verify struct containing enum field - enum must be defined first."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Token {
            id: int;
            token_type: TokenType;
        }

        enum TokenType {
            Ident;
            Keyword;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify enum is defined before struct
    enum_pos = c_code.find("enum l0_main_TokenType_tag")
    struct_pos = c_code.find("struct l0_main_Token {")

    assert enum_pos > 0, "Enum definition not found"
    assert struct_pos > 0, "Struct definition not found"
    assert enum_pos < struct_pos, "Enum should be defined before struct"


def test_enum_depends_on_struct(codegen_single):
    """Verify enum variant containing struct field - struct must be defined first."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        enum Shape {
            Circle(center: Point, radius: int);
            Rectangle(topLeft: Point, bottomRight: Point);
        }

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify struct is defined before enum
    struct_pos = c_code.find("struct l0_main_Point {")
    enum_pos = c_code.find("enum l0_main_Shape_tag")

    assert struct_pos > 0, "Struct definition not found"
    assert enum_pos > 0, "Enum definition not found"
    assert struct_pos < enum_pos, "Struct should be defined before enum"


# ============================================================================
# Test 3: Chain dependency
# ============================================================================


def test_chain_dependency(codegen_single):
    """Test chain of dependencies: C depends on B depends on A."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct C {
            b: B;
        }

        struct B {
            a: A;
        }

        struct A {
            x: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify order: A before B before C
    a_pos = c_code.find("struct l0_main_A {")
    b_pos = c_code.find("struct l0_main_B {")
    c_pos = c_code.find("struct l0_main_C {")

    assert a_pos > 0 and b_pos > 0 and c_pos > 0, "All struct definitions should exist"
    assert a_pos < b_pos < c_pos, "Order should be A, B, C"


# ============================================================================
# Test 4: Diamond dependency
# ============================================================================


def test_diamond_dependency(codegen_single):
    """Test diamond pattern: Top depends on Left and Right, both depend on Base."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Top {
            left: Left;
            right: Right;
        }

        struct Left {
            base: Base;
        }

        struct Right {
            base: Base;
        }

        struct Base {
            x: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify order: Base before both Left and Right, which are before Top
    base_pos = c_code.find("struct l0_main_Base {")
    left_pos = c_code.find("struct l0_main_Left {")
    right_pos = c_code.find("struct l0_main_Right {")
    top_pos = c_code.find("struct l0_main_Top {")

    assert all(p > 0 for p in [base_pos, left_pos, right_pos, top_pos]), \
        "All struct definitions should exist"

    assert base_pos < left_pos and base_pos < right_pos, \
        "Base should be defined before Left and Right"

    assert left_pos < top_pos and right_pos < top_pos, \
        "Left and Right should be defined before Top"


# ============================================================================
# Test 5: Pointer breaks dependency
# ============================================================================


def test_pointer_breaks_dependency(codegen_single):
    """Test that pointer fields don't create dependencies (forward decls work)."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Node {
            value: int;
            next: Node*;
        }

        enum Expr {
            Int(value: int);
            Add(left: Expr*, right: Expr*);
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Both should compile successfully without cycle errors
    # Order doesn't matter since pointers don't create dependencies
    assert "struct l0_main_Node {" in c_code
    assert "enum l0_main_Expr_tag" in c_code


# ============================================================================
# Test 6: Value-optional creates dependency
# ============================================================================


def test_value_optional_creates_dependency(codegen_single, compile_and_run, tmp_path):
    """Test that value-optional fields (T?) create dependencies and early wrappers."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Container {
            maybe_point: Point?;
        }

        struct Point {
            x: int;
            y: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify Point and its optional wrapper are defined before Container.
    point_pos = c_code.find("struct l0_main_Point {")
    wrapper_pos = c_code.find(
        "typedef struct { l0_bool has_value; struct l0_main_Point value; } l0_opt_s_l0_main_Point;"
    )
    container_pos = c_code.find("struct l0_main_Container {")

    assert point_pos > 0 and wrapper_pos > 0 and container_pos > 0, \
        "Point, optional wrapper, and Container definitions should exist"
    assert point_pos < wrapper_pos < container_pos, \
        "Point optional wrapper should be emitted before dependent type definitions"

    success, _stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, f"generated C should compile, stderr:\n{stderr}"


# ============================================================================
# Test 7: Pointer-optional does NOT create dependency
# ============================================================================


def test_pointer_optional_no_dependency(codegen_single):
    """Test that pointer-optional fields (T*?) don't create dependencies."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Node {
            value: int;
            next: Node*?;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Should compile successfully - self-reference via pointer-optional is OK
    assert "struct l0_main_Node {" in c_code


# ============================================================================
# Test 8: Cross-module dependencies
# ============================================================================


def test_multiple_modules(write_l0_file, temp_project):
    """Test dependencies across module boundaries."""
    # Create geo module with Point
    write_l0_file(
        "geo",
        """
        module geo;

        struct Point {
            x: int;
            y: int;
        }
        """,
    )

    # Create shapes module that depends on geo
    write_l0_file(
        "shapes",
        """
        module shapes;
        import geo;

        enum Shape {
            Circle(center: Point, radius: int);
        }
        """,
    )

    # Analyze shapes (will pull in geo)
    driver = L0Driver()
    driver.search_paths.add_project_root(temp_project)
    result = driver.analyze("shapes")

    assert not result.has_errors(), f"Analysis errors: {result.diagnostics}"

    backend = Backend(result)
    c_code = backend.generate()

    # Verify geo::Point is defined before shapes::Shape
    point_pos = c_code.find("struct l0_geo_Point {")
    shape_pos = c_code.find("enum l0_shapes_Shape_tag")

    assert point_pos > 0 and shape_pos > 0, "Both definitions should exist"
    assert point_pos < shape_pos, "Point should be defined before Shape"


# ============================================================================
# Test 9: Independent types
# ============================================================================


def test_independent_types(codegen_single):
    """Test multiple disconnected type families can be emitted in any order."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct PointA {
            x: int;
        }

        struct PointB {
            y: int;
        }

        enum ColorA {
            Red;
        }

        enum ColorB {
            Blue;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # All types should be present (order among independent families doesn't matter)
    assert "struct l0_main_PointA {" in c_code
    assert "struct l0_main_PointB {" in c_code
    assert "enum l0_main_ColorA_tag" in c_code
    assert "enum l0_main_ColorB_tag" in c_code


# ============================================================================
# Test 10: Complex mixed dependencies
# ============================================================================


def test_complex_mixed_dependencies(codegen_single):
    """Test complex scenario with structs, enums, pointers, and optionals."""
    c_code, _ = codegen_single(
        "main",
        """
        module main;

        struct Graph {
            nodes: NodeList*;
            root: Node?;
        }

        struct NodeList {
            head: Node*;
        }

        struct Node {
            id: int;
            status: Status;
            next: Node*;
        }

        enum Status {
            Active;
            Inactive(reason: Reason);
        }

        struct Reason {
            code: int;
        }

        func main() -> int {
            return 0;
        }
        """,
    )
    assert c_code is not None

    # Verify dependency order:
    # - Reason before Status (Status contains Reason)
    # - Status before Node (Node contains Status)
    # - Node before NodeList and Graph (but pointers don't force strict order)

    reason_pos = c_code.find("struct l0_main_Reason {")
    status_pos = c_code.find("enum l0_main_Status_tag")
    node_pos = c_code.find("struct l0_main_Node {")

    assert all(p > 0 for p in [reason_pos, status_pos, node_pos]), \
        "All type definitions should exist"

    assert reason_pos < status_pos, "Reason should be defined before Status"
    assert status_pos < node_pos, "Status should be defined before Node"

    # Graph and NodeList should exist (order relative to Node may vary)
    assert "struct l0_main_Graph {" in c_code
    assert "struct l0_main_NodeList {" in c_code
