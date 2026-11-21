# Bug Fix Plan

## Release owned payloads when dropping an allocated optional

- Date: 2026-11-21
- Status: Draft
- Title: Release owned payloads when dropping an allocated optional
- Kind: Bug Fix
- Severity: High
- Subsystem: Generated drop sequence and ARC value cleanup
- Modules:
  - `l1/compiler/src/backend/lifetime.l0`
- Test modules:
  - `l1/compiler/tests/backend_test.l0`
  - `l1/compiler/tests/l1c_arc_trace_regression_test.py`
- Related:
  - [l1/docs/reference/ownership.md][ownership]
  - [l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-ownership]
- Repro: With `std.string` imported and `type S = string?;`, run `let p = new S(concat_s("a", "b") as string?); drop p;`
  under `--trace-arc --trace-memory`.

## Summary

The program exits successfully, but the trace checker reports one leaked string and zero leaked objects. The generated
code validates and frees the object without releasing the string held in its present payload. Each such drop loses a
heap reference. The existing nullable value cleanup already knows how to check presence and release owned data.

## ADR Impact

- Decision: Apply the existing value-ownership rules to the payload of an allocated optional during drop.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Nullable value cleanup and the validated drop-begin/finish protocol already exist. This repair connects
    the optional pointee to that cleanup.

## Fix and regression criteria

1. After drop-begin validates the allocation, apply type-directed value cleanup to a live optional pointee before
   drop-finish. Use the existing cleanup rules for wrapped values and pointer niches. Preserve null-pointer drop,
   stale-pointer validation order, and the distinction between an owned string and a borrowed pointer.
2. Extend the drop code-generation test and the traced child program. Require a real string allocation and a matching
   final release/free, exactly one object drop, and zero leaked strings and objects. A zero exit code alone missed the
   original failure.
3. Contrast a present slot with an allocated absent slot initialized from `let empty: S = null;` and a null pointer to
   an optional. Neither absent case should release a payload. Keep a struct containing an owned string as a positive
   cleanup control. The typed-local fixture allows this fix to be tested independently of `new S(null)`.

From `l1/`, run `make test-compiler TESTS="backend_test l1c_arc_trace_regression_test"`. Validate the retained child
trace with `python3 compiler/scripts/check_trace_log.py <trace-log> --triage`. Update the L1 ownership reference with
the present and absent allocated-slot examples.

[l0-ownership]: ../../../../l0/work/plans/bug-fixes/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[ownership]: ../../../docs/reference/ownership.md
