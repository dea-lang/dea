# Bug Fix Plan

## Preserve enum and module PDF destinations and validate final PDF links

- Date: 2026-10-27
- Status: In Progress
- Title: Preserve enum and module PDF destinations and validate final PDF links
- Kind: Bug Fix
- Severity: Medium
- Scope: Shared
- Targets:
  - L0 LaTeX normalization and full PDF validation
  - L1 LaTeX normalization and full PDF validation
- Origin: Missing enum-variant destinations in the canonical L1 reference PDF
- Porting rule: Apply the same enum identity preservation to both normalizers and share final PDF validation.
- Target status:
  - L0 LaTeX normalization and full PDF validation: Implemented
  - L1 LaTeX normalization and full PDF validation: Implemented
- Subsystem: Documentation generation and strict artifact acceptance
- Modules:
  - `l0/compiler/docgen/l0_docgen_latex.py`
  - `l1/compiler/docgen/l1_docgen_latex.py`
  - `scripts/docgen_pdf.py`
  - `l0/scripts/gen_docs.py`
  - `l1/scripts/gen_docs.py`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_latex.py`
  - `l1/tests/test_docgen_outputs.py`
  - `l1/tests/test_docgen_make.py`
  - `scripts/tests/test_docgen_pdf.py`
  - `scripts/tests/test_docgen_inputs.py`

## Summary and root cause

The L1 reference completes its indexed PDF but reports 99 missing PDF destinations. Every target matches an XML enum
value. The normalizers replace Doxygen's enum tables with source-level payload declarations, discarding the per-variant
anchors. This affects both language-level generators. Restore the canonical variant destination and label on the
matching list item, preserving source order and declarations.

Before this repair, full PDF validation checked only ordinary unresolved references and the index in L1, with no
equivalent checks in L0. Both wrappers now validate the final `refman.log` and index, including wrapped pdfTeX
missing-destination warnings. Earlier compilation passes may legitimately report unresolved references; inspect only the
final log. Preview PDFs retain their incomplete-reference workflow.

Strict hosted validation now accepts the L1 reference and the L0 Stage 1 reference. L0 Stage 2 still reports two missing
module destinations. Doxygen emits `module__ast` and `module__l0c` references without corresponding XML compounds or
LaTeX pages; the documented Dea modules have existing source-file pages instead. Resolve these aliases from XML
reference names to unambiguous, present file pages, preserving genuine module compounds and unresolved or ambiguous
references. Apply the same normalization rule in both level generators.

The L1 environment-preparation regression also retains the old exact pytest argument list, excluding the newly wired
shared PDF checks. Update that fixture while retaining its ordering, interpreter-selection, and complete argument
checks.

## ADR Impact

- Decision: Preserve existing PDF symbol and module identities and enforce complete-reference validation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs generated links and an acceptance-check gap within the existing strict documentation
    pipeline without changing language, artifact schema, publication, or toolchain policy.

## Implementation and verification

1. Preserve XML enum-value IDs as Doxygen-compatible destinations and labels on the corresponding restored variants.
   Cover source/XML ordering differences, payload and plain variants, binding prefixes, and repeated normalization.
2. Share final full-PDF validation between L0 and L1, rejecting missing destinations, unresolved references, missing
   logs, and missing indexes before PDF promotion or bundle creation.
3. Include the shared validator in source fingerprints and focused documentation test targets. Test log wrapping,
   final-pass selection, and failed-build transactions with short fixtures and mocked subprocesses.
4. Correlate all 99 retained warning targets with repaired variant identities without rebuilding references locally.
   Complete indexed PDFs and native platform behavior remain for CI validation.
5. Resolve dangling Doxygen module aliases through their XML reference names and actual source-file page identities.
   Cover both generators, unknown and ambiguous modules, missing file pages, genuine module compounds, and repeated
   normalization with short fixtures. Update the L1 Make regression to include the shared PDF test selection.

## Findings and local validation

All 99 retained missing destinations match XML enum-value IDs: 76 belong to `TokenType`; 23 belong to nine result enums.
The repaired list renderer emits exactly one destination and label for each of those targets, matched by variant name
rather than XML order. The shared validator rejects the retained final LaTeX log with the exact count of 99 missing
destinations. These were read-only checks against retained XML/log evidence; no reference or PDF was rebuilt.

Hosted validation after the enum repair accepts the indexed L1 and L0 Stage 1 references. L0 Stage 2 rejects only the
two dangling module destinations. Native Windows also passes the existing validator and wrapper fixtures; its L1
documentation target fails in the stale Make fixture instead.

The module repair uses XML reference names and the declared Dea module names rather than inferring destinations from
display labels or Doxygen ID spelling. Genuine module compounds, unknown module names, ambiguous source mappings, and
missing LaTeX file pages retain their references. Both normalizers share one parameterized regression in the existing
PDF test module, including nested display formatting and repeated normalization.

- Before repair, four positive module-link cases fail and the 16 preservation cases pass. Both serial and parallel L1
  environment-preparation cases reproduce the missing PDF-test argument failure.
- From `l0/`, the shared environment's `python -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_latex.py`: 31
  passed.
- From `l1/`, `make test-docgen`: 244 passed, including environment preparation, the expanded shared PDF tests,
  documentation rendering, inventory, C contracts, and input fingerprints. The prepared environment uses Python 3.14.7
  and current uv with offline caches.
- From the repository root, `python -m pytest -q -n 0 scripts/tests/test_docgen_pdf.py`: 34 passed. This includes the 20
  new module-link cases alongside the existing final-log, index, and wrapper transaction checks.
- A temporary copy of retained Doxygen 1.18 Stage 2 LaTeX sources contains four links using the two missing aliases.
  Normalization redirects all four to `ast_8l0` and `l0c_8l0`; both replacement destinations have actual LaTeX target
  definitions. No reference generation or PDF compilation runs in this probe.

## Remaining validation

Keep the plan active until CI rebuilds all three strict, indexed PDFs and confirms that missing-destination warnings are
gone for the final generator inputs. The expanded module-link cases and corrected Make regression still require native
Windows hosted validation. Earlier full reference success establishes enum-link and toolchain evidence, not acceptance
of the subsequent module-link normalization changes.

## Scope

No long local tests, full documentation/PDF builds, compiler suites, toolchain changes, remote writes, or workflow
dispatches. Keep Doxygen 1.18 and the Ubuntu 26.04 documentation runners. Leave unrelated Windows tooling work intact.
