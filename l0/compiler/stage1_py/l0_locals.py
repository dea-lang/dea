#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Lexical scope resolution for the L0 compiler.

This module provides tools for building and managing lexical scopes for
local variables, function parameters, and pattern bindings.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from l0_ast import Node, TypeRef, FuncDecl, Module, Stmt, Block, LetStmt, IfStmt, WhileStmt, MatchArm, MatchStmt, \
    CaseArm, CaseElse, CaseStmt, Pattern, WildcardPattern, VariantPattern, WithStmt
from l0_symbols import SymbolKey


class LocalKind(Enum):
    """Enumeration of the different kinds of local bindings.

    Attributes:
        PARAM: A function parameter.
        LOCAL: A variable declared via a 'let' statement.
        PATTERN_VAR: A variable bound in a 'match' variant pattern.
    """
    PARAM = auto()
    LOCAL = auto()
    PATTERN_VAR = auto()


@dataclass
class LocalSymbol:
    """Represents a single local binding.

    Attributes:
        name: The name of the binding.
        kind: The kind of binding (parameter, local or pattern variable).
        type_ref: Optional type reference from the declaration.
        decl: The AST node that introduced the binding.
    """
    name: str
    kind: LocalKind
    type_ref: TypeRef | None
    decl: Node


@dataclass
class Scope:
    """A lexical scope for local bindings.

    Scopes form a tree structure via parent pointers, mirroring the nested
    structure of the source code.

    Attributes:
        parent: The enclosing scope, or None if this is a root scope.
        symbols: Mapping of names to LocalSymbol objects in this scope.
    """
    parent: Scope | None
    symbols: dict[str, LocalSymbol] = field(default_factory=dict)

    def lookup(self, name: str) -> LocalSymbol | None:
        """Look up a name in this scope and all enclosing scopes.

        Args:
            name: The name to look up.

        Returns:
            The LocalSymbol if found, otherwise None.
        """
        scope: Scope | None = self
        while scope is not None:
            sym = scope.symbols.get(name)
            if sym is not None:
                return sym
            scope = scope.parent
        return None


@dataclass
class FunctionEnv:
    """Environment for a single function.

    Attributes:
        module_name: Name of the module containing the function.
        func: The FuncDecl AST node.
        root_scope: The function's root lexical scope.
    """
    module_name: str
    func: FuncDecl
    root_scope: Scope


class LocalScopeResolver:
    """Builds lexical scopes for functions within a compilation unit.

    This resolver traverses function bodies and creates nested scopes for
    blocks, loops, and match arms.

    Note:
        - Parameters live in the function's root scope.
        - Top-level lets inside the function body also live in the root scope.
        - Each nested Block inside control flow structures gets its own child scope.
        - Pattern variables in a 'match' arm live in the arm's scope.

    Attributes:
        modules: Mapping of module names to Module AST nodes.
        function_envs: Mapping of (module, func) names to FunctionEnv objects.

    See Also:
        `get_block_scope` and `get_match_arm_scope` methods for retrieving scopes by AST node.
    """

    def __init__(self, modules: dict[str, Module]) -> None:
        """Initialize the local scope resolver.

        Args:
            modules: The modules to analyze.
        """
        self.modules = modules

        # (module_name, func_name) -> FunctionEnv
        self.function_envs: dict[SymbolKey, FunctionEnv] = {}

        # Node id -> Scope
        # We avoid using AST nodes as dict keys directly because dataclasses
        # are unhashable by default.
        self._block_scopes: dict[int, Scope] = {}
        self._match_arm_scopes: dict[int, Scope] = {}

    # --- public API ---

    def resolve(self) -> dict[SymbolKey, FunctionEnv]:
        """Build scopes for all non-extern functions in the modules.

        Returns:
            A mapping from function identifiers to their environments.
        """
        for module_name, module in self.modules.items():
            for decl in module.decls:
                if isinstance(decl, FuncDecl) and not decl.is_extern:
                    fe = self._build_function_env(module_name, decl)
                    self.function_envs[(module_name, decl.name)] = fe
        return self.function_envs

    def get_block_scope(self, block: Block) -> Scope | None:
        """Get the lexical scope associated with a block.

        Args:
            block: The Block AST node.

        Returns:
            The associated Scope if found, otherwise None.
        """
        return self._block_scopes.get(id(block))

    def get_match_arm_scope(self, arm: MatchArm) -> Scope | None:
        """Get the lexical scope associated with a match arm.

        Args:
            arm: The MatchArm AST node.

        Returns:
            The associated Scope if found, otherwise None.
        """
        return self._match_arm_scopes.get(id(arm))

    # --- internal helpers ---

    def _build_function_env(self, module_name: str, func: FuncDecl) -> FunctionEnv:
        """Build the environment and root scope for a single function."""
        root = Scope(parent=None)

        # Parameters live in the root scope.
        for param in func.params:
            self._declare(root, param.name, LocalKind.PARAM, param.type, param)

        # The function body uses the root scope directly.
        self._block_scopes[id(func.body)] = root
        self._visit_block(func.body, root)

        return FunctionEnv(module_name=module_name, func=func, root_scope=root)

    def _visit_block(self, block: Block, scope: Scope) -> None:
        """Traverse a block and populate scopes."""
        for stmt in block.stmts:
            self._visit_stmt(stmt, scope)

    def _visit_stmt(self, stmt: Stmt, scope: Scope) -> None:
        """Visit a statement and handle any scope introductions."""
        if isinstance(stmt, LetStmt):
            self._declare(scope, stmt.name, LocalKind.LOCAL, stmt.type, stmt)
            return

        if isinstance(stmt, IfStmt):
            self._visit_stmt(stmt.then_stmt, scope)
            # 'else' branch (if any) also gets visited in the same scope.
            if stmt.else_stmt is not None:
                self._visit_stmt(stmt.else_stmt, scope)
            return

        if isinstance(stmt, WhileStmt):
            body_scope = Scope(parent=scope)
            self._block_scopes[id(stmt.body)] = body_scope
            self._visit_block(stmt.body, body_scope)
            return

        if isinstance(stmt, MatchStmt):
            for arm in stmt.arms:
                self._visit_match_arm(arm, scope)
            return

        if isinstance(stmt, WithStmt):
            self._visit_with_stmt(stmt, scope)
            return

        if isinstance(stmt, CaseStmt):
            for arm in stmt.arms:
                self._visit_case_arm(arm, scope)
            if stmt.else_arm is not None:
                self._visit_case_else(stmt.else_arm, scope)
            return

        if isinstance(stmt, Block):
            # Register a new scope for this block.
            block_scope = Scope(parent=scope)
            self._block_scopes[id(stmt)] = block_scope
            self._visit_block(stmt, block_scope)
            return

        # ReturnStmt, AssignStmt, ExprStmt and others do not introduce scopes or new bindings; nothing to do here.

    def _visit_with_stmt(self, stmt: WithStmt, parent_scope: Scope) -> None:
        """Visit a with statement and manage its header and body scopes."""
        # The with header creates a scope for variables declared by items.
        # Items are sequential: item N sees names from items 0...N-1.
        header_scope = Scope(parent=parent_scope)

        for item in stmt.items:
            # Visit init statement in the header scope
            self._visit_stmt(item.init, header_scope)
            # Cleanup expressions are visited in header scope too (they see
            # all items declared so far including the current one)
            # No new bindings from cleanup

        # Body gets a nested scope under the header scope
        body_scope = Scope(parent=header_scope)
        self._block_scopes[id(stmt.body)] = body_scope
        self._visit_block(stmt.body, body_scope)

        # Cleanup body (if present) is resolved in the header scope
        if stmt.cleanup_body is not None:
            cleanup_scope = Scope(parent=header_scope)
            self._block_scopes[id(stmt.cleanup_body)] = cleanup_scope
            self._visit_block(stmt.cleanup_body, cleanup_scope)

    def _visit_match_arm(self, arm: MatchArm, parent_scope: Scope) -> None:
        """Visit a match arm and create its child scope."""
        arm_scope = Scope(parent=parent_scope)
        self._match_arm_scopes[id(arm)] = arm_scope
        self._block_scopes[id(arm.body)] = arm_scope

        # Bind pattern variables (if any).
        self._bind_pattern_vars(arm.pattern, arm_scope)

        # Visit the arm body in this scope.
        self._visit_block(arm.body, arm_scope)

    def _visit_case_arm(self, arm: CaseArm, parent_scope: Scope) -> None:
        """Visit a case arm."""
        arm_scope = Scope(parent=parent_scope)

        if isinstance(arm.body, Block):
            self._block_scopes[id(arm.body)] = arm_scope
            self._visit_block(arm.body, arm_scope)
        else:
            self._visit_stmt(arm.body, arm_scope)

    def _visit_case_else(self, arm: CaseElse, parent_scope: Scope) -> None:
        """Visit a case else arm."""
        arm_scope = Scope(parent=parent_scope)

        if isinstance(arm.body, Block):
            self._block_scopes[id(arm.body)] = arm_scope
            self._visit_block(arm.body, arm_scope)
        else:
            self._visit_stmt(arm.body, arm_scope)

    def _bind_pattern_vars(self, pattern: Pattern, scope: Scope) -> None:
        """Bind variables introduced by a pattern in the given scope."""
        if isinstance(pattern, VariantPattern):
            for var_name in pattern.vars:
                # Pattern variables have no explicit type at this stage.
                self._declare(scope, var_name, LocalKind.PATTERN_VAR, None, pattern)
        elif isinstance(pattern, WildcardPattern):
            # '_' does not introduce a binding.
            return
        else:
            # Future pattern forms would go here.
            return

    def _declare(
            self,
            scope: Scope,
            name: str,
            kind: LocalKind,
            type_ref: TypeRef | None,
            decl: Node,
    ) -> LocalSymbol:
        """Declare a local symbol in the given scope."""
        if name in scope.symbols:
            return scope.symbols[name]
        sym = LocalSymbol(name=name, kind=kind, type_ref=type_ref, decl=decl)
        scope.symbols[name] = sym
        return sym
