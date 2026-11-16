#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Stage independent L0 references on Pages and preserve historical entrypoints."""

from __future__ import annotations

import argparse
import ast
import html
from pathlib import Path
import shutil
import re
import tempfile

from docs_artifacts import L0_ROOT, pdf_name


def add_stage_selector(tree: Path, stage: str) -> None:
    """Add Pages-only links to the two reference homes on every HTML page.

    Args:
        tree: Copied HTML tree for one stage.
        stage: Stage owning this tree.

    Raises:
        ValueError: A generated page has no HTML body.
    """
    for page in tree.rglob("*.html"):
        prefix = "../" * (len(page.relative_to(tree).parts) - 1)
        homes = {"stage1": prefix + "stage1/index.html", "stage2": prefix + "index.html"}
        if stage == "stage1":
            homes = {"stage1": prefix + "index.html", "stage2": prefix + "../index.html"}
        links = []
        for name, target in homes.items():
            current = ' aria-current="true"' if name == stage else ""
            links.append(f'<a href="{target}"{current}>Stage {name[-1]}</a>')
        selector = ('<nav aria-label="Reference stage" class="m-container" style="padding: .75rem 1rem;">'
                    'Reference: ' + ' | '.join(links) + '</nav>')
        text = page.read_text(encoding="utf-8")
        if "</header>" in text:
            text = text.replace("</header>", "</header>\n" + selector, 1)
        else:
            text, count = re.subn(r"<body\b[^>]*>", lambda match: match[0] + selector, text, count=1)
            if not count:
                raise ValueError(f"Pages HTML has no body: {page}")
        page.write_text(text, encoding="utf-8")


def stage_pages(source: Path, destination: Path, root: Path = L0_ROOT, *, base_path: str = "/dea/") -> None:
    """Assemble both references without modifying their distribution inputs.

    Args:
        source: Common parent containing stage1 and stage2 HTML/PDF outputs.
        destination: Pages staging directory, separate from the input stage trees.
        root: L0 source root, used to inventory historical Python page URLs.
        base_path: Absolute URL path of the Pages site, used by the 404 fallback.

    Raises:
        ValueError: A stage is absent, mislabeled, or overlaps the destination.
    """
    if not base_path.startswith("/") or not base_path.endswith("/") or base_path.startswith("//"):
        raise ValueError("Pages base path must start and end with a single slash")
    for stage in ("stage1", "stage2"):
        tree = source / stage
        if tree.resolve().is_relative_to(destination.resolve()) or destination.resolve().is_relative_to(tree.resolve()):
            raise ValueError("Pages destination must not overlap stage inputs")
        index = tree / "html/index.html"
        if not index.is_file() or f"Dea/L0 Stage {stage[-1]}" not in index.read_text(encoding="utf-8"):
            raise ValueError(f"Pages requires the {stage} reference")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / "site"
        # Insert selectors before nesting Stage 1, keeping each search payload untouched.
        for stage in ("stage2", "stage1"):
            target = staged if stage == "stage2" else staged / "stage1"
            shutil.copytree(source / stage / "html", target)
            pdf = source / stage / "pdf" / pdf_name(stage)
            if pdf.is_file():
                (target / "pdf").mkdir(exist_ok=True)
                shutil.copy2(pdf, target / "pdf" / pdf.name)
                if stage == "stage2":
                    shutil.copy2(pdf, target / "pdf/dea_l0_api_reference.pdf")
            add_stage_selector(target, stage)
        add_legacy_links(staged, root, base_path)
        (staged / ".nojekyll").touch()
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(staged), destination)


def add_legacy_links(destination: Path, root: Path, base_path: str) -> None:
    """Route historical Stage 1 URLs without overwriting Stage 2 pages.

    Args:
        destination: Assembled Pages tree.
        root: L0 source root used to inventory historical Python page URLs.
        base_path: Absolute site path for links from arbitrary missing URLs.
    """
    retired = {Path("stage1.html")}
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
        # Existing Stage 2 URLs retain their meaning, including same-named symbols.
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        target = Path("stage1") / rel
        if not (destination / target).is_file():
            # The isolated Python renderer prefixes raw Doxygen filenames.
            prefixed = Path("stage1") / rel.with_name("python_" + rel.name)
            target = prefixed if (destination / prefixed).is_file() else Path("stage1/index.html")
        url = html.escape("../" * (len(rel.parts) - 1) + target.as_posix(), quote=True)
        path.write_text(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={url}">'
            '<title>Stage 1 reference moved</title></head><body>'
            f'<p><a href="{url}">Open the Stage 1 reference</a></p></body></html>', encoding="utf-8")
    base = html.escape(base_path, quote=True)
    (destination / "404.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<title>Dea/L0 reference page not found</title></head><body>'
        '<h1>Reference page not found</h1><p>Choose a reference and use its search:</p>'
        f'<nav aria-label="Reference stage"><a href="{base}stage1/index.html">Stage 1</a> | '
        f'<a href="{base}index.html">Stage 2</a></nav></body></html>', encoding="utf-8")


def main() -> int:
    """Stage both references for the authorized publication workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("build/docs"))
    parser.add_argument("--output", type=Path, default=Path("build/docs/pages-site"))
    parser.add_argument("--base-path", default="/dea/", help="Pages URL prefix, including leading/trailing slashes")
    args = parser.parse_args()
    stage_pages(args.source, args.output, base_path=args.base_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
