#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Compilation unit definitions for the L0 compiler."""

from dataclasses import dataclass

from l0_ast import Module


@dataclass
class CompilationUnit:
    """A closed set of modules starting from an entry module.

    Attributes:
        entry_module: The root module of the compilation (e.g., 'app.main').
        modules: Mapping of module names to Module objects for all transitively
            imported modules, including the entry module.
    """
    entry_module: Module
    modules: dict[str, Module]

    @property
    def entry_name(self) -> str:
        """Get the name of the entry module."""
        return self.entry_module.name

    def __contains__(self, module_name: str) -> bool:
        """Check if a module is part of this compilation unit."""
        return module_name in self.modules
