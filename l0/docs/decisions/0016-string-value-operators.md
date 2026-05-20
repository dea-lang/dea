# ADR-0016: String Value Operators

- Decision date: 2026-04-20
- Last edited: 2026-05-20
- Status: Accepted

## Context

The foundational ARC string value contract (see [ADR-0009](0009-string-value-semantics.md)) was established when ARC
strings were introduced. At that time, the operator surface was stdlib helpers only: `std.string::eq_s`, `cmp_s`, and
`concat_s`. L1 subsequently wired these operations as language-level type-checker operators. The question was whether to
backport the same operator surface to L0.

## Decision

The string comparison and concatenation operators `==`, `!=`, `<`, `<=`, `>`, `>=`, and `+` are wired as language-level
type-checker operators for `string`, not just stdlib helpers:

- `==` and `!=` compare byte content via `rt_string_equals`.
- `<`, `<=`, `>`, `>=` use byte-wise lexicographic order via `rt_string_compare`.
- `+` produces a fresh owned string via `rt_string_concat` without mutating or consuming either operand.

The stdlib helpers (`std.string::eq_s`, `cmp_s`, `concat_s`) remain as convenience wrappers but are not the canonical
path.

## Rationale

- Making these language operators (not just library functions) allows `case`-over-string and operator expressions to use
  the same semantic path.
- Backporting from L1 keeps the L0/L1 language surface consistent.

## Consequences

- The backend must never emit identity comparisons for string `==`/`!=`.
- Native call-sites in the Stage 2 compiler and stdlib were migrated from helper functions to native operators after
  these operators were introduced.

## Related Plans

- [l0/work/plans/features/closed/2026-04-20-string-equality-and-relational-operators-noref.md](../../work/plans/features/closed/2026-04-20-string-equality-and-relational-operators-noref.md):
  backport of string equality and relational operators
- [l0/work/plans/features/closed/2026-04-30-string-concatenation-operator-noref.md](../../work/plans/features/closed/2026-04-30-string-concatenation-operator-noref.md):
  backport of string concatenation operator
- [work/plans/refactors/closed/2026-04-20-prefer-native-string-operators-noref.md](../../../work/plans/refactors/closed/2026-04-20-prefer-native-string-operators-noref.md):
  migration from `eq_s`/`cmp_s` helpers to native operators
- [work/plans/refactors/closed/2026-04-30-prefer-native-string-concat-operator-noref.md](../../../work/plans/refactors/closed/2026-04-30-prefer-native-string-concat-operator-noref.md):
  migration from `concat_s` to native `+`

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §11 (string equality and ordering)
