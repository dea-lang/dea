#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Adapt L1 P1689R5 core facts to caller-owned GNU Make 4.3+ actions.

The caller holds ``artifact_lock`` across a successful fresh scan, adaptation,
and the inner Make invocation. This module never executes build commands.
``DEA_COMPILE`` receives shell-quoted source, primary-output, and canonical
module-name arguments; the caller uses ``$(1)``, ``$(2)``, and ``$(3)`` directly
in its recipe. ``DEA_OBJECTS`` contains Make prerequisite tokens while
``DEA_OBJECT_ARGS`` contains shell-quoted object arguments for linking. Native compile
inputs and configuration stamps belong in ``DEA_COMPILE_DEPS`` and
``DEA_CONFIG_STAMP``. Final linking depends on ``DEA_LINK_DEPS`` in addition
to the caller's native libraries, foreign inputs, and prebuilt objects.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
from typing import Iterator


class AdapterError(ValueError):
    """A report cannot be represented by the supported Make adapter contract."""


@dataclass(frozen=True)
class Action:
    """One source-backed two-output compilation action."""

    name: str
    source: Path
    primary: Path
    interface: Path
    requirements: tuple[tuple[str, Path], ...]


def make_path(value: str, *, windows: bool | None = None) -> str:
    """Encode one native path as a Make target, prerequisite, or list element.

    Args:
        value: Native path spelling, without Make or shell quoting.
        windows: Explicit Windows semantics for portable spelling tests.

    Returns:
        A Make token preserving spaces, Unicode, quotes, and number signs.

    Raises:
        AdapterError: The spelling is outside the lossless adapter subset.
    """
    if windows is None:
        windows = os.name == "nt"
    if not isinstance(value, str) or not value:
        raise AdapterError("expected a nonempty path")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise AdapterError("paths must be valid UTF-8") from error
    if windows:
        value = value.replace("\\", "/")
    forbidden = "\x00\n\r\t$%*?[],()|;\\"
    if any(character in value for character in forbidden) or any(ord(character) < 32 for character in value):
        raise AdapterError(f"unsupported Make path spelling: {value!r}")
    # A colon is meaningful only as a native Windows drive prefix. On POSIX it
    # would introduce a rule separator; rejecting it also catches cross-host data.
    colon_tail = value[2:] if windows and re.match(r"^[A-Za-z]:/", value) else value
    if ":" in colon_tail:
        raise AdapterError(f"unsupported Make path spelling: {value!r}")
    return value.replace(" ", "\\ ").replace("#", "\\#").replace(":", "\\:")


def _path(value: object, directory: Path, field: str) -> Path:
    """Resolve a report path against its rule's working-directory context.

    Args:
        value: Untrusted JSON field value.
        directory: Absolute directory for relative paths.
        field: Field name for diagnostics.

    Returns:
        An absolute native path preserving the selected spelling.

    Raises:
        AdapterError: The field is missing, invalid, or not representable.
    """
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{field} must be a nonempty string")
    make_path(value)
    path = Path(value)
    if not path.is_absolute():
        path = directory / path
    try:
        resolved = path.absolute()
        resolved.resolve()
    except (OSError, RuntimeError) as error:
        raise AdapterError(f"cannot resolve {field}: {value!r}: {error}") from error
    make_path(str(resolved))
    return resolved


def _same_path(left: Path, right: Path) -> bool:
    """Compare selected filesystem identities, including existing hard links.

    Args:
        left: First resolved path.
        right: Second resolved path.

    Returns:
        Whether the paths select the same file or unresolved destination.
    """
    if left == right or left.resolve() == right.resolve():
        return True
    try:
        return left.samefile(right)
    except OSError:
        return False


def _module(value: object) -> str:
    """Validate the canonical dotted name used for a Dea artifact mapping.

    Args:
        value: Untrusted module name.

    Returns:
        The validated name.

    Raises:
        AdapterError: The name is not canonical.
    """
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*", value):
        raise AdapterError(f"invalid canonical logical-name: {value!r}")
    return value


def _description(value: object, *, required: bool) -> dict:
    """Validate the supported logical-name module-description subset.

    Args:
        value: Untrusted module description.
        required: Whether the description is a requirement.

    Returns:
        The validated object.

    Raises:
        AdapterError: The description uses unsupported module identity semantics.
    """
    if not isinstance(value, dict):
        raise AdapterError("module descriptions must be objects")
    if value.get("unique-on-source-path", False) is not False:
        raise AdapterError("unique-on-source-path modules are unsupported")
    if required and value.get("lookup-method", "by-name") != "by-name":
        raise AdapterError("only by-name requirements are supported")
    if not required and value.get("is-interface", True) is not True:
        raise AdapterError("a source action must provide its interface")
    return value


def _actions(report: object, artifact_root: Path, fragment: Path) -> list[Action]:
    """Validate the core projection and preflight all selected provider paths.

    Args:
        report: Decoded P1689R5 document.
        artifact_root: Canonical generated-artifact root supplied by the caller.
        fragment: Destination reserved for the generated Make fragment.

    Returns:
        Validated actions in the report's deterministic order.

    Raises:
        AdapterError: The report, mapping, or generated-root contents conflict.
    """
    if not isinstance(report, dict):
        raise AdapterError("report must be a JSON object")
    if type(report.get("version")) is not int or report["version"] != 1:
        raise AdapterError("only P1689 version 1 is supported")
    if type(report.get("revision", 0)) is not int or report.get("revision", 0) != 0:
        raise AdapterError("only P1689 revision 0 is supported")
    rules = report.get("rules")
    if not isinstance(rules, list) or not rules:
        raise AdapterError("rules must be a nonempty array")
    actions: list[Action] = []
    producers: dict[str, Action] = {}
    outputs: list[Path] = []
    inputs: list[Path] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise AdapterError("rules must contain objects")
        directory = _path(rule.get("work-directory", str(Path.cwd())), Path.cwd(), "work-directory")
        if not directory.is_dir():
            raise AdapterError(f"work-directory does not exist: {directory}")
        provides = rule.get("provides", [])
        if not isinstance(provides, list) or len(provides) != 1:
            raise AdapterError("each Dea source action must provide exactly one module")
        provider = _description(provides[0], required=False)
        name = _module(provider.get("logical-name"))
        if name in producers:
            raise AdapterError(f"duplicate source producer for {name}")
        source = _path(provider.get("source-path"), directory, "source-path")
        if not source.is_file():
            raise AdapterError(f"selected source is not an existing regular file: {source}")
        primary = _path(rule.get("primary-output"), directory, "primary-output")
        interface = _path(provider.get("compiled-module-path"), directory, "compiled-module-path")
        additional = rule.get("outputs")
        if not isinstance(additional, list) or len(additional) != 1:
            raise AdapterError(f"source action {name} must declare exactly one additional interface output")
        declared_interface = _path(additional[0], directory, "outputs")
        expected_stem = artifact_root.joinpath(*name.split("."))
        expected_primary = expected_stem.with_suffix(".o").resolve()
        expected_interface = expected_stem.with_suffix(".l1m").resolve()
        if (not _same_path(primary, expected_primary) or not _same_path(interface, expected_interface)
                or not _same_path(interface, declared_interface)):
            raise AdapterError(f"conflicting artifact-root output mapping for {name}")
        for output in (primary, interface):
            if any(_same_path(output, existing) for existing in outputs):
                raise AdapterError(f"conflicting output ownership: {output}")
            outputs.append(output)
        requirements = rule.get("requires", [])
        if not isinstance(requirements, list):
            raise AdapterError("requires must be an array")
        required_paths: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for raw in requirements:
            requirement = _description(raw, required=True)
            required_name = _module(requirement.get("logical-name"))
            if required_name in seen:
                raise AdapterError(f"duplicate requirement {required_name} in {name}")
            seen.add(required_name)
            required_path = _path(requirement.get("compiled-module-path"), directory, "compiled-module-path")
            required_paths.append((required_name, required_path))
        action = Action(name, source, primary, interface, tuple(required_paths))
        producers[name] = action
        actions.append(action)
        inputs.append(source)
    selected: dict[str, Path] = {}
    for action in actions:
        for name, path in action.requirements:
            if name in selected and not _same_path(path, selected[name]):
                raise AdapterError(f"conflicting selected provider paths for {name}")
            selected[name] = path
            if name in producers:
                if not _same_path(path, producers[name].interface):
                    raise AdapterError(f"requirement does not match source producer mapping for {name}")
            else:
                if not path.is_file():
                    raise AdapterError(f"selected prebuilt interface is not an existing regular file: {path}")
                candidate = artifact_root.joinpath(*name.split(".")).with_suffix(".l1m")
                # lexists includes dangling links and non-regular paths; do not
                # follow aliases before checking the canonical generated candidate.
                if os.path.lexists(candidate):
                    raise AdapterError(
                        f"generated interface candidate conflicts with selected prebuilt {name}: {candidate}; "
                        "use a clean or fresh artifact root"
                    )
                inputs.append(path)
    selected_items = list(selected.items())
    for index, (name, path) in enumerate(selected_items):
        if any(_same_path(path, other) for _, other in selected_items[:index]):
            raise AdapterError(f"selected interface has conflicting logical-name ownership: {name}")
    for output in outputs:
        if any(_same_path(output, selected_input) for selected_input in inputs):
            raise AdapterError(f"generated output aliases a selected input: {output}")
    if any(_same_path(fragment, path) for path in inputs + outputs):
        raise AdapterError(f"Make fragment aliases a selected input or generated output: {fragment}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        """Reject source-action cycles before Make accepts a scheduling graph.

        Args:
            name: Source producer to visit.

        Raises:
            AdapterError: A dependency cycle is reachable.
        """
        if name in visiting:
            raise AdapterError(f"source-action dependency cycle involving {name}")
        if name in visited:
            return
        visiting.add(name)
        for required_name, _ in producers[name].requirements:
            if required_name in producers:
                visit(required_name)
        visiting.remove(name)
        visited.add(name)

    for action in actions:
        visit(action.name)
    return actions


def _shell_path(path: Path) -> str:
    """Quote a native path for a POSIX-compatible Make recipe shell.

    Args:
        path: Validated native path.

    Returns:
        One shell argument using forward separators on Windows.
    """
    return shlex.quote(str(path).replace(os.sep, "/"))


def render_fragment(report: object, artifact_root: str | Path, fragment_path: str | Path) -> str:
    """Render explicit grouped Make rules using only P1689R5 core fields.

    Args:
        report: Decoded JSON report from a successful fresh compiler scan.
        artifact_root: The same generated-output root supplied to the scanner.
        fragment_path: Exact destination whose timestamp invalidates the graph.

    Returns:
        Deterministic UTF-8 Make text.

    Raises:
        AdapterError: Validation or the generated-root preflight fails.
    """
    root = _path(str(artifact_root), Path.cwd(), "artifact-root")
    fragment = _path(str(fragment_path), Path.cwd(), "fragment path")
    actions = _actions(report, root, fragment)
    objects = " ".join(make_path(str(action.primary)) for action in actions)
    object_args = " ".join(_shell_path(action.primary) for action in actions).replace("#", "\\#")
    interfaces = " ".join(make_path(str(action.interface)) for action in actions)
    lines = [
        "# Generated from P1689R5 core fields; requires GNU Make 4.3 or newer.",
        "ifeq ($(filter grouped-target,$(.FEATURES)),)",
        "$(error Dependency fragments require GNU Make 4.3 or newer)",
        "endif",
        f"DEA_OBJECTS := {objects}",
        f"DEA_OBJECT_ARGS := {object_args}",
        f"DEA_INTERFACES := {interfaces}",
        f"DEA_LINK_DEPS := $(DEA_OBJECTS) {make_path(str(fragment))} $(DEA_CONFIG_STAMP)",
        "",
    ]
    for index, action in enumerate(actions):
        primary = make_path(str(action.primary))
        interface = make_path(str(action.interface))
        force = f"_dea_p1689_missing_pair_{index}"
        # Function arguments use literal '#' and ':'; only whitespace needs
        # quoting inside wildcard. Rule/list tokens require different escaping.
        primary_glob = str(action.primary).replace(os.sep, "/").replace(" ", "\\ ")
        interface_glob = str(action.interface).replace(os.sep, "/").replace(" ", "\\ ")
        lines += [
            f"ifeq ($(and $(wildcard {primary_glob}),$(wildcard {interface_glob})),)",
            f".PHONY: {force}",
            f"{primary} {interface}: {force}",
            "endif",
        ]
        prerequisites = [action.source, *(path for _, path in action.requirements), fragment]
        encoded = " ".join(make_path(str(path)) for path in prerequisites)
        lines += [
            f"{primary} {interface} &: {encoded} $(DEA_COMPILE_DEPS) $(DEA_CONFIG_STAMP)",
            f"\t$(call DEA_COMPILE,{_shell_path(action.source)},{_shell_path(action.primary)},{shlex.quote(action.name)})",
            "",
        ]
    return "\n".join(lines)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON keys instead of silently changing their meaning.

    Args:
        pairs: JSON parser object members in input order.

    Returns:
        An unambiguous JSON object.

    Raises:
        AdapterError: An object repeats a key.
    """
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise AdapterError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    """Reject non-JSON numeric constants accepted by Python's permissive decoder.

    Args:
        value: Nonstandard constant spelling encountered anywhere in the report.

    Raises:
        AdapterError: The document contains a non-JSON numeric constant.
    """
    raise AdapterError(f"invalid JSON numeric constant: {value}")


def write_fragment(report_path: str | Path, artifact_root: str | Path, fragment_path: str | Path) -> bool:
    """Validate and atomically publish a fragment, preserving unchanged bytes.

    Args:
        report_path: Report from the immediately preceding successful scan.
        artifact_root: Caller-selected generated-output root.
        fragment_path: Exact destination of the generated Make fragment.

    Returns:
        Whether changed fragment bytes were published.

    Raises:
        AdapterError: The report is invalid or its paths conflict.
        OSError: Reading, staging, or publishing the fragment fails.
    """
    source = _path(str(report_path), Path.cwd(), "report path")
    destination = _path(str(fragment_path), Path.cwd(), "fragment path")
    if _same_path(source, destination):
        raise AdapterError("Make fragment must not overwrite its dependency report")
    try:
        report = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=_reject_constant)
    except (ValueError, UnicodeError) as error:
        raise AdapterError(f"invalid dependency report: {error}") from error
    rendered = render_fragment(report, artifact_root, fragment_path).encode("utf-8")
    if destination.is_file() and destination.read_bytes() == rendered:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent, prefix=".p1689-make-", delete=False) as output:
            temporary = output.name
            output.write(rendered)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return True


@contextmanager
def artifact_lock(artifact_root: str | Path) -> Iterator[None]:
    """Serialize one outer scan/adapt/build transaction for a generated root.

    Args:
        artifact_root: Generated directory, including any trusted directory alias.

    Yields:
        Control while the root's persistent advisory lock is held.

    Raises:
        OSError: The directory or lock cannot be created or acquired.
    """
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve(strict=True)
    lock_path = root.parent / ("." + root.name + ".p1689.lock")
    with lock_path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            import time
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
            while True:
                lock.seek(0)
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (13, 36):
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    """Run the optional report-to-Make adapter command.

    Args:
        argv: Command arguments, or the process arguments when omitted.

    Returns:
        Zero after accepted publication, or one after a report/publication failure.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="fresh successful P1689R5 report")
    parser.add_argument("--artifact-root", type=Path, required=True, help="scanner's generated-output root")
    parser.add_argument("-o", "--output", type=Path, required=True, help="exact Make fragment destination")
    options = parser.parse_args(argv)
    try:
        write_fragment(options.report, options.artifact_root, options.output)
    except (AdapterError, OSError) as error:
        print(f"p1689_make: {error}; do not consume a previous fragment after this failure", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
