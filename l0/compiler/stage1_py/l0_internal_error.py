#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Internal Compiler Error (ICE) definitions for the L0 compiler."""

from dataclasses import dataclass

from l0_ast import Span


@dataclass(frozen=True)
class ICELocation:
    """Represents the location where an internal compiler error occurred.

    Attributes:
        filename: The path to the source file being processed.
        span: Optional source span information.
    """
    filename: str | None
    span: Span | None


class InternalCompilerError(RuntimeError):
    """Exception raised when an internal compiler invariant is violated.

    Internal compiler errors (ICEs) indicate bugs in the compiler itself,
    rather than mistakes in the user's source code.

    Attributes:
        message: A descriptive error message, preferably including an [ICE-nnnn] code.
        loc: The source location where the error originated.
    """

    def __init__(self, message: str, loc: ICELocation | None = None):
        """Initialize the internal compiler error.

        Args:
            message: The error message.
            loc: Optional source location.
        """
        super().__init__(message)
        self.message = message
        self.loc = loc

    def format(self) -> str:
        """Format the ICE as a human-readable string.

        Returns:
            A formatted error message including location information.
        """
        message = self.message
        if not "[ICE-" in message:
            message = f"[ICE-9999] {message}"
        if self.loc and self.loc.filename:
            if self.loc.span is not None:
                return f"{self.loc.filename}:{self.loc.span.start_line}:{self.loc.span.start_column}: internal compiler error: {message}"
            return f"{self.loc.filename}: internal compiler error: {message}"
        return f"internal compiler error: {message}"
