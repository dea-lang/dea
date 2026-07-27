# Feature Plan

## Port the L1 compiler to self-hosted Stage 2

- Date: 2026-07-11
- Status: Draft
- Title: Port the L1 compiler to self-hosted Stage 2
- Kind: Feature
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L1 Stage 1 semantic and diagnostic oracle
  - L1 Stage 2 self-hosted compiler
- Origin: L1 Stage 1 after the source-decomposition refactor settles its production module layout.
- Porting rule: Seed Stage 2 as a mechanical `.l0` to `.l1` source port, preserve Stage 1 behavior and diagnostics
  through the first fixed point, and defer L1-native source divergence to separately reviewed follow-up work.
- Target status:
  - L1 Stage 1 semantic and diagnostic oracle: Implemented
  - L1 Stage 2 self-hosted compiler: Pending
- Subsystem: Compiler bootstrap / Stage 2 port / parity validation
- Modules:
  - `l1/compiler/stage1_l0/src/`
  - `l1/compiler/stage2_l1/`
  - `l1/scripts/build_stage1_l1c.py`
  - `l1/scripts/build_stage2_l1c.py`
  - `l1/Makefile`
  - `.github/workflows/l1-ci.yml`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/`
  - `l1/compiler/stage2_l1/tests/`
  - `l1/tests/test_env_stackability.py`
- Related:
  - `l1/work/plans/refactors/2026-07-08-stage1-source-decomposition-noref.md`
  - `docs/decisions/0001-two-stage-architecture.md`
  - `l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md`
  - `l1/docs/roadmap.md`
- Repro: `make -C l1 triple-test`

## Summary

L1 has enough implemented language, standard-library, runtime, and backend surface to host its compiler today. The
remaining work is a controlled source port plus the build, test, and parity mechanics needed to make that port a
maintainable Stage 2 implementation.

This plan establishes one bounded completion point: Stage 1 builds Stage 2, Stage 2 builds itself to a byte-identical
retained-C fixed point, the self-built compiler passes its own test surface, and the normal L1 development workflow can
select Stage 2 explicitly. It does not keep the port open for subsequent L1-native readability or performance refactors.

The two-stage architecture in [docs/decisions/0001-two-stage-architecture.md][two-stage-architecture] remains
authoritative. Stage 1 is the bootstrap entrypoint and behavioral oracle; Stage 2 is a port, not an independent language
implementation.

## Current State and Feasibility Evidence

1. `l1/compiler/stage1_l0/` is the only committed L1 compiler implementation. Its production sources are written in L0
   and built by the upstream L0 Stage 2 compiler.
2. `l1/compiler/stage2_l1/` contains only a placeholder README.
3. The current Stage 1 production source tree contains 36,339 lines of `.l0` across the compiler modules.
4. A 2026-07-11 feasibility audit copied that source tree into an ignored build directory, changed only the source
   suffixes from `.l0` to `.l1`, and compiled it through the repo-local L1 Stage 1 compiler without a language or source
   rewrite.
5. The Stage 1-built compiler, its first self-build, and the next self-build emitted byte-identical retained C. The
   probe also checked a normal L1 example through the final compiler.
6. The same audit ran the current L1 validation surface successfully: 47 normal Stage 1 tests, 36 default trace tests,
   environment-stackability validation, and four warning-free examples.
7. Separate compilation, C FFI, generics, closures, address-of, dynamic buffers, and release productization are not
   prerequisites for the first self-hosted fixed point. The initial Stage 2 compiler can retain the current
   whole-program C99 backend and source-based import model.

These results remove language expressiveness as a bootstrap blocker. The work left in this plan is source lifecycle,
stage identity, artifact construction, test ownership, deterministic fixed-point validation, CI, and documentation.

## Defaults Chosen

01. Complete [l1/work/plans/refactors/2026-07-08-stage1-source-decomposition-noref.md][stage1-decomposition] before
    taking the committed Stage 2 source snapshot. Porting first would either duplicate that broad refactor or force an
    immediate two-tree synchronization exercise.
02. Close this plan at the strict self-hosting fixed point. L1-native cleanup is a prioritized follow-up queue, not a
    closure requirement.
03. Make the first source snapshot mechanical. Preserve module names, compiler passes, ownership, diagnostics, generated
    C, ABI behavior, and runtime interactions.
04. Limit intentional initial source differences to `.l1` suffixes, Stage 2 identity text, stage-specific comments,
    artifact names, temporary-file prefixes, and test labels.
05. Keep Stage 1 authoritative for language semantics and diagnostic codes. Equivalent Stage 2 conditions reuse Stage 1
    codes and messages.
06. Keep `L1_HOME`, `L1_BUILD_DIR`, `L1_CC`, `L1_CFLAGS`, the existing runtime archives, and the existing L1 stdlib
    discovery contract. Do not add a second environment namespace for Stage 2.
07. Keep stage selection explicit. `use-dev-stage1` selects the Stage 1 `l1c` alias and `use-dev-stage2` selects Stage
    2; tests invoke their subject stage directly instead of relying on the current alias.
08. Require byte-for-byte retained-C identity between the second and third Stage 2 self-builds. Compare normalized
    native artifacts where the host toolchain can produce stable output, following the platform exceptions already
    proven by [l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md][l0-triple-bootstrap].
09. Do not require exact Stage 1 versus Stage 2 generated-C identity across the full fixture corpus. Require equivalent
    behavior, matching diagnostics for equivalent failures, and an exact Stage 2 self-build fixed point.
10. Introduce no language, ABI, runtime, or stable compiler-CLI option as part of this plan.

## Goal

1. Add a complete L1-language Stage 2 compiler source tree seeded from the settled Stage 1 implementation.
2. Build a repo-local `l1c-stage2` artifact through Stage 1 using the existing runtime and stdlib layout.
3. Port the implementation test surface so Stage 2 compiles and exercises its own `.l1` tests.
4. Preserve Stage 1 and Stage 2 observable behavior, diagnostics, CLI modes, and generated-program semantics.
5. Establish strict triple-bootstrap validation and make Stage 2 selectable for normal L1 development.
6. Update CI and current L1 documentation without making L1 release-bearing.

## Public Interfaces and Deliverables

The implementation adds the following repo-local development surface:

- `make -C l1 build-stage2`
- `make -C l1 use-dev-stage2`
- `make -C l1 test-stage2`
- `make -C l1 test-stage2-trace`
- `make -C l1 triple-test`
- `build/dea/bin/l1c-stage2`
- `build/dea/bin/l1c-stage2.native`
- optional `build/dea/bin/l1c-stage2.c` when retained C is requested

The Stage 2 CLI exposes the same modes, options, exit meanings, and environment behavior as Stage 1. Its fallback
identity is:

```text
Dea language / L1 compiler (Stage 2)
```

`make -C l1 check-examples` moves to the latest-stage contract and invokes `l1c-stage2` directly once Stage 2 exists.
`make -C l1 test-all` covers both compiler stages, their default trace checks, environment validation, and examples.

This plan adds no install, distribution, release, or docs-publishing interface.

## Implementation Phases

### Phase 1: Freeze the port baseline

1. Complete the Stage 1 source-decomposition plan and its full validation.
2. Record the settled production module and line-count inventory in this plan's implementation notes.
3. Re-run the filename-only `.l1` feasibility probe against the settled tree before committing the port.
4. Confirm `make -C l1 test-all` passes and the worktree contains no generated source artifacts.

### Phase 2: Seed the Stage 2 source tree

1. Replace the placeholder-only Stage 2 directory with `src/`, `tests/`, `scripts/`, and an updated README.
2. Copy the complete settled Stage 1 production module graph into `compiler/stage2_l1/src/`, converting `.l0` suffixes
   to `.l1` while preserving module and import names.
3. Change only the approved stage-specific identity, comment, temporary-prefix, and artifact-label differences.
4. Document the Stage 1 oracle policy and the rule that future semantic changes land in Stage 1 before their Stage 2
   equivalents.
5. Review the initial port with a normalized source comparison that ignores suffixes and the documented intentional
   deltas. Do not establish permanent textual parity as a long-term requirement.

### Phase 3: Add Stage 2 build and selection mechanics

1. Add `l1/scripts/build_stage2_l1c.py`, reusing the current L1 build-layout validation and shared launcher rendering
   behavior rather than introducing a parallel artifact layout.
2. Make `build-stage2` depend on a current repo-local Stage 1 compiler and the L1 runtime archives.
3. Invoke `l1c-stage1 --build -Rp compiler/stage2_l1/src -o <build>/bin/l1c-stage2.native l1c`, adding `--keep-c` when
   requested.
4. Generate POSIX and Windows Stage 2 wrappers that set repo-relative `L1_HOME` and `L1_BUILD_DIR` consistently with
   Stage 1.
5. Add stage-aware alias selection so `use-dev-stage2` points `l1c` at `l1c-stage2` and `use-dev-stage1` remains the
   explicit way back to the bootstrap compiler.
6. Ensure build and test helpers invoke explicit repo-local stage artifacts and never infer a bootstrap compiler from
   whichever `l1c` happens to be on `PATH`.

### Phase 4: Port the implementation test surface

1. Port applicable `.l0` implementation tests to `.l1` under `compiler/stage2_l1/tests/` and update imports to the Stage
   2 production root.
2. Adapt the normal and trace runners so `.l1` tests are compiled and run by `l1c-stage2`, while Python integration
   tests receive a sanitized repo-local L1 environment.
3. Port CLI, diagnostics, backend, interface, runtime, ARC, cleanup-policy, and compiler-library coverage.
4. Add focused Stage 1 and Stage 2 parity coverage over accepted and rejected fixtures, including exit status,
   diagnostic codes, diagnostic messages, CLI help/version behavior, and representative generated-program behavior.
5. Keep the Stage 1 suite intact and continue running it through the explicit upstream L0 bootstrap contract.
6. Preserve the existing default versus slow trace-test split unless Stage 2 measurements justify a separately reviewed
   adjustment.

### Phase 5: Establish strict triple-bootstrap validation

1. Build the first Stage 2 compiler through trusted Stage 1 with retained C enabled in an isolated build directory.
2. Use the first Stage 2 compiler to build the second Stage 2 compiler from the committed Stage 2 source tree.
3. Use the second Stage 2 compiler to build the third Stage 2 compiler from the same source tree.
4. Compare second and third retained C byte-for-byte on every supported host compiler.
5. Pin one host C compiler and append deterministic compiler/linker flags before native comparison.
6. Compare normalized second and third native artifacts on stable toolchains. Keep the existing documented exceptions:
   retain the C comparison but skip native identity for `tcc` and for Windows PE output.
7. Run `--version` and a normal example through the third compiler after identity checks succeed.
8. Keep compact logs, hashes, sizes, and a short retained-C diff on failure. Clean successful artifacts unless the
   caller requests retention.

### Phase 6: Integrate Stage 2 into L1 development

1. Add the new build, stage-selection, normal-test, trace-test, and triple-test targets to the L1 Makefile and help
   output.
2. Make `check-examples` use Stage 2 directly and include Stage 1 plus Stage 2 validation in `test-all`.
3. Extend the L1 CI matrix to build and test Stage 2 on the currently supported Linux, macOS, and Windows paths, with
   slow trace coverage remaining opt-in.
4. Update [l1/docs/reference/architecture.md][architecture], [l1/docs/project-status.md][project-status],
   [l1/docs/roadmap.md][roadmap], the L1 README, and level-local contributor guidance to describe the implemented stage
   structure and commands.
5. Keep stable docs phrased as current behavior: do not describe Stage 2 as implemented until the implementation and
   validation land.

## Diagnostics

1. This port is not expected to add or reassign compiler diagnostic codes.
2. Stage 2 must reuse Stage 1 codes and messages for equivalent conditions.
3. If the bootstrap exposes a genuine Stage 1 semantic defect, fix and register it through the normal Stage 1-first
   process before porting the behavior to Stage 2.
4. If implementation discovers a Stage 2-only failure mode with no Stage 1 equivalent, update this plan and re-check
   `docs/specs/compiler/diagnostic-code-catalog.md` before assigning a code.

## L1-Native Follow-Up Queue

The initial port deliberately leaves L1-only source improvements out of scope. After the fixed point is established,
spawn focused follow-up plans in this order where the change remains worthwhile:

1. Replace simple enum ordinal comparisons with `is(value, Variant)`. The pre-port audit found roughly 495
   `ord(...kind...)` comparisons across the compiler.
2. Convert long state and AST constructors to named arguments, especially `Backend`, `CliOptions`, `ParserState`,
   `ExprNode`, `StmtNode`, `ModuleEnv`, and `ExpressionTypeChecker` initialization.
3. Replace sentinel functions and mutable constant-like top-level bindings with typed `const` declarations.
4. Add explicit export manifests plus selective or aliased imports around the decomposed compiler subsystems.
5. Replace L0-driven arithmetic bitwise emulation with guarded native bitwise operators and use `uint` or `ulong` for
   hashes, fingerprints, masks, and ABI calculations where their widths match the contract.
6. Use fixed-size arrays and current non-owning slices for genuinely bounded local and parameter APIs. Do not treat the
   current `T[]` surface as a replacement for dynamic `StringVector*` or `VectorBase*` storage: slices cannot currently
   escape or borrow dynamic vector backing.
7. Revisit lexer, parser, demangler, module-path, and numeric-text allocation after the cheap ARC-backed string-slice
   feature lands.
8. Treat generics as the major future route to typed vectors, maps, sets, arenas, and result types that remove
   `VectorBase*`, `void*`, manual element-size bookkeeping, and repeated casts.
9. Use function pointers, future closures, or unsafe specialized buffers only where architecture or profiling shows a
   concrete benefit.

Each follow-up must preserve Stage 1 behavior through parity tests. L1-native implementation divergence does not make
Stage 2 authoritative for language semantics or diagnostics.

## ADR Impact

- Decision: Treat L1 Stage 1 as the bootstrap entrypoint and behavioral oracle for a mechanical initial Stage 2 port.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0001-two-stage-architecture.md`
  - Rationale: ADR-0001 already establishes the two-stage bootstrap relationship and Stage 2 parity obligation.

## Non-Goals

1. Adding or redesigning an L1 language feature to make the first self-host possible.
2. Performing the L1-native follow-up queue before this plan closes.
3. Completing separate compilation, interface fingerprint verification, multi-CU linking, or external-library linking.
4. Adding full C FFI, generics, closures, address-of, dynamic buffers, or general borrow/lifetime analysis.
5. Redesigning the AST, semantic pipeline, backend, ARC model, runtime ABI, or generated C during the initial port.
6. Adding L1 install, distribution, release, or docs-publishing workflows.
7. Requiring permanent textual identity between Stage 1 and Stage 2 sources after the initial snapshot.
8. Requiring broad Stage 1 versus Stage 2 generated-C byte identity when observable behavior remains equivalent.

## Verification Criteria

The plan closes only when all of the following are true:

01. `make -C l1 test-stage1` and the default Stage 1 trace suite remain green after the source snapshot.
02. `make -C l1 build-stage2` produces runnable Stage 2 wrapper and native artifacts under `L1_BUILD_DIR`.
03. `l1c-stage2 --check -Rp compiler/stage2_l1/src l1c` succeeds.
04. `make -C l1 test-stage2` passes the complete ported normal test surface.
05. `make -C l1 test-stage2-trace` passes the default Stage 2 trace surface without ARC or memory leaks.
06. Focused parity tests confirm matching Stage 1 and Stage 2 CLI behavior, diagnostics, and representative accepted and
    rejected program behavior.
07. `make -C l1 triple-test` reaches byte-identical retained C for the second and third self-builds, applies the
    documented native-identity platform policy, and passes the final smoke run.
08. `make -C l1 check-examples` passes every `.l1` example through Stage 2 without warnings or errors.
09. `make -C l1 test-all` passes locally, and `make -C l1 test-docker` passes when runtime, build-driver, or Linux
    portability paths changed.
10. The L1 CI matrix passes on its supported hosts and compiler selections.
11. The roadmap, project status, architecture reference, README, Stage 2 README, and contributor guidance describe the
    implemented workflow consistently.
12. No generated source, retained C, native probe, or temporary bootstrap artifact is committed.

## Assumptions and Dependencies

1. The Stage 1 source-decomposition plan lands first and does not intentionally change language semantics, ABI,
   diagnostics, runtime behavior, or bootstrap contracts.
2. The existing L1 runtime archives and L1 stdlib remain sufficient to build the compiler workload.
3. Stage 1 continues to build through the explicit upstream L0 Stage 2 contract documented by the L1 subtree.
4. The current whole-program C99 backend remains acceptable for the initial Stage 2 compiler workload.
5. Separate-compilation and productization plans may proceed independently, but this plan does not depend on them.

[architecture]: ../../../l1/docs/reference/architecture.md
[l0-triple-bootstrap]: ../../../l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md
[project-status]: ../../../l1/docs/project-status.md
[roadmap]: ../../../l1/docs/roadmap.md
[stage1-decomposition]: ../../../l1/work/plans/refactors/2026-07-08-stage1-source-decomposition-noref.md
[two-stage-architecture]: ../../../docs/decisions/0001-two-stage-architecture.md
