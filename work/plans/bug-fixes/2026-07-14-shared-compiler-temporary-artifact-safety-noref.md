# Bug Fix Plan

## Secure compiler temporary artifacts across active stages

- Date: 2026-07-14
- Status: Draft
- Title: Eliminate unreserved compiler temporary paths across L0 Stage 1, L0 Stage 2, and L1 Stage 1
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1 Python compiler
  - L0 Stage 2 self-hosted compiler
  - L1 Stage 1 L0 bootstrap compiler
- Origin: L0 Stage 1 Python compiler
- Porting rule: Establish the temporary-artifact security and lifecycle invariant in L0 Stage 1, add one internal L0
  runtime primitive for native temporary workspaces, then port the native driver lifecycle from L0 Stage 2 to L1 Stage 1
  with only compiler identity, diagnostic-code, and artifact-prefix differences.
- Target status:
  - L0 Stage 1 Python compiler: Pending
  - L0 Stage 2 self-hosted compiler: Pending
  - L1 Stage 1 L0 bootstrap compiler: Pending
- Subsystem: Compiler drivers / Temporary artifacts / L0 runtime I/O
- Modules:
  - [l0/compiler/stage1_py/l0c.py](../../../l0/compiler/stage1_py/l0c.py)
  - [l0/compiler/stage2_l0/src/build_driver.l0](../../../l0/compiler/stage2_l0/src/build_driver.l0)
  - [l1/compiler/stage1_l0/src/build_driver.l0](../../../l1/compiler/stage1_l0/src/build_driver.l0)
  - [l0/compiler/shared/l0/stdlib/sys/rt.l0](../../../l0/compiler/shared/l0/stdlib/sys/rt.l0)
  - [l0/compiler/shared/runtime/l0_runtime.h](../../../l0/compiler/shared/runtime/l0_runtime.h)
- Test modules:
  - [l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py](../../../l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py)
  - [l0/compiler/stage2_l0/tests/build_driver_test.l0](../../../l0/compiler/stage2_l0/tests/build_driver_test.l0)
  - [l0/compiler/stage2_l0/tests/l0c_build_run_test.py](../../../l0/compiler/stage2_l0/tests/l0c_build_run_test.py)
  - [l1/compiler/stage1_l0/tests/build_driver_test.l0](../../../l1/compiler/stage1_l0/tests/build_driver_test.l0)
  - [l1/compiler/stage1_l0/tests/l1c_lib_test.l0](../../../l1/compiler/stage1_l0/tests/l1c_lib_test.l0)
  - `l1/compiler/stage1_l0/tests/l1c_stage1_temp_workspace_test.py` (new)
- Related:
  - [docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md)
  - [docs/specs/compiler/diagnostic-code-catalog.md](../../../docs/specs/compiler/diagnostic-code-catalog.md)
  - [work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md](../features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md)
- Repro: replace the path returned by Stage 1 `tempfile.mktemp()` with a symlink before `Path.write_text()`; the symlink
  target is truncated and overwritten by generated C

## Summary

All three active compiler implementations use temporary artifacts during `--build` and `--run`, but two distinct
implementations currently select paths without securely reserving them:

- L0 Stage 1 calls Python's deprecated `tempfile.mktemp()` for generated C and later opens the returned path by name.
- L0 Stage 2 and L1 Stage 1 construct predictable PID/time/counter stems, check several derived paths with `exists()`,
  and later create or execute those paths. Neither native driver reserves the stem, and both return a fixed unchecked
  fallback after exhausting collision attempts.

A controlled Stage 1 probe demonstrated that replacing the selected path with a symlink before the write overwrites a
writable victim. The native pattern exposes generated C, compiler capture files, and temporary executables to the same
check-then-use class. The run-executable case additionally permits a platform/toolchain-dependent replacement race
between compilation and execution.

This plan establishes one shared rule: compiler-created temporary artifacts must live behind an atomic reservation, must
not follow attacker-substituted paths, must use restrictive access, and must be cleaned on every exit path.

## Current State

### L0 Stage 1 Python

- `cmd_build()` calls `tempfile.mktemp(suffix=".c")` when `--keep-c` is absent, then writes generated C with
  `Path.write_text()`.
- `mktemp()` returns a name without creating it. A controlled probe inserted a symlink in that gap and confirmed that
  the generated-C write followed the link and overwrote the victim.
- `cmd_run()` already creates its temporary executable with `NamedTemporaryFile(delete=False)`. That secure creation
  should be preserved; the confirmed Stage 1 defect is the non-retained generated-C path.
- Existing tests cover compiler arguments and basic `--keep-c` behavior, but not atomic creation, permissions, or
  cleanup on both compiler success and failure.

### L0 Stage 2 and L1 Stage 1

- Each native `bd_temp_stem()` combines a compiler prefix, tag, process id, wall-clock fields, and an attempt counter.
  It checks the stem plus `.c`, `.out`, `.exe`, `.stdout`, and `.stderr` with `exists()` and returns the
  still-unreserved stem.
- After 100 collisions, each driver returns a fixed `*-fallback` stem without checking or reserving it.
- `exists()` is backed by `stat`, so a dangling symlink can appear absent. Generated C is subsequently opened with
  `fopen(path, "wb")`, which follows symlinks and truncates its target.
- C compiler stdout and stderr are captured through shell redirection to the unreserved paths. The output executable is
  also compiler-created at an unreserved path, and `--run` later executes it by pathname.
- With normal permissive process umasks, native temporary files in a shared temp root can be readable by other users
  while they exist.
- L1 Stage 1 is implemented in L0 and imports L0 `sys.rt`; its bootstrap explicitly uses the L0 system root and runtime.
  A single internal L0 runtime facility therefore serves both native drivers.

## Security Impact and Severity

The demonstrated impact is local data-integrity loss: a process able to substitute the selected temporary path can
redirect generated compiler output into another file writable by the compiler process. The native capture paths add
temporary data-confidentiality concerns, and the native `--run` path admits a plausible replacement-before-execution
race whose exact exploitability depends on the host and C toolchain.

This plan does not claim demonstrated privilege escalation. Private default temp directories reduce ordinary cross-user
exposure on some hosts, but the compilers honor `TMPDIR`, `TEMP`, and `TMP`, and native drivers fall back to `/tmp` or
the working directory. Correctness cannot depend on every selected root already being private.

Severity is High because active compiler build/run paths can clobber unrelated writable files, may expose transient
compiler data, and in native `--run` mode may execute a substituted artifact.

## Root Cause

The drivers treat name uniqueness as equivalent to ownership. A prior `exists()` check—or a name generator that merely
looks unique—does not reserve a filesystem object. Another process can create or replace the object before the compiler
opens, redirects into, or executes it.

The native implementation also lacks an internal L0 runtime primitive for atomically creating a private temporary
workspace. That gap led both seeded native drivers to duplicate check-then-use stem logic and an unsafe fallback.

## Required Invariant

1. Every compiler-owned temporary C file, capture file, executable, or workspace is atomically created or placed inside
   an atomically created private workspace before use.
2. A pre-existing file, directory, or symlink is a collision or failure; it is never opened as the selected temporary
   artifact.
3. Descriptor-created Stage 1 temporary files use owner-only access, and native POSIX temporary workspaces use mode
   `0700`; Windows uses an equivalent atomic, private workspace creation path supported by the repository toolchains.
4. Collision exhaustion fails through a controlled compiler diagnostic. There is no unchecked fixed fallback.
5. Success, analysis failure, compiler discovery failure, C compilation failure, and program completion all clean up
   compiler-owned artifacts. Cleanup failures do not cause the driver to operate on a replacement path.
6. User-selected output and `--keep-c` paths retain their existing overwrite and retention semantics; they are not
   reclassified as anonymous compiler temporaries.

## Diagnostic-Code Plan

No new diagnostic-code reservation is expected.

- L0 Stage 1 and L0 Stage 2 should reuse `L0C-9511` for temporary creation or write failures.
- L1 Stage 1 should reuse the paired `L1C-9511` code.

If a genuinely distinct failure category emerges during implementation, re-check
[docs/specs/compiler/diagnostic-code-catalog.md](../../../docs/specs/compiler/diagnostic-code-catalog.md) before
choosing an unused code. The current plan does not provisionally reserve a new range.

## Implementation Approach

### Phase 1: Secure L0 Stage 1 generated C

1. Replace `tempfile.mktemp()` with `tempfile.mkstemp()` or an equivalently secure descriptor-returning API.
2. Write generated C through the returned descriptor with explicit UTF-8 encoding, then close it before invoking the C
   compiler so Windows toolchains can reopen the source path.
3. Preserve `--keep-c` handling for user-selected paths and preserve the securely created temporary executable in
   `cmd_run()`.
4. Simplify cleanup to an idempotent deletion in `finally` and cover compiler success, compiler failure, and early
   driver failures.

### Phase 2: Add an internal native temporary-workspace primitive

1. Add minimal internal extern/runtime operations under L0 `sys.rt` for atomic private-directory creation and empty
   directory removal, or one equivalent secure temporary-workspace operation.
2. On POSIX, use atomic exclusive directory creation with owner-only mode. On Windows, use the corresponding atomic
   directory-creation primitive and retain compatibility with the repository's supported C toolchains.
3. Define collisions as failure without following or accepting pre-existing objects. Do not perform an `exists()`
   precheck inside the primitive.
4. Keep the facility internal to the L0 compiler/runtime surface. Do not add parallel APIs to the L1 stdlib or split L1
   runtime: L1 Stage 1 is an L0 program and consumes the L0 implementation.

### Phase 3: Move native drivers into private workspaces

1. Replace `bd_temp_stem()` with a nullable temporary-workspace reservation helper.
2. Attempt candidate workspace names with the atomic runtime primitive. Retry collisions, but return failure after a
   bounded number of attempts instead of returning a fixed fallback.
3. Place generated C, compiler stdout/stderr captures, and temporary run executables inside the reserved workspace.
4. Emit `L0C-9511` or `L1C-9511` and stop before code generation output, redirection, or execution when reservation
   fails.
5. Clean known artifacts and then the workspace on every exit path. Retained C and explicit build outputs remain outside
   the workspace according to existing CLI semantics.
6. Settle this lifecycle in L0 Stage 2, then port it mechanically to L1 Stage 1 while preserving the respective
   `l0c-stage2` / `l1c-stage1` names and paired diagnostic codes.

### Phase 4: Add adversarial lifecycle coverage

1. Extend Stage 1 pytest coverage with a fake compiler that inspects the temporary C path during invocation, verifies
   restrictive POSIX permissions where applicable, and confirms cleanup after success and failure.
2. Add a controlled Stage 1 collision/substitution test that fails if generated C can be redirected through a symlink.
   Keep all victims and artifacts inside the test temporary directory.
3. Exercise the native runtime primitive directly: pre-existing file, directory, and symlink candidates must be
   rejected; successful POSIX workspaces must be mode `0700`.
4. Extend L0 Stage 2 build-driver and build/run integration tests with a controlled temp root. Assert workspace
   containment and cleanup after build success, C compiler failure, and run completion.
5. Apply equivalent unit and integration coverage to L1 Stage 1, including a focused discovered Python test for
   controlled `TMPDIR`, fake compiler behavior, cleanup, and unchanged `--keep-c` behavior.
6. Exercise the Windows implementation in the existing Windows workflow; do not treat POSIX-only permissions checks as a
   substitute for atomic Windows behavior.

## Non-Goals

1. Changing overwrite semantics for explicit `--output` or retained `--keep-c` paths chosen by the user.
2. Redesigning general-purpose `std.fs` APIs or exposing a new public temporary-file API to Dea programs.
3. Changing the L1 user-program stdlib or split L1 runtime.
4. Implementing L1 Stage 2, which is currently a placeholder. Its future compiler driver must inherit this invariant
   when
   [work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md](../features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md)
   is implemented.
5. Claiming protection against a process that already has authority to modify the compiler process or its genuinely
   private workspace.

## Verification Criteria

- L0 Stage 1 never calls `tempfile.mktemp()` and writes anonymous generated C through an atomically created descriptor.
- A controlled Stage 1 symlink-substitution probe cannot modify the victim file.
- L0 Stage 2 and L1 Stage 1 reserve private workspaces atomically, reject pre-existing candidates, and have no fixed
  unchecked fallback.
- Generated C, compiler capture files, and temporary run executables remain inside the reserved native workspace and are
  inaccessible to other POSIX users while live.
- No native driver redirects into or executes an unreserved compiler-owned temporary path.
- Compiler-owned temporary artifacts are removed after success, build failure, and run completion; retained C and
  explicit outputs remain as requested.
- Reservation failure reports `L0C-9511` / `L1C-9511` and performs no compile or run action.
- Focused validation passes:
  - `make -C l0 test-stage1`
  - `make -C l0 test-stage2 TESTS="build_driver_test l0c_build_run_test"`
  - `make -C l0 test-stage2-trace TESTS="build_driver_test"`
  - `make -C l1 test-stage1 TESTS="build_driver_test l1c_lib_test l1c_stage1_temp_workspace_test.py"`
  - `make -C l1 test-stage1-trace TESTS="build_driver_test l1c_lib_test"`
- The encompassing root validation required for compiler/runtime changes passes before finalization.
