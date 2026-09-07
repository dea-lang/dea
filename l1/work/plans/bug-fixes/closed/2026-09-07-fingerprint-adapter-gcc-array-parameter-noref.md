# Bug Fix Plan

## Align fingerprint adapter output declarations for GCC

- Date: 2026-09-07
- Status: Completed
- Title: Align fingerprint adapter output declarations for GCC
- Kind: Bug Fix
- Severity: High
- Stage: 1
- Subsystem: Compiler-private fingerprint C adapter
- Modules:
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_hash.c`
  - `l1/compiler/stage1_l0/support/interface_fingerprint.c`
- Test modules:
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_runtime_test.py`
- Related:
  - [l1/docs/specs/compiler/abi.md][abi]
  - [l1/work/plans/bug-fixes/closed/2026-09-07-stage2-fingerprint-bridge-declaration-conflict-noref.md][bridge-fix]
- Repro: `make -C l1 test-stage1 TESTS=interface_fingerprint_runtime_test L1_RUNTIME_CC=gcc`

## Summary

Linux GCC 13 and Windows GCC 16 fail the generated-C fingerprint bridge regression in
[Unified CI run 34140130003](https://github.com/dea-lang/dea/actions/runs/34140130003). Both report
`-Werror=array-parameter`: the public adapter declaration uses `uint8_t out_hex[16]`, while the production L0/L1 extern
generates `dea_byte *out_hex`. These C parameter types are compatible, but GCC diagnoses the inconsistent array-bound
spelling under the regression's strict warning policy.

## ADR Impact

- Decision: Match the existing pointer adapter's output declaration to generated C.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This bounded declaration repair preserves the ABI, exact digest bytes, output extent, ownership, and
    bootstrap strategy. It introduces no architectural choice or source-language change.

## Approach

1. Reproduce the warning with GCC using the public header and the generated extern spelling.
2. Use `uint8_t *out_hex` for the compiler-private adapter in its header, both definitions, and regression harness.
   Retain the const-input C entrypoint and internal hashing helper signatures. Document the caller's 16-byte output
   obligation in the header and ABI reference.
3. Keep strict compiler warnings enabled. Run the existing generated-C, known-answer, input-immutability, output-guard,
   direct-support, and four-runtime-variant regression under GCC and Clang.
4. Run the L1 full validation tier because runtime declarations and definitions are touched, then close this plan and
   run staged whitespace, ADR Impact, and pre-commit checks.

## Non-Goals

No fingerprint algorithm, serialization, symbol, general emitter, diagnostic-code, or CI configuration changes.

## Verification Criteria

- The original minimal declaration fails with GCC, and the repaired declaration passes with strict warnings.
- GCC normal coverage and the default trace sweep pass; local sanitizer workarounds are recorded explicitly.
- The focused bridge regression also passes under Clang.
- The ABI reference and roadmap reflect the repair; staged checks pass.

## Validation Results

- Linux GCC 12.2 reproduced the same `-Werror=array-parameter` failure as both hosted jobs using the delivered-header
  include and exact generated extern spelling. The repaired declaration passes the identical strict C99 command with
  `-Wall -Wextra -Werror -pedantic`.
- The focused bridge regression passed with Linux Clang 14.0.6 against the rebuilt L1 compiler and runtime archives:
  `L1_RUNTIME_CC=clang /project/.venv/bin/python compiler/stage1_l0/tests/interface_fingerprint_runtime_test.py`, run
  from `/project/l1` in the Linux validation container. This covers generated-C/header compatibility, direct support
  linkage, all four runtime archives with and without common support, known digest bytes, input immutability, and output
  guards.
- Both modified C implementation files produce byte-identical GCC `-O2 -g0` objects before and after the repair when
  compiled from identical stdin source identities. The declaration spelling does not alter their native code.
- `make -C l1 docker CMD='clean test-all' DOCKER_IMAGE=dea-ci-fingerprint-gcc DOCKER_CC=gcc L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=4`
  passed 72 normal tests, including the original failing bridge regression, but was interrupted while
  `vector_aliasing_test.py` accumulated output in an ASan subprocess. A bounded rerun of that exact executable passed;
  repeated test attempts exposed the same stall even in the empty ASan capability probe. This is separate from the
  declaration repair.
- Ten empty GCC ASan probes passed with `-fno-pie -no-pie`. The full `vector_aliasing_test.py` then passed in checked
  and unchecked modes with `L1_ASAN_CC` pointing to a temporary wrapper that invokes `/usr/bin/gcc -fno-pie -no-pie`.
  AddressSanitizer instrumentation remained enabled. The wrapper and timeout controls are validation-only container
  artifacts; no test behavior or compiler configuration was changed in the repository.
- The original 72 passing normal results are retained with the separately passing vector regression. The remaining
  validation uses the same preserved source and build artifacts, GCC selection, and flags; only the vector sanitizer
  build uses the documented non-PIE override. Subsequent repository edits are documentation-only.
- `make test-env check-examples test-stage1-trace` passed in `/project/l1` in the preserved GCC container: environment
  stackability, four examples without warnings or errors, and all 45 default trace cases with zero leaked objects and
  strings. Together with the normal-test results and focused sanitizer recovery, this completes the L1 `test-all` tier
  selected for the runtime declaration changes. The existing slow math trace exclusion is unchanged.
- All 81 repository reference links in the edited documents resolve after closure. Staged whitespace, ADR Impact, and
  root pre-commit checks pass on the final closed plan.
- Hosted Linux GCC 13 and Windows GCC 16 reruns are outside this local repair; no remote write or workflow dispatch is
  part of this plan's completion criteria.

[abi]: ../../../../docs/specs/compiler/abi.md
[bridge-fix]: 2026-09-07-stage2-fingerprint-bridge-declaration-conflict-noref.md
