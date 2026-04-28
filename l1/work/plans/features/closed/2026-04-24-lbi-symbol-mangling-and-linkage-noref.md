# Feature Plan

## Adopt LBI symbol mangling and export-driven linkage

- Date: 2026-04-24
- Status: Completed
- Title: Adopt LBI symbol mangling and export-driven linkage
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Backend / C emitter / ABI / docs
- Modules:
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `l1/work/plans/features/closed/2026-04-04-l1-dea-c-abi-prefix-migration-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="c_emitter_test backend_test l0c_lib_test"`
- Final validation:
  - `make -C l1 test-stage1 TESTS="c_emitter_test backend_test l0c_lib_test"`
  - `make -C l1 test-stage1`
  - `make -C l1 test-stage1-trace`
  - `make -C l1 check-examples`
  - `make clean test-all`

## Summary

The initiative now fixes the L1 Binary Interface around a tagged-section, length-prefixed mangling scheme:

`__dea M <seg_len><seg> ... S <sym_len><sym>`

(no spaces in the actual encoding, e.g. `std.math::abs` → `__deaM3std4mathS3abs`).

This replaces the current `dea_{module}_{name}` nominal-mangling style and couples linkage visibility to the module's
export manifest: exported symbols remain externally visible while non-exported top-level symbols are emitted as `static`
in generated C.

The encoding uses only the ISO C99 identifier alphabet `[A-Za-z0-9_]`. The full uppercase alphabet is reserved by the
LBI for category sigils; this tranche defines `M` (module path), `S` (source symbol name), and `I` (compiler-generated
module lifecycle symbol). The full normative spec lives in `l1/docs/specs/compiler/abi.md`.

This plan is the backend tranche that makes those emitted names and linkage rules real.

## Current State

1. The completed `dea_*` ABI-prefix migration established the public Dea naming family, but not the new LBI
   per-symbol/object-name scheme.
2. Generated nominal names still follow the older `dea_{module}_{name}` pattern.
3. Top-level declarations are emitted under one linkage model because the compiler does not yet know an explicit module
   export surface.
4. FFI linkage exceptions are still represented only by legacy `extern func` behavior.

## Defaults Chosen

1. The emitted source-symbol link identity uses the tagged-section encoding `__deaM<seg_len><seg>...S<sym_len><sym>`,
   with each module-path segment and the symbol name length-prefixed; see `l1/docs/specs/compiler/abi.md` for the
   normative format.
2. The canonical source form for the module path is the module's dotted path (for example `std.math`), not its
   filesystem path; each dotted segment becomes one length-prefixed component inside the `M` section. The encoding uses
   only ISO C99 identifier characters, so generated C compiles under `-std=c99 -pedantic-errors` without relying on the
   GCC/Clang/MSVC `$`-in-identifier extension. Uppercase ASCII letters are reserved as LBI category sigils; only `M`,
   `S`, and `I` are defined in this tranche.
3. Exported top-level declarations (including `let` and `const` bindings) keep external linkage in generated C. This
   explicitly overrules the earlier `const` plan which defaulted to `static const`: an exported `const` is emitted as
   `const T __dea...;` (global linkage) to satisfy ABI linking, while an internal `const` remains `static const`.
4. Non-exported top-level declarations are emitted as `static` where the backend can do so without altering runtime
   semantics.
5. Compiler-generated module lifecycle helpers use `__deaM<seg_len><seg>...I<life_len><life>`. This tranche emits only
   `I4init` for deferred top-level `let` initialization, while reserving the section for future lifecycle entries such
   as `at_exit`.
6. `extern "C"` declarations bypass LBI mangling entirely; the full surface for those declarations is deferred to the
   FFI plan.

## Goal

1. Centralize the new LBI mangling logic in Stage 1.
2. Emit exported and internal top-level declarations with distinct linkage.
3. Keep generated C deterministic and fixture-friendly.
4. Update ABI documentation and tests to the new emitted-name contract.

## Implementation Phases

### Phase 1: Centralize mangling helpers

Replace ad hoc name construction in the C emitter/backend with one canonical helper that emits:

- functions,
- top-level lets and consts,
- structs,
- enums,
- module lifecycle helpers,
- enum variants/tags as needed by the current backend layout.

The helper must be the only path that constructs emitted user/module symbol names so later overload/generic expansion
has one extension point.

### Phase 2: Export-driven linkage selection

Thread export-surface information from analysis into code generation so the emitter can decide whether a top-level
symbol stays externally visible or becomes `static`.

This phase should cover:

- top-level functions,
- top-level storage (both `let` and `const` bindings, ensuring exported `const`s drop the `static` specifier),
- forward declarations that must match the chosen linkage,
- imported declarations that should always remain references to the provider's exported symbol spelling.

### Phase 3: Fixture and doc refresh

Update backend golden fixtures and backend/reference documentation so they assert the new LBI spelling directly and
describe the export-driven linkage model.

## Diagnostics

1. No dedicated new user-facing diagnostic family is expected from this tranche.
2. If implementation pressure reveals a real user-facing failure mode, first reuse existing reserved-identifier and
   build/link diagnostics rather than minting new codes in this naming-only/backend tranche.

## Non-Goals

1. Parser support for export manifests or aliased imports.
2. `.l1m` interface files.
3. Fingerprint hashing or object metadata.
4. External-library linking CLI.
5. Full `extern "C"` declaration support.

## Verification Criteria

1. Generated C uses `__dea...` LBI spellings consistently for ordinary L1-defined symbols.
2. Exported and internal top-level declarations emit with the intended external vs `static` linkage.
3. Imported declarations reference provider-owned mangled names instead of re-deriving local aliases.
4. Backend/emitter tests and kept-C fixtures assert the new ABI spellings directly.

## Completion Notes

Implemented in L1 Stage 1. Source-level structs, enums, functions, and top-level bindings now use `M...S...` LBI names;
compiler-generated module lifecycle helpers use `M...I...` names, with `I4init` covering deferred top-level `let`
initialization. Export manifests now drive generated C linkage for functions, lets, and consts. Runtime helper struct
declarations, backend/reference docs, ABI docs, and kept-C regression fixtures were refreshed to the finalized ABI
spelling.
