# Bug Fix Plan

## Canonical architecture in distribution test expectations

- Date: 2026-11-14
- Status: Completed
- Title: Correct the distribution test expectation for canonical architecture names
- Kind: Bug Fix
- Severity: High
- Stage: 2
- Subsystem: Distribution workflow tests
- Modules:
  - `l0/tests/test_make_dist_workflow.py`
- Test modules:
  - `l0/tests/test_dist_tools_lib_fallback.py`

## Summary

Unified CI on Windows rejects a correctly generated `windows-x86_64` archive because the distribution test derives
`windows-amd64` from the compiler's intentionally raw host report. The stale assertion blocks the L0 validation gate;
production packaging already implements the canonical architecture contract.

## ADR Impact

- Decision: Align distribution test expectations with the existing canonical architecture contract.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs test coverage without changing the package contract, compiler, runtime, or release policy.

## Implementation

1. The extracted complete archive-name assertion is shared by the lightweight regressions and the build test.
2. The test independently normalizes architecture aliases, preserving OS and format checks. Full-name matching also
   rejects trailing text and newlines.
3. Coverage includes nine Windows/POSIX host spellings and nine invalid names with wrong architectures, operating
   systems, formats, prefixes, timestamp shapes, or trailing content.

## Verification

- The new regression rejected the canonical Windows archive before the expectation fix.
- From `l0/`, `make test-dist-fallback test-release-tags` passed with the corrected expectation, including the extracted
  workflow assertion. Windows coverage uses simulated host strings, not native execution.
- Root `python3 scripts/check_adr_impact.py --all-active` passed before closure.
- Native Windows end-to-end validation remains a hosted gate. Remote operations remain outside this local repair's
  scope.
