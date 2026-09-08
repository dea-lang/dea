#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Scope tracking for resource management in the L0 compiler.

This module provides the ScopeContext class, used during code generation to
track variable lifetimes and schedule mandatory cleanups (ARC releases and
'with' statement logic).
"""

from dataclasses import dataclass, field

from l0_types import Type
from l0_ast import Block, Stmt


@dataclass
class ScopeContext:
    """Tracks variables and cleanup requirements for a single lexical scope.

    Attributes:
        owned_vars: Variables that must be cleaned up when the scope is exited.
        declared_vars: All variables visible in this scope, used for type lookups.
        parent: The enclosing scope context, if any.
        with_cleanup_inline: List of cleanup statements for inline 'with' items.
        with_cleanup_block: Optional block for 'with ... cleanup { ... }'.
        with_cleanup_in_progress: Reentrancy guard for with-cleanup emission.
    """
    owned_vars: list[tuple[str, Type]] = field(default_factory=list)
    declared_vars: list[tuple[str, Type]] = field(default_factory=list)
    parent: ScopeContext | None = None
    with_cleanup_inline: list[Stmt] | None = None
    with_cleanup_block: Block | None = None
    with_cleanup_in_progress: bool = False

    def add_owned(self, var_name: str, var_type: Type) -> None:
        """Mark a variable as owned (requiring cleanup) and declared.

        Args:
            var_name: The (mangled) name of the variable.
            var_type: The L0 Type of the variable.
        """
        if var_type is not None:
            self.owned_vars.append((var_name, var_type))
            self.declared_vars.append((var_name, var_type))

    def add_declared(self, var_name: str, var_type: Type) -> None:
        """Mark a variable as declared for type lookup only.

        Used for function parameters and pattern variables, which are
        managed by the caller or scrutinee and do not require cleanup
        within the current scope.

        Args:
            var_name: The (mangled) name of the variable.
            var_type: The L0 Type of the variable.
        """
        if var_type is not None:
            self.declared_vars.append((var_name, var_type))

    def remove_owned(self, var_name: str) -> None:
        """Remove a variable from the owned set.

        Args:
            var_name: The (mangled) name of the variable to stop tracking.
        """
        self.owned_vars = [(name, ty) for name, ty in self.owned_vars if name != var_name]
