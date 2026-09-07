#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Source search paths, compiler context, and analysis preparation."""

import argparse
import os
from pathlib import Path
from re import fullmatch
from typing import Optional
from l0_analysis import AnalysisResult
from l0_context import CompilationContext
from l0_driver import L0Driver
from l0_logger import log_info
from l0_paths import SourceSearchPaths
from l0_cli_diagnostics import _emit_diagnostic, print_diagnostics


def _init_env_defaults() -> None:
    """Initialize default environment variables based on L0_HOME."""
    l0_home = os.getenv("L0_HOME")
    if not l0_home:
        return
    if not os.getenv("L0_SYSTEM"):
        os.environ["L0_SYSTEM"] = os.path.join(l0_home, "shared", "l0", "stdlib")
    if not os.getenv("L0_RUNTIME_INCLUDE"):
        os.environ["L0_RUNTIME_INCLUDE"] = os.path.join(l0_home, "shared", "runtime")


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
        _emit_diagnostic(
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
        rt_unchecked=getattr(args, 'unchecked', False),
        rt_check_basic=getattr(args, 'check_basic', False),
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
    print_diagnostics(result)
    exit_code = 1 if (result.cu is None or result.has_errors()) else 0
    return result, context, exit_code
