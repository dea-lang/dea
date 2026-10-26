# Tool Plan

## Pin the shared CI Doxygen toolchain

- Date: 2026-10-26
- Status: Completed
- Title: Pin the shared CI Doxygen toolchain
- Kind: Tooling
- Priority: Medium
- Scope: Shared
- Targets:
  - Native compiler CI
  - Documentation build and validation CI
- Origin: Shared GitHub Actions setup action
- Porting rule: Use one upstream release and verified platform archives for all relevant jobs.
- Target status:
  - Native compiler CI: Implemented
  - Documentation build and validation CI: Implemented
- Subsystem: CI documentation toolchain
- Modules:
  - `.github/actions/setup-doxygen/`
  - `.github/workflows/`
  - `MONOREPO.md`
- Test modules:
  - `.github/actions/setup-doxygen/setup.test.cjs`
  - `scripts/tests/test_ci_bootstrap.py`
  - `l0/tests/test_release_tag_policy.py`
  - `l1/tests/test_docgen_workflow.py`
- Related:
  - `docs/reference/c-documentation.md`

## Summary

Replace ambient or distribution-selected Doxygen with upstream 1.18.0 across compiler CI and documentation producers.
Published Linux x64, macOS Intel/ARM64, and Windows x64 archives cover the current runner matrix. The shared setup
action verifies archive checksums and the executable version, then exposes the selected binary to subsequent steps.
Consistent extraction improves reference reproducibility and prevents documentation tests from silently using an older
runner-provided tool. Windows Python interpreter selection is outside this change.

## ADR Impact

- Decision: Pin the CI documentation extractor through one shared setup action.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a replaceable CI dependency selection and installation detail. It preserves existing compiler,
    documentation identity, artifact, and publication contracts without introducing an architectural boundary.

## Implementation and verification

1. Centralize the release and upstream SHA-256 checksums; reject unsupported platform/architecture combinations.
2. Download, verify, extract, check the CLI version, and publish the native binary directory through `GITHUB_PATH`.
3. Wire native compiler workflows and the five documentation producers to the setup action. Release, snapshot, and
   publication consumers inherit the pin through their existing reusable documentation workflows.
4. Test platform selection, checksum rejection, extraction, path publication, and workflow coverage. Preserve Windows
   Python setup inputs and MSYS2 package selections.
5. Build strict L0 stage references and canonical L1 references with full PDFs and verified bundles; build the L2 native
   reference. Run focused documentation regressions, workflow lint, and staged checks.

Validation is scoped to a trace-independent hosted CI/toolchain change, plus the explicitly requested real documentation
builds. Native setup and L0 documentation regressions have also passed on all four hosted platforms. No remote write,
workflow dispatch, release, or publication is part of this plan.

## Results

- The dependency-free Node 24 action selects the upstream archive, verifies its pinned SHA-256 before extraction,
  requires release 1.18.0 with optional upstream build metadata, and publishes the native executable directory and
  verified version. Installation fails before publishing a path on checksum or version errors.
- Unified CI, the three standalone compiler workflows, and five documentation producers use the action. Windows jobs
  compare MSYS2's resolved CLI output with the verified installation. Distribution-selected Doxygen installation is
  removed from documentation producers; Graphviz and TeX remain unchanged.
- All four downloaded upstream archives match their checksums and expected CLI layouts. The Linux executable uses
  standard Ubuntu runtime libraries. The actual macOS Intel action downloaded, extracted, verified, and executed its
  binary from a temporary path containing spaces; that binary is used for the documentation validation below.
- Python, uv, and MSYS2 setup steps in all nine edited workflows compare equal to their pre-change definitions.
- The existing L1 reference-workflow assertion now requires the shared action before the build, alongside its unchanged
  read-only permissions, bootstrap independence, reporting, and failure evidence checks.
- Both L0 release-policy documentation checks require the shared setup action before reference generation. They retain
  tag selection and checkout assertions without depending on the superseded version-display step name.

## Validation

Local execution uses macOS x86_64. Prepend the action-produced binary directory to `PATH`. `$PYTHON` below is the
absolute shared `.venv/bin/python` path. No compiler/runtime behavior or trace inputs changed; validation uses the
hosted CI repair exception and the explicitly requested complete documentation builds.

| Directory | Command                                                                                                                                                                                                        | Result                                                                                         |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Root      | `node --test .github/actions/setup-doxygen/setup.test.cjs`                                                                                                                                                     | 17 passed; includes simulated Windows drive, mixed-separator, UNC, space, and apostrophe paths |
| Root      | `$PYTHON -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py scripts/tests/test_l1_release.py --tb=short`                                                                                                     | 220 passed                                                                                     |
| `l0/`     | `$PYTHON -m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_*.py ../scripts/tests/test_docgen_function_inventory.py ../scripts/tests/test_c_docs.py ../scripts/tests/test_docgen_inputs.py --tb=short` | 269 passed                                                                                     |
| `l1/`     | `$PYTHON -m pytest -q -n 0 tests/test_docgen_*.py --tb=short`                                                                                                                                                  | 104 unchanged cases and seven unchanged workflow cases passed; obsolete apt assertion updated  |
| `l1/`     | `$PYTHON -m pytest -q -n 0 tests/test_docgen_workflow.py --tb=short`                                                                                                                                           | Eight passed, completing validation of all 112 distinct L1 documentation cases                 |
| `l2/`     | `$PYTHON -m pytest -q -n 0 tests/test_docgen_native.py --tb=short`                                                                                                                                             | Three passed                                                                                   |
| Root      | `actionlint -color`                                                                                                                                                                                            | Passed                                                                                         |
| Root      | `python3 scripts/check_adr_impact.py --all-active`                                                                                                                                                             | Passed                                                                                         |

The unchanged passing checks are reused after workflow-assertion updates and Markdown formatting: neither changes their
covered code, dependencies, generated inputs, or toolchain. Hosted Unified CI has verified the Node 24 setup action,
Doxygen 1.18.0 startup, and all 269 L0 documentation regressions on Linux x64, macOS Intel/ARM64, and Windows UCRT64.
The later L0 release-policy check exposed two stale assertions for the superseded version-display step. The shared setup
and documentation generation themselves passed on all four platforms.

Complete documentation builds use the same action-produced CLI and `DEA_DIST_VERSION=dev`. Both L0 stage bundles and the
canonical L1 bundle passed manifest, payload digest, and offline-link verification, with `strict` and `full_pdf` enabled
and Doxygen 1.18.0 recorded. L1's final LaTeX log has no unresolved-reference or rerun warning and its index is present.

| Directory | Command                                                                                                                         | Result                                                                                           |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `l0/`     | `make docs-artifacts PYTHON=../.venv/bin/python DEA_DIST_VERSION=dev`                                                           | Both stages passed; 839-page Stage 1 PDF and 993-page Stage 2 PDF, with verified offline bundles |
| `l0/`     | `$PYTHON -m compiler.docgen.l0_docgen_blog --stage stage2 --input build/docs/stage2/markdown --output build/docs/api-reference` | Passed                                                                                           |
| `l0/`     | `$PYTHON scripts/stage_docs_pages.py`                                                                                           | Passed                                                                                           |
| `l1/`     | `make docs-artifacts PYTHON=../.venv/bin/python DEA_DIST_VERSION=dev`                                                           | Passed; 1,863-page full indexed PDF and verified offline bundle                                  |
| `l2/`     | `make docs-pdf PYTHON=../.venv/bin/python DEA_DIST_VERSION=dev`                                                                 | Passed; strict native HTML reference and 601-page PDF                                            |

Fast validation for the L0 release-policy assertion repair:

- From `l0/`, `$PYTHON tests/test_release_tag_policy.py`: passed.
- Temporary negative probes removed or moved the setup action after generation: both documentation workflow checks
  rejected both invalid forms.
- From root, `$PYTHON -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py -k doxygen --tb=short`: passed.
- `actionlint -color`: passed.

The repair changes only the L0 policy assertions and this validation record. Existing documentation builds, toolchain
checks, and documentation regressions remain valid for unchanged inputs; compiler suites and full PDF builds are not
rerun locally. The project team will rerun CI. Every remote/publication action remains outside this local repair.
