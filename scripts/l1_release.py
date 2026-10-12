#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""L1 release identity, cross-host asset verification, and draft publication policy."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "l1/scripts"))
from docs_artifacts import pdf_name, source_identity, unpack_bundle, _unique_object
from distribution_archive import DOCS_PATH, digest, extract_archive, verify_distribution
from productization_acceptance import HARNESS

HOSTS = {"linux-x86_64", "macos-x86_64", "macos-arm64", "windows-x86_64"}
VERSION = re.compile(r"l1-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
SNAPSHOT = re.compile(r"l1-snapshot-(\d{8}-\d{4})-([0-9a-f]{7,40})")
DEVELOPMENT_NOTICE = ("Canonical L0-implemented L1 development toolchain. "
                      "This release does not declare language or toolchain stability.")


def package_version(tag: str, source: str | None = None) -> str:
    """Validate a tag and return its packaging version.

    Args:
        tag: L1 version or snapshot tag.
        source: Optional full commit identity to validate snapshot abbreviations.

    Returns:
        Version passed to every documentation and native build.

    Raises:
        ValueError: The tag or its source abbreviation is invalid.
    """
    if VERSION.fullmatch(tag):
        return tag.removeprefix("l1-v")
    match = SNAPSHOT.fullmatch(tag)
    if match:
        datetime.strptime(match[1], "%Y%m%d-%H%M")
        if source is not None and not source.startswith(match[2]):
            raise ValueError("snapshot abbreviation disagrees with source")
        return tag.removeprefix("l1-")
    raise ValueError(f"invalid L1 release tag: {tag!r}")


class GitHub:
    """Minimal authenticated API boundary, replaced by fakes in local policy tests."""

    def __init__(self) -> None:
        self.repository = os.environ["GITHUB_REPOSITORY"]
        self.base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
        self.token = os.environ["GH_TOKEN"]

    def api(self, path: str, data: dict | None = None, *, method: str = "GET"):
        """Call a repository API; only a nested GET 404 means resource absence.

        Args:
            path: Repository-relative API endpoint.
            data: JSON request body.
            method: HTTP method.

        Returns:
            Decoded response, or None for a missing nested GET resource.

        Raises:
            HTTPError: Repository lookup, authentication, or other API failure.
        """
        endpoint = f"{self.base.rstrip('/')}/repos/{self.repository}"
        if path:
            endpoint += "/" + path
        request = Request(endpoint,
                          data=None if data is None else json.dumps(data).encode(), method=method,
                          headers={"Authorization": f"Bearer {self.token}",
                                   "Accept": "application/vnd.github+json",
                                   "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=120) as response:
                return None if response.status == 204 else json.load(response)
        except HTTPError as exc:
            if exc.code == 404 and method == "GET" and path:
                return None
            raise

    def upload(self, tag: str, assets: list[Path]) -> None:
        """Upload the validated complete asset set to an existing draft.

        Args:
            tag: Exact release tag.
            assets: Verified files to upload, replacing same-named draft assets.

        Raises:
            subprocess.CalledProcessError: Asset upload fails.
        """
        subprocess.run(["gh", "release", "upload", tag, *map(str, assets), "--clobber",
                        "--repo", self.repository], check=True)


def tag_commit(api: GitHub, tag: str) -> str | None:
    """Resolve a lightweight or annotated remote tag to its commit.

    Args:
        api: Authenticated API boundary.
        tag: Validated tag name.

    Returns:
        Commit identity, or None if the tag is absent.

    Raises:
        ValueError: The tag chain does not resolve to a commit.
    """
    ref = api.api("git/ref/tags/" + quote(tag, safe=""))
    if ref is None:
        return None
    obj = ref["object"]
    for _ in range(10):
        if obj["type"] == "commit":
            return obj["sha"]
        if obj["type"] != "tag":
            break
        obj = api.api("git/tags/" + obj["sha"])["object"]
    raise ValueError("tag does not resolve to a commit")


def identity(api: GitHub, *, kind: str, ref: str, tag: str, run_id: str,
             saved: dict | None = None) -> dict:
    """Resolve once or reuse the original run identity without following moving refs.

    Args:
        api: GitHub API boundary.
        kind: Snapshot or versioned release.
        ref: Requested source, with an empty snapshot ref selecting the default branch.
        tag: Explicit tag, or empty for an automatic snapshot tag.
        run_id: Original workflow run identity, unchanged by reruns.
        saved: Previously uploaded identity from this run.

    Returns:
        Immutable source, tag, and package version for downstream jobs.

    Raises:
        ValueError: Requested or retained identity is inconsistent.
    """
    requested_tag = tag
    if kind not in {"snapshot", "release"}:
        raise ValueError("unknown release kind")
    if saved is not None:
        if saved.keys() != {"source", "tag", "version", "kind", "run_id", "requested_ref", "requested_tag"}:
            raise ValueError("invalid saved release identity")
        if any(saved[k] != v for k, v in {"kind": kind, "run_id": run_id,
                                        "requested_ref": ref, "requested_tag": tag}.items()):
            raise ValueError("saved identity belongs to another request")
        if not re.fullmatch(r"[0-9a-f]{40}", saved["source"]):
            raise ValueError("invalid saved source")
        pattern = SNAPSHOT if kind == "snapshot" else VERSION
        if not pattern.fullmatch(saved["tag"]):
            raise ValueError("saved tag has the wrong release kind")
        if package_version(saved["tag"], saved["source"]) != saved["version"]:
            raise ValueError("invalid saved version")
        return saved
    if kind == "release":
        if not VERSION.fullmatch(tag):
            raise ValueError("versioned releases require l1-vX.Y.Z")
        source = tag_commit(api, tag)
        if source != ref:
            raise ValueError("release tag differs from the immutable event commit")
    else:
        if tag and not SNAPSHOT.fullmatch(tag):
            raise ValueError("snapshots require l1-snapshot-YYYYMMDD-HHMM-<shorthash>")
        selected = ref or api.api("")["default_branch"]
        commit = api.api("commits/" + quote(selected, safe=""))
        if commit is None:
            raise ValueError("snapshot source does not exist")
        source = commit["sha"]
        if not tag:
            created = api.api(f"actions/runs/{run_id}")["created_at"]
            stamp = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc)
            tag = f"l1-snapshot-{stamp:%Y%m%d-%H%M}-{source[:12]}"
    if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("release source must be an immutable commit")
    return {"source": source, "tag": tag, "version": package_version(tag, source), "kind": kind,
            "run_id": run_id, "requested_ref": ref, "requested_tag": requested_tag}


def ensure_tag(api: GitHub, record: dict) -> None:
    """Create only missing snapshot tags; reject moved or missing release tags.

    Args:
        api: Authenticated API boundary.
        record: Validated source, tag, and release kind.

    Raises:
        ValueError: An existing tag disagrees or a release tag is missing.
    """
    current = tag_commit(api, record["tag"])
    if current is None and record["kind"] == "snapshot":
        api.api("git/refs", {"ref": "refs/tags/" + record["tag"], "sha": record["source"]}, method="POST")
    elif current != record["source"]:
        raise ValueError("tag is absent or points to another source; never move tags")


def curated_release_notes(root: Path, tag: str, source: str) -> str:
    """Read and validate the canonical versioned-release Markdown from its source commit.

    Args:
        root: Repository containing the immutable source revision.
        tag: Validated versioned L1 tag.
        source: Full commit identity selected for the release.

    Returns:
        Original UTF-8 Markdown, including its heading and development notice.

    Raises:
        ValueError: The identity or required notes are missing or invalid.
    """
    if not VERSION.fullmatch(tag) or not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("curated notes require a versioned L1 tag and immutable source commit")
    version = package_version(tag)
    path = f"l1/docs/releases/{version}.md"
    try:
        notes = subprocess.check_output(["git", "show", f"{source}:{path}"], cwd=root,
                                        stderr=subprocess.PIPE).decode("utf-8")
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read UTF-8 curated release notes at selected source: {path}") from exc
    if not notes.strip():
        raise ValueError(f"empty curated release notes: {path}")
    lines = notes.splitlines()
    if lines[0] != f"# Dea/L1 {version}":
        raise ValueError(f"curated release notes must start with '# Dea/L1 {version}': {path}")
    paragraphs = re.split(r"\n[ \t]*\n", "\n".join(lines[1:]).strip(), maxsplit=1)
    if " ".join(paragraphs[0].split()) != DEVELOPMENT_NOTICE:
        raise ValueError(f"curated release notes require the development notice after the heading: {path}")
    if len(paragraphs) != 2 or not paragraphs[1].strip():
        raise ValueError(f"curated release notes require content after the development notice: {path}")
    return notes


def release_notes(root: Path, tag: str, source: str) -> str:
    """Append generated history to curated versioned notes or an automatic snapshot header.

    Without a prior eligible tag, include history from the introduction of L1.

    Args:
        root: Repository with complete source history and tags.
        tag: Current validated L1 tag, excluded from baseline selection.
        source: Immutable commit being released.

    Returns:
        Markdown notes with development maturity and the full change range.

    Raises:
        subprocess.CalledProcessError: Git cannot read the required history.
        ValueError: Required curated notes are invalid or no L1 history is reachable.
    """
    version = package_version(tag)
    if VERSION.fullmatch(tag):
        opening = curated_release_notes(root, tag, source)
        if not opening.endswith("\n"):
            opening += "\n"
        opening += "\n## Commit history\n\n"
    else:
        opening = f"# Dea/L1 {version}\n\n{DEVELOPMENT_NOTICE}\n\n"
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    eligible = []
    for candidate in git("tag", "--merged", source).splitlines():
        if candidate == tag:
            continue
        try:
            package_version(candidate)
        except ValueError:
            continue
        if VERSION.fullmatch(tag) and not VERSION.fullmatch(candidate):
            continue
        eligible.append(candidate)
    if eligible:
        matches = [arg for name in eligible for arg in ("--match", name)]
        baseline = git("describe", "--tags", "--abbrev=0", f"--candidates={len(eligible)}", *matches, source)
        revisions = [f"{baseline}..{source}"]
        introduction = f"Changes since `{baseline}`:"
    else:
        history = git("log", "--reverse", "--topo-order", "--format=%H", source, "--", "l1").splitlines()
        if not history:
            raise ValueError("no L1 history is reachable from the source revision")
        # Exclude the introduction's parents, retaining the introduction even at the repository root.
        revisions = [source, f"{history[0]}^!"]
        introduction = "Initial L1 publication, including changes since L1 was introduced:"
    changes = git("log", "--format=- %s", *revisions)
    return f"{opening}{introduction}\n\n{changes}\n"


def read_json(path: Path) -> dict:
    """Read an object while rejecting duplicate keys.

    Args:
        path: JSON document to read.

    Returns:
        Decoded object.

    Raises:
        ValueError: JSON is malformed, duplicated, or not an object.
    """
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def archive_basename(value: str, host: str) -> str:
    """Read native result paths portably without changing their serialized spelling.

    Args:
        value: Original absolute archive path from the native builder.
        host: Normalized target host identifier.

    Returns:
        Archive basename suitable for lookup in transported evidence.

    Raises:
        ValueError: The original path is not absolute or its basename is unsafe.
    """
    path = PureWindowsPath(value) if host.startswith("windows-") else PurePosixPath(value)
    if not path.is_absolute() or not path.name or "/" in path.name or "\\" in path.name:
        raise ValueError("result archive path must be an absolute native path")
    return path.name


def stage_assets(root: Path, evidence: Path, reports: Path, bundle: Path,
                 output: Path, *, tag: str, source: str) -> list[Path]:
    """Validate all transported evidence before staging the seven public assets.

    Args:
        root: Checkout at the selected immutable source.
        evidence: Four host-named build evidence directories from one attempt.
        reports: Four host-named successful verification report directories.
        bundle: Shared documentation bundle from the same attempt.
        output: New destination, outside the source checkout.
        tag: Validated release tag.
        source: Selected immutable revision.

    Returns:
        Seven validated asset paths, including checksums.

    Raises:
        ValueError: Evidence is missing, stale, inconsistent, or unsafe.
        OSError: Input/output access fails.
    """
    version = package_version(tag, source)
    if {p.name for p in evidence.iterdir()} != HOSTS or {p.name for p in reports.iterdir()} != HOSTS:
        raise ValueError("expected exactly four build and verification hosts")
    docs_source = source_identity(root / "l1")
    if docs_source["revision"] != source or docs_source["tree_state"] != "clean":
        raise ValueError("publication checkout must match clean selected source")
    output.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix="l1-release-assets-") as temporary:
            scratch = Path(temporary)
            unpack_bundle(bundle.resolve(), scratch / "docs", version=version, source=docs_source)
            docs = scratch / "docs/dea-l1-autodocs"
            pdf = docs / "pdf" / pdf_name()
            bundle_hash = digest(bundle)
            for host in sorted(HOSTS):
                directory = evidence / host
                result = read_json(directory / "result.json")
                report = read_json(reports / host / "acceptance.json")
                expected_fields = {"schema_version", "archive_path", "archive_sha256", "archive_size", "level",
                                   "package_version", "maturity", "os", "arch", "provenance", "docs_bundle_sha256", "docs_source"}
                if result.keys() != expected_fields or type(result["schema_version"]) is not int or result["schema_version"] != 2:
                    raise ValueError("expected exact stage-free schema-2 result")
                os_name, arch = host.split("-", 1)
                if any(result[k] != v for k, v in {"level": "l1", "maturity": "development",
                       "package_version": version, "os": os_name, "arch": arch,
                       "docs_bundle_sha256": bundle_hash, "docs_source": docs_source}.items()):
                    raise ValueError("archive/docs/host identity mismatch")
                if result["provenance"]["source"] != {"url": "https://github.com/dea-lang/dea", "revision": source, "tree_state": "clean"}:
                    raise ValueError("archive source mismatch")
                basename = archive_basename(result["archive_path"], host)
                suffix = r"\.zip" if os_name == "windows" else r"\.tar\.gz"
                if not re.fullmatch(r"dea-l1-lang_" + re.escape(version + "_" + host) + r"_\d{8}-\d{6}" + suffix, basename):
                    raise ValueError("unexpected distribution archive name")
                archive = directory / basename
                if {p.name for p in directory.iterdir()} != {basename, "result.json", "harness"}:
                    raise ValueError("unexpected build evidence")
                if {p.name for p in (directory / "harness").iterdir()} != set(HARNESS):
                    raise ValueError("incomplete portable harness")
                for name in HARNESS:
                    if digest(directory / "harness" / name) != digest(root / "l1/scripts" / name):
                        raise ValueError("transported harness differs from selected source")
                if (archive.is_symlink() or type(result["archive_size"]) is not int
                        or archive.stat().st_size != result["archive_size"] or digest(archive) != result["archive_sha256"]):
                    raise ValueError("archive bytes differ from result")
                expected_report = {"schema_version": 2, "status": "passed", "archive_sha256": result["archive_sha256"],
                                   "package_version": version, "os": os_name, "arch": arch}
                if report != expected_report or type(report["schema_version"]) is not int:
                    raise ValueError("missing or mismatched successful acceptance report")
                prefix = extract_archive(archive, scratch / host)
                inventory = verify_distribution(prefix)
                for key in ("level", "package_version", "maturity", "os", "arch", "provenance"):
                    if inventory[key] != result[key]:
                        raise ValueError("result differs from archive inventory")
                if read_json(prefix / DOCS_PATH / "manifest.json") != read_json(docs / "manifest.json"):
                    raise ValueError("embedded docs differ from shared bundle")
                if digest(prefix / DOCS_PATH / "pdf" / pdf_name()) != digest(pdf):
                    raise ValueError("embedded PDF differs from standalone PDF")
                shutil.copyfile(archive, output / basename)
            shutil.copyfile(bundle, output / f"dea_l1_autodocs-{tag}.tar.gz")
            shutil.copyfile(pdf, output / f"dea_l1_api_reference-{tag}.pdf")
        assets = sorted(output.iterdir())
        (output / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.name}\n" for p in assets), encoding="utf-8")
        return sorted(output.iterdir())
    except Exception:
        shutil.rmtree(output)
        raise


def owned_asset(name: str, tag: str) -> bool:
    """Recognize only this tag's public assets when resuming a partial draft.

    Args:
        name: Existing asset basename.
        tag: Validated release tag.

    Returns:
        Whether the asset belongs to this tag's allowed public set.
    """
    if name in {"SHA256SUMS", f"dea_l1_autodocs-{tag}.tar.gz", f"dea_l1_api_reference-{tag}.pdf"}:
        return True
    version = package_version(tag)
    for host in HOSTS:
        suffix = r"\.zip" if host.startswith("windows-") else r"\.tar\.gz"
        if re.fullmatch(r"dea-l1-lang_" + re.escape(version + "_" + host) + r"_\d{8}-\d{6}" + suffix, name):
            return True
    return False


def publish(api: GitHub, *, tag: str, source: str, assets: list[Path], notes: str, publish_release: bool) -> None:
    """Resume only matching drafts; never mutate an already published release.

    Args:
        api: Authenticated API boundary.
        tag: Validated L1 tag.
        source: Immutable source commit.
        assets: Complete validated seven-file public set.
        notes: Generated release notes.
        publish_release: Whether to publish after attaching all assets.

    Raises:
        ValueError: Existing tag, release, or uploaded assets disagree.
    """
    package_version(tag, source)
    if tag_commit(api, tag) != source:
        raise ValueError("publication tag differs from validated source")
    prerelease = bool(SNAPSHOT.fullmatch(tag))
    endpoint = "releases/tags/" + quote(tag, safe="")
    release = api.api(endpoint)
    title = tag
    if release is not None:
        if not release["draft"]:
            raise ValueError("published release is immutable; explicit recovery is required")
        if release["tag_name"] != tag or release["target_commitish"] != source or release["prerelease"] != prerelease:
            raise ValueError("draft release identity mismatch")
        # A new full attempt has fresh archive timestamps. Remove only obsolete, recognized
        # assets from this matching draft, after the entire incoming set passed validation.
        names = [a["name"] for a in release["assets"]]
        if len(set(names)) != len(names) or any(not owned_asset(name, tag) for name in names):
            raise ValueError("draft contains unexpected assets; explicit recovery is required")
    else:
        release = api.api("releases", {"tag_name": tag, "target_commitish": source, "name": title,
                          "body": notes, "draft": True, "prerelease": prerelease, "make_latest": "false"}, method="POST")
    incoming = {p.name for p in assets}
    for asset in release["assets"]:
        if asset["name"] not in incoming:
            api.api(f"releases/assets/{asset['id']}", method="DELETE")
    api.upload(tag, assets)
    uploaded = api.api(f"releases/{release['id']}")
    if not uploaded["draft"]:
        raise ValueError("release was published concurrently")
    expected = {p.name: (p.stat().st_size, "sha256:" + digest(p)) for p in assets}
    actual = {a["name"]: (a["size"], a.get("digest")) for a in uploaded["assets"]}
    if actual != expected or len(uploaded["assets"]) != len(expected):
        raise ValueError("uploaded asset size/digest set differs from validated assets")
    api.api(f"releases/{release['id']}", {"name": title, "body": notes, "draft": not publish_release,
            "prerelease": prerelease, "make_latest": "false"}, method="PATCH")


def normalize_evidence(base: Path, attempt: str) -> None:
    """Require exact attempt-specific artifact directories before removing their prefixes.

    Args:
        base: Download directory containing evidence and reports subdirectories.
        attempt: Current workflow attempt; older evidence cannot satisfy this attempt.

    Raises:
        ValueError: Any host artifact is missing, unexpected, or from another attempt.
    """
    for category, prefix in (("evidence", "l1-dist-evidence"), ("reports", "l1-verification")):
        directory = base / category
        expected = {f"{prefix}-{attempt}-{host}" for host in HOSTS}
        if not directory.is_dir() or {p.name for p in directory.iterdir()} != expected:
            raise ValueError("missing or mixed-attempt release evidence; rerun all jobs")
    for category, prefix in (("evidence", "l1-dist-evidence"), ("reports", "l1-verification")):
        for host in HOSTS:
            (base / category / f"{prefix}-{attempt}-{host}").rename(base / category / host)


def main() -> None:
    """Run a workflow step; remote mutation occurs only in tag and publish commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "tag", "docs-inputs", "publish"))
    args = parser.parse_args()
    env = os.environ
    if args.command == "docs-inputs":
        if not re.fullmatch(r"[0-9a-f]{40}", env["SOURCE_REF"]):
            raise ValueError("docs source must be an immutable commit")
        if package_version(env["RELEASE_TAG"], env["SOURCE_REF"]) != env["DEA_DIST_VERSION"]:
            raise ValueError("docs version differs from selected tag")
        return
    api = GitHub()
    path = Path(env["RUNNER_TEMP"]) / "l1-identity/identity.json"
    if args.command == "prepare":
        saved = read_json(path) if path.exists() else None
        if saved is None and int(env["GITHUB_RUN_ATTEMPT"]) > 1:
            raise ValueError("original run identity is unavailable; start a new dispatch")
        requested_tag = env.get("REQUESTED_TAG", "")
        record = identity(api, kind=env["RELEASE_KIND"], ref=env.get("REQUESTED_REF", ""),
                          tag=requested_tag, run_id=env["GITHUB_RUN_ID"], saved=saved)
        if record["kind"] == "release":
            curated_release_notes(ROOT, record["tag"], record["source"])
        record["requested_tag"] = requested_tag
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            for key in ("source", "tag", "version"):
                stream.write(f"{key}={record[key]}\n")
    elif args.command == "tag":
        ensure_tag(api, read_json(path))
    else:
        tag, source = env["RELEASE_TAG"], env["SOURCE_REF"]
        base = Path(env["RUNNER_TEMP"]) / "l1-release"
        normalize_evidence(base, env["GITHUB_RUN_ATTEMPT"])
        assets = stage_assets(ROOT, base / "evidence", base / "reports", base / "docs/dea_l1_autodocs.tar.gz",
                              base / "assets", tag=tag, source=source)
        publish(api, tag=tag, source=source, assets=assets, notes=release_notes(ROOT, tag, source),
                publish_release=env["PUBLISH_RELEASE"] == "true")


if __name__ == "__main__":
    main()
