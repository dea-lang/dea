# Feature Plan

## Add typed formatting

- Date: 2026-08-30
- Last reviewed: 2026-10-29
- Status: Draft
- Title: Add typed string formatting over L1 variadics
- Kind: Feature
- Priority: Medium
- Stdlib Tier: 2
- Subsystem: Stdlib / text / I/O / diagnostics
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/format.l1`
  - `l1/compiler/shared/l1/stdlib/std/types.l1`
  - `l1/compiler/shared/l1/stdlib/std/io.l1`
  - `l1/compiler/shared/l1/stdlib/std/text.l1`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l1/compiler/tests/format_test.l0`
  - `l1/compiler/tests/diag_print_test.l0`
  - `l1/compiler/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-22-variadic-functions-noref.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Repro: `make -C l1 test-compiler TESTS="format_test diag_print_test analysis_trace_test"`

## Summary

Replace continued growth of combinatorial helpers such as `print_ss`, `print_si`, and `print_ib` with typed formatting
built on the existing `std.types::Value` enum and L1-defined variadic arguments. The result is an ordinary ARC string
that callers pass to concrete output APIs. Later L2 writer integration reuses the adopted engine.

## Proposed Surface

- `format(template: string, args: Value...) -> FormatResult`

Use sequential `{}` placeholders, optional `{:d}`, `{:x}`, `{:X}`, `{:b}`, `{:s}`, and `{:g}` specifiers, and `{{` /
`}}` for literal braces. No width, precision, positional, or named fields in this tranche. Every placeholder consumes
one explicit `Value`; missing and extra values are errors. Integer decimal and radix forms use an explicit minus sign
and unsigned magnitude, including the minimum value. Booleans use `true` / `false`, absent optional values use `null`,
and strings preserve bytes. Real general formatting uses locale-independent round-trip precision, canonical `nan` /
`inf` / `-inf`, and preserves negative zero. Invalid templates, arity, and value/specifier combinations return
structured errors with the template byte offset and argument index.

## Defaults Chosen

1. Use L1 variadics, never C variadic formatting.
2. Keep arguments typed through `Value` rather than converting everything to strings at the call site.
3. Format into a string builder and return an ordinary ARC string. Concrete file and standard-stream writes remain
   separate operations.
4. Make malformed templates and unsupported value/specifier combinations structured errors.
5. Use locale-independent defaults.
6. Permit compiler diagnostics to consume the formatter without importing shell, process, or native `printf` rules.

## Implementation Phases

1. Finalize placeholder grammar and `Value` coverage.
2. Implement template parsing and string destination formatting.
3. Cover all existing primitive and optional `Value` variants; do not invent pointer or arbitrary-type variants.
4. Preserve compatibility print helpers and demonstrate concrete output of formatted strings.
5. Add malformed-template, boundary, deterministic-output, and trace tests through actual L1 programs.

## Non-Goals

- C `printf` compatibility or C varargs
- locale-sensitive output in v1
- compile-time format-string checking without a separate language feature
- generic writers or `write_format` (deferred to L2 streams)
- implicit heterogeneous argument conversion
- implicit arbitrary struct reflection
- logging, styling, terminal control, or internationalization frameworks

## ADR Impact

- Decision: Use typed `Value...` arguments, one locale-independent template grammar, and ordinary ARC string results
  instead of expanding combinatorial print helpers or adopting C variadics.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Formatting is a durable stdlib and diagnostics boundary whose type, error, and determinism rules should
    not inherit `printf`'s unsafe ABI or ambient locale behavior.

## Verification Criteria

1. Escapes, placeholders, and all supported primitive/optional variants produce the specified bytes.
2. Missing, extra, malformed, and unsupported arguments report structured errors.
3. Wide integers and real edge cases format deterministically on all supported hosts.
4. Actual L1 target programs exercise successful/error paths with balanced ARC traces.
5. Representative old print-helper call sites can migrate without changing output.
