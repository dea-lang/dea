# Bug Fix Plan

## Diagnose non-static L0 top-level let initializers

- Date: 2026-11-27
- Status: Draft
- Title: Diagnose non-static L0 top-level let initializers
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Module-scope initializer checking and diagnostics
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage1_py/l0_check_expr.py`
  - `l0/compiler/stage1_py/l0_backend_initializers.py`
  - `l0/compiler/stage1_py/l0_diagnostics.py`
  - `l0/compiler/stage2_l0/src/expr_types/initializers.l0`
  - `l0/compiler/stage2_l0/src/expr_types/expr.l0`
  - `l0/compiler/stage2_l0/src/backend/initializers.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/integration/test_toplet.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_toplet_test.py`
- Related:
  - [l0/docs/reference/c-backend-design.md](../../../../l0/docs/reference/c-backend-design.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md)
- Repro: Run `--check`, then `--gen`, on the module below with each L0 compiler. Repeat with `new int(1)` as the
  initializer.

## Current behavior

```l0
module main;
func make_ptr() -> int* { return new int(1); }
let p: int* = make_ptr();
func main() -> int { return *p - 1; }
```

Both stages accept the runtime call and the direct allocation during `--check`. During C generation, Stage 1 reports
`ICE-1034` for the call and `ICE-1180` for the allocation. Stage 2 aborts with `ICE-1181` for either.

Both stages also accept valid static intrinsics during checking. For `sizeof(f())` with an integer-returning function
and `ord(One(2))` with a payload variant, Stage 2 generates C. Stage 1 treats each intrinsic as a constructor and
reports `ICE-1031`.

## Implementation

1. **Stage 1.** After successful name resolution and type checking of a top-level `let` initializer, check the
   expression against L0's supported static initializer forms. Report an ordinary source error at the offending
   subexpression with the exact message `A top-level let initializer must be static.` Reject every evaluated ordinary
   function call, including local, imported, module-qualified and extern calls, even when the function body returns a
   literal. Apply the same diagnostic to `new` and other expressions outside the static subset.
2. **Static forms.** Accept supported literals, typed `null`, parentheses around static expressions, bare zero-field
   variants, and resolved struct or enum constructors with recursively static arguments. Recognize intrinsics through
   their resolved meaning. Bare `sizeof` uses its operand's type and never evaluates the operand. Bare `ord` accepts a
   statically known variant with static payloads. A read of a top-level variable is a runtime operation even when its
   own initializer is static. Bring Stage 1 emission of valid static intrinsics into line with these rules.
3. **Diagnostic code.** Provisionally reserve `TYP-0054` in the initializer diagnostic group for L0. Recheck the catalog
   and active reservations at implementation time, then register it in Stage 1, its diagnostic tests, and the shared
   catalog. Preserve existing errors for unresolved names, bad arguments and failed inference.
4. **Stage 2.** Make the existing static-initializer classification available during source checking. Match Stage 1's
   accepted forms, diagnostic and source location. Keep checking and emission in agreement within each stage.

## Verification

- Exercise the reproducer, a qualified imported call, an extern call, direct allocation, and an ordinary call nested in
  a constructor argument. For each, require `--check` to exit 1 with the exact code and message at the offending call or
  `new`. For the reproducer, require the same diagnostic from `--gen`, `--build`, and `--run` before emission.
- Update the Stage 2 test for `ord(choice)`, where `choice` is a module binding, to expect the ordinary diagnostic
  during `--check`. Exercise the same case in Stage 1. Cover `ord(One(f()))` to catch evaluated calls in payloads.
- Compile and run positive cases in both stages: nested static constructors, `ord(One(2))`, `sizeof(f())`, and
  `sizeof(new int(1))`. Verify the `sizeof` operand has no runtime effects. A local binding in `main` can still call
  `make_ptr()` and drop the resulting pointer.
- Verify `let p = new int(1);` retains its single `SIG-0030` for a missing type annotation. An ill-typed `sizeof`
  operand must also retain its specific type error.

## ADR Impact

- Decision: Report an unsupported L0 initializer through the diagnostic collector during source checking.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0013-compiler-diagnostic-collection-parser-recovery-and-phase-barriers.md`
  - Rationale: The existing phase barrier prevents code generation after a source error. This fix applies it to the
    existing L0 restriction on top-level initialization.
