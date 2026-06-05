#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Module-level name resolution for the L0 compiler.

This module provides the NameResolver class which builds module environments,
collects top-level symbols, and handles import semantics.
"""

from typing import Dict

from l0_ast import Node, StructDecl, EnumVariant, EnumDecl, TypeAliasDecl, LetDecl
from l0_compilation import CompilationUnit
from l0_diagnostics import Diagnostic, diag_from_node
from l0_parser import FuncDecl
from l0_symbols import SymbolKind, Symbol, ModuleEnv


class NameResolver:
    """Stage-1 name resolver for module-level symbols.

    This resolver:
    - Builds a ModuleEnv for each module in a CompilationUnit.
    - Collects top-level symbols (functions, structs, enums, variants, aliases).
    - Processes imports by injecting imported symbols into the importer's scope.
    - Detects duplicate definitions and import conflicts.

    Attributes:
        cu: The compilation unit to resolve.
        module_envs: Mapping of module names to their built environments.
        diagnostics: List of collected diagnostics.
    """

    def __init__(self, cu: CompilationUnit):
        """Initialize the name resolver.

        Args:
            cu: The compilation unit to process.
        """
        self.cu = cu
        self.module_envs: Dict[str, ModuleEnv] = {}
        self.diagnostics: list[Diagnostic] = []

    def resolve(self) -> Dict[str, ModuleEnv]:
        """Resolve names for all modules in the compilation unit.

        Returns:
            A mapping from module names to their populated ModuleEnv objects.
        """
        # 1. Create envs
        for module in self.cu.modules.values():
            env = ModuleEnv(module=module)
            self.module_envs[module.name] = env

        # 2. Collect local symbols for each module
        for env in self.module_envs.values():
            self._collect_locals(env)

        # 3. Open imports
        for env in self.module_envs.values():
            self._open_imports(env)

        # 4. Aggregate diagnostics
        for env in self.module_envs.values():
            self.diagnostics.extend(env.diagnostics)

        return self.module_envs

    # --- internal helpers ---

    def _collect_locals(self, env: ModuleEnv) -> None:
        """Collect local symbols from module declarations.

        Args:
            env: The module environment to populate.
        """
        m = env.module

        for decl in m.decls:
            # FuncDecl (includes extern funcs via is_extern flag)
            if isinstance(decl, FuncDecl):
                self._define_local(
                    env,
                    decl.name,
                    Symbol(decl.name, SymbolKind.FUNC, m, decl),
                )
            # Structs
            elif isinstance(decl, StructDecl):
                self._define_local(
                    env,
                    decl.name,
                    Symbol(decl.name, SymbolKind.STRUCT, m, decl),
                )
            # Enums and their variants
            elif isinstance(decl, EnumDecl):
                # Enum type name
                self._define_local(
                    env,
                    decl.name,
                    Symbol(decl.name, SymbolKind.ENUM, m, decl),
                )
                # Variants
                for variant in decl.variants:
                    assert isinstance(variant, EnumVariant)
                    self._define_local(
                        env,
                        variant.name,
                        Symbol(variant.name, SymbolKind.ENUM_VARIANT, m, variant),
                    )
            # Type aliases
            elif isinstance(decl, TypeAliasDecl):
                self._define_local(
                    env,
                    decl.name,
                    Symbol(decl.name, SymbolKind.TYPE_ALIAS, m, decl),
                )
            # Top-level let bindings
            elif isinstance(decl, LetDecl):
                self._define_local(
                    env,
                    decl.name,
                    Symbol(decl.name, SymbolKind.LET, m, decl),
                )
            else:
                # In case of future new TopLevelDecl kinds
                continue

    def _define_local(self, env: ModuleEnv, name: str, sym: Symbol) -> None:
        """Define a local symbol, checking for duplicates.

        Args:
            env: The environment to define the symbol in.
            name: The name of the symbol.
            sym: The Symbol object.
        """
        if name in env.locals:
            env.diagnostics.append(
                diag_from_node(
                    kind="error",
                    message=f"[RES-0010] duplicate top-level definition of '{name}' in module '{env.name}'",
                    module_name=env.name,
                    filename=env.module.filename,
                    node=(sym.node if isinstance(sym.node, Node) else None),
                )
            )
            # Keep the previously defined local symbol
            return

        env.locals[name] = sym
        env.all[name] = sym

    def _open_imports(self, env: ModuleEnv) -> None:
        """Process imports for a module environment.

        Args:
            env: The module environment whose imports should be opened.

        Note:
            Apply the following rules when opening imports:

            - For each imported module, add its locals into `env.imported` and `env.all`.
            - If a name collides with a local, keep the local and issue a warning.
            - If a name is imported from multiple modules, mark it ambiguous, remove
              it from `env.all` and issue a warning; later resolution will see no binding.
        """
        m = env.module

        opened_modules: set[str] = set()

        for imp in m.imports:
            imported_mod_name = imp.name

            # A second `import X;` for an already-opened module is redundant.
            # Warn once and skip re-opening so the symbols are not re-merged.
            if imported_mod_name in opened_modules:
                env.diagnostics.append(
                    diag_from_node(
                        kind="warning",
                        message=f"[RES-0036] duplicated 'import {imported_mod_name}'",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=imp,
                    )
                )
                continue
            opened_modules.add(imported_mod_name)

            imported_env = self.module_envs.get(imported_mod_name)
            if imported_env is None:
                # Defensive check: the driver should have already loaded all modules
                env.diagnostics.append(
                    diag_from_node(
                        kind="error",
                        message=f"[RES-0029] unknown imported module '{imported_mod_name}' in module '{env.name}'",
                        module_name=env.name,
                        filename=env.module.filename,
                        node=imp
                    )
                )
                continue

            for name, sym in imported_env.locals.items():
                # Local definition wins
                if name in env.locals:
                    local_sym = env.locals[name]

                    # Special-case: extern function prototypes
                    if self._extern_signatures_compatible(local_sym, sym):
                        env.diagnostics.append(
                            diag_from_node(
                                kind="warning",
                                message=(
                                    f"[RES-0020] imported extern function '{imported_mod_name}::{name}' "
                                    f"will be shadowed by a compatible local extern declaration in module '{env.name}'"
                                ),
                                module_name=env.name,
                                filename=env.module.filename,
                                node=(local_sym.node if isinstance(local_sym.node, Node) else None),
                            )
                        )
                        # Keep local; do not import this symbol
                        continue

                    # Fallback: report shadowing
                    env.diagnostics.append(
                        diag_from_node(
                            kind="warning",
                            message=(
                                f"[RES-0021] imported symbol '{imported_mod_name}::{name}' will be shadowed "
                                f"by a local definition in module '{env.name}'"
                            ),
                            module_name=env.name,
                            filename=env.module.filename,
                            node=(local_sym.node if isinstance(local_sym.node, Node) else None),
                        )
                    )
                    # Keep local; do not overwrite
                    continue

                # Name already imported from another module -> ambiguous, will need disambiguation later
                if name in env.imported and env.imported[name] is not sym:
                    prev_module = env.imported[name].module.name
                    env.diagnostics.append(
                        diag_from_node(
                            kind="warning",
                            message=(
                                f"[RES-0022] symbol '{name}' imported from multiple modules "
                                f"('{prev_module}', '{imported_mod_name}') into '{env.name}'; "
                                f"unqualified '{name}' will be ambiguous unless a local definition shadows it; "
                                f"otherwise qualify as '<module>::{name}'"
                            ),

                            module_name=env.name,
                            filename=env.module.filename,
                            node=imp,
                        )
                    )
                    # Remove from visible set; name becomes unusable
                    if name in env.all and env.all[name] is env.imported[name]:
                        del env.all[name]
                    # Track ambiguous names for better diagnostics later
                    if name not in env.ambiguous_imports:
                        env.ambiguous_imports[name] = [prev_module, imported_mod_name]
                    else:
                        env.ambiguous_imports[name].append(imported_mod_name)
                    # Keep the first imported symbol in env.imported as bookkeeping,
                    # but resolution will consult env.all only.
                    continue

                # Fresh imported name
                env.imported[name] = sym
                # Only add to env.all if not already present (locals already handled)
                if name not in env.all:
                    env.all[name] = sym

    def _extern_signatures_compatible(self, local: Symbol, imported: Symbol) -> bool:
        """Check if two extern function signatures are compatible."""
        if local.kind is not SymbolKind.FUNC or imported.kind is not SymbolKind.FUNC:
            return False

        if not isinstance(local.node, FuncDecl) or not isinstance(imported.node, FuncDecl):
            return False

        a = local.node
        b = imported.node

        # Both must be extern
        if not (a.is_extern and b.is_extern):
            return False

        # Same number of parameters
        if len(a.params) != len(b.params):
            return False

        # Same parameter types (syntactic TypeRef equality is fine at this stage)
        for pa, pb in zip(a.params, b.params):
            if pa.type != pb.type:
                return False

        # Same return type
        if a.return_type != b.return_type:
            return False

        return True
