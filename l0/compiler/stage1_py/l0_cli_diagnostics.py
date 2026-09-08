#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Diagnostic presentation and source snippets for compiler commands."""

import sys
from l0_analysis import AnalysisResult
from l0_diagnostics import Diagnostic
from l0_driver import SourceEncodingError, load_source_utf8


def _load_file_lines(path: str, cache: dict[str, list[str]]) -> list[str]:
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


def _emit_diagnostic(message: str) -> None:
    """Write one normative compiler diagnostic line to standard error.

    Args:
        message: Diagnostic text without a trailing newline.
    """
    print(message, file=sys.stderr)


def print_diagnostics(result: AnalysisResult) -> None:
    """Print diagnostics from the analysis result.

    Args:
        result: The analysis result containing diagnostics.
    """
    print_diagnostic_list(result.diagnostics)


def print_diagnostic_list(diagnostics: list[Diagnostic]) -> None:
    """Print a list of diagnostics, using a file cache for source snippets.

    Args:
        diagnostics: List of diagnostics to print.
    """
    file_cache: dict[str, list[str]] = {}

    for diag in diagnostics:
        print_diagnostic_with_snippet(diag, file_cache)


def print_diagnostic_with_snippet(
    diag: Diagnostic, file_cache: dict[str, list[str]]
) -> None:
    """Print a single diagnostic, including the source line and a caret.

    Args:
        diag: The diagnostic to print.
        file_cache: Cache of file lines keyed by path.
    """
    # First line: header
    _emit_diagnostic(diag.format())

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

    _emit_diagnostic(gutter + src_line)

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
    _emit_diagnostic(caret_prefix + carets)
