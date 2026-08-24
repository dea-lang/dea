#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""String escape utilities for the L0 compiler.

This module provides helpers for decoding L0 string literals (with escape
sequences preserved) into raw bytes, and encoding raw bytes into C-compatible
string literal bodies.
"""

from dataclasses import dataclass


_HEX_CHARS = "0123456789abcdefABCDEF"
_OCT_CHARS = "01234567"
_TRIGRAPH_THIRD_BYTES = frozenset(map(ord, "=/'()!<>-"))
_SIMPLE_ESCAPES = {
    "\\": ord("\\"),
    "'": ord("'"),
    '"': ord('"'),
    "?": ord("?"),
    "a": 0x07,
    "b": 0x08,
    "f": 0x0C,
    "n": 0x0A,
    "r": 0x0D,
    "t": 0x09,
    "v": 0x0B,
}


@dataclass(frozen=True)
class EscapeDecodeError(ValueError):
    """Raised when an invalid escape sequence is encountered during decoding.

    Attributes:
        code: Error code identifying the kind of failure.
        details: Optional string providing more context.
    """
    code: str
    details: str = ""


def decode_l0_string_token(text: str) -> bytes:
    """Decode an L0 string literal payload to raw bytes.

    Processes C-style escape sequences including hex, octal, and Unicode.

    Args:
        text: The string literal content (without surrounding quotes).

    Returns:
        The decoded bytes.

    Raises:
        EscapeDecodeError: If a malformed Unicode escape is encountered.
    """
    out = bytearray()
    i = 0

    while i < len(text):
        ch = text[i]
        if ch != "\\":
            out.extend(ch.encode("utf-8"))
            i += 1
            continue

        i += 1
        if i >= len(text):
            out.append(ord("\\"))
            break

        esc = text[i]

        if esc in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[esc])
            i += 1
            continue

        if esc == "x":
            i += 1
            start = i
            while i < len(text) and text[i] in _HEX_CHARS:
                i += 1
            hex_digits = text[start:i]
            if not hex_digits:
                out.extend(b"x") # would have been rejected by the lexer, but be lenient here and preserve the 'x' as-is
                continue
            out.append(int(hex_digits, 16) & 0xFF)
            continue

        if esc == "u":
            digits = text[i + 1:i + 5]
            if len(digits) != 4 or any(c not in _HEX_CHARS for c in digits):
                raise EscapeDecodeError("invalid_unicode_escape", "\\u")
            value = int(digits, 16)
            if value > 0x10FFFF:
                raise EscapeDecodeError("unicode_out_of_range", "\\u")
            out.extend(chr(value).encode("utf-8"))
            i += 5
            continue

        if esc == "U":
            digits = text[i + 1:i + 9]
            if len(digits) != 8 or any(c not in _HEX_CHARS for c in digits):
                raise EscapeDecodeError("invalid_unicode_escape", "\\U")
            value = int(digits, 16)
            if value > 0x10FFFF:
                raise EscapeDecodeError("unicode_out_of_range", "\\U")
            out.extend(chr(value).encode("utf-8"))
            i += 9
            continue

        if esc in _OCT_CHARS:
            start = i
            i += 1
            while i < len(text) and text[i] in _OCT_CHARS and i - start < 3:
                i += 1
            oct_digits = text[start:i]
            out.append(int(oct_digits, 8) & 0xFF)
            continue

        # Unknown escapes: be lenient and preserve as-is
        out.extend(esc.encode("utf-8"))
        i += 1

    return bytes(out)


def encode_c_string_bytes(data: bytes) -> str:
    """Encode raw bytes into a C-safe string literal body.

    Uses standard escapes for common control characters and fixed-width octal
    escapes for other non-printable bytes to avoid ambiguity in C.

    Args:
        data: The raw bytes to encode.

    Returns:
        A string containing the encoded C literal content (without quotes).
    """
    parts: list[str] = []
    for index, b in enumerate(data):
        if (
            b == ord("?")
            and index > 0
            and index + 1 < len(data)
            and data[index - 1] == ord("?")
            and data[index + 1] in _TRIGRAPH_THIRD_BYTES
        ):
            parts.append("\\?")
            continue
        if b == 0x5C:  # backslash
            parts.append("\\\\")
        elif b == 0x22:  # quote
            parts.append('\\"')
        elif b == 0x0A:
            parts.append("\\n")
        elif b == 0x09:
            parts.append("\\t")
        elif b == 0x0D:
            parts.append("\\r")
        elif b == 0x08:
            parts.append("\\b")
        elif b == 0x0C:
            parts.append("\\f")
        elif b == 0x0B:
            parts.append("\\v")
        elif 0x20 <= b <= 0x7E:
            parts.append(chr(b))
        else:
            # Use fixed-width octal escape to avoid \x run-on in C string literals.
            parts.append(f"\\{b:03o}")
    return "".join(parts)
