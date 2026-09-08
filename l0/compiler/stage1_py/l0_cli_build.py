#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Native compilation and temporary-source/build/run transactions."""

import argparse
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from re import search
from l0_analysis import AnalysisResult
from l0_backend import Backend
from l0_context import CompilationContext
from l0_driver import L0Driver
from l0_internal_error import InternalCompilerError
from l0_logger import log_info, log_error, log_warning
from l0_symbols import SymbolKind
from l0_types import format_type
from l0_cli_diagnostics import _emit_diagnostic, print_diagnostics
from l0_cli_context import build_compilation_context, build_search_paths


def _find_cc() -> str | None:
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


class _TemporarySourceWriteError(OSError):
    """Report a generated-C write failure that also retained its path."""

    def __init__(self, retained_path: Path):
        """Initialize the failure.

        Args:
            retained_path: Temporary generated-C path that could not be removed.
        """
        super().__init__(f"temporary source retained at '{retained_path}'")
        self.retained_path = retained_path


def _validated_temporary_directory() -> Path:
    """Resolve and validate the host temporary directory.

    POSIX temporary sources are safe to pass to an external compiler only when
    every component in the resolved directory hierarchy is owned by root or
    the effective user. Group- or other-writable components must also carry
    the sticky bit. Windows relies on the platform temporary directory ACL.

    Returns:
        The resolved temporary directory.

    Raises:
        OSError: If the directory cannot be resolved or its POSIX hierarchy is
            not trusted.
    """
    temp_dir = Path(tempfile.gettempdir()).resolve(strict=True)
    if _is_windows_host():
        return temp_dir

    effective_uid = os.geteuid()
    for component in (temp_dir, *temp_dir.parents):
        component_stat = component.stat()
        if not stat.S_ISDIR(component_stat.st_mode):
            raise OSError(f"temporary hierarchy component is not a directory: {component}")
        if component_stat.st_uid not in {0, effective_uid}:
            raise OSError(
                f"temporary hierarchy component has an unsafe owner: {component}"
            )
        writable_by_others = component_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        if writable_by_others and not component_stat.st_mode & stat.S_ISVTX:
            raise OSError(
                "temporary hierarchy component is writable without sticky bit: "
                f"{component}"
            )

    return temp_dir


def _emit_temporary_source_cleanup_failure(c_path: Path) -> None:
    """Report a compiler-temporary source retained after failed cleanup.

    Args:
        c_path: Retained temporary generated-C path.
    """
    _emit_diagnostic(
        f"error: [L0C-9512] cannot remove compiler temporary source; retained at '{c_path}'"
    )


def _remove_temporary_c_source(c_path: Path) -> bool:
    """Remove a generated-C temporary and report retained recovery state.

    Args:
        c_path: Temporary generated-C path to remove.

    Returns:
        True when the path is absent after cleanup, otherwise False.
    """
    try:
        c_path.unlink(missing_ok=True)
    except OSError:
        _emit_temporary_source_cleanup_failure(c_path)
        return False
    return True


def _write_temporary_c_source(c_code: str) -> Path:
    """Atomically create and write one anonymous generated-C source.

    The returned descriptor reserves the path before any generated content is
    written. Writing through that descriptor avoids reopening an attacker-
    substituted path between selection and creation.

    Args:
        c_code: Generated C source text.

    Returns:
        The temporary source path, closed and ready for the host compiler.

    Raises:
        OSError: If the path cannot be created or written.
    """
    temp_dir = _validated_temporary_directory()
    descriptor, raw_path = tempfile.mkstemp(suffix=".c", dir=str(temp_dir))
    c_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(c_code)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            c_path.unlink(missing_ok=True)
        except OSError:
            raise _TemporarySourceWriteError(c_path)
        raise
    return c_path


def _check_entry_main_for_build(result: AnalysisResult, entry_name: str) -> bool:
    """Check that the entry module defines a valid 'main' function for build/run.

    Args:
        result: The analysis result.
        entry_name: The name of the entry module.

    Returns:
        True if a valid 'main' function is found, False otherwise.
    """
    entry_env = result.module_envs.get(entry_name)
    if entry_env is None:
        _emit_diagnostic(f"error: [L0C-0012] entry module '{entry_name}' not found in analysis result")
        return False

    main_symbol = entry_env.locals.get("main")
    if main_symbol is None or main_symbol.kind != SymbolKind.FUNC:
        _emit_diagnostic(
            f"error: [L0C-0012] entry module '{entry_name}' must define a 'main' function for build/run",
        )
        return False

    main_type = result.func_types.get((entry_name, "main"))
    if main_type is None:
        _emit_diagnostic(
            f"error: [L0C-0016] missing type information for entry function '{entry_name}::main'",
        )
        return False

    ret_type = format_type(main_type.result)
    if ret_type not in {"void", "int", "bool"}:
        _emit_diagnostic(
            "warning: [L0C-0013] entry 'main' returns "
            f"'{ret_type}' (preferred: void/int/bool); generated C entry wrapper will ignore the return value",
        )
    return True


def _validate_runtime_library_path(runtime_lib_path: str) -> bool:
    """Validate that the provided runtime library path exists and is a directory.

    Args:
        runtime_lib_path: Path to the runtime library directory.

    Returns:
        True if the path is a directory, False otherwise.
    """
    runtime_dir = Path(runtime_lib_path)
    if not runtime_dir.is_dir():
        _emit_diagnostic(
            f"error: [L0C-0014] runtime library path '{runtime_lib_path}' does not exist or is not a directory",
        )
        return False

    return True


def _split_c_options(raw_options: str | None) -> list[str]:
    """Split a raw C options string into individual compiler arguments.

    Args:
        raw_options: Raw options string, or None.

    Returns:
        A list of whitespace-delimited compiler option tokens.
    """
    if not raw_options:
        return []
    return raw_options.split()


def _get_optimize_flag(flag_family: str, extra_opts: list[str]) -> str | None:
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

    # Default quick optimization level for non-debug builds (can be overridden with --c-options/-Co or L0_CFLAGS)
    if flag_family in {"gcc", "tcc"}:
        return "-O1"
    elif flag_family == "msvc":
        return "/O1"
    else:
        return None


def _compile_generated_c(
    args: argparse.Namespace,
    context: CompilationContext,
    c_path: Path,
    exe_path: Path,
) -> int:
    """Invoke the selected host compiler for one generated-C source.

    Args:
        args: Parsed build arguments.
        context: Active compiler context.
        c_path: Closed generated-C source path.
        exe_path: Requested executable output path.

    Returns:
        Zero when the host compiler succeeds, otherwise one.
    """
    compiler = args.c_compiler or _find_cc()
    if compiler is None:
        _emit_diagnostic(
            "error: [L0C-0009] no C compiler found: use '--c-compiler' to specify one or set the L0_CC environment variable"
        )
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

    # Preprocessor/compiler options must precede the source path for tcc;
    # output and library flags can follow it.
    cmd = [compiler]
    cmd.extend(extra_opts)

    if flag_family == "tcc":
        cmd.extend(["-std=c99", "-Wall", "-pedantic"])
    elif flag_family == "gcc":
        cmd.extend(
            [
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-Wno-unused",
                "-Wno-unused-parameter",
                "-pedantic-errors",
            ]
        )
    elif flag_family == "msvc":
        cmd.extend(["/std:c11", "/W4"])
    else:
        log_warning(
            context,
            f"Unsupported compiler '{compiler}' (flag family '{flag_family}'): not adding standard flags",
        )

    optimize_flag = _get_optimize_flag(flag_family, extra_opts)
    if optimize_flag:
        log_info(context, f"Adding optimization flag: {optimize_flag}")
        cmd.append(optimize_flag)

    if args.runtime_include:
        cmd.extend(_runtime_include_flags(flag_family, args.runtime_include))
    elif os.getenv("L0_RUNTIME_INCLUDE"):
        cmd.extend(
            _runtime_include_flags(flag_family, os.getenv("L0_RUNTIME_INCLUDE"))
        )

    cmd.append(str(c_path))
    cmd.extend(getattr(args, "c_sources", []))
    cmd.extend(_output_flags(flag_family, exe_path))

    runtime_lib_path = args.runtime_lib or os.getenv("L0_RUNTIME_LIB")
    if runtime_lib_path and not _validate_runtime_library_path(runtime_lib_path):
        return 1

    if args.runtime_lib:
        cmd.extend(_runtime_library_flags(flag_family, args.runtime_lib))
    elif os.getenv("L0_RUNTIME_LIB"):
        cmd.extend(_runtime_library_flags(flag_family, os.getenv("L0_RUNTIME_LIB")))

    log_info(context, "Compiling:")
    log_info(context, f"{' '.join(cmd)}")

    compile_result = subprocess.run(cmd, capture_output=True, text=True)
    if compile_result.returncode != 0:
        _emit_diagnostic("error: [L0C-0010] C compilation failed:")
        if compile_result.stderr:
            log_error(context, compile_result.stderr)
        if compile_result.stdout:
            log_error(context, compile_result.stdout)
        return 1

    if compile_result.stderr:
        log_error(context, compile_result.stderr)

    log_info(context, f"Built executable: {exe_path}")
    return 0


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
    print_diagnostics(result)

    if result.cu is None or result.has_errors():
        return 1

    if not _check_entry_main_for_build(result, args.entry):
        return 1

    backend = Backend(result)
    try:
        c_code = backend.generate()
    except InternalCompilerError as error:
        _emit_diagnostic(error.format())
        return 1

    exe_path = Path(args.output) if args.output else Path(_default_executable_name())

    if args.keep_c:
        c_output_override = getattr(args, "c_output_path", None)
        c_path = (
            Path(c_output_override)
            if c_output_override
            else exe_path.with_suffix(".c")
        )
        c_path.write_text(c_code, encoding="utf-8")
        log_info(context, f"Generated C code: {c_path}")
        return _compile_generated_c(args, context, c_path, exe_path)

    try:
        c_path = _write_temporary_c_source(c_code)
    except _TemporarySourceWriteError as error:
        _emit_diagnostic("error: [L0C-9511] cannot write compiler temporary source")
        _emit_temporary_source_cleanup_failure(error.retained_path)
        return 1
    except OSError:
        _emit_diagnostic("error: [L0C-9511] cannot write compiler temporary source")
        return 1

    try:
        log_info(context, f"Generated C code: {c_path}")
        build_rc = _compile_generated_c(args, context, c_path, exe_path)
    except BaseException:
        _remove_temporary_c_source(c_path)
        raise

    if not _remove_temporary_c_source(c_path):
        return 1
    return build_rc


def cmd_run(args: argparse.Namespace) -> int:
    """Build and run an L0 module.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code from the executed program or the build process.
    """
    context = build_compilation_context(args)
    try:
        temp_dir = _validated_temporary_directory()
    except OSError:
        _emit_diagnostic("error: [L0C-9511] cannot write compiler temporary source")
        return 1

    # Create temporary executable.
    temp_exe_suffix = ".exe" if _is_windows_host() else ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=temp_exe_suffix,
            delete=False,
            dir=str(temp_dir),
        ) as stream:
            temp_exe = stream.name
    except OSError:
        _emit_diagnostic("error: [L0C-9511] cannot write compiler temporary source")
        return 1

    try:
        # Build to temporary executable
        keep_c = getattr(args, 'keep_c', False)
        output_arg = getattr(args, 'output', None)
        if output_arg and not keep_c:
            _emit_diagnostic(
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
            c_sources=getattr(args, "c_sources", []),
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
            unchecked=getattr(args, 'unchecked', False),
            check_basic=getattr(args, 'check_basic', False),
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
