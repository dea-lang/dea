#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Shared launcher and env-script renderers for Dea language levels."""

from __future__ import annotations


_MSYS2_TOOLCHAIN_PROBE_CMD = r"""
rem -- Put the supported MSYS2 toolchain bin directory on PATH (compiler + DLLs) for --build and --run.
set "_MSYS2_BIN="
if defined MSYS2_TOOLCHAIN_BIN if exist "%MSYS2_TOOLCHAIN_BIN%\" set "_MSYS2_BIN=%MSYS2_TOOLCHAIN_BIN%"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
if defined MINGW_PREFIX if exist "%MINGW_PREFIX%\bin\" set "_MSYS2_BIN=%MINGW_PREFIX%\bin"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
if defined MSYS2_ROOT if exist "%MSYS2_ROOT%\ucrt64\bin\" set "_MSYS2_BIN=%MSYS2_ROOT%\ucrt64\bin"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
if defined MSYS2_ROOT if exist "%MSYS2_ROOT%\mingw64\bin\" set "_MSYS2_BIN=%MSYS2_ROOT%\mingw64\bin"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
for /f "tokens=2*" %%A in ('reg query "HKCU\Software\MSYS2" /v "InstallDir" 2^>nul') do (
    if exist "%%B\ucrt64\bin\" set "_MSYS2_BIN=%%B\ucrt64\bin"
    if not defined _MSYS2_BIN if exist "%%B\mingw64\bin\" set "_MSYS2_BIN=%%B\mingw64\bin"
)
if defined _MSYS2_BIN goto :_msys2_toolchain_set
for /f "tokens=2*" %%A in ('reg query "HKLM\Software\MSYS2" /v "InstallDir" 2^>nul') do (
    if exist "%%B\ucrt64\bin\" set "_MSYS2_BIN=%%B\ucrt64\bin"
    if not defined _MSYS2_BIN if exist "%%B\mingw64\bin\" set "_MSYS2_BIN=%%B\mingw64\bin"
)
if defined _MSYS2_BIN goto :_msys2_toolchain_set
if exist "C:\msys64\ucrt64\bin\" set "_MSYS2_BIN=C:\msys64\ucrt64\bin"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
if exist "C:\msys64\mingw64\bin\" set "_MSYS2_BIN=C:\msys64\mingw64\bin"
if defined _MSYS2_BIN goto :_msys2_toolchain_set
echo [{env_script_label}] warning: MSYS2 UCRT64 or MINGW64 toolchain not found. Set MSYS2_TOOLCHAIN_BIN, set MSYS2_ROOT, or add ucrt64\bin or mingw64\bin to PATH. 1>&2
goto :_msys2_toolchain_done
:_msys2_toolchain_set
set "PATH_PADDED=;%PATH%;"
if /I not "%PATH_PADDED%"=="%PATH_PADDED:;%_MSYS2_BIN%;=%" goto :_msys2_toolchain_done
set "PATH=%_MSYS2_BIN%;%PATH%"
:_msys2_toolchain_done
set "_MSYS2_BIN="
set "PATH_PADDED="
"""


def render_repo_python_stage1_wrapper(
    *,
    repo_relative_from_bin: str,
    home_var_name: str,
    source_entry_relpath: str,
) -> str:
    """Return the repo-relative Python-backed Stage 1 launcher."""

    return f"""#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "${{script_dir}}/{repo_relative_from_bin}" && pwd -P)
monorepo_root=$(CDPATH= cd -- "${{repo_root}}/.." && pwd -P)

export {home_var_name}="${{repo_root}}/compiler"

python_bin="${{PYTHON:-}}"
if [ -z "${{python_bin}}" ] && [ -x "${{monorepo_root}}/.venv/bin/python" ]; then
    python_bin="${{monorepo_root}}/.venv/bin/python"
fi
if [ -z "${{python_bin}}" ] && [ -x "${{monorepo_root}}/.venv/Scripts/python.exe" ]; then
    python_bin="${{monorepo_root}}/.venv/Scripts/python.exe"
fi
if [ -z "${{python_bin}}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        python_bin="python3"
    else
        python_bin="python"
    fi
fi

exec "${{python_bin}}" "${{repo_root}}/{source_entry_relpath}" "$@"
"""


def render_repo_python_stage1_cmd_wrapper(
    *,
    repo_relative_from_bin: str,
    home_var_name: str,
    source_entry_relpath: str,
) -> str:
    """Return the repo-relative Windows Python-backed Stage 1 launcher."""

    bat_rel = repo_relative_from_bin.replace("/", "\\")
    source_entry = source_entry_relpath.replace("/", "\\")
    return f"""@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\\{bat_rel}") do set "REPO_ROOT=%%~fI"
for %%I in ("%REPO_ROOT%\\..") do set "MONOREPO_ROOT=%%~fI"
set "PYTHON_BIN=%PYTHON%"

if not defined PYTHON_BIN if exist "%MONOREPO_ROOT%\\.venv\\Scripts\\python.exe" set "PYTHON_BIN=%MONOREPO_ROOT%\\.venv\\Scripts\\python.exe"
if not defined PYTHON_BIN if exist "%MONOREPO_ROOT%\\.venv\\bin\\python.exe" set "PYTHON_BIN=%MONOREPO_ROOT%\\.venv\\bin\\python.exe"
if not defined PYTHON_BIN if exist "%MONOREPO_ROOT%\\.venv\\bin\\python" set "PYTHON_BIN=%MONOREPO_ROOT%\\.venv\\bin\\python"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

set "{home_var_name}=%REPO_ROOT%\\compiler"

"%PYTHON_BIN%" "%REPO_ROOT%\\{source_entry}" %*
set "EXITCODE=%ERRORLEVEL%"
endlocal & exit /b %EXITCODE%
"""


def render_repo_native_wrapper(
    *,
    repo_relative_from_bin: str,
    home_var_name: str,
    native_name: str,
) -> str:
    """Return the repo-relative native wrapper."""

    return f"""#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "${{script_dir}}/{repo_relative_from_bin}" && pwd -P)

export {home_var_name}="${{repo_root}}/compiler"

exec "${{script_dir}}/{native_name}" "$@"
"""


def render_repo_native_cmd_wrapper(
    *,
    repo_relative_from_bin: str,
    home_var_name: str,
    native_name: str,
) -> str:
    """Return the repo-relative Windows native wrapper."""

    bat_rel = repo_relative_from_bin.replace("/", "\\")
    return f"""@echo off
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\\{bat_rel}") do set "REPO_ROOT=%%~fI"
set "{home_var_name}=%REPO_ROOT%\\compiler"
"%SCRIPT_DIR%\\{native_name}" %*
"""


def render_repo_env_script(
    *,
    repo_relative_from_bin: str,
    build_relative_from_repo: str,
    env_script_name: str,
    env_script_label: str,
    home_var_name: str,
    compiler_env_var: str,
) -> str:
    """Return the repo-relative sourceable environment script."""

    return f"""#!/usr/bin/env bash
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

script_src="${{BASH_SOURCE[0]-}}"
if [[ -z "${{script_src}}" && -n "${{ZSH_VERSION-}}" ]]; then
    script_src="${{(%):-%x}}"
    if [[ -z "${{script_src}}" ]]; then
        script_src="${{(%):-%N}}"
    fi
fi

sourced=0
if [[ -n "${{BASH_VERSION-}}" && "${{BASH_SOURCE[0]-}}" != "${{0}}" ]]; then
    sourced=1
fi
if [[ "${{sourced}}" -eq 0 && -n "${{ZSH_VERSION-}}" && "${{ZSH_EVAL_CONTEXT-}}" == *:file ]]; then
    sourced=1
fi

source_hint="<repo-root>/{build_relative_from_repo}/bin/{env_script_name}"
if [[ -n "${{script_src}}" ]]; then
    script_dir_hint="$(cd -- "$(dirname -- "${{script_src}}")" && pwd -P 2>/dev/null || true)"
    if [[ -n "${{script_dir_hint}}" ]]; then
        source_hint="${{script_dir_hint}}/{env_script_name}"
    fi
fi

if [[ -z "${{script_src}}" || "${{sourced}}" -eq 0 ]]; then
    echo "This script must be sourced: source ${{source_hint}}" >&2
    return 1 2>/dev/null || exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${{script_src}}")" && pwd -P)"
REPO_ROOT="$(cd -- "${{SCRIPT_DIR}}/{repo_relative_from_bin}" && pwd -P)"
MONOREPO_ROOT="$(cd -- "${{REPO_ROOT}}/.." && pwd -P)"
export {home_var_name}="${{REPO_ROOT}}/compiler"

if [[ -f "${{MONOREPO_ROOT}}/.venv/bin/activate" ]]; then
    # shellcheck source=/dev/null
    . "${{MONOREPO_ROOT}}/.venv/bin/activate"
fi

case ":${{PATH}}:" in
    *":${{SCRIPT_DIR}}:"*) ;;
    *) export PATH="${{SCRIPT_DIR}}${{PATH:+:${{PATH}}}}" ;;
esac

hash -r 2>/dev/null || true

# To pin down a specific C compiler, set the {compiler_env_var} environment variable here. For example:
#export {compiler_env_var}="clang"
"""


def render_repo_env_cmd_script(
    *,
    repo_relative_from_bin: str,
    env_script_label: str,
    home_var_name: str,
) -> str:
    """Return the repo-relative Windows activation script."""

    bat_rel = repo_relative_from_bin.replace("/", "\\")
    probe = _MSYS2_TOOLCHAIN_PROBE_CMD.format(env_script_label=env_script_label)
    return f"""@echo off
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\\{bat_rel}") do set "REPO_ROOT=%%~fI"
set "{home_var_name}=%REPO_ROOT%\\compiler"
set "PATH_PADDED=;%PATH%;"
if /I "%PATH_PADDED%"=="%PATH_PADDED:;%SCRIPT_DIR%;=%" (
    if defined PATH (
        set "PATH=%SCRIPT_DIR%;%PATH%"
    ) else (
        set "PATH=%SCRIPT_DIR%"
    )
)
set "PATH_PADDED="
{probe}"""


def render_prefix_native_wrapper(
    *,
    home_var_name: str,
    native_name: str,
) -> str:
    """Return the prefix-relative native wrapper."""

    return f"""#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
prefix_root=$(CDPATH= cd -- "${{script_dir}}/.." && pwd -P)

if [ -z "${{{home_var_name}:-}}" ]; then
    export {home_var_name}="${{prefix_root}}"
fi

exec "${{script_dir}}/{native_name}" "$@"
"""


def render_prefix_native_cmd_wrapper(
    *,
    home_var_name: str,
    native_name: str,
) -> str:
    """Return the prefix-relative Windows native wrapper."""

    return f"""@echo off
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\\..") do set "PREFIX_ROOT=%%~fI"
if "%{home_var_name}%"=="" set "{home_var_name}=%PREFIX_ROOT%"
"%SCRIPT_DIR%\\{native_name}" %*
"""


def render_prefix_env_script(
    *,
    env_script_name: str,
    home_var_name: str,
    compiler_env_var: str,
) -> str:
    """Return the prefix-relative sourceable environment script."""

    return f"""#!/usr/bin/env bash
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

script_src="${{BASH_SOURCE[0]-}}"
if [[ -z "${{script_src}}" && -n "${{ZSH_VERSION-}}" ]]; then
    script_src="${{(%):-%x}}"
    if [[ -z "${{script_src}}" ]]; then
        script_src="${{(%):-%N}}"
    fi
fi

SCRIPT_DIR=""
PREFIX_DIR=""
if [[ -n "${{script_src}}" ]]; then
    SCRIPT_DIR="$(cd -- "$(dirname -- "${{script_src}}")" && pwd -P)"
    PREFIX_DIR="$(cd -- "${{SCRIPT_DIR}}/.." && pwd -P)"
fi

sourced=0
if [[ -n "${{BASH_VERSION-}}" && "${{BASH_SOURCE[0]-}}" != "${{0}}" ]]; then
    sourced=1
fi
if [[ "${{sourced}}" -eq 0 && -n "${{ZSH_VERSION-}}" && "${{ZSH_EVAL_CONTEXT-}}" == *:file ]]; then
    sourced=1
fi

if [[ -z "${{script_src}}" || "${{sourced}}" -eq 0 ]]; then
    if [[ -n "${{SCRIPT_DIR}}" ]]; then
        echo "This script must be sourced: source ${{SCRIPT_DIR}}/{env_script_name}" >&2
    else
        echo "This script must be sourced: source <install-prefix>/bin/{env_script_name}" >&2
    fi
    return 1 2>/dev/null || exit 1
fi

export {home_var_name}="${{PREFIX_DIR}}"

case ":${{PATH}}:" in
    *":${{SCRIPT_DIR}}:"*) ;;
    *) export PATH="${{SCRIPT_DIR}}${{PATH:+:${{PATH}}}}" ;;
esac

hash -r 2>/dev/null || true

# To pin down a specific C compiler, set the {compiler_env_var} environment variable here. For example:
#export {compiler_env_var}="clang"
"""


def render_prefix_env_cmd_script(
    *,
    env_script_label: str,
    home_var_name: str,
) -> str:
    """Return the prefix-relative Windows activation script."""

    probe = _MSYS2_TOOLCHAIN_PROBE_CMD.format(env_script_label=env_script_label)
    return f"""@echo off
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\\..") do set "PREFIX_ROOT=%%~fI"
set "{home_var_name}=%PREFIX_ROOT%"
set "PATH_PADDED=;%PATH%;"
if /I "%PATH_PADDED%"=="%PATH_PADDED:;%SCRIPT_DIR%;=%" (
    if defined PATH (
        set "PATH=%SCRIPT_DIR%;%PATH%"
    ) else (
        set "PATH=%SCRIPT_DIR%"
    )
)
set "PATH_PADDED="
{probe}"""
