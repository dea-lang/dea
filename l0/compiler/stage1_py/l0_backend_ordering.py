# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from l0_ast import StructDecl, EnumDecl
from l0_types import Type, BuiltinType, StructType, EnumType, PointerType, NullableType, FuncType
from l0_backend_state import BackendState


@dataclass
class TypeOrdering:
    """Value-type dependency ordering and type-definition emission."""

    state: BackendState

    def _extract_value_type_dependencies(self, typ: Type) -> Set[Tuple[str, str]]:
        """Extract type dependencies for VALUE fields only.

        Value-type fields create dependencies (types must be fully defined).
        Pointer-type fields do NOT create dependencies (forward declarations suffice).

        Examples:
        - StructType("main", "Point") -> {("main", "Point")}
        - EnumType("main", "Status") -> {("main", "Status")}
        - PointerType(StructType("main", "Node")) -> {} (no dependency, forward decl works)
        - NullableType(PointerType(...)) -> {} (pointer-optional, no dependency)
        - NullableType(BuiltinType("int")) -> {} (value-optional of builtin, no dependency)
        - NullableType(StructType("main", "Point")) -> {("main", "Point")} (value-optional of struct)
        - BuiltinType("int") -> {} (no dependency)

        Args:
            typ: The type to extract dependencies from.

        Returns:
            Set of (module, name) tuples for types that must be defined first.
        """
        if isinstance(typ, PointerType):
            # Pointers don't create dependencies - forward declarations handle them
            return set()

        elif isinstance(typ, NullableType):
            # Nullable pointer (T*?) - no dependency
            if isinstance(typ.inner, PointerType):
                return set()
            # Value-optional of user type (T?) - depends on T
            return self._extract_value_type_dependencies(typ.inner)

        elif isinstance(typ, StructType):
            return {(typ.module, typ.name)}

        elif isinstance(typ, EnumType):
            return {(typ.module, typ.name)}

        elif isinstance(typ, BuiltinType):
            return set()

        elif isinstance(typ, FuncType):
            return set()

        else:
            # Unknown type - conservatively return no dependencies
            return set()

    def _build_type_dependency_graph(self) -> Dict[Tuple[str, str], Set[Tuple[str, str]]]:
        """Build dependency graph for type definitions.

        A type X depends on type Y if X has a VALUE field of type Y.
        Pointer fields do NOT create dependencies (forward declarations handle them).

        Returns:
            Dict mapping (module, type_name) -> Set of (module, type_name) dependencies.
        """
        graph = {}

        # Process all structs
        for (mod_name, struct_name), struct_info in self.state.analysis.struct_infos.items():
            key = (mod_name, struct_name)
            deps = set()

            for field in struct_info.fields:
                field_deps = self._extract_value_type_dependencies(field.type)
                deps.update(field_deps)

            graph[key] = deps

        # Process all enums
        for (mod_name, enum_name), enum_info in self.state.analysis.enum_infos.items():
            key = (mod_name, enum_name)
            deps = set()

            for variant_info in enum_info.variants.values():
                for field_type in variant_info.field_types:
                    field_deps = self._extract_value_type_dependencies(field_type)
                    deps.update(field_deps)

            graph[key] = deps

        return graph

    def _find_cycle_details(
            self,
            graph: Dict[Tuple[str, str], Set[Tuple[str, str]]],
            unresolved: List[Tuple[str, str]]
    ) -> str:
        """Find and format cycle details for error message.

        Args:
            graph: The type dependency graph.
            unresolved: List of unresolved nodes.

        Returns:
            A string describing the detected cycle details.
        """
        # Simple approach: list unresolved nodes and their dependencies
        details = []
        for node in unresolved[:5]:  # Limit to first 5 for readability
            deps = [f"{m}::{n}" for m, n in graph.get(node, set()) if (m, n) in unresolved]
            node_str = f"{node[0]}::{node[1]}"
            if deps:
                details.append(f"{node_str} -> {', '.join(deps)}")
            else:
                details.append(node_str)

        return "; ".join(details)

    def _topological_sort(
            self,
            graph: Dict[Tuple[str, str], Set[Tuple[str, str]]]
    ) -> List[Tuple[str, str]]:
        """Perform topological sort on type dependency graph using Kahn's algorithm.

        Args:
            graph: The type dependency graph.

        Returns:
            List of (module, type_name) in dependency order (dependencies first).

        Raises:
            InternalCompilerError: On cycles (value-type cycles are impossible in valid L0).
        """
        from collections import deque

        # Calculate in-degree for each node (number of dependencies)
        # Nodes with in-degree 0 have no dependencies and can be emitted first
        in_degree = {node: len(graph[node]) for node in graph}

        # Start with nodes that have no dependencies
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree of dependents
            for dependent in graph:
                if node in graph[dependent]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Check for cycles
        if len(result) != len(graph):
            # Find nodes involved in cycle for error message
            unresolved = [node for node in graph if node not in result]
            cycle_details = self._find_cycle_details(graph, unresolved)
            self.state.ice(
                f"[ICE-1340] Value-type cycle detected in type definitions: {cycle_details}. "
                f"This indicates either a compiler bug or an invalid type checker state."
            )

        return result

    def _find_struct_decl(self, module_name: str, struct_name: str) -> Optional[StructDecl]:
        """Find the StructDecl AST node for a given struct.

        Args:
            module_name: Name of the module.
            struct_name: Name of the struct.

        Returns:
            The StructDecl if found, otherwise None.
        """
        module = self.state.analysis.cu.modules.get(module_name)
        if not module:
            return None

        for decl in module.decls:
            if isinstance(decl, StructDecl) and decl.name == struct_name:
                return decl

        return None

    def _find_enum_decl(self, module_name: str, enum_name: str) -> Optional[EnumDecl]:
        """Find the EnumDecl AST node for a given enum.

        Args:
            module_name: Name of the module.
            enum_name: Name of the enum.

        Returns:
            The EnumDecl if found, otherwise None.
        """
        module = self.state.analysis.cu.modules.get(module_name)
        if not module:
            return None

        for decl in module.decls:
            if isinstance(decl, EnumDecl) and decl.name == enum_name:
                return decl

        return None

    def _emit_type_definitions(self) -> None:
        """Order value types and emit each definition with its optional wrapper."""
        # Emit type definitions in dependency order
        # Build dependency graph and topologically sort to handle both:
        # - structs that contain enum values (need enum defined first)
        # - enums that contain struct values (need struct defined first)
        self.state.emitter.declarations.emit_section_comment("Type definitions (dependency-ordered)")
        dep_graph = self._build_type_dependency_graph()
        sorted_types = self._topological_sort(dep_graph)

        # Emit types in dependency order
        for module_name, type_name in sorted_types:
            if (module_name, type_name) in self.state.analysis.struct_infos:
                struct_decl = self._find_struct_decl(module_name, type_name)
                struct_info = self.state.analysis.struct_infos[(module_name, type_name)]
                if struct_decl:
                    self.state.current_module = module_name
                    self.state.emitter.state.current_module = module_name
                    self.state.emitter.declarations.emit_struct(module_name, struct_decl, struct_info)
                    self.state.emitter.types.emit_optional_wrapper_for_defined_type(StructType(module_name, type_name))
            elif (module_name, type_name) in self.state.analysis.enum_infos:
                enum_decl = self._find_enum_decl(module_name, type_name)
                enum_info = self.state.analysis.enum_infos[(module_name, type_name)]
                if enum_decl:
                    self.state.current_module = module_name
                    self.state.emitter.state.current_module = module_name
                    self.state.emitter.declarations.emit_enum(module_name, enum_decl, enum_info)
                    self.state.emitter.types.emit_optional_wrapper_for_defined_type(EnumType(module_name, type_name))
