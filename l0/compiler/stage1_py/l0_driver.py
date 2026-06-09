#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

from pathlib import Path
from typing import Dict, Set, List

from l0_analysis import AnalysisResult
from l0_ast import Module
from l0_compilation import CompilationUnit
from l0_context import CompilationContext
from l0_diagnostics import Diagnostic
from l0_expr_types import ExpressionTypeChecker
from l0_lexer import Lexer
from l0_locals import LocalScopeResolver
from l0_logger import log_info, log_debug, log_stage
from l0_name_resolver import NameResolver
from l0_parser import Parser
from l0_paths import SourceSearchPaths
from l0_signatures import SignatureResolver


class ImportCycleError(Exception):
    """Raised when a cyclic import is detected."""
    pass


class SourceEncodingError(Exception):
    """Raised when a source file cannot be decoded as UTF-8."""

    def __init__(self, path: str | Path, message: str):
        """Initialize a UTF-8 decoding failure.

        Args:
            path: Path to the source file that failed to decode.
            message: Human-readable explanation of the decoding failure.

        See Also:
            `load_source_utf8`: Raises this exception for invalid source encodings.
        """
        self.path = str(path)
        self.message = message
        super().__init__(f"{self.path}: {self.message}")


def load_source_utf8(path: str | Path) -> str:
    """Read source bytes and decode as UTF-8.

    UTF-8 BOM is accepted and silently stripped.

    Args:
        path: Path to the source file to read.

    Returns:
        The decoded text content of the file.

    Raises:
        SourceEncodingError: If the file cannot be decoded as UTF-8.
        OSError: If there is an error reading the file.
    """
    p = Path(path)
    data = p.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise SourceEncodingError(
            p,
            f"invalid UTF-8 encoding at byte offset {e.start}",
        ) from e
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


class L0Driver:
    """Stage-1 driver for the L0 compiler.

    Responsibilities include:
      - Reading source files.
      - Tokenizing (lexing).
      - Parsing.
      - Recursively resolving imports using SourceSearchPaths.

    Entry points:
      - analyze(name): High-level analysis pipeline for an entry module.
      - build_compilation_unit(name): Build a closed set of modules for an entry.
      - load_module(name): Load by dotted module name, recursively loading imports.
      - load_single_file(path): Ad hoc one-off parsing (no import resolution).
    """

    def __init__(
            self,
            search_paths: SourceSearchPaths | None = None,
            context: CompilationContext | None = None,
    ):
        """Initialize the L0 driver.

        Args:
            search_paths: Paths to search for modules. Defaults to an empty set
                of search paths.
            context: Compilation context for configuration and logging. Defaults
                to CompilationContext.default().
        """
        self.search_paths = search_paths or SourceSearchPaths()
        self.context = context or CompilationContext.default()
        self.diagnostics: List[Diagnostic] = []
        # Modules successfully loaded (by module name).
        self.module_cache: Dict[str, Module] = {}
        # Modules currently being loaded (for cycle detection).
        self._loading: Set[str] = set()

    # --- Public API ---

    def analyze(self, entry_module_name: str) -> AnalysisResult:
        """Execute the high-level front-end pipeline.

        The pipeline consists of the following stages:
          1. Build CompilationUnit for entry_module_name.
          2. Run NameResolver (module-level symbols).
          3. Run SignatureResolver (top-level types).
          4. Run LocalScopeResolver (function/block scopes).
          5. Run ExpressionTypeChecker (expression types).

        Args:
            entry_module_name: The name of the module to use as the entry point.

        Returns:
            An AnalysisResult containing the compilation unit, environment
            information, and all collected diagnostics.
        """
        log_info(self.context, f"Starting analysis for entry module '{entry_module_name}'")
        result = AnalysisResult(cu=None, context=self.context)

        # 1. Build compilation unit (driver-level; can raise)
        log_stage(self.context, "Building compilation unit", entry_module_name)
        try:
            cu = self.build_compilation_unit(entry_module_name)
        except (FileNotFoundError, ValueError, ImportCycleError, SourceEncodingError) as e:
            # Transfer all collected lexer/parser diagnostics
            result.diagnostics.extend(self.diagnostics)
            # If no specific diagnostic was collected but we have an exception, add it
            if not result.diagnostics:
                if isinstance(e, FileNotFoundError):
                    result.diagnostics.append(Diagnostic(kind="error", message=f"file: [DRV-0010] {str(e)}"))
                elif isinstance(e, ValueError):
                    result.diagnostics.append(Diagnostic(kind="error", message=f"input: [DRV-0020] {str(e)}"))
                elif isinstance(e, ImportCycleError):
                    result.diagnostics.append(Diagnostic(kind="error", message=f"import: [DRV-0030] {str(e)}"))
                elif isinstance(e, SourceEncodingError):
                    result.diagnostics.append(Diagnostic(kind="error", message=f"input: [DRV-0040] {e}"))
            return result

        result.cu = cu
        result.diagnostics.extend(self.diagnostics)

        if result.has_errors():
            return result

        log_debug(self.context,
                  f"Compilation unit contains {len(cu.modules)} module(s): {', '.join(sorted(cu.modules.keys()))}")

        # 2. Module-level name resolution
        log_stage(self.context, "Resolving module-level names")
        nr = NameResolver(cu)
        module_envs = nr.resolve()
        result.module_envs = module_envs
        result.diagnostics.extend(nr.diagnostics)
        log_debug(self.context, f"Name resolution produced {len(nr.diagnostics)} diagnostic(s)")

        # 3. Signature resolution (top-level type information)
        log_stage(self.context, "Resolving type signatures")
        sr = SignatureResolver(cu, module_envs)
        sr.resolve()
        result.diagnostics.extend(sr.diagnostics)
        result.func_types = sr.func_types
        result.struct_infos = sr.struct_infos
        result.enum_infos = sr.enum_infos
        result.let_types = sr.let_types
        log_debug(self.context,
                  f"Signature resolution found {len(sr.func_types)} function(s), {len(sr.struct_infos)} struct(s), {len(sr.enum_infos)} enum(s), {len(sr.let_types)} let(s)")

        # 4. Local scopes (function/block scopes)
        log_stage(self.context, "Resolving local scopes")
        ls = LocalScopeResolver(cu.modules)
        func_envs = ls.resolve()
        result.func_envs = func_envs
        log_debug(self.context, f"Local scope resolution processed {len(func_envs)} function(s)")
        # LocalScopeResolver currently has no diagnostics; add later if needed.

        # 5. Expression types
        log_stage(self.context, "Type-checking expressions")
        etc = ExpressionTypeChecker(result)
        etc.check()
        log_debug(self.context, f"Expression type checking produced {len(etc.diagnostics)} diagnostic(s)")

        log_info(self.context,
                 f"Analysis complete: {len(result.diagnostics)} total diagnostic(s), {len([d for d in result.diagnostics if d.kind == 'error'])} error(s)")
        return result

    def build_compilation_unit(self, entry_module_name: str) -> CompilationUnit:
        """Build a compilation unit for an entry module.

        Loads the entry module and recursively walks its imports to build the
        transitive closure of all required modules.

        Args:
            entry_module_name: The name of the entry module.

        Returns:
            A CompilationUnit containing the entry module and all reachable
            modules.
        """
        entry = self.load_module(entry_module_name)

        visited: Set[str] = set()
        collected: Dict[str, Module] = {}

        def visit(mod: Module) -> None:
            if mod.name in visited:
                return
            visited.add(mod.name)
            collected[mod.name] = mod
            for imp in mod.imports:
                dep = self.load_module(imp.name)
                visit(dep)

        visit(entry)
        return CompilationUnit(entry_module=entry, modules=collected)

    def load_module(self, module_name: str) -> Module:
        """Load a module by its qualified name.

        Uses search paths to resolve the module name to a file, loads and parses
        it, and recursively loads all imported modules. Results are cached.

        Args:
            module_name: The qualified (dotted) name of the module.

        Returns:
            The loaded and parsed Module object.

        Raises:
            ImportCycleError: If a cyclic import is detected.
            FileNotFoundError: If the module source file cannot be found.
            ValueError: If the module name declared in the file mismatch.
            SourceEncodingError: If the source file is not valid UTF-8.
        """
        # IMPORTANT: check for cycles *before* checking the cache.
        if module_name in self._loading:
            raise ImportCycleError(f"Cyclic import detected involving '{module_name}'")

        # If already fully loaded, reuse it.
        if module_name in self.module_cache:
            log_debug(self.context, f"Module '{module_name}' already loaded (cache hit)")
            return self.module_cache[module_name]

        log_debug(self.context, f"Loading module '{module_name}'")
        self._loading.add(module_name)
        try:
            # Resolve module name to a file path.
            path = self.search_paths.resolve(module_name)
            log_debug(self.context, f"Resolved '{module_name}' to {path}")

            module = self._load_single_file(path)

            # Sanity: declared name must match what we are loading.
            if module.name != module_name:
                raise ValueError(
                    f"Module name mismatch: file {path} declares 'module {module.name};' "
                    f"but was loaded as '{module_name}'"
                )

            # Store in cache before resolving imports so that non-cyclic
            # mutual references can reuse it once loading finishes.
            self.module_cache[module_name] = module

            # Recursively load imports.
            for imp in module.imports:
                self.load_module(imp.name)

            return module
        finally:
            self._loading.remove(module_name)

    # --- Internal helpers ---

    def _load_single_file(self, path: str | Path) -> Module:
        """Load a single file as a parsed module.

        Ignores search paths and does not recursively resolve imports.
        The module is cached by its declared name.

        Args:
            path: Path to the source file.

        Returns:
            The parsed Module object.

        Raises:
            FileNotFoundError: If the file does not exist.
            SourceEncodingError: If the file is not valid UTF-8.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"L0 source file not found: {path}")

        text = load_source_utf8(path)
        return self._parse_source(text, file_path=str(path))

    def _parse_source(self, text: str, file_path: str) -> Module:
        """Tokenize and parse source text.

        Args:
            text: The source code text.
            file_path: The path to the file (for diagnostics).

        Returns:
            The parsed Module object.
        """
        log_debug(self.context, f"Lexing {file_path}")
        lex_diag_start = len(self.diagnostics)
        lexer = Lexer(text, filename=file_path, diagnostics=self.diagnostics)
        tokens = lexer.tokenize()
        log_debug(self.context, f"Lexed {len(tokens)} token(s) from {file_path}")
        if any(diag.kind == "error" for diag in self.diagnostics[lex_diag_start:]):
            raise ValueError("lexing failed")

        log_debug(self.context, f"Parsing {file_path}")
        parser = Parser(tokens, diagnostics=self.diagnostics)
        module = parser.parse_module(filename=file_path)
        log_debug(self.context, f"Parsed module '{module.name}' from {file_path}")

        # Ensure any parsed module (even via load_single_file) appears in cache.
        self.module_cache[module.name] = module
        return module
