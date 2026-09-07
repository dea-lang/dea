#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""CLI grammar, argument normalization, and mode validation."""

import argparse
import sys
from typing import List, Optional, Sequence, Tuple
from l0_logger import log_info
from l0_cli_context import _init_env_defaults, build_compilation_context


_CLI_LONG_VALUE_OPTIONS = {
    "--project-root",
    "--sys-root",
    "--c-compiler",
    "--c-options",
    "--c-source",
    "--runtime-include",
    "--runtime-lib",
    "--interface-path",
    "--output",
}


_CLI_NAMESPACED_SHORT_VALUE_OPTIONS = {
    "-Rp",
    "-Rs",
    "-Cc",
    "-Co",
    "-Cs",
    "-Ri",
    "-Rl",
}


_CLI_CANONICAL_SHORT_VALUE_OPTIONS = {
    "-I",
    "-L",
    "-l",
}


_CLI_OTHER_SHORT_VALUE_OPTIONS = {
    "-o",
}


_CLI_VALUE_OPTIONS = (
    _CLI_LONG_VALUE_OPTIONS
    | _CLI_NAMESPACED_SHORT_VALUE_OPTIONS
    | _CLI_CANONICAL_SHORT_VALUE_OPTIONS
    | _CLI_OTHER_SHORT_VALUE_OPTIONS
)


def compiler_identity_text() -> str:
    """Return the user-facing compiler identity/version text."""
    return "Dea language / L0 compiler (Stage 1)"


def _scan_cli_presentation_options(argv: Sequence[str]) -> Tuple[int, bool]:
    """Return fallback verbosity and rich-log settings before `--`.

    Values following value-taking options are skipped even when they resemble
    presentation flags, matching the normalization grammar used for parsing.

    Args:
        argv: The complete list of command-line arguments.

    Returns:
        A tuple of (verbosity count, rich-log enabled).
    """
    cli_argv, _, _ = _split_cli_and_program_args(argv)
    verbosity = 0
    rich_log = False
    i = 0
    while i < len(cli_argv):
        token = cli_argv[i]
        if token in _CLI_VALUE_OPTIONS:
            i += 2
            continue
        if token == "--verbose":
            verbosity += 1
        elif len(token) >= 2 and token.startswith("-") and set(token[1:]) == {"v"}:
            verbosity += len(token) - 1
        elif token in {"-Vl", "--log"}:
            rich_log = True
        i += 1
    return verbosity, rich_log


def _emit_verbose_compiler_identity(args: argparse.Namespace) -> None:
    """Emit the compiler identity through the normal verbose logging path."""
    if getattr(args, "verbosity", 0) < 1:
        return
    log_info(build_compilation_context(args), compiler_identity_text())


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
        "-Cc", "--c-compiler",
        help=(
            "C compiler to use (default: $L0_CC has highest precedence if set;"
            " then tcc, gcc, clang, cc from PATH, or $CC, in that order;"
            " valid in: '--build', '--run')"
        ),
    )
    parser.add_argument(
        "-Co", "--c-options",
        help=(
            "Extra options to pass to the C compiler "
            "(default prepends $L0_CFLAGS; options from --c-options are appended after env options; "
            "e.g. -Co=\"-Og -DDEBUG\"; valid in: '--build', '--run')"
        ),
    )
    parser.add_argument(
        "-Cs", "--c-source",
        dest="c_sources",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Additional C source to compile after generated C (repeatable; "
            "valid in: '--build', '--run')"
        ),
    )
    parser.add_argument(
        "-Ri", "--runtime-include",
        help="Path to L0 runtime headers (default: $L0_RUNTIME_INCLUDE; valid in: '--build', '--run')",
    )
    parser.add_argument(
        "-Rl", "--runtime-lib",
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
        "-Va", "--trace-arc",
        action="store_true",
        help="Enable ARC runtime tracing in generated C code (emits L0_TRACE_ARC; valid in: '--build', '--run', '--gen')",
    )
    parser.add_argument(
        "-Vm", "--trace-memory",
        action="store_true",
        help="Enable memory runtime tracing in generated C code (emits L0_TRACE_MEMORY; valid in: '--build', '--run', '--gen')",
    )
    parser.add_argument(
        "-Su", "--unchecked",
        action="store_true",
        help="Disable runtime pointer validation in generated C code (emits L0_RT_UNCHECKED; valid in: '--build', '--run', '--gen')",
    )
    parser.add_argument(
        "-Sb", "--check-basic",
        action="store_true",
        help="Use basic checked runtime pointer validation in generated C code (emits L0_RT_CHECK_BASIC; valid in: '--build', '--run', '--gen')",
    )


def _split_cli_and_program_args(
    argv: Sequence[str],
) -> Tuple[List[str], List[str], bool]:
    """Split compiler CLI arguments from program arguments.

    Args:
        argv: The complete list of command-line arguments.

    Returns:
        A tuple of (compiler_args, program_args, separator_present).
    """
    argv_list = list(argv)
    if "--" not in argv_list:
        return argv_list, [], False
    idx = argv_list.index("--")
    return argv_list[:idx], argv_list[idx + 1:], True


def _normalize_cli_argv(
    parser: argparse.ArgumentParser, argv: Sequence[str]
) -> List[str]:
    """Normalize exact short-option spellings before passing them to argparse.

    Namespaced value options support a following value or `=VALUE`, but not a
    concatenated value. Canonical `-I`, `-L`, and `-l` options accept attached
    or following values, but not `=VALUE`. Only `-v` may form a cluster.

    Args:
        parser: The argument parser for reporting errors.
        argv: Compiler arguments before the optional `--` separator.

    Returns:
        A normalized compiler argument list.
    """
    short_flags = {
        "-h",
        "-V",
        "-v",
        "-Vl",
        "-Va",
        "-Vm",
        "-r",
        "-c",
        "-Gc",
        "-Gk",
        "-Sb",
        "-Su",
        "-g",
        "-S",
        "-NLD",
        "-a",
    }
    long_flags = {
        "--help",
        "--version",
        "--verbose",
        "--log",
        "--run",
        "--build",
        "--compile",
        "--gen",
        "--codegen",
        "--check",
        "--analyze",
        "--tok",
        "--tokens",
        "--ast",
        "--sym",
        "--symbols",
        "--type",
        "--types",
        "--no-line-directives",
        "--trace-arc",
        "--trace-memory",
        "--unchecked",
        "--check-basic",
        "--keep-c",
        "--all-modules",
        "--include-eof",
    }
    mode_flags = {
        "-r": "--run",
        "--run": "--run",
        "--build": "--build",
        "-c": "--compile",
        "--compile": "--compile",
        "-Gc": "--gen",
        "--gen": "--gen",
        "--codegen": "--gen",
        "--check": "--check",
        "--analyze": "--check",
        "--tok": "--tok",
        "--tokens": "--tok",
        "--ast": "--ast",
        "--sym": "--sym",
        "--symbols": "--sym",
        "--type": "--type",
        "--types": "--type",
    }

    normalized: List[str] = []
    selected_mode: Optional[str] = None
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in _CLI_VALUE_OPTIONS:
            if i + 1 >= len(argv):
                parser.error(f"[L0C-2003] missing value for option '{token}'")
            normalized.append(f"{token}={argv[i + 1]}")
            i += 2
            continue

        if not token.startswith("-"):
            normalized.append(token)
            i += 1
            continue

        if token in short_flags or token in long_flags:
            requested_mode = mode_flags.get(token)
            if requested_mode is not None:
                if selected_mode is None:
                    selected_mode = requested_mode
                elif selected_mode != requested_mode:
                    parser.error(
                        "[L0C-2002] multiple mode flags provided: "
                        f"{selected_mode} conflicts with {requested_mode}"
                    )
            normalized.append(token)
            i += 1
            continue

        if len(token) >= 2 and set(token[1:]) == {"v"}:
            normalized.append(token)
            i += 1
            continue

        if any(
            token.startswith(f"{option}=")
            for option in _CLI_LONG_VALUE_OPTIONS
        ):
            normalized.append(token)
            i += 1
            continue

        if any(
            token.startswith(f"{option}=")
            for option in _CLI_NAMESPACED_SHORT_VALUE_OPTIONS
        ):
            normalized.append(token)
            i += 1
            continue

        if any(
            token.startswith(option)
            and len(token) > len(option)
            and token[len(option)] != "="
            for option in _CLI_CANONICAL_SHORT_VALUE_OPTIONS
        ):
            normalized.append(token)
            i += 1
            continue

        parser.error(f"[L0C-2001] unknown option '{token}'")

    return normalized


def _validate_mode_scoped_flags(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject flags that were provided for a mode where they are not valid.

    Args:
        parser: The argument parser for reporting errors.
        args: The parsed command-line arguments.
    """
    mode = args.mode

    scoped_flags = [
        ("output", "--output", {"build", "run", "gen"}, "L0C-2010"),
        ("keep_c", "--keep-c", {"build", "run"}, "L0C-2011"),
        ("c_compiler", "--c-compiler", {"build", "run"}, "L0C-2012"),
        ("c_options", "--c-options", {"build", "run"}, "L0C-2013"),
        ("c_sources", "--c-source", {"build", "run"}, "L0C-2029"),
        ("runtime_include", "--runtime-include", {"build", "run"}, "L0C-2014"),
        ("runtime_lib", "--runtime-lib", {"build", "run"}, "L0C-2015"),
        ("no_line_directives", "--no-line-directives", {"build", "run", "gen"}, "L0C-2016"),
        ("trace_arc", "--trace-arc", {"build", "run", "gen"}, "L0C-2017"),
        ("trace_memory", "--trace-memory", {"build", "run", "gen"}, "L0C-2018"),
        ("unchecked", "--unchecked", {"build", "run", "gen"}, "L0C-2025"),
        ("check_basic", "--check-basic", {"build", "run", "gen"}, "L0C-2027"),
        ("all_modules", "--all-modules", {"tok", "ast", "sym", "type"}, "L0C-2019"),
        ("include_eof", "--include-eof", {"tok"}, "L0C-2020"),
        ("interface_paths", "--interface-path", {"compile"}, "L0C-2031"),
    ]
    optional_string_attrs = {
        "output",
        "c_compiler",
        "c_options",
        "runtime_include",
        "runtime_lib",
    }

    for attr, flag_name, valid_modes, code in scoped_flags:
        value = getattr(args, attr)
        provided = value is not None if attr in optional_string_attrs else bool(value)
        if not provided:
            continue
        if mode in valid_modes:
            continue
        modes_msg = ", ".join(f"--{m}" for m in sorted(valid_modes))
        if code == "L0C-2031":
            parser.error(f"[{code}] option '{flag_name}' is valid only with mode: {modes_msg}")
        else:
            parser.error(f"[{code}] option '{flag_name}' is valid only with modes: {modes_msg}")

    if getattr(args, "unchecked", False) and (
        getattr(args, "trace_arc", False) or getattr(args, "trace_memory", False)
    ):
        parser.error("[L0C-2026] option '--unchecked' cannot be combined with '--trace-arc' or '--trace-memory'")
    if getattr(args, "check_basic", False) and (
        getattr(args, "unchecked", False)
        or getattr(args, "trace_arc", False)
        or getattr(args, "trace_memory", False)
    ):
        parser.error("[L0C-2028] option '--check-basic' cannot be combined with '--unchecked', '--trace-arc', or '--trace-memory'")


def _validate_reserved_canonical_flags(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Reject canonical compiler options whose behavior is not implemented.

    Args:
        parser: The argument parser for reporting errors.
        args: The parsed command-line arguments.
    """
    reserved_options = [
        (
            "reserved_debug",
            "option '-g' is reserved for debug information and is not supported yet",
        ),
        (
            "reserved_assembly",
            "option '-S' is reserved for assembly output and is not supported yet",
        ),
        (
            "reserved_library_paths",
            "option '-L' is reserved for external library search and is not supported yet",
        ),
        (
            "reserved_libraries",
            "option '-l' is reserved for external library selection and is not supported yet",
        ),
    ]
    for attr, message in reserved_options:
        if getattr(args, attr):
            parser.error(f"[L0C-2032] {message}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse and validate compiler arguments.

    Args:
        argv: Arguments to parse, or the current process arguments when omitted.

    Returns:
        The validated command options.

    Raises:
        SystemExit: For help, version, or invalid arguments.
    """
    _init_env_defaults()
    parser = argparse.ArgumentParser(
        prog="l0c",
        description=compiler_identity_text(),
        allow_abbrev=False,
        epilog=(
            "Modes are selected with flags (default: --build). "
            "Use '--' to pass program arguments for --run."
        ),
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=compiler_identity_text(),
        help="show compiler version and exit",
    )

    parser.add_argument("-v", "--verbose",
                        action='count',
                        default=0,
                        dest='verbosity',
                        help="Increase verbosity: -v=INFO, -vvv=DEBUG")
    parser.add_argument("-Vl", "--log",
                        action='store_true',
                        default=False,
                        help="Enable rich log formatting (timestamps, levels)")
    parser.add_argument(
        "-Rp", "--project-root",
        action="append",
        default=[],
        help="Add a project source root (can be passed multiple times)",
    )
    parser.add_argument(
        "-Rs", "--sys-root",
        action="append",
        default=[],
        help="Add a system/stdlib source root (can be passed multiple times; default: $L0_SYSTEM as colon-separated paths)",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--run", "-r", action="store_const", const="run", dest="mode",
                            help="Build and run a module")
    mode_group.add_argument("--build", action="store_const", const="build", dest="mode",
                            help="Build an executable (default mode)")
    mode_group.add_argument("-c", "--compile", action="store_const", const="compile", dest="mode",
                            help="Compile one target without linking (not implemented in Stage 1 yet)")
    mode_group.add_argument("--gen", "-Gc", "--codegen", action="store_const", const="gen", dest="mode",
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
    parser.add_argument(
        "-I", "--interface-path",
        action="append",
        default=[],
        dest="interface_paths",
        metavar="INTERFACE_PATH",
        help=(
            "Add an interface search path (can be passed multiple times; "
            "valid in: '--compile'; interface loading is not implemented yet)"
        ),
    )
    parser.add_argument(
        "-g",
        action="store_true",
        dest="reserved_debug",
        help="Generate debug information (reserved; not supported yet)",
    )
    parser.add_argument(
        "-S",
        action="store_true",
        dest="reserved_assembly",
        help="Emit assembly output (reserved; not supported yet)",
    )
    parser.add_argument(
        "-L",
        action="append",
        default=[],
        dest="reserved_library_paths",
        metavar="LIBRARY_PATH",
        help="Add an external library search path (reserved; not supported yet)",
    )
    parser.add_argument(
        "-l",
        action="append",
        default=[],
        dest="reserved_libraries",
        metavar="LIBRARY",
        help="Select an external library (reserved; not supported yet)",
    )
    _add_codegen_arg(parser)
    parser.add_argument(
        "-Gk", "--keep-c",
        action="store_true",
        help="Keep generated C file (valid in: '--build', '--run'; use with '--output' to specify C file path"
    )
    _add_all_modules_arg(parser)
    parser.add_argument("--include-eof", action="store_true",
                        help="Include the EOF token in output (valid in: '--tok')")
    _add_target_args(parser)

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    cli_argv, program_args, separator_present = _split_cli_and_program_args(raw_argv)
    try:
        early_exit = next(
            (
                token
                for token in cli_argv
                if token in {"-h", "--help", "-V", "--version"}
            ),
            None,
        )
        if early_exit is not None:
            parser.parse_args([early_exit])
        normalized_cli_argv = _normalize_cli_argv(parser, cli_argv)
        if not any(not token.startswith("-") for token in normalized_cli_argv):
            parser.error("[L0C-2021] missing required target module/file name")
        args = parser.parse_args(normalized_cli_argv)
    except SystemExit as exc:
        fallback_verbosity, fallback_log = _scan_cli_presentation_options(raw_argv)
        if exc.code == 2 and fallback_verbosity >= 1:
            fallback_args = argparse.Namespace(
                verbosity=fallback_verbosity,
                log=fallback_log,
                no_line_directives=False,
                trace_arc=False,
                trace_memory=False,
                unchecked=False,
                check_basic=False,
            )
            log_info(build_compilation_context(fallback_args), compiler_identity_text())
        raise

    if args.mode == "run":
        if len(args.targets) > 1:
            parser.error("[L0C-2022] mode '--run' accepts exactly one target; use '--' before runtime program arguments")
        args.entry = args.targets[0]
        args.args = program_args
    else:
        if separator_present:
            parser.error("[L0C-2023] arguments after '--' are valid only with '--run'")
        if len(args.targets) > 1:
            parser.error("[L0C-2024] multiple targets are not supported yet; pass exactly one target")
        args.entry = args.targets[0]

    _validate_reserved_canonical_flags(parser, args)
    _validate_mode_scoped_flags(parser, args)
    _emit_verbose_compiler_identity(args)

    return args
