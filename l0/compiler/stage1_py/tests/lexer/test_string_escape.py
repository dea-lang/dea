#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from l0_lexer import Lexer, TokenKind
from l0_string_escape import EscapeDecodeError, decode_l0_string_token, encode_c_string_bytes


def test_decode_l0_string_token_simple_ascii():
    assert decode_l0_string_token("hello") == b"hello"


def test_decode_l0_string_token_common_escapes():
    assert decode_l0_string_token(r"Line1\nLine2\t\\\"") == b'Line1\nLine2\t\\"'


def test_decode_l0_string_token_hex_and_octal():
    assert decode_l0_string_token(r"\x41\101") == b"AA"


@pytest.mark.parametrize("spelling,expected", [
    (r"\u00E9", b"\xc3\xa9"),
    (r"\u20AC", b"\xe2\x82\xac"),
    (r"\uD7FF", b"\xed\x9f\xbf"),
    (r"\uE000", b"\xee\x80\x80"),
    (r"\U0001F600", b"\xf0\x9f\x98\x80"),
    (r"\U0010FFFF", b"\xf4\x8f\xbf\xbf"),
    (r"\\u00E9", b"\\u00E9"),
])
def test_decode_l0_string_token_unicode_to_utf8_bytes(spelling, expected):
    assert decode_l0_string_token(spelling) == expected


@pytest.mark.parametrize("spelling", [
    r"\uD800", r"\uDFFF", r"\U0000D800", r"\U0000DFFF", r"\U00110000", r"\UFFFFFFFF",
])
def test_invalid_scalar_in_lexer_and_decoder(spelling):
    for quote in ("'", '"'):
        token, eof = Lexer.from_source(f"\n  {quote}{spelling}{quote}").tokenize()
        assert eof.kind == TokenKind.EOF
        assert token.kind == TokenKind.LEXER_ERROR
        diagnostic, = token.diagnostics
        assert diagnostic.message.startswith("[LEX-0054]")
        assert (diagnostic.line, diagnostic.column) == (2, 4)

    with pytest.raises(EscapeDecodeError) as error:
        decode_l0_string_token(spelling)
    assert error.value.code == "unicode_out_of_range"


def test_encode_c_string_bytes_ascii_passthrough():
    assert encode_c_string_bytes(b"abcXYZ09") == "abcXYZ09"


def test_encode_c_string_bytes_escapes_controls_and_quotes():
    encoded = encode_c_string_bytes(b"a\n\t\\\"b")
    assert encoded == r"a\n\t\\\"b"


def test_encode_c_string_bytes_non_printable_to_octal():
    assert encode_c_string_bytes(bytes([0x00, 0x1F, 0x7F, 0xFF])) == r"\000\037\177\377"


def test_encode_c_string_bytes_escapes_every_trigraph_spelling():
    source = b"??=??/??'??(??)??!??<??>??-"
    assert encode_c_string_bytes(source) == r"?\?=?\?/?\?'?\?(?\?)?\?!?\?<?\?>?\?-"


def test_encode_c_string_bytes_preserves_question_mark_runs_and_controls():
    assert encode_c_string_bytes(b"? ?? ??? ????= ?!?=") == r"? ?? ??? ???\?= ?!?="
