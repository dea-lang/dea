#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Create and verify offline stage documentation bundles without running TeX."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlsplit
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

from productization_provenance import package_version as compiler_package_version

L1_ROOT = Path(__file__).resolve().parents[1]


def pdf_name(stage: str) -> str:
    """Return the stage-qualified reference filename.

    Args:
        stage: Concrete stage name.

    Returns:
        Reference PDF basename.
    """
    return f"dea_l1_{stage}_api_reference.pdf"


def _git(root: Path, *args: str) -> str:
    """Read Git metadata, using an explicit unknown identity outside Git.

    Args:
        root: Source root used as the working directory.
        args: Git command arguments.

    Returns:
        Trimmed Git output, or unknown when unavailable.
    """
    try:
        return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def source_identity(root: Path, stage: str) -> dict[str, object]:
    """Fingerprint selected sources and generation inputs.

    Args:
        root: L1 source root.
        stage: Selected documentation stage.

    Returns:
        Revision, tree state, and a digest of named source and generator inputs.
    """
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from compiler.docgen.l1_docgen_sources import build_source_manifest

    inputs = set(build_source_manifest(root, stage).files)
    for directory in ("compiler/docgen", "scripts/docs/templates"):
        inputs.update(p.relative_to(root) for p in (root / directory).rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".j2", ".in"})
    inputs.update((Path("scripts/gen_docs.py"), Path("scripts/docs_artifacts.py")))
    digest = hashlib.sha256()
    for path in sorted(inputs):
        digest.update(path.as_posix().encode() + b"\0")
        digest.update(hashlib.sha256((root / path).read_bytes()).digest())
    state = _git(root, "status", "--porcelain")
    return {"revision": _git(root, "rev-parse", "HEAD"),
            "tree_state": "unknown" if state == "unknown" else ("dirty" if state else "clean"),
            "input_digest": digest.hexdigest()}


def package_version(root: Path) -> str:
    """Return the package identity shared with compiler distribution provenance.

    Args:
        root: L1 source root.

    Returns:
        Explicit distribution version, or the matching development identity.
    """
    version = compiler_package_version(dict(os.environ))
    tag = os.environ.get("L1_DOCS_RELEASE_TAG", "").strip()
    if tag and tag.removeprefix("l1-").removeprefix("v") != version.removeprefix("v"):
        raise ValueError("L1_DOCS_RELEASE_TAG must agree with DEA_DIST_VERSION")
    return version


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON keys instead of silently overwriting evidence."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest entry: {key}")
        result[key] = value
    return result


class _Links(HTMLParser):
    """Collect local references and resources fetched by an offline page."""

    def __init__(self) -> None:
        super().__init__()
        self.links = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if value and key in {"href", "src", "poster", "data"}:
                self.links.append((value, tag != "a"))
            if key == "srcset" and value:
                self.links.extend((entry.strip().split()[0], True) for entry in value.split(",") if entry.strip())
            if key == "style" and value:
                self.links.extend((v.strip("\"' "), True) for v in re.findall(r"url\(([^)]+)\)", value))
            if tag == "base":
                raise ValueError("offline HTML cannot override its base URL")


def verify_links(root: Path) -> None:
    """Reject missing local files, escaping links, and remote assets.

    Args:
        root: Payload directory containing HTML and PDF trees.

    Raises:
        ValueError: A resource requires checkout, sibling output, or network access.
    """
    for path in (root / "html").rglob("*"):
        if path.suffix == ".html":
            parser = _Links()
            parser.feed(path.read_text(encoding="utf-8"))
            links = parser.links
        elif path.suffix == ".css":
            links = [(v.strip("\"' "), True) for v in re.findall(r"url\(([^)]+)\)", path.read_text())]
        else:
            continue
        for value, asset in links:
            url = urlsplit(value)
            if url.scheme or url.netloc:
                if not asset and url.scheme in {"https", "http", "mailto"}:
                    continue
                if asset and url.scheme == "data":
                    continue
                raise ValueError(f"nonlocal documentation resource: {value}")
            if not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f"missing or escaping documentation link in {path.relative_to(root)}: {value}")


def _file_digests(root: Path) -> dict[str, str]:
    """Hash regular payload files, rejecting links and unrelated contents.

    Args:
        root: Offline payload root.

    Returns:
        Relative file paths mapped to SHA-256 digests, excluding the manifest.

    Raises:
        ValueError: The tree contains a link or an unrelated payload entry.
    """
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"documentation payload contains a link: {relative}")
        if relative == "manifest.json" and (not path.is_file() or path.is_symlink()):
            raise ValueError("documentation manifest is not a regular file")
        if path.is_dir() and relative not in {"html", "pdf"} and not relative.startswith(("html/", "pdf/")):
            raise ValueError(f"unexpected documentation directory: {relative}")
        if path.is_file() and relative != "manifest.json":
            if not relative.startswith(("html/", "pdf/")):
                raise ValueError(f"unexpected documentation payload: {relative}")
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify_tree(root: Path, *, stage: str, version: str, source: dict[str, object]) -> dict:
    """Verify completeness, identity, and every digest after extraction.

    Args:
        root: Extracted bundle root.
        stage: Expected stage.
        version: Expected package version.
        source: Expected source identity.

    Returns:
        Verified manifest.

    Raises:
        ValueError: The bundle is partial, stale, mismatched, or corrupt.
    """
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(manifest, dict):
            raise ValueError("invalid documentation manifest")
        if type(manifest.get("stage")) is not int or type(manifest.get("schema_version")) is not int or manifest.get("strict") is not True or manifest.get("full_pdf") is not True:
            raise ValueError("documentation bundle identity has invalid success/schema types")
        expected = {"schema_version": 1, "level": "l1", "stage": int(stage[-1]), "package_version": version,
                    "source": source, "strict": True, "full_pdf": True}
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise ValueError(f"documentation bundle identity mismatch: {key}")
        files = _file_digests(root)
        if files != manifest.get("files"):
            raise ValueError("documentation bundle file digests do not match")
        other = "stage1_l0/src" if stage == "stage2" else "stage2_l1/src"
        if any(f"/compiler/{other}/" in name for name in files):
            raise ValueError("documentation payload contains the other compiler stage")
        if "html/index.html" not in files or f"pdf/{pdf_name(stage)}" not in files:
            raise ValueError("documentation bundle requires HTML and complete PDF")
        if not (root / "pdf" / pdf_name(stage)).read_bytes().startswith(b"%PDF-"):
            raise ValueError("documentation reference is not a PDF")
        if not isinstance(manifest.get("tools"), dict) or not all(manifest["tools"].get(k) for k in ("doxygen", "pdflatex", "python", "mcss")):
            raise ValueError("documentation tool provenance is missing")
        verify_links(root)
        return manifest
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid documentation bundle: {exc}") from exc


def unpack_bundle(bundle: Path, destination: Path, *, stage: str, version: str, source: dict[str, object]) -> dict:
    """Safely extract and verify a bundle before any distribution is created.

    Args:
        bundle: Absolute path to an offline bundle.
        destination: Empty extraction directory.
        stage: Expected stage.
        version: Expected version.
        source: Expected source identity.

    Returns:
        Verified manifest.

    Raises:
        ValueError: The archive has unsafe members or fails verification.
    """
    hint = "Generate it with make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=<version> and set DOCS_ARTIFACT=<absolute-path>."
    if not bundle.is_absolute() or not bundle.is_file():
        raise ValueError(f"missing absolute DOCS_ARTIFACT bundle. {hint}")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("documentation extraction destination must be empty")
    top = f"dea-l1-{stage}-autodocs"
    try:
        with tarfile.open(bundle, "r:gz") as archive:
            seen = set()
            members = archive.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if (member.name.rstrip("/") != path.as_posix() or path.as_posix() in seen or not path.parts or path.parts[0] != top or path.is_absolute()
                        or ".." in path.parts or "\\" in member.name or ":" in member.name
                        or not (member.isfile() or member.isdir())):
                    raise ValueError(f"unsafe documentation archive member: {member.name}")
                seen.add(path.as_posix())
            archive.extractall(destination, members=members, filter="data")
        return verify_tree(destination / top, stage=stage, version=version, source=source)
    except (OSError, tarfile.TarError, ValueError) as exc:
        raise ValueError(f"invalid DOCS_ARTIFACT: {exc}. {hint}") from exc


def create_bundle(stage_root: Path, output: Path, *, stage: str, version: str, source: dict[str, object], tools: dict[str, str]) -> None:
    """Bundle a successfully completed strict HTML/full-PDF build atomically.

    Args:
        stage_root: Completed generated outputs.
        output: Destination tarball.
        stage: Selected stage.
        version: Package version.
        source: Source identity captured before generation.
        tools: Recorded tool versions.

    Raises:
        ValueError: Required outputs or provenance are invalid.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".autodocs-", dir=output.parent) as work:
        tree = Path(work) / f"dea-l1-{stage}-autodocs"
        tree.mkdir()
        shutil.copytree(stage_root / "html", tree / "html")
        # The HTML-local copy is produced only after the full PDF succeeds.
        shutil.copytree(stage_root / "pdf", tree / "pdf")
        manifest = {"schema_version": 1, "level": "l1", "stage": int(stage[-1]), "package_version": version,
                    "source": source, "tools": tools, "strict": True, "full_pdf": True,
                    "files": _file_digests(tree)}
        (tree / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verify_tree(tree, stage=stage, version=version, source=source)
        archive_path = Path(work) / "bundle.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(tree, arcname=tree.name)
        archive_path.replace(output)
