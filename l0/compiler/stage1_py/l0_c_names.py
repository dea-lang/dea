# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import Set
from l0_types import EnumType


@dataclass
class CNames:
    """C identifiers and the session-local temporary-name sequence."""

    C_KEYWORDS: Set[str] = field(default_factory=lambda: {
        # C89/C99 keywords
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
        'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
        'inline', 'int', 'long', 'register', 'restrict', 'return', 'short',
        'signed', 'sizeof', 'static', 'struct', 'switch', 'typedef', 'union',
        'unsigned', 'void', 'volatile', 'while',
        # C23 additions
        'alignas', 'alignof', 'atomic', 'bool', 'complex', 'imaginary',
        # Other identifiers to avoid
        'NULL', 'null', 'bool', 'true', 'false', 'asm', 'offsetof', 'typeof',
    })
    _tmp_counter: int = 0

    def mangle_struct_name(self, module_name: str, struct_name: str) -> str:
        """Mangle a struct name to avoid C namespace collisions.

        Args:
            module_name: Module name.
            struct_name: L0 struct name.

        Returns:
            Mangled C struct name (e.g., "l0_module_Point").
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{struct_name}"

    def mangle_enum_name(self, module_name: str, enum_name: str) -> str:
        """Mangle an enum name.

        Args:
            module_name: Module name.
            enum_name: L0 enum name.

        Returns:
            Mangled C enum name.
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{enum_name}"

    def mangle_function_name(self, module_name: str, func_name: str) -> str:
        """Mangle a function name.

        Args:
            module_name: Module name.
            func_name: L0 function name.

        Returns:
            Mangled C function name.
        """
        mangled_module = module_name.replace(".", "_")
        return f"l0_{mangled_module}_{func_name}"

    def mangle_let_name(self, module_name: str, let_name: str) -> str:
        """Mangle a top-level let name to C identifier.

        Args:
            module_name: Module name.
            let_name: L0 constant name.

        Returns:
            Mangled C identifier.
        """
        safe_module = module_name.replace(".", "_")
        safe_name = let_name
        if safe_name in self.C_KEYWORDS:
            safe_name = f"l0_kw_{safe_name}"
        return f"l0_{safe_module}_{safe_name}"

    def mangle_identifier(self, name: str) -> str:
        """Mangle an identifier if it conflicts with C keywords or L0 names.

        Used for local variables, parameters, and pattern variables.
        Appends '__v' suffix to avoid C keyword conflicts. Also mangles names
        starting with '_' or 'l0_'/'L0_' to avoid clashes with runtime names.

        Args:
            name: The L0 identifier to mangle.

        Returns:
            The safe C identifier.
        """
        if name in self.C_KEYWORDS or name.endswith("__v") or name.startswith("l0_") or name.startswith("L0_") or name.startswith("_"):
            return f"{name}__v"
        return name

    def fresh_tmp(self, kind: str = "tmp") -> str:
        """Generate a unique temporary variable name.

        Args:
            kind: Category of temporary (e.g., "tmp", "ptr", "try").

        Returns:
            Unique C identifier like "l0_tmp_1", "l0_ptr_2", etc.
        """
        self._tmp_counter += 1
        return f"l0_{kind}_{self._tmp_counter}"

    def emit_enum_tag(self, enum_type: EnumType, variant_name: str) -> str:
        """Emit C tag enum value for an enum variant.

        Args:
            enum_type: The L0 enum type.
            variant_name: The name of the variant.

        Returns:
            The mangled C enum tag identifier.
        """
        c_enum_name = self.mangle_enum_name(enum_type.module, enum_type.name)
        return f"{c_enum_name}_{variant_name}"
