# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Generate HTML, Markdown, and LaTeX API documentation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .l1_docgen_l0_filter import transform_l0_for_doxygen
from .l1_docgen_latex import normalize_latex_site
from .l1_docgen_markdown import (
    normalize_search_result_urls,
    render_compat_redirect_pages,
    render_curated_html_site,
    render_markdown_site,
    render_raw_reference_backlinks,
    rewrite_and_prune_raw_html_surface,
)
from .l1_docgen_sources import SourceManifest, build_source_manifest

_LATEX_FRONT_MATTER_BREAK = "l0docgenlinetwo"


def repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[2]


def _git_revision_suffix_for_latex(root: Path | None = None) -> str:
    root = root or repo_root()
    try:
        short_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    if not short_hash:
        return ""

    dirty_suffix = ""
    try:
        status_output = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        status_output = ""
    if status_output.strip():
        dirty_suffix = "+"
    return f" ({short_hash}{dirty_suffix})"


def _release_tag_for_latex() -> str:
    return os.environ.get("L1_DOCS_RELEASE_TAG", "").strip() or os.environ.get("RELEASE_VERSION", "").strip()


def _project_number_for_latex() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    build_date_text: str | None = None
    if source_date_epoch:
        try:
            timestamp = int(source_date_epoch)
        except ValueError:
            pass
        else:
            build_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
            build_date_text = build_date.isoformat()

    if build_date_text is None:
        build_date_text = datetime.now(timezone.utc).date().isoformat()

    revision_suffix = _git_revision_suffix_for_latex()
    if not revision_suffix:
        return f"Generated {build_date_text}"

    release_tag = _release_tag_for_latex()
    second_line = f"{release_tag}{revision_suffix}" if release_tag else revision_suffix.lstrip()
    return f"Generated {build_date_text} {_LATEX_FRONT_MATTER_BREAK} {second_line}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "For wrapper-only options such as --pdf, --pdf-fast, and --verbose, "
            "use python scripts/gen_docs.py --help."
        ),
    )
    parser.add_argument("--stage", choices=("stage1", "stage2", "all"), default="all")
    parser.add_argument("--html-only", action="store_true", help="Generate only HTML output.")
    parser.add_argument("--markdown-only", action="store_true", help="Generate only Markdown output.")
    parser.add_argument("--latex-only", action="store_true", help="Generate only LaTeX output.")
    parser.add_argument("--no-latex", action="store_true", help="Skip LaTeX generation in the default mixed mode.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/docs"),
        help="Output root for generated documentation.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on Doxygen warnings and synthetic __padN__ symbol regressions.",
    )
    args = parser.parse_args(argv)
    only_modes = [args.html_only, args.markdown_only, args.latex_only]
    if sum(1 for enabled in only_modes if enabled) > 1:
        parser.error("--html-only, --markdown-only, and --latex-only are mutually exclusive")
    if args.no_latex and any(only_modes):
        parser.error("--no-latex cannot be combined with --html-only, --markdown-only, or --latex-only")
    return args


def _resolve_output_modes(args: argparse.Namespace) -> tuple[bool, bool, bool]:
    if args.html_only:
        return True, False, False
    if args.markdown_only:
        return False, True, False
    if args.latex_only:
        return False, False, True
    return True, True, not args.no_latex


def _copy_regular_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _build_shadow_tree(root: Path, manifest: SourceManifest, shadow_root: Path) -> None:
    if shadow_root.exists():
        shutil.rmtree(shadow_root)
    shadow_root.mkdir(parents=True)

    for relative_path in manifest.files:
        src = root / relative_path
        dst = shadow_root / relative_path
        if src.suffix in {".l0", ".l1"}:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(transform_l0_for_doxygen(src.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            _copy_regular_file(src, dst)


def _write_template(template_name: str, destination: Path, **context: object) -> None:
    templates_dir = repo_root() / "scripts/docs/templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    destination.write_text(env.get_template(template_name).render(**context), encoding="utf-8")


def _patch_mcss_renderer(mcss_root: Path) -> None:
    renderer = mcss_root / "documentation/doxygen.py"
    text = renderer.read_text(encoding="utf-8")
    replacements = {
        "title = html.escape(i.text)": 'title = html.escape("".join(i.itertext()))',
        "if not i.text:": "if not i.text and len(i) == 0:",
        "html.escape(i.text))": 'html.escape("".join(i.itertext())))',
        "if compounddef.attrib.get('language', 'C++') not in ['C++']:": "if compounddef.attrib.get('language', 'C++') not in ['C++', 'Python', 'C', 'Markdown', 'Objective-C']:",
        "if not state.config['SEARCH_DISABLED'] and not compound.kind == 'example' and (compound.kind == 'group' or compound.brief or len(compounddef.find('detaileddescription'))):": (
            "if not state.config['SEARCH_DISABLED'] and compound.kind != 'dir' and not compound.kind == 'example' and "
            "(compound.kind == 'group' or compound.brief or len(compounddef.find('detaileddescription'))):"
        ),
        "        return (html.escape('<{}>'.format(make_include_strip_from_path(file, state.doxyfile['STRIP_FROM_INC_PATH']) if state.doxyfile['STRIP_FROM_INC_PATH'] is not None else file)), state.compounds[state.includes[file]].url)": (
            "        include_name = make_include_strip_from_path(file, state.doxyfile['STRIP_FROM_INC_PATH']) if state.doxyfile['STRIP_FROM_INC_PATH'] is not None else file\n"
            "        if include_name.endswith(('.l0', '.l1')):\n"
            "            rendered_include = include_name\n"
            "        else:\n"
            "            rendered_include = '<{}>'.format(include_name)\n"
            "        return (html.escape(rendered_include), state.compounds[state.includes[file]].url)"
        ),
        "        return (html.escape('<{}>'.format(name)), state.compounds[file_id].url)": (
            "        if name.endswith(('.l0', '.l1')):\n"
            "            rendered_include = name\n"
            "        else:\n"
            "            rendered_include = '<{}>'.format(name)\n"
            "        return (html.escape(rendered_include), state.compounds[file_id].url)"
        ),
    }
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != text:
        renderer.write_text(updated, encoding="utf-8")


def _run_command(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _warnings_count(warnings_log: Path) -> int:
    if not warnings_log.exists():
        return 0
    ignore_patterns = [
        re.compile(r"Failed to map file extension 'md'"),
        re.compile(r"Found documentation for module .* but it has no primary interface unit"),
        re.compile(r"argument '.*' of command @param is not found in the argument list of"),
        re.compile(r"the name 'Optional' supplied as the argument of the \\class"),
        re.compile(r"the name 'Base' supplied as the argument of the \\class"),
    ]
    count = 0
    for line in warnings_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if any(pattern.search(line) for pattern in ignore_patterns):
            continue
        count += 1
    return count


def _member_line(memberdef: ET.Element) -> int | None:
    location = memberdef.find("location")
    if location is None:
        return None
    line_text = location.attrib.get("declline") or location.attrib.get("line")
    if not line_text:
        return None
    try:
        line = int(line_text)
    except ValueError:
        return None
    return line if line > 0 else None


def _member_has_documentation(memberdef: ET.Element) -> bool:
    for tag in ("briefdescription", "detaileddescription", "inbodydescription"):
        section = memberdef.find(tag)
        if section is not None and "".join(section.itertext()).strip():
            return True
    return False


def _collect_undocumented_functions(xml_dir: Path) -> list[tuple[str, int | None, str]]:
    entries: set[tuple[str, int | None, str]] = set()
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "index.xml":
            continue
        root = ET.parse(xml_path).getroot()
        for memberdef in root.findall(".//memberdef[@kind='function']"):
            location = memberdef.find("location")
            if location is None:
                continue
            source_path = location.attrib.get("file", "").strip()
            name = memberdef.findtext("name", default="").strip()
            if not source_path or not name or _member_has_documentation(memberdef):
                continue
            entries.add((source_path, _member_line(memberdef), name))
    return sorted(entries, key=lambda item: (item[0], item[1] if item[1] is not None else 0, item[2]))


def _undocumented_function_source_type(source_path: str) -> str:
    suffix = Path(source_path).suffix
    if suffix in {".l0", ".l1"}:
        return "Dea"
    if suffix == ".py":
        return "Python"
    return "Other"


def _write_undocumented_functions_report(report_path: Path, entries: list[tuple[str, int | None, str]]) -> None:
    lines = ["# Undocumented Functions", ""]
    if not entries:
        lines.append("No undocumented functions found.")
    else:
        grouped_entries: dict[str, list[tuple[str, int | None, str]]] = {"Dea": [], "Python": [], "Other": []}
        for entry in entries:
            grouped_entries[_undocumented_function_source_type(entry[0])].append(entry)
        for section_name in ("Dea", "Python", "Other"):
            section_entries = grouped_entries[section_name]
            if not section_entries:
                continue
            lines.append(f"## {section_name}")
            lines.append("")
            for source_path, line, name in section_entries:
                location = f"{source_path}:{line}" if line is not None else source_path
                lines.append(f"{location} {name}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _find_synthetic_pad_members(xml_dir: Path) -> list[tuple[str, str]]:
    """Return synthetic __padN__ members discovered in generated Doxygen XML."""
    pad_member_re = re.compile(r"^__pad[0-9]+__$")
    hits: list[tuple[str, str]] = []
    for xml_path in sorted(xml_dir.glob("*.xml")):
        if xml_path.name == "Doxyfile.xml":
            continue
        root = ET.parse(xml_path).getroot()
        for name_node in root.findall(".//memberdef/name"):
            name = (name_node.text or "").strip()
            if pad_member_re.fullmatch(name):
                hits.append((xml_path.name, name))
    return hits


def _verify_source_functions(root: Path, manifest: SourceManifest, xml_dir: Path) -> None:
    """Fail when a declared source function disappears during filtering.

    Args:
        root: L1 source root.
        manifest: Selected stage inventory.
        xml_dir: Doxygen XML database for exactly this stage.

    Raises:
        ValueError: A source function is absent from the generated database.
    """
    found = set()
    for xml in xml_dir.glob("*.xml"):
        for member in ET.parse(xml).findall(".//memberdef[@kind='function']"):
            location = member.find("location")
            if location is not None:
                found.add((location.get("file"), member.findtext("name")))
    missing = []
    for path in manifest.files:
        if path.suffix not in {".l0", ".l1"}:
            continue
        for name in re.findall(r"^(?:unsafe\s+)?(?:extern\s+)?func\s+(\w+)\s*\(", (root / path).read_text(), re.MULTILINE):
            if (path.as_posix(), name) not in found:
                missing.append(f"{path}:{name}")
    if missing:
        raise ValueError("functions missing from documentation: " + ", ".join(missing[:20]))


def _normalize_html_output(doxygen_root: Path, html_dir: Path) -> None:
    generated_html_dir = doxygen_root / "html"
    if not generated_html_dir.exists():
        return
    if html_dir.exists():
        shutil.rmtree(html_dir)
    shutil.copytree(generated_html_dir, html_dir)


def _generate_stage(args: argparse.Namespace) -> int:
    """Generate one isolated stage into its supplied working directory.

    Args:
        args: Parsed options with a concrete stage and temporary output directory.

    Returns:
        Zero after successful generation and strict validation.

    Raises:
        SystemExit: Required tools are missing or strict validation fails.
        subprocess.CalledProcessError: An external generator fails.
    """
    root = repo_root()
    html_enabled, markdown_enabled, latex_enabled = _resolve_output_modes(args)
    output_root = (root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
    doxygen_root = output_root / "doxygen"
    xml_dir = doxygen_root / "xml"
    html_dir = output_root / "html"
    markdown_dir = output_root / "markdown"
    tmp_root = output_root / ".tmp"
    shadow_root = tmp_root / "shadow"
    generated_root = tmp_root / "generated"
    templates_dir = root / "scripts/docs/templates"
    xml_warnings_log = doxygen_root / "warnings-xml.log"
    latex_warnings_log = doxygen_root / "warnings-latex.log"
    undocumented_functions_report = output_root / "undocumented-functions.txt"
    xml_doxygen_path = generated_root / "Doxyfile.xml"
    latex_doxygen_path = generated_root / "Doxyfile.latex"
    mcss_conf_path = generated_root / "mcss_conf.py"
    html_mainpage_path = shadow_root / "docs-mainpage-html.md"
    latex_mainpage_path = shadow_root / "docs-mainpage-latex.md"
    mcss_root = root.parent / "tools/m.css"

    if not shutil.which("doxygen"):
        raise SystemExit("doxygen was not found in PATH")
    if not mcss_root.is_dir():
        raise SystemExit(f"vendored m.css checkout not found at {mcss_root}")

    if output_root.exists():
        shutil.rmtree(output_root)
    xml_dir.mkdir(parents=True)
    if html_enabled:
        html_dir.mkdir(parents=True)
    if markdown_enabled:
        markdown_dir.mkdir(parents=True)
    generated_root.mkdir(parents=True)

    manifest = build_source_manifest(root, args.stage)
    _build_shadow_tree(root, manifest, shadow_root)
    local_mcss = tmp_root / "mcss"
    shutil.copytree(mcss_root, local_mcss, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    mcss_root = local_mcss
    _patch_mcss_renderer(mcss_root)

    _write_template("mainpage_html.md.j2", html_mainpage_path, stage=args.stage)
    _write_template(
        "doxyfile.in",
        xml_doxygen_path,
        stage=args.stage,
        input_files=[(shadow_root / path).as_posix() for path in manifest.files],
        output_directory=doxygen_root.as_posix(),
        mainpage=html_mainpage_path.as_posix(),
        strip_from_path=shadow_root.as_posix(),
        warn_logfile=xml_warnings_log.as_posix(),
        project_number="",
        generate_xml="YES",
        generate_latex="NO",
    )
    _write_template(
        "mcss_conf.py.in",
        mcss_conf_path,
        stage=args.stage,
        doxygen_path=xml_doxygen_path.as_posix(),
        html_output=html_dir.as_posix(),
    )

    _run_command(["doxygen", str(xml_doxygen_path)], cwd=root)

    if latex_enabled:
        _write_template("mainpage_latex.md.j2", latex_mainpage_path, stage=args.stage)
        _write_template(
            "doxyfile.in",
            latex_doxygen_path,
            stage=args.stage,
            input_files=[(shadow_root / path).as_posix() for path in manifest.files],
            output_directory=doxygen_root.as_posix(),
            mainpage=latex_mainpage_path.as_posix(),
            strip_from_path=shadow_root.as_posix(),
            warn_logfile=latex_warnings_log.as_posix(),
            project_number=_project_number_for_latex(),
            generate_xml="NO",
            generate_latex="YES",
        )
        _run_command(["doxygen", str(latex_doxygen_path)], cwd=root)

    markdown_render_root: Path | None = None
    if markdown_enabled or html_enabled:
        markdown_render_root = markdown_dir if markdown_enabled else tmp_root / "markdown-html-source"
        markdown_render_root.mkdir(parents=True, exist_ok=True)

    if html_enabled:
        _run_command([sys.executable, str(mcss_root / "documentation/doxygen.py"), str(mcss_conf_path)], cwd=root)
        _normalize_html_output(doxygen_root, html_dir)
        normalize_search_result_urls(html_dir)
    if markdown_render_root is not None:
        render_markdown_site(xml_dir, markdown_render_root, templates_dir, stage=args.stage)
    if html_enabled and markdown_render_root is not None:
        render_curated_html_site(xml_dir, markdown_render_root, html_dir, templates_dir, stage=args.stage)
        render_raw_reference_backlinks(xml_dir, markdown_render_root, html_dir)
        rewrite_and_prune_raw_html_surface(xml_dir, markdown_render_root, html_dir)
        render_compat_redirect_pages(xml_dir, markdown_render_root, html_dir, templates_dir)
    if latex_enabled:
        normalize_latex_site(xml_dir, doxygen_root / "latex")

    undocumented_functions = _collect_undocumented_functions(xml_dir)
    _write_undocumented_functions_report(undocumented_functions_report, undocumented_functions)

    warning_count = _warnings_count(xml_warnings_log) + _warnings_count(latex_warnings_log)
    if args.strict:
        _verify_source_functions(root, manifest, xml_dir)
        pad_hits = _find_synthetic_pad_members(xml_dir)
        if pad_hits:
            preview = ", ".join(f"{xml}:{name}" for xml, name in pad_hits[:8])
            raise SystemExit(
                "detected synthetic Doxygen members matching __padN__: "
                f"{preview}; this indicates a Dea parsing regression"
            )
    if args.strict and warning_count:
        raise SystemExit(
            "doxygen reported "
            f"{warning_count} warning(s); see {xml_warnings_log} and {latex_warnings_log}"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    """Run independent stage pipelines, replacing only successful stage outputs.

    Args:
        argv: Optional command-line arguments.

    Returns:
        Zero after every selected stage succeeds.

    Raises:
        SystemExit: Argument parsing or generation fails.
        subprocess.CalledProcessError: An external generator fails.
    """
    args = parse_args(argv)
    parent = (repo_root() / args.output_dir).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    for stage in (("stage1", "stage2") if args.stage == "all" else (args.stage,)):
        (parent / "artifacts" / f"dea_l1_{stage}_autodocs.tar.gz").unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{stage}-", dir=parent) as work:
            selected = argparse.Namespace(**vars(args))
            selected.stage = stage
            selected.output_dir = Path(work) / stage
            try:
                _generate_stage(selected)
            except (SystemExit, OSError, subprocess.CalledProcessError):
                failure = parent / f"{stage}-failure"
                shutil.rmtree(failure, ignore_errors=True)
                shutil.copytree(work, failure)
                raise
            destination = parent / stage
            if destination.exists():
                shutil.rmtree(destination)
            shutil.move(str(selected.output_dir), destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
