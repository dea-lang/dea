# Feature Plan

## Add `extern "C"` declarations and `cstr`

- Date: 2026-04-24
- Status: Draft
- Title: Add `extern "C"` declarations and `cstr`
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0003-c-ffi.md`
- Subsystem: Parser / signatures / typing / backend / runtime / stdlib / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/work/initiatives/0003-c-ffi.md`
  - `l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md`
  - `l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`
  - `l1/work/plans/features/2026-06-21-cheap-string-slices-noref.md`
  - `l1/work/proposals/cstr-and-c-string-guards.md`
  - `l1/work/plans/features/closed/2026-04-22-variadic-functions-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test signatures_test expr_types_test backend_test l0c_lib_test"`

## Summary

Initiative `0003` fixes the C boundary around two core ideas:

- `extern "C"` blocks as the unmangled declaration surface for C interop,
- `cstr` as the distinct null-terminated string boundary type.

This plan adds the non-variadic, typed core of that boundary so L1 can express C layouts, C-callable declarations, and
explicit `string` -> `cstr` conversion without pretending that ordinary L1 `string` values are ABI-compatible with C
strings.

## Current State

1. The current FFI surface is still the older `extern func` primitive with no general `extern "C"` declaration block.
2. L1 has no dedicated `cstr` type distinct from `string`.
3. Dea `string` values already carry a trailing `\0` byte by construction, and runtime helpers
   (`sys.rt::rt_string_bytes_ptr`, the C-only `_rt_string_bytes`) already expose the underlying byte pointer, but there
   is no typed `string -> cstr` conversion surface that uses them.
4. The analyzer does not enforce a closed FFI-safe type set for the broader C boundary.
5. Initiative `0001` plans repeatable `--foreign-object` inputs for metadata-free C relocatable objects. This plan
   consumes that mechanism rather than treating C objects as Dea modules or bypassing object verification through raw
   positional inputs.

The draft [cheap string slices plan] would allow a logical `string` view whose end is not NUL-terminated. The
[C-string guard proposal] records the resulting alternative to this plan's current zero-cost reinterpretation default.
Phase 3 must not implement the conversion contract until that proposal is accepted, rejected, or superseded.

## Defaults Chosen

01. `extern "C"` is the only new declaration envelope in this plan.
02. Inside an `extern "C"` block, L1 supports `func`, `struct`, opaque `struct`, `type`, `enum`, and `let` declarations.
03. Declarations inside the block bypass LBI mangling entirely.
04. `cstr` is a builtin FFI boundary type distinct from `string` and bit-compatible with `byte*`. It is a distinct
    surface type with its own typing rules: conversion between `cstr` and `byte*` requires an explicit cast in either
    direction, with no implicit assignment or call-site compatibility, so the trailing-null guarantee is enforced at the
    type level even though the representations are identical.
05. `string -> cstr` conversion is a zero-cost reinterpretation of the string's byte pointer, not a copy. It is backed
    by the existing runtime primitives (`sys.rt::rt_string_bytes_ptr`, or the C-only `_rt_string_bytes`). The trailing
    null terminator is guaranteed by the `string` construction invariant, not by conversion-time work.
06. The conversion entrypoint lives as a boundary-level builtin or `sys.*` surface; `std.string` is user-facing and is
    not the right home for a runtime-lowering helper.
07. Ordinary `string` does not cross the C boundary unwrapped.
08. This plan focuses on the non-variadic typed core. C variadic FFI is a separate sibling tranche under Initiative
    `0003` per its §Resolved decisions; it does not land here regardless of how cleanly it would couple, so the main
    `extern "C"` surface ships independently of platform-specific variadic ABI work.
09. Declarations inside `extern "C"` blocks support an optional per-symbol link-name override. The exact syntax
    (trailing `= "..."`, attribute-style, or prefix annotation) is settled in Phase 1 of this plan; the closed answer at
    the initiative level (Initiative 0003 §Resolved decisions) is that the override exists in v1.
10. A raw C provider object is passed explicitly with `--foreign-object`; it has no Dea fingerprint, module identity,
    lifecycle, or entry semantics. Libraries and their search/rpath requirements use Initiative `0001`'s external-link
    options.

## Goal

1. Parse and represent `extern "C"` declarations.
2. Type-check a closed non-variadic FFI-safe boundary.
3. Emit unmangled C declarations/uses for that boundary.
4. Introduce `cstr` plus the standard conversion path from `string`.

## Implementation Phases

### Phase 1: Parser and declaration model

Extend parsing and AST representation for `extern "C"` blocks and the declarations allowed inside them:

- functions,
- concrete and opaque structs,
- opaque types,
- enums,
- extern globals.

Phase 1 also pins the syntax for the optional per-symbol link-name override (closed at the initiative level; see
Initiative 0003 §Resolved decisions). Validation must reject overrides that are not valid C identifiers and overrides
that collide with another link-visible symbol in the same link set.

### Phase 2: Signature and type rules

Teach signature analysis and type checking to enforce the FFI-safe boundary:

- builtin scalars,
- raw pointers,
- extern structs/enums,
- opaque extern types behind pointers,
- `cstr`.

Reject ordinary `string`, owned non-extern aggregate types, and other non-FFI-safe surfaces at the boundary.

### Phase 3: Backend and runtime support

Emit unmangled C declarations and lower `cstr` consistently in generated C. Wire the `string -> cstr` reinterpretation
through the existing runtime helpers (`sys.rt::rt_string_bytes_ptr` / `_rt_string_bytes`) rather than adding a new
`std.string` function; Dea strings already carry a trailing null by construction, so no conversion-time copy or
allocation is required. The conversion entrypoint lives as a boundary-level builtin or `sys.*` surface to keep the
runtime-lowering detail out of the user-facing `std.string` module.

### Phase 4: Docs and fixtures

Update grammar/design-decision docs and add regression coverage for:

- successful `extern "C"` declarations,
- opaque-vs-concrete extern types,
- invalid FFI-safe type crossings,
- `string` to `cstr` conversion behavior.
- an end-to-end fixture that compiles a tiny C provider to a relocatable object, links it through `--foreign-object`,
  calls it through `extern "C"`, and runs successfully.

## Diagnostics

1. This plan is expected to need parse-time diagnostics for malformed `extern "C"` blocks plus signature/type
   diagnostics for invalid boundary declarations and uses.
2. Provisionally reserve `PAR-0580` to `PAR-0599` for `extern "C"` syntax and placement diagnostics.
3. Provisionally reserve `SIG-0260` to `SIG-0279` for FFI declaration-shape and allowed-type diagnostics during
   signature analysis.
4. Provisionally reserve `TYP-0760` to `TYP-0779` for FFI-boundary type-checking diagnostics in expressions and calls.
5. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## ADR Impact

- Decision: Define a non-variadic C boundary with unmangled `extern "C"` declarations and a distinct `cstr` type.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The declaration envelope, admissible boundary types, naming behavior, and ownership rules form a durable
    L1 interoperability contract.
- Decision: Classify C-FFI diagnostics by compiler phase rather than a feature-specific family.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0005-diagnostic-code-catalog.md`
  - Rationale: The shared diagnostic catalog owns cross-level code-family allocation and should state the phase-oriented
    rule explicitly.
- Decision: Resolve `string` to `cstr` conversion against non-terminated cheap string views.
  - Scope: L1
  - Disposition: Pending
  - ADR: None
  - Rationale: The current zero-cost default conflicts with the cheap-string-slice representation and must be resolved
    before the conversion phase is implemented.

## Non-Goals

1. Automatic bindgen or C-header parsing.
2. New calling conventions beyond the platform C default.
3. Any package/dependency metadata for external libraries unless and until Dea adopts a package-management direction.
4. Any backport to L0.

## Verification Criteria

1. `extern "C"` declarations parse and lower without LBI mangling.
2. The analyzer enforces the intended non-variadic FFI-safe type boundary.
3. `cstr` exists as a distinct boundary type; `string -> cstr` conversion is a zero-cost reinterpretation backed by the
   existing runtime string-bytes primitives and does not touch `std.string`.
4. The roadmap and design-decision docs clearly distinguish this FFI surface from L1-defined variadic functions.
5. A metadata-free C provider object links only through `--foreign-object` and satisfies the declared unmangled C symbol
   without participating in Dea metadata, lifecycle, or entry selection.
6. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.

[c-string guard proposal]: ../../proposals/cstr-and-c-string-guards.md
[cheap string slices plan]: 2026-06-21-cheap-string-slices-noref.md
