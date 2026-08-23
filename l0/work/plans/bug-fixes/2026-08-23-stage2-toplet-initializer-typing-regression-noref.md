# Bug Fix Plan

## Type-check Stage 2 top-level let initializers

- Date: 2026-08-23
- Status: Draft
- Title: Type-check L0 Stage 2 top-level `let` initializers before backend lowering
- Kind: Bug Fix
- Severity: High
- Stage: 2
- Subsystem: Type checker / Top-level initialization / Backend metadata
- Modules:
  - `l0/compiler/stage2_l0/src/signatures.l0`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l0/compiler/stage2_l0/src/analysis.l0`
  - `l0/compiler/stage2_l0/src/backend.l0`
- Test modules:
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/backend_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_toplet_test.py`
- Related:
  - `l1/work/plans/bug-fixes/closed/2026-06-18-stage1-toplet-initializer-typing-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-06-19-stage1-toplet-diagnostic-recovery-noref.md`
  - `l0/work/plans/features/closed/2026-03-01-stage2-expression-type-checking-milestone.md`
- Repro: `./l0/build/dea/bin/l0c-stage2 --check` accepts a module containing `let bad: int = "text";` without
  `TYP-0310`, while L0 Python Stage 1 rejects it.

## Summary

L0 Stage 2 signature resolution records the annotated or inferred type of a top-level `let`, but expression checking
does not subsequently validate the initializer against that type. An incompatible initializer can therefore pass
analysis and reach backend lowering without the expression and intrinsic metadata normally established for typed
initializers.

L0 Python Stage 1 already rejects the reproduction. L1 Stage 1 fixed the homologous omission in the completed top-level
initializer typing plan and provides a close native implementation model. This plan is intentionally L0-local because no
production change remains pending in either of those targets.

## ADR Impact

- Decision: Apply existing contextual initializer typing to L0 Stage 2 module-scope `let` declarations.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The fix restores existing `let` typing and diagnostic semantics in one omitted compiler path; it does not
    change the language, runtime, ABI, or compiler architecture.

## Current State and Root Cause

1. `sig_resolve_let()` resolves an explicit annotation or infers a restricted literal type and records it in signature
   tables.
2. For an annotated declaration, signature resolution does not infer the initializer expression or compare its type with
   the annotation.
3. The expression checker walks function bodies but has no per-module pass over resolved top-level initializers.
4. Backend top-level lowering assumes accepted initializers and may depend on expression-type or intrinsic-target
   metadata that was never populated.
5. The L1 Stage 1 fix introduced a reusable contextual initializer checker and a module-scope initializer pass, while
   preserving signature-only restrictions and diagnostic recovery.

## Scope of This Fix

1. Reuse or introduce one contextual initializer path for local annotated lets and top-level lets.
2. Check every resolved top-level initializer after signatures are available and before function-body checking or
   backend lowering.
3. Report annotation mismatches with existing `TYP-0310` semantics and source spans.
4. Populate expression types, variable-resolution records, and intrinsic targets needed by backend lowering.
5. Preserve existing top-level restrictions, literal inference, error recovery, and avoidance of diagnostic cascades.
6. Adapt the completed L1 implementation to L0's smaller language surface rather than copying L1-only bigint, slice,
   const, or opaque-layout branches.

## Diagnostics

No new code is required:

1. Reuse `TYP-0310` for incompatible annotated initializers.
2. Reuse existing intrinsic operand and constructor diagnostics.
3. Preserve `SIG-0030` for an unannotated non-literal initializer whose type cannot be inferred under the L0 top-level
   rules.
4. Add exact-count tests so a signature failure and initializer failure do not produce duplicate or cascading errors.

## Non-Goals

1. Adding L1 top-level `const`, bigint, slice, or non-constant initialization features to L0.
2. Changing which unannotated top-level initializer forms L0 permits.
3. Redesigning backend module initialization.

## Implementation Sequence

1. Add a failing analyzer fixture for annotated scalar mismatch and controls for valid scalar, struct, enum, and
   intrinsic initializers.
2. Factor or port the contextual initializer helper needed by both local and top-level declarations.
3. Add the per-module top-level initializer pass with explicit incoming-error recovery behavior.
4. Verify backend-required metadata for accepted initializers and prevent lowering after rejected ones.
5. Run focused analyzer/backend tests, then complete Stage 2 and triple-bootstrap validation.

## Verification

```bash
cd l0 && make test-stage2 TESTS="expr_types_test backend_test l0c_stage2_toplet_test.py"
cd l0 && make triple-test
make test
```

## Verification Criteria

1. `let bad: int = "text";` reports exactly one `TYP-0310` and never reaches code generation.
2. Valid annotated top-level initializers retain their existing generated behavior.
3. Intrinsic and constructor initializers receive the metadata required by backend lowering.
4. L0 Stage 2 agrees with Python Stage 1 for the shared L0 fixture set.
5. L1-only top-level semantics remain out of scope.
