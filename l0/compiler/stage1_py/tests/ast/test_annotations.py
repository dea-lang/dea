# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Verify deferred annotations still support AST introspection."""

from inspect import signature
from typing import get_type_hints

from l0_ast import Block, Expr, FuncDecl, ReturnStmt, WithItem, WithStmt
from l0_lexer import Token


def test_forward_annotations_resolve_after_module_initialization() -> None:
    assert get_type_hints(FuncDecl)["body"] is Block
    assert get_type_hints(ReturnStmt)["value"] == Expr | None
    assert get_type_hints(WithStmt)["items"] == list[WithItem]
    assert get_type_hints(Token)["recovery"] == Token | None


def test_backend_forward_annotations_support_signature_introspection() -> None:
    from l0_backend_lowering import Lowering

    for method in (Lowering._register_inline_with_cleanup, Lowering._emit_inline_with_header_item):
        assert signature(method).parameters["item"].annotation is WithItem
