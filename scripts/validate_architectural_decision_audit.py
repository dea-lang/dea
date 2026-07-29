#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Validate and summarize the human-reviewed architectural-decision audit."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path, PurePosixPath
import re
import statistics
import subprocess
import sys


AUDIT_DIR = Path("work/audits/architectural-decisions/2026-07-26")
PLAN_PATTERNS = (
    "work/plans/*/closed/*.md",
    "l0/work/plans/*/closed/*.md",
    "l1/work/plans/*/closed/*.md",
)
INITIATIVE_PATTERN = "l1/work/initiatives/closed/*.md"
ADR_DIRS = (
    Path("docs/decisions"),
    Path("l0/docs/decisions"),
    Path("l1/docs/decisions"),
)

PRIMARY_CATEGORIES = {
    "Language syntax",
    "Language semantics",
    "Type system",
    "Ownership and memory safety",
    "Frontend architecture",
    "Semantic analysis",
    "Backend and C emission",
    "Diagnostics and recovery",
    "Runtime",
    "ABI and linking",
    "Standard library",
    "Bootstrap and self-hosting",
    "CLI and distribution",
    "Portability",
    "Repository and process architecture",
}
SCOPES = {
    "Dea-wide",
    "Shared L0/L1",
    "L0",
    "L0 Stage 1",
    "L0 Stage 2",
    "L1",
    "L1 Stage 1",
    "L1 Stage 2",
    "Repository/tooling",
}
STATUSES = {
    "Retained",
    "Superseded",
    "Retracted",
    "Deferred",
    "Historical only",
    "Unclear",
}
EXPLICITNESS = {"Explicit", "Embedded", "Inferred"}
CONFIDENCE = {"High", "Medium", "Low"}
ADR_COVERAGE = {
    "Directly covered",
    "Covered as part of a broader ADR",
    "Partially covered",
    "Not covered",
    "ADR not warranted",
    "Unclear",
}
RELATIONSHIP_TYPES = {
    "Superseded by",
    "Retracted by",
    "Narrowed by",
    "Broadened by",
    "Temporarily introduced then removed by",
    "Transferred to stable documentation by",
}

INVENTORY_FIELDS = {
    "record_type",
    "path",
    "date",
    "title",
    "kind",
    "repository_area",
    "scope",
    "stage",
    "subsystem",
    "final_status",
    "decision_count",
    "notes",
}
EVENT_FIELDS = {
    "event_id",
    "source_type",
    "source_path",
    "local_id",
    "date",
    "summary",
    "primary_category",
    "secondary_categories",
    "scope",
    "status",
    "explicitness",
    "confidence",
    "evidence_section",
    "line_start",
    "line_end",
    "evidence_paraphrase",
    "alternatives",
    "rationale",
    "current_docs",
    "related_adrs",
    "canonical_id",
    "adr_coverage",
    "adr_recommendation",
    "included_in_primary_total",
    "reviewer_notes",
}
CANONICAL_FIELDS = {
    "canonical_id",
    "summary",
    "primary_category",
    "secondary_categories",
    "scope",
    "current_status",
    "included_in_current_total",
    "historical_event_ids",
    "incoming_relationship_ids",
    "outgoing_relationship_ids",
    "affected_targets",
    "current_docs",
    "related_adrs",
    "adr_coverage",
    "adr_warranted",
    "reviewer_notes",
}
RELATIONSHIP_FIELDS = {
    "relationship_id",
    "from_event_id",
    "to_event_id",
    "relationship_type",
    "earlier_source_path",
    "later_source_path",
    "evidence_section",
    "line_start",
    "line_end",
    "explanation",
    "confidence",
}
ADR_INVENTORY_FIELDS = {
    "adr_path",
    "title",
    "status",
    "related_closed_plan_count",
    "related_closed_plans",
    "related_closed_initiatives",
    "textually_referenced_closed_plans",
    "textually_referenced_closed_initiatives",
    "canonical_decision_ids",
    "coverage_notes",
}
CANDIDATE_FIELDS = {
    "candidate_id",
    "candidate_key",
    "title",
    "destination",
    "priority",
    "canonical_decision_ids",
    "related_closed_plans",
    "related_closed_initiatives",
    "architectural_question",
    "chosen_decision",
    "alternatives",
    "rationale",
    "consequences",
    "current_docs",
    "proposed_adr_ref",
    "numbering_action",
}


def repository_root() -> Path:
    """Return the monorepo root.

    Returns:
        Absolute repository-root path.
    """

    return Path(__file__).resolve().parents[1]


def plan_metadata_title(source_text: str) -> str | None:
    """Return the Markdown plan's possibly wrapped ``Title`` metadata."""

    lines = source_text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("- Title: "):
            continue
        parts = [line.removeprefix("- Title: ").strip()]
        for continuation in lines[index + 1 :]:
            if continuation.startswith("  ") and continuation.strip():
                parts.append(continuation.strip())
                continue
            break
        return " ".join(parts)
    return None


def normalized_plan_kind(source_text: str) -> str | None:
    """Return a controlled kind derived from the plan's ``Kind`` metadata."""

    match = re.search(
        r"^- Kind: (.+)$", source_text, flags=re.MULTILINE
    )
    if match is None:
        return None
    raw_kind = match.group(1).strip().lower()
    if raw_kind.startswith("bug"):
        return "Bug Fix"
    if raw_kind.startswith("feature"):
        return "Feature"
    if raw_kind.startswith("refactor"):
        return "Refactor"
    if raw_kind.startswith("tool"):
        return "Tool"
    return None


def parse_args() -> argparse.Namespace:
    """Parse command-line options.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Validate audit coverage and IDs, then recompute aggregate statistics."
        )
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=AUDIT_DIR,
        help="Repository-relative or absolute audit directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print aggregate statistics as JSON.",
    )
    parser.add_argument(
        "--write-stats",
        type=Path,
        help=(
            "After a successful validation, write aggregate statistics "
            "as JSON to this repository-relative or absolute path."
        ),
    )
    return parser.parse_args()


def load_csv(path: Path, required_fields: set[str]) -> list[dict[str, str]]:
    """Load one CSV file and validate its header.

    Args:
        path: CSV file path.
        required_fields: Required column names.

    Returns:
        List of CSV rows.

    Raises:
        ValueError: If the file is absent or required columns are missing.
    """

    if not path.is_file():
        raise ValueError(f"missing required file: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or ())
        missing = required_fields - fields
        if missing:
            raise ValueError(f"{path}: missing columns: {sorted(missing)}")
        return list(reader)


def split_values(value: str) -> list[str]:
    """Split a pipe-separated audit field.

    Args:
        value: Raw field value.

    Returns:
        Non-empty stripped values.
    """

    return [part.strip() for part in value.split("|") if part.strip()]


def find_duplicates(values: list[str]) -> list[str]:
    """Return duplicate non-empty values in sorted order.

    Args:
        values: Values to inspect.

    Returns:
        Sorted duplicates.
    """

    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)


def markdown_table_rows(text: str) -> list[tuple[str, ...]]:
    """Return Markdown table rows with formatter padding removed.

    Args:
        text: Markdown source.

    Returns:
        Cell tuples for pipe-delimited table rows.
    """

    rows: list[tuple[str, ...]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        rows.append(
            tuple(cell.strip() for cell in stripped[1:-1].split("|"))
        )
    return rows


def table_has_prefix(
    rows: list[tuple[str, ...]], expected: tuple[str, ...]
) -> bool:
    """Return whether a Markdown table contains a row with these first cells."""

    return any(row[: len(expected)] == expected for row in rows)


def add_enum_error(
    errors: list[str],
    row_name: str,
    field_name: str,
    value: str,
    allowed: set[str],
) -> None:
    """Append an error when an enum-like field is invalid.

    Args:
        errors: Mutable error list.
        row_name: Human-readable row identifier.
        field_name: Field being checked.
        value: Field value.
        allowed: Allowed values.
    """

    if value not in allowed:
        errors.append(
            f"{row_name}: invalid {field_name} {value!r}; "
            f"expected one of {sorted(allowed)}"
        )


def git_paths_at_commit(root: Path, commit: str) -> set[str]:
    """Return repository paths recorded by one Git commit.

    Args:
        root: Repository root.
        commit: Commit object name.

    Returns:
        Repository-relative paths in the commit tree.
    """

    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def git_text_at_commit(root: Path, commit: str, path: str) -> str:
    """Return one UTF-8 repository file from a Git commit.

    Args:
        root: Repository root.
        commit: Commit object name.
        path: Repository-relative file path.

    Returns:
        File text stored in the commit.
    """

    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def validate_adr_inventory(root: Path, errors: list[str]) -> tuple[int, int]:
    """Verify each ADR index against numbered files.

    Args:
        root: Repository root.
        errors: Mutable error list.

    Returns:
        Pair of numbered ADR file count and index-entry count.
    """

    file_count = 0
    index_count = 0
    for relative_dir in ADR_DIRS:
        directory = root / relative_dir
        numbered = sorted(directory.glob("[0-9][0-9][0-9][0-9]-*.md"))
        index_text = (directory / "INDEX.md").read_text(encoding="utf-8")
        indexed_names = re.findall(
            r"\]\((\d{4}-[^)]+\.md)\)", index_text
        )
        duplicate_links = find_duplicates(indexed_names)
        if duplicate_links:
            errors.append(
                f"{relative_dir}/INDEX.md has duplicate ADR links "
                f"{duplicate_links}"
            )
        numbered_names = {path.name for path in numbered}
        indexed_name_set = set(indexed_names)
        if indexed_name_set != numbered_names:
            errors.append(
                f"{relative_dir}/INDEX.md ADR link mismatch: "
                f"missing={sorted(numbered_names - indexed_name_set)}, "
                f"extra={sorted(indexed_name_set - numbered_names)}"
            )
        file_count += len(numbered)
        index_count += len(indexed_names)
    return file_count, index_count


def numbered_adr_paths(root: Path) -> set[str]:
    """Return all numbered ADR paths relative to the repository.

    Args:
        root: Repository root.

    Returns:
        Set of repository-relative ADR paths.
    """

    return {
        path.relative_to(root).as_posix()
        for relative_dir in ADR_DIRS
        for path in (root / relative_dir).glob("[0-9][0-9][0-9][0-9]-*.md")
    }


def markdown_repository_targets(
    root: Path, source_path: str, text: str
) -> set[str]:
    """Return repository-relative targets of local Markdown links.

    Args:
        root: Repository root.
        source_path: Repository-relative Markdown source path.
        text: Markdown source text.

    Returns:
        Resolved repository-relative link targets. External URLs, anchors,
        and targets outside the repository are omitted.
    """

    raw_targets = re.findall(r"\]\(([^)]+)\)", text)
    raw_targets.extend(
        re.findall(r"^\[[^\]]+\]:\s+(\S+)", text, flags=re.MULTILINE)
    )
    targets: set[str] = set()
    source_directory = (root / source_path).parent
    repository = root.resolve()
    for raw_target in raw_targets:
        candidate = raw_target.strip()
        if candidate.startswith("<") and ">" in candidate:
            candidate = candidate[1 : candidate.index(">")]
        else:
            candidate = candidate.split(maxsplit=1)[0]
        candidate = candidate.split("#", maxsplit=1)[0]
        if (
            not candidate
            or candidate.startswith("/")
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", candidate)
        ):
            continue
        resolved = (source_directory / candidate).resolve()
        try:
            relative = resolved.relative_to(repository)
        except ValueError:
            continue
        targets.add(relative.as_posix())
    return targets


def validate_relative_paths(
    root: Path,
    row_name: str,
    field_name: str,
    value: str,
    errors: list[str],
    *,
    known_paths: set[str] | None = None,
) -> None:
    """Validate pipe-separated repository-relative file paths.

    Args:
        root: Repository root.
        row_name: Human-readable row identifier.
        field_name: Field containing paths.
        value: Pipe-separated paths.
        errors: Mutable error list.
        known_paths: Optional frozen repository-path inventory.
    """

    for relative_path in split_values(value):
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(
                f"{row_name}: {field_name} must contain repository-relative "
                f"paths, got {relative_path!r}"
            )
            continue
        if known_paths is not None:
            if relative_path not in known_paths:
                errors.append(
                    f"{row_name}: {field_name} references file absent from "
                    f"the audited commit {relative_path!r}"
                )
            continue
        resolved = (root / candidate).resolve()
        if root.resolve() not in resolved.parents or not resolved.is_file():
            errors.append(
                f"{row_name}: {field_name} references missing file "
                f"{relative_path!r}"
            )


def validate_audit(
    root: Path,
    audit_dir: Path,
    inventory: list[dict[str, str]],
    events: list[dict[str, str]],
    canonical: list[dict[str, str]],
    relationships: list[dict[str, str]],
    adr_inventory: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> tuple[list[str], dict[str, object]]:
    """Validate cross-file audit invariants and compute statistics.

    Args:
        root: Repository root.
        audit_dir: Directory containing the audit deliverables.
        inventory: Closed-plan and initiative inventory rows.
        events: Historical decision-event rows.
        canonical: Canonical decision rows.
        relationships: Supersession/retraction relationship rows.
        adr_inventory: Existing-ADR coverage rows.
        candidates: Proposed missing-ADR clusters.

    Returns:
        Pair of validation errors and computed statistics.
    """

    errors: list[str] = []
    for required_name in (
        "audit-manifest.md",
        "missing-adr-candidates.md",
        "dea-architectural-decision-audit.md",
    ):
        if not (audit_dir / required_name).is_file():
            errors.append(f"missing required audit deliverable {required_name}")
    manifest = audit_dir / "audit-manifest.md"
    if manifest.is_file():
        manifest_text = manifest.read_text(encoding="utf-8")
    else:
        manifest_text = ""
        errors.append("missing required audit manifest")

    def declared_manifest_paths(label: str) -> set[str]:
        """Read one-line or mdformat-wrapped path declarations."""

        matches = re.findall(
            rf"^- {re.escape(label)}:(?: `([^`]+)`|\n  `([^`]+)`)$",
            manifest_text,
            flags=re.MULTILINE,
        )
        return {single or wrapped for single, wrapped in matches}

    required_manifest_patterns = {
        "repository URL": (
            r"^- Repository: "
            r"<https://github\.com/googlielmo/dea-lang>$"
        ),
        "audited source remote": (
            r"^- Audited source remote: "
            r"<https://github\.com/googlielmo/DEA\.git>$"
        ),
        "baseline branch": r"^- Baseline branch: `dev`$",
        "audit date": r"^- Audit date: 2026-07-26$",
        "baseline verification": (
            r"^- Baseline verification: .+remote "
            r"`refs/heads/dev`.+\s+2026-07-26$"
        ),
        "included plan patterns": (
            r"`work/plans/\*/closed/\*\.md`"
        ),
        "limitations": r"^## Known limitations$",
        "counting definition": r"^## Counting definition$",
    }
    for label, pattern in required_manifest_patterns.items():
        if re.search(pattern, manifest_text, flags=re.MULTILINE) is None:
            errors.append(f"audit manifest omits {label}")
    sha_match = re.search(
        r"^- Audited commit: `([0-9a-f]{40})`$",
        manifest_text,
        flags=re.MULTILINE,
    )
    audited_sha = sha_match.group(1) if sha_match is not None else ""
    baseline_paths: set[str] = set()
    if sha_match is None:
        errors.append("audit manifest has no exact 40-character commit SHA")
    else:
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        ancestor_check = subprocess.run(
            ["git", "merge-base", "--is-ancestor", audited_sha, head_sha],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestor_check.returncode != 0:
            errors.append(
                f"audited commit {audited_sha} is not an ancestor of "
                f"HEAD {head_sha}"
            )
        else:
            baseline_paths = git_paths_at_commit(root, audited_sha)

    baseline_text_cache: dict[str, str] = {}

    def audited_text(path: str) -> str | None:
        """Return audited-commit text for a known baseline path."""

        if path not in baseline_paths:
            return None
        if path not in baseline_text_cache:
            baseline_text_cache[path] = git_text_at_commit(
                root, audited_sha, path
            )
        return baseline_text_cache[path]

    plan_paths = {
        path
        for path in baseline_paths
        if any(PurePosixPath(path).match(pattern) for pattern in PLAN_PATTERNS)
    }
    initiative_paths = {
        path
        for path in baseline_paths
        if PurePosixPath(path).match(INITIATIVE_PATTERN)
    }
    baseline_adr_paths: set[str] = set()
    for relative_dir in ADR_DIRS:
        prefix = f"{relative_dir.as_posix()}/"
        baseline_adr_paths.update(
            path
            for path in baseline_paths
            if path.startswith(prefix)
            and re.fullmatch(r"\d{4}-[^/]+\.md", path[len(prefix) :])
        )

    current_plan_paths = {
        path.relative_to(root).as_posix()
        for pattern in PLAN_PATTERNS
        for path in root.glob(pattern)
    }
    declared_post_baseline_plans = declared_manifest_paths(
        "Post-baseline closed plan"
    )
    actual_post_baseline_plans = current_plan_paths - plan_paths
    undeclared_post_baseline_plans = sorted(
        actual_post_baseline_plans - declared_post_baseline_plans
    )
    stale_post_baseline_plans = sorted(
        declared_post_baseline_plans - actual_post_baseline_plans
    )
    if undeclared_post_baseline_plans or stale_post_baseline_plans:
        errors.append(
            "post-baseline closed-plan declarations disagree with the "
            f"current tree: undeclared={undeclared_post_baseline_plans}, "
            f"stale_or_baseline={stale_post_baseline_plans}"
        )
    current_initiative_paths = {
        path.relative_to(root).as_posix()
        for path in root.glob(INITIATIVE_PATTERN)
    }
    post_baseline_initiatives = sorted(
        current_initiative_paths - initiative_paths
    )
    if post_baseline_initiatives:
        errors.append(
            "current tree contains post-baseline closed initiatives that "
            f"the manifest cannot declare: {post_baseline_initiatives}"
        )

    current_adr_paths = numbered_adr_paths(root)
    declared_post_baseline_adrs = declared_manifest_paths(
        "Post-baseline ADR"
    )
    declared_post_baseline_adr_amendments = declared_manifest_paths(
        "Post-baseline ADR amendment"
    )
    actual_post_baseline_adrs = current_adr_paths - baseline_adr_paths
    undeclared_post_baseline_adrs = sorted(
        actual_post_baseline_adrs - declared_post_baseline_adrs
    )
    stale_post_baseline_adrs = sorted(
        declared_post_baseline_adrs - actual_post_baseline_adrs
    )
    if undeclared_post_baseline_adrs or stale_post_baseline_adrs:
        errors.append(
            "post-baseline ADR declarations disagree with the current tree: "
            f"undeclared={undeclared_post_baseline_adrs}, "
            f"stale_or_baseline={stale_post_baseline_adrs}"
        )
    invalid_declared_adr_amendments = sorted(
        declared_post_baseline_adr_amendments
        - (baseline_adr_paths & current_adr_paths)
    )
    if invalid_declared_adr_amendments:
        errors.append(
            "post-baseline ADR amendment declarations do not name current "
            f"baseline ADRs: {invalid_declared_adr_amendments}"
        )

    inventory_paths = [row["path"] for row in inventory]
    inventory_path_set = set(inventory_paths)

    duplicates = find_duplicates(inventory_paths)
    if duplicates:
        errors.append(f"duplicate inventory paths: {duplicates}")
    expected_paths = plan_paths | initiative_paths
    if inventory_path_set != expected_paths:
        missing = sorted(expected_paths - inventory_path_set)
        extra = sorted(inventory_path_set - expected_paths)
        errors.append(f"inventory mismatch: missing={missing}, extra={extra}")

    event_ids = [row["event_id"] for row in events]
    canonical_ids = [row["canonical_id"] for row in canonical]
    relationship_ids = [row["relationship_id"] for row in relationships]
    for label, values in (
        ("event IDs", event_ids),
        ("canonical IDs", canonical_ids),
        ("relationship IDs", relationship_ids),
    ):
        duplicates = find_duplicates(values)
        if duplicates:
            errors.append(f"duplicate {label}: {duplicates}")
    local_event_keys = [
        f"{row['source_path']}::{row['local_id']}" for row in events
    ]
    duplicates = find_duplicates(local_event_keys)
    if duplicates:
        errors.append(f"duplicate source-local decision IDs: {duplicates}")

    event_id_set = set(event_ids)
    canonical_id_set = set(canonical_ids)
    known_adr_paths = baseline_adr_paths
    inventory_by_path = {row["path"]: row for row in inventory}
    events_by_source: Counter[str] = Counter()

    for row in inventory:
        path = row["path"]
        source_text = audited_text(path)
        if source_text is None:
            errors.append(f"{path}: absent from the audited commit")
            source_text = ""
        for field_name in (
            "date",
            "title",
            "scope",
            "stage",
            "subsystem",
            "final_status",
        ):
            if not row[field_name].strip():
                errors.append(f"{path}: empty metadata field {field_name}")
        expected_type = "Initiative" if path in initiative_paths else "Plan"
        if row["record_type"] != expected_type:
            errors.append(
                f"{path}: record_type={row['record_type']!r}, "
                f"expected {expected_type!r}"
            )
        if path.startswith("l0/"):
            expected_area = "L0"
        elif path.startswith("l1/"):
            expected_area = "L1"
        else:
            expected_area = "Root/shared"
        if row["repository_area"] != expected_area:
            errors.append(
                f"{path}: repository_area={row['repository_area']!r}, "
                f"expected {expected_area!r}"
            )
        expected_kind = (
            normalized_plan_kind(source_text)
            if expected_type == "Plan"
            else "Initiative"
        )
        if expected_kind is None:
            errors.append(f"{path}: unsupported or missing Kind metadata")
            expected_kind = row["kind"]
        if row["kind"] != expected_kind:
            errors.append(
                f"{path}: kind={row['kind']!r}, expected {expected_kind!r}"
            )
        status_match = re.search(
            r"^- Status: (.+)$", source_text, flags=re.MULTILINE
        )
        if (
            status_match is None
            or row["final_status"] != status_match.group(1).strip()
        ):
            errors.append(f"{path}: final status disagrees with source")
        date_match = re.search(
            r"^- (?:Date|Version): (\d{4}-\d{2}-\d{2})$",
            source_text,
            flags=re.MULTILINE,
        )
        if date_match is None or row["date"] != date_match.group(1):
            errors.append(f"{path}: date disagrees with source metadata")
        if expected_type == "Plan":
            source_title = plan_metadata_title(source_text)
            if source_title is not None and row["title"] != source_title:
                errors.append(f"{path}: title disagrees with source metadata")
        else:
            heading_match = re.search(r"^# (.+)$", source_text, re.MULTILINE)
            if (
                heading_match is None
                or row["title"] != heading_match.group(1)
            ):
                errors.append(f"{path}: title disagrees with source heading")

    for row in events:
        event_id = row["event_id"]
        source_path = row["source_path"]
        row_name = event_id or "<event without ID>"
        for field_name in (
            "event_id",
            "local_id",
            "summary",
            "evidence_section",
            "evidence_paraphrase",
        ):
            if not row[field_name].strip():
                errors.append(f"{row_name}: empty required field {field_name}")
        if not row["current_docs"].strip() and not row["related_adrs"].strip():
            errors.append(
                f"{row_name}: requires current normative documentation "
                "or a related ADR"
            )
        if source_path not in inventory_by_path:
            errors.append(f"{row_name}: unknown source path {source_path}")
        else:
            source_record = inventory_by_path[source_path]
            if row["source_type"] != source_record["record_type"]:
                errors.append(
                    f"{row_name}: source_type={row['source_type']!r}, "
                    f"inventory has {source_record['record_type']!r}"
                )
            expected_inclusion = (
                "Yes" if source_record["record_type"] == "Plan" else "No"
            )
            if row["included_in_primary_total"] != expected_inclusion:
                errors.append(
                    f"{row_name}: included_in_primary_total="
                    f"{row['included_in_primary_total']!r}, "
                    f"expected {expected_inclusion!r}"
                )
            if row["date"] != source_record["date"]:
                errors.append(
                    f"{row_name}: date={row['date']!r}, "
                    f"inventory has {source_record['date']!r}"
                )
        events_by_source[source_path] += 1
        add_enum_error(
            errors,
            row_name,
            "primary_category",
            row["primary_category"],
            PRIMARY_CATEGORIES,
        )
        invalid_secondary = sorted(
            set(split_values(row["secondary_categories"]))
            - PRIMARY_CATEGORIES
        )
        if invalid_secondary:
            errors.append(
                f"{row_name}: invalid secondary categories "
                f"{invalid_secondary}"
            )
        add_enum_error(errors, row_name, "scope", row["scope"], SCOPES)
        add_enum_error(errors, row_name, "status", row["status"], STATUSES)
        add_enum_error(
            errors,
            row_name,
            "explicitness",
            row["explicitness"],
            EXPLICITNESS,
        )
        add_enum_error(
            errors, row_name, "confidence", row["confidence"], CONFIDENCE
        )
        add_enum_error(
            errors,
            row_name,
            "adr_coverage",
            row["adr_coverage"],
            ADR_COVERAGE,
        )
        if row["canonical_id"] not in canonical_id_set:
            errors.append(
                f"{row_name}: unknown canonical ID {row['canonical_id']!r}"
            )
        validate_relative_paths(
            root,
            row_name,
            "current_docs",
            row["current_docs"],
            errors,
            known_paths=baseline_paths,
        )
        validate_relative_paths(
            root,
            row_name,
            "related_adrs",
            row["related_adrs"],
            errors,
            known_paths=baseline_paths,
        )
        unknown_adrs = sorted(
            set(split_values(row["related_adrs"])) - known_adr_paths
        )
        if unknown_adrs:
            errors.append(
                f"{row_name}: related_adrs contains non-ADR paths "
                f"{unknown_adrs}"
            )
        try:
            start = int(row["line_start"])
            end = int(row["line_end"])
        except ValueError:
            errors.append(f"{row_name}: non-integer evidence line range")
        else:
            source_text = audited_text(source_path)
            if source_text is None:
                errors.append(
                    f"{row_name}: source absent from the audited commit "
                    f"{source_path}"
                )
            elif (
                start < 1
                or end < start
                or end > len(source_text.splitlines())
            ):
                errors.append(
                    f"{row_name}: invalid evidence range {start}-{end} "
                    f"for {source_path}"
                )

    for row in inventory:
        path = row["path"]
        try:
            recorded_count = int(row["decision_count"])
        except ValueError:
            errors.append(f"{path}: invalid decision_count")
            continue
        actual_count = events_by_source[path]
        if recorded_count != actual_count:
            errors.append(
                f"{path}: decision_count={recorded_count}, events={actual_count}"
            )
        expected_note_prefix = (
            f"Final audited decision count: {recorded_count}."
        )
        if not row["notes"].startswith(expected_note_prefix):
            errors.append(
                f"{path}: notes must begin with "
                f"{expected_note_prefix!r}"
            )

    for row in canonical:
        canonical_id = row["canonical_id"]
        if not row["summary"].strip():
            errors.append(f"{canonical_id}: empty summary")
        add_enum_error(
            errors,
            canonical_id,
            "primary_category",
            row["primary_category"],
            PRIMARY_CATEGORIES,
        )
        invalid_secondary = sorted(
            set(split_values(row["secondary_categories"]))
            - PRIMARY_CATEGORIES
        )
        if invalid_secondary:
            errors.append(
                f"{canonical_id}: invalid secondary categories "
                f"{invalid_secondary}"
            )
        add_enum_error(errors, canonical_id, "scope", row["scope"], SCOPES)
        add_enum_error(
            errors,
            canonical_id,
            "current_status",
            row["current_status"],
            STATUSES,
        )
        expected_current_inclusion = (
            "Yes"
            if row["current_status"] in {"Retained", "Deferred"}
            else "No"
        )
        if row["included_in_current_total"] != expected_current_inclusion:
            errors.append(
                f"{canonical_id}: included_in_current_total="
                f"{row['included_in_current_total']!r}, expected "
                f"{expected_current_inclusion!r}"
            )
        for field_name in (
            "incoming_relationship_ids",
            "outgoing_relationship_ids",
        ):
            unknown_relationships = sorted(
                set(split_values(row[field_name])) - set(relationship_ids)
            )
            if unknown_relationships:
                errors.append(
                    f"{canonical_id}: {field_name} has unknown IDs "
                    f"{unknown_relationships}"
                )
        add_enum_error(
            errors,
            canonical_id,
            "adr_coverage",
            row["adr_coverage"],
            ADR_COVERAGE,
        )
        if row["adr_warranted"] not in {"Yes", "No"}:
            errors.append(
                f"{canonical_id}: invalid adr_warranted "
                f"{row['adr_warranted']!r}"
            )
        validate_relative_paths(
            root,
            canonical_id,
            "current_docs",
            row["current_docs"],
            errors,
            known_paths=baseline_paths,
        )
        validate_relative_paths(
            root,
            canonical_id,
            "related_adrs",
            row["related_adrs"],
            errors,
            known_paths=baseline_paths,
        )
        unknown_adrs = sorted(
            set(split_values(row["related_adrs"])) - known_adr_paths
        )
        if unknown_adrs:
            errors.append(
                f"{canonical_id}: related_adrs contains non-ADR paths "
                f"{unknown_adrs}"
            )
        historical_ids = split_values(row["historical_event_ids"])
        if not historical_ids:
            errors.append(f"{canonical_id}: no historical events")
        unknown = sorted(set(historical_ids) - event_id_set)
        if unknown:
            errors.append(
                f"{canonical_id}: unknown historical event IDs {unknown}"
            )
        reverse = sorted(
            event["event_id"]
            for event in events
            if event["canonical_id"] == canonical_id
        )
        if sorted(historical_ids) != reverse:
            errors.append(
                f"{canonical_id}: historical_event_ids disagree with event ledger"
            )

    relationship_from = Counter(row["from_event_id"] for row in relationships)
    relationship_types_from: dict[str, set[str]] = {}
    for row in relationships:
        relationship_types_from.setdefault(
            row["from_event_id"], set()
        ).add(row["relationship_type"])
    event_by_id = {row["event_id"]: row for row in events}
    canonical_by_id = {
        row["canonical_id"]: row for row in canonical
    }
    for row in canonical:
        canonical_id = row["canonical_id"]
        coverage = row["adr_coverage"]
        warranted_value = row["adr_warranted"]
        related_adrs = split_values(row["related_adrs"])
        if (
            coverage
            in {
                "Directly covered",
                "Covered as part of a broader ADR",
                "Partially covered",
            }
            and not related_adrs
        ):
            errors.append(
                f"{canonical_id}: {coverage} but no related ADR is listed"
            )
        if coverage == "ADR not warranted" and warranted_value != "No":
            errors.append(
                f"{canonical_id}: ADR not warranted requires "
                "adr_warranted=No"
            )
        if warranted_value == "No" and coverage != "ADR not warranted":
            errors.append(
                f"{canonical_id}: adr_warranted=No requires "
                "adr_coverage='ADR not warranted'"
            )

    candidate_ids = [row["candidate_id"] for row in candidates]
    candidate_keys = [row["candidate_key"] for row in candidates]
    candidate_refs = [row["proposed_adr_ref"] for row in candidates]
    for label, values in (
        ("missing-ADR candidate IDs", candidate_ids),
        ("missing-ADR candidate keys", candidate_keys),
        ("proposed ADR references", candidate_refs),
    ):
        duplicates = find_duplicates(values)
        if duplicates:
            errors.append(f"duplicate {label}: {duplicates}")
    destination_prefixes = {
        "docs/decisions/": "DEA",
        "l0/docs/decisions/": "L0",
        "l1/docs/decisions/": "L1",
    }
    existing_adr_numbers: dict[str, set[int]] = {
        destination: set() for destination in destination_prefixes
    }
    for row in adr_inventory:
        adr_path = Path(row["adr_path"])
        destination = f"{adr_path.parent.as_posix()}/"
        if destination in existing_adr_numbers:
            existing_adr_numbers[destination].add(
                int(adr_path.name[:4])
            )
    occupied_adr_numbers = {
        destination: set(numbers)
        for destination, numbers in existing_adr_numbers.items()
    }
    for adr_path_text in numbered_adr_paths(root):
        adr_path = Path(adr_path_text)
        destination = f"{adr_path.parent.as_posix()}/"
        if destination in occupied_adr_numbers:
            occupied_adr_numbers[destination].add(
                int(adr_path.name[:4])
            )
    proposed_new_numbers: dict[str, list[int]] = {
        destination: [] for destination in destination_prefixes
    }
    baseline_adr_by_slot: dict[tuple[str, int], str] = {}
    for adr_path_text in baseline_adr_paths:
        adr_path = Path(adr_path_text)
        destination = f"{adr_path.parent.as_posix()}/"
        if destination in destination_prefixes:
            baseline_adr_by_slot[(destination, int(adr_path.name[:4]))] = (
                adr_path_text
            )
    current_adr_by_slot: dict[tuple[str, int], str] = {}
    for adr_path_text in current_adr_paths:
        adr_path = Path(adr_path_text)
        destination = f"{adr_path.parent.as_posix()}/"
        if destination not in destination_prefixes:
            continue
        slot = (destination, int(adr_path.name[:4]))
        previous_path = current_adr_by_slot.get(slot)
        if previous_path is not None:
            errors.append(
                f"duplicate current ADR number {destination}"
                f"{adr_path.name[:4]}: {previous_path!r}, {adr_path_text!r}"
            )
        current_adr_by_slot[slot] = adr_path_text
    implemented_candidate_paths: dict[str, str] = {}
    implemented_candidate_amendment_paths: set[str] = set()
    unresolved_candidate_ids: list[str] = []
    candidate_canonical_ids: list[str] = []
    for row in candidates:
        candidate_id = row["candidate_id"] or "<candidate without ID>"
        if row["priority"] not in {"P0", "P1", "P2", "P3"}:
            errors.append(
                f"{candidate_id}: invalid priority {row['priority']!r}"
            )
        if row["destination"] not in {
            "docs/decisions/",
            "l0/docs/decisions/",
            "l1/docs/decisions/",
        }:
            errors.append(
                f"{candidate_id}: invalid destination "
                f"{row['destination']!r}"
            )
        numbering_action = row["numbering_action"]
        if numbering_action not in {"New ADR", "Amend existing ADR"}:
            errors.append(
                f"{candidate_id}: invalid numbering_action "
                f"{numbering_action!r}"
            )
        destination = row["destination"]
        expected_prefix = destination_prefixes.get(destination)
        proposed_ref = row["proposed_adr_ref"]
        ref_match = (
            re.fullmatch(
                rf"{expected_prefix}-ADR-(\d{{4}})", proposed_ref
            )
            if expected_prefix is not None
            else None
        )
        if ref_match is None:
            errors.append(
                f"{candidate_id}: proposed_adr_ref {proposed_ref!r} "
                f"does not match destination {destination!r}"
            )
        else:
            proposed_number = int(ref_match.group(1))
            slot = (destination, proposed_number)
            current_candidate_path = current_adr_by_slot.get(slot)
            baseline_candidate_path = baseline_adr_by_slot.get(slot)
            if numbering_action == "New ADR":
                if baseline_candidate_path is not None:
                    errors.append(
                        f"{candidate_id}: proposed new ADR "
                        f"{proposed_ref} already existed at the audit baseline"
                    )
                elif current_candidate_path is None:
                    proposed_new_numbers[destination].append(
                        proposed_number
                    )
                    unresolved_candidate_ids.append(candidate_id)
                else:
                    implemented_candidate_paths[candidate_id] = (
                        current_candidate_path
                    )
                    current_text = (
                        root / current_candidate_path
                    ).read_text(encoding="utf-8")
                    heading_pattern = (
                        rf"^# ADR-{proposed_number:04d}: \S.*$"
                    )
                    if re.search(
                        heading_pattern,
                        current_text,
                        flags=re.MULTILINE,
                    ) is None:
                        errors.append(
                            f"{candidate_id}: implemented ADR does not have "
                            f"a non-empty ADR-{proposed_number:04d} heading: "
                            f"{current_candidate_path}"
                        )
            elif baseline_candidate_path is None:
                errors.append(
                    f"{candidate_id}: amendment target "
                    f"{proposed_ref} does not exist at the audit baseline"
                )
            elif current_candidate_path is None:
                errors.append(
                    f"{candidate_id}: amendment target "
                    f"{proposed_ref} is absent from the current tree"
                )
            else:
                baseline_text = audited_text(baseline_candidate_path)
                current_text = (
                    root / current_candidate_path
                ).read_text(encoding="utf-8")
                if baseline_text == current_text:
                    unresolved_candidate_ids.append(candidate_id)
                else:
                    implemented_candidate_paths[candidate_id] = (
                        current_candidate_path
                    )
            implemented_path = implemented_candidate_paths.get(
                candidate_id
            )
            if implemented_path is not None:
                if numbering_action == "Amend existing ADR":
                    implemented_candidate_amendment_paths.add(
                        implemented_path
                    )
                implemented_text = (root / implemented_path).read_text(
                    encoding="utf-8"
                )
                implemented_targets = markdown_repository_targets(
                    root, implemented_path, implemented_text
                )
                for related_path in (
                    split_values(row["related_closed_plans"])
                    + split_values(row["related_closed_initiatives"])
                    + split_values(row["current_docs"])
                ):
                    if related_path == implemented_path:
                        continue
                    if (
                        related_path not in implemented_text
                        and related_path not in implemented_targets
                    ):
                        errors.append(
                            f"{candidate_id}: implemented ADR "
                            f"{implemented_path} does not reference "
                            f"{related_path!r}"
                        )
        for field_name in (
            "candidate_key",
            "title",
            "architectural_question",
            "chosen_decision",
            "rationale",
        ):
            if not row[field_name].strip():
                errors.append(
                    f"{candidate_id}: empty required field {field_name}"
                )
        candidate_ids_for_row = split_values(
            row["canonical_decision_ids"]
        )
        if not candidate_ids_for_row:
            errors.append(f"{candidate_id}: no canonical decisions")
        candidate_canonical_ids.extend(candidate_ids_for_row)
        for canonical_id in candidate_ids_for_row:
            canonical_row = canonical_by_id.get(canonical_id)
            if canonical_row is None:
                errors.append(
                    f"{candidate_id}: unknown canonical ID {canonical_id}"
                )
                continue
            if canonical_row["current_status"] not in {
                "Retained",
                "Deferred",
            }:
                errors.append(
                    f"{candidate_id}: non-current canonical ID "
                    f"{canonical_id}"
                )
            if canonical_row["adr_warranted"] != "Yes":
                errors.append(
                    f"{candidate_id}: {canonical_id} is not ADR-worthy"
                )
            if canonical_row["adr_coverage"] not in {
                "Not covered",
                "Partially covered",
            }:
                errors.append(
                    f"{candidate_id}: {canonical_id} has incompatible "
                    f"coverage {canonical_row['adr_coverage']!r}"
                )
        related_plans = split_values(row["related_closed_plans"])
        unknown_plans = sorted(set(related_plans) - plan_paths)
        if unknown_plans:
            errors.append(
                f"{candidate_id}: unknown related plans {unknown_plans}"
            )
        related_initiatives = split_values(
            row["related_closed_initiatives"]
        )
        unknown_initiatives = sorted(
            set(related_initiatives) - initiative_paths
        )
        if unknown_initiatives:
            errors.append(
                f"{candidate_id}: unknown related initiatives "
                f"{unknown_initiatives}"
            )
        candidate_event_ids = {
            event_id
            for canonical_id in candidate_ids_for_row
            if canonical_id in canonical_by_id
            for event_id in split_values(
                canonical_by_id[canonical_id]["historical_event_ids"]
            )
        }
        expected_candidate_plans = sorted(
            {
                event_by_id[event_id]["source_path"]
                for event_id in candidate_event_ids
                if event_by_id[event_id]["source_type"] == "Plan"
            }
        )
        expected_candidate_initiatives = sorted(
            {
                event_by_id[event_id]["source_path"]
                for event_id in candidate_event_ids
                if event_by_id[event_id]["source_type"] == "Initiative"
            }
        )
        if sorted(related_plans) != expected_candidate_plans:
            errors.append(
                f"{candidate_id}: related plans disagree with canonical "
                "event provenance"
            )
        if sorted(related_initiatives) != (
            expected_candidate_initiatives
        ):
            errors.append(
                f"{candidate_id}: related initiatives disagree with "
                "canonical event provenance"
            )
        validate_relative_paths(
            root,
            candidate_id,
            "current_docs",
            row["current_docs"],
            errors,
            known_paths=baseline_paths,
        )
    if (
        declared_post_baseline_adr_amendments
        != implemented_candidate_amendment_paths
    ):
        errors.append(
            "post-baseline ADR amendment declarations disagree with "
            "implemented audit candidates: "
            f"declared={sorted(declared_post_baseline_adr_amendments)}, "
            f"implemented={sorted(implemented_candidate_amendment_paths)}"
        )
    for destination, proposed_numbers in proposed_new_numbers.items():
        existing_numbers = occupied_adr_numbers[destination]
        next_number = max(existing_numbers, default=0) + 1
        expected_numbers = list(
            range(next_number, next_number + len(proposed_numbers))
        )
        if sorted(proposed_numbers) != expected_numbers:
            errors.append(
                f"{destination}: proposed new ADR numbers "
                f"{sorted(proposed_numbers)} are not the contiguous "
                f"sequence {expected_numbers}"
            )
    duplicate_candidate_canonicals = find_duplicates(
        candidate_canonical_ids
    )
    if duplicate_candidate_canonicals:
        errors.append(
            "canonical decisions occur in multiple missing-ADR candidates: "
            f"{duplicate_candidate_canonicals}"
        )
    expected_missing_canonical_ids = {
        row["canonical_id"]
        for row in canonical
        if row["current_status"] in {"Retained", "Deferred"}
        and row["adr_warranted"] == "Yes"
        and row["adr_coverage"] == "Not covered"
    }
    recorded_missing_canonical_ids = {
        canonical_id
        for canonical_id in candidate_canonical_ids
        if canonical_id in canonical_by_id
        and canonical_by_id[canonical_id]["adr_coverage"] == "Not covered"
    }
    if recorded_missing_canonical_ids != expected_missing_canonical_ids:
        errors.append(
            "missing-ADR backlog mismatch: "
            f"missing={sorted(expected_missing_canonical_ids - recorded_missing_canonical_ids)}, "
            f"extra={sorted(recorded_missing_canonical_ids - expected_missing_canonical_ids)}"
        )

    for row in relationships:
        relationship_id = row["relationship_id"]
        for field_name in ("evidence_section", "explanation"):
            if not row[field_name].strip():
                errors.append(
                    f"{relationship_id}: empty required field {field_name}"
                )
        if row["from_event_id"] not in event_id_set:
            errors.append(
                f"{relationship_id}: unknown from_event_id "
                f"{row['from_event_id']!r}"
            )
        if row["to_event_id"] and row["to_event_id"] not in event_id_set:
            errors.append(
                f"{relationship_id}: unknown to_event_id "
                f"{row['to_event_id']!r}"
            )
        add_enum_error(
            errors,
            relationship_id,
            "relationship_type",
            row["relationship_type"],
            RELATIONSHIP_TYPES,
        )
        add_enum_error(
            errors,
            relationship_id,
            "confidence",
            row["confidence"],
            CONFIDENCE,
        )
        from_event = event_by_id.get(row["from_event_id"])
        to_event = event_by_id.get(row["to_event_id"])
        if (
            from_event is not None
            and row["earlier_source_path"] != from_event["source_path"]
        ):
            errors.append(
                f"{relationship_id}: earlier_source_path disagrees with "
                f"{row['from_event_id']}"
            )
        if (
            to_event is not None
            and row["later_source_path"] != to_event["source_path"]
        ):
            errors.append(
                f"{relationship_id}: later_source_path disagrees with "
                f"{row['to_event_id']}"
            )
        if (
            from_event is not None
            and to_event is not None
            and to_event["date"] < from_event["date"]
        ):
            errors.append(
                f"{relationship_id}: later event predates earlier event"
            )
        if (
            not row["to_event_id"]
            and (
                "/work/plans/" in row["later_source_path"]
                or "/work/initiatives/" in row["later_source_path"]
            )
        ):
            errors.append(
                f"{relationship_id}: path-only later evidence must be stable "
                "documentation, not plan/initiative material"
            )
        try:
            start = int(row["line_start"])
            end = int(row["line_end"])
        except ValueError:
            errors.append(
                f"{relationship_id}: non-integer evidence line range"
            )
        else:
            later_source_path = row["later_source_path"]
            later_source_text = audited_text(later_source_path)
            if later_source_text is None:
                errors.append(
                    f"{relationship_id}: later source absent from the "
                    f"audited commit {later_source_path}"
                )
            elif (
                start < 1
                or end < start
                or end > len(later_source_text.splitlines())
            ):
                errors.append(
                    f"{relationship_id}: invalid evidence range {start}-{end} "
                    f"for {later_source_path}"
                )

    expected_incoming: dict[str, list[str]] = {
        canonical_id: [] for canonical_id in canonical_id_set
    }
    expected_outgoing: dict[str, list[str]] = {
        canonical_id: [] for canonical_id in canonical_id_set
    }
    for row in relationships:
        from_event = event_by_id.get(row["from_event_id"])
        if from_event is not None:
            expected_outgoing[from_event["canonical_id"]].append(
                row["relationship_id"]
            )
        to_event = event_by_id.get(row["to_event_id"])
        if to_event is not None:
            expected_incoming[to_event["canonical_id"]].append(
                row["relationship_id"]
            )
    for row in canonical:
        canonical_id = row["canonical_id"]
        if split_values(row["incoming_relationship_ids"]) != (
            expected_incoming[canonical_id]
        ):
            errors.append(
                f"{canonical_id}: incoming relationship IDs disagree "
                "with relationship ledger"
            )
        if split_values(row["outgoing_relationship_ids"]) != (
            expected_outgoing[canonical_id]
        ):
            errors.append(
                f"{canonical_id}: outgoing relationship IDs disagree "
                "with relationship ledger"
            )

    for row in events:
        event_id = row["event_id"]
        status = row["status"]
        if status in {"Superseded", "Retracted"}:
            if relationship_from[event_id] == 0:
                errors.append(
                    f"{event_id}: {status} without later relationship"
                )
                continue
            compatible_types = (
                {
                    "Superseded by",
                    "Narrowed by",
                    "Broadened by",
                    "Temporarily introduced then removed by",
                }
                if status == "Superseded"
                else {
                    "Retracted by",
                    "Temporarily introduced then removed by",
                }
            )
            if not (
                relationship_types_from.get(event_id, set())
                & compatible_types
            ):
                errors.append(
                    f"{event_id}: {status} has no type-compatible later "
                    "relationship"
                )

    validate_adr_inventory(root, errors)
    recorded_adrs = [row["adr_path"] for row in adr_inventory]
    duplicates = find_duplicates(recorded_adrs)
    if duplicates:
        errors.append(f"duplicate ADR inventory paths: {duplicates}")
    if set(recorded_adrs) != baseline_adr_paths:
        missing = sorted(baseline_adr_paths - set(recorded_adrs))
        extra = sorted(set(recorded_adrs) - baseline_adr_paths)
        errors.append(f"ADR inventory mismatch: missing={missing}, extra={extra}")
    adr_file_count = len(recorded_adrs)
    adr_index_count = len(recorded_adrs)
    plan_path_set = {
        row["path"] for row in inventory if row["record_type"] == "Plan"
    }
    initiative_path_set = {
        row["path"] for row in inventory if row["record_type"] == "Initiative"
    }
    for row in adr_inventory:
        adr_path = row["adr_path"]
        row_name = adr_path or "<ADR without path>"
        adr_text = audited_text(adr_path)
        if adr_text is None:
            errors.append(f"{row_name}: absent from the audited commit")
            adr_text = ""
        heading_match = re.search(r"^# ADR-\d+: (.+)$", adr_text, re.MULTILINE)
        status_match = re.search(
            r"^- Status: (.+)$", adr_text, flags=re.MULTILINE
        )
        if heading_match is None or heading_match.group(1) != row["title"]:
            errors.append(f"{row_name}: title disagrees with ADR heading")
        if status_match is None or status_match.group(1) != row["status"]:
            errors.append(f"{row_name}: status disagrees with ADR metadata")
        referenced_sources = set(
            re.findall(
                r"(?:(?:l0|l1)/)?work/(?:plans|initiatives)/"
                r"[A-Za-z0-9_./-]+\.md",
                adr_text,
            )
        )
        expected_textual_plans = sorted(referenced_sources & plan_path_set)
        expected_textual_initiatives = sorted(
            referenced_sources & initiative_path_set
        )
        textual_plans = split_values(
            row["textually_referenced_closed_plans"]
        )
        if sorted(textual_plans) != expected_textual_plans:
            errors.append(
                f"{row_name}: textual closed-plan references disagree "
                "with ADR text"
            )
        textual_initiatives = split_values(
            row["textually_referenced_closed_initiatives"]
        )
        if sorted(textual_initiatives) != expected_textual_initiatives:
            errors.append(
                f"{row_name}: textual closed-initiative references disagree "
                "with ADR text"
            )
        try:
            recorded_plan_count = int(row["related_closed_plan_count"])
        except ValueError:
            errors.append(f"{row_name}: invalid related_closed_plan_count")
        else:
            related_plans = split_values(row["related_closed_plans"])
            if recorded_plan_count != len(related_plans):
                errors.append(
                    f"{row_name}: related_closed_plan_count="
                    f"{recorded_plan_count}, listed={len(related_plans)}"
                )
            unknown = sorted(set(related_plans) - plan_path_set)
            if unknown:
                errors.append(
                    f"{row_name}: unknown related closed plans {unknown}"
                )
        related_initiatives = split_values(
            row["related_closed_initiatives"]
        )
        unknown_initiatives = sorted(
            set(related_initiatives) - initiative_path_set
        )
        if unknown_initiatives:
            errors.append(
                f"{row_name}: unknown related closed initiatives "
                f"{unknown_initiatives}"
            )
        unknown_canonical = sorted(
            set(split_values(row["canonical_decision_ids"]))
            - canonical_id_set
        )
        if unknown_canonical:
            errors.append(
                f"{row_name}: unknown canonical decision IDs "
                f"{unknown_canonical}"
            )
        expected_canonical = sorted(
            canonical_row["canonical_id"]
            for canonical_row in canonical
            if row_name
            in split_values(canonical_row["related_adrs"])
        )
        if sorted(split_values(row["canonical_decision_ids"])) != (
            expected_canonical
        ):
            errors.append(
                f"{row_name}: canonical_decision_ids disagree with "
                "canonical ledger ADR links"
            )
        contributor_event_ids = {
            event_id
            for canonical_id in expected_canonical
            for event_id in split_values(
                canonical_by_id[canonical_id]["historical_event_ids"]
            )
        }
        expected_related_plans = sorted(
            {
                event_by_id[event_id]["source_path"]
                for event_id in contributor_event_ids
                if event_by_id[event_id]["source_type"] == "Plan"
            }
        )
        expected_related_initiatives = sorted(
            {
                event_by_id[event_id]["source_path"]
                for event_id in contributor_event_ids
                if event_by_id[event_id]["source_type"] == "Initiative"
            }
        )
        if sorted(split_values(row["related_closed_plans"])) != (
            expected_related_plans
        ):
            errors.append(
                f"{row_name}: contributing plans disagree with canonical "
                "ledger provenance"
            )
        if sorted(split_values(row["related_closed_initiatives"])) != (
            expected_related_initiatives
        ):
            errors.append(
                f"{row_name}: contributing initiatives disagree with "
                "canonical ledger provenance"
            )

    primary_inventory = [
        row for row in inventory if row["record_type"] == "Plan"
    ]
    initiative_inventory = [
        row for row in inventory if row["record_type"] == "Initiative"
    ]
    primary_events = [
        row for row in events if row["included_in_primary_total"] == "Yes"
    ]
    primary_counts = [int(row["decision_count"]) for row in primary_inventory]
    quartiles = statistics.quantiles(primary_counts, n=4, method="inclusive")
    current_canonical = [
        row
        for row in canonical
        if row["included_in_current_total"] == "Yes"
    ]
    primary_event_ids = {
        row["event_id"] for row in events if row["included_in_primary_total"] == "Yes"
    }
    plan_grounded_current = [
        row
        for row in current_canonical
        if set(split_values(row["historical_event_ids"])) & primary_event_ids
    ]
    initiative_only_current = [
        row
        for row in current_canonical
        if not (
            set(split_values(row["historical_event_ids"])) & primary_event_ids
        )
    ]
    warranted = [
        row for row in current_canonical if row["adr_warranted"] == "Yes"
    ]
    covered = [
        row
        for row in warranted
        if row["adr_coverage"]
        in {"Directly covered", "Covered as part of a broader ADR"}
    ]
    low_confidence = [
        row["event_id"] for row in events if row["confidence"] == "Low"
    ]
    primary_warranted = [
        row
        for row in plan_grounded_current
        if row["adr_warranted"] == "Yes"
    ]
    primary_covered = [
        row
        for row in primary_warranted
        if row["adr_coverage"]
        in {"Directly covered", "Covered as part of a broader ADR"}
    ]

    def compiler_stage_bucket(row: dict[str, str]) -> str:
        scope = row["scope"]
        if scope in {"L0 Stage 1", "L1 Stage 1"}:
            return "Stage 1-specific"
        if scope in {"L0 Stage 2", "L1 Stage 2"}:
            return "Stage 2-specific"
        if scope == "Repository/tooling":
            return "Repository/tooling"
        return "Cross-stage or language-level"

    historical_stage_counts = Counter(
        compiler_stage_bucket(row) for row in primary_events
    )
    current_stage_counts = Counter(
        compiler_stage_bucket(row) for row in current_canonical
    )
    primary_current_stage_counts = Counter(
        compiler_stage_bucket(row) for row in plan_grounded_current
    )
    status_counts = Counter(row["status"] for row in primary_events)
    current_status_counts = Counter(
        row["current_status"] for row in current_canonical
    )
    canonical_status_counts = Counter(
        row["current_status"] for row in canonical
    )
    primary_current_status_counts = Counter(
        row["current_status"] for row in plan_grounded_current
    )
    explicitness_counts = Counter(
        row["explicitness"] for row in primary_events
    )
    confidence_counts = Counter(
        row["confidence"] for row in primary_events
    )
    initiative_events = [
        row for row in events if row["included_in_primary_total"] == "No"
    ]
    candidate_priority_counts = Counter(
        row["priority"] for row in candidates
    )
    candidate_numbering_action_counts = Counter(
        row["numbering_action"] for row in candidates
    )
    candidate_canonical_ids = {
        canonical_id
        for row in candidates
        for canonical_id in split_values(row["canonical_decision_ids"])
    }
    candidate_coverage_counts = Counter(
        canonical_by_id[canonical_id]["adr_coverage"]
        for canonical_id in candidate_canonical_ids
    )
    adr_support_counts = Counter(
        (
            "zero"
            if int(row["related_closed_plan_count"]) == 0
            else "one"
            if int(row["related_closed_plan_count"]) == 1
            else "multiple"
        )
        for row in adr_inventory
    )
    multiple_plan_adrs = [
        row["adr_path"]
        for row in adr_inventory
        if int(row["related_closed_plan_count"]) > 1
    ]
    filename_date_mismatches = [
        row["path"]
        for row in primary_inventory
        if (
            re.match(r"^(\d{4}-\d{2}-\d{2})-", Path(row["path"]).name)
            and re.match(
                r"^(\d{4}-\d{2}-\d{2})-", Path(row["path"]).name
            ).group(1)
            != row["date"]
        )
    ]

    def adr_repository_area(path: str) -> str:
        if path.startswith("l0/"):
            return "L0"
        if path.startswith("l1/"):
            return "L1"
        return "Root/shared"

    stats: dict[str, object] = {
        "closed_plans": len(primary_inventory),
        "closed_initiatives": len(initiative_inventory),
        "historical_decision_events": len(primary_events),
        "initiative_decision_events": len(initiative_events),
        "current_distinct_decisions": len(current_canonical),
        "primary_current_distinct_decisions": len(
            plan_grounded_current
        ),
        "current_retained_decisions": current_status_counts["Retained"],
        "current_deferred_decisions": current_status_counts["Deferred"],
        "plan_grounded_current_decisions": len(plan_grounded_current),
        "initiative_only_current_decisions": len(initiative_only_current),
        "mean_decisions_per_plan": statistics.mean(primary_counts),
        "median_decisions_per_plan": statistics.median(primary_counts),
        "lower_quartile": quartiles[0],
        "upper_quartile": quartiles[2],
        "maximum_decisions_in_one_plan": max(primary_counts),
        "plans_by_repository_area": dict(
            sorted(Counter(row["repository_area"] for row in primary_inventory).items())
        ),
        "plans_by_kind": dict(
            sorted(Counter(row["kind"] for row in primary_inventory).items())
        ),
        "plans_by_month": dict(
            sorted(Counter(row["date"][:7] for row in primary_inventory).items())
        ),
        "decision_count_buckets": {
            "zero": sum(value == 0 for value in primary_counts),
            "one": sum(value == 1 for value in primary_counts),
            "two_to_five": sum(2 <= value <= 5 for value in primary_counts),
            "six_or_more": sum(value >= 6 for value in primary_counts),
        },
        "historical_events_by_category": {
            value: Counter(
                row["primary_category"] for row in primary_events
            )[value]
            for value in sorted(PRIMARY_CATEGORIES)
        },
        "historical_events_by_scope": {
            value: Counter(row["scope"] for row in primary_events)[value]
            for value in sorted(SCOPES)
        },
        "historical_events_by_compiler_stage": {
            value: historical_stage_counts[value]
            for value in (
                "Stage 1-specific",
                "Stage 2-specific",
                "Cross-stage or language-level",
                "Repository/tooling",
            )
        },
        "historical_events_by_month": dict(
            sorted(Counter(row["date"][:7] for row in primary_events).items())
        ),
        "historical_events_by_repository_area": dict(
            sorted(
                Counter(
                    inventory_by_path[row["source_path"]]["repository_area"]
                    for row in primary_events
                ).items()
            )
        ),
        "historical_events_by_plan_kind": dict(
            sorted(
                Counter(
                    inventory_by_path[row["source_path"]]["kind"]
                    for row in primary_events
                ).items()
            )
        ),
        "historical_events_by_status": {
            value: status_counts[value] for value in sorted(STATUSES)
        },
        "current_decisions_by_status": {
            value: current_status_counts[value] for value in sorted(STATUSES)
        },
        "canonical_decisions_by_status": {
            value: canonical_status_counts[value]
            for value in sorted(STATUSES)
        },
        "primary_current_decisions_by_status": {
            value: primary_current_status_counts[value]
            for value in sorted(STATUSES)
        },
        "historical_events_by_explicitness": {
            value: explicitness_counts[value]
            for value in sorted(EXPLICITNESS)
        },
        "historical_events_by_confidence": {
            value: confidence_counts[value]
            for value in sorted(CONFIDENCE)
        },
        "initiative_events_by_category": dict(
            sorted(
                Counter(
                    row["primary_category"] for row in initiative_events
                ).items()
            )
        ),
        "initiative_events_by_scope": dict(
            sorted(
                Counter(row["scope"] for row in initiative_events).items()
            )
        ),
        "initiative_events_by_status": {
            value: Counter(
                row["status"] for row in initiative_events
            )[value]
            for value in sorted(STATUSES)
        },
        "current_decisions_by_category": {
            value: Counter(
                row["primary_category"] for row in current_canonical
            )[value]
            for value in sorted(PRIMARY_CATEGORIES)
        },
        "primary_current_decisions_by_category": {
            value: Counter(
                row["primary_category"] for row in plan_grounded_current
            )[value]
            for value in sorted(PRIMARY_CATEGORIES)
        },
        "current_decisions_by_scope": {
            value: Counter(row["scope"] for row in current_canonical)[value]
            for value in sorted(SCOPES)
        },
        "primary_current_decisions_by_scope": {
            value: Counter(row["scope"] for row in plan_grounded_current)[
                value
            ]
            for value in sorted(SCOPES)
        },
        "current_decisions_by_compiler_stage": {
            value: current_stage_counts[value]
            for value in (
                "Stage 1-specific",
                "Stage 2-specific",
                "Cross-stage or language-level",
                "Repository/tooling",
            )
        },
        "primary_current_decisions_by_compiler_stage": {
            value: primary_current_stage_counts[value]
            for value in (
                "Stage 1-specific",
                "Stage 2-specific",
                "Cross-stage or language-level",
                "Repository/tooling",
            )
        },
        "current_decisions_by_adr_coverage": {
            value: Counter(
                row["adr_coverage"] for row in current_canonical
            )[value]
            for value in sorted(ADR_COVERAGE)
        },
        "primary_current_decisions_by_adr_coverage": {
            value: Counter(
                row["adr_coverage"] for row in plan_grounded_current
            )[value]
            for value in sorted(ADR_COVERAGE)
        },
        "adr_warranted_current_decisions": len(warranted),
        "adr_covered_current_decisions": len(covered),
        "adr_partially_covered_current_decisions": sum(
            row["adr_coverage"] == "Partially covered" for row in warranted
        ),
        "adr_worthy_current_decisions_missing_an_adr": sum(
            row["adr_coverage"] == "Not covered" for row in warranted
        ),
        "adr_coverage_percentage": (
            (100.0 * len(covered) / len(warranted)) if warranted else 0.0
        ),
        "adr_coverage_percentage_including_partial": (
            (
                100.0
                * (
                    len(covered)
                    + sum(
                        row["adr_coverage"] == "Partially covered"
                        for row in warranted
                    )
                )
                / len(warranted)
            )
            if warranted
            else 0.0
        ),
        "adr_coverage_percentage_of_all_current_decisions": (
            (100.0 * len(covered) / len(current_canonical))
            if current_canonical
            else 0.0
        ),
        "primary_adr_warranted_current_decisions": len(
            primary_warranted
        ),
        "primary_adr_covered_current_decisions": len(
            primary_covered
        ),
        "primary_adr_partially_covered_current_decisions": sum(
            row["adr_coverage"] == "Partially covered"
            for row in primary_warranted
        ),
        "primary_adr_worthy_current_decisions_missing_an_adr": sum(
            row["adr_coverage"] == "Not covered"
            for row in primary_warranted
        ),
        "primary_adr_coverage_percentage": (
            100.0 * len(primary_covered) / len(primary_warranted)
            if primary_warranted
            else 0.0
        ),
        "low_confidence_event_ids": low_confidence,
        "filename_date_mismatch_count": len(filename_date_mismatches),
        "filename_date_mismatch_paths": filename_date_mismatches,
        "canonical_decision_rows": len(canonical),
        "decision_relationships": len(relationships),
        "decision_relationships_by_type": {
            value: Counter(
                row["relationship_type"] for row in relationships
            )[value]
            for value in sorted(RELATIONSHIP_TYPES)
        },
        "adr_files": adr_file_count,
        "adr_index_entries_verified": adr_index_count,
        "existing_adrs_by_repository_area": dict(
            sorted(
                Counter(
                    adr_repository_area(row["adr_path"])
                    for row in adr_inventory
                ).items()
            )
        ),
        "existing_adrs_by_plan_support": {
            key: adr_support_counts[key]
            for key in ("zero", "one", "multiple")
        },
        "adrs_supported_by_multiple_closed_plans": len(
            multiple_plan_adrs
        ),
        "multiple_plan_supported_adr_paths": multiple_plan_adrs,
        "plans_contributing_to_each_adr": {
            row["adr_path"]: split_values(row["related_closed_plans"])
            for row in adr_inventory
        },
        "proposed_adr_candidate_count": len(candidates),
        "proposed_adr_mapped_current_decisions": len(
            candidate_canonical_ids
        ),
        "proposed_adr_mapped_decisions_by_existing_coverage": dict(
            sorted(candidate_coverage_counts.items())
        ),
        "proposed_adr_candidates_by_priority": {
            priority: candidate_priority_counts[priority]
            for priority in ("P0", "P1", "P2", "P3")
        },
        "proposed_new_adr_count": candidate_numbering_action_counts[
            "New ADR"
        ],
        "proposed_adr_amendment_count": (
            candidate_numbering_action_counts["Amend existing ADR"]
        ),
        "implemented_adr_candidate_count": len(
            implemented_candidate_paths
        ),
        "implemented_adr_candidate_paths": dict(
            sorted(implemented_candidate_paths.items())
        ),
        "unresolved_adr_candidate_count": len(
            unresolved_candidate_ids
        ),
        "unresolved_adr_candidate_ids": sorted(
            unresolved_candidate_ids
        ),
        "proposed_adr_refs_by_destination": {
            destination: sorted(
                row["proposed_adr_ref"]
                for row in candidates
                if row["destination"] == destination
            )
            for destination in (
                "docs/decisions/",
                "l0/docs/decisions/",
                "l1/docs/decisions/",
            )
        },
    }
    report_path = audit_dir / "dea-architectural-decision-audit.md"
    if report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")
        report_fragments = {
            "audited commit": f"`{audited_sha}`",
            "relationship total": (
                f"The complete {len(relationships)}-edge graph"
            ),
            "ADR candidate total": (
                f"The {len(candidates)} candidates below"
            ),
        }
        if len(implemented_candidate_paths) == len(candidates):
            report_fragments["candidate resolution"] = (
                f"all {len(candidates)} candidates were implemented"
            )
        for label, fragment in report_fragments.items():
            if fragment not in report_text:
                errors.append(
                    f"final report does not reproduce {label}: "
                    f"expected {fragment!r}"
                )
        report_table_rows = markdown_table_rows(report_text)
        required_report_rows = {
            "primary and combined historical totals": (
                "Historical decision events",
                str(len(primary_events)),
                str(len(initiative_events)),
                str(len(events)),
            ),
            "primary and combined current totals": (
                "Current distinct decisions",
                str(len(plan_grounded_current)),
                str(len(initiative_only_current)),
                str(len(current_canonical)),
            ),
        }
        for label, cells in required_report_rows.items():
            if not table_has_prefix(report_table_rows, cells):
                errors.append(
                    f"final report does not reproduce {label}: "
                    f"expected table cells {cells!r}"
                )
        for row in candidates:
            numbering_cells = (
                f"`{row['candidate_id']}`",
                f"`{row['proposed_adr_ref']}`",
            )
            if not table_has_prefix(report_table_rows, numbering_cells):
                errors.append(
                    "final report omits proposed ADR numbering: "
                    f"{numbering_cells!r}"
                )
    backlog_path = audit_dir / "missing-adr-candidates.md"
    if backlog_path.is_file():
        backlog_text = backlog_path.read_text(encoding="utf-8")
        if (
            len(implemented_candidate_paths) == len(candidates)
            and (
                f"All {len(candidates)} candidates were implemented"
                not in backlog_text
            )
        ):
            errors.append(
                "missing-ADR Markdown backlog omits current candidate "
                "resolution status"
            )
        backlog_table_rows = markdown_table_rows(backlog_text)
        for row in candidates:
            numbering_cells = (
                f"`{row['candidate_id']}`",
                f"`{row['proposed_adr_ref']}`",
            )
            if not table_has_prefix(backlog_table_rows, numbering_cells):
                errors.append(
                    "missing-ADR Markdown backlog omits proposed "
                    f"numbering: {numbering_cells!r}"
                )
    return errors, stats


def print_stats(stats: dict[str, object]) -> None:
    """Print aggregate statistics in a stable text form.

    Args:
        stats: Statistics dictionary.
    """

    for key, value in stats.items():
        print(f"{key}: {value}")


def main() -> int:
    """Run audit validation and aggregation.

    Returns:
        Process exit code.
    """

    args = parse_args()
    root = repository_root()
    audit_dir = args.audit_dir
    if not audit_dir.is_absolute():
        audit_dir = root / audit_dir
    try:
        inventory = load_csv(
            audit_dir / "closed-plan-inventory.csv", INVENTORY_FIELDS
        )
        events = load_csv(
            audit_dir / "architectural-decision-events.csv", EVENT_FIELDS
        )
        canonical = load_csv(
            audit_dir / "canonical-architectural-decisions.csv",
            CANONICAL_FIELDS,
        )
        relationships = load_csv(
            audit_dir / "decision-relationships.csv", RELATIONSHIP_FIELDS
        )
        adr_inventory = load_csv(
            audit_dir / "existing-adr-coverage.csv", ADR_INVENTORY_FIELDS
        )
        candidates = load_csv(
            audit_dir / "missing-adr-candidates.csv", CANDIDATE_FIELDS
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    errors, stats = validate_audit(
        root,
        audit_dir,
        inventory,
        events,
        canonical,
        relationships,
        adr_inventory,
        candidates,
    )
    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True))
    else:
        print_stats(stats)
    if errors:
        print("\nvalidation errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if args.write_stats is not None:
        stats_path = args.write_stats
        if not stats_path.is_absolute():
            stats_path = root / stats_path
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(
            json.dumps(stats, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if not args.json:
        print("\nvalidation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
