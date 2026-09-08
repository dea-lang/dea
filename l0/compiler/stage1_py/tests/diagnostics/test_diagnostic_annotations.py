# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Keep diagnostic signatures inspectable across the lexer import cycle."""

from inspect import signature
from typing import get_type_hints

from l0_diagnostics import diag_from_token
from l0_lexer import Token


def test_token_annotation_can_be_inspected_without_a_runtime_lexer_import() -> None:
    assert signature(diag_from_token).parameters["token"].annotation == "Token | None"
    assert get_type_hints(diag_from_token, localns={"Token": Token})["token"] == Token | None
