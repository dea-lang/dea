# Feature Plan

## Emit per-module backend output and lifecycle entry points

- Date: 2026-07-17
- Status: Draft
- Title: Emit per-module backend output and lifecycle entry points
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: Backend / C emission / module lifecycle / executable entry bridge
- Modules:
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/codegen_options.l0`
  - `l1/docs/specs/compiler/abi.md`
  - `l1/docs/reference/c-backend-design.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/fixtures/driver/toplet_init_dep.l1`
  - `l1/compiler/stage1_l0/tests/fixtures/driver/toplet_init_main.l1`
- Related:
  - [`l1/work/plans/features/2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md`][module-graph]
  - [`l1/work/plans/features/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l1/work/plans/features/closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md`][superseded-init]
- Repro: `make -C l1 test-stage1 TESTS="backend_test c_emitter_test l1c_lib_test"`

## Summary

Add a per-module backend mode that emits definitions for exactly one source-backed module and declarations for the
imported surface it consumes. Each generated module translation unit exposes stable, externally linked lifecycle
functions `I4init` and `I4fini`. A module that defines a valid source `main` also exposes an `I5entry` bridge whose C
result is always `int`.

This plan does not switch the current `--build` or `--run` paths to per-module output. The existing whole-program
backend entry point and process-level C wrapper remain available until the later fan-out plan can replace them in one
complete step. That compatibility boundary allows the lifecycle ABI to land before compile-only production and
standalone linking without breaking the current compiler workflow.

## Dependencies and Ownership

1. The [module graph plan][module-graph] lands first and supplies the canonical target module plus its ordered direct
   imports and interface-backed analysis state.
2. This plan owns the module-output boundary, `I4init`, `I4fini`, and `I5entry`. It does not own object metadata or
   executable wrapper generation.
3. The [object metadata plan][object-metadata] follows this plan and anchors its metadata arrays from the always-present
   `I4init` function.
4. The [link-set plan][link-set] selects one `I5entry`, generates the only process-level C `main`, and orders lifecycle
   calls across modules.
5. Interface fingerprint work is independent of this plan after the module-graph dependency and may proceed in parallel.

## Current State

1. `backend_generate(...)` walks every source unit in the analyzed closure and emits one combined C translation unit.
2. Imported source modules therefore contribute definitions rather than declarations to the generated program.
3. A hidden per-module init function exists only when that module has deferred top-level `let` initialization, and a
   hidden whole-program function sequences those conditional helpers.
4. The backend emits the process-level C `main` beside the program definitions. That wrapper invokes the user `main` and
   cleans every ARC-managed top-level `let` in the combined closure.
5. There is no per-module finalizer or stable compiler-generated bridge through which a separately generated wrapper can
   call a non-exported source `main`.

## Backend Interface

Retain `backend_generate(result, opts, cfg)` as the legacy whole-program generator until the fan-out plan removes its
need. Add a distinct internal entry point with this semantic contract:

```text
backend_generate_module(result, target_module, opts, cfg) -> string
```

1. `target_module` is a canonical dotted module name and must resolve to exactly one source-backed unit in `result`.
   Interface-only units are declaration providers and cannot be selected for definition emission.
2. The module generator emits full definitions only for the target module's own types, top-level bindings, and
   non-extern functions.
3. Imported functions and top-level bindings are emitted only as `extern` declarations under their provider-owned LBI
   names. Imported transparent nominal layouts and other required C type declarations may be reproduced, but no imported
   value or lifecycle definition is emitted.
4. The target module's export manifest continues to control source-symbol linkage: exported definitions are external,
   non-exported definitions are `static`.
5. Compiler-generated lifecycle and entry symbols are ABI infrastructure, not source exports. Their linkage is not
   controlled by the source export manifest.
6. Module output never contains the process-level C `main`, the legacy whole-program init chain, or dependency lifecycle
   calls.

The implementation may represent the distinction as an output-kind enum in `codegen_options.l0`, but callers must not
toggle individual emission booleans that could create unsupported hybrids. The two supported states are the legacy
whole-program generator and one named module generator.

## Lifecycle and Entry ABI

### `I4init`

1. Every module translation unit defines exactly one external `void` function mangled as the module lifecycle name
   `I4init`, including modules with no deferred initialization.
2. The function initializes only deferred top-level `let` values owned by that module, in their established
   within-module order. It does not initialize imported modules.
3. A module with no deferred work emits an empty, callable function body. The symbol must not become `static` or be
   omitted.
4. The function is a one-shot lifecycle operation. The generated executable wrapper is responsible for calling it
   exactly once in dependency order; the function does not add an idempotence guard.

### `I4fini`

1. Every module translation unit defines exactly one external `void` function mangled as `I4fini`.
2. The function performs the existing final cleanup operation for ARC-managed top-level `let` values owned by that
   module. It never cleans imported storage or calls another module's finalizer.
3. A module with no owned cleanup work emits an empty, callable function body.
4. The function is also one-shot. Reverse dependency ordering and exactly-once invocation belong to the executable
   wrapper in the link-set plan.

### `I5entry`

1. A source-backed module that defines a non-extern `main` accepted by the existing entry-signature checks emits one
   external bridge mangled as `I5entry`, with C signature `int <mangled-name>(void)`.
2. The bridge is emitted even when source `main` is non-exported. It calls that module's possibly `static` source
   definition from inside the same translation unit.
3. A module without a valid source definition of `main` emits no `I5entry` symbol. An `extern` declaration alone does
   not make a module an entry candidate.
4. The bridge preserves the current process-wrapper normalization: an L1 `int` result becomes the C exit status, a
   `bool` result maps `true` to `0` and `false` to `1`, and every other currently accepted result type is called and
   normalized to `0`. Existing diagnostics for non-preferred entry result types remain unchanged.
5. `I5entry` does not call `_rt_init_args`, `I4init`, or `I4fini`. The process wrapper owns argument initialization and
   the complete lifecycle sequence.

The ABI specification records `I4init`, `I4fini`, and `I5entry` as reserved compiler-generated module symbols under the
existing `I` terminal. No new source spelling is introduced.

## Implementation Phases

### Phase 1: Isolate one-module emission

Add the module generator and make definition-emitting backend walks target-aware. Preserve imported type and value
declarations required to compile the target C translation unit, while proving that imported definitions cannot leak into
it. Keep the legacy generator behavior unchanged.

### Phase 2: Emit the lifecycle pair

Replace conditional module-init emission in module mode with the always-present external `I4init`. Partition existing
top-level ARC cleanup by owning module and emit it through the always-present external `I4fini`. Keep cross-module
sequencing out of both functions.

### Phase 3: Emit the entry bridge

Move result normalization into the optional `I5entry` bridge for module output. Keep the source `main` linkage dictated
by its export state and remove process-wrapper emission from module mode.

### Phase 4: Lock the ABI and compatibility boundary

Update the LBI ABI and backend-design references, add focused golden C assertions, and retain regression coverage for
the legacy generator until the fan-out plan removes it.

## Diagnostics

1. No new user-facing diagnostic category or code reservation is expected. Selecting an invalid module-output target is
   an internal caller-contract failure because semantic driver validation precedes backend generation.
2. Existing entry-signature diagnostics remain the source of truth for whether a source `main` is valid.
3. If implementation exposes a genuinely user-triggerable lifecycle diagnostic, inspect the live catalog and plan an
   unused code before adding it; do not consume the object-metadata reservation owned by the next plan.

## Non-Goals

1. Computing or embedding interface fingerprints.
2. Defining the object metadata wire format or reading object files.
3. Implementing `-c`, standalone `--link`, `--entry`, or `--foreign-object`.
4. Topologically ordering modules or generating the executable wrapper.
5. Changing source `main` signature rules, source export semantics, or ARC ownership rules.
6. Switching existing `--build` and `--run` to multi-CU output.

## Verification Criteria

1. Module-mode C contains definitions for exactly the selected source module and only declarations for imported values.
2. Exported target definitions remain external, non-exported target definitions remain `static`, and compiler-generated
   lifecycle symbols remain external in both cases.
3. Every module output contains exactly one `I4init` and one `I4fini`, including modules where both bodies are no-ops.
4. Deferred top-level initialization affects only the owning module; ARC top-level finalization affects only the owning
   module.
5. A non-exported valid source `main` remains `static` and is reachable through an external `I5entry`; a module without
   a valid source `main` has no entry bridge.
6. Golden tests cover `int`, `bool`, and other accepted result normalization and prove that the bridge performs no
   lifecycle orchestration.
7. Module output contains no process-level C `main` and no calls to another module's lifecycle functions.
8. Existing single-CU build/run and top-level initializer tests remain unchanged through the legacy generator.
9. The ABI and C backend design documents describe the three compiler-generated symbols before this plan closes.

[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[link-set]: 2026-07-17-link-set-driver-and-wrapper-noref.md
[module-graph]: 2026-07-17-separate-compilation-artifact-layout-and-module-graph-noref.md
[object-metadata]: 2026-07-17-object-metadata-emission-and-readers-noref.md
[superseded-init]: closed/2026-04-24-multi-cu-initialization-and-link-order-noref.md
