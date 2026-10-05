# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Minimal verified docs payload for packaging tests, without invoking TeX."""

from pathlib import Path
import sys

L0_ROOT = Path(__file__).resolve().parents[1]
if str(L0_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(L0_ROOT / "scripts"))
from docs_artifacts import create_bundle, package_version, pdf_name, source_identity


def docs_fixture(work: Path, stage: str = "stage2") -> Path:
    """Create a synthetic payload for distribution contract tests.

    Args:
        work: Fixture directory.
        stage: Documentation stage.

    Returns:
        Absolute bundle path.
    """
    tree = work / stage
    (tree / "html").mkdir(parents=True)
    (tree / "html/index.html").write_text(f"<title>Dea/L0 Stage {stage[-1]} API</title>", encoding="utf-8")
    (tree / "pdf").mkdir()
    (tree / "pdf" / pdf_name(stage)).write_bytes(b"%PDF-1.4\nPackaging test fixture\n")
    bundle = (work / f"{stage}.tar.gz").resolve()
    create_bundle(tree, bundle, stage=stage, version=package_version(L0_ROOT),
                  source=source_identity(L0_ROOT, stage),
                  tools={name: "test fixture" for name in ("doxygen", "pdflatex", "python", "mcss")})
    return bundle
