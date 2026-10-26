# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Acceptance checks for the final pass of full, indexed reference PDFs."""

from pathlib import Path
import re


def validate_full_pdf(latex_dir: Path) -> None:
    """Reject unresolved references or missing destinations before PDF promotion.

    Args:
        latex_dir: Completed Doxygen LaTeX build containing the final pass log.

    Raises:
        OSError: The final LaTeX log cannot be read.
        ValueError: References, PDF destinations, or the generated index are incomplete.
    """
    log_path = latex_dir / "refman.log"
    # TeX wraps both identifiers and warning sentences at its print-line limit.
    compact = re.sub(r"\s+", "", log_path.read_text(encoding="utf-8", errors="replace"))
    missing = sorted(set(re.findall(
        r"pdfTeXwarning\(dest\):name\{([^}]+)\}hasbeenreferencedbutdoesnotexist", compact)))
    if missing:
        preview = ", ".join(missing[:3])
        raise ValueError(f"full PDF has {len(missing)} missing destination(s): {preview}; see {log_path}")
    if "Therewereundefinedreferences" in compact or "Reruntogetcross-referencesright" in compact:
        raise ValueError(f"full PDF has unresolved references; see {log_path}")
    if not (latex_dir / "refman.ind").is_file():
        raise ValueError(f"full PDF index is missing: {latex_dir / 'refman.ind'}")
