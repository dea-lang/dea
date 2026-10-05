#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Generate L0 documentation and optional PDF artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import re
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from docs_artifacts import create_bundle, package_version, pdf_name, source_identity

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ParsedArgs:
    """Parsed wrapper options plus docgen pass-through arguments."""

    stage: str
    artifacts: bool
    build_pdf: bool
    build_pdf_fast: bool
    verbose: bool
    output_dir: Path
    html_only: bool
    markdown_only: bool
    latex_only: bool
    no_latex: bool
    docgen_args: list[str]


def show_usage() -> None:
    """Print wrapper usage."""

    print(
        """Usage: python scripts/gen_docs.py [--pdf|--pdf-fast] [-v|--verbose] [docgen options...]

Wrapper around `python -m compiler.docgen.l0_docgen`.

Extra options:
  --stage STAGE    Select stage1, stage2, or all (default); output-dir names their common parent.
  --artifacts      Require strict HTML/full PDF and create verified offline bundles.
  --pdf            Build stage-qualified complete PDFs under `<output-dir>/stageS/pdf/`.
  --pdf-fast       Build a preview stage-qualified PDF with a single `pdflatex` pass (faster, less complete references/index).
  -v, --verbose    Show docgen warnings and LaTeX build output directly.

Environment:
  L0_DOCS_RELEASE_TAG
                   Optional release tag to show on the PDF front matter title page, e.g.
                   `L0_DOCS_RELEASE_TAG=v0.9.9 python scripts/gen_docs.py --pdf-fast`."""
    )


def venv_python() -> str:
    """Return the path to the shared monorepo venv's Python interpreter."""

    venv = REPO_ROOT.parent / ".venv"
    posix = venv / "bin" / "python"
    if posix.exists():
        return str(posix)
    return str(venv / "Scripts" / "python.exe")


def parse_args(argv: list[str]) -> ParsedArgs:
    """Parse wrapper arguments while preserving docgen pass-through options."""

    stage = "all"
    artifacts = False
    build_pdf = False
    build_pdf_fast = False
    verbose = False
    output_dir = Path("build/docs")
    html_only = False
    markdown_only = False
    latex_only = False
    no_latex = False
    docgen_args: list[str] = []

    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--artifacts":
            artifacts = True
        elif arg == "--stage":
            if index + 1 >= len(argv):
                raise ValueError("--stage requires a value")
            stage = argv[index + 1]
            index += 1
        elif arg.startswith("--stage="):
            stage = arg.split("=", 1)[1]
        elif arg == "--pdf":
            build_pdf = True
        elif arg == "--pdf-fast":
            build_pdf_fast = True
        elif arg in {"-v", "--verbose"}:
            verbose = True
        elif arg == "--output-dir":
            if index + 1 >= len(argv):
                raise ValueError("--output-dir requires a value")
            output_dir = Path(argv[index + 1])
            index += 1
        elif arg.startswith("--output-dir="):
            output_dir = Path(arg.split("=", 1)[1])
        elif arg == "--html-only":
            html_only = True
            docgen_args.append(arg)
        elif arg == "--markdown-only":
            markdown_only = True
            docgen_args.append(arg)
        elif arg == "--latex-only":
            latex_only = True
            docgen_args.append(arg)
        elif arg == "--no-latex":
            no_latex = True
            docgen_args.append(arg)
        elif arg in {"-h", "--help"}:
            show_usage()
            subprocess.run(
                [venv_python(), "-m", "compiler.docgen.l0_docgen", "--help"],
                cwd=REPO_ROOT,
                check=False,
            )
            raise SystemExit(0)
        else:
            docgen_args.append(arg)
        index += 1

    if stage not in {"stage1", "stage2", "all"}:
        raise ValueError("--stage must be stage1, stage2, or all")
    return ParsedArgs(
        stage=stage,
        artifacts=artifacts,
        build_pdf=build_pdf,
        build_pdf_fast=build_pdf_fast,
        verbose=verbose,
        output_dir=output_dir,
        html_only=html_only,
        markdown_only=markdown_only,
        latex_only=latex_only,
        no_latex=no_latex,
        docgen_args=docgen_args,
    )


def require_command(name: str, message: str) -> None:
    """Raise when one required external command is not available."""

    if shutil.which(name) is None:
        raise RuntimeError(message)


def run_logged(
        command: list[str],
        log_file: Path,
        *,
        verbose: bool,
        cwd: Path = REPO_ROOT,
        env: dict[str, str] | None = None,
) -> None:
    """Run one command, logging output on quiet failure."""

    if verbose:
        subprocess.run(command, cwd=cwd, env=env, check=True)
        return

    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_file.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        print(f"Error: command failed: {' '.join(command)}", file=sys.stderr)
        print(f"Log saved to: {log_file}", file=sys.stderr)
        print(completed.stdout, file=sys.stderr, end="" if completed.stdout.endswith("\n") else "\n")
        raise SystemExit(1)


def sync_preview_dir(src_dir: Path, dst_dir: Path) -> None:
    """Mirror one generated docs directory into `build/preview`."""

    if not src_dir.is_dir():
        return
    dst_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(dst_dir, ignore_errors=True)
    shutil.copytree(src_dir, dst_dir)


def has_undocumented_functions(report_path: Path) -> bool:
    """Return whether the undocumented-functions report has actionable entries."""

    if not report_path.is_file():
        return False
    ignored = re.compile(r"^(#|$|No undocumented functions found\.)")
    return any(not ignored.match(line) for line in report_path.read_text(encoding="utf-8").splitlines())


def main(argv: list[str] | None = None) -> int:
    """Program entrypoint."""

    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        if args.artifacts and (not args.build_pdf or "--strict" not in args.docgen_args or args.latex_only):
            raise ValueError("--artifacts requires --strict --pdf and HTML output")
        if args.build_pdf and args.build_pdf_fast:
            raise ValueError("--pdf and --pdf-fast are mutually exclusive")
        if (args.build_pdf or args.build_pdf_fast) and (args.html_only or args.markdown_only or args.no_latex):
            raise ValueError(
                "--pdf and --pdf-fast require LaTeX output. They cannot be combined with "
                "--html-only, --markdown-only, or --no-latex."
            )

        require_command("doxygen", "doxygen could not be found. Please install it.")
        require_command("uv", "uv could not be found. Please install it.")
        if not (REPO_ROOT.parent / "tools" / "m.css" / "documentation").is_dir():
            raise RuntimeError("vendored m.css checkout is missing at ../tools/m.css.")
        if args.build_pdf:
            require_command("make", "make could not be found. Please install it to build PDF output.")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parent = (REPO_ROOT / args.output_dir).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    for stage in (("stage1", "stage2") if args.stage == "all" else (args.stage,)):
        identity = source_identity(REPO_ROOT, stage)
        bundle = parent / "artifacts" / f"dea_l0_{stage}_autodocs.tar.gz"
        # Invalidate distribution success on every new selected-stage attempt.
        bundle.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{stage}-", dir=parent) as work:
            work_root = Path(work)
            try:
                run_logged(
                    [venv_python(), "-m", "compiler.docgen.l0_docgen", "--stage", stage,
                     "--output-dir", str(work_root), *args.docgen_args],
                    work_root / "docgen.log", verbose=args.verbose,
                )
                stage_root = work_root / stage
                if args.build_pdf or args.build_pdf_fast:
                    latex_dir = stage_root / "doxygen/latex"
                    pdf_dir = stage_root / "pdf"
                    pdf_dir.mkdir(parents=True, exist_ok=True)
                    if args.build_pdf:
                        command = ["make", "-C", str(latex_dir), "LATEX_CMD=pdflatex -interaction=nonstopmode -halt-on-error"]
                        run_logged(command, work_root / "latex.log", verbose=args.verbose)
                    else:
                        run_logged(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "refman"],
                                   work_root / "latex.log", verbose=args.verbose, cwd=latex_dir)
                    shutil.copy2(latex_dir / "refman.pdf", pdf_dir / pdf_name(stage))
                    if (stage_root / "html").is_dir():
                        shutil.copytree(pdf_dir, stage_root / "html/pdf")
                if source_identity(REPO_ROOT, stage) != identity:
                    raise ValueError("documentation source changed during generation")
                if args.artifacts:
                    tools = {name: subprocess.check_output([name, "--version"], text=True).splitlines()[0]
                             for name in ("doxygen", "pdflatex")}
                    tools["python"] = subprocess.check_output([venv_python(), "--version"], text=True).strip()
                    tools["mcss"] = hashlib.sha256(
                        (REPO_ROOT.parent / "tools/m.css/documentation/doxygen.py").read_bytes()).hexdigest()
                    create_bundle(stage_root, bundle, stage=stage, version=package_version(REPO_ROOT), source=identity, tools=tools)
                destination = parent / stage
                shutil.rmtree(destination, ignore_errors=True)
                shutil.move(str(stage_root), destination)
                preview = REPO_ROOT / "build/preview" / stage
                shutil.rmtree(preview, ignore_errors=True)
                for kind in ("html", "markdown", "pdf"):
                    sync_preview_dir(destination / kind, preview / kind)
                report = destination / "undocumented-functions.txt"
                if has_undocumented_functions(report):
                    print(f"Undocumented functions report: {report}")
            except (SystemExit, subprocess.CalledProcessError, OSError, ValueError) as exc:
                bundle.unlink(missing_ok=True)
                # Retain the previous successful stage and preserve failure logs.
                failure = parent / f"{stage}-failure"
                shutil.rmtree(failure, ignore_errors=True)
                shutil.copytree(work_root, failure)
                print(f"Error: {exc}; failed build saved to {failure}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
