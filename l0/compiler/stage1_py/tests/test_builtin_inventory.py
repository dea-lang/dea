#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from l0_lexer import KEYWORDS, Lexer, TokenKind, is_reserved_keyword
from l0_parser import Parser
from l0_types import L0_PRIMITIVE_TYPES, get_builtin_type, is_builtin_type_name


@pytest.mark.parametrize("name", L0_PRIMITIVE_TYPES)
def test_builtin_inventory_drives_lexer_parser_and_semantic_factory(name):
    assert is_builtin_type_name(name)
    assert KEYWORDS[name] is TokenKind.IDENT
    assert is_reserved_keyword(name)

    parser = Parser(Lexer.from_source(name).tokenize())
    assert parser._is_builtin_type_name()
    assert get_builtin_type(name).name == name


@pytest.mark.parametrize("name", ["", "uint", "integer", "Bool"])
def test_builtin_inventory_rejects_non_builtin_names(name):
    assert not is_builtin_type_name(name)
    if name:
        parser = Parser(Lexer.from_source(name).tokenize())
        assert not parser._is_builtin_type_name()
    with pytest.raises(ValueError, match="unknown L0 builtin type"):
        get_builtin_type(name)
