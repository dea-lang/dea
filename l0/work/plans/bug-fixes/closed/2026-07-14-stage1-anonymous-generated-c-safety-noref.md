# Bug Fix Plan

## Secure Stage 1 anonymous generated C

- Date: 2026-07-25
- Status: Completed
- Title: Harden the L0 Stage 1 anonymous generated-C temporary lifecycle
- Kind: Bug Fix
- Severity: High
- Stage: Stage 1
- Subsystem: Compiler driver / Temporary generated C
- Modules:
  - `l0/compiler/stage1_py/l0c.py`
  - `l0/compiler/stage1_py/l0_diagnostics.py`
  - `l0/docs/specs/compiler/stage1-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_l0c_assumptions.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
- Related:
  - [`work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md`][native-safety]
  - [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostic-catalog]
- Repro: replace the path returned by Stage 1 `tempfile.mktemp()` with a dangling symlink before `Path.write_text()`;
  the generated-C write follows the link and creates or truncates the target

## Summary

L0 Stage 1 selected an anonymous generated-C name with deprecated `tempfile.mktemp()` and later opened that name for
writing. Name selection did not reserve a filesystem object. A dangling symlink at the selected path therefore appeared
absent to the selection check but redirected the later generated-C write into its target.

This fix replaces the demonstrated L0 Stage 1 path-selection defect and rejects untrusted POSIX temporary-directory
chains before any compiler temporary is created. Anonymous generated C is atomically created with
`tempfile.mkstemp(dir=<validated-directory>)`, written as UTF-8 through the returned descriptor, and closed before the
host C compiler is invoked. Caller-selected retained C keeps its existing path and retention behavior.

Anonymous-source cleanup is part of the build result. A removal failure reports the retained path with `L0C-9512` and
returns failure instead of being swallowed. If host compilation already produced a caller-visible build executable, that
executable is retained. A setup or write failure followed by cleanup failure reports both `L0C-9511` and `L0C-9512`.

The corresponding native L0 Stage 2 and L1 Stage 1 build/run defects are not part of this completed L0-local plan. They
remain actively tracked by the shared [native temporary-workspace safety plan][native-safety].

## Implemented Invariant

01. L0 Stage 1 never uses `tempfile.mktemp()` for anonymous generated C.
02. On POSIX, Stage 1 resolves the selected temporary directory and validates every directory from that resolved path
    through the filesystem root before creating an anonymous source or a `--run` executable.
03. Every validated POSIX directory is owned by the effective user or root. A group- or other-writable directory must
    also have the sticky bit. Failure reports `L0C-9511` and does not invoke the host compiler.
04. Windows retains the documented assumption that the selected temporary directory is protected by trusted ACLs.
05. The validated resolved directory is passed explicitly to `tempfile.mkstemp()`, and the temporary source path is
    reserved atomically before generated content is written.
06. Generated C is written through the descriptor returned by `mkstemp()` with explicit UTF-8 encoding. The descriptor
    is closed before the host compiler receives the temporary path, and POSIX creation retains owner-only permissions.
07. Build success, compiler discovery failure, runtime-library validation failure, and C compilation failure all attempt
    to remove the anonymous generated-C file.
08. A successful cleanup removes the anonymous source. Cleanup failure reports `L0C-9512` with the retained path and
    makes the build fail, including when host compilation succeeded.
09. Temporary creation or write failure reports `L0C-9511` and does not invoke the host compiler. If cleanup of a
    reserved path also fails, `L0C-9512` is reported as a second diagnostic.
10. A caller-visible executable successfully produced before anonymous-source cleanup failure is retained.
11. `--keep-c` continues to use and retain the caller-selected C path. `--run` validates the temporary parent before it
    creates its anonymous executable even when retained C means no anonymous source is needed.
12. Apart from the pre-creation trust check, the existing `--run` temporary-executable lifecycle is unchanged.

## Implementation

1. Resolve the selected temporary directory on POSIX and validate its ownership and sticky-bit trust chain. Reuse this
   check before `cmd_run()` creates its anonymous executable. Keep the Windows trusted-ACL assumption explicit.
2. Create anonymous `.c` through `tempfile.mkstemp(dir=<validated-directory>)`.
3. Wrap the returned descriptor with `os.fdopen(..., encoding="utf-8")`, write generated C through that stream, and
   close it before returning the path.
4. If descriptor wrapping or writing fails, close any still-owned descriptor, attempt to remove the reserved path, and
   preserve both the primary failure and any cleanup failure for `cmd_build()`.
5. Have `cmd_build()` report `L0C-9511` for unsafe temporary-parent selection or anonymous temporary-source creation or
   write failure.
6. Make temporary-source cleanup result-bearing. Report `L0C-9512` and the retained path on removal failure, return
   nonzero, and do not remove a successfully produced caller-visible executable.
7. Preserve retained-C overwrite behavior and the existing run-executable cleanup lifecycle.
8. Re-check the shared catalog, register the confirmed-unused `L0C-9512` in the Stage 1 CLI diagnostic family, and
   update its canonical meaning.

## Focused Regression Coverage

01. Accept an effective-user-owned `0700` temporary directory and trusted sticky writable hierarchy.
02. Reject a direct or ancestor `0777` non-sticky directory with `L0C-9511` and prove the fake host compiler is not
    invoked.
03. Observe that the resolved validated directory is passed explicitly to `mkstemp()` and generated C is written through
    `os.fdopen()` with UTF-8 encoding.
04. Inspect the generated C while the fake host compiler runs, verify owner-only POSIX mode, and verify cleanup after
    success.
05. Verify cleanup after host C compiler failure.
06. Force temporary creation and descriptor-wrapping failures, assert `L0C-9511`, and verify that reserved files and
    descriptors are cleaned.
07. Inject removal failure after compiler success, compiler failure, and source-write failure. Verify the retained-path
    `L0C-9512` diagnostic and nonzero status; verify the write-failure case reports both codes.
08. Present a dangling symlink as the first temporary-name candidate and verify atomic creation treats it as a
    collision, leaves its target untouched, and selects a different reserved path.
09. Verify `--keep-c` retains its caller-selected C path while `--run` still rejects an unsafe temporary parent before
    creating the anonymous executable.
10. Verify the CLI diagnostic registry and shared catalog include both `L0C-9511` and `L0C-9512`.

## Non-Goals

1. Changing native L0 Stage 2 or L1 Stage 1 temporary-stem behavior.
2. Changing retained-C paths or the current `--run` temporary-executable lifecycle.
3. Adding a public `std.fs`, `sys.rt`, runtime, or language API.
4. Defending against same-authority mutation, administrative access, unusual ACL grants, hostile mount behavior,
   recursive deletion, crash recovery, or durability.
5. Auditing Windows ACLs beyond the documented trusted-temporary-parent assumption.

## Outcome

Implemented 2026-07-26.

- L0 Stage 1 validates the resolved POSIX temporary-directory trust chain before anonymous source or run-executable
  creation, then descriptor-creates anonymous generated C in that validated directory.
- Anonymous source cleanup covers successful and failed host compilation plus temporary-source setup failures. Failure
  reports `L0C-9512` and the retained path instead of being swallowed.
- The implementation-time catalog re-check on 2026-07-26 confirmed `L0C-9512` was unused before assignment.
- Retained C and, apart from the trust check, the existing `--run` temporary-executable behavior are unchanged.
- Native L0 Stage 2 and L1 Stage 1 hardening remain open under the shared follow-up plan.

Validation:

- `../.venv/bin/python -m pytest -q compiler/stage1_py/tests/cli/test_l0c_assumptions.py compiler/stage1_py/tests/diagnostics/test_diagnostic_codes.py`
  from `l0/` (`309 passed`)
- `make test-stage1` from `l0/` (`1431 passed`)

[diagnostic-catalog]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[native-safety]: ../../../../../work/plans/bug-fixes/2026-07-25-shared-native-compiler-temporary-workspace-safety-noref.md
