# Bug Fix Plan

## Restore the repository inputs required by Docker validation

- Date: 2026-09-08
- Status: Completed
- Title: Include cross-level and vendored test dependencies in the L0 Docker image
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Subsystem: Local Docker validation
- Modules:
  - `l0/Dockerfile`
  - `l0/README.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_mcss_compat.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage1_py/tests/cli/test_stage2_trace_log_checker.py`
  - `l0/tests/test_shuffle_sources.py`
- Repro: `make -C l0 docker CMD=test-all`

## Summary

Restore the source files needed to run L0 validation inside the existing Docker image.

## ADR Impact

- Decision: Include existing test dependencies in the L0 Docker source layer.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs an incomplete test environment without changing compiler architecture, runtime contracts,
    supported Python versions, or the existing Docker workflow.

## Root Cause

The Docker source layer copies L0 and shared scripts but includes only L1's workspace metadata and no vendored tools.
Documentation tests require `tools/m.css/documentation/doxygen.py`; runtime compatibility tests and source-selection
tests require L1 sources. Trace-checker parity tests also load L1's checker script. These files exist in a normal
checkout but are absent from the container.

## Approach

1. Copy L1 and vendored tools into the source layer, retaining the cached dependency layer and existing exclusions for
   host virtual environments and build outputs.
2. Document the image's cross-level test inputs.
3. Run the exact Docker `test-all` command, investigate any remaining failures, and obtain an independent read-only
   review before finalizing.

## Verification Criteria

- Existing documentation, runtime header, and source-selection regressions execute successfully in the image.
- `make -C l0 docker CMD=test-all` passes, including the dedicated trace sweep.
- ADR validation, staged whitespace, and pre-commit pass. No CI workflow changes are required.

## Outcome and Validation

The Docker source layer now includes `l1/` and `tools/`. The dependency layer, Python baseline, compiler selection,
host-artifact exclusions, and CI workflows are unchanged. Existing integration tests directly cover the formerly missing
inputs; no duplicate Dockerfile-shape test was added.

- `make -C l0 docker CMD=test-all`: passed in the rebuilt Python 3.14 Linux image with GCC. All 1,525 Stage 1 tests, 58
  Stage 2 test groups including triple bootstrap, eight examples, 13 runtime build-flag tests, distribution/build
  workflow checks, fallback provenance checks, and source-selection checks passed.
- The same command completed all 34 dedicated trace cases with zero object or string leaks.
- Release-tag-policy checks retained their existing skip because `.github` is excluded from the image.
- A focused Docker run of `compiler/stage1_py/tests/backend/test_runtime_quarantine_asan.py` also passed both tests.
- An independent read-only review found no actionable bugs, missing inputs, regressions, or coverage gaps.

This is a test-environment repair with no compiler or runtime behavior changes. Full Docker validation was used to
verify the exact reported command, including its trace tier.
