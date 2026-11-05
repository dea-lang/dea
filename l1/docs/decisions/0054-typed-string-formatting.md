# ADR-0054: Typed String Formatting

- Decision date: 2026-11-05
- Last edited: 2026-11-09
- Status: Accepted

## Context

L1 tools need structured text containing heterogeneous primitive values. Extending the pair-print helpers for every
numeric width grows a combinatorial API, while C variadic formatting would couple safety and output to an untyped ABI
and ambient locale. L1 already supplies `std.types::Value`, typed variadic arguments, and ARC strings.

## Decision

`std.format::format(template: string, args: Value...) -> FormatResult` accepts explicit `Value` arguments and returns
`FormatOk(string)` or `FormatErr(FormatError)`. Formatting is separate from concrete output and does not change the
existing `std.io` print helpers. Generic writer integration remains L2 work.

The grammar supports sequential `{}` fields, `{:d}`, `{:x}`, `{:X}`, `{:b}`, `{:s}`, `{:g}`, and doubled brace escapes.
Every field consumes one argument; missing and extra arguments fail. Named or positional fields, width, precision,
implicit heterogeneous conversion, reflection, and C format syntax are outside this contract.

Defaults cover every existing primitive and optional `Value` variant. Integer specifiers accept only integers, `{:s}`
accepts strings, and `{:g}` accepts reals. An optional follows the same type rule even when absent; a compatible absent
optional emits `null`. Booleans use the default field and emit `true` or `false`. Strings preserve every byte. Signed
radix output uses a minus sign and magnitude, including signed minima, without a radix prefix.

Real conversion uses exact binary-to-decimal expansion followed by nearest rounding with ties to even at 9 significant
digits for `float` and 17 for `double`. The rounded exponent selects fixed notation in `[-4, precision)` and scientific
notation otherwise. Scientific exponents use lowercase `e`, an explicit sign, and at least two digits. Unnecessary
fractional zeros and decimal points are removed. Special spellings are `nan`, `inf`, `-inf`, `0`, and `-0`. This is a
round-trip-precision contract, not shortest-decimal formatting, and does not use ambient locale or rounding mode.

`FormatError` carries `kind`, `offset`, and `argument_index`. Kinds distinguish invalid template syntax, missing
arguments, extra arguments, and incompatible valid specifiers. Coordinates are zero-based bytes and argument indices.
The offset identifies the opening brace of a field, an unmatched closing brace, or template length for unused arguments.
Parsing proceeds left to right, validating a field's syntax before argument availability and type. Errors contain no
partial output string and allocate no compiler diagnostic codes.

## Rationale

Explicit variants preserve the type information needed for a safe formatting policy and reuse ordinary L1 variadic
calling conventions. A bounded grammar has predictable parsing and failure behavior. Ordinary ARC string results fit
existing diagnostics and output APIs without introducing writer ownership. Exact real conversion makes golden output
independent of host formatting libraries, locale, and floating-point rounding state.

## Consequences

Call sites wrap values explicitly and handle the result before output. Existing print helpers preserve compatibility;
the formatter introduces neither implicit writes nor flush policy. Real conversion performs more work than a
host-specific shortest-decimal routine, but it has bounded storage and deterministic semantics for supported binary32
and binary64 values. Allocation failure retains the existing fatal stdlib allocation policy. Arbitrary pointers and
application-defined values require an explicit application representation before formatting.

## Related Plans

- [l1/work/plans/features/closed/2026-08-30-typed-formatting-noref.md][format-plan]

## Current Docs

- [l1/docs/reference/standard-library.md][stdlib]
- [l1/docs/reference/design-decisions.md][design]
- [l1/docs/project-status.md][status]

[design]: ../reference/design-decisions.md
[format-plan]: ../../work/plans/features/closed/2026-08-30-typed-formatting-noref.md
[status]: ../project-status.md
[stdlib]: ../reference/standard-library.md
