#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Validate the structured ADR Impact contract in plans and initiatives."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Iterable, Protocol


ADR_HEADING = "## ADR Impact"
DISPOSITIONS = {
    "Pending",
    "New ADR",
    "Amend ADR",
    "Covered by ADR",
    "ADR not warranted",
}
FIELDS = ("Scope", "Disposition", "ADR", "Rationale")
ROOT_SCOPES = {"Dea-wide", "Shared", "Repository/tooling"}
LEVEL_SCOPE_RE = re.compile(r"L([0-9]+)\Z")
ADR_FILE_RE = re.compile(r"(?:l[0-9]+/)?docs/decisions/[0-9]{4}-[^/]+\.md\Z")
DECISION_RE = re.compile(r"^- Decision:(?:[ \t]+(.*))?\Z")
FIELD_RE = re.compile(r"^  - ([A-Za-z][A-Za-z /-]*):(?:[ \t]+(.*))?\Z")
LINK_RE = re.compile(
    r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
)
REFERENCE_DEFINITION_RE = re.compile(
    r"^[ \t]{0,3}\[([^\]]+)\]:[ \t]*(?:<([^>]+)>|(\S+))",
    flags=re.MULTILINE,
)
FULL_REFERENCE_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\[([^\]]*)\]")
SHORTCUT_REFERENCE_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\](?![\[(:])")


class RepositoryError(RuntimeError):
    """An expected failure while reading a repository tree."""


@dataclass(frozen=True, order=True)
class Diagnostic:
    """One deterministic, source-positioned policy violation."""

    path: str
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


@dataclass
class ImpactRecord:
    """One parsed ADR Impact decision record."""

    line: int
    decision: str
    values: dict[str, str]
    lines: dict[str, int]


@dataclass(frozen=True)
class ChangedPath:
    """A path present in the selected tree and its change provenance."""

    status: str
    path: str
    old_path: str | None = None

    @property
    def is_closure(self) -> bool:
        if not is_closed_document(self.path):
            return False
        return self.status == "A" or (
            self.status.startswith("R")
            and self.old_path is not None
            and not is_closed_document(self.old_path)
        )


class Tree(Protocol):
    """Minimal selected-tree interface used by validation."""

    def paths(self) -> set[str]:
        """Return all files in the selected tree."""

    def read_text(self, path: str) -> str:
        """Read UTF-8 text from the selected tree."""


class Worktree:
    """Read repository files from the working tree."""

    def __init__(self, root: Path) -> None:
        self.root = root
        output = run_git(
            root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
        )
        self._paths = {item for item in output.split("\0") if item}

    def paths(self) -> set[str]:
        return set(self._paths)

    def read_text(self, path: str) -> str:
        try:
            return (self.root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise RepositoryError(f"cannot read {path}: {error}") from error


class GitTree:
    """Read files from a commit tree or the Git index."""

    def __init__(self, root: Path, reference: str | None) -> None:
        self.root = root
        self.reference = reference
        if reference is None:
            output = run_git(root, "ls-files", "-z")
        else:
            output = run_git(root, "ls-tree", "-r", "--name-only", "-z", reference)
        self._paths = {item for item in output.split("\0") if item}

    def paths(self) -> set[str]:
        return set(self._paths)

    def read_text(self, path: str) -> str:
        if path not in self._paths:
            raise RepositoryError(f"path is absent from selected tree: {path}")
        spec = f":{path}" if self.reference is None else f"{self.reference}:{path}"
        return run_git(self.root, "show", spec)


def run_git(root: Path, *arguments: str) -> str:
    """Run Git and return decoded stdout, raising a controlled error."""

    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise RepositoryError(f"cannot execute git: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryError(f"git {' '.join(arguments)} failed: {detail}")
    try:
        return completed.stdout.decode("utf-8")
    except UnicodeError as error:
        raise RepositoryError(
            f"git {' '.join(arguments)} produced non-UTF-8 output"
        ) from error


def repository_root() -> Path:
    """Return the repository root containing this script."""

    return Path(__file__).resolve().parents[1]


def is_active_document(path: str) -> bool:
    """Return whether a path is an active plan or initiative."""

    parts = PurePosixPath(path).parts
    if not path.endswith(".md") or PurePosixPath(path).name == "README.md":
        return False
    if "closed" in parts or "attachments" in parts:
        return False
    if len(parts) == 4 and parts[-3] == "plans":
        return parts[0] == "work"
    if len(parts) == 5 and re.fullmatch(r"l[0-9]+", parts[0]):
        return parts[1] == "work" and parts[2] == "plans"
    if len(parts) == 3 and parts[0] == "work" and parts[1] == "initiatives":
        return True
    return (
        len(parts) == 4
        and re.fullmatch(r"l[0-9]+", parts[0]) is not None
        and parts[1] == "work"
        and parts[2] == "initiatives"
    )


def is_closed_document(path: str) -> bool:
    """Return whether a path is a closed plan or initiative."""

    parts = PurePosixPath(path).parts
    if not path.endswith(".md") or PurePosixPath(path).name == "README.md":
        return False
    if "attachments" in parts:
        return False
    if (
        len(parts) == 5
        and parts[0] == "work"
        and parts[1] == "plans"
        and parts[3] == "closed"
    ):
        return True
    if (
        len(parts) == 6
        and re.fullmatch(r"l[0-9]+", parts[0])
        and parts[1] == "work"
        and parts[2] == "plans"
        and parts[4] == "closed"
    ):
        return True
    if (
        len(parts) == 4
        and parts[0] == "work"
        and parts[1] == "initiatives"
        and parts[2] == "closed"
    ):
        return True
    return (
        len(parts) == 5
        and re.fullmatch(r"l[0-9]+", parts[0]) is not None
        and parts[1] == "work"
        and parts[2] == "initiatives"
        and parts[3] == "closed"
    )


def lifecycle_state(path: str) -> str | None:
    """Return ``active`` or ``closed`` for a lifecycle document path."""

    if is_active_document(path):
        return "active"
    if is_closed_document(path):
        return "closed"
    return None


def conventional_closed_destination(path: str) -> str | None:
    """Return the exact conventional closed path for an active document."""

    if not is_active_document(path):
        return None
    parts = list(PurePosixPath(path).parts)
    parts.insert(len(parts) - 1, "closed")
    destination = PurePosixPath(*parts).as_posix()
    return destination if is_closed_document(destination) else None


def parse_name_status(output: str) -> list[ChangedPath]:
    """Parse ``git diff --name-status -z`` output."""

    items = output.split("\0")
    if items and items[-1] == "":
        items.pop()
    changes: list[ChangedPath] = []
    index = 0
    while index < len(items):
        status = items[index]
        index += 1
        if not status:
            raise RepositoryError("git diff returned an empty status")
        if status[0] in {"R", "C"}:
            if index + 1 >= len(items):
                raise RepositoryError("git diff returned a truncated rename")
            old_path, path = items[index], items[index + 1]
            index += 2
            changes.append(ChangedPath(status, path, old_path))
        else:
            if index >= len(items):
                raise RepositoryError("git diff returned a truncated path")
            path = items[index]
            index += 1
            changes.append(ChangedPath(status, path))
    return changes


def changed_paths(
    root: Path, *, staged: bool = False, base: str | None = None, head: str | None = None
) -> list[ChangedPath]:
    """Return A/M/R destination paths for a selected comparison."""

    common = ("diff", "--name-status", "-z", "--find-renames")
    if staged:
        return parse_name_status(run_git(root, *common, "--cached", "HEAD"))
    if base is None or head is None:
        raise RepositoryError("both base and head are required")
    return parse_name_status(run_git(root, *common, base, head))


def parse_impact(path: str, text: str) -> tuple[list[ImpactRecord], list[Diagnostic]]:
    """Parse one document's ADR Impact section."""

    lines = markdown_visible_lines(text)
    headings = [index for index, line in enumerate(lines) if line.strip() == ADR_HEADING]
    if not headings:
        return [], [Diagnostic(path, 1, "missing required '## ADR Impact' section")]
    if len(headings) > 1:
        return [], [
            Diagnostic(path, index + 1, "duplicate '## ADR Impact' section")
            for index in headings[1:]
        ]

    start = headings[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    diagnostics: list[Diagnostic] = []
    records: list[ImpactRecord] = []
    current: ImpactRecord | None = None
    current_field: str | None = None
    for index in range(start + 1, end):
        line = lines[index]
        line_number = index + 1
        if not line.strip():
            continue
        decision_match = DECISION_RE.fullmatch(line)
        if decision_match:
            decision = (decision_match.group(1) or "").strip()
            current = ImpactRecord(line_number, decision, {}, {})
            records.append(current)
            current_field = None
            if not decision:
                diagnostics.append(
                    Diagnostic(path, line_number, "Decision must not be empty")
                )
            continue
        field_match = FIELD_RE.fullmatch(line)
        if field_match and current is not None:
            field, value = field_match.groups()
            if field not in FIELDS:
                diagnostics.append(
                    Diagnostic(path, line_number, f"unknown ADR Impact field '{field}'")
                )
                current_field = None
                continue
            if field in current.values:
                diagnostics.append(
                    Diagnostic(path, line_number, f"duplicate ADR Impact field '{field}'")
                )
                current_field = None
                continue
            current.values[field] = (value or "").strip()
            current.lines[field] = line_number
            current_field = field
            continue
        if (
            current is not None
            and current_field is not None
            and line.startswith("    ")
            and not line.lstrip().startswith("- ")
        ):
            current.values[current_field] = (
                f"{current.values[current_field]} {line.strip()}".strip()
            )
            continue
        if (
            current is not None
            and current_field is None
            and line.startswith("  ")
            and not line.lstrip().startswith("- ")
        ):
            current.decision = f"{current.decision} {line.strip()}".strip()
            continue
        diagnostics.append(
            Diagnostic(path, line_number, "malformed ADR Impact record line")
        )
        current_field = None

    if not records:
        diagnostics.append(
            Diagnostic(path, start + 1, "ADR Impact must contain at least one decision")
        )
    for record in records:
        for field in FIELDS:
            if field not in record.values:
                diagnostics.append(
                    Diagnostic(
                        path, record.line, f"missing required ADR Impact field '{field}'"
                    )
                )
            elif not record.values[field]:
                diagnostics.append(
                    Diagnostic(
                        path,
                        record.lines[field],
                        f"ADR Impact field '{field}' must not be empty",
                    )
                )
    return records, diagnostics


def markdown_visible_lines(text: str) -> list[str]:
    """Return Markdown lines with comments and fenced code content masked."""

    visible: list[str] = []
    in_comment = False
    fence_character: str | None = None
    fence_length = 0
    for raw_line in text.splitlines():
        if fence_character is not None:
            closing = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                raw_line,
            )
            visible.append("")
            if closing is not None:
                fence_character = None
                fence_length = 0
            continue

        if not in_comment:
            raw_opening = re.match(r"^ {0,3}(`{3,}|~{3,})", raw_line)
            if raw_opening is not None:
                marker = raw_opening.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
                visible.append("")
                continue

        remaining = raw_line
        visible_parts: list[str] = []
        while remaining:
            if in_comment:
                close = remaining.find("-->")
                if close < 0:
                    remaining = ""
                    continue
                remaining = remaining[close + 3 :]
                in_comment = False
                continue
            opening = remaining.find("<!--")
            if opening < 0:
                visible_parts.append(remaining)
                remaining = ""
                continue
            visible_parts.append(remaining[:opening])
            remaining = remaining[opening + 4 :]
            in_comment = True

        line = "".join(visible_parts)
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if opening is not None:
            marker = opening.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            visible.append("")
        else:
            visible.append(line)
    return visible


def normalized_adr(value: str) -> str:
    """Strip Markdown code quoting and a harmless leading ``./``."""

    result = value.strip()
    if len(result) >= 2 and result.startswith("`") and result.endswith("`"):
        result = result[1:-1].strip()
    return result.removeprefix("./")


def scope_directory(scope: str) -> str | None:
    """Return the required decisions directory for a scope."""

    if scope in ROOT_SCOPES:
        return "docs/decisions/"
    match = LEVEL_SCOPE_RE.fullmatch(scope)
    if match:
        return f"l{match.group(1)}/docs/decisions/"
    return None


def source_level(path: str) -> int | None:
    """Return the owning language level, if any."""

    first = PurePosixPath(path).parts[0]
    match = re.fullmatch(r"l([0-9]+)", first)
    return int(match.group(1)) if match else None


def indexed_adrs(tree: Tree, directory: str) -> set[str]:
    """Return repository-relative ADR targets linked by a selected index."""

    index_path = f"{directory}INDEX.md"
    if index_path not in tree.paths():
        raise RepositoryError(f"ADR index is absent from selected tree: {index_path}")
    text = "\n".join(markdown_visible_lines(tree.read_text(index_path)))
    indexed: set[str] = set()
    base = PurePosixPath(directory)
    for target in LINK_RE.findall(text):
        clean = target.split("#", 1)[0]
        if "://" in clean or clean.startswith("#"):
            continue
        candidate = normalize_repo_path(base / clean)
        if candidate is not None and ADR_FILE_RE.fullmatch(candidate):
            indexed.add(candidate)
    return indexed


def normalize_repo_path(path: PurePosixPath) -> str | None:
    """Normalize a repository-relative path, rejecting root escapes."""

    if path.is_absolute():
        return None
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def related_plan_link_exists(adr_path: str, adr_text: str, plan_path: str) -> bool:
    """Return whether Related Plans contains a link resolving to the plan."""

    lines = markdown_visible_lines(adr_text)
    starts = [
        index for index, line in enumerate(lines) if line.strip() == "## Related Plans"
    ]
    if len(starts) != 1:
        return False
    start = starts[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    base = PurePosixPath(adr_path).parent
    section_text = "\n".join(lines[start:end])
    targets = list(LINK_RE.findall(section_text))
    visible_text = "\n".join(lines)
    definitions = {
        normalize_reference_label(label): angle_target or bare_target
        for label, angle_target, bare_target in REFERENCE_DEFINITION_RE.findall(
            visible_text
        )
    }
    occupied_spans: list[tuple[int, int]] = []
    for match in FULL_REFERENCE_LINK_RE.finditer(section_text):
        label = match.group(2) or match.group(1)
        target = definitions.get(normalize_reference_label(label))
        if target is not None:
            targets.append(target)
        occupied_spans.append(match.span())
    for match in SHORTCUT_REFERENCE_LINK_RE.finditer(section_text):
        if any(
            occupied_start <= match.start() and match.end() <= occupied_end
            for occupied_start, occupied_end in occupied_spans
        ):
            continue
        target = definitions.get(normalize_reference_label(match.group(1)))
        if target is not None:
            targets.append(target)
    for target in targets:
        target = target.split("#", 1)[0]
        if "://" in target or not target or target.startswith("/"):
            continue
        resolved = normalize_repo_path(base / target)
        if resolved == plan_path:
            return True
    return False


def normalize_reference_label(label: str) -> str:
    """Normalize a Markdown reference-link label for case-insensitive lookup."""

    return " ".join(label.split()).casefold()


def validate_record(
    tree: Tree,
    base_tree: Tree | None,
    path: str,
    record: ImpactRecord,
    *,
    closed: bool,
    closure_event: bool,
    changed: dict[str, ChangedPath],
) -> list[Diagnostic]:
    """Validate one syntactically complete ADR Impact record."""

    diagnostics: list[Diagnostic] = []
    if any(field not in record.values or not record.values[field] for field in FIELDS):
        return diagnostics
    scope = record.values["Scope"]
    disposition = record.values["Disposition"]
    adr = normalized_adr(record.values["ADR"])
    rationale = record.values["Rationale"]

    required_directory = scope_directory(scope)
    if scope != "N/A" and required_directory is None:
        diagnostics.append(
            Diagnostic(path, record.lines["Scope"], f"invalid ADR Impact scope '{scope}'")
        )
    if len(rationale.split()) < 3:
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["Rationale"],
                "Rationale must contain a substantive explanation",
            )
        )
    if disposition not in DISPOSITIONS:
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["Disposition"],
                f"invalid ADR Impact disposition '{disposition}'",
            )
        )
        return diagnostics

    owner_level = source_level(path)
    scope_match = LEVEL_SCOPE_RE.fullmatch(scope)
    if (
        scope_match
        and owner_level is not None
        and owner_level != int(scope_match.group(1))
    ):
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["Scope"],
                f"scope '{scope}' is outside the source document's ownership",
            )
        )

    if disposition == "Pending":
        if closed:
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["Disposition"],
                    "Pending is allowed only in active documents",
                )
            )
        if adr != "None":
            diagnostics.append(
                Diagnostic(path, record.lines["ADR"], "Pending requires 'ADR: None'")
            )
        if scope == "N/A":
            diagnostics.append(
                Diagnostic(path, record.lines["Scope"], "Pending requires a real scope")
            )
        return diagnostics

    if disposition == "ADR not warranted":
        if adr != "None":
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    "ADR not warranted requires 'ADR: None'",
                )
            )
        if scope != "N/A":
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["Scope"],
                    "ADR not warranted requires 'Scope: N/A'",
                )
            )
        return diagnostics

    if scope == "N/A":
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["Scope"],
                f"{disposition} requires a real scope",
            )
        )
        return diagnostics
    if required_directory is None:
        return diagnostics

    if disposition == "New ADR" and not closed:
        if adr != required_directory:
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"active New ADR must target '{required_directory}'",
                )
            )
        return diagnostics

    if not ADR_FILE_RE.fullmatch(adr):
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["ADR"],
                f"{disposition} requires an exact numbered ADR file",
            )
        )
        return diagnostics
    if not adr.startswith(required_directory):
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["ADR"],
                f"ADR target must be under '{required_directory}' for scope '{scope}'",
            )
        )
        return diagnostics
    if adr not in tree.paths():
        diagnostics.append(
            Diagnostic(path, record.lines["ADR"], f"ADR target does not exist: {adr}")
        )
        return diagnostics
    try:
        index_entries = indexed_adrs(tree, required_directory)
    except RepositoryError as error:
        diagnostics.append(Diagnostic(path, record.lines["ADR"], str(error)))
        return diagnostics
    if adr not in index_entries:
        diagnostics.append(
            Diagnostic(
                path,
                record.lines["ADR"],
                f"ADR target is not listed in {required_directory}INDEX.md",
            )
        )

    if closure_event:
        if base_tree is None:
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    "closure evidence cannot be validated without a base tree",
                )
            )
            return diagnostics
        adr_change = changed.get(adr)
        if disposition == "New ADR" and (
            adr_change is None or adr_change.status[0] != "A"
        ):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"New ADR requires {adr} to be added in the same closure change",
                )
            )
        if disposition in {"Amend ADR", "Covered by ADR"} and (
            adr_change is None or adr_change.status[0] in {"A", "C", "R"}
        ):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"{disposition} requires {adr} to exist in the base tree and change in the closure change",
                )
            )
        if (
            disposition == "New ADR"
            and f"{required_directory}INDEX.md" not in changed
        ):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"New ADR requires {required_directory}INDEX.md to change in the same closure change",
                )
            )
        if disposition == "New ADR":
            if adr in base_tree.paths():
                diagnostics.append(
                    Diagnostic(
                        path,
                        record.lines["ADR"],
                        f"New ADR target already exists in the base tree: {adr}",
                    )
                )
            base_index_path = f"{required_directory}INDEX.md"
            base_entries = (
                indexed_adrs(base_tree, required_directory)
                if base_index_path in base_tree.paths()
                else set()
            )
            if adr in base_entries:
                diagnostics.append(
                    Diagnostic(
                        path,
                        record.lines["ADR"],
                        f"New ADR index entry already exists in the base tree: {adr}",
                    )
                )
        if (
            disposition in {"Amend ADR", "Covered by ADR"}
            and adr not in base_tree.paths()
        ):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"{disposition} target is absent from the base tree: {adr}",
                )
            )
        if not related_plan_link_exists(adr, tree.read_text(adr), path):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"{adr} must link this document from its Related Plans section",
                )
            )
        if (
            disposition == "Covered by ADR"
            and adr in base_tree.paths()
            and related_plan_link_exists(adr, base_tree.read_text(adr), path)
        ):
            diagnostics.append(
                Diagnostic(
                    path,
                    record.lines["ADR"],
                    f"Covered by ADR requires the Related Plans link to be added by the closure change: {adr}",
                )
            )
    return diagnostics


def validate_document(
    tree: Tree,
    path: str,
    *,
    closed: bool,
    closure_event: bool = False,
    changed: dict[str, ChangedPath] | None = None,
    base_tree: Tree | None = None,
) -> list[Diagnostic]:
    """Validate one plan or initiative from the selected tree."""

    records, diagnostics = parse_impact(path, tree.read_text(path))
    changed_paths = changed or {}
    for record in records:
        diagnostics.extend(
            validate_record(
                tree,
                base_tree,
                path,
                record,
                closed=closed,
                closure_event=closure_event,
                changed=changed_paths,
            )
        )
    if (
        len(records) > 1
        and any(
            record.values.get("Disposition") == "ADR not warranted"
            for record in records
        )
    ):
        record = next(
            record
            for record in records
            if record.values.get("Disposition") == "ADR not warranted"
        )
        diagnostics.append(
            Diagnostic(
                path,
                record.lines.get("Disposition", record.line),
                "ADR not warranted must be the sole ADR Impact record",
            )
        )
    return diagnostics


def validate_selected_tree(
    tree: Tree,
    changes: Iterable[ChangedPath] = (),
    *,
    base_tree: Tree | None = None,
) -> list[Diagnostic]:
    """Validate all active documents and changed closed documents."""

    all_paths = tree.paths()
    change_list = list(changes)
    changed_by_path = {change.path: change for change in change_list}
    changed = set(changed_by_path)
    documents = {path for path in all_paths if is_active_document(path)}
    documents.update(
        path for path in changed if path in all_paths and is_closed_document(path)
    )
    diagnostics = validate_lifecycle_changes(change_list)
    for path in sorted(documents):
        change = changed_by_path.get(path)
        diagnostics.extend(
            validate_document(
                tree,
                path,
                closed=is_closed_document(path),
                closure_event=change.is_closure if change else False,
                changed=changed_by_path,
                base_tree=base_tree,
            )
        )
    return sorted(set(diagnostics))


def validate_lifecycle_changes(
    changes: Iterable[ChangedPath],
) -> list[Diagnostic]:
    """Reject source-side lifecycle deletions and invalid moves."""

    change_list = list(changes)
    added_paths = {
        change.path for change in change_list if change.status.startswith("A")
    }
    diagnostics: list[Diagnostic] = []
    for change in change_list:
        if change.status.startswith("D"):
            state = lifecycle_state(change.path)
            if (
                state == "active"
                and conventional_closed_destination(change.path) in added_paths
            ):
                continue
            if state is not None:
                article = "an" if state == "active" else "a"
                diagnostics.append(
                    Diagnostic(
                        change.path,
                        1,
                        f"deleting {article} {state} lifecycle document is not allowed",
                    )
                )
            continue
        if not change.status.startswith("R") or change.old_path is None:
            continue
        old_state = lifecycle_state(change.old_path)
        if old_state is None:
            continue
        new_state = lifecycle_state(change.path)
        allowed = {
            ("active", "active"),
            ("active", "closed"),
            ("closed", "closed"),
        }
        if (old_state, new_state) not in allowed:
            article = "an" if old_state == "active" else "a"
            destination = new_state or "a non-lifecycle destination"
            diagnostics.append(
                Diagnostic(
                    change.path,
                    1,
                    f"moving {article} {old_state} lifecycle document from {change.old_path} to {destination} is not allowed",
                )
            )
    return diagnostics


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Validate structured ADR Impact sections."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--all-active",
        action="store_true",
        help="validate all active plans and initiatives in the working tree",
    )
    mode.add_argument(
        "--staged",
        action="store_true",
        help="validate the Git index and changed closed documents",
    )
    mode.add_argument(
        "--base",
        metavar="SHA",
        help="base commit for CI comparison (requires --head)",
    )
    parser.add_argument("--head", metavar="SHA", help="head commit for CI comparison")
    return parser


def main(argv: list[str] | None = None, *, root: Path | None = None) -> int:
    """Run the checker and return its documented process exit code."""

    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)
    if arguments.base is not None and arguments.head is None:
        parser.print_usage(sys.stderr)
        print("check_adr_impact.py: error: --base requires --head", file=sys.stderr)
        return 2
    if arguments.head is not None and arguments.base is None:
        parser.print_usage(sys.stderr)
        print("check_adr_impact.py: error: --head requires --base", file=sys.stderr)
        return 2

    repo = (root or repository_root()).resolve()
    try:
        if arguments.all_active:
            tree: Tree = Worktree(repo)
            changes: list[ChangedPath] = []
            base_tree: Tree | None = None
        elif arguments.staged:
            tree = GitTree(repo, None)
            changes = changed_paths(repo, staged=True)
            base_tree = GitTree(repo, "HEAD")
        else:
            tree = GitTree(repo, arguments.head)
            changes = changed_paths(
                repo, base=arguments.base, head=arguments.head
            )
            base_tree = GitTree(repo, arguments.base)
        diagnostics = validate_selected_tree(
            tree, changes, base_tree=base_tree
        )
    except RepositoryError as error:
        print(f"check_adr_impact.py: repository error: {error}", file=sys.stderr)
        return 2

    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    if diagnostics:
        return 1
    print("ADR Impact validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
