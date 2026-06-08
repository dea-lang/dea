# Bug Fix Plan

## L1 Stage 1 `case` equality-based literal support

- Date: 2026-06-08
- Status: Draft
- Title: Make L1 Stage 1 `case` literals follow equality comparability rules
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Parser / Type checker / C backend
- Modules:
  - `compiler/stage1_l0/src/parser/stmt.l0`
  - `compiler/stage1_l0/src/expr_types.l0`
  - `compiler/stage1_l0/src/backend.l0`
  - `docs/reference/grammar.md`
  - `docs/roadmap.md`
- Test modules:
  - `compiler/stage1_l0/tests/parser_test.l0`
  - `compiler/stage1_l0/tests/expr_types_test.l0`
  - `compiler/stage1_l0/tests/backend_test.l0`
  - `compiler/stage1_l0/tests/l1c_stage1_toplet_test.py`
- Related:
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Repro: `case (a: long) { 1 => ... }` reports `TYP-0107` because the arm literal is inferred as `int`.

## Summary

L1 Stage 1 `case` currently treats arm literals as requiring an exact type match with the scrutinee, except for the
special contextual bigint path. That makes `case` inconsistent with ordinary equality:

- `case (a: long) { 1 => ... }` is rejected even though `a == 1` is valid.
- `float` and `double` scrutinees are rejected even though they support `==`.
- Wider or out-of-domain integer literals cannot be represented safely as arm values.

The fix should make `case` arm literals follow the same comparability model as `==`, while preserving compile-time
safety. Integer arm literals that can never match the scrutinee type, such as `-1` for an unsigned scrutinee or
`2000000000` for a `short` scrutinee, should be accepted with a warning and must never lower to C that can overflow,
cause undefined behavior, or route through runtime checked arithmetic.

## Current State

The parser already accepts integer, bigint, byte, string, and bool `case` arm literals. The type checker currently
allows only `int`, `byte`, `bool`, and `string` as `case` scrutinees and then requires exact arm-literal type equality
unless the literal has the internal bigint placeholder type.

The backend lowers `string` cases as `if` / `else if` chains through `rt_string_equals`, and lowers all other accepted
cases with C `switch`. That `switch` path is not suitable for floating-point cases, equality-style integer widening, or
always-false integer arms whose source literal cannot be safely emitted as a C case label for the scrutinee type.

## Scope of This Fix

1. Extend `case` arm parsing to accept real literals (`float` and `double`) in addition to the existing literal forms.
2. Allow `case` scrutinees with builtin integer types, `float`, `double`, `bool`, and `string`.
3. Replace exact arm-literal type matching with a helper that classifies each literal as:
   - `possible`: the arm can match under the same comparability rules as `==`
   - `always false`: the literal is a well-formed literal family for the scrutinee, but is outside the scrutinee value
     domain or otherwise trivially unable to compare equal
   - `error`: the literal family cannot be compared with the scrutinee type
4. For integer scrutinees:
   - accept ordinary `int` and bigint literals when the comparison can be classified safely
   - treat negative constants for unsigned scrutinees as warning-only always-false arms
   - treat integer constants outside the scrutinee domain, such as a 32-bit value for `short`, as warning-only
     always-false arms
   - use the existing common-integer equality rules as the source of truth for possible comparisons
5. For real scrutinees:
   - allow real arm literals that compare under the existing real `==` rules
   - reject literal families that cannot compare with the real scrutinee
   - do not add special NaN matching semantics
6. Keep `bool` and `string` cases on their current value-equality semantics.
7. Preserve cleanup and definite-return behavior, with always-false arms not contributing to definite-return analysis.
8. Update L1 reference grammar and the shared diagnostic catalog wording for the expanded `case` surface.

## Diagnostic Plan

Reuse existing error diagnostics where possible:

- `TYP-0106` remains the invalid `case` scrutinee diagnostic, with wording updated for the expanded builtin set.
- `TYP-0107` remains the invalid arm-literal comparability diagnostic, with wording updated away from exact type match.
- `TYP-0108` remains duplicate literal detection for reachable arm values.

Add one warning diagnostic for trivially unreachable value arms:

- Provisional code: `TYP-0111`
- Meaning: `case` arm literal can never match the scrutinee type
- Severity: warning

The implementation must re-check `docs/specs/compiler/diagnostic-code-catalog.md` before assigning `TYP-0111`; if that
code has been used by then, choose the next nearby unused `TYP-01xx` code and update the plan or implementation notes.

## Approach

### 1. Parse real arm literals

Extend `ps_parse_case_literal` in `compiler/stage1_l0/src/parser/stmt.l0` to mirror primary-expression real literal
parsing. Preserve current span behavior and existing diagnostics for invalid arm starts.

### 2. Add case-literal classification

In `compiler/stage1_l0/src/expr_types.l0`, add small helpers for:

- identifying supported builtin `case` scrutinee types
- extracting the exact integer literal text/base/sign for ordinary and bigint integer literals
- checking whether an integer literal value is inside the scrutinee type domain
- determining whether an integer literal can participate in an existing common-integer equality comparison
- classifying real, bool, and string literals against their scrutinee types

The classifier should report ordinary mismatches as errors and always-false integer arms as warnings. Always-false arms
remain syntactically valid and their bodies are still type-checked so local diagnostics inside the body are not hidden.

### 3. Preserve safe lowering

In `compiler/stage1_l0/src/backend.l0`, avoid emitting unsafe C for always-false arms. The backend may either omit those
arms from the generated dispatch chain or emit an explicit safe false condition such as `if (false)`.

Use `if` / `else if` lowering for cases that need equality-style conversion or cannot use C `switch`, including:

- string cases
- float and double cases
- integer cases with widened comparison operands
- cases containing any always-false arm

Keep C `switch` only when every arm is safe to emit as a C case label and the result is semantically identical to the
`==` rules.

### 4. Update docs

Update `docs/reference/grammar.md` so `CaseLiteral` includes real literals and bigint literals as accepted literal
forms. Update `docs/specs/compiler/diagnostic-code-catalog.md` for the changed `TYP-0106` / `TYP-0107` meanings and the
new warning code.

## Non-Goals

1. Adding named constants, const expressions, or arbitrary expressions as `case` arms.
2. Adding nullable, pointer, function, struct, enum, array, or `void` `case` scrutinees.
3. Adding special NaN matching behavior for floating-point cases.
4. Performing full semantic normalization for every differently spelled equal numeric literal beyond what is needed for
   correctness and duplicate detection in this fix.
5. Changing `match` semantics.

## Tests

Add parser coverage for:

1. `case` arms with unsuffixed `double` literals.
2. `case` arms with suffixed `float` literals.
3. Negative real literals in value arms.

Add type-checker coverage for:

1. `case (a: long) { 1 => ... }` accepted.
2. `case` over `tiny`, `byte`, `short`, `ushort`, `int`, `uint`, `long`, and `ulong` with ordinary integer literals.
3. Bigint literals that are possible for comparison.
4. Negative constants for unsigned scrutinees warning as always false.
5. Large constants outside narrow scrutinee domains warning as always false.
6. Invalid literal families, such as string literals for integer scrutinees, still erroring.
7. Always-false arms not making a `case` definitely returning unless another reachable arm/default returns.
8. Duplicate reachable literals still reporting `TYP-0108`.

Add backend and runtime coverage for:

1. Widened integer cases selecting the expected arm.
2. Always-false integer arms not executing.
3. Generated C for always-false arms avoiding overflowing switch labels, unsafe casts, and checked arithmetic calls.
4. Float and double cases selecting expected arms and using non-switch lowering.

## Verification Criteria

Run from `l1/`:

```bash
make test-stage1 TESTS="parser_test expr_types_test backend_test l1c_stage1_toplet_test"
```

The focused test run should pass with the new parser, typing, backend, and runtime cases. If the implementation touches
shared diagnostics or diagnostic-message parity helpers, also run the affected diagnostic parity test.

## Assumptions

- Existing `==` common integer and real comparability rules remain the source of truth.
- Always-false integer arm diagnostics are warnings, so programs continue compiling unless another error exists.
- Bigint case literals are compile-time-only values and must be classified before backend emission.
