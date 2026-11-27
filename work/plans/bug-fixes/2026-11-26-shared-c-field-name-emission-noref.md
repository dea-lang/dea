# Bug Fix Plan

## Emit valid C names for Dea fields

- Date: 2026-11-26
- Status: Draft
- Title: Emit valid C names for Dea fields
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 canonical compiler
- Origin: Establish the member-name mapping and native regression in L0 Stage 1.
- Porting rule: Apply the same field cases to L0 Stage 2, then L1, respecting each level's C interface.
- Target status:
  - L0 Stage 1: Pending
  - L0 Stage 2: Pending
  - L1 canonical compiler: Pending
- Subsystem: C aggregate declarations, construction, access and cleanup
- Modules:
  - `l0/compiler/stage1_py/l0_c_declarations.py`, `l0/compiler/stage1_py/l0_c_values.py`,
    `l0/compiler/stage1_py/l0_c_cleanup.py`
  - `l0/compiler/stage2_l0/src/c_emitter/declarations.l0`, `l0/compiler/stage2_l0/src/c_emitter/values.l0`,
    `l0/compiler/stage2_l0/src/c_emitter/lifetime.l0`
  - `l1/compiler/src/c_emitter/declarations.l0`, `l1/compiler/src/c_emitter/expr.l0`,
    `l1/compiler/src/c_emitter/lifetime.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_constructors.py`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l1/compiler/tests/l1c_build_run_multi_cu_test.py`
- Related:
  - [l0/work/plans/bug-fixes/2026-11-21-module-qualified-lookup-noref.md](../../../l0/work/plans/bug-fixes/2026-11-21-module-qualified-lookup-noref.md)
  - [l0/docs/reference/c-backend-design.md](../../../l0/docs/reference/c-backend-design.md)
  - [l1/docs/reference/c-backend-design.md](../../../l1/docs/reference/c-backend-design.md)
- Repro: Save the example below as `main.l0` or `main.l1`; run the target compiler with `--check`, then `--run`.

## Summary

```dea
module main;
struct Box { sizeof: int; }

func main() -> int {
    let b = Box(9);
    b.sizeof = b.sizeof + 1;
    return b.sizeof - 10;
}
```

Both L0 stages and L1 accept this program during checking. Each emitter copies the source field name into the C
declaration, where `sizeof` is a keyword. Native compilation fails with a field-name error. A named enum payload
(`enum Item { Value(sizeof: int); }`) fails the same way when constructed and matched. Renaming the field in Dea works
around the failure. Both field declarations remain legal under the planned L0 module-scope reservation.

## Implementation and verification

1. Establish one deterministic, collision-free mapping per emitter for source names used as C members. Preserve existing
   safe spellings wherever possible. Test a keyword alongside a legal source name that matches its proposed escape, with
   different values in the same aggregate. Preserve field order and types, and the member spellings in public runtime
   headers used by foreign C callers.
2. Apply the mapping at declarations and every use, including designated initializers, value and pointer reads and
   writes, enum construction and pattern extraction, and generated retain and cleanup code. Include variant names used
   as C union members. Keep the original Dea names in lookup, diagnostics and L1 module interfaces.
3. Compile and run the example and a named-payload match through each target. Include an ordinary field such as `ord`, a
   collision pair, and an owned string field exercised through copy and drop. Verify distinct values and balanced
   ownership. In L1, compile a provider and consumer separately to exercise header and use-site agreement.

## ADR Impact

- Decision: Preserve Dea field identity when emitting C aggregate members.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: The emitter must already produce valid C for legal Dea fields. The fix concerns the spelling of generated
    members within the existing aggregate layout.
