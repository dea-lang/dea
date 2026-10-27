# Bug Fix Plan

## Select Ubuntu 26 documentation runners and report live phase timings

- Date: 2026-10-27
- Status: Completed
- Title: Select Ubuntu 26 documentation runners and report live phase timings
- Kind: Bug Fix
- Severity: Medium
- Scope: Shared
- Targets:
  - Shared Ubuntu documentation toolchain
  - L0 and L1 reference generation and offline bundles
- Origin: Doxygen 1.18 table rendering with Ubuntu's old tabularray package
- Porting rule: Select Ubuntu 26.04 for every documentation producer and share progress reporting across levels.
- Target status:
  - Shared Ubuntu documentation toolchain: Implemented
  - L0 and L1 reference generation and offline bundles: Implemented
- Subsystem: Documentation CI and generation
- Modules:
  - `.github/actions/setup-docs-toolchain/`
  - `scripts/docgen_progress.py`
  - `scripts/docgen_doxygen.py`
  - `l0/scripts/gen_docs.py`
  - `l1/scripts/gen_docs.py`
  - `l0/compiler/docgen/l0_docgen.py`
  - `l1/compiler/docgen/l1_docgen.py`
- Test modules:
  - `scripts/tests/test_ci_docs_toolchain.py`
  - `scripts/tests/test_docgen_progress.py`
  - `scripts/tests/test_docgen_inputs.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_stage_artifacts.py`
  - `l1/tests/test_docgen_outputs.py`

## Summary

Doxygen 1.18 uses tabularray for LaTeX parameter and field tables. Ubuntu's 2023A package is slow and exhausts the TeX
font slots used for internal integer arrays on the canonical L1 reference. The former Doxygen 1.9.8 renderer used a
different table implementation. Successful local validation used a newer TeX stack, exposing a CI compatibility gap.
Quiet wrappers also buffer whole subprocesses, hiding phase progress until completion.

Keep Doxygen 1.18 and select Ubuntu 26.04 explicitly for the five documentation-producing jobs. Ubuntu packages TeX Live
2025 from a January 2026 snapshot, including the newer tabularray improvements. Retain distribution package
installation, mirror selection, retries, optional PDF tools, and the setup timeout. Report active package/tool versions
before generation. Add phase timing and heartbeat output while preserving complete command logs, strict validation,
indexed PDFs, atomic output replacement, and bundle provenance.

## ADR Impact

- Decision: Select a modern documentation runner release and report generation phase timings.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: These are operational dependency and diagnostic changes within the existing documentation pipeline;
    compiler, artifact, publication, and source-identity contracts remain intact.

## Implementation and verification

1. Set the documentation jobs in the L0/L1 build and validation workflows and L1 productization acceptance to
   `ubuntu-26.04`. Keep other jobs and native compiler CI unchanged, including Windows Python selection and Doxygen
   1.18.
2. Report Ubuntu package versions, active tool paths and versions, and the selected tabularray release. Retain the
   existing APT package selection, bounded retries, and installation step limit without adding another installer.
3. Share live start/end/elapsed timing and heartbeat diagnostics. Relay child phase messages immediately, flush logs
   during execution, and preserve complete failure output. Identify extraction bindings, HTML/Markdown work, LaTeX
   generation/normalization, PDF compilation, and bundle verification.
4. Include new shared generator code in bundle input fingerprints. Validate the runner pin, optional package selection,
   version reporting, progress output before process completion, failure logs, phase errors, and wrapper transactions
   with short mocked checks and tiny subprocess probes only.

## Sources

- [GitHub runner availability and gradual latest-label migration](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/)
- [Ubuntu 26.04 TeX package snapshot](https://packages.ubuntu.com/resolute/tex/texlive-latex-extra)
- [tabularray 2025A performance improvements and 2025B integer-array fix](https://github.com/TeXackers/tabularray/blob/main/CHANGELOG.md)

## Local validation

- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_ci_docs_toolchain.py scripts/tests/test_docgen_progress.py scripts/tests/test_docgen_inputs.py`:
  50 passed.
- From `l0/`, `.venv/bin/python` at the monorepo root ran
  `-m pytest -q -n 0 compiler/stage1_py/tests/cli/test_docgen_stage_artifacts.py`: 31 passed.
- From `l1/`, the same interpreter ran `-m pytest -q -n 0 tests/test_docgen_outputs.py tests/test_docgen_workflow.py`:
  27 passed.
- After preserving the host environment in the portable subprocess probe,
  `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_docgen_progress.py scripts/tests/test_docgen_function_inventory.py -k 'progress or failed_group'`:
  10 passed. Earlier setup, fingerprint, and wrapper results remain valid; their covered inputs did not change.
- From `l0/`, `.venv/bin/python` at the monorepo root ran `tests/test_release_tag_policy.py`: PASS.
- `actionlint -config-file /private/tmp/dea-docs-actionlint.yaml` passed for the five changed workflows. The temporary
  configuration recognizes only the newly available `ubuntu-26.04` label missing from the local linter; no repository
  lint policy changes were needed.
- Local validation used focused tests and probes without aggregate suites, reference/PDF builds, package installs, or
  remote operations. Hosted validation supplies the remaining acceptance evidence.

## Portable progress-log validation

Progress logs are UTF-8 regardless of the host's default text encoding. Every progress-test read selects UTF-8
explicitly while retaining live flushing, invalid-byte replacement, failure status, complete logs, and verbosity checks.
A temporary CP1252-default-read simulation reproduces the two affected failures without that selection and passes all
nine progress cases with it. This macOS simulation is separate from the confirmed hosted validation.

## Completion and hosted validation

The project maintainer confirmed on 2026-10-27 that the final implementation passed hosted CI and approved closure. The
confirmed CI result resolves the outstanding hosted-validation gate. No quantitative rendering-speed improvement is
claimed beyond the recorded timing instrumentation and successful validation.

## Scope

This is a trace-independent CI/tooling repair. Local validation excluded long tests, TeX installation, reference/PDF
builds, container builds, remote writes, workflow dispatches, and publication. A modern compatible stack addresses the
known resource-exhaustion bug; any rendering-speed claim requires measured timing evidence.
