#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Module path resolution for the L0 compiler.

This module provides tools for mapping L0 module names to file system paths
using configurable search roots.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceSearchPaths:
    """Search configuration for L0 modules.

    Resolution order: system_roots are searched first, then project_roots.

    Attributes:
        system_roots: List of paths for standard library and toolchain modules.
        project_roots: List of paths for user and project-specific modules.
        explicit_entry: Module name and exact source file selected by a path operand.
    """
    system_roots: list[Path] = field(default_factory=list)
    project_roots: list[Path] = field(default_factory=list)
    explicit_entry: tuple[str, Path] | None = None

    def add_system_root(self, root: str | Path) -> None:
        """Add a path to the system search roots.

        Args:
            root: The directory path to add.
        """
        self.system_roots.append(Path(root))

    def add_project_root(self, root: str | Path) -> None:
        """Add a path to the project search roots.

        Args:
            root: The directory path to add.
        """
        self.project_roots.append(Path(root))

    def module_relpath(self, module_name: str) -> Path:
        """Convert a dotted module name to its relative file path.

        Example: 'std.io' -> 'std/io.l0'

        Args:
            module_name: The dotted L0 module name.

        Returns:
            The relative Path to the module file.
        """
        return Path(*module_name.split(".")) .with_suffix(".l0")

    def resolve(self, module_name: str) -> Path:
        """Find the absolute path for an L0 module name.

        Args:
            module_name: The dotted L0 module name.

        Returns:
            The absolute Path to the first matching file found.

        Raises:
            FileNotFoundError: If the module cannot be found in any root.
        """
        if self.explicit_entry is not None and self.explicit_entry[0] == module_name:
            path = self.explicit_entry[1]
            if path.is_file():
                return path.absolute()
            raise FileNotFoundError(f"L0 source file not found: {path}")

        rel = self.module_relpath(module_name)
        for root in (*self.system_roots, *self.project_roots):
            candidate = root / rel
            if candidate.is_file():
                return candidate.absolute()

        raise FileNotFoundError(
            f"Module '{module_name}' not found in system_roots or project_roots"
        )
