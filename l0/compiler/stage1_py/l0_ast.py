#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""AST definitions for the L0 compiler."""

from dataclasses import dataclass, field


# ==========================
# AST definitions
# ==========================


@dataclass
class Span:
    """Represents a range of text in a source file.

    Attributes:
        start_line: 1-based starting line number.
        start_column: 1-based starting column number.
        end_line: 1-based ending line number.
        end_column: 1-based ending column number.
    """
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass
class Node:
    """Base class for all AST nodes.

    Attributes:
        span: Optional source span information.
    """
    span: Span | None = field(default=None, repr=False, compare=False, kw_only=True)


# --- types ---

@dataclass
class TypeRef(Node):
    """Reference to a type in the source code.

    Attributes:
        name: The name of the type (e.g., "int", "MyStruct").
        pointer_depth: Number of pointer levels (number of '*' suffixes).
        is_nullable: Whether the type is nullable (trailing '?').
        module_path: Optional list of module components for qualified names.
        name_qualifier: Optional extra segments for namespaced types.
    """
    name: str
    pointer_depth: int = 0
    is_nullable: bool = False
    module_path: list[str] | None = None
    name_qualifier: list[str] | None = None


# --- declarations ---

@dataclass
class Import(Node):
    """An import declaration.

    Attributes:
        name: The qualified name of the module being imported.
    """
    name: str


class TopLevelDecl(Node):
    """Base class for top-level declarations (functions, structs, etc.)."""
    pass


@dataclass
class Param(Node):
    """A function parameter declaration.

    Attributes:
        name: The name of the parameter.
        type: The type of the parameter.
    """
    name: str
    type: TypeRef


@dataclass
class FuncDecl(TopLevelDecl):
    """A function declaration.

    Attributes:
        name: The name of the function.
        params: List of function parameters.
        return_type: The return type of the function.
        body: The function body block.
        is_extern: Whether the function is declared as 'extern'.
    """
    name: str
    params: list[Param]
    return_type: TypeRef
    body: Block
    is_extern: bool = False


@dataclass
class FieldDecl(Node):
    """A field declaration within a struct.

    Attributes:
        name: The name of the field.
        type: The type of the field.
    """
    name: str
    type: TypeRef


@dataclass
class StructDecl(TopLevelDecl):
    """A struct declaration.

    Attributes:
        name: The name of the struct.
        fields: List of field declarations.
    """
    name: str
    fields: list[FieldDecl]


@dataclass
class EnumVariant(Node):
    """A variant declaration within an enum.

    Attributes:
        name: The name of the variant.
        fields: List of payload fields for the variant.
    """
    name: str
    fields: list[FieldDecl]


@dataclass
class EnumDecl(TopLevelDecl):
    """An enum declaration.

    Attributes:
        name: The name of the enum.
        variants: List of enum variant declarations.
    """
    name: str
    variants: list[EnumVariant]


@dataclass
class TypeAliasDecl(TopLevelDecl):
    """A type alias declaration.

    Attributes:
        name: The name of the alias.
        target: The target type being aliased.
    """
    name: str
    target: TypeRef


@dataclass
class LetDecl(TopLevelDecl):
    """A top-level 'let' declaration.

    Attributes:
        name: The name of the constant.
        type: Optional type annotation.
        value: The initialization expression.
    """
    name: str
    type: TypeRef | None
    value: Expr


@dataclass
class Module(Node):
    """A complete L0 module.

    Attributes:
        name: The name of the module.
        imports: List of module imports.
        decls: List of top-level declarations.
        filename: Optional source file path.
    """
    name: str
    imports: list[Import]
    decls: list[TopLevelDecl]
    filename: str | None = field(default=None, repr=False, compare=False, kw_only=True)


# --- statements ---

@dataclass
class Stmt(Node):
    """Base class for all statements."""
    pass


@dataclass
class Block(Stmt):
    """A block containing a sequence of statements.

    Attributes:
        stmts: List of statements in the block.
    """
    stmts: list[Stmt]


@dataclass
class LetStmt(Stmt):
    """A local variable declaration statement.

    Attributes:
        name: The name of the variable.
        type: Optional type annotation.
        value: The initialization expression.
    """
    name: str
    type: TypeRef | None
    value: Expr


@dataclass
class AssignStmt(Stmt):
    """An assignment statement.

    Attributes:
        target: The target expression (must be an l-value).
        value: The expression whose value is being assigned.
    """
    target: Expr
    value: Expr


@dataclass
class ExprStmt(Stmt):
    """A statement consisting of a single expression.

    Attributes:
        expr: The expression to execute.
    """
    expr: Expr


@dataclass
class IfStmt(Stmt):
    """An if-else statement.

    Attributes:
        cond: The condition expression.
        then_stmt: The statement to execute if the condition is true.
        else_stmt: Optional statement to execute if the condition is false.
    """
    cond: Expr
    then_stmt: Stmt
    else_stmt: Stmt | None


@dataclass
class WhileStmt(Stmt):
    """A while loop statement.

    Attributes:
        cond: The condition expression.
        body: The block to execute while the condition is true.
    """
    cond: Expr
    body: Block


@dataclass
class ForStmt(Stmt):
    """A for loop statement.

    Attributes:
        init: Optional initialization statement.
        cond: Optional condition expression.
        update: Optional update statement.
        body: The loop body block.
    """
    init: Stmt | None
    cond: Expr | None
    update: Stmt | None
    body: Block


@dataclass
class ReturnStmt(Stmt):
    """A return statement.

    Attributes:
        value: Optional expression to return.
    """
    value: Expr | None


@dataclass
class DropStmt(Stmt):
    """An explicit drop statement for manual memory/resource release.

    Attributes:
        name: The name of the variable to drop.
    """
    name: str


@dataclass
class MatchArm(Node):
    """A single arm in a match statement.

    Attributes:
        pattern: The pattern to match against.
        body: The block to execute if the pattern matches.
    """
    pattern: Pattern
    body: Block


@dataclass
class MatchStmt(Stmt):
    """A match statement for pattern matching.

    Attributes:
        expr: The expression to match.
        arms: List of match arms.
    """
    expr: Expr
    arms: list[MatchArm]


@dataclass
class WithItem(Node):
    """An item in a with statement.

    Attributes:
        init: Initialization statement.
        cleanup: Optional cleanup statement (mutually exclusive with a cleanup block in WithStmt).
    """
    init: Stmt
    cleanup: Stmt | None


@dataclass
class WithStmt(Stmt):
    """A with statement for RAII-style resource management.

    Attributes:
        items: List of items to manage.
        body: The main block of the statement.
        cleanup_body: Optional block to execute for cleanup (mutually exclusive with per-item cleanup statements).
    """
    items: list[WithItem]
    body: Block
    cleanup_body: Block | None


@dataclass
class CaseArm(Node):
    """A single arm in a case statement.

    Attributes:
        literal: The constant expression to match.
        body: The statement to execute on match.
    """
    literal: Expr
    body: Stmt


@dataclass
class CaseElse(Node):
    """The else arm of a case statement.

    Attributes:
        body: The statement to execute if no other arms match.
    """
    body: Stmt


@dataclass
class CaseStmt(Stmt):
    """A case statement (switch-like).

    Attributes:
        expr: The expression to evaluate.
        arms: List of constant arms.
        else_arm: Optional default arm.
    """
    expr: Expr
    arms: list[CaseArm]
    else_arm: CaseElse | None


@dataclass
class BreakStmt(Stmt):
    """A break statement."""
    pass


@dataclass
class ContinueStmt(Stmt):
    """A continue statement."""
    pass


# --- patterns (minimal: variant or wildcard) ---

class Pattern(Node):
    """Base class for match patterns."""
    pass


@dataclass
class WildcardPattern(Pattern):
    """A wildcard pattern ('_') that matches anything."""
    pass


@dataclass
class VariantPattern(Pattern):
    """A pattern that matches an enum variant.

    Attributes:
        name: The name of the variant.
        vars: List of variable names to bind to variant fields.
        module_path: Optional list of module components.
        name_qualifier: Optional extra name segments.
    """
    name: str
    vars: list[str]
    module_path: list[str] | None = None
    name_qualifier: list[str] | None = None


# --- expressions ---

class Expr(Node):
    """Base class for all expressions."""
    pass


@dataclass
class IntLiteral(Expr):
    """An integer literal expression.

    Attributes:
        value: The integer value.
    """
    value: int


@dataclass
class ByteLiteral(Expr):
    """A byte literal expression.

    Attributes:
        value: The byte value as a string representation.
    """
    value: str


@dataclass
class StringLiteral(Expr):
    """A string literal expression.

    Attributes:
        value: The string value.
    """
    value: str


@dataclass
class BoolLiteral(Expr):
    """A boolean literal expression.

    Attributes:
        value: The boolean value.
    """
    value: bool


@dataclass
class NullLiteral(Expr):
    """A null literal expression."""
    pass


@dataclass
class VarRef(Expr):
    """A variable reference expression.

    Attributes:
        name: The name of the variable.
        module_path: Optional list of module components.
        name_qualifier: Optional extra name segments.
    """
    name: str
    module_path: list[str] | None = None
    name_qualifier: list[str] | None = None


@dataclass
class NewExpr(Expr):
    """A heap allocation or constructor expression.

    Attributes:
        type_ref: The type to instantiate.
        args: List of constructor arguments.
    """
    type_ref: TypeRef
    args: list[Expr]


@dataclass
class UnaryOp(Expr):
    """A unary operator expression.

    Attributes:
        op: The operator string (e.g., "-", "!").
        operand: The expression the operator is applied to.
    """
    op: str
    operand: Expr


@dataclass
class BinaryOp(Expr):
    """A binary operator expression.

    Attributes:
        op: The operator string (e.g., "+", "&&").
        left: The left-hand side expression.
        right: The right-hand side expression.
    """
    op: str
    left: Expr
    right: Expr


@dataclass
class CallExpr(Expr):
    """A function or method call expression.

    Attributes:
        callee: The expression evaluating to the function to call.
        args: List of call arguments.
    """
    callee: Expr
    args: list[Expr]


@dataclass
class IndexExpr(Expr):
    """An array indexing expression.

    Attributes:
        array: The array expression.
        index: The index expression.
    """
    array: Expr
    index: Expr


@dataclass
class FieldAccessExpr(Expr):
    """A field access expression.

    Attributes:
        obj: The object expression.
        field: The name of the field to access.
    """
    obj: Expr
    field: str


@dataclass
class ParenExpr(Expr):
    """A parenthesized expression.

    Attributes:
        inner: The expression inside the parentheses.
    """
    inner: Expr


@dataclass
class CastExpr(Expr):
    """A type cast expression.

    Attributes:
        expr: The expression to cast.
        target_type: The type to cast to.
    """
    expr: Expr
    target_type: TypeRef


@dataclass
class TryExpr(Expr):
    """A try expression for error handling.

    Attributes:
        expr: The expression to attempt.
    """
    expr: Expr


@dataclass
class TypeExpr(Expr):
    """A type used in an expression position.

    Attributes:
        type_ref: The type reference.
    """
    type_ref: TypeRef
