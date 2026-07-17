# Feature Plan

## Add the separate-compilation driver surface

- Date: 2026-06-13
- Status: In Progress
- Title: Add the separate-compilation driver surface
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0001-separate-compilation-and-linking.md`
- Subsystem: CLI / driver / build workflow / docs
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/l1c.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/name_resolver.l0`
  - `l1/compiler/stage1_l0/src/parser/interface.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/sem_context.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/name_resolver_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/work/initiatives/0001-separate-compilation-and-linking.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-all`

## Summary

Initiative `0001` now commits L1 to a real separate-compilation workflow built around per-module `.l1m`, generated C,
and object files. This plan owns the driver/CLI side of that workflow, but it is split into implementation tranches so
the repo does not land a half-wired user surface:

1. direct `.l1m` import replay and codegen plumbing,
2. CLI option parsing and validation for the future surface,
3. correct compile-only output for one implementation module,
4. build/run fan-out and link orchestration.

Link-option expansion for external libraries is tracked separately so this driver plan can stay focused on module
compilation orchestration.

## Current State

1. Internal analysis entry points can replay supplied dependency-free direct-provider `.l1m` files through semantic
   analysis and C generation without loading provider source.
2. Stage 1 still treats one requested entry module plus its import closure as one generated C program build.
3. The current CLI mode matrix is centered on `--build`, `--run`, and inspection modes, not compile-only output.
4. The driver does not search an interface-path list for `.l1m` files.
5. Before Phase 2, shared runtime short-option plumbing occupied `-I` / `-L` in a pre-separate-compilation way and L0
   used `-c` for host-C selection, so reclaiming canonical driver syntax required one coordinated breaking migration.
6. The abandoned local `module-interface-implementation` branch proved that direct `.l1m` imports are useful, but also
   showed that exposing `-I` to `--build`/`--run` before provider objects are linked leaves unresolved externs, and that
   compile-only must not emit a whole source closure into one object.
7. The same branch did not complete transitive `.l1m` dependency loading, and any parsed implementation-tier `link`
   entries were not yet populated into the project graph that later provider-object linking depends on.

## Defaults Chosen

1. `-c <module>` (long alias `--compile <module>`) is the stable compile-only user surface.
2. `-I <dir>` (long alias `--interface-path <dir>`) becomes the interface-search path used during compile-involving
   flows.
3. The old runtime-specific `-I` / `-L` short aliases are withdrawn across L0 and L1. The long forms `--runtime-include`
   and `--runtime-lib` keep working unchanged, with `-Ri` and `-Rl` as their semantic short aliases.
4. Shared Dea-specific controls use exact semantic namespaces: `-Gc`, `-Rp` / `-Rs`, `-Cc` / `-Co`, `-Ri` / `-Rl`, and
   `-Vl`. Conventional `-g`, `-S`, `-L`, and `-l` meanings are reserved until their capabilities land.
5. Whole-program `--build` and `--run` remain convenience orchestrators. They do not accept interface-backed imports as
   a complete user-facing workflow until the fan-out/link tranche can provide every required provider object.
6. The driver continues to own import-closure computation rather than pushing build-graph logic into ad hoc scripts.
7. External-library linker flags are not part of this plan beyond reserving their canonical syntax.

## Goal

1. Add interface-backed semantic and codegen plumbing for direct imports.
2. Add compile-only and interface-path options to the L1 CLI/driver when their behavior is coherent.
3. Teach build/run orchestration to compile modules individually in a later fan-out tranche.
4. Preserve current bootstrap ergonomics for ordinary `--build` and `--run` users.
5. Establish the command surface that later link and external-library plans can build on.

## Implementation Phases

### Phase 1: Direct `.l1m` import plumbing (completed)

Teach the driver, name resolver, signature resolver, and backend to consume a direct imported `.l1m` for:

- exported symbols,
- transparent struct/enum layouts and opaque name-visible nominal declarations,
- function and top-level binding signatures,
- external declarations in generated C.

Direct interface replay must preserve imported nominal visibility state. Transparent imported nominal types carry full
layout for ordinary by-value and field operations; opaque imported nominal types are name-visible but layout-hidden and
must support pointer-only use without requiring a full definition in the consumer CU.

This phase should not expose `-I` to `--build` or `--run` as a complete workflow. Its verification should compile a
consumer against a pre-existing direct provider interface and check generated C shape, while keeping provider-object
linking out of scope.

This phase may start with direct provider interfaces only, but it must not silently treat missing transitive interface
dependencies as success. Until transitive `.l1m` closure loading exists, nested interface dependencies should either be
rejected with a clear diagnostic or documented as unsupported in the specific driver entry point being tested.

Stage 1 now activates only supplied interfaces selected by imports and replays their cloned canonical metadata through
name resolution, signature resolution, expression typing, interface projection, and C generation. Source and interface
providers share enum export behavior; interface literals round-trip recursive arrays and signed scalars; extern ABI,
unsafe, variadic, fingerprint, hash, and parameter-name metadata survive replay. Dependency-bearing direct providers
remain rejected until closure loading lands, and malformed duplicate declarations are rejected before replay.

The completed tranche passed focused replay, parser, resolver, backend, and emitter tests; focused replay/parser trace
tests; and the clean full L1 suite:

```bash
make -C l1 test-stage1 TESTS="interface_replay_test interface_test name_resolver_test signatures_test type_resolve_test backend_test c_emitter_test"
make -C l1 test-stage1-trace TESTS="interface_replay_test interface_test"
make -C l1 clean test-all
```

#### Phase 1 review follow-up (completed 2026-07-13)

Post-implementation review found three direct-replay gaps. Active interfaces now retain a wire-preserving clone for
projection alongside their alias-normalized semantic clone, so alias spellings remain aligned with stored fingerprints
and symbol hashes. Interface-backed `sys.real` providers now enable the runtime helper definitions and host math-library
flags. Expression typing rejects `drop` on imported opaque pointees with `RES-0038`, because hidden owned fields require
provider-side cleanup.

The follow-up passed focused interface, emitter, and build-driver tests; focused replay/emitter trace tests; and clean
full L1 validation:

```bash
make -C l1 test-stage1 TESTS="analysis_test interface_replay_test interface_test c_emitter_test build_driver_test"
make -C l1 test-stage1-trace TESTS="analysis_test interface_replay_test c_emitter_test"
make -C l1 clean test-all
```

Results: 48 normal tests, 37 default trace tests, the environment stackability check, and all four L1 examples passed.

### Phase 2: CLI option and mode design (completed 2026-07-16)

Extend CLI parsing and validation for:

- `-c` / `--compile`,
- `-I` / `--interface-path`,
- `-Gc`, `-Rp` / `-Rs`, `-Cc` / `-Co`, and `-Vl` as shared semantic aliases,
- `-Ri` (new short alias for the existing `--runtime-include`),
- `-Rl` (new short alias for the existing `--runtime-lib`),
- any internal/testing-only long-form interface-emission mode needed to support Stage 1 development.

This phase should also retire the old runtime-specific meaning of `-I` and `-L` so the option surface stops conflicting
with the new separate-compilation model. The long forms `--runtime-include` / `--runtime-lib` keep working unchanged.

CLI parsing may land before all orchestration is complete only if mode validation prevents users from entering
half-supported workflows. In particular, `--build` and `--run` must not accept interface-backed imports until their
provider objects are linked.

All current compiler stages now reserve `-c` / `--compile` for compile-only mode, store repeatable `-I` /
`--interface-path` values in declaration order, and gate interface paths to compile mode with paired `L0C-2031` /
`L1C-2031`. The coordinated L0 2.0/L1 alias migration uses exact semantic namespaces for Dea-specific controls. The
canonical `-g`, `-S`, `-L`, and `-l` spellings report paired `L0C-2032` / `L1C-2032` until debug, assembly, and external
linking support lands. Compile mode deliberately dispatches to `L0C-9510` / `L1C-9510` without analysis or artifact
creation, so Phase 3 remains responsible for interface discovery and atomic `.c`, `.o`, and `.l1m` output.

Implementation review closed the remaining parity gaps in this surface. L0 Stage 1 fallback presentation now skips
value-option arguments and retains empty-value presence for mode validation. All active drivers reject a bare `--`
outside run mode, while self-hosted missing-value diagnostics preserve the exact short or long token. The L1 Stage 1
build inherits raw `L0_CFLAGS`, and resolver tests plus live docs pin system roots before project roots while preserving
declaration order inside each group.

The completed tranche passed focused CLI, library-driver, source-path, and build-environment tests across L0 and L1,
normal full monorepo validation, and both full self-hosted trace sweeps:

```bash
make -C l0 test-stage1
make -C l0 test-stage2 TESTS="cli_args_test l0c_lib_test source_paths_test"
make -C l0 test-stage2-trace
make -C l1 test-stage1 TESTS="cli_args_test l1c_lib_test source_paths_test compiler_runtime_build_env_test.py"
make -C l1 test-stage1-trace
make test
```

Results: L0 Stage 1 passed 1,412 tests; the focused L0 Stage 2 and L1 Stage 1 matrices passed 3/3 and 4/4 targets. Root
`make test` passed L0 Stage 2 (54/54 normal tests, 8/8 examples, and all workflow checks) and L1 Stage 1 (53/53 normal
tests, the environment stackability check, and 4/4 examples). The full L0 Stage 2 and L1 Stage 1 trace sweeps passed
33/33 and 37/37 eligible tests.

### Phase 3: Compile-only driver flow

Teach the driver/library entry points to compile a single module into generated C, object output, and `.l1m`, with
imported modules loaded through interface discovery rather than always rebuilding the whole closure as one generated C
unit.

The compile-only artifact writer must treat `.l1m` as part of a successful output set, not as an early side effect. If C
compilation or object writing fails, the command must not leave a newly written interface file that can be mistaken for
a valid provider artifact on a later build.

### Phase 4: Build/run fan-out orchestration

Update `--build` and `--run` to compute the import closure, compile modules individually, and prepare the later link
stage inputs deterministically. This phase owns passing every provider object needed by an interface-backed consumer to
the linker.

This phase also owns walking the transitive `.l1m` dependency graph for interface-backed builds and ensuring any
implementation-tier dependency records that feed linking, including populated `link` entries, correspond to concrete
provider objects or explicit external-link inputs.

## Diagnostics

1. This plan is expected to need new driver diagnostics for interface-path handling, compile-only target resolution, and
   new mode-validation failures.
2. Provisionally reserve `DRV-0070` to `DRV-0089` for separate-compilation target and interface-search-path discovery
   diagnostics.
3. Provisionally reserve `L1C-2030` to `L1C-2049` for new CLI mode validation and compile-only/build orchestration
   failures.
4. Re-check the live catalog at implementation time before assigning final numbers. If any proposed slot has been used
   in the meantime, choose a different free block then.

## Non-Goals

1. Fingerprint hashing and link-time provider verification.
2. External-library linking flags.
3. Runtime static-library extraction.
4. Full C FFI support.
5. Landing `--build`/`--run` interface search without provider-object link orchestration.
6. Emitting one compile-only object that contains multiple source modules from the import closure.
7. Treating direct-interface replay as proof that transitive interface closure, dependency graph population, or
   provider-object discovery is complete.
8. Defining the source-language `export opaque { T }` semantic diagnostics; the opaque-export plan owns by-value opaque
   rejection and exported-surface visibility checks.

## Verification Criteria

01. Direct `.l1m` imports replay into analysis and codegen without requiring the provider source.
02. `-c` / `--compile` and `-I` / `--interface-path` parse, validate, and participate in the driver only for supported
    modes.
03. Shared exact aliases resolve as documented, the historical meanings of `-c`, `-I`, `-L`, `-l`, `-g`, `-S`, `-P`, and
    `-C` are retired, and long option names remain stable.
04. `--compile` emits exactly one implementation module's object and does not smuggle source-import definitions into
    that object.
05. A failed object compilation does not leave a fresh `.l1m` interface artifact behind.
06. `--build` and `--run` preserve current user-facing behavior until the fan-out tranche links all provider objects.
07. Interfaces with transitive `require` / `link` dependencies are either resolved through the interface closure or
    rejected with a clear diagnostic until closure loading is implemented.
08. Implementation-tier `link` dependency records are populated before any build/run or link-verification path relies on
    them to select provider objects.
09. Direct interface replay tests cover pointer-only use of imported opaque nominal types without requiring imported
    layout, reject layout-dependent `drop` on opaque pointees, and retain by-value opaque rejection coverage.
10. Driver tests cover invalid mode combinations, missing interface paths, direct interface imports, and successful
    compile-only flows.
11. Any newly assigned diagnostic codes are registered in `docs/specs/compiler/diagnostic-code-catalog.md`.
