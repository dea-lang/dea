#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Analysis, dump, and generated-C commands."""

import argparse
import sys
from pathlib import Path
from typing import List
from l0_ast_printer import format_module
from l0_backend import Backend
from l0_compilation import CompilationUnit
from l0_driver import L0Driver, SourceEncodingError, load_source_utf8
from l0_internal_error import InternalCompilerError
from l0_lexer import TokenKind, Lexer
from l0_symbols import SymbolKind
from l0_types import format_type
from l0_cli_diagnostics import _emit_diagnostic, print_diagnostic_list
from l0_cli_context import _run_analysis, build_compilation_context, build_search_paths


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
        _emit_diagnostic(e.format())
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


def cmd_compile(args: argparse.Namespace) -> int:
    """Report that separate compilation is not implemented in Stage 1 yet.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code 1.
    """
    del args
    _emit_diagnostic(
        "error: [L0C-9510] mode '--compile' is not implemented in Stage 1 yet"
    )
    return 1


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
            print_diagnostic_list(driver.diagnostics)
        else:
            _emit_diagnostic(f"error: [L0C-0020] {e}")
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
            _emit_diagnostic(f"error: [L0C-0030] entry module '{args.entry}' not found in compilation unit")
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


def _dump_tokens_for_file(path: Path, include_eof: bool) -> int:
    """Dump lexer tokens for a single file.

    Args:
        path: Path to the source file.
        include_eof: Whether to include the EOF token in the output.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    try:
        text = load_source_utf8(path)
    except OSError as e:
        _emit_diagnostic(f"error: [L0C-0040] cannot read {path}: {e}")
        return 1
    except SourceEncodingError as e:
        _emit_diagnostic(f"error: [L0C-0041] {e}")
        return 1

    lexer = Lexer(text, filename=str(path))
    try:
        tokens = lexer.tokenize()
    except Exception as e:
        if lexer.diagnostics:
            print_diagnostic_list(lexer.diagnostics)
        else:
            _emit_diagnostic(f"error: [L0C-0042] {e}")
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
                print_diagnostic_list(driver.diagnostics)
            else:
                _emit_diagnostic(f"error: [L0C-0050] {e}")
            return 1

        exit_code = 0
        for name in sorted(cu.modules.keys()):
            try:
                path = search_paths.resolve(name)
            except FileNotFoundError as e:
                _emit_diagnostic(f"error: [L0C-0060] {e}")
                exit_code = 1
                continue

            print(f"=== Tokens for module {name} ({path}) ===")
            rc = _dump_tokens_for_file(path, include_eof=args.include_eof)
            if rc != 0:
                exit_code = rc
            print()
        return exit_code
    else:
        # Only the entry module: resolve its path directly.
        try:
            path = search_paths.resolve(args.entry)
        except FileNotFoundError as e:
            _emit_diagnostic(f"error: [L0C-0070] {e}")
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
