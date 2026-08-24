#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from conftest import has_error_code


def _first_error(result):
    return next(d for d in result.diagnostics if d.kind == "error")


def _first_error_code(result, code: str):
    needle = f"[{code}]"
    return next(d for d in result.diagnostics if d.kind == "error" and needle in d.message)


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
    # The parser runs past the invalid characters and reports the missing
    # module header exactly once, without cascading errors.
    par_errors = [d for d in result.diagnostics if d.message.startswith("[PAR-")]
    assert len(par_errors) == 1
    assert has_error_code(result.diagnostics, "PAR-0310")
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
    assert result.cu is not None


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
    assert result.cu is not None


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

    diag = _first_error_code(result, "LEX-0010")
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


def test_lexer_invalid_run_reports_one_diagnostic_with_span(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;
        ⚽⚽⚽
        func main() -> int {
            return 0;
        }
        """,
    )
    assert result.has_errors()
    lex_errors = [d for d in result.diagnostics if d.kind == "error" and d.message.startswith("[LEX-0040]")]
    assert len(lex_errors) == 1
    diag = lex_errors[0]
    assert (diag.line, diag.column) == (3, 1)
    assert (diag.end_line, diag.end_column) == (3, 4)
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is not None


def test_parser_continues_past_lexer_error_to_later_errors(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = ⚽ 1;
            return x
        }
        """,
    )
    assert result.has_errors()
    assert has_error_code(result.diagnostics, "LEX-0040")
    # The missing semicolon after `return x` is still found after recovery.
    assert any(d.message.startswith("[PAR-") for d in result.diagnostics)


def test_lexer_error_not_duplicated_across_backtracking(analyze_single):
    # `x` followed by an invalid run exercises the qualified-name lookahead,
    # which backtracks across the LEXER_ERROR token.
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            let x: int = 1;
            return x ⚽⚽;
        }
        """,
    )
    assert result.has_errors()
    lex_errors = [d for d in result.diagnostics if d.kind == "error" and d.message.startswith("[LEX-0040]")]
    assert len(lex_errors) == 1
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is not None


def test_recovered_integer_preserves_binary_minus_in_parser(analyze_single):
    result = analyze_single(
        "main",
        """
        module main;

        func main() -> int {
            return 2147483648 -5;
        }
        """,
    )
    lex_errors = [
        d for d in result.diagnostics
        if d.kind == "error" and d.message.startswith("[LEX-0060]")
    ]
    assert len(lex_errors) == 1
    assert not any(d.message.startswith("[PAR-") for d in result.diagnostics)
    assert result.cu is not None


def test_lexer_unicode_string_keeps_following_columns(analyze_single):
    src_line = '    let s: string = "☕☕"; ⚽'
    result = analyze_single(
        "main",
        "module main;\n\nfunc main() -> int {\n" + src_line + "\n    return 0;\n}\n",
    )
    lex_errors = [d for d in result.diagnostics if d.kind == "error" and d.message.startswith("[LEX-0040]")]
    assert len(lex_errors) == 1
    # Columns count codepoints, so the multibyte string content does not
    # shift the position of the invalid character that follows it.
    assert (lex_errors[0].line, lex_errors[0].column) == (4, src_line.index("⚽") + 1)
