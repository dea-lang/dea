# Bug Fix Plan

## Support Doxygen 1.18 anonymous compound names in m.css

- Date: 2026-08-27
- Status: Completed
- Title: Support Doxygen 1.18 anonymous compound naming in the vendored m.css renderer
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Subsystem: Documentation tooling / Vendored m.css / CI
- Modules:
  - `tools/m.css/documentation/doxygen.py`
  - `tools/m.css.L0-PATCHES.md`
  - `.github/workflows/l0-docs-build.yml`
  - `.github/workflows/l0-docs-validate.yml`
- Test modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_mcss_compat.py`
  - `l0/tests/test_release_tag_policy.py`
- Related:
  - `l0/work/plans/tools/closed/2026-03-02-doxygen-mcss-docs-system.md`
- Repro: `cd l0 && python3 scripts/gen_docs.py --strict`

## Summary

Strict L0 documentation generation succeeds with Ubuntu 24.04's Doxygen 1.9.8 but fails with Doxygen 1.18.0 while the
vendored m.css renderer derives leaf names for nested compounds. The fix must recognize Doxygen 1.18's validated
anonymous-compound field paths without weakening m.css's rejection of inconsistent parent-child names.

## ADR Impact

- Decision: Adapt the vendored renderer to Doxygen 1.18's anonymous nested-compound naming while retaining its strict
  parent-child validation.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a narrowly scoped compatibility repair for an upstream XML spelling change; it preserves the
    existing documentation architecture, generated artifact contract, and strict validation policy.

## Current State

1. Doxygen 1.9.8 flattens the anonymous `l0_string.data` union and its `s_str` struct members into the enclosing
   `l0_string` compound.
2. Doxygen 1.18.0 emits separate compounds named `l0_string::[union].data` and `l0_string::[struct].data.s_str` and
   links the struct as an `innerclass` of the union.
3. m.css requires every nested class, struct, or union name to begin with the full parent name followed by `::`.
4. The Doxygen 1.18 names encode the same field path with different `[union]` and `[struct]` markers, so the valid XML
   relationship violates m.css's textual-prefix assumption and triggers an assertion.

## Scope of This Fix

1. Preserve the exact parent-prefix path used by Doxygen 1.9.8 and other established compound names.
2. Recognize the Doxygen 1.18 anonymous-compound form only when parent and child share the same named scope and the
   child's field path is a direct extension of the parent's field path.
3. Continue raising an assertion for names that satisfy neither relationship.
4. Add focused regression coverage for the established, Doxygen 1.18, and malformed cases.
5. Record the vendored m.css change and expose the installed Doxygen version in both distinct L0 CI documentation entry
   points.

## Non-Goals

1. Changing the runtime `l0_string` layout or documentation comments to avoid the upstream XML form.
2. Ignoring anonymous compounds, suppressing renderer failures, or weakening strict documentation validation.
3. Pinning CI to a single Doxygen version or publishing generated documentation.

## Implementation Sequence

1. Isolate m.css leaf-name derivation behind a helper that preserves the exact-prefix fast path.
2. Add a narrowly validated fallback for Doxygen 1.18 anonymous compound field paths.
3. Add representative naming regressions and workflow policy coverage.
4. Add `doxygen --version` reporting to the standalone validation workflow and the reusable build workflow.
5. Run strict generation, documentation-generator tests, Markdown export, formatting, ADR, pre-commit, and cross-cutting
   trace-independent validation.

## Verification Criteria

1. `python3 scripts/gen_docs.py --strict` passes with Doxygen 1.18.0 without ignored or suppressed data.
2. The focused regression accepts both established exact-prefix names and the Doxygen 1.18 anonymous field-path form.
3. The focused regression rejects an unrelated anonymous child path.
4. Ubuntu 24.04 Doxygen 1.9.8 generates compatible XML and passes the renderer or equivalent strict pipeline when
   container access permits.
5. Both distinct CI documentation build/validation entry points print `doxygen --version`, while release, snapshot, and
   publication callers continue to reuse the shared build workflow.

## Implementation Outcome

1. The vendored m.css renderer keeps its established exact parent-name prefix path and adds a focused fallback for
   Doxygen anonymous-compound names.
2. The fallback accepts a child only when its named scope matches the anonymous parent and its field path extends the
   parent's field path; unrelated names still raise an assertion.
3. Regression coverage uses the exact Doxygen 1.18 names from `l0_string.data.s_str`, plus established and malformed
   representative names.
4. `tools/m.css.L0-PATCHES.md` records the vendored compatibility change. `THIRD_PARTY_NOTICES` remains current because
   the component, upstream snapshot, license, vendored path, and local-patch pointer are unchanged.
5. `.github/workflows/l0-docs-validate.yml` now prints the Doxygen version in the standalone validation entry point.
6. `.github/workflows/l0-docs-build.yml` now prints the Doxygen version once in the reusable build entry point used by
   release, snapshot, and documentation-publication workflows.

## Verification Outcome

1. Before the fix, `python3 scripts/gen_docs.py --strict` reproduced the assertion with host Doxygen 1.18.0.
2. `python3 scripts/gen_docs.py --strict` passed after the fix with host Doxygen 1.18.0.
3. Ubuntu 24.04 Doxygen 1.9.8 generated the comparison XML and passed the complete strict pipeline through a temporary
   Docker-backed Doxygen wrapper using `PATH=build/doxygen-198-bin:$PATH python3 scripts/gen_docs.py --strict`.
4. `../.venv/bin/python -m pytest -q $(rg --files compiler/stage1_py/tests/cli | rg '/test_docgen.*\.py$' | sort)`
   passed all 98 documentation-generator tests.
5. `../.venv/bin/python -m compiler.docgen.l0_docgen_blog --input build/docs/markdown --output build/docs/api-reference`
   completed successfully.
6. `python3 tests/test_release_tag_policy.py` passed with coverage for both Doxygen-version workflow steps.
7. The repository-wide clean trace-independent aggregate passed: `make clean` completed for L0 and L1, then `make test`
   passed from that unchanged clean tree with 1,468 L0 Python tests, 56 L0 Stage 2 tests, eight L0 examples, all L0
   workflow/distribution checks, 68 L1 Stage 1 tests, the L1 environment check, and four L1 examples.
8. The dedicated broad trace sweeps were not required because the change affects documentation rendering, CI visibility,
   and non-trace test coverage only; it does not alter compiler/runtime behavior, ownership, generated cleanup, trace
   inputs, or trace wiring.
