#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""AST pretty-printing utility for the L0 compiler."""

from dataclasses import is_dataclass, fields
from typing import Any

from l0_ast import Span, Node, Module


def _format_span(span: Span | None) -> str:
    """Format a source span for printing.

    Args:
        span: The source span to format, or None.

    Returns:
        A string representation of the span (e.g., " @1:1-2:1"), or an empty
        string if the span is None.
    """
    if span is None:
        return ""
    return f" @{span.start_line}:{span.start_column}-{span.end_line}:{span.end_column}"


def format_node(node: Any, indent: int = 0) -> list[str]:
    """Generic, reflection-based AST pretty-printer.

    This function recursively traverses an AST node (or a list of nodes) and
    produces a human-readable string representation. It uses reflection to
    discover fields in dataclasses.

    - Shows the node class name.
    - Prints simple scalar fields inline (excluding `span`).
    - Recursively prints child Node or list-of-Node fields on new indented lines.
    - Appends a concise span annotation when available.

    Args:
        node: The AST node, list of nodes, or other object to format.
        indent: The current indentation level (number of 2-space increments).

    Returns:
        A list of strings representing the formatted AST, one line per string.
    """
    ind = "  " * indent

    # Lists: print each element at same indentation
    if isinstance(node, list):
        lines: list[str] = []
        for elem in node:
            lines.extend(format_node(elem, indent))
        return lines

    # AST nodes (dataclasses derived from Node)
    if isinstance(node, Node) and is_dataclass(node):
        span = node.span
        # Split fields into "simple scalars" vs "children"
        data_fields = [f for f in fields(node) if f.name != "span"]
        simple_parts = []
        child_fields = []

        for f in data_fields:
            value = getattr(node, f.name)
            if isinstance(value, Node) or isinstance(value, list):
                child_fields.append((f.name, value))
            else:
                simple_parts.append((f.name, value))

        # Header: ClassName(field1=..., field2=...) @line:col-line:col
        header = node.__class__.__name__
        if simple_parts:
            inner = ", ".join(f"{name}={value!r}" for name, value in simple_parts if value is not None)
            header = f"{header}({inner})"
        header += _format_span(span)

        lines: list[str] = [ind + header]

        # Child fields on separate indented lines
        for name, value in child_fields:
            if value is None:
                continue
            if isinstance(value, list):
                if not value:
                    continue
                lines.append(ind + "  " + f"{name}:")
                for elem in value:
                    lines.extend(format_node(elem, indent + 2))
            else:
                lines.append(ind + "  " + f"{name}:")
                lines.extend(format_node(value, indent + 2))

        return lines

    # Other dataclasses (if any) – fallback to repr
    if is_dataclass(node):
        return [ind + repr(node)]

    # Fallback for unexpected values
    return [ind + repr(node)]


def format_module(mod: Module) -> str:
    """Convenience function to pretty-print a single Module as a string.

    Args:
        mod: The module to format.

    Returns:
        A multiline string representing the formatted module.
    """
    lines = format_node(mod, indent=0)
    return "\n".join(lines)
