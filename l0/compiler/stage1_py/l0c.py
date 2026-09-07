#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Executable entrypoint and coarse compiler-command dispatch."""

from typing import List, Optional
from l0_cli_build import cmd_build, cmd_run
from l0_cli_commands import cmd_ast, cmd_check, cmd_codegen, cmd_compile, cmd_sym, cmd_tok, cmd_type
from l0_cli_args import parse_args


def main(argv: Optional[List[str]] = None) -> None:
    """Parse arguments, dispatch one compiler command, and exit.

    Args:
        argv: Arguments to parse, or the current process arguments when omitted.

    Raises:
        SystemExit: With the selected command exit code.
    """
    args = parse_args(argv)
    dispatch = {
        "run": cmd_run,
        "build": cmd_build,
        "compile": cmd_compile,
        "gen": cmd_codegen,
        "check": cmd_check,
        "tok": cmd_tok,
        "ast": cmd_ast,
        "sym": cmd_sym,
        "type": cmd_type,
    }

    rc = dispatch[args.mode](args)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
