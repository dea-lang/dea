# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for Markdown-to-Chirpy export."""

from pathlib import Path

from compiler.docgen.l0_docgen_blog import (
    export_markdown_tree,
    file_anchor_for_source_path,
    parse_args,
    parse_markdown_index,
    rewrite_anchor_targets,
    rewrite_markdown_links,
)


def test_parse_markdown_index_groups_entries() -> None:
    groups = parse_markdown_index(
        """# Index

## Stage 1
- [`compiler/stage1_py/demo.py`](compiler/stage1_py/demo.md)

## Stage 2
- [`compiler/stage2_l0/src/tokens.l0`](compiler/stage2_l0/src/tokens.md)

## Shared
- [`compiler/shared/runtime/l0_runtime.h`](compiler/shared/runtime/l0_runtime.md)
"""
    )
    assert groups["stage1"] == [("compiler/stage1_py/demo.py", "compiler/stage1_py/demo.md")]
    assert groups["stage2"] == [("compiler/stage2_l0/src/tokens.l0", "compiler/stage2_l0/src/tokens.md")]
    assert groups["shared"] == [("compiler/shared/runtime/l0_runtime.h", "compiler/shared/runtime/l0_runtime.md")]


def test_parse_markdown_index_ignores_non_link_lines_within_sections() -> None:
    groups = parse_markdown_index(
        """# Dea/L0 API Markdown Index

Generated from Doxygen XML.
Use this catalog for source-path-first browsing.

## Stage 1
Count: 1 files
- [`compiler/stage1_py/demo.py`](compiler/stage1_py/demo.md)

## Stage 2
Count: 1 files
- [`compiler/stage2_l0/src/tokens.l0`](compiler/stage2_l0/src/tokens.md)

## Shared
Count: 1 files
- [`compiler/shared/runtime/l0_runtime.h`](compiler/shared/runtime/l0_runtime.md)
"""
    )
    assert groups["stage1"] == [("compiler/stage1_py/demo.py", "compiler/stage1_py/demo.md")]
    assert groups["stage2"] == [("compiler/stage2_l0/src/tokens.l0", "compiler/stage2_l0/src/tokens.md")]
    assert groups["shared"] == [("compiler/shared/runtime/l0_runtime.h", "compiler/shared/runtime/l0_runtime.md")]


def test_rewrite_markdown_links_rewrites_internal_targets_and_preserves_anchors() -> None:
    text = (
        "See [tokens](../stage2_l0/src/tokens.md#enum-tokentype), "
        "[same](#struct-demo), and [web](https://example.com).\n"
        "```md\n"
        "[raw](../stage2_l0/src/tokens.md)\n"
        "```\n"
    )
    rewritten = rewrite_markdown_links(text, Path("compiler/stage1_py/demo.md"), "api/reference")
    assert "[tokens]({{ '/api/reference/compiler/stage2_l0/src/tokens/' | relative_url }}#enum-tokentype)" in rewritten
    assert "[same](#struct-demo)" in rewritten
    assert "[web](https://example.com)" in rewritten
    assert "[raw](../stage2_l0/src/tokens.md)" in rewritten


def test_parse_args_defaults_blog_tab_order_to_five(tmp_path: Path) -> None:
    args = parse_args(["--input", str(tmp_path / "in"), "--output", str(tmp_path / "out")])
    assert args.tab_order == 5


def test_file_anchor_for_source_path_matches_markdown_renderer_shape() -> None:
    assert file_anchor_for_source_path("compiler/shared/l0/stdlib/std/io.l0") == "file-iol0"
    assert file_anchor_for_source_path("compiler/stage1_py/l0_paths.py") == "file-l0_pathspy"


def test_rewrite_anchor_targets_replaces_anchor_only_tags() -> None:
    text = '<a id="function-demo"></a>\n<a name="struct-demo"></a>\n'
    rewritten = rewrite_anchor_targets(text)
    assert '<span id="function-demo"></span>' in rewritten
    assert '<span id="struct-demo"></span>' in rewritten
    assert "<a id=" not in rewritten
    assert "<a name=" not in rewritten


def test_export_markdown_tree_generates_chirpy_pages_and_tab(tmp_path: Path) -> None:
    input_dir = tmp_path / "markdown"
    output_dir = tmp_path / "blog-export"
    (input_dir / "compiler/stage1_py").mkdir(parents=True)
    (input_dir / "compiler/stage2_l0/src").mkdir(parents=True)

    (input_dir / "index.md").write_text(
        """# Dea/L0 API Markdown Index

## Stage 1

- [`compiler/stage1_py/demo.py`](compiler/stage1_py/demo.md)

## Stage 2

- [`compiler/stage2_l0/src/tokens.l0`](compiler/stage2_l0/src/tokens.md)

## Shared
""",
        encoding="utf-8",
    )
    (input_dir / "compiler/stage1_py/demo.md").write_text(
        """# compiler/stage1_py/demo.py

Source: `compiler/stage1_py/demo.py`
Language: `Python`

<a id="function-demo"></a>

Demo summary.

See [tokens](../stage2_l0/src/tokens.md#enum-tokentype).
""",
        encoding="utf-8",
    )
    (input_dir / "compiler/stage2_l0/src/tokens.md").write_text(
        """# compiler/stage2_l0/src/tokens.l0

Module: `tokens`

Source: `compiler/stage2_l0/src/tokens.l0`
Language: `Dea/L0`

Token docs.
""",
        encoding="utf-8",
    )
    (input_dir / "docs-mainpage-html.md").write_text("# temp mainpage\n", encoding="utf-8")

    export_markdown_tree(
        input_dir,
        output_dir,
        docs_prefix="api/reference",
        tab_title="API",
        tab_icon="fas fa-book",
        tab_order=5,
        html_site_url="https://example.com/api/",
        pdf_url="https://example.com/api/pdf/dea_l0_api_reference.pdf",
    )

    page = (output_dir / "api/reference/compiler/stage1_py/demo.md").read_text(encoding="utf-8")
    tab = (output_dir / "_tabs/api.md").read_text(encoding="utf-8")

    assert 'title: "demo.py"' in page
    assert "permalink: /api/reference/compiler/stage1_py/demo/" in page
    assert not page.splitlines()[6].startswith("# ")
    assert '<span id="file-demopy"></span>' in page
    assert '<span id="function-demo"></span>' in page
    assert '<a id="function-demo"></a>' not in page
    assert "[tokens]({{ '/api/reference/compiler/stage2_l0/src/tokens/' | relative_url }}#enum-tokentype)" in page

    assert 'title: "API"' in tab
    assert "permalink: /api/" in tab
    assert "[Standalone HTML reference](https://example.com/api/)" in tab
    assert "[PDF reference](https://example.com/api/pdf/dea_l0_api_reference.pdf)" in tab
    assert "**Release" not in tab
    assert "- [compiler/stage1_py/demo.py]({{ '/api/reference/compiler/stage1_py/demo/' | relative_url }})" in tab
    assert not (output_dir / "api/reference/docs-mainpage-html.md").exists()


def test_parse_args_accepts_release_tag(tmp_path: Path) -> None:
    args = parse_args(["--input", str(tmp_path / "in"), "--output", str(tmp_path / "out"), "--release-tag", "v0.9.1"])
    assert args.release_tag == "v0.9.1"


def test_export_markdown_tree_shows_release_tag(tmp_path: Path) -> None:
    input_dir = tmp_path / "markdown"
    output_dir = tmp_path / "blog-export"
    (input_dir / "compiler/stage1_py").mkdir(parents=True)

    (input_dir / "index.md").write_text(
        "# Index\n\n## Stage 1\n\n"
        "- [`compiler/stage1_py/demo.py`](compiler/stage1_py/demo.md)\n\n"
        "## Stage 2\n\n## Shared\n",
        encoding="utf-8",
    )
    (input_dir / "compiler/stage1_py/demo.md").write_text(
        "# compiler/stage1_py/demo.py\n\nSource: `compiler/stage1_py/demo.py`\n\nDemo.\n",
        encoding="utf-8",
    )

    export_markdown_tree(
        input_dir,
        output_dir,
        docs_prefix="api/reference",
        tab_title="API",
        tab_icon="fas fa-book",
        tab_order=5,
        html_site_url="https://example.com/api/",
        pdf_url="https://github.com/googlielmo/dea-lang/releases/download/v0.9.1/refman.pdf",
        release_tag="v0.9.1",
    )

    tab = (output_dir / "_tabs/api.md").read_text(encoding="utf-8")
    assert "**Release v0.9.1**" in tab
    assert "[PDF reference](https://github.com/googlielmo/dea-lang/releases/download/v0.9.1/refman.pdf)" in tab
    # Release tag appears before the links.
    tag_pos = tab.index("**Release v0.9.1**")
    link_pos = tab.index("[Standalone HTML reference]")
    assert tag_pos < link_pos
