#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Install Ubuntu documentation packages with bounded network retries."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

MIRROR = b"https://archive.ubuntu.com/ubuntu"
AZURE_ARCHIVE = re.compile(rb"https?://azure\.archive\.ubuntu\.com/ubuntu(?=/|\s|$)")
APT_OPTIONS = [
    "-o", "Acquire::Retries=3",
    "-o", "Acquire::http::Timeout=30",
    "-o", "Acquire::https::Timeout=30",
]
# Doxygen converts EPS diagrams during LaTeX generation, before optional PDF compilation.
BASE_PACKAGES = ["graphviz", "make", "texlive-font-utils", "ghostscript"]
TEX_PACKAGES = ["texlive-latex-recommended", "texlive-latex-extra", "texlive-fonts-recommended"]


def verify_tools(build_pdf: bool) -> None:
    """Require commands used by reference generation and optional PDF compilation.

    Args:
        build_pdf: Whether PDF compilation commands must also be available.

    Raises:
        RuntimeError: One or more required commands are absent from PATH.
    """
    required = ["dot", "make", "epstopdf", "gs"]
    if build_pdf:
        required += ["pdflatex", "makeindex"]
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"Documentation toolchain is missing required commands: {', '.join(missing)}")
    print(f"docs-toolchain: verified commands: {', '.join(required)}", flush=True)


def configure_mirror(apt_root: Path) -> None:
    """Replace Azure archive URLs without changing other APT configuration.

    Args:
        apt_root: Directory containing sources, including the hosted runner's mirror list.

    Raises:
        OSError: A source file cannot be read or the write command cannot start.
        subprocess.CalledProcessError: A privileged source-file write fails.
    """
    # Hosted Ubuntu sources use mirror+file to select URLs from apt-mirrors.txt.
    sources = [apt_root / "sources.list", apt_root / "apt-mirrors.txt",
               *sorted((apt_root / "sources.list.d").glob("*.list")),
               *sorted((apt_root / "sources.list.d").glob("*.sources"))]
    changed = 0
    for source in sources:
        if not source.is_file():
            continue
        original = source.read_bytes()
        updated = AZURE_ARCHIVE.sub(MIRROR, original)
        if updated != original:
            subprocess.run(["sudo", "tee", str(source)], input=updated, stdout=subprocess.DEVNULL, check=True)
            print(f"docs-toolchain: {source}: selected {MIRROR.decode()}", flush=True)
            changed += 1
    if not changed:
        print("docs-toolchain: no Azure archive URLs found; retaining configured sources", flush=True)


def report_versions(build_pdf: bool) -> None:
    """Report installed packages and the TeX commands selected by PATH.

    Args:
        build_pdf: Whether to report the full PDF engine and table package.

    Raises:
        OSError: A command or the table package file cannot be read.
        subprocess.CalledProcessError: A version query fails.
        RuntimeError: The active table package has no recognizable version.
    """
    packages = [*BASE_PACKAGES, *(TEX_PACKAGES if build_pdf else []), "texlive-binaries"]
    subprocess.run(["dpkg-query", "--show", "--showformat=${Package} ${Version}\\n", *packages], check=True)
    commands = [["epstopdf", "--version"], ["gs", "--version"]]
    if build_pdf:
        commands += [["pdflatex", "--version"]]
        print(f"docs-toolchain: makeindex: {shutil.which('makeindex')}", flush=True)
    for command in commands:
        print(f"docs-toolchain: {command[0]}: {shutil.which(command[0])}", flush=True)
        subprocess.run(command, check=True)
    if build_pdf:
        package = subprocess.check_output(["kpsewhich", "tabularray.sty"], text=True).strip()
        style = Path(package).read_text(encoding="utf-8")
        release = re.search(r"\\ProvidesExplPackage\{tabularray\}\{([^}]+)\}\{([^}]+)\}", style)
        if release is None:
            raise RuntimeError(f"Cannot identify tabularray version in {package}")
        print(f"docs-toolchain: tabularray {' '.join(release.groups())}: {package}", flush=True)


def install_toolchain(build_pdf: bool, *, apt_root: Path = Path("/etc/apt")) -> None:
    """Refresh package indexes and install the requested documentation tools.

    Args:
        build_pdf: Whether to include the existing TeX package selection.
        apt_root: APT source directory; overridden by filesystem-only tests.

    Raises:
        OSError: Source configuration or an installation command is unavailable.
        subprocess.CalledProcessError: Source writing, index refresh, or installation fails.
        RuntimeError: Required generation or PDF commands remain unavailable.
    """
    configure_mirror(apt_root)
    command = ["sudo", "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", *APT_OPTIONS]
    subprocess.run([*command, "update", "--error-on=any"], check=True)
    packages = [*BASE_PACKAGES, *(TEX_PACKAGES if build_pdf else [])]
    subprocess.run([*command, "install", "-y", *packages], check=True)
    verify_tools(build_pdf)


def main() -> int:
    """Install the Ubuntu toolchain selected by the shared action.

    Returns:
        Zero on success, or one on configuration or package-installation failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-pdf", choices=("true", "false"), default="true")
    parser.add_argument("--report-versions", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Documentation package setup requires an Ubuntu runner")
    try:
        if args.report_versions:
            report_versions(args.build_pdf == "true")
        else:
            install_toolchain(args.build_pdf == "true")
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"docs-toolchain: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
