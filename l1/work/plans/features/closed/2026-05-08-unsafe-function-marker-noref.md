# Feature Plan

## Add the `unsafe` function marker

- Date: 2026-05-08
- Status: Completed
- Title: Add the `unsafe` function marker
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0004-array-primitives-and-unsafe-marker.md`
- Subsystem: Lexer / parser / signatures / typing / interfaces / backend / stdlib / docs
- Modules:
  - `l1/compiler/stage1_l0/src/tokens.l0`
  - `l1/compiler/stage1_l0/src/lexer.l0`
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/decl.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/shared/l1/stdlib/sys/memory.l1`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/signatures_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
- Related:
  - `l1/work/initiatives/0004-array-primitives-and-unsafe-marker.md`
  - `work/plans/refactors/closed/2026-05-08-sys-memory-rename-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test signatures_test expr_types_test backend_test c_emitter_test"`

## Summary

Initiative `0004` introduces `unsafe` as a function-level contract marker. This plan adds the marker to the language
surface and type system after `sys.unsafe` has been renamed to `sys.memory`.

This tranche does not gate ordinary pointer dereference. Current L1 dereference-as-rvalue is a place copy and
recursively retains ARC fields, so expressions such as `let x = *p;` remain valid safe code when `p` is a valid
initialized pointer. Raw-pointer indexing gates land in a later pointer-indexing plan.

## Current State

1. `unsafe` is not a reserved keyword.
2. Function declarations and function pointer types carry no unsafe bit.
3. Bare references to top-level functions have plain `func(...) -> T` types.
4. The low-level memory module is expected to be named `sys.memory` by the prerequisite refactor plan.
5. Raw-memory externs rely on module naming and comments to communicate unchecked caller-side preconditions.

## Defaults Chosen

1. Function declaration syntax is `unsafe func name(...) -> T { ... }`.
2. Extern declaration syntax is `unsafe extern func name(...) -> T;`.
3. Function pointer syntax is `unsafe func(...) -> T`.
4. `unsafe func(...) -> T` and `func(...) -> T` are distinct types with no implicit conversion in either direction.
5. Safe functions may call `unsafe func` values in this initiative. The marker is a contract/type-surface marker, not a
   call-site gate.
6. Ordinary `*p` and `p.field` semantics are preserved. Gating dereference would require a future pointer-provenance
   design that can distinguish safe heap object pointers from unchecked raw pointers.
7. Raw-pointer indexing `p[i]` remains accepted under current behavior until the later pointer-index finalization plan
   adds its unsafe-context gate.

## Goal

1. Reserve `unsafe` as a keyword.
2. Parse and represent unsafe function declarations, unsafe extern function declarations, and unsafe function pointer
   types.
3. Carry the unsafe bit through signature analysis, type resolution, type equality, type formatting, bare function
   references, interface emission/parsing, and backend declaration emission.
4. Annotate the raw-memory extern declarations whose calls have unchecked caller-side preconditions.

## Implementation Phases

### Phase 1: Syntax and AST

1. Add an `unsafe` token and reserve it as a keyword.
2. Parse `unsafe func`, `unsafe extern func`, and `unsafe func(...) -> T`.
3. Store the unsafe bit on parsed function declarations and parsed function type references.
4. Update AST printing and parser tests for accepted and rejected syntax.

### Phase 2: Types, signatures, and interfaces

1. Add an unsafe bit to semantic function types.
2. Include the unsafe bit in type equality, type cloning, formatting, and cleanup.
3. Teach signature collection and type resolution to preserve unsafe function types.
4. Emit and parse unsafe function signatures in `.l1m` interfaces.
5. Type bare references to unsafe top-level functions as `unsafe func(...) -> T`.
6. Reject implicit assignment, argument passing, and return conversion between plain and unsafe function pointer types.

### Phase 3: Backend, stdlib, and docs

1. Emit C declarations and typedefs for unsafe function types with the same C ABI representation as matching plain
   function types, while keeping the L1 type distinction in analysis.
2. Mark `rt_realloc`, `rt_free`, `rt_memcpy`, `rt_memset`, `rt_memcmp`, `rt_array_element`, `rt_stdin_read`,
   `rt_stdout_write`, and `rt_stderr_write` as `unsafe extern func` in `sys.memory`.
3. Leave `rt_alloc` and `rt_calloc` as plain `extern func`.
4. Update reference docs for syntax, function pointer typing, and the present non-gating call semantics.

## Diagnostics

1. Provisionally reserve `PAR-0600` to `PAR-0619` for unsafe syntax diagnostics.
2. Provisionally reserve `TYP-0780` to `TYP-0799` for unsafe/plain function type mismatch diagnostics.
3. Re-check these ranges against the live diagnostic catalog at implementation time. If any code has been assigned in
   the meantime, choose a fresh unused range before implementation.

## Non-Goals

1. No block-level `unsafe { }`.
2. No unsafe call-site enforcement.
3. No gating of ordinary `*p` dereference or `p.field` access.
4. No pointer-indexing gate; that belongs to the later `ptr[i]` finalization plan.
5. No array type work.

## Verification Criteria

1. Parser tests cover unsafe function declarations, unsafe extern declarations, unsafe function pointer types, and
   malformed unsafe syntax.
2. Type tests prove `unsafe func(...) -> T` and `func(...) -> T` are distinct and do not implicitly convert.
3. Interface tests prove unsafe function signatures round-trip through `.l1m` emission/parsing.
4. Backend/C-emitter tests prove unsafe function values and declarations still lower to valid C function pointer
   representations.
5. Existing dereference examples such as `let copy = *p;` and pointer field access remain valid.
6. `make -C l1 test-stage1` passes.

## Completion Notes

1. `unsafe` is now a reserved keyword and the parser accepts `unsafe func`, `unsafe extern func`, and
   `unsafe func(...) -> T`.
2. Semantic function types carry the unsafe bit through type resolution, formatting, equality, bare function references,
   and `.l1m` interface round-tripping.
3. Plain and unsafe function pointer types remain ABI-compatible in generated C while staying distinct in L1 analysis,
   with `TYP-0780` covering unsafe/plain mismatch diagnostics.
4. `sys.memory` now marks the raw-memory and raw-buffer helpers with unchecked caller-side preconditions as
   `unsafe extern func`, and the runtime autodoc comments mirror the shipped Dea signatures.
5. Safe code may still call `unsafe func` values in this tranche; no call-site gate, `unsafe {}` block, dereference
   gate, or pointer-indexing gate was introduced.

## Final Validation

- `make -C l1 test-stage1 TESTS="parser_test signatures_test expr_types_test backend_test c_emitter_test interface_test"`
