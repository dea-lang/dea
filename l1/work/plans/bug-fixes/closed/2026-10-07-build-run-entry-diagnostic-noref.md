# Bug Fix Plan

## Source entry diagnostics for build/run

- Date: 2026-10-07
- Status: Closed (fixed)
- Title: Diagnose ineligible L1 build/run entries before native compilation
- Kind: Bug Fix
- Severity: Low
- Stage: Shared
- Subsystem: L1 build/run orchestration
- Modules:
  - `l1/compiler/stage1_l0/src/link_driver/workspace.l0`
  - `l1/compiler/stage2_l1/src/link_driver/workspace.l1`
- Test modules:
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`

## Summary

Reuse `analysis_module_entry_type` after successful semantic analysis in both compiler stages. Report the existing
`L1C-0012` for absent, extern-only, parameterized, or non-function target `main` declarations. Preserve standalone
`L1C-2104`, private eligible entry functions, and semantic-error precedence. No new diagnostic code is assigned. The
check precedes runtime preparation and source graph native compilation, but workspace creation and semantic preparation
still precede it.

## Validation

Exercise both build and run for ineligible entries, including an imported eligible main. Run the multi-CU and link
driver regressions in both stages and the normal development gate. This change uses existing analysis lifetimes and
cleanup and is trace-independent.

### Results

- Stage 1 source semantic check passed with
  `l0/scripts/l0c --check --project-root l1/compiler/stage1_l0/src link_driver.workspace` (invoked from the L0 directory
  with adjusted relative paths).
- Python regression syntax, Markdown formatting, whitespace, and active ADR validation passed.
- Selected native compiler: `/usr/bin/gcc`, Debian GCC 14.2.0.
- Focused native regressions passed in both stages:
  `make test-stage1 TESTS='l1c_stage1_build_run_multi_cu_test link_driver_test'` and
  `make test-stage2 TESTS='l1c_stage1_build_run_multi_cu_test link_driver_test'` (two tests each).
- The L1 `make test` gate passed, including both-stage smoke tests, stage parity, examples, Docker/Wine runner
  regressions, and Stage 2 tooling/bootstrap identity checks.
- Native validation used escalated execution because the sandbox reports untrusted UID 65534 for the root directory.
  Escalation provided a trusted filesystem view; the compiler's filesystem trust checks were unchanged.
- Validation commands selected GCC explicitly through `L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc` and used
  `UV_CACHE_DIR=/tmp/dea-uv-cache` for the writable dependency cache.

## ADR Impact

- Decision: Improve source entry diagnostics at the existing build/run semantic boundary.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This localized validation reuses existing entry eligibility and diagnostic meanings without changing the
    compilation or linking architecture.
