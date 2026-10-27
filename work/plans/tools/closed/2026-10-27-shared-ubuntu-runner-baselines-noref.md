# Tool Plan

## Pin hosted Ubuntu runners by job role

- Date: 2026-10-27
- Status: Completed
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
  - `.github/actions/setup-linux-temp/`
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
supported Linux distribution or glibc version. Actual-artifact acceptance remains a separate release gate.

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
3. Select disk-backed temporary storage for Unified and standalone Linux compiler CI before tool setup or testing.
   Export `TMPDIR`, `TMP`, and `TEMP` as `$RUNNER_TEMP/dea-tmp` and report its filesystem and available space.
4. Document the two baselines and cover generated CI selections, static artifact matrices, and utility runners with
   focused workflow regressions. Preserve job commands, compiler flags, trace selection, and non-Ubuntu platforms.
5. Run short workflow tests, release-policy checks, workflow lint, ADR Impact checks, staged whitespace, and pre-commit.
   Do not run aggregate suites, native rebuilds, full PDF builds, package installations, or containers locally.
6. Review hosted compiler CI and Linux release/acceptance evidence before closing this plan. Remote writes, workflow
   dispatches, tags, and publication are outside this local change and require their normal separate authorization.

## Verification criteria

- No workflow uses the moving Ubuntu runner alias.
- Generated Linux compiler CI selections and all Ubuntu utility/documentation jobs use Ubuntu 26.04.
- Both L0 native distribution builders and all six L1 release/snapshot/acceptance builder and verifier lanes use Ubuntu
  24.04.
- Linux compiler CI selects disk-backed temporary storage before tools and tests; missing runner storage fails setup.
- Build/test commands, dependencies, compiler/runtime controls, and non-Ubuntu matrix entries retain their existing
  behavior.
- Local focused checks pass, and the project maintainer confirmed passing hosted CI for the final implementation.

## Local results

All 36 moving-alias selections in 12 workflows are replaced: 28 CI/utility selections use Ubuntu 26.04 and eight native
artifact build/verification lanes use Ubuntu 24.04. Existing documentation producers retain Ubuntu 26.04. Linux compiler
CI additionally selects disk-backed temporary storage. The shared monorepo guide records both baselines and their
limits.

The runner-policy regressions exercise generated Linux matrices for Unified CI and all three standalone levels, static
native artifact matrices, and every direct Ubuntu utility/documentation runner. These assertions compare runner labels
and structured matrix values. The temporary-storage probe compares extracted native paths with same-host `Path` values;
it does not add Windows-specific branches or compare diagnostic path spelling.

## Ubuntu 26 temporary storage

Hosted Unified CI initially passed L0 and the L1 normal compiler, examples, productization, and environment checks with
`/usr/bin/gcc` reporting Ubuntu GCC 15.2.0. The L1 dedicated trace sweep failed while draining captured output with
`OSError: failed to drain captured process output: [Errno 122] Disk quota exceeded`. Its artifact root is under `/tmp`.
Ubuntu 26.04 runner images can mount `/tmp` as a quota-limited RAM-backed filesystem. This matches the reproduced
upstream failure documented in
[actions/runner-images issue 14777](https://github.com/actions/runner-images/issues/14777).

The shared Linux setup action creates `$RUNNER_TEMP/dea-tmp` and selects it through all three standard temporary-path
environment variables for subsequent job steps. This covers Python trace artifacts and compiler/tool scratch files in
Unified CI and all three standalone compiler workflows without changing trace contents, analyzer rules, parallelism,
compiler flags, or the Ubuntu release/artifact pins. Setup uses no privileged mount operations and reports the selected
filesystem and capacity. The explicit directory avoids dependence on upstream runner-image repair rollout.

Focused regressions execute the real Bash setup with a runner directory containing spaces and an apostrophe, then start
a fresh Python subprocess that creates and writes a temporary trace artifact under the exported directory. Missing or
empty runner storage fails before environment publication. Wiring checks require the Linux guard and setup ordering
before tool setup and compiler delegates. These local POSIX checks do not reproduce the hosted tmpfs mount or establish
completion of the full Linux trace sweep.

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

The temporary-storage repair has separate focused coverage for the shared action and four compiler workflow entrypoints:

- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py -k 'linux_temp or ubuntu or generated_linux_ci or workflow_handoffs or doxygen_setup or l0_manual' --tb=short`:
  42 passed, 188 deselected in 1.90 seconds with CPython 3.15.2 and the locked shared environment.
- `actionlint -config-file <temporary-config>`: passed for all workflows, with the same Ubuntu 26.04 label allowance.
- `git diff --check` and `python3 scripts/check_adr_impact.py --all-active`: passed.

## Completion and hosted validation

The project maintainer confirmed on 2026-10-27 that the final runner-baseline and temporary-storage changes passed
hosted CI and approved closure. The confirmed result resolves the outstanding hosted-validation gate. This records
acceptance of the runner policy and repair; it introduces no Linux compatibility guarantee and does not replace
actual-artifact acceptance for releases.

The focused repair results remain applicable after this Markdown-only closure; covered workflow, action, test,
dependency, and interpreter inputs are unchanged.

This is a hosted configuration change with no compiler/runtime implementation, compiler flag, trace command, or trace
input edits; the repair changes Linux temporary storage inherited by trace execution. Validation follows the project
maintainer's short-check scope. No aggregate suites, native rebuilds, toolchain installations, full PDF builds,
container builds, or remote operations were performed locally. Hosted validation is recorded above.
