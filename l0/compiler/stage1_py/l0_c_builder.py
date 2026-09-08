# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2025-2026 gwz

from dataclasses import dataclass, field


@dataclass
class CCodeBuilder:
    """Helper for building C code with indentation tracking.

    Attributes:
        lines: List of emitted code lines.
        indent_level: Current indentation depth.
        indent_str: String used for a single level of indentation. Defaults to 4 spaces.
    """
    lines: list[str] = field(default_factory=list)
    indent_level: int = 0
    indent_str: str = "    "  # 4 spaces

    def indent(self) -> None:
        """Increase the indentation level."""
        self.indent_level += 1

    def dedent(self) -> None:
        """Decrease the indentation level.

        Raises:
            AssertionError: If indentation level is already zero.
        """
        assert self.indent_level > 0, "dedent below zero"
        self.indent_level -= 1

    def emit(self, line: str = "") -> None:
        """Emit a line with current indentation.

        Args:
            line: The C code line to emit. If empty, emits a blank line.
        """
        if line:
            self.lines.append(self.indent_str * self.indent_level + line)
        else:
            self.lines.append("")

    def emit_raw(self, line: str) -> None:
        """Emit a line without indentation.

        Args:
            line: The C code line to emit directly.
        """
        self.lines.append(line)

    def to_string(self) -> str:
        """Combine all lines into a single string.

        Returns:
            The complete C source code string with a trailing newline.
        """
        return "\n".join(self.lines) + "\n"  # Ensure trailing newline
