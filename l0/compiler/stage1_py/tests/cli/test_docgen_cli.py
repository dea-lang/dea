# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Tests for the docs CLI."""

from pathlib import Path
import subprocess

import compiler.docgen.l0_docgen as l0_docgen
import pytest

from compiler.docgen.l0_docgen import (
    _collect_undocumented_functions,
    _find_synthetic_pad_members,
    _patch_mcss_renderer,
    _project_number_for_latex,
    _resolve_output_modes,
    _write_undocumented_functions_report,
    parse_args,
    repo_root,
)


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.output_dir == Path("build/docs")
    assert not args.html_only
    assert not args.markdown_only
    assert not args.latex_only
    assert not args.no_latex
    assert not args.strict
    assert _resolve_output_modes(args) == (True, True, True)


def test_parse_args_rejects_conflicting_output_modes() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--html-only", "--markdown-only"])
    with pytest.raises(SystemExit):
        parse_args(["--html-only", "--latex-only"])
    with pytest.raises(SystemExit):
        parse_args(["--markdown-only", "--latex-only"])


def test_parse_args_supports_latex_only_mode() -> None:
    args = parse_args(["--latex-only"])
    assert args.latex_only
    assert _resolve_output_modes(args) == (False, False, True)


def test_parse_args_supports_no_latex_mode() -> None:
    args = parse_args(["--no-latex"])
    assert args.no_latex
    assert _resolve_output_modes(args) == (True, True, False)


def test_parse_args_rejects_no_latex_with_only_modes() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--no-latex", "--html-only"])
    with pytest.raises(SystemExit):
        parse_args(["--no-latex", "--markdown-only"])
    with pytest.raises(SystemExit):
        parse_args(["--no-latex", "--latex-only"])


def test_parse_args_help_mentions_wrapper_for_pdf_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--help"])

    captured = capsys.readouterr()
    assert "For wrapper-only options such as --pdf, --pdf-fast, and --verbose" in captured.out
    assert "python" in captured.out
    assert "scripts/gen_docs.py --help" in captured.out


def test_project_number_for_latex_uses_source_date_epoch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    monkeypatch.delenv("L0_DOCS_RELEASE_TAG", raising=False)
    monkeypatch.setattr(l0_docgen, "_git_revision_suffix_for_latex", lambda root=None: " (abc1234)")
    assert _project_number_for_latex() == "Generated 2026-01-01 l0docgenlinetwo (abc1234)"


def test_project_number_for_latex_includes_release_tag_on_second_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    monkeypatch.setenv("L0_DOCS_RELEASE_TAG", "v0.9.1")
    monkeypatch.setattr(l0_docgen, "_git_revision_suffix_for_latex", lambda root=None: " (abc1234)")
    assert _project_number_for_latex() == "Generated 2026-01-01 l0docgenlinetwo v0.9.1 (abc1234)"


def test_project_number_for_latex_omits_second_line_without_git_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    monkeypatch.setenv("L0_DOCS_RELEASE_TAG", "v0.9.1")
    monkeypatch.setattr(l0_docgen, "_git_revision_suffix_for_latex", lambda root=None: "")
    assert _project_number_for_latex() == "Generated 2026-01-01"


def test_git_revision_suffix_for_latex_marks_dirty_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args == ["git", "rev-parse", "--short", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout="abc1234\n", stderr="")
        if args == ["git", "status", "--porcelain"]:
            return subprocess.CompletedProcess(args, 0, stdout=" M compiler/docgen/l0_docgen.py\n", stderr="")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(l0_docgen.subprocess, "run", fake_run)
    assert l0_docgen._git_revision_suffix_for_latex(tmp_path) == " (abc1234+)"


def test_git_revision_suffix_for_latex_omits_hash_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(128, args)

    monkeypatch.setattr(l0_docgen.subprocess, "run", fake_run)
    assert l0_docgen._git_revision_suffix_for_latex(tmp_path) == ""


def test_find_synthetic_pad_members_detects_generated_padding_names(tmp_path: Path) -> None:
    (tmp_path / "with-pad.xml").write_text(
        """
<doxygen>
  <compounddef>
    <sectiondef>
      <memberdef kind="variable"><name>__pad0__</name></memberdef>
      <memberdef kind="variable"><name>real_field</name></memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "without-pad.xml").write_text(
        """
<doxygen>
  <compounddef>
    <sectiondef>
      <memberdef kind="variable"><name>field_ok</name></memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert _find_synthetic_pad_members(tmp_path) == [("with-pad.xml", "__pad0__")]


def test_find_synthetic_pad_members_ignores_non_matching_names(tmp_path: Path) -> None:
    (tmp_path / "candidates.xml").write_text(
        """
<doxygen>
  <compounddef>
    <sectiondef>
      <memberdef kind="variable"><name>__pad__</name></memberdef>
      <memberdef kind="variable"><name>__padA__</name></memberdef>
      <memberdef kind="variable"><name>__pad1_</name></memberdef>
      <memberdef kind="variable"><name>field</name></memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert _find_synthetic_pad_members(tmp_path) == []


def test_collect_undocumented_functions_uses_xml_documentation_content(tmp_path: Path) -> None:
    (tmp_path / "demo_8l0.xml").write_text(
        """
<doxygen>
  <compounddef>
    <sectiondef>
      <memberdef kind="function">
        <name>documented</name>
        <briefdescription><para>Has docs.</para></briefdescription>
        <detaileddescription></detaileddescription>
        <location file="compiler/stage2_l0/src/demo.l0" line="3" declline="3" />
      </memberdef>
      <memberdef kind="function">
        <name>undocumented</name>
        <briefdescription></briefdescription>
        <detaileddescription></detaileddescription>
        <location file="compiler/stage2_l0/src/demo.l0" line="9" declline="8" />
      </memberdef>
      <memberdef kind="function">
        <name>param_only</name>
        <briefdescription></briefdescription>
        <detaileddescription>
          <para>
            <parameterlist kind="param">
              <parameteritem>
                <parameternamelist><parametername>x</parametername></parameternamelist>
                <parameterdescription><para>Still documented.</para></parameterdescription>
              </parameteritem>
            </parameterlist>
          </para>
        </detaileddescription>
        <location file="compiler/stage2_l0/src/demo.l0" line="12" />
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "demo_8py.xml").write_text(
        """
<doxygen>
  <compounddef>
    <sectiondef>
      <memberdef kind="function">
        <name>helper</name>
        <briefdescription></briefdescription>
        <detaileddescription></detaileddescription>
        <location file="compiler/stage1_py/demo.py" line="4" />
      </memberdef>
    </sectiondef>
  </compounddef>
</doxygen>
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert _collect_undocumented_functions(tmp_path) == [
        ("compiler/stage1_py/demo.py", 4, "helper"),
        ("compiler/stage2_l0/src/demo.l0", 8, "undocumented"),
    ]


def test_write_undocumented_functions_report_formats_empty_and_non_empty_lists(tmp_path: Path) -> None:
    report_path = tmp_path / "undocumented-functions.txt"

    _write_undocumented_functions_report(report_path, [])
    assert report_path.read_text(encoding="utf-8") == "# Undocumented Functions\n\nNo undocumented functions found.\n"

    _write_undocumented_functions_report(
        report_path,
        [
            ("compiler/stage1_py/demo.py", 4, "helper"),
            ("compiler/stage2_l0/src/demo.l0", None, "undocumented"),
            ("compiler/shared/runtime/l0_runtime.h", 7, "_rt_helper"),
        ],
    )
    assert report_path.read_text(encoding="utf-8") == (
        "# Undocumented Functions\n\n"
        "## Dea\n\n"
        "compiler/stage2_l0/src/demo.l0 undocumented\n\n"
        "## Python\n\n"
        "compiler/stage1_py/demo.py:4 helper\n\n"
        "## Other\n\n"
        "compiler/shared/runtime/l0_runtime.h:7 _rt_helper\n"
    )


def test_mcss_template_uses_show_undocumented_setting() -> None:
    template = (repo_root() / "scripts/docs/templates/mcss_conf.py.in").read_text(encoding="utf-8")
    assert "SHOW_UNDOCUMENTED = True" in template
    assert "M_SHOW_UNDOCUMENTED" not in template
    assert "annotated.html" not in template
    assert '<a href="pdf/dea_l0_{{ stage }}_api_reference.pdf">PDF</a>' in template


def test_mainpage_html_template_links_to_pdf_reference() -> None:
    template = (repo_root() / "scripts/docs/templates/mainpage_html.md.j2").read_text(encoding="utf-8")
    assert "[Reference Manual (pdf)](pdf/dea_l0_{{ stage }}_api_reference.pdf)" in template


def test_doxyfile_template_supports_project_number() -> None:
    template = (repo_root() / "scripts/docs/templates/doxyfile.in").read_text(encoding="utf-8")
    assert 'PROJECT_NUMBER         = "{{ project_number }}"' in template


def test_patch_mcss_renderer_excludes_directory_pages_from_search_results(tmp_path: Path) -> None:
    mcss_root = tmp_path / "m.css"
    renderer_dir = mcss_root / "documentation"
    renderer_dir.mkdir(parents=True)
    renderer = renderer_dir / "doxygen.py"
    renderer.write_text(
        "if not state.config['SEARCH_DISABLED'] and not compound.kind == 'example' and "
        "(compound.kind == 'group' or compound.brief or len(compounddef.find('detaileddescription'))):\n"
        "    pass\n",
        encoding="utf-8",
    )

    _patch_mcss_renderer(mcss_root)

    patched = renderer.read_text(encoding="utf-8")
    assert "compound.kind != 'dir'" in patched
