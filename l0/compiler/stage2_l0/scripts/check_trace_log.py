#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

import argparse
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

TRACE_RE = re.compile(r"^\[l0\]\[(mem|arc)\]\s+(.*)$")
KV_RE = re.compile(r"(\w+)=([^\s]+)")


class _MessageCollector:
    """Count messages while retaining only a bounded leading sample."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.messages: list[str] = []
        self.total = 0

    def append(self, message: str) -> None:
        self.total += 1
        if len(self.messages) < self.limit:
            self.messages.append(message)


def _iter_events(
    lines: Iterable[str],
    max_details: int = 20,
) -> tuple[Iterable[dict[str, str]], _MessageCollector, dict[str, int]]:
    """Yield structured trace events from one raw line iterator.

    Args:
        lines: Raw trace log lines, typically captured from Stage 2 stderr.
        max_details: Maximum number of non-fatal parse-warning details to retain.

    Returns:
        A triple containing the parsed event iterator, non-fatal parse warnings,
        and summary event counts.

    See Also:
        `_validate_events`: Consumes the parsed events for semantic checks.
        `main`: Opens the input file and drives the full validation flow.
    """
    warnings = _MessageCollector(max_details)
    counts = {"mem_events": 0, "arc_events": 0, "total_events": 0}

    def event_iter() -> Iterable[dict[str, str]]:
        for line_no, raw in enumerate(lines, start=1):
            m = TRACE_RE.match(raw.lstrip())
            if not m:
                continue

            family = m.group(1)
            payload = m.group(2)
            fields = dict(KV_RE.findall(payload))
            event = {"family": family, "line_no": str(line_no), "raw": raw.rstrip("\n")}
            event.update(fields)

            counts["total_events"] += 1
            if family == "mem":
                counts["mem_events"] += 1
            else:
                counts["arc_events"] += 1

            if "op" not in fields:
                warnings.append(f"line {line_no}: trace line missing op=..., ignored for op-based checks")
            yield event

    return event_iter(), warnings, counts


def _validate_events(
    events: Iterable[dict[str, str]],
    max_details: int = 20,
) -> tuple[_MessageCollector, _MessageCollector, dict[str, int], dict]:
    """Validate trace event sequences for definite runtime misuse patterns.

    Args:
        events: Parsed trace events from `_parse_events`.
        max_details: Maximum number of validation error and warning details to retain.

    Returns:
        A tuple of ``(errors, warnings, op_counts, triage)`` summarizing the
        validation result and leak triage metadata.

    See Also:
        `_parse_events`: Produces the event stream consumed here.
        `_print_report`: Renders the returned validation summary.
    """
    errors = _MessageCollector(max_details)
    warnings = _MessageCollector(max_details)
    op_counts: Counter[str] = Counter()

    obj_balance: defaultdict[str, int] = defaultdict(int)
    str_balance: defaultdict[str, int] = defaultdict(int)
    obj_new_meta: dict[str, dict[str, str]] = {}
    obj_last_ptr_line: dict[str, str] = {}
    str_alloc_line: dict[str, str] = {}
    str_alloc_loc: dict[str, str] = {}
    str_last_ptr_line: dict[str, str] = {}

    def forget_object(ptr: str) -> None:
        obj_balance.pop(ptr, None)
        obj_new_meta.pop(ptr, None)
        obj_last_ptr_line.pop(ptr, None)

    def forget_string(ptr: str) -> None:
        str_balance.pop(ptr, None)
        str_alloc_line.pop(ptr, None)
        str_alloc_loc.pop(ptr, None)
        str_last_ptr_line.pop(ptr, None)

    for ev in events:
        family = ev["family"]
        line_no = ev["line_no"]
        op = ev.get("op")
        action = ev.get("action")
        ptr = ev.get("ptr")

        if op:
            op_counts[f"{family}:{op}"] += 1

        if family == "mem":
            if ptr:
                if obj_balance.get(ptr, 0) > 0:
                    obj_last_ptr_line[ptr] = line_no
                if str_balance.get(ptr, 0) > 0:
                    str_last_ptr_line[ptr] = line_no

            if op in {"new_alloc", "drop", "alloc_string", "free_string"} and not ptr:
                errors.append(f"line {line_no}: mem op={op} is missing ptr")
                continue

            if op == "new_alloc" and action == "ok":
                obj_balance[ptr] = obj_balance.get(ptr, 0) + 1  # type: ignore[arg-type]
                obj_new_meta[ptr] = {
                    "new_line": line_no,
                    "bytes": ev.get("bytes", "?"),
                    "loc": ev.get("loc", "?"),
                }
                obj_last_ptr_line[ptr] = line_no  # type: ignore[index]
            elif op == "drop" and action == "free":
                remaining = obj_balance.get(ptr, 0) - 1  # type: ignore[arg-type]
                if remaining < 0:
                    obj_balance[ptr] = remaining  # type: ignore[index]
                    errors.append(
                        f"line {line_no}: drop/free for ptr={ptr} without matching new_alloc in this log"
                    )
                elif remaining == 0:
                    forget_object(ptr)  # type: ignore[arg-type]
                else:
                    obj_balance[ptr] = remaining  # type: ignore[index]
            elif op == "free" and action == "call" and ptr:
                # Compatibility path: some object pointers may be finalized by direct free().
                # Treat it as a release for balance accounting, but surface it as a warning.
                if obj_balance.get(ptr, 0) > 0:
                    remaining = obj_balance[ptr] - 1
                    if remaining == 0:
                        forget_object(ptr)
                    else:
                        obj_balance[ptr] = remaining
                    warnings.append(
                        f"line {line_no}: new_alloc ptr={ptr} released via mem op=free action=call (preferred: drop/free)"
                    )
            elif op == "alloc_string":
                str_balance[ptr] = str_balance.get(ptr, 0) + 1  # type: ignore[arg-type]
                if ptr not in str_alloc_line:
                    str_alloc_line[ptr] = line_no
                    str_alloc_loc[ptr] = ev.get("loc", "?")
                str_last_ptr_line[ptr] = line_no  # type: ignore[index]
            elif op == "free_string" and action == "free":
                remaining = str_balance.get(ptr, 0) - 1  # type: ignore[arg-type]
                if remaining < 0:
                    str_balance[ptr] = remaining  # type: ignore[index]
                    errors.append(
                        f"line {line_no}: free_string/free for ptr={ptr} without matching alloc_string in this log"
                    )
                elif remaining == 0:
                    forget_string(ptr)  # type: ignore[arg-type]
                else:
                    str_balance[ptr] = remaining  # type: ignore[index]
            elif op == "free_string" and action == "decrement-only":
                pass
            elif op == "free_string" and action:
                warnings.append(f"line {line_no}: free_string has uncommon action={action}")

        if family == "arc":
            if action and action.startswith("panic"):
                errors.append(f"line {line_no}: arc panic action detected ({action})")

            is_heap_terminal_free = ev.get("kind") == "heap" and op == "release" and action == "free"
            if is_heap_terminal_free:
                if not ptr:
                    errors.append(f"line {line_no}: arc heap free release is missing ptr")
                    continue

                rc_before = ev.get("rc_before")
                rc_after = ev.get("rc_after")
                if rc_before is None or rc_after is None:
                    errors.append(f"line {line_no}: arc heap free release missing rc_before/rc_after")
                    continue

                try:
                    int(rc_before)
                    rc_after_i = int(rc_after)
                except ValueError:
                    errors.append(
                        f"line {line_no}: arc heap free release has non-integer rc values rc_before={rc_before} rc_after={rc_after}"
                    )
                    continue

                if rc_after_i != 0:
                    errors.append(
                        f"line {line_no}: arc heap free release must end at rc_after=0, got rc_after={rc_after_i}"
                    )

    leaked_objects: list[dict[str, str]] = []
    leaked_strings: list[dict[str, str]] = []
    leaked_object_bytes: Counter[str] = Counter()

    for ptr, bal in obj_balance.items():
        if bal != 0:
            errors.append(f"object leak balance for ptr={ptr}: remaining={bal} (new_alloc vs drop/free mismatch)")
            if bal > 0:
                meta = obj_new_meta.get(ptr, {})
                obj_bytes = meta.get("bytes", "?")
                leaked_object_bytes[obj_bytes] += 1
                leaked_objects.append(
                    {
                        "ptr": ptr,
                        "remaining": str(bal),
                        "new_line": meta.get("new_line", "?"),
                        "bytes": obj_bytes,
                        "loc": meta.get("loc", "?"),
                        "last_ptr_line": obj_last_ptr_line.get(ptr, "?"),
                    }
                )
    for ptr, bal in str_balance.items():
        if bal != 0:
            errors.append(
                f"string leak balance for ptr={ptr}: remaining={bal} (alloc_string vs free_string/free mismatch)"
            )
            if bal > 0:
                leaked_strings.append(
                    {
                        "ptr": ptr,
                        "remaining": str(bal),
                        "alloc_line": str_alloc_line.get(ptr, "?"),
                        "loc": str_alloc_loc.get(ptr, "?"),
                        "last_ptr_line": str_last_ptr_line.get(ptr, "?"),
                    }
                )

    triage = {
        "leaked_objects": sorted(
            leaked_objects,
            key=lambda item: int(item["new_line"]) if item["new_line"].isdigit() else 10**9,
        ),
        "leaked_strings": sorted(
            leaked_strings,
            key=lambda item: int(item["alloc_line"]) if item["alloc_line"].isdigit() else 10**9,
        ),
        "leaked_object_bytes": dict(leaked_object_bytes),
    }

    return errors, warnings, dict(op_counts), triage


def _print_report(
    counts: dict[str, int],
    parse_warnings: _MessageCollector,
    errors: _MessageCollector,
    warnings: _MessageCollector,
    op_counts: dict[str, int],
    triage: dict,
    max_details: int,
    show_triage: bool,
) -> None:
    """Print a validation summary and optional leak triage details.

    Args:
        counts: Parsed trace event counts by family and in total.
        parse_warnings: Non-fatal warnings produced during parsing.
        errors: Validation errors to report.
        warnings: Validation warnings to report.
        op_counts: Per-family operation counts.
        triage: Leak triage metadata from `_validate_events`.
        max_details: Maximum number of detail lines to print per section.
        show_triage: Whether to print the triage section.

    See Also:
        `_validate_events`: Produces the summary and triage data rendered here.
    """
    total_warning_count = parse_warnings.total + warnings.total
    warning_samples = (parse_warnings.messages + warnings.messages)[:max_details]

    print("stats:")
    print(f"  mem_events={counts['mem_events']}")
    print(f"  arc_events={counts['arc_events']}")
    print(f"  total_events={counts['total_events']}")
    print(f"  errors={errors.total}")
    print(f"  warnings={total_warning_count}")

    if op_counts:
        print("op_counts:")
        op_keys = sorted(op_counts.keys())
        for key in op_keys[:max_details]:
            print(f"  {key}={op_counts[key]}")
        if len(op_keys) > max_details:
            print(f"  ... {len(op_keys) - max_details} more operation kinds")

    if errors.total:
        print("errors:")
        for msg in errors.messages:
            print(f"ERROR: {msg}")
        if errors.total > len(errors.messages):
            print(f"ERROR: ... {errors.total - len(errors.messages)} more")

    if total_warning_count:
        print("warnings:")
        for msg in warning_samples:
            print(f"WARN: {msg}")
        if total_warning_count > len(warning_samples):
            print(f"WARN: ... {total_warning_count - len(warning_samples)} more")

    if show_triage:
        leaked_objects = triage.get("leaked_objects", [])
        leaked_strings = triage.get("leaked_strings", [])
        leaked_object_bytes = triage.get("leaked_object_bytes", {})

        print("triage:")
        print(f"  leaked_object_ptrs={len(leaked_objects)}")
        print(f"  leaked_string_ptrs={len(leaked_strings)}")

        if leaked_object_bytes:
            print("  leaked_object_bytes:")
            byte_counts = sorted(
                leaked_object_bytes.items(),
                key=lambda item: (-item[1], item[0]),
            )
            for b, count in byte_counts[:max_details]:
                print(f"    bytes={b} count={count}")
            if len(byte_counts) > max_details:
                print(f"    ... {len(byte_counts) - max_details} more byte sizes")

        if leaked_objects:
            print("  leaked_object_examples:")
            for item in leaked_objects[:max_details]:
                print(
                    "    "
                    f"ptr={item['ptr']} remaining={item['remaining']} bytes={item['bytes']} "
                    f"new_line={item['new_line']} loc={item['loc']} last_ptr_line={item['last_ptr_line']}"
                )
            if len(leaked_objects) > max_details:
                print(f"    ... {len(leaked_objects) - max_details} more")

        if leaked_strings:
            print("  leaked_string_examples:")
            for item in leaked_strings[:max_details]:
                print(
                    "    "
                    f"ptr={item['ptr']} remaining={item['remaining']} "
                    f"alloc_line={item['alloc_line']} loc={item['loc']} last_ptr_line={item['last_ptr_line']}"
                )
            if len(leaked_strings) > max_details:
                print(f"    ... {len(leaked_strings) - max_details} more")


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the trace log checker.

    Returns:
        Configured argument parser for the `check_trace_log.py` CLI.

    See Also:
        `main`: Uses this parser to handle CLI arguments.
    """
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Analyze Stage 2 trace stderr logs for definite runtime issues.",
    )
    parser.add_argument("trace_file", help="Path to trace stderr log file")
    parser.add_argument(
        "--max-details",
        type=int,
        default=20,
        help="Maximum number of error/warning/triage detail lines to print (default: 20)",
    )
    parser.add_argument(
        "--triage",
        action="store_true",
        help="Print leak triage details (leak counts by size and pointer examples)",
    )
    return parser


def main(argv: list[str]) -> int:
    """Run the trace log checker command-line entry point.

    Args:
        argv: Process argument vector, including program name at index 0.

    Returns:
        Exit status ``0`` on success, ``1`` when validation finds errors, or
        ``2`` for invalid usage or file-read failures.

    See Also:
        `_build_arg_parser`: Defines the accepted CLI arguments.
        `_iter_events`: Parses the raw trace file contents.
        `_validate_events`: Checks the parsed events for runtime issues.
        `_print_report`: Prints the final human-readable report.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv[1:])

    if args.max_details < 1:
        print("error: --max-details must be >= 1")
        return 2

    trace_path = Path(args.trace_file)
    if not trace_path.exists() or not trace_path.is_file():
        print(f"error: trace file not found: {trace_path}")
        return 2

    try:
        with trace_path.open(encoding="utf-8", errors="replace") as trace_file:
            events, parse_warnings, counts = _iter_events(trace_file, args.max_details)
            errors, warnings, op_counts, triage = _validate_events(events, args.max_details)
    except OSError as exc:
        print(f"error: failed to read trace file {trace_path}: {exc}")
        return 2

    _print_report(
        counts,
        parse_warnings,
        errors,
        warnings,
        op_counts,
        triage,
        max_details=args.max_details,
        show_triage=args.triage,
    )
    return 1 if errors.total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
