# Bug Fix Plan

## Improve temporary-directory trust diagnostics

- Date: 2026-10-03
- Status: Completed
- Title: Preserve temporary-directory trust failure details
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1
  - L0 Stage 2
  - L1 Stage 1
  - L1 Stage 2
- Origin: L0 compiler filesystem validation
- Porting rule: Preserve equivalent native failure details across both levels and L1 stages.
- Target status:
  - L0 Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
  - L1 Stage 2: Implemented
- Subsystem: Compiler temporary-directory validation and diagnostics
- Modules:
  - `l0/compiler/stage1_py/l0_cli_build.py`
  - `l0/compiler/stage2_l0/src/compiler_filesystem.l0`
  - `l0/compiler/stage2_l0/support/compiler_filesystem.c`
  - `l1/compiler/stage1_l0/src/compiler_filesystem.l0`
  - `l1/compiler/stage1_l0/support/compiler_support.c`
  - `l1/compiler/stage2_l1/src/compiler_filesystem.l1`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage2_l0/tests/compiler_filesystem_support_test.py`
  - `l0/compiler/stage2_l0/tests/build_driver_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_support_test.py`
  - `l1/compiler/stage1_l0/tests/compiler_filesystem_test.l0`
  - `l1/compiler/stage2_l1/tests/compiler_filesystem_test.l1`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_workspace_test.py`

## Summary

Preserve the rejected directory and failed requirement through Python and native compiler drivers. Ownership failures
report the observed owner UID, effective UID, and requirement for ownership by root or the effective account.
Distinguish canonicalization, inspection, non-directory, and missing-sticky-bit failures without changing trust
decisions or diagnostic codes. Native Windows failures retain the failing operation and unsigned error code across
handle cleanup while preserving the trusted-ACL assumption.

## ADR Impact

- Decision: Preserve the existing temporary-parent ownership and permission policy.
  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0020-native-compiler-private-temporary-workspaces.md`
  - Rationale: Failure reporting and portability documentation refine the existing policy without adding exceptions.

## Implementation

- Preserve structured caller-owned native inspection results; format diagnostics in Dea without repeating inspection.
- Preserve Python validation exceptions through build/run reporting.
- Capture the failing Win32 operation and `GetLastError()` immediately in the caller-owned snapshot. Preserve the
  primary cause across cleanup and distinguish non-directories, allocation/retry failures, and close-only failures.
- Run portable snapshot API tests on every host, with separate POSIX ownership simulation and Win32 fault injection.
- Retain Python L0C-9511 and native L0C-9513/L1C-9513; no new codes or reassignment.
- Document conservative rejection of remapped ownership and why changing TMPDIR cannot repair rejection of root.
- Exclude temporary-file I/O redesign, unrelated path inspection APIs, cloud execution instructions, bypass switches,
  UID exceptions, and namespace-specific policy changes.

## Outcome

All four targets retain the original ownership, sticky-bit, selection, and diagnostic-code policies. Python preserves
validation exceptions in build/run diagnostics. Native drivers read caller-owned inspection snapshots and format errors
in Dea; snapshot field retrieval never re-inspects the filesystem. Unsigned UIDs are transported as decimal strings to
avoid narrowing them to Dea integers. The legacy raw resolver remains available with its original return convention.

The shared CLI and Python Stage 1 contracts document conservative rejection of remapped ownership and the root-ancestor
limitation. No cloud execution instructions or trust bypasses were introduced.

Native Windows failures preserve the operation and unsigned error code captured before handle cleanup, which can replace
the thread's last error even when cleanup succeeds. An earlier failure takes precedence over cleanup failure; non-API
failures carry no stale Windows error. Dea formats equivalent evidence in all three native compiler targets.

## Verification

Validation used `/usr/bin/clang`, Apple Clang 17, on macOS, with `L0_CC=clang`, `L1_CC=clang`, and
`L1_RUNTIME_CC=clang`. The extended cross-level tier and focused L1 trace checks cover the new snapshot allocation,
string-copy, and release paths.

- Root `make clean test-extended`: passed. L0 completed 1,569 Python tests, 58 native tests including triple bootstrap,
  34 trace checks, eight examples, and workflow/distribution checks. L1 completed 79 Stage 1 and 65 Stage 2 normal
  tests, stage parity, four examples, six Docker/Wine runner tests, and 18 tooling/bootstrap-identity tests.
- `make -C l1 test-stage1-trace test-stage2-trace TESTS=compiler_filesystem_test`: passed in both stages with zero
  leaked objects and strings.
- Both native `compiler_filesystem_support_test.py` snapshot harnesses compiled with `-fsanitize=address` and
  `-fno-omit-frame-pointer`: passed.
- Regression coverage simulates rejected root, intermediate, and selected directories, including UID 65534 and unsigned
  UID 4294967295, without changing real filesystem ownership. It checks inspection/type/sticky-bit failures, valid root
  and effective-account ownership, stable bounded snapshot fields, and build/run rejection before scratch creation or
  application C compilation. Python includes run with retained C.
- Both native support harnesses exercise portable canonicalization, missing/non-directory parents, buffer boundaries,
  invalid input, and snapshot fields after directory removal. Only synthetic UID/sticky-bit tests skip Windows. Separate
  Win32 fault tests cover access denied, missing paths, inspection, canonicalization, unsigned error codes, allocation,
  retry exhaustion, and cleanup precedence. Expected paths use native separators even when MSYS2 Python supplies POSIX
  spelling.
- Windows binaries passed in the existing local Wine/MSYS2 environment with `gcc.exe` 16.2.0 and Windows Python
  (`os.name == "nt"`). Both complete support harnesses passed. L0 `build_driver_test` and L1 Stage 1
  `compiler_filesystem_test`, generated with Python L0 `--gen`, compiled and ran against their real Win32 support.
  Missing-parent assertions verified the path, operation, and error code in the compiler diagnostic.
- The same Windows Dea tests passed with `-DL0_TRACE_ARC -DL0_TRACE_MEMORY`; `check_trace_log.py` reported zero errors
  and warnings for both. These are Wine-hosted Windows-binary results, not native Windows CI or Windows self-bootstrap
  results. The committed tests remain enabled for the repository's Windows CI lanes.
- ADR impact validation, staged whitespace checks, and root pre-commit hooks: passed.

Reproduce the focused Windows checks with both `compiler_filesystem_support_test.py` scripts under Windows Python and
MinGW GCC. Generate the two Dea tests using `l0/scripts/l0c --gen` with their compiler source and test directories as
`-Rp` roots. Compile each generated C file with its native support C file and `-I l0/compiler/shared/runtime`, run it,
then repeat with the trace defines and analyze stderr using `l0/compiler/stage2_l0/scripts/check_trace_log.py`.

Completed validation is reused through documentation-only finalization and consolidation; compiler, test, build, and
toolchain inputs remain unchanged.
