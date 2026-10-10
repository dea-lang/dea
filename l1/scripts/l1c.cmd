@REM SPDX-License-Identifier: MIT OR Apache-2.0
@REM Copyright (c) 2026 gwz
@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "SELECTED_L1C=%L1C_WRAPPER%"
if not defined SELECTED_L1C set "SELECTED_L1C=%REPO_ROOT%\build\dea\bin\l1c.cmd"
if not exist "%SELECTED_L1C%" (
    echo missing repo-local l1c wrapper at %SELECTED_L1C%; run `make build` first 1>&2
    endlocal & exit /b 1
)

call "%SELECTED_L1C%" %*
set "EXITCODE=%ERRORLEVEL%"
endlocal & exit /b %EXITCODE%

