# Bug Fix Plan

## Release owned payloads when dropping an allocated optional

- Date: 2026-11-26
- Status: Completed
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
  - [l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md][l0-ownership]
- Repro: With `std.string` imported and `type S = string?;`, run `let p = new S(concat_s("a", "b") as string?); drop p;`
  under `--trace-arc --trace-memory`.

## Findings and implementation

Before the fix the reproducer exited successfully with one leaked string and zero leaked objects. The drop emitter
handled structs, enums, arrays and bare strings. For a `string?` pointee it emitted only the allocation validation and
final free.

After the struct and enum cases, the emitter now checks whether the resolved pointee contains ARC data. For a live slot
with such data, it applies the existing value cleanup to the validated pointee before drop-finish. For `string?`, that
cleanup tests `has_value` before releasing the payload. An optional pointer carries no owned reference to its pointee.

## ADR Impact

- Decision: Apply the existing value-ownership rules to the payload of an allocated optional during drop.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Nullable value cleanup and the validated drop-begin/finish protocol already exist. This repair connects
    the optional pointee to that cleanup.

## Verification

The project maintainer confirmed on 2026-11-26 that Unified CI passed for the optional payload cleanup fix.

Both focused compiler test modules and the dedicated backend trace passed on macOS x86_64 with Apple Clang 17. Run the
checks from `l1/`.

```sh
KEEP_ARTIFACTS=1 make test-compiler TESTS="backend_test l1c_arc_trace_regression_test"
make test-compiler-trace TESTS=backend_test
python3 compiler/scripts/check_trace_log.py <child-stderr-log> --triage
```

- The code-generation regression checks that drop-begin precedes the presence test and that the payload release precedes
  drop-finish.
- The present-slot trace recorded one heap string allocation, its matching terminal release and free, and one slot drop.
  The trace checker reported zero leaked strings and objects.
- The control program dropped an allocated absent slot and a null pointer, then dropped a slot containing a borrowed
  pointer and read the pointee before freeing it explicitly. Its trace recorded three object frees, one null drop, zero
  ARC events and zero leaks. The existing struct-field and stale-drop trace cases cover the struct cleanup path.

[l0-ownership]: ../../../../../l0/work/plans/bug-fixes/closed/2026-11-21-stage1-nullable-conversions-and-ownership-noref.md
[ownership]: ../../../../docs/reference/ownership.md
