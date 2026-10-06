#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""L1 installed-context adapters around the shared prefix renderers."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from dea_tooling.launchers import (
    render_prefix_env_cmd_script, render_prefix_env_script,
    render_prefix_native_cmd_wrapper, render_prefix_native_wrapper,
)


def _replace_once(text: str, original: str, replacement: str) -> str:
    """Fail visibly if a shared template changes the L1 adaptation boundary."""
    if text.count(original) != 1:
        raise ValueError("shared prefix template changed; review the L1 installed-context adapter")
    return text.replace(original, replacement, 1)


def native_wrapper(*, native_name: str = "l1c-stage2.native") -> str:
    """Render a POSIX installed launcher that selects its own prefix.

    Args:
        native_name: Sibling native artifact filename.

    Returns:
        Shell script overriding inherited repo layout while retaining selectors.
    """
    text = render_prefix_native_wrapper(home_var_name="L1_HOME", native_name=native_name)
    return _replace_once(text, 'if [ -z "${L1_HOME:-}" ]; then\n'
                         '    export L1_HOME="${prefix_root}"\nfi\n',
                         'export L1_HOME="${prefix_root}"\nunset L1_BUILD_DIR\n')


def native_cmd_wrapper(*, native_name: str = "l1c-stage2.native") -> str:
    """Render a scoped Windows launcher preserving the compiler exit status.

    Args:
        native_name: Sibling native artifact filename.

    Returns:
        Batch script restoring the caller environment on success and failure.
    """
    text = render_prefix_native_cmd_wrapper(home_var_name="L1_HOME", native_name=native_name)
    text = _replace_once(text, "@echo off\n", "@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\n")
    text = _replace_once(text, 'if "%L1_HOME%"=="" set "L1_HOME=%PREFIX_ROOT%"\n',
                         'set "L1_HOME=%PREFIX_ROOT%"\nset "L1_BUILD_DIR="\n')
    return text + 'set "_L1_EXITCODE=%ERRORLEVEL%"\nendlocal & exit /b %_L1_EXITCODE%\n'


_POSIX_PREPEND = r"""_l1_prepend_path() {
    local rest="${PATH-}:"
    local entry
    local selected_path="${SCRIPT_DIR}"
    while [[ -n "${rest}" ]]; do
        entry="${rest%%:*}"
        rest="${rest#*:}"
        if [[ "${entry}" != "${SCRIPT_DIR}" ]]; then
            selected_path="${selected_path}:${entry}"
        fi
    done
    export PATH="${selected_path}"
}
_l1_prepend_path
unset -f _l1_prepend_path 2>/dev/null || true
"""


def env_script() -> str:
    """Render bash/zsh activation with stackable prefix selection.

    Returns:
        Sourceable script clearing repo build defaults and moving bin to PATH front.
    """
    text = render_prefix_env_script(env_script_name="l1-env.sh", home_var_name="L1_HOME",
                                    compiler_env_var="L1_CC")
    text = _replace_once(text, 'export L1_HOME="${PREFIX_DIR}"\n',
                         'export L1_HOME="${PREFIX_DIR}"\nunset L1_BUILD_DIR\n')
    return _replace_once(text, 'case ":${PATH}:" in\n'
                         '    *":${SCRIPT_DIR}:"*) ;;\n'
                         '    *) export PATH="${SCRIPT_DIR}${PATH:+:${PATH}}" ;;\nesac\n',
                         _POSIX_PREPEND)


# Keep delayed expansion off so literal exclamation marks survive. Split PATH
# character by character to retain empty entries and the order of other entries.
_CMD_PREPEND = r"""set "_L1_TAIL="
set "_L1_TOOLCHAIN_PRESENT="
if not defined PATH goto :_l1_path_done
set "_L1_REST=%PATH%;"
set "_L1_ENTRY="
:_l1_path_loop
if not defined _L1_REST goto :_l1_path_done
set "_L1_CHAR=%_L1_REST:~0,1%"
set "_L1_REST=%_L1_REST:~1%"
if "%_L1_CHAR%"==";" goto :_l1_path_entry
set "_L1_ENTRY=%_L1_ENTRY%%_L1_CHAR%"
goto :_l1_path_loop
:_l1_path_entry
if /I "%_L1_ENTRY%"=="%SCRIPT_DIR%" goto :_l1_path_next
if defined _L1_TOOLCHAIN_BIN if /I "%_L1_ENTRY%"=="%_L1_TOOLCHAIN_BIN%" set "_L1_TOOLCHAIN_PRESENT=1"
set "_L1_TAIL=%_L1_TAIL%;%_L1_ENTRY%"
:_l1_path_next
set "_L1_ENTRY="
goto :_l1_path_loop
:_l1_path_done
set "PATH=%SCRIPT_DIR%%_L1_TAIL%"
if /I "%_L1_TOOLCHAIN_BIN%"=="%SCRIPT_DIR%" set "_L1_TOOLCHAIN_PRESENT=1"
if defined _L1_TOOLCHAIN_BIN if not defined _L1_TOOLCHAIN_PRESENT set "PATH=%SCRIPT_DIR%;%_L1_TOOLCHAIN_BIN%%_L1_TAIL%"
set "_L1_REST="
set "_L1_ENTRY="
set "_L1_CHAR="
set "_L1_TAIL="
set "_L1_TOOLCHAIN_BIN="
set "_L1_TOOLCHAIN_PRESENT="
"""


def env_cmd_script() -> str:
    """Render native Windows activation while retaining the shared toolchain probe.

    Returns:
        Batch activation changing the caller's prefix and deduplicating PATH.
    """
    text = render_prefix_env_cmd_script(env_script_label="l1-env", home_var_name="L1_HOME")
    text = _replace_once(text, "@echo off\n", "@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\n")
    text = _replace_once(text, 'set "L1_HOME=%PREFIX_ROOT%"\n',
                         'set "L1_HOME=%PREFIX_ROOT%"\nset "L1_BUILD_DIR="\n')
    text = _replace_once(text, 'set "PATH_PADDED=;%PATH%;"\n'
                         'if /I "%PATH_PADDED%"=="%PATH_PADDED:;%SCRIPT_DIR%;=%" (\n'
                         '    if defined PATH (\n'
                         '        set "PATH=%SCRIPT_DIR%;%PATH%"\n'
                         '    ) else (\n'
                         '        set "PATH=%SCRIPT_DIR%"\n'
                         '    )\n)\nset "PATH_PADDED="\n', "")
    # Retain toolchain discovery, but check membership in the PATH entry loop.
    # CMD cannot nest percent expansions in the shared substitution expression.
    text = _replace_once(text, 'set "PATH_PADDED=;%PATH%;"\n'
                         'if /I not "%PATH_PADDED%"=="%PATH_PADDED:;%_MSYS2_BIN%;=%" goto :_msys2_toolchain_done\n'
                         'set "PATH=%_MSYS2_BIN%;%PATH%"\n',
                         'set "_L1_TOOLCHAIN_BIN=%_MSYS2_BIN%"\n')
    text = _replace_once(text, 'set "_MSYS2_BIN="\nif defined MSYS2_TOOLCHAIN_BIN',
                         'set "_MSYS2_BIN="\nset "_L1_TOOLCHAIN_BIN="\nif defined MSYS2_TOOLCHAIN_BIN')
    return text + _CMD_PREPEND + 'endlocal & set "PATH=%PATH%" & set "L1_HOME=%L1_HOME%" & set "L1_BUILD_DIR="\n'
