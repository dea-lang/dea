# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for Python docstring normalization."""

from compiler.docgen.l0_docgen_python_filter import transform_python_for_doxygen


def test_transform_python_for_doxygen_preserves_modern_type_annotations() -> None:
    import ast

    source = '''
type SymbolKey = tuple[str, str]

def find(keys: list[SymbolKey]) -> SymbolKey | None:
    """Find the first key.

    Args:
        keys: Qualified symbol keys.

    Returns:
        The first key, if present.
    """
    match keys:
        case [first, *_]:
            return first
        case _:
            return None
'''
    transformed = transform_python_for_doxygen(source)
    tree = ast.parse(transformed)
    assert isinstance(tree.body[0], ast.TypeAlias)
    assert ast.unparse(tree.body[1].returns) == "SymbolKey | None"
    assert "# @param keys Qualified symbol keys." in transformed
    assert "# @return The first key, if present." in transformed


def test_transform_python_for_doxygen_rewrites_google_docstrings() -> None:
    source = '''
def add(x: int, y: int) -> int:
    """Add two integers.

    Args:
        x: First input value.
        y: Second input value.

    Returns:
        Sum of ``x`` and ``y``.
    """
    return x + y
'''

    transformed = transform_python_for_doxygen(source)

    assert "## Add two integers." in transformed
    assert "# @param x First input value." in transformed
    assert "# @param y Second input value." in transformed
    assert "# @return Sum of @c x and @c y." in transformed
    assert '"""Add two integers.' not in transformed


def test_transform_python_for_doxygen_renders_note_and_escapes_hash_text() -> None:
    source = '''
def emit_line() -> None:
    """Emit a `#line` directive.

    Note:
        - Keep `#line` escaped so Doxygen does not resolve it as a link.
        - Preserve list structure in the rendered docs.
    """
    return None
'''

    transformed = transform_python_for_doxygen(source)

    assert "## Emit a @c \\#line directive." in transformed
    assert "# @par Note" in transformed
    assert "# - Keep @c \\#line escaped so Doxygen does not resolve it as a link." in transformed
    assert "# - Preserve list structure in the rendered docs." in transformed


def test_transform_python_for_doxygen_renders_see_also_sections() -> None:
    source = '''
def analyze() -> None:
    """Analyze the module.

    See Also:
        resolve_names(): Performs name resolution.
        - `emit_c()`: Lowers the analyzed module to C.
    """
    return None
'''

    transformed = transform_python_for_doxygen(source)

    assert "## Analyze the module." in transformed
    assert "# @see resolve_names(): Performs name resolution." in transformed
    assert "# @see @c emit_c(): Lowers the analyzed module to C." in transformed


def test_transform_python_for_doxygen_preserves_intro_bullets_without_blank_lines() -> None:
    source = '''
class CEmitter:
    """C-specific code emitter.

    Responsibilities:
        - Emit C syntax (knows C keywords, syntax, conventions).
        - Name mangling for C.
        - Type emission (L0 types -> C types).

    Does NOT:
        - Make decisions about what to emit.
        - Perform semantic analysis.
    """
    pass
'''

    transformed = transform_python_for_doxygen(source)

    assert "## C-specific code emitter." in transformed
    assert "# Responsibilities:" in transformed
    assert "# - Emit C syntax (knows C keywords, syntax, conventions)." in transformed
    assert "# - Name mangling for C." in transformed
    assert "# - Type emission (L0 types -> C types)." in transformed
    assert "# Does NOT:" in transformed
    assert "# - Make decisions about what to emit." in transformed
    assert "# - Perform semantic analysis." in transformed
