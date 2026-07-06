#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Compilation context for cross-cutting compiler options.

This module defines the CompilationContext dataclass which holds compiler
options that affect multiple stages of compilation (code generation,
diagnostics, etc.).
"""

from dataclasses import dataclass
from enum import IntEnum


class LogLevel(IntEnum):
    """Hierarchical logging levels for the L0 compiler.

    Attributes:
        SILENT: No logging.
        ERROR: Error messages only.
        WARNING: Warning messages.
        INFO: General progress messages (-v).
        DEBUG: Detailed diagnostic information (-vvv).
    """
    SILENT = 0      # No logging (default)
    ERROR = 3       # Error messages only
    WARNING = 6     # Warning messages
    INFO = 10       # General progress messages (-v)
    DEBUG = 30      # Detailed diagnostic information (-vvv)


@dataclass
class CompilationContext:
    """Cross-cutting compiler options affecting multiple compilation stages.

    Attributes:
        emit_line_directives: If True, emit #line directives in generated C code
            for better debugging and error messages.
        trace_arc: If True, generated C enables ARC tracing in runtime (`L0_TRACE_ARC`).
        trace_memory: If True, generated C enables memory tracing in runtime
            (`L0_TRACE_MEMORY`).
        rt_unchecked: If True, generated C disables runtime pointer validation
            and allocation tracking (`L0_RT_UNCHECKED`).
        log_rich_format: If True, emit logs in rich format: may include log
            level, timestamps, etc.
        log_level: Current logging level.
    """
    emit_line_directives: bool = True
    trace_arc: bool = False
    trace_memory: bool = False
    rt_unchecked: bool = False
    log_rich_format: bool = False
    log_level: LogLevel = LogLevel.WARNING

    @staticmethod
    def default() -> 'CompilationContext':
        """Create a CompilationContext with default settings.

        Returns:
            A new CompilationContext instance with default values.
        """
        return CompilationContext(log_level=LogLevel.WARNING)
