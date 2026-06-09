#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Lexer implementation for the L0 compiler.

This module provides the Lexer class for tokenizing L0 source code,
along with Token definitions and related utilities.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
from l0_diagnostics import Diagnostic


# ==========================
# Tokens and lexer
# ==========================

class TokenKind(Enum):
    """Enumeration of all supported token types in L0.

    Attributes:
        EOF: End of file marker.
        IDENT: Identifier (e.g., variable or function name).
        UNDERSCORE: Wildcard identifier ('_').
        INT: Integer literal.
        BYTE: Byte/character literal.
        STRING: String literal.
        MODULE: 'module' keyword.
        IMPORT: 'import' keyword.
        FUNC: 'func' keyword.
        STRUCT: 'struct' keyword.
        ENUM: 'enum' keyword.
        TYPE: 'type' keyword.
        EXTERN: 'extern' keyword.
        LET: 'let' keyword.
        RETURN: 'return' keyword.
        MATCH: 'match' keyword.
        CASE: 'case' keyword.
        IF: 'if' keyword.
        ELSE: 'else' keyword.
        WHILE: 'while' keyword.
        FOR: 'for' keyword.
        BREAK: 'break' keyword.
        CONTINUE: 'continue' keyword.
        TRUE: 'true' keyword.
        FALSE: 'false' keyword.
        NULL: 'null' keyword.
        AS: 'as' keyword.
        NEW: 'new' keyword.
        DROP: 'drop' keyword.
        WITH: 'with' keyword.
        CLEANUP: 'cleanup' keyword.
        LBRACE: '{'
        RBRACE: '}'
        LPAREN: '('
        RPAREN: ')'
        LBRACKET: '['
        RBRACKET: ']'
        COMMA: ','
        SEMI: ';'
        COLON: ':'
        DOUBLE_COLON: '::'
        ARROW_FUNC: '->'
        ARROW_MATCH: '=>'
        EQ: '='
        PLUS: '+'
        MINUS: '-'
        STAR: '*'
        SLASH: '/'
        MODULO: '%'
        LT: '<'
        GT: '>'
        LE: '<='
        GE: '>='
        EQEQ: '=='
        NE: '!='
        ANDAND: '&&'
        OROR: '||'
        BANG: '!'
        QUESTION: '?'
        DOT: '.'
        AMP: '&' (reserved)
        PIPE: '|' (reserved)
        CARET: '^' (reserved)
        TILDE: '~' (reserved)
        LSHIFT: '<<' (reserved)
        RSHIFT: '>>' (reserved)
        FUTURE_EXTENSION: Placeholder for future tokens.
    """
    # Special
    EOF = auto()

    IDENT = auto()
    UNDERSCORE = auto()
    INT = auto()
    BYTE = auto()
    STRING = auto()

    # Keywords
    MODULE = auto()
    IMPORT = auto()
    FUNC = auto()
    STRUCT = auto()
    ENUM = auto()
    TYPE = auto()
    EXTERN = auto()
    LET = auto()
    RETURN = auto()
    MATCH = auto()
    CASE = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    BREAK = auto()
    CONTINUE = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    AS = auto()

    NEW = auto()
    DROP = auto()
    WITH = auto()
    CLEANUP = auto()

    # Punctuation / operators
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMI = auto()
    COLON = auto()
    DOUBLE_COLON = auto()
    ARROW_FUNC = auto()
    ARROW_MATCH = auto()
    EQ = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    MODULO = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    EQEQ = auto()
    NE = auto()
    ANDAND = auto()
    OROR = auto()
    BANG = auto()
    QUESTION = auto()
    DOT = auto()

    # Reserved operators (not yet supported, lexed for diagnostics)
    AMP = auto()
    PIPE = auto()
    CARET = auto()
    TILDE = auto()
    LSHIFT = auto()
    RSHIFT = auto()

    FUTURE_EXTENSION = auto()


KEYWORDS = {
    "module": TokenKind.MODULE,
    "import": TokenKind.IMPORT,
    "func": TokenKind.FUNC,
    "struct": TokenKind.STRUCT,
    "enum": TokenKind.ENUM,
    "type": TokenKind.TYPE,
    "extern": TokenKind.EXTERN,
    "let": TokenKind.LET,
    "return": TokenKind.RETURN,
    "match": TokenKind.MATCH,
    "case": TokenKind.CASE,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "for": TokenKind.FOR,
    "break": TokenKind.BREAK,
    "continue": TokenKind.CONTINUE,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "null": TokenKind.NULL,
    "as": TokenKind.AS,
    "new": TokenKind.NEW,
    "drop": TokenKind.DROP,
    "with": TokenKind.WITH,
    "cleanup": TokenKind.CLEANUP,
    "void": TokenKind.IDENT,
    "bool": TokenKind.IDENT,
    "string": TokenKind.IDENT,
    "int": TokenKind.IDENT,
    "byte": TokenKind.IDENT,
    "tiny": TokenKind.FUTURE_EXTENSION,
    "short": TokenKind.FUTURE_EXTENSION,
    "long": TokenKind.FUTURE_EXTENSION,
    "ushort": TokenKind.FUTURE_EXTENSION,
    "uint": TokenKind.FUTURE_EXTENSION,
    "ulong": TokenKind.FUTURE_EXTENSION,
    "float": TokenKind.FUTURE_EXTENSION,
    "double": TokenKind.FUTURE_EXTENSION,
    "__dea__future__keyword__": TokenKind.FUTURE_EXTENSION,
    "in": TokenKind.FUTURE_EXTENSION,
    "const": TokenKind.FUTURE_EXTENSION,
}


@dataclass
class Token:
    """A single token produced by the lexer.

    Attributes:
        kind: The kind of token.
        text: The literal text of the token.
        line: 1-based line number in source.
        column: 1-based column number in source.
    """
    kind: TokenKind
    text: str
    line: int
    column: int

    def __repr__(self) -> str:
        """Returns a string representation of the token."""
        return f"{self.text!r}" if self.kind != TokenKind.EOF else "end-of-file"


def is_reserved_keyword(word: str) -> bool:
    """Check if a word is a reserved L0 keyword.

    Args:
        word: The word to check.

    Returns:
        True if the word is a keyword, False otherwise.
    """
    return word in KEYWORDS


# Tokens that can end an expression — minus after these is binary, not unary.
_EXPR_ENDING_TOKENS = frozenset({
    TokenKind.IDENT,
    TokenKind.INT,
    TokenKind.BYTE,
    TokenKind.STRING,
    TokenKind.TRUE,
    TokenKind.FALSE,
    TokenKind.NULL,
    TokenKind.RPAREN,
    TokenKind.RBRACKET,
})

# Constants for escape sequence validation
OCT_CHARS = "01234567"
HEX_CHARS = "0123456789abcdefABCDEF"


class Lexer:
    """Tokenizes L0 source code.

    This lexer scans source text and produces a list of Token objects.
    It tracks line and column information for diagnostics.

    Attributes:
        source: The source code string.
        filename: Name of the file being tokenized.
        diagnostics: List of collected diagnostics.
    """

    def __init__(self, source: str, filename: str = "<input>", diagnostics: Optional[List[Diagnostic]] = None) -> None:
        """Initialize the lexer.

        Args:
            source: The source code text.
            filename: The source filename for diagnostics.
            diagnostics: Optional list to collect diagnostics into.
        """
        self.source = source
        self.filename = filename
        self.length = len(source)
        self.index = 0
        self.line = 1
        self.column = 1
        self._prev_kind: TokenKind | None = None
        self.diagnostics = diagnostics if diagnostics is not None else []

    @classmethod
    def from_source(cls, source: str) -> "Lexer":
        """Create a lexer from a source string with default settings.

        Args:
            source: The source code text.

        Returns:
            A new Lexer instance.
        """
        return cls(source)

    # --- low-level char utilities ---

    def _error(self, message: str, line: int, column: int) -> None:
        """Add an error diagnostic."""
        self.diagnostics.append(Diagnostic(kind="error", message=message, filename=self.filename, line=line, column=column))

    def _at_end(self) -> bool:
        """Check if all input has been scanned."""
        return self.index >= self.length

    def _peek(self) -> str:
        """Peek at the current character without advancing."""
        if self._at_end():
            return "\0"
        return self.source[self.index]

    def _peek_next(self) -> str:
        """Peek at the next character without advancing."""
        if self.index + 1 >= self.length:
            return "\0"
        return self.source[self.index + 1]

    def _advance(self) -> str:
        """Advance the current index and return the character."""
        c = self._peek()
        if not self._at_end():
            self.index += 1
            if c == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
        return c

    # --- main API ---

    def tokenize(self) -> List[Token]:
        """Perform tokenization of the source string.

        Returns:
            A list of all tokens, ending with an EOF token.
        """
        tokens: List[Token] = []
        while True:
            tok = self._next_token()
            tokens.append(tok)
            self._prev_kind = tok.kind
            if tok.kind is TokenKind.EOF:
                break

        return tokens

    def _next_token(self) -> Token:
        """Scan and return the next token."""
        while True:
            self._skip_ws_and_comments()
            start_line, start_col = self.line, self.column

            if self._at_end():
                return Token(TokenKind.EOF, "", start_line, start_col)

            c = self._advance()

            # identifiers / keywords and underscore wildcard
            if c.isalpha() or c == "_":
                ident = [c]
                while self._peek().isalnum() or self._peek() == "_":
                    ident.append(self._advance())
                text = "".join(ident)
                if text == "_":
                    kind = TokenKind.UNDERSCORE
                else:
                    kind = KEYWORDS.get(text, TokenKind.IDENT)
                return Token(kind, text, start_line, start_col)

            # numbers (only integers for now)
            if c.isdigit():
                text = self._read_number(c, start_col, start_line)
                return Token(TokenKind.INT, text, start_line, start_col)

            # strings
            if c == '"':
                text = self._read_string_literal()
                return Token(TokenKind.STRING, text, start_line, start_col)

            # byte / char literals
            if c == "'":
                text = self._read_byte_literal(start_col, start_line)
                return Token(TokenKind.BYTE, text, start_line, start_col)

            # punctuation / operators with lookahead

            if c == "-":
                if self._peek() == ">":
                    self._advance()
                    return Token(TokenKind.ARROW_FUNC, "->", start_line, start_col)
                elif self._peek().isdigit() and self._prev_kind not in _EXPR_ENDING_TOKENS:
                    text = self._read_number(self._advance(), start_col, start_line, is_negative=True)
                    return Token(TokenKind.INT, text, start_line, start_col)
                return Token(TokenKind.MINUS, c, start_line, start_col)

            if c == "(":
                return Token(TokenKind.LPAREN, c, start_line, start_col)
            if c == ")":
                return Token(TokenKind.RPAREN, c, start_line, start_col)
            if c == "{":
                return Token(TokenKind.LBRACE, c, start_line, start_col)
            if c == "}":
                return Token(TokenKind.RBRACE, c, start_line, start_col)
            if c == "[":
                return Token(TokenKind.LBRACKET, c, start_line, start_col)
            if c == "]":
                return Token(TokenKind.RBRACKET, c, start_line, start_col)
            if c == ",":
                return Token(TokenKind.COMMA, c, start_line, start_col)
            if c == ";":
                return Token(TokenKind.SEMI, c, start_line, start_col)
            if c == ":":
                if self._peek() == ":":
                    self._advance()
                    return Token(TokenKind.DOUBLE_COLON, "::", start_line, start_col)
                return Token(TokenKind.COLON, c, start_line, start_col)
            if c == ".":
                return Token(TokenKind.DOT, c, start_line, start_col)
            if c == "?":
                return Token(TokenKind.QUESTION, c, start_line, start_col)

            if c == "=":
                nxt = self._peek()
                if nxt == ">":
                    self._advance()
                    return Token(TokenKind.ARROW_MATCH, "=>", start_line, start_col)
                if nxt == "=":
                    self._advance()
                    return Token(TokenKind.EQEQ, "==", start_line, start_col)
                return Token(TokenKind.EQ, c, start_line, start_col)

            if c == "!":
                if self._peek() == "=":
                    self._advance()
                    return Token(TokenKind.NE, "!=", start_line, start_col)
                return Token(TokenKind.BANG, c, start_line, start_col)

            if c == "<":
                if self._peek() == "=":
                    self._advance()
                    return Token(TokenKind.LE, "<=", start_line, start_col)
                if self._peek() == "<":
                    self._advance()
                    return Token(TokenKind.LSHIFT, "<<", start_line, start_col)
                return Token(TokenKind.LT, c, start_line, start_col)

            if c == ">":
                if self._peek() == "=":
                    self._advance()
                    return Token(TokenKind.GE, ">=", start_line, start_col)
                if self._peek() == ">":
                    self._advance()
                    return Token(TokenKind.RSHIFT, ">>", start_line, start_col)
                return Token(TokenKind.GT, c, start_line, start_col)

            if c == "&":
                if self._peek() == "&":
                    self._advance()
                    return Token(TokenKind.ANDAND, "&&", start_line, start_col)
                return Token(TokenKind.AMP, c, start_line, start_col)

            if c == "|":
                if self._peek() == "|":
                    self._advance()
                    return Token(TokenKind.OROR, "||", start_line, start_col)
                return Token(TokenKind.PIPE, c, start_line, start_col)

            if c == "^":
                return Token(TokenKind.CARET, c, start_line, start_col)
            if c == "~":
                return Token(TokenKind.TILDE, c, start_line, start_col)

            if c == "+":
                return Token(TokenKind.PLUS, c, start_line, start_col)
            if c == "*":
                return Token(TokenKind.STAR, c, start_line, start_col)
            if c == "/":
                return Token(TokenKind.SLASH, c, start_line, start_col)
            if c == "%":
                return Token(TokenKind.MODULO, c, start_line, start_col)

            self._error(f"[LEX-0040] invalid character in source", start_line, start_col)
            self._skip_invalid_characters()
            continue

    def _read_byte_literal(self, start_col: int, start_line: int) -> str:
        """Scan a byte/character literal."""
        chars: List[str] = []
        ch = self._peek()

        if ch == "\0" or ch == "\n":
            self._error("[LEX-0020] unterminated char literal", self.line, self.column)
            return "\0"

        if ch == "\\":
            chars.append(self._read_valid_char_escape())
        else:
            chars.append(self._advance())

        if self._peek() != "'":
            self._error("[LEX-0021] invalid char literal, expected closing single quote", self.line, self.column)
        else:
            self._advance()  # consume closing '

        text = "".join(chars)

        # validate that the char literal **represents a single byte**
        if text.startswith("\\x"):
            # Hex escape: \xH+ (variable length, C rules)
            hex_digits = text[2:]
            value = int(hex_digits, 16)

            if value > 255:
                self._error(
                    f"[LEX-0031] character literal hex escape out of range (0-255): '\\x{hex_digits}' = {value}",
                    start_line, start_col
                )
        elif text.startswith("\\") and len(text) > 1 and text[1] in OCT_CHARS:
            # octal escape (range was checked during escape parsing)
            pass
        else:
            utf8string = text.encode("utf-8").decode("unicode_escape").encode("utf-8")
            if len(utf8string) != 1:
                self._error("[LEX-0030] character literal must represent a single byte", start_line,
                                 start_col)

            # if text is a \u or \U escape, convert it to the \xXX form to be C99-compatible
            if text.startswith("\\u") or text.startswith("\\U"):
                byte_value = utf8string[0]
                text = f"\\x{byte_value:02x}"
        return text

    def _read_string_literal(self) -> str:
        """Scan a double-quoted string literal."""
        chars: List[str] = []
        while True:
            ch = self._peek()

            if ch == "\0" or ch == "\n":
                self._error("[LEX-0010] unterminated string literal", self.line, self.column)
                break
            if ch == "\\":
                chars.append(self._read_valid_char_escape())
                continue
            if ch == '"':
                self._advance()
                break

            chars.append(self._advance())

        text = "".join(chars)
        return text

    def _read_valid_char_escape(self) -> str:
        """Scan a single escape sequence."""
        chars: List[str] = [self._advance()]
        esc = self._peek()
        if esc in ("\\", "'", '"', "?", "a", "b", "f", "n", "r", "t", "v"):
            chars.append(self._advance())  # valid escapes

        elif esc == "x":  # hex escape of the form \xX+
            chars.append(self._advance())  # append 'x'
            next_ch = self._peek()  # expect at least one hex digit
            if next_ch in HEX_CHARS:
                chars.append(self._advance())
            else:
                self._error(f"[LEX-0050] invalid hex escape sequence", self.line, self.column)
                return "".join(chars)
            while True:  # consume additional hex digits
                next_ch = self._peek()
                if next_ch in HEX_CHARS:
                    chars.append(self._advance())
                else:
                    break

        elif esc == "u":  # unicode escape of the form \uXXXX
            chars.append(self._advance())  # append 'u'
            for _ in range(4):  # expect exactly four hex digits
                next_ch = self._peek()
                if next_ch in HEX_CHARS:
                    chars.append(self._advance())
                else:
                    self._error(f"[LEX-0051] invalid unicode escape sequence (\\u)", self.line, self.column)
                    return "".join(chars)

        elif esc == "U":  # unicode escape of the form \UXXXXXXXX
            chars.append(self._advance())  # append 'U'
            for _ in range(8):  # expect exactly eight hex digits
                next_ch = self._peek()
                if next_ch in HEX_CHARS:
                    chars.append(self._advance())
                else:
                    self._error(f"[LEX-0052] invalid unicode escape sequence (\\U)", self.line, self.column)
                    return "".join(chars)
            value = int("".join(chars[2:]), 16)
            if value > 0x10FFFF:
                self._error("[LEX-0054] Unicode code point out of range (must be <= 0x10FFFF)",
                                 self.line, self.column)

        elif esc in OCT_CHARS:  # octal escape
            chars.append(self._advance())  # append the first octal digit
            for _ in range(2):  # expect one to three octal digits total
                next_ch = self._peek()
                if next_ch in OCT_CHARS:
                    chars.append(self._advance())
                else:
                    break
            # check that the octal value is in range 0-255
            oct_value = int("".join(chars[1:]), 8)
            if oct_value > 255:
                self._error(f"[LEX-0053] octal escape sequence out of range 0..255", self.line, self.column)
        else:
            self._error(f"[LEX-0059] unknown escape sequence \\{esc}", self.line, self.column)

        return "".join(chars)

    def _read_number(self, c: str, start_col: int, start_line: int, is_negative: bool = False) -> str:
        """Scan an integer literal."""
        digits = [c]
        while self._peek().isdigit():
            digits.append(self._advance())
        text = "".join(digits)
        if is_negative:
            text = "-" + text
        if self._peek().isalpha() or self._peek() == "_":
            self._error(f"[LEX-0061] invalid character '{self._peek()}' after integer literal",
                             self.line, self.column)
        value = int(text)
        if value > 2 ** 31 - 1 or value < -2 ** 31:
            self._error(f"[LEX-0060] integer literal '{value}' exceeds 32-bit signed range",
                             start_line, start_col)
        return text

    def _skip_ws_and_comments(self) -> None:
        """Skip whitespace and both line and block comments."""
        while True:
            c = self._peek()
            if c in (" ", "\t", "\r", "\n"):
                self._advance()
                continue
            if c == "/" and self._peek_next() == "/":
                # line comment
                self._advance()  # '/'
                self._advance()  # second '/'
                while self._peek() not in ("\n", "\0"):
                    self._advance()
                continue
            if c == "/" and self._peek_next() == "*":
                # block comment
                self._advance()  # '/'
                self._advance()  # '*'
                while True:
                    if self._at_end():
                        self._error("[LEX-0070] unterminated block comment", self.line, self.column)
                        break
                    if self._peek() == "*" and self._peek_next() == "/":
                        self._advance()  # '*'
                        self._advance()  # '/'
                        break
                    self._advance()
                continue
            break

    def _skip_invalid_characters(self) :
        """Skip non-ASCII characters after LEX-0040."""
        while True:
            c = self._peek()
            if c == "\0" or (" " <= c <= "~"):
                break
            self._advance()