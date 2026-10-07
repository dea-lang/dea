#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""L1 prefix ownership and recoverable payload installation primitives.

The package builder selects the payload and supplies provenance. These helpers
never build a compiler, discover a cache, or treat directory contents as ownership.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from typing import Any
import unicodedata


L1_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "share/dea/l1/install-manifest.json"
SCHEMA_VERSION = 1
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
_TARGET = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


class InventoryError(ValueError):
    """An unsafe or invalid package inventory or prefix."""


def resolve_prefix(
    value: str | Path, *, working_dir: Path = L1_ROOT,
    protected_paths: tuple[Path, ...] = (),
) -> Path:
    """Resolve a prefix independently of the repo-local build layout.

    Args:
        value: Required prefix, relative to the L1 working directory by default.
        working_dir: Source root that must not be replaced by the installation.
        protected_paths: Source/build/payload inputs that must remain disjoint.

    Returns:
        Physical absolute prefix path.

    Raises:
        InventoryError: The prefix is empty, a symlink, or overlaps an input.
    """
    if not str(value).strip():
        raise InventoryError("PREFIX is required and must not be empty")
    raw = Path(value)
    raw = raw if raw.is_absolute() else working_dir / raw
    if raw.is_symlink():
        raise InventoryError(f"PREFIX must not be a symlink: {raw}")
    prefix = raw.resolve()
    source = working_dir.resolve()
    if prefix == source or prefix in source.parents:
        raise InventoryError(f"PREFIX would replace the source root: {prefix}")
    for protected in protected_paths:
        protected = protected.resolve()
        if prefix == protected or prefix in protected.parents or protected in prefix.parents:
            raise InventoryError(f"PREFIX overlaps an installation input: {protected}")
    return prefix


def _relative_path(value: Any) -> str:
    """Validate one portable, canonical prefix-relative inventory path."""
    if not isinstance(value, str) or not value:
        raise InventoryError("inventory paths must be nonempty strings")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise InventoryError(f"noncanonical inventory path: {value!r}")
    for part in parts:
        if (any(ord(char) < 32 or ord(char) == 127 or char in '\\:*?"<>|' for char in part)
                or part.endswith((" ", ".")) or part.split(".")[0].lower() in _RESERVED):
            raise InventoryError(f"nonportable inventory path: {value!r}")
    return value


def _alias_destination(path: str, target: Any) -> str:
    """Resolve a relative alias lexically, without following filesystem links."""
    if not isinstance(target, str) or not target or target.startswith("/") or "\\" in target:
        raise InventoryError(f"alias target must be relative: {path}")
    parts = path.split("/")[:-1]
    for part in target.split("/"):
        if part in ("", "."):
            raise InventoryError(f"noncanonical alias target: {path}")
        if part == "..":
            if not parts:
                raise InventoryError(f"alias escapes PREFIX: {path}")
            parts.pop()
        else:
            _relative_path(part)
            parts.append(part)
    return _relative_path("/".join(parts))


def _validate_entries(entries: Any) -> None:
    """Validate ownership paths, modes, digests, and closed alias chains."""
    if not isinstance(entries, list):
        raise InventoryError("inventory entries must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    spellings: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise InventoryError("inventory entries must be objects")
        path = _relative_path(entry.get("path"))
        if path in indexed:
            raise InventoryError(f"duplicate inventory path: {path}")
        indexed[path] = entry
        for i in range(1, len(path.split("/")) + 1):
            parent = "/".join(path.split("/")[:i])
            previous = spellings.setdefault(unicodedata.normalize("NFC", parent).casefold(), parent)
            if previous != parent:
                raise InventoryError(f"case-colliding inventory paths: {previous}, {parent}")
        kind = entry.get("kind")
        if kind == "file":
            if set(entry) != {"path", "kind", "mode", "sha256"}:
                raise InventoryError(f"invalid file entry: {path}")
            if not isinstance(entry["sha256"], str) or not _DIGEST.fullmatch(entry["sha256"]):
                raise InventoryError(f"invalid file digest: {path}")
        elif kind == "alias":
            if set(entry) != {"path", "kind", "target"}:
                raise InventoryError(f"invalid alias entry: {path}")
            _alias_destination(path, entry["target"])
        elif kind == "manifest":
            if path != MANIFEST_PATH or set(entry) != {"path", "kind", "mode"}:
                raise InventoryError(f"invalid manifest entry: {path}")
        else:
            raise InventoryError(f"unsupported inventory entry kind: {path}")
        if kind != "alias" and (type(entry["mode"]) is not int or entry["mode"] not in (0o644, 0o755)):
            raise InventoryError(f"invalid portable file mode: {path}")
    if indexed.get(MANIFEST_PATH) != {"path": MANIFEST_PATH, "kind": "manifest", "mode": 0o644}:
        raise InventoryError("inventory must own its manifest without a self-digest")
    for path in indexed:
        if any(str(parent) in indexed for parent in PurePosixPath(path).parents if str(parent) != "."):
            raise InventoryError(f"inventory file is also a parent directory: {path}")
    for path, entry in indexed.items():
        seen = {path}
        while entry["kind"] == "alias":
            path = _alias_destination(path, entry["target"])
            if path in seen or path not in indexed or path == MANIFEST_PATH:
                raise InventoryError(f"cyclic, dangling, or metadata alias: {path}")
            seen.add(path)
            entry = indexed[path]


def _validate_native_json(record: Any) -> None:
    """Enforce the native reader's size, nesting, node, and string bounds."""
    nodes = 0

    def visit(value: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if depth > 64 or nodes > 100000:
            raise InventoryError("inventory exceeds native JSON nesting or node limits")
        if isinstance(value, str):
            if "\0" in value:
                raise InventoryError("inventory strings must not contain NUL")
            value.encode("utf-8")
        elif isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str) or "\0" in key:
                    raise InventoryError("inventory object keys must be strings without NUL")
                key.encode("utf-8")
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif value is not None and type(value) not in (bool, int, float):
            raise InventoryError("inventory must contain JSON values")

    try:
        visit(record, 0)
        wire = json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if len(wire.encode("utf-8")) > 16 * 1024 * 1024:
            raise InventoryError("inventory exceeds native JSON size limit")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise InventoryError(f"invalid native inventory JSON: {exc}") from exc


def validate_inventory(record: Any, *, require_complete: bool = False) -> None:
    """Validate schema 1 metadata without reading or hashing payload files.

    Args:
        record: Decoded JSON record.
        require_complete: Reject interruption/retry state for consumers.

    Raises:
        InventoryError: Required metadata, ownership, or state is invalid.
    """
    required = {"schema_version", "level", "stage", "state", "package_version", "maturity",
                "os", "arch", "provenance", "entries"}
    if not isinstance(record, dict):
        raise InventoryError("inventory must be an object")
    state = record.get("state")
    expected = required | ({"previous_entries"} if state == "incomplete" else set())
    if set(record) != expected:
        raise InventoryError("inventory has missing or unsupported fields")
    if (type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION
            or record["level"] != "l1" or type(record["stage"]) is not int or record["stage"] != 2):
        raise InventoryError("inventory requires schema_version=1, level=l1, stage=2")
    if state not in ("complete", "incomplete") or record["maturity"] != "development":
        raise InventoryError("invalid installation state or package maturity")
    for name, pattern in (("package_version", _TOKEN), ("os", _TARGET), ("arch", _TARGET)):
        if not isinstance(record[name], str) or not pattern.fullmatch(record[name]):
            raise InventoryError(f"invalid package {name}")
    if not isinstance(record["provenance"], dict) or not record["provenance"]:
        raise InventoryError("package provenance must be a nonempty object")
    _validate_native_json(record)
    _validate_entries(record["entries"])
    if state == "incomplete":
        _validate_entries(record["previous_entries"])
    if require_complete and state != "complete":
        raise InventoryError("installation is incomplete; retry installation before using this prefix")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject JSON object-key ambiguity shared readers could interpret differently."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError(f"duplicate inventory field: {key}")
        result[key] = value
    return result


def _safe_path(prefix: Path, relative: str) -> Path:
    """Reject substituted parent directories without following payload aliases."""
    path = prefix / _relative_path(relative)
    parents = [prefix]
    for part in relative.split("/")[:-1]:
        parents.append(parents[-1] / part)
    for parent in parents:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise InventoryError(f"unsafe destination parent: {parent}")
    return path


def read_inventory(prefix: Path, *, require_complete: bool = True) -> dict[str, Any]:
    """Read recorded ownership, rejecting invalid state with repair guidance.

    Args:
        prefix: Physical installation root.
        require_complete: Whether consumers require successful publication.

    Returns:
        Validated inventory record, without payload digest verification.

    Raises:
        InventoryError: Metadata is absent, unreadable, malformed, or incomplete.
    """
    path = _safe_path(prefix, MANIFEST_PATH)
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise InventoryError("installation metadata must be a regular file")
        record = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        validate_inventory(record, require_complete=require_complete)
        return record
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise InventoryError(f"invalid installation metadata at {path}: {exc}; repair or retry installation") from exc


def list_installed(prefix: Path) -> list[str]:
    """Return sorted recorded paths from a complete installation.

    Args:
        prefix: Physical installation root.

    Returns:
        Owned prefix-relative paths, including the inventory itself.

    Raises:
        InventoryError: The inventory is missing, invalid, or incomplete.
    """
    return sorted(entry["path"] for entry in read_inventory(prefix)["entries"])


def _digest(path: Path) -> str:
    """Hash one regular file without loading the entire payload into memory."""
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk_error(error: OSError) -> None:
    """Reject unreadable payload directories rather than silently omitting inputs."""
    raise InventoryError(f"cannot inventory payload directory: {error}") from error


def inventory_payload(payload: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    """Inventory an already curated payload and add the self-owned manifest.

    Args:
        payload: Private staging tree, excluding installation metadata.
        metadata: Package version, maturity, OS, architecture, and provenance.

    Returns:
        Complete schema 1 inventory suitable for verification/publication.

    Raises:
        InventoryError: A source, alias, or metadata field is unsafe or unsupported.
    """
    if payload.is_symlink() or not payload.is_dir():
        raise InventoryError(f"payload must be a regular directory: {payload}")
    entries = [{"path": MANIFEST_PATH, "kind": "manifest", "mode": 0o644}]
    for directory, dirs, files in os.walk(payload, followlinks=False, onerror=_walk_error):
        for name in sorted(dirs + files):
            source = Path(directory) / name
            path = _relative_path(source.relative_to(payload).as_posix())
            if path == MANIFEST_PATH or (source.parent == payload / Path(MANIFEST_PATH).parent
                                         and name.startswith(".install-manifest-")):
                raise InventoryError(f"payload must not supply private installation metadata: {path}")
            mode = source.lstat().st_mode
            if stat.S_ISLNK(mode):
                entries.append({"path": path, "kind": "alias", "target": os.readlink(source)})
            elif stat.S_ISREG(mode):
                entries.append({"path": path, "kind": "file", "mode": 0o755 if mode & 0o111 else 0o644,
                                "sha256": _digest(source)})
            elif not stat.S_ISDIR(mode):
                raise InventoryError(f"unsupported payload file type: {path}")
    record = {**metadata, "schema_version": SCHEMA_VERSION, "level": "l1", "stage": 2,
              "state": "complete", "entries": sorted(entries, key=lambda entry: entry["path"])}
    validate_inventory(record, require_complete=True)
    return record


def verify_payload(prefix: Path, record: dict[str, Any]) -> None:
    """Verify all recorded payload bytes, modes, and relative aliases.

    Args:
        prefix: Installation or staged payload root.
        record: Validated inventory; metadata publication is checked separately.

    Raises:
        InventoryError: A payload file is missing, changed, or unsafe.
    """
    validate_inventory(record)
    for entry in record["entries"]:
        if entry["kind"] == "manifest":
            continue
        path = _safe_path(prefix, entry["path"])
        if entry["kind"] == "alias":
            valid = path.is_symlink() and os.readlink(path) == entry["target"]
        else:
            valid = (not path.is_symlink() and path.is_file() and _digest(path) == entry["sha256"])
            if valid and os.name != "nt":
                valid = stat.S_IMODE(path.stat().st_mode) == entry["mode"]
        if not valid:
            raise InventoryError(f"payload verification failed: {path}")


def _publish_inventory(prefix: Path, record: dict[str, Any]) -> None:
    """Replace metadata only after a complete temporary record has been closed."""
    destination = _safe_path(prefix, MANIFEST_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".install-manifest-",
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        temporary.chmod(0o644)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def install_payload(
    payload: Path, prefix: Path, metadata: dict[str, Any], *, protected_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Replace owned payload files with recoverable, externally serialized writes.

    Args:
        payload: Curated source tree, disjoint from the installation.
        prefix: Required installation destination.
        metadata: Package version, maturity, OS, architecture, and provenance.
        protected_paths: Additional source/build inputs that must remain disjoint.

    Returns:
        Successfully verified and published complete inventory.

    Raises:
        InventoryError: Preflight or final verification rejects unsafe inputs.
        OSError: Publication or payload mutation fails; retry from retained ownership.
    """
    prefix = resolve_prefix(prefix, protected_paths=(payload, L1_ROOT / "compiler", *protected_paths))
    record = inventory_payload(payload, metadata)
    manifest = _safe_path(prefix, MANIFEST_PATH)
    prior = read_inventory(prefix, require_complete=False) if manifest.exists() or manifest.is_symlink() else None
    owned = {MANIFEST_PATH: {"path": MANIFEST_PATH, "kind": "manifest", "mode": 0o644}}
    if prior:
        for entry in [*prior.get("previous_entries", []), *prior["entries"]]:
            owned[entry["path"]] = entry
    intended = {entry["path"]: entry for entry in record["entries"]}
    # All parents and collisions are checked before metadata or payload mutation.
    for relative in sorted(owned.keys() | intended.keys()):
        destination = _safe_path(prefix, relative)
        if not destination.exists() and not destination.is_symlink():
            continue
        if relative not in owned:
            raise InventoryError(f"unowned payload collision: {destination}")
        mode = destination.lstat().st_mode
        if stat.S_ISLNK(mode):
            target = _alias_destination(relative, os.readlink(destination))
            if relative == MANIFEST_PATH or target not in owned:
                raise InventoryError(f"unsafe substituted payload alias: {destination}")
        elif not stat.S_ISREG(mode):
            raise InventoryError(f"owned payload path is not a file: {destination}")
        elif destination.stat().st_nlink != 1:
            raise InventoryError(f"owned payload file has substituted hard links: {destination}")
    incomplete = {**record, "state": "incomplete",
                  "previous_entries": sorted(owned.values(), key=lambda entry: entry["path"])}
    validate_inventory(incomplete)
    _publish_inventory(prefix, incomplete)
    for relative, entry in sorted(intended.items()):
        if entry["kind"] == "manifest":
            continue
        destination = _safe_path(prefix, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink() or entry["kind"] == "alias" and destination.exists():
            destination.unlink()
        if entry["kind"] == "alias":
            destination.symlink_to(entry["target"])
        else:
            shutil.copyfile(payload / relative, destination)
            destination.chmod(entry["mode"])
    for relative in sorted(owned.keys() - intended.keys()):
        path = _safe_path(prefix, relative)
        if path.exists() or path.is_symlink():
            path.unlink()
    verify_payload(prefix, record)
    _publish_inventory(prefix, record)
    return record
