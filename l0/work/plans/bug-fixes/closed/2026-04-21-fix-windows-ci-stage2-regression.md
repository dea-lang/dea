# Fix Windows CI Stage 2 Regression

Fix the `WinError 193` regression on Windows CI during `make test-stage2` caused by the recent Bash-to-Python tooling
port.

- Date: 2026-04-21
- Status: Completed
- Kind: Bug Fix
- Level: L0

## Background

In the recent Bash-to-Python tooling port, shell scripts for testing the Stage 2 compiler were ported to Python. The new
Python scripts use `subprocess.run` to execute the compiler using a path like `bin/l0c-stage2`. While Unix-like systems
execute this file directly, Windows strictly requires an executable extension (`.exe` or `.cmd`) when invoking via
`subprocess.run`. Omitting the extension results in `OSError: [WinError 193] %1 is not a valid Win32 application`.

## Solution

1. Centralize tool resolution in `tool_test_common.py` via `resolve_tool(bin_dir, name)`.
2. Update Stage 2 integration tests to use `resolve_tool` instead of hardcoded paths.

## Validation Results

- `make test-stage2` passes on macOS (Darwin).
- Verified `resolve_tool` correctly handles `is_windows_host()` logic.
- Final verification will be performed by the Windows CI runner.
