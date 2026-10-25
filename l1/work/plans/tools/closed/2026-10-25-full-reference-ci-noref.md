# Tool Plan

## Validate full L1 references in routine CI

- Date: 2026-10-25
- Status: Completed
- Title: Validate full L1 references in routine CI
- Kind: Tooling
- Priority: Medium
- Subsystem: Documentation CI
- Modules:
  - `.github/workflows/ci.yml`
  - `.github/workflows/l1-docs-validate.yml`
  - `l1/compiler/docgen/l1_docgen_latex.py`
- Test modules:
  - `scripts/tests/test_ci_bootstrap.py`
  - `l1/tests/test_docgen_workflow.py`
  - `l1/tests/test_docgen_outputs.py`
- Related:
  - [MONOREPO.md][monorepo]
  - [l1/docs/README.md][docs-guide]
- Repro: From `l1/`, run `make docs-artifacts DEA_DIST_VERSION=dev`.

## Summary

Add independently routed full L1 reference validation to Unified CI, matching L0's generation and informational-report
behavior. The job builds strict XML, HTML, Markdown, LaTeX, a complete indexed PDF, and a verified offline bundle. It
explicitly prints the canonical undocumented-function report when available; entries do not fail the job. L1 has one
canonical report, while L0 prints both stage reports. Available diagnostics and completed bundles are retained on build
failure.

## ADR Impact

- Decision: Add full routine L1 reference validation with informational reports matching L0.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This adds CI coverage under the existing reference-generation and publication boundaries without changing
    documentation completeness policy or introducing a new architecture.

## Scope and approach

1. Preserve L0 routing and add an independent L1 documentation route for canonical inputs, documentation tooling, and
   relevant shared dependencies, including manual and unavailable-diff fallbacks.
2. Add a read-only reusable Ubuntu workflow with Python, Doxygen, Graphviz, and complete TeX dependencies.
3. Generate the full strict reference and verified bundle, then print the available report with an always-running step.
4. Test actual routing scripts, report-step behavior for populated/empty/missing reports, and retained diagnostic and
   bundle artifacts.
5. Verify full local PDF/bundle generation without dispatching hosted CI.

No compiler/runtime behavior, trace configuration, diagnostic codes, documentation coverage policy, publication, or
remote writes change.

## Full-build rendering repair

The full corpus build exposed corrupt LaTeX enum tables: separate removal/insertion passes reused stale offsets, and XML
declaration order could differ from LaTeX document order. Apply each replacement in one splice, ordered from the end of
the original document. Bound each table search to its own enum section so a missing or already-replaced table cannot
consume a following plain enum's table. Regressions cover multiple enums, reversed declaration order, absent tables, and
repeated normalization.

## Verification

- `python -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py l1/tests/test_docgen_workflow.py` passes all 150 cases.
- From `l1/`, `make test-docgen` passes all 112 documentation tests, including four LaTeX enum-replacement regressions.
- Routing and workflow regressions exercise positive/negative paths, manual and missing-diff fallbacks, unchanged L0
  routing, artifact retention, and execution of the actual report-printing command.
- The report step succeeds for canonical empty reports, populated Dea/Python/native-support reports, and an absent
  report. Available report contents are printed unchanged.
- `actionlint .github/workflows/ci.yml .github/workflows/l1-docs-validate.yml` passes.
- From `l1/`, `make docs-artifacts DEA_DIST_VERSION=dev` succeeds with the complete indexed PDF and no unresolved
  references. Extraction and manifest validation confirms strict/full-PDF success, all 564 payload-file digests, and
  current source identity. This generation evidence remains valid because the generator, sources, dependencies, and
  toolchain inputs are unchanged by the informational-report adjustment.
- The current 432-entry report remains informational. Hosted workflow execution was not dispatched.

[docs-guide]: ../../../../docs/README.md
[monorepo]: ../../../../../MONOREPO.md
