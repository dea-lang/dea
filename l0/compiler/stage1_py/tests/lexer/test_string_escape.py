#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

from l0_string_escape import decode_l0_string_token, encode_c_string_bytes


def test_decode_l0_string_token_simple_ascii():
    assert decode_l0_string_token("hello") == b"hello"


def test_decode_l0_string_token_common_escapes():
    assert decode_l0_string_token(r"Line1\nLine2\t\\\"") == b'Line1\nLine2\t\\"'


def test_decode_l0_string_token_hex_and_octal():
    assert decode_l0_string_token(r"\x41\101") == b"AA"


def test_decode_l0_string_token_unicode_to_utf8_bytes():
    assert decode_l0_string_token(r"\u20AC") == "€".encode("utf-8")


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
