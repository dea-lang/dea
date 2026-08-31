# Feature Plan

## Add typed formatting

- Date: 2026-08-30
- Status: Draft
- Title: Add typed string and writer formatting over L1 variadics
- Kind: Feature
- Severity: Medium
- Priority: 2
- Stage: L1
- Subsystem: Stdlib / text / I/O / diagnostics
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/format.l1`
  - `l1/compiler/shared/l1/stdlib/std/types.l1`
  - `l1/compiler/shared/l1/stdlib/std/io.l1`
  - `l1/compiler/shared/l1/stdlib/std/stream.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/format_test.l0`
  - `l1/compiler/stage1_l0/tests/diag_print_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-22-variadic-functions-noref.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Repro: `make -C l1 test-stage1 TESTS="format_test diag_print_test analysis_trace_test"`

## Summary

Replace continued growth of combinatorial helpers such as `print_ss`, `print_si`, and `print_ib` with typed formatting
built on the existing `std.types::Value` enum and L1-defined variadic arguments. The same engine formats into a string
or writes through `std.stream::Writer`.

## Proposed Surface

- `format(template: string, args: Value...) -> FormatResult`
- `write_format(writer: Writer*, template: string, args: Value...) -> WriteResult`

The plan must define placeholder grammar, escaping, missing/extra argument errors, supported `Value` variants, numeric
format options, and deterministic output independent of C locale.

## Defaults Chosen

1. Use L1 variadics, never C variadic formatting.
2. Keep arguments typed through `Value` rather than converting everything to strings at the call site.
3. Share one parser/formatter between string and writer destinations.
4. Make malformed templates and unsupported value/specifier combinations structured errors.
5. Use locale-independent defaults.
6. Permit compiler diagnostics to consume the formatter without importing shell, process, or native `printf` rules.

## Implementation Phases

1. Finalize placeholder grammar and `Value` coverage.
2. Implement template parsing and string destination formatting.
3. Add integer, wide-integer, boolean, byte, real, string, pointer, and nullable policies as supported by `Value`.
4. Add writer output with partial-write propagation.
5. Migrate representative `std.io` and diagnostic call sites without removing compatibility helpers prematurely.
6. Add malformed-template, boundary, deterministic-output, and trace tests.

## Non-Goals

- C `printf` compatibility or C varargs
- locale-sensitive output in v1
- compile-time format-string checking without a separate language feature
- implicit arbitrary struct reflection
- logging, styling, terminal control, or internationalization frameworks

## ADR Impact

- Decision: Use typed `Value...` arguments, one locale-independent template grammar, and shared string/writer formatting
  instead of expanding combinatorial print helpers or adopting C variadics.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Formatting is a durable stdlib and diagnostics boundary whose type, error, and determinism rules should
    not inherit `printf`'s unsafe ABI or ambient locale behavior.

## Verification Criteria

1. String and writer destinations produce identical bytes for the same template and values.
2. Missing, extra, malformed, and unsupported arguments report structured errors.
3. Wide integers and real edge cases format deterministically on all supported hosts.
4. Writer failures and short writes propagate without losing earlier progress semantics.
5. Representative old print-helper call sites can migrate without changing output.
