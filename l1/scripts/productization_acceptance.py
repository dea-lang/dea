#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Build an exact distribution and carry its verification to a checkout-free host."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

HARNESS = (
    "productization_acceptance.py", "smoke_dist.py", "distribution_archive.py",
    "docs_artifacts.py", "productization_inventory.py", "productization_provenance.py",
)
# Explicitly selected sibling modules also work under Python's isolated mode (-I).
sys.path.insert(0, str(Path(__file__).resolve().parent))


def build(directory: Path, env: dict[str, str]) -> None:
    """Build and retain one archive, original result, and portable smoke harness.

    Args:
        directory: New absolute output directory; existing destinations are rejected.
        env: Explicit documentation, version, bootstrap, and native tool controls.

    Raises:
        ValueError: Output or distribution inputs are invalid.
        OSError: Output creation or copying fails.
        subprocess.CalledProcessError: Distribution construction fails.
    """
    from dist_toolchain import distribute

    if not directory.is_absolute():
        raise ValueError("ACCEPTANCE_DIR must be an absolute new directory")
    directory.mkdir(parents=True, exist_ok=False)
    # Keep DIST_RESULT outside the checkout regardless of the evidence destination.
    with tempfile.TemporaryDirectory(prefix="l1-acceptance-result-") as temporary:
        result = Path(temporary).resolve() / "result.json"
        archive = distribute({**env, "DIST_RESULT": str(result)}, make=env.get("L1_INSTALL_MAKE", "make"))
        record = json.loads(result.read_text(encoding="utf-8"))
        if Path(record["archive_path"]) != archive:
            raise ValueError("distribution result does not identify the returned archive")
        shutil.copyfile(archive, directory / archive.name)
        shutil.copyfile(result, directory / "result.json")
    harness = directory / "harness"
    harness.mkdir()
    for name in HARNESS:
        shutil.copyfile(Path(__file__).with_name(name), harness / name)
    print(f"productization acceptance: built evidence in {directory}", flush=True)


def verify(directory: Path, env: dict[str, str]) -> None:
    """Validate the result handoff and smoke its exact transported archive.

    Args:
        directory: Evidence directory produced by build, possibly on a fresh host.
        env: Host tool selection and temporary/cache environment.

    Raises:
        ValueError: Result identity, size, digest, or payload metadata disagree.
        OSError: Evidence is missing or unreadable.
        subprocess.SubprocessError: Native smoke execution fails.
    """
    from distribution_archive import digest, extract_archive, verify_distribution
    from smoke_dist import smoke
    from productization_inventory import _unique_object

    directory = directory.resolve()
    report = directory / "acceptance.json"
    report.unlink(missing_ok=True)
    record = json.loads((directory / "result.json").read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    fields = {"schema_version", "archive_path", "archive_sha256", "archive_size", "level", "stage",
              "package_version", "maturity", "os", "arch", "provenance", "docs_bundle_sha256", "docs_source"}
    if not isinstance(record, dict) or record.keys() != fields:
        raise ValueError("distribution result must contain exactly the schema-1 fields")
    if not isinstance(record["docs_bundle_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["docs_bundle_sha256"]):
        raise ValueError("distribution result must record the documentation bundle digest")
    if (type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["level"] != "l1" or type(record["stage"]) is not int or record["stage"] != 2
            or record["maturity"] != "development" or type(record["archive_size"]) is not int):
        raise ValueError("unsupported distribution result identity")
    original = Path(record["archive_path"])
    if not original.is_absolute():
        raise ValueError("distribution result archive_path must be absolute")
    archive = directory / original.name
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("result archive must be a regular transported file")
    if archive.stat().st_size != record["archive_size"] or digest(archive) != record["archive_sha256"]:
        raise ValueError("transported archive size/digest disagrees with result")
    with tempfile.TemporaryDirectory(prefix="l1-acceptance-identity-") as temporary:
        prefix = extract_archive(archive, Path(temporary).resolve())
        inventory = verify_distribution(prefix)
        for key in ("level", "stage", "package_version", "maturity", "os", "arch", "provenance"):
            if record[key] != inventory[key]:
                raise ValueError(f"distribution result disagrees with payload: {key}")
        docs = json.loads((prefix / "share/doc/dea/l1/autodocs/stage2/manifest.json").read_text(encoding="utf-8"))
        if record["docs_source"] != docs["source"]:
            raise ValueError("distribution result disagrees with documentation source")
    smoke(archive, env)
    report.write_text(json.dumps({"schema_version": 1, "status": "passed",
                                 "archive_sha256": record["archive_sha256"],
                                 "package_version": record["package_version"],
                                 "os": record["os"], "arch": record["arch"]}, indent=2) + "\n", encoding="utf-8")
    print("productization acceptance: exact archive passed", flush=True)


def main() -> int:
    """Run the local combined gate or one phase of the hosted acceptance gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("all", "build", "verify"),
                        default=os.environ.get("ACCEPTANCE_PHASE") or "all")
    parser.add_argument("--directory", default=os.environ.get("ACCEPTANCE_DIR"))
    args = parser.parse_args()
    try:
        if args.phase not in ("all", "build", "verify"):
            raise ValueError("ACCEPTANCE_PHASE must be all, build, or verify")
        if not args.directory:
            raise ValueError("ACCEPTANCE_DIR is required (an absolute new evidence directory)")
        directory = Path(args.directory)
        if args.phase in ("all", "build"):
            build(directory, dict(os.environ))
        if args.phase in ("all", "verify"):
            verify(directory, dict(os.environ))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, tarfile.TarError,
            zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"productization acceptance: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
