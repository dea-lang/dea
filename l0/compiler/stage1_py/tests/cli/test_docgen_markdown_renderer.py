# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for XML-to-Markdown rendering."""

from pathlib import Path

from compiler.docgen.l0_docgen_markdown import (
    normalize_search_result_urls,
    render_compat_redirect_pages,
    render_curated_html_site,
    render_markdown_site,
    render_raw_reference_backlinks,
    rewrite_and_prune_raw_html_surface,
)


def test_render_markdown_site_creates_file_page(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "demo_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8py" kind="file" language="Python">
    <compoundname>demo.py</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="demo_8py_1a" prot="public">
        <definition>demo.add</definition>
        <argsstring>(x, y)</argsstring>
        <name>add</name>
        <briefdescription>
          <para>Add two values.</para>
        </briefdescription>
        <detaileddescription>
          <para>
            <parameterlist kind="param">
              <parameteritem>
                <parameternamelist><parametername>x</parametername></parameternamelist>
                <parameterdescription><para>Left operand.</para></parameterdescription>
              </parameteritem>
              <parameteritem>
                <parameternamelist><parametername>y</parametername></parameternamelist>
                <parameterdescription><para>Right operand.</para></parameterdescription>
              </parameteritem>
            </parameterlist>
            <simplesect kind="return"><para>Computed sum.</para></simplesect>
            <simplesect kind="see"><para><ref refid="demo_8py_1b" kindref="member">multiply</ref> for repeated addition.</para></simplesect>
          </para>
        </detaileddescription>
        <location file="compiler/stage1_py/demo.py" line="1" />
      </memberdef>
      <memberdef kind="function" id="demo_8py_1b" prot="public">
        <definition>demo.multiply</definition>
        <argsstring>(x, y)</argsstring>
        <name>multiply</name>
        <briefdescription>
          <para>Multiply two values.</para>
        </briefdescription>
        <location file="compiler/stage1_py/demo.py" line="5" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage1_py/demo.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage1_py/demo.md").read_text(encoding="utf-8")
    index_page = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "# compiler/stage1_py/demo.py" in page
    assert "Add two values." in page
    assert "- `x`: Left operand." in page
    assert "- `y`: Right operand." in page
    assert "Returns: Computed sum." in page
    assert "See also:" in page
    assert "- [multiply](#function-demomultiply) for repeated addition." in page
    assert "- [`compiler/stage1_py/demo.py`](compiler/stage1_py/demo.md)" in index_page


def test_render_markdown_site_preserves_itemized_lists(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "demo_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8py" kind="file" language="Python">
    <compoundname>demo.py</compoundname>
    <innerclass refid="class_demo_1_1_emitter">demo::Emitter</innerclass>
    <location file="compiler/stage1_py/demo.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "class_demo_1_1_emitter.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="class_demo_1_1_emitter" kind="class" language="Python">
    <compoundname>demo::Emitter</compoundname>
    <briefdescription><para>C-specific code emitter.</para></briefdescription>
    <detaileddescription>
      <para>Responsibilities:</para>
      <para><itemizedlist>
        <listitem><para>Emit C syntax.</para></listitem>
        <listitem><para>Name mangling for C.</para></listitem>
        <listitem><para>Type emission (<ref refid="struct_type" kindref="compound">Type</ref> lowering).</para></listitem>
      </itemizedlist></para>
      <para>Does NOT:</para>
      <para><itemizedlist>
        <listitem><para>Perform semantic analysis.</para></listitem>
        <listitem><para>Manage scopes or lifetimes.</para></listitem>
      </itemizedlist></para>
    </detaileddescription>
    <location file="compiler/stage1_py/demo.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_type.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_type" kind="struct" language="C++">
    <compoundname>Type</compoundname>
    <location file="compiler/stage2_l0/src/types.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage1_py/demo.md").read_text(encoding="utf-8")
    assert "Responsibilities:" in page
    assert "- Emit C syntax." in page
    assert "- Name mangling for C." in page
    assert "[Type](../stage2_l0/src/types.md#struct-type) lowering" in page
    assert "Does NOT:" in page
    assert "- Perform semantic analysis." in page
    assert "- Manage scopes or lifetimes." in page


def test_render_markdown_site_links_namespaced_compounds_with_heading_anchors(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "l0_ast_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0_ast_8py" kind="file" language="Python">
    <compoundname>l0_ast.py</compoundname>
    <innerclass refid="classl0__ast_1_1_node">l0_ast::Node</innerclass>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "classl0__ast_1_1_node.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__ast_1_1_node" kind="class" language="Python">
    <compoundname>l0_ast::Node</compoundname>
    <briefdescription><para>AST base node.</para></briefdescription>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "l0_ast_printer_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0_ast_printer_8py" kind="file" language="Python">
    <compoundname>l0_ast_printer.py</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="l0_ast_printer_8py_1a" prot="public">
        <definition>l0_ast_printer.format_node</definition>
        <argsstring>(node, indent=0)</argsstring>
        <name>format_node</name>
        <briefdescription>
          <para>Recursively prints child <ref refid="classl0__ast_1_1_node" kindref="compound">Node</ref>.</para>
        </briefdescription>
        <location file="compiler/stage1_py/l0_ast_printer.py" line="1" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage1_py/l0_ast_printer.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    ast_page = (output_dir / "compiler/stage1_py/l0_ast.md").read_text(encoding="utf-8")
    printer_page = (output_dir / "compiler/stage1_py/l0_ast_printer.md").read_text(encoding="utf-8")
    assert '<a id="class-l0_astnode"></a>' in ast_page
    assert "## Class `l0_ast::Node`" in ast_page
    assert "[Node](l0_ast.md#class-l0_astnode)" in printer_page


def test_render_markdown_site_prefers_stage1_module_for_stage1_page_refs(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "l0_ast_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0_ast_8py" kind="file" language="Python">
    <compoundname>l0_ast.py</compoundname>
    <innerclass refid="classl0__ast_1_1_module">l0_ast::Module</innerclass>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "classl0__ast_1_1_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__ast_1_1_module" kind="class" language="Python">
    <compoundname>l0_ast::Module</compoundname>
    <briefdescription><para>Python Stage 1 module node.</para></briefdescription>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "ast_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="ast_8l0" kind="file" language="C++">
    <compoundname>ast.l0</compoundname>
    <innerstruct refid="struct_module">Module</innerstruct>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_module" kind="struct" language="C++">
    <compoundname>Module</compoundname>
    <briefdescription><para>Stage 2 module struct.</para></briefdescription>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "namespacel0__ast__printer.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="namespacel0__ast__printer" kind="namespace" language="Python">
    <compoundname>l0_ast_printer</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="namespacel0__ast__printer_1a" prot="public">
        <definition>str l0_ast_printer.format_module</definition>
        <argsstring>(Module mod)</argsstring>
        <name>format_module</name>
        <qualifiedname>l0_ast_printer.format_module</qualifiedname>
        <briefdescription>
          <para>Pretty-print a <ref refid="struct_module" kindref="compound">Module</ref>.</para>
        </briefdescription>
        <location file="compiler/stage1_py/l0_ast_printer.py" line="1" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage1_py/l0_ast_printer.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "l0_ast_printer_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0_ast_printer_8py" kind="file" language="Python">
    <compoundname>l0_ast_printer.py</compoundname>
    <innernamespace refid="namespacel0__ast__printer">l0_ast_printer</innernamespace>
    <location file="compiler/stage1_py/l0_ast_printer.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage1_py/l0_ast_printer.md").read_text(encoding="utf-8")
    assert "[Module](l0_ast.md#class-l0_astmodule)" in page
    assert "stage2_l0/src/ast.md#struct-module" not in page


def test_render_markdown_site_prefers_stage2_module_for_stage2_page_refs(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "l0_ast_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0_ast_8py" kind="file" language="Python">
    <compoundname>l0_ast.py</compoundname>
    <innerclass refid="classl0__ast_1_1_module">l0_ast::Module</innerclass>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "classl0__ast_1_1_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__ast_1_1_module" kind="class" language="Python">
    <compoundname>l0_ast::Module</compoundname>
    <briefdescription><para>Python Stage 1 module node.</para></briefdescription>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "ast_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="ast_8l0" kind="file" language="C++">
    <compoundname>ast.l0</compoundname>
    <innerstruct refid="struct_module">Module</innerstruct>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_module" kind="struct" language="C++">
    <compoundname>Module</compoundname>
    <briefdescription><para>Stage 2 module struct.</para></briefdescription>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "l0c_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0c_8l0" kind="file" language="C++">
    <compoundname>l0c.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="l0c_8l0_1a" prot="public">
        <definition>func l0c_run</definition>
        <argsstring>() -&gt; int</argsstring>
        <name>l0c_run</name>
        <briefdescription>
          <para>Uses <ref refid="classl0__ast_1_1_module" kindref="compound">Module</ref> metadata.</para>
        </briefdescription>
        <location file="compiler/stage2_l0/src/l0c.l0" line="1" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/l0c.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/l0c.md").read_text(encoding="utf-8")
    assert "[Module](ast.md#struct-module)" in page
    assert "stage1_py/l0_ast.md#class-l0_astmodule" not in page


def test_render_markdown_site_drops_stage1_link_on_stage2_page_without_local_match(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "namespacel0c.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="namespacel0c" kind="namespace" language="Python">
    <compoundname>l0c</compoundname>
    <location file="compiler/stage1_py/l0c.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "demo_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8l0" kind="file" language="C++">
    <compoundname>demo.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="demo_8l0_1a" prot="public">
        <definition>func main</definition>
        <argsstring>()</argsstring>
        <name>main</name>
        <briefdescription>
          <para>Run the Stage 2 <ref refid="namespacel0c" kindref="compound">l0c</ref> entry point.</para>
        </briefdescription>
        <location file="compiler/stage2_l0/src/demo.l0" line="1" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/demo.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/demo.md").read_text(encoding="utf-8")
    assert "`l0c` entry point." in page
    assert "stage1_py/l0c.md#namespace-l0c" not in page


def test_render_markdown_site_renders_enum_variants(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"
    source_path = tmp_path / "compiler/stage2_l0/src/util/diag.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """enum DiagnosticSeverity {
    Error;
    Warning;
    Note;
}
""",
        encoding="utf-8",
    )

    (xml_dir / "diag_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="diag_8l0" kind="file" language="C++">
    <compoundname>diag.l0</compoundname>
    <sectiondef kind="enum">
      <memberdef kind="enum" id="diag_8l0_1a" prot="public" static="no" strong="no">
        <type></type>
        <name>DiagnosticSeverity</name>
        <enumvalue id="diag_8l0_1a1" prot="public"><name>Error</name></enumvalue>
        <enumvalue id="diag_8l0_1a2" prot="public"><name>Warning</name></enumvalue>
        <enumvalue id="diag_8l0_1a3" prot="public"><name>Note</name></enumvalue>
        <briefdescription><para>Defines the DiagnosticSeverity enumeration.</para></briefdescription>
        <location file="compiler/stage2_l0/src/util/diag.l0" line="1" bodystart="1" bodyend="5" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/util/diag.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/util/diag.md").read_text(encoding="utf-8")
    assert "## Enum `DiagnosticSeverity`" in page
    assert "Variants:" in page
    assert "- `Error`" in page
    assert "- `Warning`" in page
    assert "- `Note`" in page


def test_render_markdown_site_renders_l0_type_alias_initializer(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "ast_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="ast_8l0" kind="file" language="C++">
    <compoundname>ast.l0</compoundname>
    <sectiondef kind="var">
      <memberdef kind="variable" id="ast_8l0_1a_exprid" prot="public" static="no" mutable="no">
        <type>type</type>
        <definition>type ExprId</definition>
        <name>ExprId</name>
        <initializer>= int</initializer>
        <location file="compiler/stage2_l0/src/ast.l0" line="17" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/ast.md").read_text(encoding="utf-8")
    assert "## Type Alias `ExprId`" in page
    assert "type ExprId = int" in page


def test_render_markdown_site_renders_payload_enum_variants_from_source(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"
    source_path = tmp_path / "compiler/stage2_l0/src/tokens.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """enum TokenType {
    TT_EOF;
    TT_IDENT(text: string);
    TT_INT(text: string, value: int);
}
""",
        encoding="utf-8",
    )

    (xml_dir / "tokens_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="tokens_8l0" kind="file" language="C++">
    <compoundname>tokens.l0</compoundname>
    <sectiondef kind="enum">
      <memberdef kind="enum" id="tokens_8l0_1a" prot="public" static="no" strong="no">
        <type></type>
        <name>TokenType</name>
        <enumvalue id="tokens_8l0_1a1" prot="public"><name>TT_EOF</name></enumvalue>
        <briefdescription><para>Defines the TokenType enumeration.</para></briefdescription>
        <location file="compiler/stage2_l0/src/tokens.l0" line="1" bodystart="1" bodyend="5" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/tokens.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/tokens.md").read_text(encoding="utf-8")
    assert "- `TT_EOF`" in page
    assert "- `TT_IDENT(text: string)`" in page
    assert "- `TT_INT(text: string, value: int)`" in page


def test_render_markdown_site_does_not_treat_function_bodies_as_enum_variants(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"
    source_path = tmp_path / "compiler/stage2_l0/src/tokens.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """func token_to_string(token: Token) -> string {
    match (token.token_type) {
        TT_EOF => { return "end-of-file"; }
    }
}
""",
        encoding="utf-8",
    )

    (xml_dir / "tokens_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="tokens_8l0" kind="file" language="C++">
    <compoundname>tokens.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="tokens_8l0_1a" prot="public">
        <type>func</type>
        <definition>func token_to_string</definition>
        <argsstring>(token:Token) -&gt; string</argsstring>
        <name>token_to_string</name>
        <briefdescription><para>Render a token as human-readable text.</para></briefdescription>
        <location file="compiler/stage2_l0/src/tokens.l0" line="1" bodystart="1" bodyend="5" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/tokens.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/tokens.md").read_text(encoding="utf-8")
    assert "## Function `token_to_string`" in page
    assert "Render a token as human-readable text." in page
    assert "func token_to_string(token: Token) -> string" in page
    assert "Variants:" not in page
    assert "match (token.token_type)" not in page


def test_render_markdown_site_renders_struct_members_in_l0_style(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "diag_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="diag_8l0" kind="file" language="C++">
    <compoundname>diag.l0</compoundname>
    <innerstruct refid="struct_diagnostic">Diagnostic</innerstruct>
    <location file="compiler/stage2_l0/src/util/diag.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_diagnostic.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_diagnostic" kind="struct" language="C++" prot="public">
    <compoundname>Diagnostic</compoundname>
    <sectiondef kind="public-attrib">
      <memberdef kind="variable" id="struct_diagnostic_1a" prot="public">
        <type>string</type>
        <definition>string Diagnostic::phase</definition>
        <name>phase</name>
        <qualifiedname>Diagnostic::phase</qualifiedname>
        <location file="compiler/stage2_l0/src/util/diag.l0" line="2" />
      </memberdef>
    </sectiondef>
    <briefdescription>
      <para><ref refid="struct_diagnostic" kindref="compound">Diagnostic</ref> represents an error.</para>
    </briefdescription>
    <detaileddescription>
      <para>Includes source location details.</para>
    </detaileddescription>
    <location file="compiler/stage2_l0/src/util/diag.l0" line="1" bodystart="1" bodyend="3" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/util/diag.md").read_text(encoding="utf-8")
    assert "## Struct `Diagnostic`" in page
    assert "[Diagnostic](#struct-diagnostic) represents an error." in page
    assert "### Diagnostic Field `phase`" in page
    assert "phase: string" in page
    assert "Diagnostic::phase: string" not in page


def test_render_markdown_site_renders_c_struct_members_with_member_data_and_bitfields(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "l0__runtime_8h.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0__runtime_8h" kind="file" language="C">
    <compoundname>compiler/shared/runtime/l0_runtime.h</compoundname>
    <innerstruct refid="structl0__string">l0_string</innerstruct>
    <location file="compiler/shared/runtime/l0_runtime.h" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "structl0__string.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="structl0__string" kind="struct" language="C++" prot="public">
    <compoundname>l0_string</compoundname>
    <sectiondef kind="public-attrib">
      <memberdef kind="variable" id="structl0__string_kind" prot="public" static="no" mutable="no">
        <type>unsigned int</type>
        <definition>unsigned int l0_string::kind</definition>
        <name>kind</name>
        <qualifiedname>l0_string::kind</qualifiedname>
        <bitfield>1</bitfield>
        <briefdescription><para>Kind of string.</para></briefdescription>
        <location file="compiler/shared/runtime/l0_runtime.h" line="10" />
      </memberdef>
      <memberdef kind="variable" id="structl0__string_int" prot="public" static="no" mutable="no">
        <type>unsigned</type>
        <definition>unsigned l0_string::int</definition>
        <name>int</name>
        <qualifiedname>l0_string::int</qualifiedname>
        <bitfield>0</bitfield>
        <briefdescription><para>Alignment boundary.</para></briefdescription>
        <location file="compiler/shared/runtime/l0_runtime.h" line="11" />
      </memberdef>
      <memberdef kind="variable" id="structl0__string_s_str" prot="public" static="no" mutable="no">
        <type>struct l0_string::@002303017346171041326120020165247372035106052264::@032015275323014106025236100337221307303275114220</type>
        <definition>struct l0_string::@002303017346171041326120020165247372035106052264::@032015275323014106025236100337221307303275114220 l0_string::s_str</definition>
        <name>s_str</name>
        <qualifiedname>l0_string::s_str</qualifiedname>
        <briefdescription><para>Static string data.</para></briefdescription>
        <location file="compiler/shared/runtime/l0_runtime.h" line="12" />
      </memberdef>
      <memberdef kind="variable" id="structl0__string_data" prot="public" static="no" mutable="no">
        <type>union l0_string::@002303017346171041326120020165247372035106052264</type>
        <definition>union l0_string::@002303017346171041326120020165247372035106052264 l0_string::data</definition>
        <name>data</name>
        <qualifiedname>l0_string::data</qualifiedname>
        <location file="compiler/shared/runtime/l0_runtime.h" line="13" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/runtime/l0_runtime.h" line="9" bodystart="9" bodyend="14" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/shared/runtime/l0_runtime.md").read_text(encoding="utf-8")
    assert "## Struct `l0_string`" in page
    assert "### Member Data `l0_string::kind`" in page
    assert "### Member Data `l0_string::int`" in page
    assert "unsigned int kind: 1" in page
    assert "unsigned int: 0" in page
    assert "struct s_str" in page
    assert "union data" in page
    assert "### Variable `l0_string::kind`" not in page
    assert "kind: unsigned int" not in page
    assert "::@" not in page


def test_render_markdown_site_preserves_l0_signature_prefix_and_expands_link_label(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "l0__runtime_8h.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0__runtime_8h" kind="file" language="C">
    <compoundname>compiler/shared/runtime/l0_runtime.h</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="l0__runtime_8h_1a_slice" prot="public" static="yes">
        <type>l0_string</type>
        <definition>static l0_string rt_string_slice</definition>
        <argsstring>(l0_string s, l0_int start, l0_int end)</argsstring>
        <name>rt_string_slice</name>
        <briefdescription><para>Create a substring.</para></briefdescription>
        <detaileddescription>
          <para>
            <parameterlist kind="param">
              <parameteritem>
                <parameternamelist><parametername>s</parametername></parameternamelist>
                <parameterdescription><para>Source string.</para></parameterdescription>
              </parameteritem>
            </parameterlist>
            <simplesect kind="return"><para>Slice string.</para></simplesect>
            L0 signature: <computeroutput>extern func <ref refid="rt_8l0_1a_slice" kindref="member">rt_string_slice(s: string, start: int, end: int)</ref> -&gt; string;</computeroutput>
          </para>
        </detaileddescription>
        <location file="compiler/shared/runtime/l0_runtime.h" line="100" />
      </memberdef>
      <memberdef kind="function" id="l0__runtime_8h_1a_free" prot="public" static="yes">
        <type>void</type>
        <definition>static void rt_free</definition>
        <argsstring>(void *ptr)</argsstring>
        <name>rt_free</name>
        <briefdescription><para>Free allocated pointer.</para></briefdescription>
        <detaileddescription>
            <para>L0 signature: <computeroutput>extern func <ref refid="memory_8l0_1a_free" kindref="member">rt_free</ref>(ptr: void*?) -&gt; void;</computeroutput></para>
        </detaileddescription>
        <location file="compiler/shared/runtime/l0_runtime.h" line="120" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/runtime/l0_runtime.h" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "rt_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="rt_8l0" kind="file" language="C++">
    <compoundname>rt.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="rt_8l0_1a_slice" prot="public" extern="yes">
        <type>string</type>
        <definition>string rt_string_slice</definition>
        <argsstring>(string s, int start, int end)</argsstring>
        <name>rt_string_slice</name>
        <param>
          <type>string</type>
          <declname>s</declname>
        </param>
        <param>
          <type>int</type>
          <declname>start</declname>
        </param>
        <param>
          <type>int</type>
          <declname>end</declname>
        </param>
        <location file="compiler/shared/l0/stdlib/sys/rt.l0" line="10" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/l0/stdlib/sys/rt.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "memory_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="memory_8l0" kind="file" language="C++">
    <compoundname>memory.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="memory_8l0_1a_free" prot="public" extern="yes">
        <type>void</type>
        <definition>void rt_free</definition>
        <argsstring>(void *ptr)</argsstring>
        <name>rt_free</name>
        <param>
          <type>void *</type>
          <declname>ptr</declname>
        </param>
        <location file="compiler/shared/l0/stdlib/sys/memory.l0" line="10" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/l0/stdlib/sys/memory.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/shared/runtime/l0_runtime.md").read_text(encoding="utf-8")
    assert (
        "L0 signature: extern [func rt_string_slice(s: string, start: int, end: int) -> string]"
        "(../l0/stdlib/sys/rt.md#function-rt_string_slice);"
    ) in page
    assert "L0 signature: extern [func rt_free(ptr: void*?) -> void](../l0/stdlib/sys/memory.md#function-rt_free);" in page
    rt_page = (output_dir / "compiler/shared/l0/stdlib/sys/rt.md").read_text(encoding="utf-8")
    memory_page = (output_dir / "compiler/shared/l0/stdlib/sys/memory.md").read_text(encoding="utf-8")
    assert "extern func rt_string_slice(s: string, start: int, end: int) -> string" in rt_page
    assert "extern func rt_free(ptr: void*?) -> void" in memory_page


def test_render_markdown_site_recovers_nullable_l0_function_signatures_from_source(
    tmp_path: Path, monkeypatch
) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    source_path = tmp_path / "compiler/shared/l0/stdlib/sys/memory.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """module sys.memory;

extern func rt_alloc(bytes: int) -> void*?;
extern func rt_free(ptr: void*?) -> void;
""",
        encoding="utf-8",
    )

    (xml_dir / "memory_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="memory_8l0" kind="file" language="C++">
    <compoundname>memory.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="memory_8l0_1a_alloc" prot="public" extern="yes">
        <type>void *</type>
        <definition>void * rt_alloc</definition>
        <argsstring>(int bytes)</argsstring>
        <name>rt_alloc</name>
        <param>
          <type>int</type>
          <declname>bytes</declname>
        </param>
        <location file="compiler/shared/l0/stdlib/sys/memory.l0" line="3" declline="3" />
      </memberdef>
      <memberdef kind="function" id="memory_8l0_1a_free" prot="public" extern="yes">
        <type>void</type>
        <definition>void rt_free</definition>
        <argsstring>(void *ptr)</argsstring>
        <name>rt_free</name>
        <param>
          <type>void *</type>
          <declname>ptr</declname>
        </param>
        <location file="compiler/shared/l0/stdlib/sys/memory.l0" line="4" declline="4" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/l0/stdlib/sys/memory.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/shared/l0/stdlib/sys/memory.md").read_text(encoding="utf-8")
    assert "extern func rt_alloc(bytes: int) -> void*?" in page
    assert "extern func rt_free(ptr: void*?) -> void" in page


def test_render_markdown_site_recovers_l0_top_level_let_from_source(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    source_path = tmp_path / "compiler/shared/l0/stdlib/std/hashset.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """module std.hashset;

let HS_EMPTY: byte = 0;
""",
        encoding="utf-8",
    )

    (xml_dir / "hashset_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="hashset_8l0" kind="file" language="C++">
    <compoundname>hashset.l0</compoundname>
    <sectiondef kind="var">
      <memberdef kind="variable" id="hashset_8l0_1a_empty" prot="public">
        <type>let</type>
        <definition>let HS_EMPTY</definition>
        <name>HS_EMPTY</name>
        <location file="compiler/shared/l0/stdlib/std/hashset.l0" line="3" />
      </memberdef>
    </sectiondef>
    <location file="compiler/shared/l0/stdlib/std/hashset.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/shared/l0/stdlib/std/hashset.md").read_text(encoding="utf-8")
    assert "let HS_EMPTY: byte = 0" in page


def test_render_markdown_site_recovers_nullable_l0_struct_fields_from_source(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    source_path = tmp_path / "compiler/stage2_l0/src/ast.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """module ast;

struct TypeRef {
    module_path: StringVector*?;   // string entries
}
""",
        encoding="utf-8",
    )

    (xml_dir / "ast_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="ast_8l0" kind="file" language="C++">
    <compoundname>ast.l0</compoundname>
    <innerstruct refid="struct_type_ref">TypeRef</innerstruct>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_type_ref.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_type_ref" kind="struct" language="C++" prot="public">
    <compoundname>TypeRef</compoundname>
    <sectiondef kind="public-attrib">
      <memberdef kind="variable" id="struct_type_ref_1a_module_path" prot="public">
        <type>StringVector *</type>
        <definition>StringVector * TypeRef::module_path</definition>
        <name>module_path</name>
        <qualifiedname>TypeRef::module_path</qualifiedname>
        <location file="compiler/stage2_l0/src/ast.l0" line="4" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/ast.l0" line="3" bodystart="3" bodyend="5" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/ast.md").read_text(encoding="utf-8")
    assert "module_path: StringVector*?" in page


def test_render_markdown_site_uses_display_language_mapping_for_l0(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "diag_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="diag_8l0" kind="file" language="C++">
    <compoundname>diag.l0</compoundname>
    <location file="compiler/stage2_l0/src/util/diag.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/util/diag.md").read_text(encoding="utf-8")
    assert "Language: `Dea/L0`" in page


def test_render_markdown_site_excludes_nested_struct_members_from_file_symbols(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "demo_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8l0" kind="file" language="C++">
    <compoundname>demo.l0</compoundname>
    <innerstruct refid="struct_demo_state">DemoState</innerstruct>
    <sectiondef kind="var">
      <memberdef kind="variable" id="demo_8l0_1a_field" prot="public">
        <type>int</type>
        <definition>int count</definition>
        <name>count</name>
        <location file="compiler/stage2_l0/src/demo.l0" line="3" />
      </memberdef>
    </sectiondef>
    <sectiondef kind="func">
      <memberdef kind="function" id="demo_8l0_1a_func" prot="public">
        <definition>func demo_run</definition>
        <argsstring>()</argsstring>
        <name>demo_run</name>
        <location file="compiler/stage2_l0/src/demo.l0" line="8" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/demo.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_demo_state.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_demo_state" kind="struct" language="C++" prot="public">
    <compoundname>DemoState</compoundname>
    <sectiondef kind="public-attrib">
      <memberdef kind="variable" id="struct_demo_state_1a_field" prot="public">
        <type>int</type>
        <definition>int DemoState::count</definition>
        <name>count</name>
        <location file="compiler/stage2_l0/src/demo.l0" line="3" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/demo.l0" line="2" bodystart="2" bodyend="4" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/demo.md").read_text(encoding="utf-8")
    assert "## Function `demo_run`" in page
    assert "\n## `count`\n" not in page
    assert "### DemoState Field `count`" in page


def test_render_markdown_site_excludes_struct_fields_from_file_symbols_using_source_ranges(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    source_path = tmp_path / "compiler/stage2_l0/src/demo.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        """struct HiddenState {
    count: int;
}

func demo_run() -> int {
    return 0;
}
""",
        encoding="utf-8",
    )

    (xml_dir / "demo_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8l0" kind="file" language="C++">
    <compoundname>demo.l0</compoundname>
    <sectiondef kind="var">
      <memberdef kind="variable" id="demo_8l0_1a_field" prot="public">
        <type>int</type>
        <definition>int count</definition>
        <name>count</name>
        <location file="compiler/stage2_l0/src/demo.l0" line="2" />
      </memberdef>
    </sectiondef>
    <sectiondef kind="func">
      <memberdef kind="function" id="demo_8l0_1a_func" prot="public">
        <definition>func demo_run</definition>
        <argsstring>()</argsstring>
        <name>demo_run</name>
        <location file="compiler/stage2_l0/src/demo.l0" line="5" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/demo.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/demo.md").read_text(encoding="utf-8")
    assert "## Function `demo_run`" in page
    assert "\n## `count`\n" not in page


def test_render_curated_html_site_creates_group_and_file_pages(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    page = markdown_dir / "compiler/stage2_l0/src/analysis.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# compiler/stage2_l0/src/analysis.l0

Source: `compiler/stage2_l0/src/analysis.l0`
Language: `C++`

## Symbols

- [analysis_analyze_entry](#symbol-analysis)

<a id="symbol-analysis"></a>
## `analysis_analyze_entry`

```text
func analysis_analyze_entry(search_paths: SourceSearchPaths*) -> AnalysisResult*
```

Analyzes the entry module.
""",
        encoding="utf-8",
    )

    (xml_dir / "analysis_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="analysis_8l0" kind="file" language="C++">
    <compoundname>analysis.l0</compoundname>
    <innerclass refid="struct_analysis_result">AnalysisResult</innerclass>
    <location file="compiler/stage2_l0/src/analysis.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    html_dir.mkdir(parents=True)
    (html_dir / "struct_analysis_result.html").write_text("<html></html>\n", encoding="utf-8")

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    stage2 = (html_dir / "stage2.html").read_text(encoding="utf-8")
    file_page = (html_dir / "api/compiler/stage2_l0/src/analysis.html").read_text(encoding="utf-8")
    assert 'href="api/compiler/stage2_l0/src/analysis.html"' in stage2
    assert 'href="struct_analysis_result.html"' in stage2
    assert 'class="m-doc-browse-entry-main-link"' in stage2
    assert 'class="m-doc-browse-entry-grid"' in stage2
    assert 'class="m-doc-browse-entry-ref"' in stage2
    assert 'class="m-doc-browse-entry-ref-list"' in stage2
    assert 'class="m-doc-browse-entry-ref-item"' in stage2
    assert "Reference pages</p>" not in stage2
    assert stage2.count("compiler/stage2_l0/src/analysis.l0") == 1
    assert "Struct</span>" in stage2
    assert "<h2><code>analysis_analyze_entry</code></h2>" in file_page
    assert "Analyzes the entry module." in file_page
    assert "func analysis_analyze_entry(search_paths: SourceSearchPaths*) -&gt; AnalysisResult*" in file_page
    assert 'href="../../../../struct_analysis_result.html"' in file_page
    assert "Struct</span>" in file_page
    assert "Reference Pages" in file_page
    assert "annotated.html" not in stage2
    assert "annotated.html" not in file_page
    assert 'id="search"' in stage2
    assert "search-v2.js" in stage2
    assert 'href="./pdf/dea_l0_api_reference.pdf"' in stage2
    assert 'id="search"' in file_page
    assert "search-v2.js" in file_page
    assert 'href="../../../../pdf/dea_l0_api_reference.pdf"' in file_page


def test_render_curated_html_site_shows_source_path_when_title_differs(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    page = markdown_dir / "compiler/stage1_py/custom.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# Stage 1 Custom Page

Source: `compiler/stage1_py/custom.py`
Language: `Python`
""",
        encoding="utf-8",
    )

    (xml_dir / "custom_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="custom_8py" kind="file" language="Python">
    <compoundname>custom.py</compoundname>
    <location file="compiler/stage1_py/custom.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    stage1 = (html_dir / "stage1.html").read_text(encoding="utf-8")
    assert ">Stage 1 Custom Page<" in stage1
    assert "m-doc-browse-entry-source\">compiler/stage1_py/custom.py<" in stage1


def test_render_curated_html_site_excludes_non_source_pages_from_shared_index(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    shared_page = markdown_dir / "compiler/shared/runtime/l0_runtime.md"
    shared_page.parent.mkdir(parents=True, exist_ok=True)
    shared_page.write_text(
        """# compiler/shared/runtime/l0_runtime.h

Source: `compiler/shared/runtime/l0_runtime.h`
Language: `C`
""",
        encoding="utf-8",
    )

    non_source_page = markdown_dir / "docs-mainpage-html.md"
    non_source_page.write_text(
        """# docs-mainpage-html.md

Source: `docs-mainpage-html.md`
Language: `Markdown`
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    shared = (html_dir / "shared.html").read_text(encoding="utf-8")
    assert 'href="api/compiler/shared/runtime/l0_runtime.html"' in shared
    assert "docs-mainpage-html.md" not in shared
    assert 'href="api/docs-mainpage-html.html"' not in shared


def test_render_curated_html_site_uses_compound_kind_for_struct_reference_labels(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    page = markdown_dir / "compiler/shared/runtime/l0_runtime.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# compiler/shared/runtime/l0_runtime.h

Source: `compiler/shared/runtime/l0_runtime.h`
Language: `C`
""",
        encoding="utf-8",
    )

    (xml_dir / "l0__runtime_8h.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0__runtime_8h" kind="file" language="C">
    <compoundname>compiler/shared/runtime/l0_runtime.h</compoundname>
    <innerclass refid="structl0__opt__bool">l0_opt_bool</innerclass>
    <location file="compiler/shared/runtime/l0_runtime.h" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "structl0__opt__bool.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="structl0__opt__bool" kind="struct" language="C++">
    <compoundname>l0_opt_bool</compoundname>
    <location file="compiler/shared/runtime/l0_runtime.h" line="10" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    html_dir.mkdir(parents=True)
    (html_dir / "structl0__opt__bool.html").write_text("<html></html>\n", encoding="utf-8")

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    shared = (html_dir / "shared.html").read_text(encoding="utf-8")
    assert 'href="structl0__opt__bool.html"' in shared
    assert "Struct</span>" in shared
    assert "Class</span>" not in shared


def test_render_markdown_site_normalizes_l0_function_signature_spacing(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    output_dir = tmp_path / "markdown"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    (xml_dir / "driver_8l0.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="driver_8l0" kind="file" language="C++">
    <compoundname>driver.l0</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="driver_8l0_1a" prot="public">
        <type>bool</type>
        <definition>bool dr_sv_has</definition>
        <argsstring>(StringVector *items, string module_name)</argsstring>
        <name>dr_sv_has</name>
        <param>
          <type>StringVector *</type>
          <declname>items</declname>
        </param>
        <param>
          <type>string</type>
          <declname>module_name</declname>
        </param>
        <briefdescription><para>Check whether a module name is present.</para></briefdescription>
        <location file="compiler/stage2_l0/src/driver.l0" line="1" />
      </memberdef>
    </sectiondef>
    <location file="compiler/stage2_l0/src/driver.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_markdown_site(xml_dir, output_dir, templates_dir)

    page = (output_dir / "compiler/stage2_l0/src/driver.md").read_text(encoding="utf-8")
    assert "func dr_sv_has(items: StringVector*, module_name: string) -> bool" in page


def test_render_curated_html_site_keeps_stage1_page_as_hub(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    page = markdown_dir / "compiler/stage1_py/demo.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# compiler/stage1_py/demo.py

Source: `compiler/stage1_py/demo.py`
Language: `Python`

## Symbols

- [demo::Thing](#class-thing)

<a id="class-thing"></a>
## Class `demo::Thing`

This verbose class body should not appear on the curated Stage 1 hub page.
""",
        encoding="utf-8",
    )

    (xml_dir / "demo_8py.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="demo_8py" kind="file" language="Python">
    <compoundname>demo.py</compoundname>
    <sectiondef kind="func">
      <memberdef kind="function" id="demo_8py_1a" prot="public">
        <definition>demo.helper</definition>
        <argsstring>(value)</argsstring>
        <name>helper</name>
        <briefdescription><para>Small helper.</para></briefdescription>
        <location file="compiler/stage1_py/demo.py" line="3" />
      </memberdef>
    </sectiondef>
    <innerclass refid="classdemo_1_1_thing">demo::Thing</innerclass>
    <location file="compiler/stage1_py/demo.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    html_dir.mkdir(parents=True)
    (html_dir / "classdemo_1_1_thing.html").write_text("<html></html>\n", encoding="utf-8")

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    file_page = (html_dir / "api/compiler/stage1_py/demo.html").read_text(encoding="utf-8")
    assert "Reference Pages" in file_page
    assert 'href="../../../classdemo_1_1_thing.html"' in file_page
    assert "Module Members" in file_page
    assert "demo.helper(value)" in file_page
    assert "Small helper." in file_page
    assert "This verbose class body should not appear" not in file_page
    assert "Class <code>demo::Thing</code>" not in file_page


def test_render_compat_redirect_pages_creates_namespace_alias(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    markdown_page = markdown_dir / "compiler/stage1_py/l0_driver.md"
    markdown_page.parent.mkdir(parents=True, exist_ok=True)
    markdown_page.write_text(
        """# compiler/stage1_py/l0_driver.py

<a id="namespace-l0-driver"></a>
## Namespace `l0_driver`
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    (xml_dir / "namespacel0__driver.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="namespacel0__driver" kind="namespace" language="Python">
    <compoundname>l0_driver</compoundname>
    <location file="compiler/stage1_py/l0_driver.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_compat_redirect_pages(xml_dir, markdown_dir, html_dir, templates_dir)

    alias = (html_dir / "namespacel0__driver.html").read_text(encoding="utf-8")
    assert "api/compiler/stage1_py/l0_driver.html#namespace-l0_driver" in alias


def test_normalize_search_result_urls_rewrites_relative_links(tmp_path: Path) -> None:
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    search_js = html_dir / "search-v2.js"
    search_js.write_text(
        """var Search = {
    renderResults: /* istanbul ignore next */ function(resultsSuggestedTabAutocompletion) {
        let results = resultsSuggestedTabAutocompletion[0];
        let list = '';
        for(let i = 0; i != results.length; ++i) {
            list += '<li' + (i ? '' : ' id="search-current"') + '><a href="' + results[i].url + '" onmouseover="selectResult(event)">';
        }
    },
};
""",
        encoding="utf-8",
    )

    normalize_search_result_urls(html_dir)

    rewritten = search_js.read_text(encoding="utf-8")
    assert 'href="\' + this.resolveResultUrl(results[i].url) + \'"' in rewritten
    assert "resolveResultUrl: function(url) {" in rewritten
    assert "search-v[0-9]+\\.js" in rewritten


def test_normalize_search_result_urls_is_idempotent(tmp_path: Path) -> None:
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    search_js = html_dir / "search-v2.js"
    search_js.write_text(
        """var Search = {
    renderResults: /* istanbul ignore next */ function(resultsSuggestedTabAutocompletion) {
        let results = resultsSuggestedTabAutocompletion[0];
        let list = '';
        for(let i = 0; i != results.length; ++i) {
            list += '<li' + (i ? '' : ' id="search-current"') + '><a href="' + results[i].url + '" onmouseover="selectResult(event)">';
        }
    },
};
""",
        encoding="utf-8",
    )

    normalize_search_result_urls(html_dir)
    once = search_js.read_text(encoding="utf-8")
    normalize_search_result_urls(html_dir)
    twice = search_js.read_text(encoding="utf-8")

    assert once == twice
    assert once.count("resolveResultUrl: function(url) {") == 1


def test_normalize_search_result_urls_noop_when_search_js_missing(tmp_path: Path) -> None:
    html_dir = tmp_path / "html"
    html_dir.mkdir()
    normalize_search_result_urls(html_dir)


def test_rewrite_and_prune_raw_html_surface_rewrites_file_links_and_prunes_pages(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    markdown_page = markdown_dir / "compiler/shared/runtime/l0_runtime.md"
    markdown_page.parent.mkdir(parents=True, exist_ok=True)
    markdown_page.write_text(
        """# compiler/shared/runtime/l0_runtime.h

Source: `compiler/shared/runtime/l0_runtime.h`
Language: `C`
""",
        encoding="utf-8",
    )

    (xml_dir / "l0__runtime_8h.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="l0__runtime_8h" kind="file" language="C">
    <compoundname>compiler/shared/runtime/l0_runtime.h</compoundname>
    <location file="compiler/shared/runtime/l0_runtime.h" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "structl0__opt__bool.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="structl0__opt__bool" kind="struct" language="C++">
    <compoundname>l0_opt_bool</compoundname>
    <location file="compiler/shared/runtime/l0_runtime.h" line="10" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "dir_0a7b48d47eb638e59f8f8d787747200e.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="dir_0a7b48d47eb638e59f8f8d787747200e" kind="dir">
    <compoundname>compiler/shared/runtime</compoundname>
    <location file="compiler/shared/runtime/" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    struct_page = html_dir / "structl0__opt__bool.html"
    struct_page.write_text(
        """<!DOCTYPE html>
<html>
<body>
<div class="m-doc-include"><a class="cpf" href="l0__runtime_8h.html">&lt;compiler/shared/runtime/l0_runtime.h&gt;</a></div>
<p><a href="l0__runtime_8h.html#af2e730066892116db3c6848d67cbd246" class="m-doc">l0_bool</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )
    (html_dir / "l0__runtime_8h.html").write_text("<html>raw file page</html>\n", encoding="utf-8")
    (html_dir / "dir_0a7b48d47eb638e59f8f8d787747200e.html").write_text("<html>raw dir page</html>\n", encoding="utf-8")
    (html_dir / "files.html").write_text("<html>raw files index</html>\n", encoding="utf-8")

    rewrite_and_prune_raw_html_surface(xml_dir, markdown_dir, html_dir)

    rewritten = struct_page.read_text(encoding="utf-8")
    assert 'href="api/compiler/shared/runtime/l0_runtime.html"' in rewritten
    assert not (html_dir / "l0__runtime_8h.html").exists()
    assert not (html_dir / "dir_0a7b48d47eb638e59f8f8d787747200e.html").exists()
    assert not (html_dir / "files.html").exists()

    render_compat_redirect_pages(xml_dir, markdown_dir, html_dir, templates_dir)
    file_alias = (html_dir / "l0__runtime_8h.html").read_text(encoding="utf-8")
    dir_alias = (html_dir / "dir_0a7b48d47eb638e59f8f8d787747200e.html").read_text(encoding="utf-8")
    assert "api/compiler/shared/runtime/l0_runtime.html" in file_alias
    assert "shared.html" in dir_alias


def test_render_raw_reference_backlinks_adds_source_link(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    markdown_page = markdown_dir / "compiler/stage2_l0/src/tokens.md"
    markdown_page.parent.mkdir(parents=True, exist_ok=True)
    markdown_page.write_text(
        """# compiler/stage2_l0/src/tokens.l0

<a id="struct-tokenvector"></a>
## Struct `TokenVector`
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    (xml_dir / "struct_token_vector.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_token_vector" kind="struct" language="C++">
    <compoundname>TokenVector</compoundname>
    <location file="compiler/stage2_l0/src/tokens.l0" line="10" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    raw_page = html_dir / "struct_token_vector.html"
    raw_page.write_text(
        """<!DOCTYPE html>
<html>
<body>
<h1>TokenVector <span class="m-thin">struct</span></h1>
<p>Represents the <a href="struct_token_vector.html" class="m-doc">TokenVector</a> structure.</p>
</body>
</html>
""",
        encoding="utf-8",
    )

    render_raw_reference_backlinks(xml_dir, markdown_dir, html_dir)

    content = raw_page.read_text(encoding="utf-8")
    assert 'href="api/compiler/stage2_l0/src/tokens.html#struct-tokenvector"' in content
    assert "Defined in module <code>tokens</code>" in content
    assert ">tokens.l0</a>" in content


def test_render_raw_reference_backlinks_prefers_stage1_compound_links(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    compilation_page = markdown_dir / "compiler/stage1_py/l0_compilation.md"
    compilation_page.parent.mkdir(parents=True, exist_ok=True)
    compilation_page.write_text(
        """# compiler/stage1_py/l0_compilation.py

<a id="class-l0_compilationcompilationunit"></a>
## Class `l0_compilation::CompilationUnit`
""",
        encoding="utf-8",
    )
    ast_page = markdown_dir / "compiler/stage1_py/l0_ast.md"
    ast_page.parent.mkdir(parents=True, exist_ok=True)
    ast_page.write_text(
        """# compiler/stage1_py/l0_ast.py

<a id="class-l0_astmodule"></a>
## Class `l0_ast::Module`
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    (xml_dir / "classl0__compilation_1_1_compilation_unit.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__compilation_1_1_compilation_unit" kind="class" language="Python">
    <compoundname>l0_compilation::CompilationUnit</compoundname>
    <briefdescription>
      <para>Mapping to <ref refid="struct_module" kindref="compound">Module</ref> objects.</para>
    </briefdescription>
    <location file="compiler/stage1_py/l0_compilation.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "classl0__ast_1_1_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__ast_1_1_module" kind="class" language="Python">
    <compoundname>l0_ast::Module</compoundname>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_module" kind="struct" language="C++">
    <compoundname>Module</compoundname>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    raw_page = html_dir / "classl0__compilation_1_1_compilation_unit.html"
    raw_page.write_text(
        """<!DOCTYPE html>
<html>
<body>
<h1>CompilationUnit</h1>
<p>Mapping of modules to <a href="struct_module.html" class="m-doc">Module</a> objects.</p>
</body>
</html>
""",
        encoding="utf-8",
    )

    render_raw_reference_backlinks(xml_dir, markdown_dir, html_dir)

    content = raw_page.read_text(encoding="utf-8")
    assert 'href="classl0__ast_1_1_module.html"' in content
    assert 'href="struct_module.html"' not in content


def test_render_raw_reference_backlinks_rewrites_links_when_backlink_exists(tmp_path: Path) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"

    compilation_page = markdown_dir / "compiler/stage1_py/l0_compilation.md"
    compilation_page.parent.mkdir(parents=True, exist_ok=True)
    compilation_page.write_text(
        """# compiler/stage1_py/l0_compilation.py

<a id="class-l0_compilationcompilationunit"></a>
## Class `l0_compilation::CompilationUnit`
""",
        encoding="utf-8",
    )
    ast_page = markdown_dir / "compiler/stage1_py/l0_ast.md"
    ast_page.parent.mkdir(parents=True, exist_ok=True)
    ast_page.write_text(
        """# compiler/stage1_py/l0_ast.py

<a id="class-l0_astmodule"></a>
## Class `l0_ast::Module`
""",
        encoding="utf-8",
    )

    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    (xml_dir / "classl0__compilation_1_1_compilation_unit.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__compilation_1_1_compilation_unit" kind="class" language="Python">
    <compoundname>l0_compilation::CompilationUnit</compoundname>
    <location file="compiler/stage1_py/l0_compilation.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "classl0__ast_1_1_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="classl0__ast_1_1_module" kind="class" language="Python">
    <compoundname>l0_ast::Module</compoundname>
    <location file="compiler/stage1_py/l0_ast.py" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )
    (xml_dir / "struct_module.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_module" kind="struct" language="C++">
    <compoundname>Module</compoundname>
    <location file="compiler/stage2_l0/src/ast.l0" line="1" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    raw_page = html_dir / "classl0__compilation_1_1_compilation_unit.html"
    raw_page.write_text(
        """<!DOCTYPE html>
<html>
<body>
<h1>CompilationUnit</h1>
<p>Defined in module <code>l0_compilation</code> (<a href="api/compiler/stage1_py/l0_compilation.html#class-l0_compilationcompilationunit">l0_compilation.py</a>).</p>
<p>Mapping of modules to <a href="struct_module.html" class="m-doc">Module</a> objects.</p>
</body>
</html>
""",
        encoding="utf-8",
    )

    render_raw_reference_backlinks(xml_dir, markdown_dir, html_dir)

    content = raw_page.read_text(encoding="utf-8")
    assert 'href="classl0__ast_1_1_module.html"' in content
    assert 'href="struct_module.html"' not in content


def test_render_raw_reference_backlinks_uses_declared_l0_module_name(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"
    source_path = tmp_path / "compiler/shared/l0/stdlib/std/unit.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("module std.unit;\n", encoding="utf-8")

    markdown_page = markdown_dir / "compiler/shared/l0/stdlib/std/unit.md"
    markdown_page.parent.mkdir(parents=True, exist_ok=True)
    markdown_page.write_text(
        """# compiler/shared/l0/stdlib/std/unit.l0

<a id="struct-unit"></a>
## Struct `Unit`
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    (xml_dir / "struct_unit.xml").write_text(
        """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygen>
  <compounddef id="struct_unit" kind="struct" language="C++">
    <compoundname>Unit</compoundname>
    <location file="compiler/shared/l0/stdlib/std/unit.l0" line="10" />
  </compounddef>
</doxygen>
""",
        encoding="utf-8",
    )

    raw_page = html_dir / "struct_unit.html"
    raw_page.write_text(
        """<!DOCTYPE html>
<html>
<body>
<h1>Unit <span class="m-thin">struct</span></h1>
</body>
</html>
""",
        encoding="utf-8",
    )

    render_raw_reference_backlinks(xml_dir, markdown_dir, html_dir)

    content = raw_page.read_text(encoding="utf-8")
    assert "Defined in module <code>std.unit</code>" in content
    assert '>unit.l0</a>' in content


def test_render_curated_html_site_shows_declared_l0_module_banner(tmp_path: Path, monkeypatch) -> None:
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    markdown_dir = tmp_path / "markdown"
    html_dir = tmp_path / "html"
    templates_dir = Path(__file__).resolve().parents[4] / "scripts/docs/templates"
    source_path = tmp_path / "compiler/shared/l0/stdlib/std/unit.l0"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("module std.unit;\n", encoding="utf-8")

    page = markdown_dir / "compiler/shared/l0/stdlib/std/unit.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# compiler/shared/l0/stdlib/std/unit.l0

Source: `compiler/shared/l0/stdlib/std/unit.l0`
Language: `Dea/L0`
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    render_curated_html_site(xml_dir, markdown_dir, html_dir, templates_dir)

    file_page = (html_dir / "api/compiler/shared/l0/stdlib/std/unit.html").read_text(encoding="utf-8")
    assert '<span class="m-label m-flat m-primary">Module</span> <code>std.unit</code>' in file_page
    assert "<h1>compiler/shared/l0/stdlib/std/unit.l0</h1>" in file_page
