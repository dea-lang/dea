# Bug Fix Plan

## Secure native compiler temporary workspaces

- Date: 2026-07-25
- Status: Draft
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
  - L0 Stage 2 self-hosted compiler: Pending
  - L1 Stage 1 L0 bootstrap compiler: Pending
- Subsystem: Compiler driver / Temporary workspace lifecycle
- Modules:
  - `l0/compiler/stage2_l0/src/build_driver.l0`
  - `l0/compiler/stage2_l0/support/compiler_filesystem.c` (new)
  - `l0/scripts/build_stage2_l0c.py`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
- Test modules:
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_lib_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/compiler_filesystem_support_test.py` (new)
  - `l1/compiler/stage1_l0/tests/build_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_lib_test.l0`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_workspace_test.py` (new)
- Related:
  - [`l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md`][stage1-fix]
  - [`work/plans/bug-fixes/2026-07-21-shared-structured-c-source-input-noref.md`][structured-input]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]
  - [`l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`][publication-adr]
- Repro: reserve or replace a path selected by `bd_temp_stem()` after its `exists()` checks but before the native
  compiler creates generated C, compiler captures, side artifacts, or a run executable

## Summary

L0 Stage 2 and L1 Stage 1 derive predictable PID/time/counter temporary stems, check a fixed set of derived paths with
`exists()`, and create or execute those paths later. The selection does not reserve a filesystem object, retains an
unchecked fallback after collision exhaustion, and cannot contain host-compiler side artifacts within an
invocation-owned directory.

The completed [L0 Stage 1 fix][stage1-fix] removed the demonstrated Python `mktemp()` defect, validates the resolved
POSIX temporary-directory trust chain, and makes anonymous-source cleanup failure result-bearing. L1 compile-only is
independently protected by its output-local transaction directory and endpoint rollback, but native `--build` and
`--run` still use `bd_temp_stem()`. This plan remains open until both native targets validate their temporary parent and
use an atomically reserved private workspace with bounded, tested cleanup.

## Dependencies and Ownership

1. The [structured C-source-input plan][structured-input] must land before L0 Stage 2 gains its dedicated support
   translation unit. `l0/scripts/build_stage2_l0c.py` must pass that unit through structured `--c-source`, not inject
   its path into whitespace-split `L0_CFLAGS`.
2. This plan owns the native L0 Stage 2 and L1 Stage 1 build/run workspace lifecycle.
3. The completed [L1 compile-only plan][compile-only] owns its same-parent staging and endpoint-rollback publication
   path and remains explicitly separate from this plan.
4. L1 build/run multi-translation-unit fan-out must use the workspace lifecycle settled here rather than define another
   temporary-root policy.

## Current Defect

1. Candidate checks and later file creation are separate operations.
2. Any concurrent process able to write the shared temporary root can claim a checked path before generated C, output
   captures, side artifacts, or the run executable is created.
3. The fixed fallback returned after collision exhaustion is not checked or reserved.
4. Related files are siblings in a shared temporary root rather than children of one invocation-owned directory.
5. Cleanup knows selected filenames but cannot reliably account for unexpected host-compiler side artifacts.

## Required Contract

1. Each native build/run invocation atomically creates one private workspace before deriving any temporary child path.
2. L0 Stage 2 defines the shared workspace lifecycle first; L1 Stage 1 preserves the same observable safety contract.
3. Before workspace creation on POSIX, resolve the selected temporary parent and validate every directory through the
   filesystem root. Each component must be owned by the effective user or root, and each group- or other-writable
   component must have the sticky bit. Reject failure before invoking the host compiler.
4. POSIX requests workspace mode `0700`. MinGW support uses the repository's documented native directory-creation path
   and retains the trusted-ACL assumption for the selected temporary parent.
5. Generated C, compiler stdout/stderr captures, temporary objects and interfaces, host-compiler side artifacts, and
   temporary run executables remain beneath the workspace unless a public option explicitly selects a retained output.
6. `--keep-c` and caller-selected build outputs preserve their documented external paths and overwrite/error behavior.
7. Normal success, compiler discovery failure, compile/link failure, launch failure, and validation failure use one
   idempotent cleanup path.
8. A workspace that cannot be cleaned completely is retained and reported with enough location information for manual
   inspection; cleanup never follows a substituted symlink or reparse-point directory.
9. L1 compile-only keeps its existing same-parent staging, sequential publication, endpoint rollback, and recovery
   semantics rather than being routed through the global native build/run workspace.

## Implementation Approach

1. After structured C-source input is available, add the smallest compiler-private raw-byte support translation unit
   needed for POSIX temporary-parent trust validation, exclusive directory creation, no-follow classification, and
   empty-directory cleanup in L0 Stage 2. Pass it from `l0/scripts/build_stage2_l0c.py` through `--c-source`.
2. Resolve and validate the temporary parent before replacing `bd_temp_stem()` build/run selection with an invocation
   workspace plus fixed child names.
3. Route compiler captures, generated C, intermediate objects, link wrappers, side artifacts, and run executables
   through that workspace.
4. Make cleanup state explicit and idempotent. Remove only known regular children and the empty owned directory; retain
   and report unexpected contents instead of recursively deleting them.
5. Port the settled lifecycle to L1 Stage 1, reusing its existing compiler filesystem support translation unit where
   appropriate without adding a public Dea runtime or standard-library API.
6. Update native driver tests with deterministic collision, substitution, partial-setup, compiler-failure,
   launch-failure, cleanup-failure, and no-leftover coverage on POSIX and the supported MinGW environment.

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

## ADR Impact

- Decision: Reserve one private native build/run workspace atomically before deriving any compiler-owned child path.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: The rule removes check-then-use stems and unchecked fallbacks across native compiler stages.
- Decision: Validate the complete POSIX temporary-parent ownership and sticky-bit chain while retaining the documented
  MinGW ACL assumption.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: Temporary-parent trust is a cross-stage portability and security boundary independent of workspace
    reservation.
- Decision: Remove only known workspace children without following substitutions and retain and report any incompletely
  cleaned workspace.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: The bounded no-follow cleanup policy constrains failure handling and deliberately rejects recursive
    deletion.
- Decision: Keep L1 compile-only publication on its output-local transaction and endpoint-rollback boundary rather than
  route it through the native build/run workspace.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: ADR-0022 owns compile-only same-parent staging, endpoint rollback, recovery files, and external
    serialization.

## Diagnostic-Code Plan

No new diagnostic family is expected. Reuse the established driver and output-write diagnostics, including `L0C-9511` /
`L1C-9511`, for unsafe temporary-parent selection or workspace creation/write failure when their meanings fit. The L0
Python Stage 1 cleanup fix assigned `L0C-9512` specifically to retained compiler-temporary source cleanup failure after
an implementation-time catalog re-check; that assignment is not a blanket workspace-cleanup code. If retained native
workspace state requires a distinct user-facing condition, select nearby unused paired driver codes only after
re-checking the live `docs/specs/compiler/diagnostic-code-catalog.md`; do not reserve a broad new range for this bounded
fix.

## Non-Goals

1. Changing compile-only artifact publication, endpoint rollback, or its trusted-parent and external-serialization
   boundary.
2. Defending caller-selected retained-output directories from hostile mutation during an invocation.
3. Simultaneous writers to the same public artifact stem, locking, crash recovery, `SIGKILL`, power-loss guarantees, or
   `fsync` durability.
4. Adding recursive general-purpose deletion, public filesystem APIs, or a process-wide Dea temporary-directory policy.
5. Routing MSVC-specific side artifacts outside the currently documented MinGW support environment.
6. Containing processes that run with the same authority as the compiler and can mutate its private workspace.

## Verification Criteria

01. No production native build/run path calls `bd_temp_stem()` or uses an unchecked temporary fallback.
02. Trusted owner-only and sticky-writable POSIX hierarchies are accepted; direct and ancestor non-sticky writable
    components are rejected without invoking the host compiler.
03. A pre-existing workspace candidate is never reused, and deterministic collision injection selects a separately
    reserved directory.
04. Generated C, captures, objects, interfaces, wrappers, side artifacts, and run executables remain inside the private
    workspace unless explicitly retained.
05. End-to-end tests use a controlled temporary parent and fake host compiler to cover success, compiler failure, and
    launch failure while proving side-artifact containment.
06. Success and every ordinary failure path remove known children without following substituted paths, then remove the
    empty workspace; unexpected contents are left untouched.
07. Cleanup failure retains and reports the workspace rather than deleting unknown contents.
08. Existing `--keep-c`, build-output, run-status, host-compiler output, and diagnostic behavior remains compatible.
09. L0 Stage 2 and L1 Stage 1 focused normal and trace tests cover the same lifecycle and platform aliases.
10. `make -C l0 test-all`, `make -C l1 test-all`, and root `make test-all` pass before the plan closes.

[build-run]: ../../../l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md
[compile-only]: ../../../l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md
[publication-adr]: ../../../l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md
[stage1-fix]: ../../../l0/work/plans/bug-fixes/closed/2026-07-14-stage1-anonymous-generated-c-safety-noref.md
[structured-input]: 2026-07-21-shared-structured-c-source-input-noref.md
