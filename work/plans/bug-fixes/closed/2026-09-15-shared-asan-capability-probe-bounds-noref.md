# Bug Fix Plan

## Bound shared ASan capability probes without changing compiler identity

- Date: 2026-09-15
- Status: Completed
- Title: Bound shared ASan capability probes without changing compiler identity
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Stage 1 quarantine and Stage 2 vector ASan harnesses
  - L1 Stage 1 quarantine and vector ASan harnesses
- Origin: The macOS ARM64 GCC Unified CI job stalled in an empty ASan support executable until the six-hour job limit
- Porting rule: Settle one capability policy and apply the same explicit-selection, timeout, and non-PIE retry semantics
  mechanically across the L0 and L1 harness shapes.
- Target status:
  - L0 Stage 1 quarantine and Stage 2 vector ASan harnesses: Implemented and validated
  - L1 Stage 1 quarantine and vector ASan harnesses: Implemented and validated
- Subsystem: Test harnesses / AddressSanitizer capability detection / CI portability
- Modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_quarantine_asan.py`
  - `l0/compiler/stage2_l0/tests/vector_aliasing_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_quarantine_asan_test.py`
  - `l1/compiler/stage1_l0/tests/vector_aliasing_test.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_quarantine_asan.py`
  - `l0/compiler/stage1_py/tests/cli/test_asan_test_support.py`
  - `l0/compiler/stage2_l0/tests/vector_aliasing_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_quarantine_asan_test.py`
  - `l1/compiler/stage1_l0/tests/vector_aliasing_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md`
  - `work/plans/bug-fixes/closed/2026-09-01-shared-vector-aliased-byte-push-noref.md`
  - `l1/work/plans/bug-fixes/closed/2026-09-07-fingerprint-adapter-gcc-array-parameter-noref.md`
- Repro: Run the L0 `test-all` target with `L0_CC=gcc-15` on the macOS ARM64 hosted runner; pytest stalls while
  executing the empty `asan-support` capability probe.

## Summary

The shared ASan harnesses run compiler and executable subprocesses without timeouts and search fallback compiler names
after configured compiler failures. A broken sanitizer runtime can therefore stall an aggregate suite until its outer
job limit, while a different compiler can silently satisfy an ASan check in a compiler-specific validation run.

ASan is an optional oracle unless `L0_ASAN_CC` or `L1_ASAN_CC` explicitly requests it. Capability detection must remain
bound to the selected compiler, retry the same compiler with the established non-PIE compatibility flags only when the
ordinary empty probe is unavailable, and distinguish optional unavailability from an explicit request failure.

## ADR Impact

- Decision: Bound optional ASan test capability detection while preserving configured compiler identity.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This restores reliable execution of existing test-only sanitizer probes and their documented optional
    capability contract without changing Dea semantics, compiler output, runtime ABI, or supported-host policy.

## Root Cause

1. Empty ASan support executables and real probe programs use unbounded `subprocess.run` calls.
2. Candidate selection tries `L0_CC` or `L1_CC`, then generic Clang and GCC names. A configured compiler that cannot run
   ASan may therefore be replaced silently by another compiler.
3. The harness cannot distinguish an explicit sanitizer compiler request from implicit reuse of the ordinary C compiler,
   so it cannot enforce failure for the former and an honest skip for the latter.
4. Earlier GCC validation established that `-fno-pie -no-pie` can recover an empty ASan runtime startup stall, but that
   bounded same-compiler retry remained a validation-only workaround.

## Scope of This Fix

1. Add one shared Python helper for ASan compiler selection and bounded capability probing, with small data structures
   describing the selected compiler and any required compatibility flags.
2. Treat `L0_ASAN_CC` and `L1_ASAN_CC` as explicit sanitizer requests. Fail when those compilers cannot compile and run
   the empty probe after the bounded default and non-PIE attempts.
3. When no ASan-specific variable is set, probe only the configured level/runtime compiler. If its default and non-PIE
   attempts are unavailable, report an explicit ASan skip without changing compiler identity.
4. When no configured compiler exists, retain local developer discovery across conventional compiler names while
   reporting optional unavailability honestly.
5. Retry `-fno-pie -no-pie` only with the same compiler after the ordinary empty capability probe fails or times out;
   propagate the selected flags to every compile and link step of the real ASan fixture.
6. Bound real ASan fixture execution. Once capability is established, any compile, execution, diagnostic, or timeout
   failure remains a test failure.
7. Add focused tests using controlled fake compiler and executable behavior for normal success, same-compiler non-PIE
   recovery, implicit skip, explicit failure, timeout handling, and prohibition of configured-compiler substitution.

## Non-Goals

- Requiring ASan support from every C compiler supported for ordinary Dea compilation.
- Falling back from a configured GCC validation run to Clang for ASan checks.
- Making non-PIE output the default for Dea programs or unconditional for sanitizer tests.
- Changing checked-runtime quarantine semantics, vector behavior, or sanitizer poisoning implementation.
- Diagnosing or repairing the external GCC, linker, or ASan runtime defect itself.

## Verification Criteria

- Every ASan subprocess has a finite timeout and reports the selected compiler plus attempted flag mode.
- A configured ordinary compiler remains the only compiler considered for that job's optional ASan checks.
- An unavailable implicit ASan capability skips only ASan assertions and leaves the ordinary compiler suite running.
- An unavailable explicitly requested ASan compiler fails promptly.
- A default-probe failure can recover only through the same compiler with `-fno-pie -no-pie`, and the real fixture uses
  the same flags.
- Once a capability probe succeeds, real Dea ASan fixture failures and timeouts fail instead of skipping.
- Focused L0 and L1 harness tests pass, followed by the trace-independent cross-level normal validation tier.
- Active and staged ADR Impact checks, staged whitespace checks, and root pre-commit pass.

## Outcome

- Added `scripts/asan_test_support.py` as the shared policy implementation for compiler selection, bounded capability
  probes, explicit-request failures, optional skips, and same-compiler non-PIE recovery.
- Updated all four L0 and L1 ASan harnesses to reuse the selected compiler and compatibility flags for their real
  fixtures, with finite compile, build, and execution deadlines.
- Preserved configured compiler identity: a GCC-selected job no longer substitutes Clang when GCC's ASan runtime is
  unavailable. Conventional compiler discovery remains available only when no compiler was configured.
- Added focused regression coverage for default success, non-PIE recovery, implicit skip, explicit failure, bounded
  timeouts, and the prohibition on configured-compiler substitution.
- No stable product documentation or diagnostic-code changes were required because this change affects test
  orchestration only and does not alter Dea compiler, runtime, language, or supported-host semantics.

## Verification

- `python3 -m py_compile` passed for the shared helper and all five affected Python test modules.
- The focused helper and L0 quarantine run passed `8` tests.
- The L0 vector harness passed with `L0_CC=clang`; with `L0_CC=gcc-mp-15`, ordinary vector coverage passed and ASan
  skipped after bounded default and same-GCC non-PIE attempts because the local MacPorts installation lacks `libasan`.
- The same explicit `L0_ASAN_CC=gcc-mp-15` selection failed promptly, confirming that an explicit ASan request cannot be
  skipped.
- The L1 quarantine harness passed with `L1_RUNTIME_CC=clang`.
- Clean-tree root `make test` passed after root `make clean`: L0 passed `1532` Stage 1 tests, `58` Stage 2 suites, all
  examples and workflow checks; L1 passed all `82` normal suites, including both ASan harnesses, plus environment,
  example, and Docker/Wine checks.
- `python3 scripts/check_adr_impact.py --all-active` and `git diff --check` passed before closure.
