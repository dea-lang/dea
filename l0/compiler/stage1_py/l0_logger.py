#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Logging utilities for the L0 compiler.

This module provides logging functions that respect the CompilationContext
flags (verbosity and rich format).
"""

import sys
import time

from l0_context import CompilationContext, LogLevel


def log(context: CompilationContext, log_level: LogLevel, message: str) -> None:
    """Log a message according to the current context and level.

    Args:
        context: The compilation context containing logging configuration.
        log_level: The level of the message to log.
        message: The message to log.
    """
    if context is None:
        print("No context provided for logging.", file=sys.stderr)
        print(f"{message}", file=sys.stderr)
        return
    prefix = ""
    if context.log_rich_format:
        # timestamp prefix
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        prefix = {
            LogLevel.ERROR: f"{timestamp} [ERROR] ",
            LogLevel.WARNING: f"{timestamp} [WARNING] ",
            LogLevel.INFO: f"{timestamp} [INFO] ",
            LogLevel.DEBUG: f"{timestamp} [DEBUG] ",
        }.get(log_level, "")
    if context.log_level >= log_level:
        print(f"{prefix}{message}", file=sys.stderr)

def log_error(context: CompilationContext, message: str) -> None:
    """Log an error-level message.

    Args:
        context: The compilation context.
        message: The message to log.
    """
    log(context, LogLevel.ERROR, message)

def log_warning(context: CompilationContext, message: str) -> None:
    """Log a warning-level message.

    Args:
        context: The compilation context.
        message: The message to log.
    """
    log(context, LogLevel.WARNING, message)

def log_info(context: CompilationContext, message: str) -> None:
    """Log an info-level message.

    Args:
        context: The compilation context.
        message: The message to log.
    """
    log(context, LogLevel.INFO, message)


def log_debug(context: CompilationContext, message: str) -> None:
    """Log a debug-level message.

    Args:
        context: The compilation context.
        message: The message to log.
    """
    log(context, LogLevel.DEBUG, message)

def log_stage(context: CompilationContext, stage: str, module: str | None = None) -> None:
    """Log the start or transition of a compilation stage.

    Args:
        context: The compilation context.
        stage: The name of the compilation stage (e.g., "Lexing", "Parsing").
        module: Optional module name being processed.
    """
    if module:
        log(context, LogLevel.INFO, f"{stage} module '{module}'")
    else:
        log(context, LogLevel.INFO, f"{stage}...")
