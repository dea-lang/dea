# Tool Plan

## Pin hosted Ubuntu runners by job role

- Date: 2026-10-27
- Status: In Progress
- Title: Pin hosted Ubuntu runners by job role
- Kind: Tooling
- Priority: Medium
- Scope: Shared
- Targets:
  - Compiler CI and utility jobs
  - Linux release, snapshot, and artifact acceptance jobs
- Origin: Shared GitHub Actions workflow configuration
- Porting rule: Use Ubuntu 26.04 for CI and utilities and Ubuntu 24.04 for native artifact builders and matching
  verifiers.
- Target status:
  - Compiler CI and utility jobs: Implemented
  - Linux release, snapshot, and artifact acceptance jobs: Implemented
- Subsystem: Hosted CI and release runner selection
- Modules:
  - `.github/workflows/`
  - `MONOREPO.md`
- Test modules:
  - `scripts/tests/test_ci_bootstrap.py`
  - `scripts/tests/test_ci_docs_toolchain.py`
  - `scripts/tests/test_l1_release.py`
  - `l0/tests/test_release_tag_policy.py`

## Summary

Replace the moving Ubuntu runner alias with explicit job-role baselines. Compiler CI, documentation producers,
repository checks, routing, and release/publication utilities use Ubuntu 26.04. Linux release and snapshot distribution
builders use Ubuntu 24.04, as do L1 artifact acceptance builders and their matching fresh verification jobs. The latter
retains the pre-migration native build environment instead of silently increasing system-library requirements.

This pins the operating-system release, not an immutable runner image or package set. It does not establish a minimum
supported Linux distribution or glibc version. Hosted compatibility and actual-artifact acceptance remain required.

## ADR Impact

- Decision: Pin hosted Ubuntu operating-system releases according to existing CI and artifact job roles.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: These replaceable hosted environment selections preserve the existing compiler, artifact acceptance,
    documentation, and publication contracts without defining a new Linux support guarantee or architectural boundary.

## Implementation and verification

1. Pin direct CI and utility runners and generated compiler CI matrices to `ubuntu-26.04`.
2. Pin Linux distribution matrices in both levels' release/snapshot workflows and L1 productization acceptance to
   `ubuntu-24.04`, including matching verification matrices. Keep documentation producers on Ubuntu 26.04.
3. Document the two baselines and cover generated CI selections, static artifact matrices, and utility runners with
   focused workflow regressions. Preserve job commands, compiler flags, trace selection, and non-Ubuntu platforms.
4. Run short workflow tests, release-policy checks, workflow lint, ADR Impact checks, staged whitespace, and pre-commit.
   Do not run aggregate suites, native rebuilds, full PDF builds, package installations, or containers locally.
5. Review hosted compiler CI and Linux release/acceptance evidence before closing this plan. Remote writes, workflow
   dispatches, tags, and publication are outside this local change and require their normal separate authorization.

## Verification criteria

- No workflow uses the moving Ubuntu runner alias.
- Generated Linux compiler CI selections and all Ubuntu utility/documentation jobs use Ubuntu 26.04.
- Both L0 native distribution builders and all six L1 release/snapshot/acceptance builder and verifier lanes use Ubuntu
  24.04.
- Workflow steps, dependencies, compiler/runtime controls, and non-Ubuntu matrix entries retain their existing behavior.
- Local focused checks pass; hosted validation and native artifact compatibility remain explicitly pending.

## Local results

All 36 moving-alias selections in 12 workflows are replaced: 28 CI/utility selections use Ubuntu 26.04 and eight native
artifact build/verification lanes use Ubuntu 24.04. Existing documentation producers retain Ubuntu 26.04. Workflow diffs
contain only runner-label replacements. The shared monorepo guide records both baselines and their limits.

The workflow regressions exercise generated Linux matrices for Unified CI and all three standalone levels, static native
artifact matrices, and every direct Ubuntu utility/documentation runner. Changed assertions compare runner labels and
structured matrix values; they do not add native filesystem-path comparisons or Windows-specific branches.

## Local validation

- From the repository root,
  `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py scripts/tests/test_ci_docs_toolchain.py scripts/tests/test_l1_release.py --tb=short`:
  330 passed in 38.78 seconds.
- From `l0/`, `../.venv/bin/python tests/test_release_tag_policy.py`: PASS.
- `actionlint -config-file <temporary-config>`: passed for all workflows. The temporary configuration allows the
  `ubuntu-26.04` runner label, which local actionlint 1.7.12 does not yet recognize; it does not change repository lint
  policy.
- `python3 scripts/check_adr_impact.py --all-active`: passed after plan creation.
- Final local commit gates: staged whitespace, ADR Impact, and root pre-commit.

The focused test results remain applicable after Markdown-only updates and formatting: no covered workflow, code, test,
dependency, or toolchain inputs changed after those checks, and the diff contains no unrelated modifications.

This is a hosted configuration change with no compiler/runtime implementation, compiler flags, trace commands, or trace
input edits. Validation follows the project maintainer's short-check scope. No aggregate suites, native rebuilds,
toolchain installations, full PDF builds, container builds, or remote operations were performed. Hosted compiler CI and
actual Linux artifact acceptance remain pending; keep this plan active until that evidence is reviewed.
