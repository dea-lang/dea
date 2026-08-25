#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import os
from typing import Dict, List

from l0_ast import Node
from l0_diagnostics import Diagnostic, diag_from_node, diag_from_token
from l0_parser import Parser, Span, Token, TokenKind
from l0c import print_diagnostic_with_snippet


# -------------------------
# diag_from_node / diag_from_token
# -------------------------


def test_diag_from_node_uses_span():
    node = Node(span=Span(start_line=3, start_column=5, end_line=3, end_column=10))

    diag = diag_from_node(
        kind="error",
        message="type mismatch",
        module_name="test.module",
        filename="test.l0",
        node=node,
    )

    assert diag.kind == "error"
    assert diag.message == "type mismatch"
    assert diag.module_name == "test.module"
    assert diag.filename == "test.l0"
    assert diag.line == 3
    assert diag.column == 5
    assert diag.end_line == 3
    assert diag.end_column == 10


def test_diag_from_node_handles_missing_span():
    node = Node(span=None)

    diag = diag_from_node(
        kind="error",
        message="oops",
        module_name="m",
        filename="f.l0",
        node=node,
    )

    assert diag.line is None
    assert diag.column is None
    assert diag.end_line is None
    assert diag.end_column is None


def test_diag_from_token_uses_token_position():
    tok = Token(TokenKind.IDENT, "foo", line=7, column=13)

    diag = diag_from_token(
        kind="error",
        message="unexpected identifier",
        module_name="test.m",
        filename="test.l0",
        token=tok,
    )

    assert diag.kind == "error"
    assert diag.message == "unexpected identifier"
    assert diag.module_name == "test.m"
    assert diag.filename == "test.l0"
    assert diag.line == 7
    assert diag.column == 13
    assert diag.end_line is None
    assert diag.end_column is None


def test_diag_from_token_handles_none():
    diag = diag_from_token(
        kind="warning",
        message="something odd",
        module_name=None,
        filename=None,
        token=None,
    )

    assert diag.line is None
    assert diag.column is None
    assert diag.end_line is None
    assert diag.end_column is None


# -------------------------
# Diagnostic.format()
# -------------------------


def test_diagnostic_format_no_location():
    diag = Diagnostic(kind="error", message="boom")

    assert diag.format() == "error: boom"


def test_diagnostic_format_with_file_and_position(tmp_path):
    filename = tmp_path / "mod.l0"
    diag = Diagnostic(
        kind="warning",
        message="unused variable",
        module_name="m",
        filename=str(filename),
        line=4,
        column=2,
    )

    s = diag.format()
    # Exact structure: mod.l0(m):4:2: warning: ...
    assert "mod.l0" in s
    assert "(m)" in s
    assert f"{os.path.basename(str(filename))}:4:2(m): warning: unused variable" in s


# -------------------------
# Snippet + caret printing
# -------------------------


def _capture_snippet(diag: Diagnostic, monkeypatch) -> List[str]:
    """
    Helper: run print_diagnostic_with_snippet and capture stderr as list of lines.
    """
    from io import StringIO
    import sys

    fake_err = StringIO()
    monkeypatch.setattr(sys, "stderr", fake_err)
    file_cache: Dict[str, List[str]] = {}
    print_diagnostic_with_snippet(diag, file_cache)
    return fake_err.getvalue().splitlines()


def test_snippet_no_location_prints_only_header(monkeypatch):
    diag = Diagnostic(kind="error", message="boom")

    lines = _capture_snippet(diag, monkeypatch)

    assert lines == ["error: boom"]


def test_snippet_point_caret_single_line(tmp_path, monkeypatch):
    src = "abcdef\nsecond line\n"
    path = tmp_path / "snippet.l0"
    path.write_text(src, encoding="utf-8")

    diag = Diagnostic(
        kind="error",
        message="here",
        filename=str(path),
        line=1,
        column=3,  # under 'c'
    )

    lines = _capture_snippet(diag, monkeypatch)
    assert lines == [
        diag.format(),
        "    1 | abcdef",
        "      |   ^",
    ]


def test_snippet_span_same_line(tmp_path, monkeypatch):
    src = "0123456789\n"
    path = tmp_path / "span.l0"
    path.write_text(src, encoding="utf-8")

    # Span from col 3 to col 7 (exclusive) → carets under '2','3','4','5'
    diag = Diagnostic(
        kind="error",
        message="bad span",
        filename=str(path),
        line=1,
        column=3,
        end_line=1,
        end_column=7,
    )

    lines = _capture_snippet(diag, monkeypatch)
    assert lines == [
        diag.format(),
        "    1 | 0123456789",
        "      |   ^^^^",
    ]


def test_parser_token_span_renders_full_else_keyword(tmp_path, monkeypatch):
    src = """module main;
func main() -> int {
    case (1) {
        else { return 0; }
        "a" => { return 1; }
        _ => 2;
        else 3;
    }
    printl_s("ok");
    return 0;
}
"""
    path = tmp_path / "case_else_span.l0"
    path.write_text(src, encoding="utf-8")

    parser = Parser.from_source(src)
    parser.parse_module(filename=str(path))
    stray_else_diag = next(
        diag for diag in parser.diagnostics
        if "[PAR-0123]" in diag.message and diag.line == 7
    )

    lines = _capture_snippet(stray_else_diag, monkeypatch)
    assert lines == [
        stray_else_diag.format(),
        "    7 |         else 3;",
        "      |         ^^^^",
    ]


def test_snippet_span_multiline_end_extends_to_eol(tmp_path, monkeypatch):
    src = "abcdef\nsecond line\n"
    path = tmp_path / "multi.l0"
    path.write_text(src, encoding="utf-8")

    # Span from col 2 on line 1 through line 2
    diag = Diagnostic(
        kind="error",
        message="multi",
        filename=str(path),
        line=1,
        column=2, # under 'b'
        end_line=2,
        end_column=1,
    )

    lines = _capture_snippet(diag, monkeypatch)
    assert lines == [
        diag.format(),
        "    1 | abcdef",
        "      |  ^^^^^",
    ]


def test_snippet_no_column_prints_no_carets(tmp_path, monkeypatch):
    src = "line only\n"
    path = tmp_path / "nocol.l0"
    path.write_text(src, encoding="utf-8")

    diag = Diagnostic(
        kind="warning",
        message="no column",
        filename=str(path),
        line=1,
        column=None,
    )

    lines = _capture_snippet(diag, monkeypatch)

    # Header + source line, but no caret line
    assert lines == [
        diag.format(),
        "    1 | line only",
    ]
