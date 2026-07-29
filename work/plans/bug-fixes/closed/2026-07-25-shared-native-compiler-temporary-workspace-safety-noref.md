# Bug Fix Plan

## Secure native compiler temporary workspaces

- Date: 2026-07-29
- Status: Completed
- Title: Replace unreserved native compiler temporary stems with private workspaces
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 2 self-hosted compiler
  - L1 Stage 1 L0 bootstrap compiler
- Origin: L0 Stage 2 self-hosted compiler
- Porting rule: Settle the native workspace lifecycle in L0 Stage 2, then port it mechanically to L1 Stage 1 except
  where L1's implemented compile-only publication path requires an intentional documented divergence.
- Target status:
  - L0 Stage 2 self-hosted compiler: Completed
  - L1 Stage 1 L0 bootstrap compiler: Completed
- Subsystem: Compiler driver / Temporary workspace lifecycle
- Modules:
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l0/compiler/stage2_l0/src/compiler_filesystem.l0` (new)
  - `l0/compiler/stage2_l0/support/compiler_filesystem.c` (new)
  - `l0/compiler/stage2_l0/scripts/run_test_trace.py`
  - `l0/compiler/stage2_l0/scripts/run_trace_tests.py`
  - `l0/compiler/stage2_l0/scripts/test_runner_common.py`
  - `l0/scripts/build_stage2_l0c.py`
  - `l0/scripts/gen_dist_tools.py`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0` (new)
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
  - `scripts/shuffle_sources.py`
  - `scripts/validate_architectural_decision_audit.py`
  - `work/audits/architectural-decisions/2026-07-26/audit-manifest.md`
- Test modules:
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/compiler_filesystem_support_test.py` (new)
  - `l0/compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py`
  - `l0/tests/test_shuffle_sources.py`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compile_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_test.l0` (new)
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_workspace_test.py` (new)
- Related:
  - [`l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`][stage1-fix]
  - [`work/plans/bug-fixes/closed/2026-07-21-shared-structured-c-source-input-noref.md`][structured-input]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`][standalone-link]
  - [`l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]
  - [`l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`][publication-adr]
  - [`docs/decisions/0020-native-compiler-private-temporary-workspaces.md`][workspace-adr]
- Repro: reserve or replace a path selected by `bd_temp_stem()` after its `exists()` checks but before the native
  compiler creates generated C, compiler captures, driver-selected scratch artifacts, or a run executable

## Summary

L0 Stage 2 and L1 Stage 1 derive predictable PID/time/counter temporary stems, check a fixed set of derived paths with
`exists()`, and create or execute those paths later. The selection does not reserve a filesystem object, retains an
unchecked fallback after collision exhaustion, and leaves driver-selected scratch artifacts as unreserved siblings
rather than children of an invocation-owned directory.

The completed [L0 Stage 1 fix][stage1-fix] removed the demonstrated Python `mktemp()` defect, validates the resolved
POSIX temporary-directory trust chain, and makes anonymous-source cleanup failure result-bearing. L1 compile-only is
independently protected by its output-local transaction directory and endpoint rollback.

This plan replaced the native `bd_temp_stem()` lifecycle in both targets. Native `--build` and `--run` now validate the
selected temporary parent, reserve one command-owned private workspace atomically, keep every driver-selected scratch
path beneath it, and perform bounded, result-bearing cleanup.

## Dependencies and Ownership

1. The [structured C-source-input plan][structured-input] landed before L0 Stage 2 gained its dedicated support
   translation unit. `l0/scripts/build_stage2_l0c.py` passes that unit through structured `--c-source`, not through
   whitespace-split `L0_CFLAGS`.
2. This plan owns the native L0 Stage 2 and L1 Stage 1 build/run workspace lifecycle.
3. The completed [L1 compile-only plan][compile-only] owns its same-parent staging and endpoint-rollback publication
   path and remains explicitly separate from this plan.
4. The shared workspace abstraction owns temporary-parent selection, exclusive reservation, child registration, and
   bounded cleanup. L1 build/run multi-translation-unit orchestration must use that abstraction, while its
   [build/run plan][build-run] owns which per-module artifacts it registers and which generated-C outputs it retains.
5. Standalone L1 `--link` is not blocked by this plan. Its [link-set plan][standalone-link] owns a bounded transaction
   beside the mandatory output path and supplies explicit wrapper scratch paths to the common link executor.

## Current Defect

1. Candidate checks and later file creation are separate operations.
2. Any concurrent process able to write the shared temporary root can claim a checked path before generated C, output
   captures, driver-selected intermediate outputs, or the run executable is created.
3. The fixed fallback returned after collision exhaustion is not checked or reserved.
4. Related files are siblings in a shared temporary root rather than children of one invocation-owned directory.
5. Cleanup has no owned directory whose unexpected contents can be detected and retained for inspection.

## Required Contract

01. The command-level `bd_cmd_build()` and `bd_cmd_run()` flows each own exactly one workspace for the complete native
    operation. They create it after CLI, source, and entry-point validation, pass it through subordinate compile/link
    helpers, keep it alive through child execution for `--run`, and release it from one command epilogue. A subordinate
    helper must not create or independently clean a second build/run workspace.
02. L0 Stage 2 defines the shared workspace lifecycle first; L1 Stage 1 preserves the same observable safety contract.
03. Temporary-parent selection preserves the existing precedence: `TMPDIR`, `TEMP`, `TMP`, `/tmp`, then `.`. An absent,
    nonexistent, or non-directory candidate falls through to the next candidate. A filesystem inspection error is fatal.
    Once an existing directory is selected, canonical resolution or trust-validation failure is fatal and must not fall
    through to a later root.
04. Workspace creation uses the selected parent's canonical resolved path. On POSIX, validate every directory through
    the filesystem root: each component must be owned by the effective user or root, and each group- or other-writable
    component must have the sticky bit. Workspace and fixed-child path construction follows actual-host separator
    semantics, including treating a trailing `\` in a POSIX parent name as a literal byte. Reject failure before
    invoking the host compiler.
05. POSIX versus Windows trust behavior follows the actual compiled host, not `L0_PLATFORM`, `L1_PLATFORM`, or another
    target-behavior test alias. POSIX requests workspace mode `0700`; MinGW uses the repository's native
    directory-creation path and retains the trusted-ACL assumption for the selected temporary parent.
06. The containment guarantee covers every scratch path selected or explicitly supplied by the driver: generated C,
    compiler stdout/stderr captures, temporary objects and interfaces, generated wrappers, and temporary run
    executables. Those paths remain beneath the workspace unless a public option explicitly selects a retained output.
07. The driver does not change the host compiler's current directory, rewrite process temporary-directory environment
    variables, normalize arbitrary user-supplied path-bearing C options, or claim containment of auxiliary files that
    the host compiler invents independently. An unexpected object that does appear inside the workspace prevents
    empty-directory cleanup and causes retention; artifacts created elsewhere solely by host-compiler behavior are
    outside this contract.
08. `--keep-c` and caller-selected build outputs preserve their documented external paths and overwrite/error behavior.
    A successfully produced retained output remains available when later workspace cleanup fails.
09. Normal success, compiler discovery failure, compile/link failure, launch failure, validation failure, and a nonzero
    child-program result use one idempotent cleanup path.
10. Cleanup failure always reports `L0C-9514` or `L1C-9514` with the retained workspace path. It changes a successful
    primary result to status 1; when compilation, launch, or the child program already produced a failure or nonzero
    status, that primary status is preserved.
11. Cleanup removes only registered regular children and then the empty owned directory. A workspace that cannot be
    cleaned completely is retained for manual inspection; cleanup never follows a substituted symlink or reparse-point
    directory.
12. L1 compile-only keeps its existing same-parent staging, sequential publication, endpoint rollback, and recovery
    semantics rather than being routed through the global native build/run workspace.

## Implementation Approach

1. Add a compiler-private `compiler_filesystem.l0` module to each target. Move L1's reusable filesystem declarations,
   result constants, and thin wrappers out of `compile_driver.l0` so compile, build, and link code depend on one
   internal wrapper API rather than on one another for filesystem operations.
2. Keep the raw-byte C ABI primitive and policy-free: canonical temporary-parent resolution and trust validation,
   actual-host child path construction, exclusive directory creation, no-follow path classification, and empty-directory
   removal. Workspace naming, collision retry, child registration, diagnostics, cleanup ordering, and result precedence
   stay in Dea.
3. Add L0's primitive implementation in `support/compiler_filesystem.c` and pass it from
   `l0/scripts/build_stage2_l0c.py` through structured `--c-source`. L1 may retain the primitive implementation in its
   existing `support/interface_fingerprint.c` translation unit for this bounded fix; the new Dea module owns the
   compiler-facing abstraction regardless of that C filename.
4. Preserve the current temporary-parent candidate precedence, then resolve and validate the first existing directory
   before replacing `bd_temp_stem()` with a command-owned invocation workspace and fixed or registered child paths.
5. Route compiler captures, generated C, intermediate objects and interfaces, build/run link wrappers, and run
   executables selected by the driver through that workspace. Do not change the host compiler's current directory or
   process temporary-directory environment as part of this fix.
6. Make cleanup state explicit and idempotent. Remove only registered regular children and the empty owned directory;
   retain and report unexpected contents instead of recursively deleting them, then apply the required primary-result
   precedence.
7. Port the settled lifecycle to L1 Stage 1 without adding a public Dea runtime or standard-library API. Future L1
   multi-translation-unit build/run orchestration supplies its artifact registration and generated-C retention choices
   to this abstraction rather than defining another temporary-root policy.
8. Update native driver tests with deterministic candidate selection, collision, substitution, partial-setup,
   compiler-failure, launch-failure, child-status, cleanup-failure, and no-leftover coverage on POSIX and the supported
   MinGW environment.

## Threat Model

POSIX mode/ownership validation rejects every component not owned by the effective user or root and every group- or
other-writable component without the sticky bit. Exclusive directory creation removes the unchecked-name race, and
workspace mode `0700` prevents access by other accounts where filesystem permissions are enforced. Windows retains the
trusted-ACL assumption.

The plan does not claim containment against another process running with the same account, administrative access,
unusual ACL grants, hostile mount behavior, or another authority able to mutate the workspace. Stronger containment
would require handle- or directory-descriptor-relative child operations plus identity validation and is outside this
bounded fix. No-follow classification limits cleanup damage if a known child path is substituted; it is not a
same-authority security boundary.

The containment contract is limited to paths selected or explicitly supplied by the driver. It does not claim control
over arbitrary auxiliary files invented by a host compiler or requested solely through raw user C options. Preserving
the current child working directory and environment avoids changing the meaning of relative source paths, include paths,
response files, and other path-bearing compiler options.

## ADR Impact

- Decision: Give each command-level native build/run operation ownership of one atomically reserved private workspace
  through compilation, linking, optional execution, and one cleanup epilogue.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: The rule removes check-then-use stems and unchecked fallbacks, prevents split cleanup ownership, and
    keeps the `--run` executable alive for exactly the required lifetime.
- Decision: Preserve temporary-parent precedence and non-directory fallthrough, but make candidate inspection errors and
  canonical resolution or trust failure of the first existing directory fatal under the actual host's POSIX or Windows
  policy.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: The choice preserves environment compatibility without allowing an unsafe selected root to be hidden by a
    later fallback or by target-behavior platform aliases.
- Decision: Guarantee containment only for driver-selected scratch paths without changing the host compiler's current
  directory, temporary-directory environment, or arbitrary user C options.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: The boundary is portable and enforceable while preserving existing relative-path behavior and avoiding an
    unsupportable claim about independently invented host-compiler artifacts.
- Decision: Remove only known workspace children without following substitutions and retain and report any incompletely
  cleaned workspace, with cleanup failure overriding success but not an existing failure or child status.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: The bounded no-follow cleanup policy constrains failure handling, deliberately rejects recursive
    deletion, and reports residue without discarding a more meaningful primary result.
- Decision: Put the shared workspace mechanics behind compiler-private `compiler_filesystem.l0` modules backed by
  policy-free C primitives, while leaving artifact membership and retained-output choices to each operation's owner.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: The dependency direction lets compile, build, link, and future L1 multi-unit orchestration share
    reservation and cleanup without moving compiler policy into the C support ABI.
- Decision: Keep L1 compile-only publication on its output-local transaction and endpoint-rollback boundary rather than
  route it through the native build/run workspace.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 owns compile-only same-parent staging, endpoint rollback, recovery files, and external
    serialization.

## Diagnostic-Code Plan

The implementation-time catalog re-check assigned two nearby unused paired driver codes:

- `L0C-9513` / `L1C-9513`: native compiler temporary-parent inspection, workspace setup, parent-trust validation, or
  exclusive reservation failed.
- `L0C-9514` / `L1C-9514`: native compiler temporary workspace cleanup failed and the retained workspace path was
  reported.

`L0C-9511` / `L1C-9511` retain their existing meaning for actual output-file write failures. `L0C-9512` remains the
L0-only diagnostic for retained Stage 1 compiler-temporary source cleanup failure; it is not reused for the native
workspace lifecycle. No new diagnostic family or broad range is needed.

## Non-Goals

1. Changing compile-only artifact publication, endpoint rollback, or its trusted-parent and external-serialization
   boundary.
2. Defending caller-selected retained-output directories from hostile mutation during an invocation.
3. Simultaneous writers to the same public artifact stem, locking, crash recovery, `SIGKILL`, power-loss guarantees, or
   `fsync` durability.
4. Adding recursive general-purpose deletion, public filesystem APIs, or a process-wide Dea temporary-directory policy.
5. Capturing arbitrary auxiliary artifacts invented by a host compiler or requested solely by raw C options, changing
   the child working directory, redirecting its temporary-directory environment, or adding compiler-family-specific
   containment flags.
6. Routing MSVC-specific side artifacts outside the currently documented MinGW support environment.
7. Containing processes that run with the same authority as the compiler and can mutate its private workspace.
8. Replacing or relocating the standalone link mode's output-local transaction.

## Verification Criteria

01. No production native build/run path calls `bd_temp_stem()` or uses an unchecked temporary fallback.
02. Tests preserve `TMPDIR`, `TEMP`, `TMP`, `/tmp`, `.` precedence and non-directory fallthrough, while proving that a
    filesystem inspection error or canonical-resolution or trust failure for the first existing candidate is fatal
    rather than hidden by fallback.
03. Trusted owner-only and sticky-writable POSIX hierarchies are accepted; direct and ancestor non-sticky writable
    components are rejected without invoking the host compiler. These checks follow the actual host even when
    `L0_PLATFORM` or `L1_PLATFORM` selects different target behavior.
04. Workspace creation uses the resolved canonical parent. A pre-existing candidate is never reused, deterministic
    collision injection selects a separately reserved directory, and a POSIX parent ending in a literal `\` still owns
    the workspace rather than a sibling path.
05. Generated C, captures, objects, interfaces, build/run wrappers, and run executables selected by the driver remain
    inside the private workspace unless explicitly retained.
06. End-to-end tests use a controlled temporary parent and fake host compiler to cover success, compiler failure, and
    launch failure while proving the exact driver-selected scratch paths; they do not claim containment of arbitrary
    host-compiler auxiliary output.
07. Success and every ordinary failure path remove registered children without following substituted paths, then remove
    the empty workspace; unexpected contents are left untouched.
08. Cleanup failure reports `L0C-9514` or `L1C-9514` and the retained workspace path rather than deleting unknown
    contents. Inspection, setup, trust, and reservation failures report the paired `9513` code, while actual writes
    retain `9511`.
09. A cleanup failure changes primary success to status 1 but preserves a compile/launch failure or nonzero child
    status. Successfully retained caller-selected outputs remain in place.
10. Existing `--keep-c`, build-output, run-status, host-compiler output, and unrelated diagnostic behavior remains
    compatible.
11. L0 Stage 2 and L1 Stage 1 focused normal and trace tests cover the same lifecycle; platform aliases do not select
    host-filesystem trust behavior.
12. `make -C l0 test-all`, `make -C l1 test-all`, and root `make test-all` pass before the plan closes.

## Completion

1. L0 Stage 2 and L1 Stage 1 now use matching compiler-private filesystem modules for actual-host temporary-parent
   selection and trust, fixed-child path construction, exclusive workspace reservation, and bounded no-follow cleanup.
2. Command-level build/run ownership, containment limits, result precedence, and the paired `9513` / `9514` diagnostics
   are recorded in [ADR-0020][workspace-adr], the shared CLI contract, the diagnostic catalog, and both level
   architecture/contract references.
3. Compile-only publication and standalone linking retain their output-local transaction boundaries; their ADRs and
   completed plans now point to this completed shared lifecycle without inheriting it.
4. Root `make test-all` passed on 2026-07-29: L0 passed 1,447 Python tests, 55 Stage 2 tests, 8 examples, all workflow
   checks, and 33 default trace tests; L1 passed 66 Stage 1 tests, 4 examples, environment stackability, and 45 default
   trace tests.
5. Direct C ABI, Dea unit, and end-to-end tests cover POSIX trust, precedence, inspection errors, collisions, cleanup
   retention/status, and a canonical temporary parent ending in a literal `\`. The local host had no MinGW
   cross-compiler, so Windows behavior is covered by conditional source and direct ABI tests and still requires the
   supported MinGW CI lane for host-execution validation.
6. The architectural-audit manifest declares this closed plan and ADR-0020. Its validator accepts the manifest's
   mdformat-wrapped long path declarations, preserving strict formatting and exact current-tree reconciliation.

[build-run]: ../../../../l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: ../../../../l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[publication-adr]: ../../../../l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md
[stage1-fix]: ../../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
[standalone-link]: ../../../../l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[structured-input]: 2026-07-21-shared-structured-c-source-input-noref.md
[workspace-adr]: ../../../../docs/decisions/0020-native-compiler-private-temporary-workspaces.md
