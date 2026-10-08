# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Curated L1 archive writing and inventory-driven, preflighted extraction."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import zipfile
from urllib.parse import unquote, urlsplit

from docs_artifacts import verify_tree
from productization_inventory import (
    MANIFEST_PATH, _relative_path, _unique_object, _validate_entries,
    read_inventory, validate_inventory, verify_payload,
)
from productization_provenance import PackageProvenance

DOCS_PATH = "share/doc/dea/l1/autodocs/stage2"
DOCUMENTS = ("README.md", "README-WINDOWS.md", "share/doc/dea/l1/toolchain.md")
BASE_FILES = {*DOCUMENTS, "VERSION", "LICENSE-MIT", "LICENSE-APACHE", "THIRD_PARTY_NOTICES",
              MANIFEST_PATH, "share/dea/l1/smoke/hello.l1", "include/dea_rt.h", "include/l1_real.h",
              "bin/l1c", "bin/l1c-stage2", "bin/l1c-stage2.native", "bin/l1-env.sh"}
WINDOWS_FILES = {"bin/l1c.cmd", "bin/l1c-stage2.cmd", "bin/l1-env.cmd"}


def digest(path: Path) -> str:
    """Hash a file without loading the archive into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def directories(paths: set[str]) -> set[str]:
    """Return exactly the parent directories implied by payload files."""
    return {parent.as_posix() for path in paths for parent in PurePosixPath(path).parents
            if parent.as_posix() != "."}


def verify_distribution(prefix: Path) -> dict:
    """Verify complete inventory, curated contents, provenance, and offline docs.

    Args:
        prefix: Private installed or extracted distribution root.

    Returns:
        Complete verified installation inventory.

    Raises:
        ValueError: The distribution is incomplete, uncurated, or inconsistent.
        OSError: Required payload files cannot be read.
    """
    record = read_inventory(prefix)
    verify_payload(prefix, record)
    entries = {entry["path"]: entry for entry in record["entries"]}
    required = BASE_FILES | (WINDOWS_FILES if record["os"] == "windows" else set())
    if not required <= entries.keys():
        raise ValueError(f"distribution lacks required files: {sorted(required - entries.keys())}")
    actual_files = {p.relative_to(prefix).as_posix() for p in prefix.rglob("*") if p.is_symlink() or not p.is_dir()}
    actual_dirs = {p.relative_to(prefix).as_posix() for p in prefix.rglob("*") if p.is_dir() and not p.is_symlink()}
    if actual_files != entries.keys() or actual_dirs != directories(set(entries)):
        raise ValueError("distribution contents differ from inventory")
    support = {}
    for path, entry in entries.items():
        if path in required:
            if path.startswith("include/"):
                support[path] = entry.get("sha256")
            continue
        if path.startswith(DOCS_PATH + "/"):
            continue
        allowed = ((path.startswith("interfaces/") and path.endswith(".l1m")) or
                   (path.startswith("shared/l1/stdlib/") and path.endswith(".l1")) or
                   (path.startswith("shared/runtime/src/") and path.endswith(".c")) or
                   (path.startswith(("shared/runtime/include/", "shared/runtime/internal/")) and path.endswith(".h")) or
                   path in {"shared/runtime/dea_rt.symbols", "shared/runtime/dea_rt_traced.symbols"})
        if not allowed or entry["kind"] != "file":
            raise ValueError(f"excluded distribution file: {path}")
        support[path] = entry["sha256"]
    provenance = record["provenance"]
    if support != provenance.get("preparation_inputs") or not any(p.startswith("interfaces/") for p in support):
        raise ValueError("distribution preparation inputs differ from provenance")
    metadata = {key: record[key] for key in ("package_version", "maturity", "os", "arch", "provenance")}
    if (prefix / "VERSION").read_text(encoding="utf-8") != PackageProvenance(json.dumps(metadata)).version_text():
        raise ValueError("VERSION differs from installation metadata")
    docs_root = prefix / DOCS_PATH
    docs = json.loads((docs_root / "manifest.json").read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    source = docs.get("source") if isinstance(docs, dict) else None
    package_source = provenance.get("source", {})
    if (not isinstance(source, dict) or set(source) != {"revision", "tree_state", "input_digest"}
            or any(source.get(key) != package_source.get(key) for key in ("revision", "tree_state"))
            or not re.fullmatch("[0-9a-f]{64}", str(source.get("input_digest")))):
        raise ValueError("documentation source differs from package provenance")
    verify_tree(docs_root, stage="stage2", version=record["package_version"], source=source)
    for name in DOCUMENTS:
        document = prefix / name
        text = document.read_text(encoding="utf-8")
        targets = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r"^\[[^]]+\]: (\S+)", text, re.MULTILINE)
        for target in targets:
            url = urlsplit(target)
            if url.scheme == "https" and url.netloc:
                continue
            path = (document.parent / unquote(url.path)).resolve()
            if url.scheme or url.netloc or not path.is_relative_to(prefix.resolve()) or not path.is_file():
                raise ValueError(f"missing or escaping packaged documentation link: {target}")
    return record


def write_archive(prefix: Path, output: Path, *, windows: bool) -> None:
    """Write only verified inventory entries under one dea-l1 root."""
    record = verify_distribution(prefix)
    entries = {entry["path"]: entry for entry in record["entries"]}
    paths = ["", *sorted(directories(set(entries))), *sorted(entries)]
    if windows:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                source = prefix / path
                name = "dea-l1" + ("/" + path if path else "")
                if source.is_symlink():
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, os.readlink(source))
                else:
                    archive.write(source, name)
                    # Windows stat modes are not the executable inventory contract.
                    info = archive.filelist[-1]
                    info.create_system = 3
                    info.external_attr = ((stat.S_IFREG | entries[path]["mode"]) << 16 if path in entries
                                          else ((stat.S_IFDIR | 0o755) << 16) | 0x10)
    else:
        with tarfile.open(output, "w:gz", dereference=False) as archive:
            for path in paths:
                archive.add(prefix / path, arcname="dea-l1" + ("/" + path if path else ""), recursive=False)


def extract_archive(archive_path: Path, destination: Path) -> Path:
    """Preflight every archive entry and alias before writing any payload byte.

    Args:
        archive_path: Exact tar.gz or zip archive to inspect.
        destination: Empty private extraction directory.

    Returns:
        Extracted and fully verified dea-l1 prefix.

    Raises:
        ValueError: Members, ownership, aliases, or distribution contents are unsafe.
        OSError: Extraction fails.
    """
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("archive extraction destination must be empty")
    zipped = archive_path.name.endswith(".zip")
    if not zipped and not archive_path.name.endswith(".tar.gz"):
        raise ValueError("ARCHIVE must be a .tar.gz or .zip file")
    opener = zipfile.ZipFile if zipped else tarfile.open
    with opener(archive_path, "r") as archive:
        members = archive.infolist() if zipped else archive.getmembers()
        indexed = {}
        entries = []
        dirs = set()
        for member in members:
            name = member.filename if zipped else member.name
            canonical = name.removesuffix("/")
            _relative_path(canonical)
            if canonical in indexed or (canonical != "dea-l1" and not canonical.startswith("dea-l1/")):
                raise ValueError(f"duplicate or unexpected archive root: {name}")
            indexed[canonical] = member
            mode = member.external_attr >> 16 if zipped else member.mode
            is_dir = member.is_dir() if zipped else member.isdir()
            is_alias = stat.S_ISLNK(mode) if zipped else member.issym()
            is_file = (stat.S_IFMT(mode) in (0, stat.S_IFREG) and not is_dir) if zipped else member.isfile()
            if not (is_dir or is_alias or is_file) or mode & 0o7000 or (name.endswith("/") and not is_dir):
                raise ValueError(f"unsupported archive member: {name}")
            if is_dir:
                dirs.add(canonical)
                continue
            path = canonical.removeprefix("dea-l1/")
            if canonical == "dea-l1":
                raise ValueError("archive root must be a directory")
            if is_alias:
                target = archive.read(member).decode("utf-8") if zipped else member.linkname
                entries.append({"path": path, "kind": "alias", "target": target})
            elif path == MANIFEST_PATH:
                entries.append({"path": path, "kind": "manifest", "mode": stat.S_IMODE(mode)})
            else:
                entries.append({"path": path, "kind": "file", "mode": stat.S_IMODE(mode), "sha256": "0" * 64})
        # Reuse inventory path/case/parent/closed-alias validation before extraction.
        _validate_entries(entries)
        file_paths = {"dea-l1/" + entry["path"] for entry in entries}
        if dirs != directories(file_paths):
            raise ValueError("archive directories differ from inventory parents")
        manifest_member = indexed["dea-l1/" + MANIFEST_PATH]
        def open_member(member):
            return archive.open(member) if zipped else archive.extractfile(member)
        with open_member(manifest_member) as stream:
            record = json.load(stream, object_pairs_hook=_unique_object)
        validate_inventory(record, require_complete=True)
        expected = {entry["path"]: entry for entry in record["entries"]}
        if set(expected) != {entry["path"] for entry in entries}:
            raise ValueError("archive files differ from inventory")
        for entry in entries:
            if {k: v for k, v in entry.items() if k != "sha256"} != {
                    k: v for k, v in expected[entry["path"]].items() if k != "sha256"}:
                raise ValueError(f"archive entry differs from inventory: {entry['path']}")
        destination.mkdir(parents=True, exist_ok=True)
        for directory in sorted(dirs):
            (destination / directory).mkdir(exist_ok=True)
        for entry in entries:
            if entry["kind"] == "alias":
                continue
            path = destination / "dea-l1" / entry["path"]
            with open_member(indexed["dea-l1/" + entry["path"]]) as source, path.open("xb") as output:
                shutil.copyfileobj(source, output)
            path.chmod(entry["mode"])
        for entry in entries:
            if entry["kind"] == "alias":
                (destination / "dea-l1" / entry["path"]).symlink_to(entry["target"])
    prefix = destination / "dea-l1"
    verify_distribution(prefix)
    return prefix
