#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code


def _first_error(result):
    return next(d for d in result.diagnostics if d.kind == "error")


def test_lexer_invalid_token_reports_span(analyze_single):
    result = analyze_single("main", "@")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0040")

    diag = _first_error(result)
    assert (diag.line, diag.column) == (1, 1)
    assert diag.message == "[LEX-0040] invalid character in source"

def test_lexer_invalid_token_recovery(analyze_single):
    result = analyze_single("main", "@ $ @")
    assert result.has_errors()
    lex_errors = [d for d in result.diagnostics if d.kind == "error" and d.message.startswith("[LEX-0040]")]
    assert len(lex_errors) == 3
    assert (lex_errors[0].line, lex_errors[0].column) == (1, 1)
    assert (lex_errors[1].line, lex_errors[1].column) == (1, 3)
    assert (lex_errors[2].line, lex_errors[2].column) == (1, 5)
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is None


def test_lexer_rejects_non_ascii_identifier_characters(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            let café: int = 1;
            return café;
        }
        """,
    )
    assert result.has_errors()
    lex_errors = [d for d in result.diagnostics if d.kind == "error" and d.message.startswith("[LEX-0040]")]
    assert len(lex_errors) == 2
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is None


def test_lexer_rejects_non_ascii_leading_identifier_characters(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            let éclair: int = 1;
            return 0;
        }
        """,
    )
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0040")
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is None


def test_lexer_rejects_non_ascii_module_name(analyze_single):
    result = analyze_single(
        "main",
        """
        module café;

        func main() -> int {
            return 0;
        }
        """,
    )
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0040")
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is None


def test_lexer_allows_unicode_comments_and_strings(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        // caffè Привет ☕
        func main() -> int {
            let msg: string = "caffè Привет ☕";
            return 0;
        }
        """,
    )
    assert not result.has_errors()
    assert result.cu is not None


def test_lexer_numeric_overflow_reports_span(analyze_single):
    result = analyze_single("main", "2147483648")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0060")

    diag = _first_error(result)
    assert (diag.line, diag.column) == (1, 1)


def test_lexer_unterminated_string_reports_span(analyze_single):
    src = 'let msg = "unterminated\nnext line'
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0010")

    diag = _first_error(result)
    assert (diag.line, diag.column) == (1, 24)


def test_lexer_unterminated_comment_reports_span(analyze_single):
    result = analyze_single("main", "/* comment")
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0070")

    diag = _first_error(result)
    assert (diag.line, diag.column) == (1, 11)


def test_lexer_invalid_escape_sequences(analyze_single):
    result = analyze_single("main", '"\\xGG"')
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0050")

    result = analyze_single("main", '"\\q"')
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0059")
