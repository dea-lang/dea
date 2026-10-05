#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Stage the Stage 2 Pages reference and preserve historical entrypoints."""

from __future__ import annotations

import argparse
import ast
import html
from pathlib import Path
import shutil

from docs_artifacts import L0_ROOT, pdf_name


NOTICE = """<!DOCTYPE html><html lang="en"><meta charset="utf-8">
<title>Dea/L0 documentation migration</title><h1>Stage 1 reference moved</h1>
<p>The public reference now documents Dea/L0 Stage 2 and shared APIs.
Stage 1 compiler pages are available through local generation with
<code>make docs-pdf DOC_STAGE=stage1</code> and the separate validation artifacts.
Historical release downloads retain their original mixed references.</p>
<p><a href="{home}">Open the Stage 2 reference</a></p></html>
"""


def stage_pages(source: Path, destination: Path, root: Path = L0_ROOT) -> None:
    """Copy Stage 2 HTML and add migration notices and the old PDF alias.

    Args:
        source: Stage 2 output directory.
        destination: Pages staging directory.
        root: L0 source root, used to inventory retired Python page URLs.

    Raises:
        ValueError: The selected reference is not Stage 2.
    """
    if "Dea/L0 Stage 2" not in (source / "html/index.html").read_text(encoding="utf-8"):
        raise ValueError("Pages requires the Stage 2 reference")
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(source / "html", destination)
    pdf = source / "pdf" / pdf_name("stage2")
    if pdf.is_file():
        (destination / "pdf").mkdir(exist_ok=True)
        shutil.copy2(pdf, destination / "pdf" / pdf.name)
        shutil.copy2(pdf, destination / "pdf/dea_l0_api_reference.pdf")
    retired = {Path("stage1.html"), Path("404.html")}
    for path in (root / "compiler/stage1_py").rglob("*.py"):
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root)
        retired.add(Path("api") / rel.with_suffix(".html"))
        # Doxygen's previous raw file, namespace, and class URLs.
        def encode(name: str) -> str:
            return "".join("__" if c == "_" else "_" + c.lower() if c.isupper() else c for c in name)
        stem = encode(path.stem)
        retired.update((Path(f"{stem}_8py.html"), Path(f"namespace{stem}.html")))
        def visit_classes(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
            for child in ast.iter_child_nodes(node):
                scope = parents
                if isinstance(child, ast.ClassDef):
                    scope = (*parents, encode(child.name))
                    retired.add(Path(f"class{stem}_1_1{'_1_1'.join(scope)}.html"))
                visit_classes(child, scope)
        visit_classes(ast.parse(path.read_text(encoding="utf-8")))
    for rel in retired:
        path = destination / rel
        # Never redirect a removed oracle symbol to an unrelated Stage 2 symbol.
        if path.exists():
            raise ValueError(f"retired Stage 1 URL collides with Stage 2 output: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        home = "../" * (len(rel.parts) - 1) + "index.html"
        path.write_text(NOTICE.format(home=html.escape(home)), encoding="utf-8")
    (destination / ".nojekyll").touch()


def main() -> int:
    """Stage the current Stage 2 reference for the authorized publication workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("build/docs/stage2"))
    parser.add_argument("--output", type=Path, default=Path("build/docs/pages-site"))
    args = parser.parse_args()
    stage_pages(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
