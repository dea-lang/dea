#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from enum import Enum

from l0_compilation import CompilationUnit
from l0_context import CompilationContext
from l0_diagnostics import Diagnostic
from l0_locals import FunctionEnv
from l0_signatures import StructInfo, EnumInfo
from l0_symbols import SymbolKey, ModuleEnv
from l0_types import Type, FuncType, BuiltinType, StructType, EnumType, NullableType, PointerType


class VarRefResolution(Enum):
    """Enumeration of variable reference resolution targets."""
    LOCAL = "local"
    MODULE = "module"


@dataclass
class AnalysisResult:
    """Full front-end analysis result for an entry module.

    Attributes:
        cu: The compilation unit containing all modules.
        context: Cross-cutting compiler options and configuration.
        module_envs: Module-level symbol environments keyed by module name.
        func_types: Function signatures keyed by (module_name, decl_name).
        struct_infos: Struct definitions keyed by (module_name, decl_name).
        enum_infos: Enum definitions keyed by (module_name, decl_name).
        func_envs: Function scope information keyed by (module_name, decl_name).
        let_types: Types of top-level 'let' declarations keyed by (module_name, decl_name).
        expr_types: Resolved types of expressions keyed by id(expr_node).
        var_ref_resolution: Resolution targets for VarRef nodes keyed by id(expr_node).
        intrinsic_targets: Target types for intrinsic operations keyed by id(expr_node).
        diagnostics: List of all diagnostics accumulated during analysis.
    """
    cu: CompilationUnit | None = None
    context: CompilationContext = field(default_factory=CompilationContext.default)

    module_envs: dict[str, ModuleEnv] = field(default_factory=dict)

    # Keys are (module_name, decl_name)
    func_types: dict[SymbolKey, FuncType] = field(default_factory=dict)
    struct_infos: dict[SymbolKey, StructInfo] = field(default_factory=dict)
    enum_infos: dict[SymbolKey, EnumInfo] = field(default_factory=dict)
    func_envs: dict[SymbolKey, FunctionEnv] = field(default_factory=dict)
    let_types: dict[SymbolKey, Type] = field(default_factory=dict)

    # Expression types keyed by id(expr_node)
    expr_types: dict[int, Type] = field(default_factory=dict)

    # VarRef resolution keyed by id(expr_node): VarRefResolution.LOCAL or VarRefResolution.MODULE
    var_ref_resolution: dict[int, VarRefResolution] = field(default_factory=dict)

    # Intrinsic function/type targets keyed by intrinsic id(expr_node)
    intrinsic_targets: dict[int, Type] = field(default_factory=dict)

    diagnostics: list[Diagnostic] = field(default_factory=list)

    def has_errors(self) -> bool:
        """Check if any 'error' diagnostics were reported.

        Returns:
            True if at least one error exists, False otherwise.
        """
        return any(d.kind == "error" for d in self.diagnostics)

    def has_warnings(self) -> bool:
        """Check if any 'warning' diagnostics were reported.

        Returns:
            True if at least one warning exists, False otherwise.
        """
        return any(d.kind == "warning" for d in self.diagnostics)

    def is_arc_type(self, ty: Type) -> bool:
        """Check if a type requires Automatic Reference Counting (ARC).

        Currently, only the 'string' builtin type requires ARC.

        Args:
            ty: The type to check.

        Returns:
            True if the type is managed by ARC, False otherwise.
        """
        return isinstance(ty, BuiltinType) and ty.name == "string"

    def has_arc_data(self, typ: Type) -> bool:
        """Check if a type transitively contains ARC-managed data.

        This is used to determine if a value of this type requires retain/release
        orchestration during assignment or when going out of scope.

        Args:
            typ: The type to check.

        Returns:
            True if the type or any of its components are managed by ARC,
            False otherwise.
        """
        if self.is_arc_type(typ):
            return True

        if isinstance(typ, StructType):
            info = self.struct_infos.get((typ.module, typ.name))
            if info is None:
                return False
            return any(self.has_arc_data(f.type) for f in info.fields)

        if isinstance(typ, EnumType):
            enum_info = self.enum_infos.get((typ.module, typ.name))
            if enum_info is None:
                return False
            return any(
                any(self.has_arc_data(ft) for ft in vi.field_types)
                for vi in enum_info.variants.values()
            )

        if isinstance(typ, NullableType):
            if isinstance(typ.inner, PointerType):
                return False
            return self.has_arc_data(typ.inner)

        return False
