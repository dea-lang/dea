#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from l0_lexer import Lexer, TokenKind


def deferred_messages(tokens):
    messages = []
    for token in tokens:
        diagnostics = token.diagnostics if token.diagnostics is not None else []
        if not diagnostics and token.diagnostic is not None:
            diagnostics = [token.diagnostic]
        messages.extend(d.message for d in diagnostics)
    return messages


def test_int_literal_above_32bit_range_raises():
    src = "2147483648"

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("exceeds 32-bit signed range" in message for message in deferred_messages(tokens))
    assert tokens[0].kind is TokenKind.LEXER_ERROR
    assert tokens[0].recovery is not None
    assert tokens[0].recovery.kind is TokenKind.INT


def test_int_literal_below_32bit_range_raises():
    src = "-2147483649"

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("exceeds 32-bit signed range" in message for message in deferred_messages(tokens))
    assert tokens[0].kind is TokenKind.LEXER_ERROR
    assert tokens[0].recovery is not None
    assert tokens[0].recovery.kind is TokenKind.INT


def test_common_tokenization_cases_and_comments():
    src = """// leading comment
let x: int = -42;
// trailing comment on its own line
/* block comment spanning
several
        lines */ x = x - 1;
_ => -> ==
"""
    tokens = Lexer.from_source(src).tokenize()
    kinds = [t.kind for t in tokens]
    texts = [t.text for t in tokens]

    assert kinds == [
        TokenKind.LET,
        TokenKind.IDENT,
        TokenKind.COLON,
        TokenKind.IDENT,
        TokenKind.EQ,
        TokenKind.INT,
        TokenKind.SEMI,
        TokenKind.IDENT,
        TokenKind.EQ,
        TokenKind.IDENT,
        TokenKind.MINUS,
        TokenKind.INT,
        TokenKind.SEMI,
        TokenKind.UNDERSCORE,
        TokenKind.ARROW_MATCH,
        TokenKind.ARROW_FUNC,
        TokenKind.EQEQ,
        TokenKind.EOF,
    ]

    assert "-42" in texts
    minus_index = texts.index("-")
    assert texts[minus_index + 1] == "1"


def test_string_literal_tokenized_without_escapes():
    src = "let s: string = \"abc 123\";"

    tokens = Lexer.from_source(src).tokenize()
    assert [t.kind for t in tokens][:5] == [
        TokenKind.LET,
        TokenKind.IDENT,
        TokenKind.COLON,
        TokenKind.IDENT,
        TokenKind.EQ,
    ]

    string_tok = tokens[5]
    assert string_tok.kind is TokenKind.STRING
    assert string_tok.text == "abc 123"
    assert (string_tok.line, string_tok.column) == (1, 17)


def test_unterminated_string_literal_raises_with_location():
    src = 'let msg = "unterminated\nnext line'

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    err = next(d for t in tokens for d in (t.diagnostics or []) if "unterminated" in d.message)
    assert err.line == 1
    assert err.column == 24
    assert tokens[3].kind is TokenKind.LEXER_ERROR
    assert tokens[3].recovery is not None
    assert tokens[3].recovery.kind is TokenKind.STRING


def test_line_and_column_increment_across_newlines_and_comments():
    src = "\n// comment on line 2\n    let x = 0;\n"

    tokens = Lexer.from_source(src).tokenize()
    let_tok = tokens[0]

    assert let_tok.kind is TokenKind.LET
    assert (let_tok.line, let_tok.column) == (3, 5)


# ============================================================================
# Escape sequence error tests
# ============================================================================


def test_lexer_invalid_hex_escape_non_hex():
    """Test that invalid hex escape sequence raises error."""
    src = '"\\xGG"'

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("invalid hex escape sequence" in message for message in deferred_messages(tokens))


def test_lexer_invalid_unicode_escape_incomplete():
    """Test that incomplete \\u escape raises error."""
    src = '"\\u12"'  # Only 2 hex digits, needs 4

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("invalid unicode escape sequence (\\u)" in message for message in deferred_messages(tokens))


def test_lexer_invalid_unicode_escape_long_incomplete():
    """Test that incomplete \\U escape raises error."""
    src = '"\\U1234567"'  # Only 7 hex digits, needs 8

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("invalid unicode escape sequence (\\U)" in message for message in deferred_messages(tokens))


def test_lexer_unknown_escape_sequence():
    """Test that unknown escape sequence raises error."""
    src = '"\\q"'

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("unknown escape sequence" in message for message in deferred_messages(tokens))


def test_lexer_octal_escape_out_of_range():
    """Test that octal escape > 255 raises error."""
    src = '"\\777"'  # 0o777 = 511 > 255

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert any("octal escape sequence out of range" in message for message in deferred_messages(tokens))


def test_lexer_unterminated_block_comment():
    """Test that unterminated block comment raises error."""
    src = "/* this comment never ends"

    lexer = Lexer.from_source(src)
    lexer.tokenize()

    assert any("unterminated block comment" in d.message for d in lexer.diagnostics)


def test_lexer_unexpected_character():
    """Test that an unexpected character yields a deferred lexer-error token."""
    src = "@"

    lexer = Lexer.from_source(src)
    tokens = lexer.tokenize()

    assert lexer.diagnostics == []
    assert tokens[0].kind is TokenKind.LEXER_ERROR
    assert tokens[0].diagnostic is not None
    assert "invalid character in source" in tokens[0].diagnostic.message
