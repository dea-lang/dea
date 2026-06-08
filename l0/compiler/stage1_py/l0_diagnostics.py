#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2025-2026 gwz

"""Diagnostic reporting for the L0 compiler.

This module defines the Diagnostic dataclass and helper functions for
creating diagnostics from AST nodes and tokens.
"""

import os
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from l0_ast import Node

if TYPE_CHECKING:
    from l0_lexer import Token

DIAGNOSTIC_CODE_FAMILIES = {
    "LEX": [
        "LEX-0010",
        "LEX-0020",
        "LEX-0021",
        "LEX-0030",
        "LEX-0031",
        "LEX-0040",
        "LEX-0050",
        "LEX-0051",
        "LEX-0052",
        "LEX-0053",
        "LEX-0054", # Unicode code point out of range (currently not used in Stage 1)
        "LEX-0059",
        "LEX-0060",
        "LEX-0061",
        "LEX-0070",
    ],
    "PAR": [
        "PAR-0010",
        "PAR-0011",
        "PAR-0020",
        "PAR-0030",
        "PAR-0040",
        "PAR-0041",
        "PAR-0042",
        "PAR-0043",
        "PAR-0044",
        "PAR-0045",
        "PAR-0046",
        "PAR-0050",
        "PAR-0051",
        "PAR-0052",
        "PAR-0053",
        "PAR-0054",
        "PAR-0055",
        "PAR-0056",
        "PAR-0060",
        "PAR-0061",
        "PAR-0062",
        "PAR-0063",
        "PAR-0064",
        "PAR-0065",
        "PAR-0066",
        "PAR-0067",
        "PAR-0068",
        "PAR-0070",
        "PAR-0071",
        "PAR-0072",
        "PAR-0073",
        "PAR-0080",
        "PAR-0081",
        "PAR-0082",
        "PAR-0083",
        "PAR-0090",
        "PAR-0091",
        "PAR-0100",
        "PAR-0110",
        "PAR-0111",
        "PAR-0112",
        "PAR-0120",
        "PAR-0121",
        "PAR-0122",
        "PAR-0123",
        "PAR-0130",
        "PAR-0131",
        "PAR-0132",
        "PAR-0140",
        "PAR-0141",
        "PAR-0142",
        "PAR-0143",
        "PAR-0144",
        "PAR-0150",
        "PAR-0160",
        "PAR-0161",
        "PAR-0170",
        "PAR-0171",
        "PAR-0172",
        "PAR-0173",
        "PAR-0174",
        "PAR-0175",
        "PAR-0176",
        "PAR-0177",
        "PAR-0180",
        "PAR-0181",
        "PAR-0182",
        "PAR-0190",
        "PAR-0200",
        "PAR-0210",
        "PAR-0211",
        "PAR-0212",
        "PAR-0223",
        "PAR-0224",
        "PAR-0225",
        "PAR-0226",
        "PAR-0230",
        "PAR-0231",
        "PAR-0232",
        "PAR-0233",
        "PAR-0234",
        "PAR-0235",
        "PAR-0236",
        "PAR-0237",
        "PAR-0238",
        "PAR-0239",
        "PAR-0240",
        "PAR-0241",
        "PAR-0242",
        "PAR-0243",
        "PAR-0300",
        "PAR-0310",
        "PAR-0311",
        "PAR-0312",
        "PAR-0320",
        "PAR-0321",
        "PAR-0400",
        "PAR-0401",
        "PAR-9401",
        "PAR-0500",
        "PAR-0501",
        "PAR-0502",
        "PAR-0503",
        "PAR-0504",
        "PAR-0505",
        "PAR-0506",
    ],
    "DRV": [
        "DRV-0010",
        "DRV-0020",
        "DRV-0030",
        "DRV-0040",
    ],
    "L0C": [
        "L0C-0009",
        "L0C-0010",
        "L0C-0011",
        "L0C-0012",
        "L0C-0013",
        "L0C-0014",
        "L0C-0016",
        "L0C-0017",
        "L0C-0020",
        "L0C-0030",
        "L0C-0040",
        "L0C-0041",
        "L0C-0050",
        "L0C-0060",
        "L0C-0070",
    ],
    "RES": [
        "RES-0010",
        "RES-0020",
        "RES-0021",
        "RES-0022",
        "RES-0029",
        "RES-0036",
    ],
    "SIG": [
        "SIG-0010",
        "SIG-0011",
        "SIG-0018",
        "SIG-0019",
        "SIG-0020",
        "SIG-0030",
        "SIG-0040",
        "SIG-9029",
    ],
    # ICE codes are internal compiler errors raised as exceptions,
    # not user-facing diagnostics; they are excluded from this registry.
    "TYP": [
        "TYP-0001", "TYP-0002", "TYP-0010", "TYP-0020", "TYP-0021",
        "TYP-0022", "TYP-0023", "TYP-0024", "TYP-0025", "TYP-0030",
        "TYP-0031", "TYP-0040", "TYP-0050", "TYP-0051", "TYP-0052",
        "TYP-0053", "TYP-0060", "TYP-0061", "TYP-0062", "TYP-0063", "TYP-0070",
        "TYP-0080", "TYP-0090", "TYP-0100", "TYP-0101", "TYP-0102",
        "TYP-0103", "TYP-0104", "TYP-0105", "TYP-0106", "TYP-0107",
        "TYP-0108", "TYP-0109", "TYP-0110", "TYP-0120", "TYP-0139",
        "TYP-0149", "TYP-0150", "TYP-0151", "TYP-0152", "TYP-0153",
        "TYP-0154", "TYP-0155", "TYP-0156", "TYP-0158", "TYP-0159",
        "TYP-0160", "TYP-0161", "TYP-0162", "TYP-0170", "TYP-0171",
        "TYP-0172", "TYP-0173", "TYP-0180", "TYP-0181", "TYP-0182",
        "TYP-0183", "TYP-0189", "TYP-0190", "TYP-0191", "TYP-0200",
        "TYP-0201", "TYP-0210", "TYP-0211", "TYP-0212", "TYP-0220",
        "TYP-0221", "TYP-0222", "TYP-0230", "TYP-0240", "TYP-0241",
        "TYP-0242", "TYP-0243", "TYP-0250", "TYP-0251", "TYP-0260",
        "TYP-0270", "TYP-0271", "TYP-0278", "TYP-0279", "TYP-0280",
        "TYP-0281", "TYP-0282", "TYP-0283", "TYP-0285", "TYP-0286",
        "TYP-0290", "TYP-0300", "TYP-0301", "TYP-0303",
        "TYP-0310", "TYP-0311", "TYP-0312", "TYP-0313",
        "TYP-0314", "TYP-0315", "TYP-0316", "TYP-0319",
        "TYP-0700", "TYP-0701",
        "TYP-9209",
        "TYP-9288", "TYP-9289",
    ],
}


@dataclass
class Diagnostic:
    """Represents a compiler diagnostic (error or warning).

    Attributes:
        kind: The kind of diagnostic ("error" or "warning").
        message: The diagnostic message.
        module_name: Optional name of the module where the diagnostic occurred.
        filename: Optional file path where the diagnostic occurred.
        line: 1-based line number of the start of the diagnostic.
        column: 1-based column number of the start of the diagnostic.
        end_line: 1-based line number of the end of the diagnostic.
        end_column: 1-based column number of the end of the diagnostic.
    """
    kind: str
    message: str
    module_name: Optional[str] = None
    filename: Optional[str] = None

    # Primary location (start of the span)
    line: Optional[int] = None
    column: Optional[int] = None

    # Optional end of span (exclusive)
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def format(self) -> str:
        """Format the diagnostic as a one-line string header.

        Returns:
            A formatted string containing location, kind, and message.
        """
        loc = ""
        if self.filename is not None:
            loc += f"{os.path.abspath(str(self.filename))}"
        if self.line is not None:
            loc += f":{self.line}"
            if self.column is not None:
                loc += f":{self.column}"
            if self.module_name is not None:
                loc += f"({self.module_name})"
        if loc:
            loc += ": "
        return f"{loc}{self.kind}: {self.message}"


def diag_from_node(
        kind: str,
        message: str,
        *,
        module_name: Optional[str],
        filename: Optional[str],
        node: Optional[Node],
) -> Diagnostic:
    """Create a Diagnostic from an AST node.

    Args:
        kind: The kind of diagnostic ("error" or "warning").
        message: The diagnostic message.
        module_name: Optional module name.
        filename: Optional filename.
        node: Optional AST node providing span information.

    Returns:
        A new Diagnostic instance.
    """
    line = column = end_line = end_column = None
    if node is not None and node.span is not None:
        s = node.span
        line = s.start_line
        column = s.start_column
        end_line = s.end_line
        end_column = s.end_column
    return Diagnostic(
        kind=kind,
        message=message,
        module_name=module_name,
        filename=filename,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
    )

def diag_from_token(
        kind: str,
        message: str,
        *,
        module_name: Optional[str],
        filename: Optional[str],
        token: Optional["Token"],
) -> Diagnostic:
    """Create a Diagnostic from a lexer token.

    Args:
        kind: The kind of diagnostic ("error" or "warning").
        message: The diagnostic message.
        module_name: Optional module name.
        filename: Optional filename.
        token: Optional lexer token providing location information.

    Returns:
        A new Diagnostic instance.
    """
    line = column = end_line = end_column = None
    if token is not None:
        line = token.line
        column = token.column
    return Diagnostic(
        kind=kind,
        message=message,
        module_name=module_name,
        filename=filename,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
    )
