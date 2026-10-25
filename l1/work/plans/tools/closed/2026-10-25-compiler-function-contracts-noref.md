# Tool Plan

## Complete L1 compiler function contracts

- Date: 2026-10-25
- Status: Completed
- Title: Complete L1 compiler function contracts
- Kind: Tooling
- Priority: Medium
- Subsystem: Compiler implementation and native binding documentation
- Modules:
  - `l1/compiler/src/backend/coerce.l0`
  - `l1/compiler/src/backend/expr.l0`
  - `l1/compiler/src/c_emitter/expr.l0`
  - `l1/compiler/src/expr_types/convert.l0`
  - `l1/compiler/src/expr_types/lookup.l0`
  - `l1/compiler/src/util/demangler.l0`
  - `l1/compiler/src/compiler_filesystem.l0`
  - `l1/compiler/src/preparation.l0`
  - `l1/compiler/src/preparation/frontend.l0`
  - `l1/compiler/support/preparation_support.c`
- Related:
  - [docs/reference/c-documentation.md][c-docs]
  - [l1/docs/README.md][docs-guide]
- Repro: From `l1/`, run `make docs-artifacts DEA_DIST_VERSION=dev`.

## Summary

Document the 36 compiler helpers and 37 native extern bindings listed in the current L1 undocumented-function report.
Use multiline Javadoc autobrief contracts with applicable parameter, return, ownership, mutation, and failure details.
Describe existing behavior from implementations and callers; preserve executable code and the informational CI report
policy. Regenerate the complete L1 reference and verify that the resulting report has no findings. Complete the work
locally; remote publication is outside this plan.

## ADR Impact

- Decision: Apply existing Javadoc autobrief conventions to the remaining L1 compiler functions.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This documents existing helper and binding contracts without changing interfaces, runtime behavior,
    reference architecture, or documentation coverage policy.

## Scope and method

1. Audit the report against definitions, native implementations, and direct callers.
2. Add adjacent multiline contracts with first-sentence briefs and blank source lines before each opening block.
3. Preserve compiler-internal scope, borrowed and owned resources, output mutation, sizing queries, status values, and
   partial-failure behavior. Correct directly related stale native documentation without changing its implementation.
4. Compare language and C executable tokens against the initial source tree.
5. Generate strict Markdown, XML, HTML, LaTeX, the complete indexed PDF, and a verified offline bundle.
6. Check all reported functions' generated briefs, parameter/return sections, signatures, and source locations; verify
   an empty report, offline links, and bundle identity. Run whitespace, ADR Impact, and pre-commit checks before local
   finalization.

## Verification

This is a documentation-only change with no compiler/runtime, ownership execution, diagnostic-code, or trace
configuration changes. Independent source reviews cover all 73 new contracts.

- The official L0 lexer produces identical executable-token sequences for all nine compiler sources. The related C
  return-description correction also preserves its executable-token sequence.
- The fresh strict reference has zero undocumented findings. All 73 XML occurrences match their current declaration
  lines, original signatures, first-sentence briefs, and complete parameter/return sections.
- Generated HTML retains all 397 narrative/parameter/return paragraphs and all 185 parameter labels/descriptions across
  the nine source pages. Its 588 pages have no broken local paths or fragments; the completed PDF target is present.
- From `l1/`, `make docs-artifacts DEA_DIST_VERSION=dev` completes strict XML, Markdown, HTML, and LaTeX generation with
  zero extraction warnings, a complete indexed 1,863-page PDF, and no unresolved references.
- Unpacking and verifying the offline bundle validates all 592 HTML/PDF payload hashes, current source identity, and
  strict/full-PDF provenance. All ten source input hashes remain unchanged after source review and generation.
- `python3 scripts/check_c_docs.py` reports 98 maintained C/header files, 73 vendor/generated exclusions, and zero
  errors. Existing generator/test inputs are unchanged; the current source corpus is verified by the fresh full build
  and direct XML/HTML audits rather than rerunning compiler or trace aggregates.

## Contract audit findings

Native path outputs report a required positive byte count when a buffer is short, while `l1c_prep_get` returns -1 for an
insufficient nonnull buffer. Unknown, unavailable, and empty context fields produce zero bytes; the corresponding stale
C return description is corrected. Raw spans are not implicitly NUL-terminated, and context and result cleanup rules are
explicit.

Type-map updates clone borrowed types and respect liveness-only suppression. Named-argument resolution allocates an
independent reordered id vector and releases partial results on errors. Demangler helpers retain partial cursor/output
mutation on failure and parse components without promising complete canonical LBI validation.

## Outcome

All 73 reported L1 compiler helpers and extern bindings now have individual Javadoc autobrief contracts. The regenerated
canonical report has zero findings, and the complete reference and offline bundle are verified. CI coverage policy is
unchanged. All work is complete locally; remote publication is outside this plan.

[c-docs]: ../../../../docs/reference/c-documentation.md
[docs-guide]: ../../../docs/README.md
