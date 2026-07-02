#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from re import fullmatch, search
from typing import Dict, List, Optional, Sequence, Tuple

from l0_analysis import AnalysisResult
from l0_ast_printer import format_module
from l0_backend import Backend
from l0_compilation import CompilationUnit
from l0_context import CompilationContext
from l0_diagnostics import Diagnostic
from l0_driver import L0Driver, SourceEncodingError, load_source_utf8
from l0_internal_error import InternalCompilerError
from l0_lexer import TokenKind, Lexer
from l0_logger import log_info, log_error, log_warning
from l0_paths import SourceSearchPaths
from l0_symbols import SymbolKind
from l0_types import (
    format_type,
)


### L0 Compiler (l0c) - Stage 1: Analysis and C Code Generation
### This is the main entry point for the L0 compiler's stage 1, which includes:
### - Command-line interface parsing
### - Environment variable handling for defaults
### - Building the compilation context and search paths


def compiler_identity_text() -> str:
    """Return the user-facing compiler identity/version text."""
    return "Dea language / L0 compiler (Stage 1)"


def _count_cli_verbosity(argv: Sequence[str]) -> int:
    """Count verbosity flags in compiler CLI args before `--`."""
    cli_argv, _ = _split_cli_and_program_args(argv)
    count = 0
    for token in cli_argv:
        if token == "--verbose":
            count += 1
            continue
        if len(token) >= 2 and token.startswith("-") and set(token[1:]) == {"v"}:
            count += len(token) - 1
    return count


def _has_cli_log_flag(argv: Sequence[str]) -> bool:
    """Report whether compiler CLI args enable rich logging before `--`."""
    cli_argv, _ = _split_cli_and_program_args(argv)
    return any(token in {"-l", "--log"} for token in cli_argv)


def _emit_verbose_compiler_identity(args: argparse.Namespace) -> None:
    """Emit the compiler identity through the normal verbose logging path."""
    if getattr(args, "verbosity", 0) < 1:
        return
    log_info(build_compilation_context(args), compiler_identity_text())


def _init_env_defaults() -> None:
    """Initialize default environment variables based on L0_HOME."""
    l0_home = os.getenv("L0_HOME")
    if not l0_home:
        return
    if not os.getenv("L0_SYSTEM"):
        os.environ["L0_SYSTEM"] = os.path.join(l0_home, "shared", "l0", "stdlib")
    if not os.getenv("L0_RUNTIME_INCLUDE"):
        os.environ["L0_RUNTIME_INCLUDE"] = os.path.join(l0_home, "shared", "runtime")


def _load_file_lines(path: str, cache: Dict[str, List[str]]) -> List[str]:
    """Load lines of a source file, using a cache to avoid redundant reads.

    Args:
        path: Path to the source file.
        cache: Cache of file lines keyed by path.

    Returns:
        A list of strings representing the lines of the file.
    """
    if path not in cache:
        text = load_source_utf8(path)
        cache[path] = text.splitlines()
    return cache[path]


def print_diagnostics(result: AnalysisResult, context: CompilationContext) -> None:
    """Print diagnostics from the analysis result.

    Args:
        result: The analysis result containing diagnostics.
        context: The compilation context for logging and formatting.
    """
    print_diagnostic_list(result.diagnostics, context)


def print_diagnostic_list(diagnostics: List[Diagnostic], context: CompilationContext) -> None:
    """Print a list of diagnostics, using a file cache for source snippets.

    Args:
        diagnostics: List of diagnostics to print.
        context: The compilation context for logging and formatting.
    """
    file_cache: Dict[str, List[str]] = {}

    for diag in diagnostics:
        print_diagnostic_with_snippet(diag, file_cache, context)


def print_diagnostic_with_snippet(diag: Diagnostic, file_cache: Dict[str, List[str]],
                                  context: CompilationContext = None) -> None:
    """Print a single diagnostic, including the source line and a caret.

    Args:
        diag: The diagnostic to print.
        file_cache: Cache of file lines keyed by path.
        context: Optional compilation context for logging. Defaults to None.
    """
    # First line: header
    log_error(context, diag.format())

    if not diag.filename or diag.line is None:
        return

    try:
        lines = _load_file_lines(diag.filename, file_cache)
    except (OSError, SourceEncodingError):
        # Can't read file; fall back to header only
        return

    line_idx = diag.line - 1
    if not (0 <= line_idx < len(lines)):
        return

    src_line = lines[line_idx]

    # Pretty "N | ..." formatting (calculate width so multi-digit line numbers align)
    width = max(5, len(str(diag.line)))
    gutter = f"{diag.line:>{width}} | "

    log_error(context, gutter + src_line)

    if diag.column is None:
        return

    # Determine caret span (simple case: same line)
    start_col = max(1, diag.column)
    if diag.end_line is None or diag.end_column is None:
        end_col = start_col
    else:
        if diag.end_line == diag.line:
            end_col = max(start_col, diag.end_column)
        else:
            end_col = len(src_line) + 1

    caret_width = max(1, end_col - start_col)
    # Spaces: same gutter, then (start_col-1) spaces before carets
    caret_prefix = " " * width + " | " + " " * (start_col - 1)
    carets = "^" * caret_width
    log_error(context, caret_prefix + carets)


def _is_valid_module_name(module_name: str) -> bool:
    """Check if a module name is valid (dot-separated identifiers).

    Args:
        module_name: The module name to validate.

    Returns:
        True if the module name is valid, False otherwise.
    """
    if not module_name:
        return False
    parts = module_name.split(".")
    if any(not part for part in parts):
        return False
    return all(fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts)


def build_search_paths(context: CompilationContext, args: argparse.Namespace) -> Optional[SourceSearchPaths]:
    """Build source search paths from command-line arguments.

    Handles entry path parsing and default values from environment variables.

    Args:
        context: The compilation context for logging.
        args: Parsed command-line arguments.

    Returns:
        A SourceSearchPaths object if successful, or None if the entry name
        is invalid.
    """
    # if args.entry is a path, split into dir and module name
    entry_path = Path(args.entry)
    if entry_path.suffix == ".l0" or entry_path.is_absolute() or entry_path.parent != Path('.'):
        if entry_path.suffix == ".l0":
            module_name = entry_path.stem
        else:
            module_name = entry_path.name
        if entry_path.parent != Path('.'):
            args.project_root.append(str(entry_path.parent))
        args.entry = module_name
    if not _is_valid_module_name(args.entry):
        log_error(
            context,
            f"error: [L0C-0011] invalid entry module name '{args.entry}': module components must be valid identifiers",
        )
        return None
    if not args.project_root:
        args.project_root = ["."]
    if not args.sys_root:
        # Default system root from environment variable L0_SYSTEM if set
        # Supports multiple paths separated by : (Unix) or ; (Windows)
        sys_env = os.getenv("L0_SYSTEM")
        if sys_env:
            separator = ';' if os.name == 'nt' else ':'
            args.sys_root = [p for p in sys_env.split(separator) if p]
        else:
            args.sys_root = []
    sp = SourceSearchPaths()
    for root in args.sys_root:
        sp.add_system_root(root)
    for root in args.project_root:
        sp.add_project_root(root)
    sys_list = ",".join(f"'{p}'" for p in sp.system_roots)
    proj_list = ",".join(f"'{p}'" for p in sp.project_roots)
    log_info(context, f"System root(s): {sys_list or '<none>'}")
    log_info(context, f"Project root(s): {proj_list or '<none>'}")
    return sp


def build_compilation_context(args: argparse.Namespace) -> CompilationContext:
    """Build a CompilationContext from command-line arguments.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A new CompilationContext configured based on arguments.
    """
    from l0_context import LogLevel

    # Log format
    log_rich_format = getattr(args, 'log', False)

    # Convert verbosity count to LogLevel
    verbosity = getattr(args, 'verbosity', 0)
    if verbosity >= 3:
        log_level = LogLevel.DEBUG
    elif verbosity >= 1:
        log_level = LogLevel.INFO
    else:
        log_level = LogLevel.ERROR

    return CompilationContext(
        emit_line_directives=not getattr(args, 'no_line_directives', False),
        trace_arc=getattr(args, 'trace_arc', False),
        trace_memory=getattr(args, 'trace_memory', False),
        log_rich_format=log_rich_format,
        log_level=log_level,
    )


def _run_analysis(args: argparse.Namespace):
    """Run the analysis pipeline.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A tuple of (AnalysisResult, CompilationContext, int) where the integer
        is the suggested exit code.
    """
    context = build_compilation_context(args)
    search_paths = build_search_paths(context, args)
    if search_paths is None:
        return AnalysisResult(cu=None, context=context), context, 1
    driver = L0Driver(search_paths=search_paths, context=context)
    result = driver.analyze(args.entry)
    print_diagnostics(result, context=context)
    exit_code = 1 if (result.cu is None or result.has_errors()) else 0
    return result, context, exit_code


def _get_module_names(args: argparse.Namespace, cu: CompilationUnit) -> List[str]:
    """Get the list of module names based on the `--all-modules` flag.

    Args:
        args: Parsed command-line arguments.
        cu: The compilation unit.

    Returns:
        A list of module names to process.
    """
    if getattr(args, 'all_modules', False):
        return sorted(cu.modules.keys())
    return [args.entry]


def _find_cc() -> Optional[str]:
    """Find the best available C compiler.

    Used in codegen and build stages if the user didn't specify one explicitly.

        The search order is:

        1. L0_CC environment variable.
        2. Common compiler names in PATH: tcc, gcc, clang, cc (in that order).
        3. CC environment variable.

    Returns:
        The compiler command if found, or None if no compiler is found.
    """
    from_env = os.environ.get("L0_CC")
    if from_env:
        return from_env
    for candidate in ("tcc", "gcc", "clang", "cc"):
        if shutil.which(candidate):
            return candidate
    from_env = os.environ.get("CC")
    if from_env:
        return from_env
    return None


def _compiler_flag_family(compiler: str):
    """Determine the compiler family for flag selection using a simple heuristic.

    Uses pattern matching to handle cases like "gcc-10" or "clang-14" on Unix
    and "gcc.exe" or "clang.exe" on Windows.

    Args:
        compiler: The compiler command string.

    Returns:
        A string representing the compiler family ("tcc", "gcc", "cc", "msvc",
        or "unknown").
    """
    if compiler.endswith("tcc") or search(r"tcc(\.exe)?$", compiler):
        return "tcc"
    elif compiler.endswith(("gcc", "clang")) or search(r"(gcc|clang)(\.exe)?(-\d+)?$", compiler):
        # clang supports most gcc flags and is often aliased to gcc, so treat them as the same family.
        return "gcc"
    elif compiler.endswith("cc") or search(r"cc(\.exe)?$", compiler):
        return "cc"
    elif compiler.endswith("cl") or search(r"cl(\.exe)?$", compiler):
        return "msvc"
    else:
        return "unknown"


def _is_windows_host() -> bool:
    """Return whether the current Python host is Windows."""
    return os.name == "nt"


def _default_executable_name() -> str:
    """Return the default build output name for the current platform."""
    return "a.exe" if _is_windows_host() else "a.out"


def _runtime_include_flags(flag_family: str, runtime_include: str) -> list[str]:
    """Return compiler-family-specific runtime include flags."""
    if flag_family == "msvc":
        return [f"/I{runtime_include}"]
    return ["-I", runtime_include]


def _runtime_library_flags(flag_family: str, runtime_lib: str) -> list[str]:
    """Return compiler-family-specific runtime library search-path flags."""
    if flag_family == "msvc":
        return ["/link", f"/LIBPATH:{runtime_lib}"]
    return ["-L", runtime_lib]


def _output_flags(flag_family: str, exe_path: Path) -> list[str]:
    """Return compiler-family-specific output flags."""
    if flag_family == "msvc":
        return [f"/Fe:{exe_path}"]
    return ["-o", str(exe_path)]


def _check_entry_main_for_build(result: AnalysisResult, entry_name: str, context: CompilationContext) -> bool:
    """Check that the entry module defines a valid 'main' function for build/run.

    Args:
        result: The analysis result.
        entry_name: The name of the entry module.
        context: The compilation context for logging.

    Returns:
        True if a valid 'main' function is found, False otherwise.
    """
    entry_env = result.module_envs.get(entry_name)
    if entry_env is None:
        log_error(context, f"error: [L0C-0012] entry module '{entry_name}' not found in analysis result")
        return False

    main_symbol = entry_env.locals.get("main")
    if main_symbol is None or main_symbol.kind != SymbolKind.FUNC:
        log_error(
            context,
            f"error: [L0C-0012] entry module '{entry_name}' must define a 'main' function for build/run",
        )
        return False

    main_type = result.func_types.get((entry_name, "main"))
    if main_type is None:
        log_error(
            context,
            f"error: [L0C-0016] missing type information for entry function '{entry_name}::main'",
        )
        return False

    ret_type = format_type(main_type.result)
    if ret_type not in {"void", "int", "bool"}:
        log_error(
            context,
            "warning: [L0C-0013] entry 'main' returns "
            f"'{ret_type}' (preferred: void/int/bool); generated C entry wrapper will ignore the return value",
        )
    return True


def _validate_runtime_library_path(runtime_lib_path: str, context: CompilationContext) -> bool:
    """Validate that the provided runtime library path exists and is a directory.

    Args:
        runtime_lib_path: Path to the runtime library directory.
        context: The compilation context for logging.

    Returns:
        True if the path is a directory, False otherwise.
    """
    runtime_dir = Path(runtime_lib_path)
    if not runtime_dir.is_dir():
        log_error(
            context,
            f"error: [L0C-0014] runtime library path '{runtime_lib_path}' does not exist or is not a directory",
        )
        return False

    return True


def _split_c_options(raw_options: Optional[str]) -> List[str]:
    """Split a raw C options string into individual compiler arguments.

    Args:
        raw_options: Raw options string, or None.

    Returns:
        A list of whitespace-delimited compiler option tokens.
    """
    if not raw_options:
        return []
    return raw_options.split()


def _get_optimize_flag(flag_family: str, extra_opts: List[str]) -> Optional[str]:
    """Determine the appropriate optimization flag for the compiler family.

    Args:
        flag_family: The detected compiler family string.
        extra_opts: List of extra C compiler options.

    Returns:
        The optimization flag string (e.g., '-O1') or None if no suitable flag
        is found or if the user provided explicit optimization flags.
    """
    # if any opt starts with -O or /O, assume user is explicitly controlling optimization and do not add a default optimize flag
    if extra_opts and any(opt.startswith("-O") or opt.startswith("/O") for opt in extra_opts):
        return None

    # if debug options are present, use the minimal optimization level that still allows debugging (e.g. -Og for gcc/clang, -O0 for tcc)
    if extra_opts and any(opt in extra_opts for opt in ["-g", "/Zi", "/Z7"]):
        if flag_family == "tcc":
            return "-O0"
        elif flag_family == "gcc":
            return "-Og"
        elif flag_family == "msvc":
            return "/Od"

    # MinGW/GCC on Windows has shown optimizer-sensitive miscompiles in some
    # Stage 2 teardown-heavy traces. Keep the automatic default conservative on
    # that host; callers can still opt in explicitly with -O*.
    if _is_windows_host() and flag_family == "gcc":
        return "-O0"

    # Default quick optimization level for non-debug builds (can be overridden with --c-options/-C or L0_CFLAGS)
    if flag_family in {"gcc", "tcc"}:
        return "-O1"
    elif flag_family == "msvc":
        return "/O1"
    else:
        return None


def cmd_build(args: argparse.Namespace) -> int:
    """Build an executable from an L0 module.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    context = build_compilation_context(args)
    search_paths = build_search_paths(context, args)
    if search_paths is None:
        return 1
    driver = L0Driver(search_paths=search_paths, context=context)

    result = driver.analyze(args.entry)
    print_diagnostics(result, context=context)

    if result.cu is None or result.has_errors():
        return 1

    if not _check_entry_main_for_build(result, args.entry, context):
        return 1

    # Generate C code
    backend = Backend(result)
    try:
        c_code = backend.generate()
    except InternalCompilerError as e:
        log_error(context, e.format())
        return 1

    # Determine output executable path
    if args.output:
        exe_path = Path(args.output)
    else:
        exe_path = Path(_default_executable_name())

    # Write C code to temporary or specified file
    if args.keep_c:
        c_output_override = getattr(args, "c_output_path", None)
        if c_output_override:
            c_path = Path(c_output_override)
        else:
            c_path = exe_path.with_suffix(".c")
    else:
        # noinspection PyDeprecation
        c_path = Path(tempfile.mktemp(suffix=".c"))

    try:
        c_path.write_text(c_code)
        log_info(context, f"Generated C code: {c_path}")

        # Determine C compiler
        compiler = args.c_compiler or _find_cc()
        if compiler is None:
            log_error(context,
                      "error: [L0C-0009] no C compiler found: use '--c-compiler' to specify one or set the L0_CC environment variable")
            return 1

        log_info(context, f"Using C compiler: {compiler}")

        flag_family = _compiler_flag_family(compiler)
        log_info(context, f"Detected compiler flag family: {flag_family}")

        # Extra C compiler flags/options from environment + CLI (CLI appended last).
        env_opts = _split_c_options(os.getenv("L0_CFLAGS"))
        cli_opts = _split_c_options(args.c_options)
        if env_opts:
            log_info(context, f"C compiler options from $L0_CFLAGS: {env_opts}")
        if cli_opts:
            log_info(context, f"C compiler options from --c-options: {cli_opts}")
        extra_opts = env_opts + cli_opts
        if extra_opts:
            log_info(context, f"Extra C compiler options: {extra_opts}")

        # Build compiler command. Preprocessor/compiler options must precede the
        # source path for tcc; output and library flags can follow it.
        cmd = [compiler]
        cmd.extend(extra_opts)

        # Add standard flags
        if flag_family == "tcc":
            cmd.extend(["-std=c99", "-Wall", "-pedantic"])
        elif flag_family == "gcc":
            cmd.extend(["-std=c99", "-Wall", "-Wextra", "-Wno-unused", "-Wno-unused-parameter", "-pedantic-errors"])
        elif flag_family == "msvc":
            cmd.extend(["/std:c11", "/W4"])
        else:
            log_warning(context,
                        f"Unsupported compiler '{compiler}' (flag family '{flag_family}'): not adding standard flags")

        # Optimization flags for non-debug builds
        optimize_flag = _get_optimize_flag(flag_family, extra_opts)

        if optimize_flag:
            log_info(context, f"Adding optimization flag: {optimize_flag}")
            cmd.append(optimize_flag)

        # Add runtime include path
        if args.runtime_include:
            cmd.extend(_runtime_include_flags(flag_family, args.runtime_include))
        elif os.getenv("L0_RUNTIME_INCLUDE"):
            cmd.extend(_runtime_include_flags(flag_family, os.getenv("L0_RUNTIME_INCLUDE")))

        cmd.append(str(c_path))
        cmd.extend(_output_flags(flag_family, exe_path))

        # Add runtime library search path
        runtime_lib_path = args.runtime_lib or os.getenv("L0_RUNTIME_LIB")
        if runtime_lib_path:
            if not _validate_runtime_library_path(runtime_lib_path, context):
                return 1

        if args.runtime_lib:
            cmd.extend(_runtime_library_flags(flag_family, args.runtime_lib))
        elif os.getenv("L0_RUNTIME_LIB"):
            cmd.extend(_runtime_library_flags(flag_family, os.getenv("L0_RUNTIME_LIB")))

        log_info(context, f"Compiling:")
        log_info(context, f"{' '.join(cmd)}")

        # Run C compiler
        compile_result = subprocess.run(cmd, capture_output=True, text=True)

        if compile_result.returncode != 0:
            log_error(context, "error: [L0C-0010] C compilation failed:")
            if compile_result.stderr:
                log_error(context, compile_result.stderr)
            if compile_result.stdout:
                log_error(context, compile_result.stdout)
            return 1

        if compile_result.stderr:
            log_error(context, compile_result.stderr)

        log_info(context, f"Built executable: {exe_path}")

        return 0

    finally:
        # Clean up temporary C file if not keeping it
        if not args.keep_c and c_path.exists():
            c_path.unlink()


def cmd_run(args: argparse.Namespace) -> int:
    """Build and run an L0 module.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code from the executed program or the build process.
    """
    context = build_compilation_context(args)
    # Create temporary executable
    temp_exe_suffix = ".exe" if _is_windows_host() else ""
    with tempfile.NamedTemporaryFile(mode='w', suffix=temp_exe_suffix, delete=False) as f:
        temp_exe = f.name

    try:
        # Build to temporary executable
        keep_c = getattr(args, 'keep_c', False)
        output_arg = getattr(args, 'output', None)
        if output_arg and not keep_c:
            log_error(
                context,
                "warning: [L0C-0017] '--output' is ignored in '--run' mode unless '--keep-c' is set; "
                "the executable path remains temporary",
            )
        c_output_path = None
        if keep_c:
            if output_arg:
                c_output_path = str(Path(output_arg).with_suffix(".c"))
            else:
                c_output_path = str(Path(_default_executable_name()).with_suffix(".c"))

        build_args = argparse.Namespace(
            entry=args.entry,
            output=temp_exe,
            c_compiler=args.c_compiler,
            c_options=args.c_options,
            runtime_include=args.runtime_include,
            runtime_lib=args.runtime_lib,
            keep_c=keep_c,
            c_output_path=c_output_path,
            verbosity=getattr(args, 'verbosity', 0),
            project_root=args.project_root,
            sys_root=args.sys_root,
            no_line_directives=args.no_line_directives,
            trace_arc=getattr(args, 'trace_arc', False),
            trace_memory=getattr(args, 'trace_memory', False),
            log=args.log,
        )

        rc = cmd_build(build_args)
        if rc != 0:
            return rc

        # Run the executable with any provided arguments
        log_info(context, f"Running: {temp_exe} {' '.join(args.args)}")

        run_result = subprocess.run([temp_exe] + args.args)
        return run_result.returncode

    # Handle Ctrl-C gracefully
    except KeyboardInterrupt:
        return 130
    finally:
        # Clean up temporary executable.  On Windows the file may still be
        # locked briefly after the child process exits; ignore the error.
        try:
            if Path(temp_exe).exists():
                Path(temp_exe).unlink()
        except OSError:
            pass


def cmd_codegen(args: argparse.Namespace) -> int:
    """Generate C code for a module.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    result, context, exit_code = _run_analysis(args)
    if exit_code != 0:
        return exit_code

    backend = Backend(result)
    try:
        c_code = backend.generate()
    except InternalCompilerError as e:
        log_error(context, e.format())
        return 1

    # Write to output file or stdout
    if args.output:
        Path(args.output).write_text(c_code)
    else:
        sys.stdout.write(c_code)

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run analysis and type checking without code generation.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    _, _, exit_code = _run_analysis(args)
    return exit_code


def cmd_ast(args: argparse.Namespace) -> int:
    """Pretty-print the parsed AST.

    By default, prints only the entry module. With --all-modules, prints
    every module in the compilation unit.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    context = build_compilation_context(args)
    search_paths = build_search_paths(context, args)
    if search_paths is None:
        return 1
    driver = L0Driver(search_paths=search_paths, context=context)

    try:
        cu = driver.build_compilation_unit(args.entry)
    except Exception as e:
        if driver.diagnostics:
            print_diagnostic_list(driver.diagnostics, context)
        else:
            log_error(context, f"error: [L0C-0020] {e}")
        return 1

    if args.all_modules:
        for name in sorted(cu.modules.keys()):
            mod = cu.modules[name]
            print(f"=== Module {name} ===")
            print(format_module(mod))
            print()
    else:
        mod = cu.modules.get(args.entry)
        if mod is None:
            log_error(context, f"error: [L0C-0030] entry module '{args.entry}' not found in compilation unit")
            return 1
        print(format_module(mod))

    return 0


def _format_token_dump_text(tok) -> str:
    """Return token payload text for `--tok` output."""
    if tok.kind is TokenKind.LEXER_ERROR:
        diagnostics = tok.diagnostics if tok.diagnostics is not None else []
        code = "LEX-????"
        if diagnostics:
            code = diagnostics[0].message.split("]", 1)[0].lstrip("[")
        elif tok.diagnostic is not None:
            code = tok.diagnostic.message.split("]", 1)[0].lstrip("[")
        recovery = "none"
        if tok.recovery is not None:
            recovery = f"{tok.recovery.kind.name.lower()}({tok.recovery.text!r})"
        return f"lex-error({code}, recovery={recovery})"
    return repr(tok.text)


def _dump_tokens_for_file(path: Path, include_eof: bool, context: Optional[CompilationContext] = None) -> int:
    """Dump lexer tokens for a single file.

    Args:
        path: Path to the source file.
        include_eof: Whether to include the EOF token in the output.
        context: Optional compilation context for logging. Defaults to None.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    try:
        text = load_source_utf8(path)
    except OSError as e:
        log_error(context, f"error: [L0C-0040] cannot read {path}: {e}")
        return 1
    except SourceEncodingError as e:
        log_error(context, f"error: [L0C-0041] {e}")
        return 1

    lexer = Lexer(text, filename=str(path))
    try:
        tokens = lexer.tokenize()
    except Exception as e:
        if lexer.diagnostics:
            print_diagnostic_list(lexer.diagnostics, context)
        else:
            log_error(context, f"error: [L0C-0042] {e}")
        return 1

    for tok in tokens:
        if not include_eof and tok.kind is TokenKind.EOF:
            continue
        # Format: file:line:col: KIND  'text'
        print(
            f"{path}:{tok.line}:{tok.column}:\t"
            f"{tok.kind.name:<12} {_format_token_dump_text(tok)}"
        )
    return 0


def cmd_tok(args: argparse.Namespace) -> int:
    """Dump lexer tokens.

    By default, dumps tokens for the entry module only. With --all-modules,
    dumps tokens for all modules in the compilation unit.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    context = build_compilation_context(args)
    search_paths = build_search_paths(context, args)
    if search_paths is None:
        return 1
    driver = L0Driver(search_paths=search_paths, context=context)

    if args.all_modules:
        # Use the driver to discover all modules, then lex each file separately.
        try:
            cu = driver.build_compilation_unit(args.entry)
        except Exception as e:
            if driver.diagnostics:
                print_diagnostic_list(driver.diagnostics, context)
            else:
                log_error(context, f"error: [L0C-0050] {e}")
            return 1

        exit_code = 0
        for name in sorted(cu.modules.keys()):
            try:
                path = search_paths.resolve(name)
            except FileNotFoundError as e:
                log_error(context, f"error: [L0C-0060] {e}")
                exit_code = 1
                continue

            print(f"=== Tokens for module {name} ({path}) ===")
            rc = _dump_tokens_for_file(path, include_eof=args.include_eof, context=context)
            if rc != 0:
                exit_code = rc
            print()
        return exit_code
    else:
        # Only the entry module: resolve its path directly.
        try:
            path = search_paths.resolve(args.entry)
        except FileNotFoundError as e:
            log_error(context, f"error: [L0C-0070] {e}")
            return 1

        return _dump_tokens_for_file(path, include_eof=args.include_eof)


def cmd_sym(args: argparse.Namespace) -> int:
    """Dump module-level symbol tables.

    By default, dumps symbols only for the entry module. With --all-modules,
    dumps symbols for all modules in the compilation unit.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    result, _, _ = _run_analysis(args)
    if result.cu is None:
        return 1

    module_names = _get_module_names(args, result.cu)

    for mod_name in module_names:
        env = result.module_envs.get(mod_name)
        if env is None:
            print(f"=== module {mod_name} (no symbol env) ===")
            continue

        print(f"=== module {mod_name} ===")

        # locals
        print("  locals:")
        if env.locals:
            for name in sorted(env.locals.keys()):
                sym = env.locals[name]
                type_str = f": {format_type(sym.type)}" if sym.type is not None else ""
                print(f"    {sym.kind.name:<12} {sym.name}{type_str}")
        else:
            print("    <none>")

        # imported
        print("  imported:")
        if env.imported:
            for name in sorted(env.imported.keys()):
                sym = env.imported[name]
                type_str = f": {format_type(sym.type)}" if sym.type is not None else ""
                print(
                    f"    {sym.kind.name:<12} {sym.name}"
                    f" (from {sym.module.name}){type_str}"
                )
        else:
            print("    <none>")

        # all
        print("  all:")
        if env.all:
            for name in sorted(env.all.keys()):
                sym = env.all[name]
                origin = (
                    "local" if name in env.locals
                    else ("imported" if name in env.imported else "unknown")
                )
                type_str = f": {format_type(sym.type)}" if sym.type is not None else ""
                print(
                    f"    {sym.kind.name:<12} {sym.name}"
                    f" [{origin}]{type_str}"
                )
        else:
            print("    <none>")

        print()

    return 0


def cmd_type(args: argparse.Namespace) -> int:
    """Dump resolved type information.

    Dumps function signatures, struct field types, enum variant payloads,
    and type aliases.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    result, _, _ = _run_analysis(args)
    if result.cu is None:
        return 1

    module_names = _get_module_names(args, result.cu)

    for mod_name in module_names:
        print(f"=== module {mod_name} ===")

        # Functions
        print("  functions:")
        any_funcs = False
        for (m, fname), ftype in sorted(result.func_types.items()):
            if m != mod_name:
                continue
            any_funcs = True
            print(f"    {fname}: {format_type(ftype)}")
        if not any_funcs:
            print("    <none>")

        # Structs
        print("  structs:")
        any_structs = False
        for (m, sname), sinfo in sorted(result.struct_infos.items()):
            if m != mod_name:
                continue
            any_structs = True
            print(f"    {sname}:")
            for field in sinfo.fields:
                print(f"      {field.name}: {format_type(field.type)}")
        if not any_structs:
            print("    <none>")

        # Enums
        print("  enums:")
        any_enums = False
        for (m, ename), einfo in sorted(result.enum_infos.items()):
            if m != mod_name:
                continue
            any_enums = True
            print(f"    {ename}:")
            for vname, vinfo in sorted(einfo.variants.items()):
                if not vinfo.field_types:
                    print(f"      {vname}")
                else:
                    fields_str = ", ".join(
                        format_type(t) for t in vinfo.field_types
                    )
                    print(f"      {vname}({fields_str})")
        if not any_enums:
            print("    <none>")

        # Type aliases (from symbol table)
        env = result.module_envs.get(mod_name)
        print("  type aliases:")
        if env is not None:
            aliases = [
                sym
                for sym in env.locals.values()
                if sym.kind == SymbolKind.TYPE_ALIAS
            ]
            if aliases:
                for sym in sorted(aliases, key=lambda s: s.name):
                    if sym.type is not None:
                        print(f"    {sym.name} = {format_type(sym.type)}")
                    else:
                        print(f"    {sym.name} = <unresolved>")
            else:
                print("    <none>")
        else:
            print("    <no module env>")

        print()

    return 0


def _add_target_args(parser: argparse.ArgumentParser) -> None:
    """Add target module/file arguments to the parser.

    Args:
        parser: The argument parser to update.
    """
    parser.add_argument(
        "targets",
        nargs="+",
        help="Target module/file name(s); currently exactly one target is supported",
    )


def _add_all_modules_arg(parser: argparse.ArgumentParser) -> None:
    """Add the --all-modules flag to the parser.

    Args:
        parser: The argument parser to update.
    """
    parser.add_argument(
        "--all-modules", "-a",
        action="store_true",
        help="Process all modules in the compilation unit (valid in: '--tok', '--ast', '--sym', '--type')",
    )


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    """Add runtime-related arguments to the parser.

    Args:
        parser: The argument parser to update.
    """
    parser.add_argument(
        "--c-compiler", "-c",
        help=(
            "C compiler to use (default: $L0_CC has highest precedence if set;"
            " then tcc, gcc, clang, cc from PATH, or $CC, in that order;"
            " valid in: '--build', '--run')"
        ),
    )
    parser.add_argument(
        "--c-options", "-C",
        help=(
            "Extra options to pass to the C compiler "
            "(default prepends $L0_CFLAGS; options from --c-options are appended after env options; "
            "e.g. -C=\"-Og -DDEBUG\"; valid in: '--build', '--run')"
        ),
    )
    parser.add_argument(
        "--runtime-include", "-I",
        help="Path to L0 runtime headers (default: $L0_RUNTIME_INCLUDE; valid in: '--build', '--run')",
    )
    parser.add_argument(
        "--runtime-lib", "-L",
        help="Path to L0 runtime library search directory (default: $L0_RUNTIME_LIB; valid in: '--build', '--run')",
    )


def _add_codegen_arg(parser: argparse.ArgumentParser) -> None:
    """Add codegen-related arguments to the parser.

    Args:
        parser: The argument parser to update.
    """
    parser.add_argument(
        "--no-line-directives", "-NLD",
        action="store_true",
        help="Disable #line directives in generated C code (valid in: '--build', '--run', '--gen')",
    )
    parser.add_argument(
        "--trace-arc",
        action="store_true",
        help="Enable ARC runtime tracing in generated C code (emits L0_TRACE_ARC; valid in: '--build', '--run', '--gen')",
    )
    parser.add_argument(
        "--trace-memory",
        action="store_true",
        help="Enable memory runtime tracing in generated C code (emits L0_TRACE_MEMORY; valid in: '--build', '--run', '--gen')",
    )


_OPTIONS_REQUIRING_VALUE = {
    "-P", "--project-root",
    "-S", "--sys-root",
    "-c", "--c-compiler",
    "-C", "--c-options",
    "-I", "--runtime-include",
    "-L", "--runtime-lib",
    "-o", "--output",
}


def _split_cli_and_program_args(argv: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Split compiler CLI arguments from program arguments.

    Args:
        argv: The complete list of command-line arguments.

    Returns:
        A tuple of (compiler_args, program_args).
    """
    argv_list = list(argv)
    if "--" not in argv_list:
        return argv_list, []
    idx = argv_list.index("--")
    return argv_list[:idx], argv_list[idx + 1:]


def _validate_mode_scoped_flags(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject flags that were provided for a mode where they are not valid.

    Args:
        parser: The argument parser for reporting errors.
        args: The parsed command-line arguments.
    """
    mode = args.mode

    scoped_flags = [
        ("output", "--output", {"build", "run", "gen"}),
        ("keep_c", "--keep-c", {"build", "run"}),
        ("c_compiler", "--c-compiler", {"build", "run"}),
        ("c_options", "--c-options", {"build", "run"}),
        ("runtime_include", "--runtime-include", {"build", "run"}),
        ("runtime_lib", "--runtime-lib", {"build", "run"}),
        ("no_line_directives", "--no-line-directives", {"build", "run", "gen"}),
        ("trace_arc", "--trace-arc", {"build", "run", "gen"}),
        ("trace_memory", "--trace-memory", {"build", "run", "gen"}),
        ("all_modules", "--all-modules", {"tok", "ast", "sym", "type"}),
        ("include_eof", "--include-eof", {"tok"}),
    ]

    for attr, flag_name, valid_modes in scoped_flags:
        value = getattr(args, attr)
        provided = bool(value)
        if not provided:
            continue
        if mode in valid_modes:
            continue
        modes_msg = ", ".join(f"--{m}" for m in sorted(valid_modes))
        parser.error(f"option '{flag_name}' is valid only with modes: {modes_msg}")


def main(argv: Optional[List[str]] = None) -> None:
    """Parse CLI arguments, dispatch the selected mode, and exit.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv[1:].
    """
    _init_env_defaults()
    parser = argparse.ArgumentParser(
        prog="l0c",
        description=compiler_identity_text(),
        epilog=(
            "Modes are selected with flags (default: --build). "
            "Use '--' to pass program arguments for --run."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=compiler_identity_text(),
        help="show compiler version and exit",
    )

    parser.add_argument("-v", "--verbose",
                        action='count',
                        default=0,
                        dest='verbosity',
                        help="Increase verbosity: -v=INFO, -vvv=DEBUG")
    parser.add_argument("-l", "--log",
                        action='store_true',
                        default=False,
                        help="Enable rich log formatting (timestamps, levels)")
    parser.add_argument(
        "-P", "--project-root",
        action="append",
        default=[],
        help="Add a project source root (can be passed multiple times)",
    )
    parser.add_argument(
        "-S", "--sys-root",
        action="append",
        default=[],
        help="Add a system/stdlib source root (can be passed multiple times; default: $L0_SYSTEM as colon-separated paths)",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--run", "-r", action="store_const", const="run", dest="mode",
                            help="Build and run a module")
    mode_group.add_argument("--build", action="store_const", const="build", dest="mode",
                            help="Build an executable (default mode)")
    mode_group.add_argument("--gen", "-g", "--codegen", action="store_const", const="gen", dest="mode",
                            help="Generate C code")
    mode_group.add_argument("--check", "--analyze", action="store_const", const="check", dest="mode",
                            help="Parse and analyze a module")
    mode_group.add_argument("--tok", "--tokens", action="store_const", const="tok", dest="mode",
                            help="Dump lexer tokens")
    mode_group.add_argument("--ast", action="store_const", const="ast", dest="mode", help="Pretty-print the AST")
    mode_group.add_argument("--sym", "--symbols", action="store_const", const="sym", dest="mode",
                            help="Dump module-level symbols")
    mode_group.add_argument("--type", "--types", action="store_const", const="type", dest="mode",
                            help="Dump resolved types")
    parser.set_defaults(mode="build")

    parser.add_argument(
        "--output",
        "-o",
        help=(
            "Output path (valid in: '--build', '--gen', '--run')"
        ),
    )
    _add_runtime_args(parser)
    _add_codegen_arg(parser)
    parser.add_argument(
        "--keep-c",
        action="store_true",
        help="Keep generated C file (valid in: '--build', '--run'; use with '--output' to specify C file path"
    )
    _add_all_modules_arg(parser)
    parser.add_argument("--include-eof", action="store_true",
                        help="Include the EOF token in output (valid in: '--tok')")
    _add_target_args(parser)

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    cli_argv, program_args = _split_cli_and_program_args(raw_argv)
    try:
        args = parser.parse_args(cli_argv)
    except SystemExit as exc:
        if exc.code == 2 and _count_cli_verbosity(raw_argv) >= 1:
            fallback_args = argparse.Namespace(
                verbosity=_count_cli_verbosity(raw_argv),
                log=_has_cli_log_flag(raw_argv),
                no_line_directives=False,
                trace_arc=False,
                trace_memory=False,
            )
            log_info(build_compilation_context(fallback_args), compiler_identity_text())
        raise

    if args.mode == "run":
        if len(args.targets) > 1:
            parser.error("mode '--run' accepts exactly one target; use '--' before runtime program arguments")
        args.entry = args.targets[0]
        args.args = program_args
    else:
        if program_args:
            parser.error("arguments after '--' are valid only with '--run'")
        if len(args.targets) > 1:
            parser.error("multiple targets are not supported yet; pass exactly one target")
        args.entry = args.targets[0]

    _validate_mode_scoped_flags(parser, args)
    _emit_verbose_compiler_identity(args)

    dispatch = {
        "run": cmd_run,
        "build": cmd_build,
        "gen": cmd_codegen,
        "check": cmd_check,
        "tok": cmd_tok,
        "ast": cmd_ast,
        "sym": cmd_sym,
        "type": cmd_type,
    }

    rc = dispatch[args.mode](args)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
