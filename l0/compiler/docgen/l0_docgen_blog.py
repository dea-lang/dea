# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Export generated API Markdown into a Chirpy/Jekyll-friendly tree."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

SECTION_HEADINGS = {"## Stage 1": "stage1", "## Stage 2": "stage2", "## Shared": "shared"}
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
SOURCE_LINE_RE = re.compile(r"^Source:\s*`([^`]+)`\s*$", re.MULTILINE)
ANCHOR_TAG_RE = re.compile(r"<a\s+(?:id|name)=['\"]([^'\"]+)['\"]\s*>\s*</a>")


@dataclass(frozen=True)
class ExportEntry:
    """A single generated Markdown page exported into the blog tree."""

    rel_markdown_path: Path
    source_path: str
    title: str
    permalink: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input Markdown root produced by l0_docgen.")
    parser.add_argument("--output", type=Path, required=True, help="Output root for the blog export.")
    parser.add_argument("--stage", choices=("all", "stage1", "stage2"), default="all", help="Select stage; all accepts historical mixed references.")
    parser.add_argument("--docs-prefix", default="api/reference", help="Destination prefix inside the blog repo.")
    parser.add_argument("--tab-title", default="API", help="Title for the generated Chirpy tab page.")
    parser.add_argument("--tab-icon", default="fas fa-book", help="Icon class for the generated Chirpy tab page.")
    parser.add_argument("--tab-order", type=int, default=5, help="Order for the generated Chirpy tab page.")
    parser.add_argument("--html-site-url", default="", help="Standalone HTML site URL.")
    parser.add_argument("--pdf-url", default="", help="Published PDF URL.")
    parser.add_argument("--release-tag", default="", help="Release tag for version display.")
    return parser.parse_args(argv)


def _normalize_docs_prefix(prefix: str) -> str:
    return prefix.strip("/").replace("\\", "/")


def _heading_slug(value: str) -> str:
    """Return the same fragment slug shape used by the markdown renderer."""

    normalized = value.lower().replace("`", "").replace(":", "")
    normalized = re.sub(r"[^a-z0-9_\-\s]+", "", normalized)
    normalized = re.sub(r"[\s\-]+", "-", normalized).strip("-")
    return normalized or "section"


def file_anchor_for_source_path(source_path: str) -> str:
    """Return the file-compound anchor expected by generated cross-page links."""

    return _heading_slug(f"File `{Path(source_path).name}`")


def _source_path_from_markdown(markdown_text: str, fallback_rel_path: Path) -> str:
    match = SOURCE_LINE_RE.search(markdown_text)
    if match:
        return match.group(1)
    first_line = markdown_text.splitlines()[0] if markdown_text.splitlines() else ""
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return fallback_rel_path.as_posix()


def _strip_leading_h1(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).rstrip() + "\n"


def _jekyll_target_for_markdown_target(target_path: Path, docs_prefix: str) -> str:
    return f"/{docs_prefix}/{target_path.with_suffix('').as_posix()}/"


def rewrite_markdown_links(markdown_text: str, current_rel_path: Path, docs_prefix: str) -> str:
    """Rewrite internal Markdown links to Jekyll permalinks."""
    rewritten_lines: list[str] = []
    in_fence = False

    def replace(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith("#"):
            return match.group(0)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            return match.group(0)

        path_part, anchor = target, ""
        if "#" in target:
            path_part, anchor = target.split("#", 1)
            anchor = f"#{anchor}"
        if not path_part.endswith(".md"):
            return match.group(0)

        resolved = Path(os.path.normpath((current_rel_path.parent / Path(path_part)).as_posix()))
        permalink = _jekyll_target_for_markdown_target(resolved, docs_prefix)
        return f"[{label}]({{{{ '{permalink}' | relative_url }}}}{anchor})"

    for line in markdown_text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            rewritten_lines.append(line)
            continue
        if in_fence:
            rewritten_lines.append(line)
            continue
        rewritten_lines.append(LINK_RE.sub(replace, line))

    return "\n".join(rewritten_lines).rstrip() + "\n"


def rewrite_anchor_targets(markdown_text: str) -> str:
    """Rewrite anchor-only HTML tags to fragment-safe non-link elements."""

    return ANCHOR_TAG_RE.sub(lambda match: f'<span id="{match.group(1)}"></span>', markdown_text)


def parse_markdown_index(index_text: str) -> dict[str, list[tuple[str, str]]]:
    """Return grouped entries from the generated markdown index."""
    groups: dict[str, list[tuple[str, str]]] = {"stage1": [], "stage2": [], "shared": []}
    current_group: str | None = None
    for line in index_text.splitlines():
        stripped = line.strip()
        current_group = SECTION_HEADINGS.get(stripped, current_group)
        if not current_group:
            continue
        match = re.match(r"- \[`([^`]+)`\]\(([^)]+)\)", stripped)
        if match:
            groups[current_group].append((match.group(1), match.group(2)))
    return groups


def export_markdown_tree(
    input_dir: Path,
    output_dir: Path,
    *,
    docs_prefix: str,
    tab_title: str,
    tab_icon: str,
    tab_order: int,
    html_site_url: str = "",
    pdf_url: str = "",
    release_tag: str = "",
    stage: str = "all",
) -> None:
    """Export generated Markdown into a Chirpy-friendly directory tree."""
    docs_prefix = _normalize_docs_prefix(docs_prefix)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = input_dir / "index.md"
    grouped_entries = parse_markdown_index(index_path.read_text(encoding="utf-8"))

    export_entries: dict[Path, ExportEntry] = {}
    destination_root = output_dir / docs_prefix

    for markdown_path in sorted(input_dir.rglob("*.md")):
        if markdown_path == index_path:
            continue
        rel_path = markdown_path.relative_to(input_dir)
        if rel_path.name.startswith("docs-mainpage"):
            continue
        raw_text = markdown_path.read_text(encoding="utf-8")
        source_path = _source_path_from_markdown(raw_text, rel_path)
        if stage == "stage2" and source_path.startswith("compiler/stage1_py/"):
            continue
        if stage == "stage1" and source_path.startswith("compiler/stage2_l0/"):
            continue
        title = Path(source_path).name
        permalink = _jekyll_target_for_markdown_target(rel_path, docs_prefix)
        export_entries[rel_path] = ExportEntry(rel_path, source_path, title, permalink)

        body = _strip_leading_h1(raw_text)
        body = rewrite_markdown_links(body, rel_path, docs_prefix)
        body = rewrite_anchor_targets(body)

        front_matter = "\n".join(
            [
                "---",
                "layout: page",
                f'title: "{title}"',
                f"permalink: {permalink}",
                "toc: true",
                "---",
                "",
            ]
        )
        destination = destination_root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_anchor = f'<span id="{file_anchor_for_source_path(source_path)}"></span>\n\n'
        destination.write_text(front_matter + file_anchor + body, encoding="utf-8")

    def render_group(title: str, key: str) -> list[str]:
        lines = [f"## {title}", ""]
        for label, href in grouped_entries[key]:
            rel_path = Path(href)
            entry = export_entries.get(rel_path)
            if entry is None:
                continue
            lines.append(f"- [{label}]({{{{ '{entry.permalink}' | relative_url }}}})")
        lines.append("")
        return lines

    tab_lines = [
        "---",
        "layout: page",
        f'title: "{tab_title}"',
        f'icon: "{tab_icon}"',
        f"order: {tab_order}",
        "permalink: /api/",
        "---",
        "",
        "Generated API reference synchronized from the Dea/L0 compiler repository.",
        "",
    ]
    if release_tag:
        tab_lines.append(f"**Release {release_tag}**")
        tab_lines.append("")
    if html_site_url:
        tab_lines.append(f"- [Standalone HTML reference]({html_site_url})")
    if pdf_url:
        tab_lines.append(f"- [PDF reference]({pdf_url})")
    if html_site_url or pdf_url:
        tab_lines.append("")
    for key, title in (("stage1", "Stage 1"), ("stage2", "Stage 2")):
        if grouped_entries[key] and stage in {"all", key}:
            tab_lines.extend(render_group(title, key))
    tab_lines.extend(render_group("Shared", "shared"))

    tabs_dir = output_dir / "_tabs"
    tabs_dir.mkdir(parents=True, exist_ok=True)
    (tabs_dir / "api.md").write_text("\n".join(tab_lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the blog export."""
    args = parse_args(argv)
    export_markdown_tree(
        args.input.resolve(),
        args.output.resolve(),
        docs_prefix=args.docs_prefix,
        tab_title=args.tab_title,
        tab_icon=args.tab_icon,
        tab_order=args.tab_order,
        html_site_url=args.html_site_url,
        pdf_url=args.pdf_url,
        release_tag=args.release_tag,
        stage=args.stage,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
