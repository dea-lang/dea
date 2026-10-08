#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Build one local Stage 2 distribution with failure-safe result metadata."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from install_toolchain import REPO_ROOT, install
from distribution_archive import DOCS_PATH, digest, extract_archive, verify_distribution, write_archive
from productization_inventory import resolve_prefix


def result_destination(env: dict[str, str], output_dir: Path) -> Path | None:
    """Validate a result path before invalidating prior success.

    Results may live outside the checkout or directly in its dist directory.
    Reject links, hard links, archive names, and overlaps with explicit inputs.
    Invalid destinations are never unlinked.
    """
    value = env.get("DIST_RESULT", "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute() or path.suffix != ".json" or path.is_symlink():
        raise ValueError("DIST_RESULT must be an absolute regular .json path")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("DIST_RESULT parents must not be symlinks")
    path = path.resolve()
    if path.is_relative_to(REPO_ROOT.parent.resolve()) and path.parent != output_dir:
        raise ValueError("DIST_RESULT inside the checkout must be directly in l1/dist")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("DIST_RESULT must be a regular file with no hard links")
    for name in ("DOCS_ARTIFACT", "L1_BOOTSTRAP_L0C"):
        if env.get(name):
            source = Path(env[name]).resolve()
            if path == source or path in source.parents or source in path.parents:
                raise ValueError(f"DIST_RESULT overlaps {name}")
    return path


def publish_result(destination: Path, record: dict) -> None:
    """Close complete JSON in a sibling temporary file, then atomically replace."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".dist-result-",
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def distribute(env: dict[str, str], *, make: str = "make") -> Path:
    """Install privately, verify an archive round trip, then publish archive/result.

    Args:
        env: Explicit package, bootstrap, required docs, and optional result controls.
        make: GNU Make used by the shared installer for missing upstream preparation.

    Returns:
        Absolute path of the newly published host archive.

    Raises:
        ValueError: An input, destination, or package contract is invalid.
        OSError: Construction or atomic publication fails.
        RuntimeError: Compiler construction is unavailable.
        subprocess.CalledProcessError: A bootstrap step fails.
    """
    output_dir = REPO_ROOT / "dist"
    result = result_destination(env, output_dir)
    if result is not None:
        result.unlink(missing_ok=True)
    docs = Path(env.get("DOCS_ARTIFACT", ""))
    if not env.get("DOCS_ARTIFACT", "").strip() or not docs.is_absolute() or not docs.is_file():
        raise ValueError("DOCS_ARTIFACT is required: run make docs-artifacts DOC_STAGE=stage2 "
                         "DEA_DIST_VERSION=<version> and set DOCS_ARTIFACT=<absolute-bundle-path>")
    # Private staging is outside the checkout and disjoint from installer scratch.
    with tempfile.TemporaryDirectory(prefix="l1-dist-") as temporary:
        scratch = Path(temporary).resolve()
        snapshot = scratch / "docs.tar.gz"
        shutil.copyfile(docs, snapshot)
        docs_digest = digest(snapshot)
        prefix = install(str(scratch / "dea-l1"), {**env, "DOCS_ARTIFACT": str(snapshot)}, make=make)
        record = verify_distribution(prefix)
        stamp = datetime.strptime(record["provenance"]["build_time"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y%m%d-%H%M%S")
        windows = record["os"] == "windows"
        name = f"dea-l1-lang_{record['package_version']}_{record['os']}-{record['arch']}_{stamp}"
        name += ".zip" if windows else ".tar.gz"
        output_dir = resolve_prefix(output_dir, working_dir=REPO_ROOT,
                                    protected_paths=(docs, Path(env.get("L1_BUILD_DIR", REPO_ROOT / "build/dea"))))
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / name
        if archive_path.exists() or archive_path.is_symlink():
            raise ValueError(f"archive already exists; retry with a new build timestamp: {archive_path}")
        with tempfile.TemporaryDirectory(prefix=".dist-", dir=output_dir) as publication:
            candidate = Path(publication) / name
            write_archive(prefix, candidate, windows=windows)
            extract_archive(candidate, scratch / "roundtrip")
            docs_manifest = json.loads((prefix / DOCS_PATH / "manifest.json").read_text(encoding="utf-8"))
            result_record = {"schema_version": 1, "archive_path": str(archive_path),
                             "archive_sha256": digest(candidate), "archive_size": candidate.stat().st_size,
                             "level": "l1", "stage": 2, "package_version": record["package_version"],
                             "maturity": record["maturity"], "os": record["os"], "arch": record["arch"],
                             "provenance": record["provenance"], "docs_bundle_sha256": docs_digest,
                             "docs_source": docs_manifest["source"]}
            os.replace(candidate, archive_path)
    if result is not None:
        publish_result(result, result_record)
    return archive_path


def main() -> int:
    """Print the exact new archive path only after successful publication."""
    try:
        archive = distribute(dict(os.environ), make=os.environ.get("L1_INSTALL_MAKE", "make"))
    except (OSError, RuntimeError, ValueError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.CalledProcessError) as exc:
        print(f"dist: {exc}", file=sys.stderr)
        return 1
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
