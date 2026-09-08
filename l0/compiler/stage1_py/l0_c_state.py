# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import NoReturn
from l0_analysis import AnalysisResult
from l0_ast import EnumDecl, EnumVariant, Node
from l0_internal_error import InternalCompilerError, ICELocation
from l0_signatures import EnumInfo, StructInfo
from l0_string_escape import encode_c_string_bytes
from l0_types import StructType, EnumType
from l0_c_builder import CCodeBuilder


@dataclass
class CEmitterState:
    """Shared analysis, output, diagnostic context, and active source location."""

    analysis: AnalysisResult | None = None
    current_module: str | None = None
    out: CCodeBuilder = field(default_factory=CCodeBuilder)
    _active_line_directive: str | None = None

    def find_variant_decl(
            self, module_name: str, enum_name: str, variant_name: str
    ) -> EnumVariant | None:
        """Look up an enum variant's AST declaration.

        Args:
            module_name: Name of the module containing the enum.
            enum_name: Name of the enum.
            variant_name: Name of the variant to find.

        Returns:
            The EnumVariant node if found, otherwise None.
        """
        if self.analysis.cu is None:
            return None
        module = self.analysis.cu.modules.get(module_name)
        if not module:
            return None
        for decl in module.decls:
            if isinstance(decl, EnumDecl) and decl.name == enum_name:
                for variant in decl.variants:
                    if variant.name == variant_name:
                        return variant
        return None

    def ice(self, message: str, node: object | None = None) -> NoReturn:
        """Raise an internal compiler error with context.

        Args:
            message: Descriptive error message.
            node: Optional AST node to provide source location information.

        Raises:
            InternalCompilerError: Always raised with provided context.
        """
        filename = None
        if self.current_module and self.analysis.cu:
            mod = self.analysis.cu.modules.get(self.current_module)
            if mod:
                filename = mod.filename
        span = getattr(node, "span", None) if node else None
        raise InternalCompilerError(message, ICELocation(filename=filename, span=span))

    def emit_line_directive(self, node: Node, current_module: str) -> None:
        """Emit #line directive for debugging generated C.

        Args:
            node: AST node with span information.
            current_module: Name of the current module.
        """
        if not self.analysis.context.emit_line_directives:
            self._active_line_directive = None
            return
        if node is None or node.span is None:
            self._active_line_directive = None
            return
        filename = None
        if current_module and self.analysis.cu:
            mod = self.analysis.cu.modules.get(current_module)
            if mod:
                filename = mod.filename or f"{current_module}.l0"
        if filename:
            escaped_filename = encode_c_string_bytes(str(filename).replace("\\", "/").encode("utf-8"))
            self._active_line_directive = f'#line {node.span.start_line} "{escaped_filename}"'
            self.out.emit(self._active_line_directive)
        else:
            self._active_line_directive = None

    def restore_active_line_directive(self) -> None:
        """Re-emit the current source line directive after generated helper lines."""
        if self._active_line_directive is not None:
            self.out.emit(self._active_line_directive)

    def _get_struct_info(self, struct_type: StructType, *, strict: bool) -> StructInfo | None:
        """Look up resolved metadata for a struct type.

        Args:
            struct_type: Struct type whose metadata is needed.
            strict: Whether a missing entry should raise an internal compiler error.

        Returns:
            The matching ``StructInfo`` when available, otherwise ``None``.

        See Also:
            `emit_struct_cleanup`: Requires strict struct metadata during emission.
        """
        info = self.analysis.struct_infos.get((struct_type.module, struct_type.name))
        if info is None and strict:
            self.ice(f"[ICE-1270] missing StructInfo for {struct_type.module}.{struct_type.name}", None)
        return info

    def _get_enum_info(self, enum_type: EnumType, *, strict: bool) -> EnumInfo | None:
        """Look up resolved metadata for an enum type.

        Args:
            enum_type: Enum type whose metadata is needed.
            strict: Whether a missing entry should raise an internal compiler error.

        Returns:
            The matching ``EnumInfo`` when available, otherwise ``None``.

        See Also:
            `_emit_enum_cleanup_switch`: Uses enum metadata to enumerate payload fields.
        """
        info = self.analysis.enum_infos.get((enum_type.module, enum_type.name))
        if info is None and strict:
            self.ice(f"[ICE-1080] missing EnumInfo for {enum_type.module}.{enum_type.name}", None)
        return info
