# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""PDF link normalization, final-pass acceptance, and wrapper transactions."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from docgen_pdf import validate_full_pdf

MISSING = "pdfTeX warning (dest): name{enum_avariant} has been referenced but does not exist, replaced by a fixed one"


@pytest.mark.parametrize("level", ["l0", "l1"])
@pytest.mark.parametrize("module_name", ["ast", "std.syntax"])
@pytest.mark.parametrize("case", ["file", "module", "unknown", "ambiguous", "missing-page"])
def test_module_links_use_only_unambiguous_documented_file_destinations(tmp_path, level, module_name, case):
    xml = tmp_path / "xml"
    latex = tmp_path / "latex"
    xml.mkdir()
    latex.mkdir()
    alias = "module__" + module_name.replace(".", "_8")
    for index in range(2 if case == "ambiguous" else 1):
        source = Path(f"compiler/src/source{index}.l0")
        (tmp_path / source).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / source).write_text(f"module {module_name};\n", encoding="utf-8")
        (xml / f"file{index}.xml").write_text(
            f'<doxygen><compounddef id="file{index}" kind="file">'
            f'<location file="{source.as_posix()}" /></compounddef></doxygen>', encoding="utf-8")
        if case != "missing-page":
            (latex / f"file{index}.tex").write_text(
                rf"\hypertarget{{file{index}}}{{}}\label{{file{index}}}\index{{source}}" + "\n",
                encoding="utf-8")
    # The link can originate outside an L0 source compound and use a display label
    # that differs from the module name. XML provides the alias identity.
    referenced_name = "unavailable.module" if case == "unknown" else module_name
    (xml / "header.xml").write_text(
        '<doxygen><compounddef id="header" kind="file"><location file="native.h" />'
        f'<briefdescription><para><ref refid="{alias}" kindref="compound">'
        f'{referenced_name}</ref></para></briefdescription></compounddef></doxygen>', encoding="utf-8")
    if case == "module":
        (xml / "module.xml").write_text(
            f'<doxygen><compounddef id="{alias}" kind="module" /></doxygen>', encoding="utf-8")
        (latex / f"{alias}.tex").write_text(rf"\hypertarget{{{alias}}}{{}}", encoding="utf-8")
    original = (rf"\doxylink{{{alias}}}{{\texttt{{display name}}}} "
                rf"\hyperlink{{{alias}}}{{display name}} "
                r"\doxylink{module__unlisted}{unchanged}" + "\n")
    (latex / "header.tex").write_text(original, encoding="utf-8")
    code = '''
import importlib, os, pathlib, sys
level, fixture = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(level))
normalize = importlib.import_module(f"compiler.docgen.{level.name}_docgen_latex").normalize_latex_site
os.chdir(fixture)
normalize(fixture / "xml", fixture / "latex")
first = (fixture / "latex/header.tex").read_text(encoding="utf-8")
normalize(fixture / "xml", fixture / "latex")
assert (fixture / "latex/header.tex").read_text(encoding="utf-8") == first
'''
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / level), str(tmp_path)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = original.replace("{" + alias + "}", "{file0}") if case == "file" else original
    assert (latex / "header.tex").read_text(encoding="utf-8") == expected


@pytest.fixture
def latex(tmp_path):
    (tmp_path / "refman.log").write_text("Output written on refman.pdf\n")
    (tmp_path / "refman.ind").write_text("index")
    return tmp_path


@pytest.mark.parametrize("width", [None, 11, 79])
def test_missing_destinations_are_rejected_even_when_tex_wraps_identifiers_and_words(latex, width):
    warning = MISSING if width is None else "\n".join(MISSING[i:i + width] for i in range(0, len(MISSING), width))
    (latex / "refman.log").write_text(warning + "\n" + warning)
    with pytest.raises(ValueError, match=r"1 missing destination\(s\): enum_avariant; see"):
        validate_full_pdf(latex)


@pytest.mark.parametrize("warning", [
    "LaTeX Warning: There were undefined references.",
    "LaTeX Warning: Label(s) may have changed. Rerun to get cross-\nreferences right.",
])
def test_unresolved_references_are_rejected(latex, warning):
    (latex / "refman.log").write_text(warning)
    with pytest.raises(ValueError, match="unresolved references"):
        validate_full_pdf(latex)


def test_only_final_pass_is_checked_and_layout_messages_remain_permitted(latex):
    (latex / "latex.log").write_text(MISSING + "\nThere were undefined references.\n")
    (latex / "refman.log").write_text("Overfull \\hbox (1.0pt too wide)\nUnderfull \\vbox\nOutput written on refman.pdf\n")
    validate_full_pdf(latex)


def test_missing_index_is_rejected(latex):
    (latex / "refman.ind").unlink()
    with pytest.raises(ValueError, match="index is missing"):
        validate_full_pdf(latex)


def test_missing_final_log_is_rejected(latex):
    (latex / "refman.log").unlink()
    with pytest.raises(OSError):
        validate_full_pdf(latex)


@pytest.mark.parametrize("level", ["l0", "l1"])
@pytest.mark.parametrize("mode", ["full-clean", "full-missing", "preview"])
def test_wrapper_checks_before_publishing_and_preserves_failed_outputs(tmp_path, level, mode):
    # Isolate each level's identically named compiler and wrapper modules.
    code = '''
from pathlib import Path
import sys
root, checkout, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(root / "scripts"))
import gen_docs
repo = checkout / root.name
repo.mkdir(parents=True)
(checkout / "tools/m.css/documentation").mkdir(parents=True)
(checkout / "tools/m.css/documentation/doxygen.py").write_text("fixture renderer")
gen_docs.REPO_ROOT = repo
gen_docs.require_command = lambda *args: None
gen_docs.venv_python = lambda: sys.executable
gen_docs.package_version = lambda *args: "dev"
gen_docs.source_identity = lambda *args: {"revision": "fixture", "tree_state": "clean", "input_digest": "a"*64}
gen_docs.subprocess.check_output = lambda *args, **kwargs: "fixture version\\n"
selected = "stage1" if root.name == "l0" else "reference"
output = repo / "build/docs"
previous = output / selected
previous.mkdir(parents=True)
(previous / "old").write_text("previous successful output")
bundle = output / "artifacts" / ("dea_l0_stage1_autodocs.tar.gz" if root.name == "l0" else "dea_l1_autodocs.tar.gz")
bundle.parent.mkdir()
bundle.write_text("previous bundle")
def run(command, log, **kwargs):
    log.write_text("complete command output\\n")
    if "-m" in command:
        stage = Path(command[command.index("--output-dir") + 1]) / selected
        (stage / "doxygen/latex").mkdir(parents=True)
        (stage / "html").mkdir()
        (stage / "html/index.html").write_text("reference")
        return
    latex = Path(command[command.index("-C") + 1]) if "-C" in command else kwargs["cwd"]
    (latex / "refman.pdf").write_bytes(b"fixture PDF")
    (latex / "refman.ind").write_text("index")
    (latex / "refman.log").write_text("clean" if mode == "full-clean" else sys.argv[4])
def create(stage_root, path, **kwargs):
    assert mode == "full-clean", "invalid PDF reached bundle creation"
    path.write_text("new bundle")
gen_docs.run_logged = run
gen_docs.create_bundle = create
args = ["--strict", "--pdf-fast"] if mode == "preview" else ["--strict", "--pdf", "--artifacts"]
if root.name == "l0":
    args += ["--stage", selected]
result = gen_docs.main(args)
if mode == "full-missing":
    assert result == 1
    assert (previous / "old").read_text() == "previous successful output"
    assert not bundle.exists()
    assert not (repo / "build/preview").exists()
    assert not (previous / "pdf").exists()
    assert any((output / (selected + "-failure")).rglob("refman.log"))
else:
    assert result == 0
    assert not (previous / "old").exists()
    assert any((previous / "pdf").glob("*.pdf"))
    assert bundle.exists() == (mode == "full-clean")
'''
    completed = subprocess.run([sys.executable, "-c", code, str(ROOT / level), str(tmp_path / "checkout with spaces"), mode, MISSING],
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert ("1 missing destination(s)" in completed.stderr) == (mode == "full-missing")
