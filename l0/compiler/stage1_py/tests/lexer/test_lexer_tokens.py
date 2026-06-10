#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from conftest import has_error_code
from l0_lexer import Lexer, TokenKind


def test_lexer_tokens_include_literals_and_operators():
    src = """
    module main;

    func main() -> int {
        let a: int = 1 + 2 * 3 - 4 / 2 % 3;
        let b: bool = true && false || !false;
        let c: byte = 'z';
        let d: string = "hi";
        if (a <= 3 || a >= 1) { return 1; }
        if (a == 2 || a != 0) { return 2; }
        return a;
    }
    """
    tokens = Lexer.from_source(src).tokenize()
    kinds = {t.kind for t in tokens}

    assert TokenKind.INT in kinds
    assert TokenKind.BYTE in kinds
    assert TokenKind.STRING in kinds
    assert TokenKind.TRUE in kinds
    assert TokenKind.FALSE in kinds
    assert TokenKind.PLUS in kinds
    assert TokenKind.MINUS in kinds
    assert TokenKind.STAR in kinds
    assert TokenKind.SLASH in kinds
    assert TokenKind.MODULO in kinds
    assert TokenKind.LE in kinds
    assert TokenKind.GE in kinds
    assert TokenKind.EQEQ in kinds
    assert TokenKind.NE in kinds
    assert TokenKind.ANDAND in kinds
    assert TokenKind.OROR in kinds
    assert TokenKind.BANG in kinds


def test_lexer_reserved_bitwise_operator_tokens():
    src = "& | ^ ~ << >>"
    tokens = Lexer.from_source(src).tokenize()
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]

    assert kinds == [
        TokenKind.AMP,
        TokenKind.PIPE,
        TokenKind.CARET,
        TokenKind.TILDE,
        TokenKind.LSHIFT,
        TokenKind.RSHIFT,
    ]


def test_lexer_amp_vs_andand():
    tokens = Lexer.from_source("& &&").tokenize()
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.AMP, TokenKind.ANDAND]


def test_lexer_pipe_vs_oror():
    tokens = Lexer.from_source("| ||").tokenize()
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.PIPE, TokenKind.OROR]


def test_lexer_lshift_vs_lt():
    tokens = Lexer.from_source("<< < <=").tokenize()
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.LSHIFT, TokenKind.LT, TokenKind.LE]


def test_lexer_rshift_vs_gt():
    tokens = Lexer.from_source(">> > >=").tokenize()
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.RSHIFT, TokenKind.GT, TokenKind.GE]


def test_lexer_minus_context_sensitive():
    """Minus is absorbed into INT only when it cannot be binary."""
    cases = [
        # (source, expected_token_kinds)
        ("x-1",   [TokenKind.IDENT, TokenKind.MINUS, TokenKind.INT]),
        ("1-1",   [TokenKind.INT, TokenKind.MINUS, TokenKind.INT]),
        ("-1",    [TokenKind.INT]),
        ("(-1)",  [TokenKind.LPAREN, TokenKind.INT, TokenKind.RPAREN]),
        ("f(-1)", [TokenKind.IDENT, TokenKind.LPAREN, TokenKind.INT, TokenKind.RPAREN]),
        ("3+-1",  [TokenKind.INT, TokenKind.PLUS, TokenKind.INT]),
        ("x - 1", [TokenKind.IDENT, TokenKind.MINUS, TokenKind.INT]),
    ]
    for src, expected in cases:
        tokens = Lexer.from_source(src).tokenize()
        kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
        assert kinds == expected, f"Failed for {src!r}: got {kinds}"


def test_lexer_negative_int_token_text():
    """Absorbed negative INT tokens have minus in text."""
    tokens = Lexer.from_source("-42").tokenize()
    assert tokens[0].kind == TokenKind.INT
    assert tokens[0].text == "-42"


@pytest.mark.parametrize(
    ("src", "code"),
    [
        ("\"unterminated", "LEX-0010"),
        ("'\\u0100'", "LEX-0030"),
        ("\"\\xGG\"", "LEX-0050"),
        ("@", "LEX-0040"),
    ],
)

def test_lexer_invalid_literals_and_tokens(analyze_single, src, code):
    result = analyze_single("main", src)
    assert result.has_errors()
    assert has_error_code(result.diagnostics, code)


def test_lexer_error_token_carries_deferred_diagnostic():
    lexer = Lexer.from_source("⚽⚽ x")
    tokens = lexer.tokenize()
    # The lexer defers the diagnostic into the token instead of emitting it.
    assert lexer.diagnostics == []
    assert tokens[0].kind == TokenKind.LEXER_ERROR
    assert tokens[0].text == "⚽⚽"
    diag = tokens[0].diagnostic
    assert diag is not None
    assert diag.message == "[LEX-0040] invalid character in source"
    assert (diag.line, diag.column, diag.end_line, diag.end_column) == (1, 1, 1, 3)
    assert tokens[1].kind == TokenKind.IDENT
