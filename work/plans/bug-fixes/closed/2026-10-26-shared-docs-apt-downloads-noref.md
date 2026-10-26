# Bug Fix Plan

## Bound documentation toolchain package downloads

- Date: 2026-10-26
- Status: Completed
- Title: Bound documentation toolchain package downloads
- Kind: Bug Fix
- Severity: Medium
- Scope: Shared
- Targets:
  - L0 documentation build and validation
  - L1 documentation build, validation, and productization acceptance
- Origin: Slow package downloads from the Azure Ubuntu archive
- Porting rule: Use one shared Ubuntu package setup action for every documentation producer.
- Target status:
  - L0 documentation build and validation: Implemented
  - L1 documentation build, validation, and productization acceptance: Implemented
- Subsystem: CI documentation dependencies
- Modules:
  - `.github/actions/setup-docs-toolchain/`
  - `.github/workflows/`
  - `l0/Makefile`
  - `MONOREPO.md`
- Test modules:
  - `scripts/tests/test_ci_docs_toolchain.py`
  - `l1/tests/test_docgen_workflow.py`
  - `l0/tests/test_release_tag_policy.py`

## Summary

Documentation package installation has taken 80-97 minutes, with downloads below 50 kB/s from the Azure Ubuntu archive.
Actual reference builds in those completed jobs took only a few minutes. Replace the affected mirror, bound failed fetch
retries and network inactivity, and cap installation time. Required EPS conversion utilities are installed explicitly
and command availability is checked before reference generation. Repository signatures, Doxygen selection, and Windows
Python selection remain unchanged.

## ADR Impact

- Decision: Centralize bounded APT installation for Ubuntu documentation jobs.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is an operational mirror and retry policy for replaceable CI dependencies, preserving existing
    documentation, artifact, and compiler contracts.

## Implementation and verification

1. Replace only Azure Ubuntu archive URLs with `https://archive.ubuntu.com/ubuntu` in legacy and deb822 source files and
   the hosted runner's `apt-mirrors.txt`. Preserve other repositories, security sources, mirror priorities, suites,
   components, and signing configuration.
2. Apply three APT retries per failed download and 30-second HTTP/HTTPS connection and data timeouts to index refresh
   and installation. Fail index refresh on fetch errors and keep package installation noninteractive.
3. Use one shared action in all five documentation producers with a 15-minute caller step timeout. Install EPS
   conversion utilities for LaTeX generation and preserve optional full PDF packages in reusable L0 documentation
   builds.
4. Add fast mocked source/command/failure tests and workflow coverage; run the focused policy checks, workflow lint, ADR
   checks, and pre-commit. Do not install packages, build containers, run compiler suites, or rebuild references
   locally. The project team will validate installation and full builds in CI.

## Scope

This is a trace-independent CI repair. No remote write, workflow dispatch, cancellation, release, or publication is
authorized by this plan. Completion covers local implementation and short checks; hosted execution remains the next
validation step.

## Results and validation

The shared action is wired into all five producers. It invokes a standard-library Python helper after the existing
Python setup. Package acquisition uses command-local APT retry/timeout options and strict index-refresh failure
handling. Each calling step applies the 15-minute limit to the complete composite action, including package
configuration. Graphviz, Make, and optional full PDF package choices are preserved; Doxygen remains separately pinned.
`texlive-font-utils` supplies `epstopdf`, with Ghostscript supplying its conversion engine. Both are base dependencies:
Doxygen generates EPS diagrams and runs the converter during LaTeX generation, including when PDF compilation is
disabled. Setup checks `dot`, `make`, `epstopdf`, and `gs`, plus `pdflatex` and `makeindex` for PDF compilation. Missing
commands fail setup with an explicit diagnostic. Failed L0 reference builds retain their complete generation and Doxygen
warning logs as an artifact, including logs inside hidden staging directories.

The hosted runner's published source configuration and completed job logs confirm `mirror+file` indirection through
`/etc/apt/apt-mirrors.txt`. The helper rewrites that list as well as direct source entries, preserving priorities,
fallback entries, source suites/components, security URLs, signing keys, and unrelated repositories. Tests exercise this
actual format, HTTP/HTTPS variants, legacy/deb822 sources, CRLF preservation, spaces in paths, idempotence, lookalike
URLs, update/install failures, both CLI PDF selections, and missing conversion/PDF commands.

Hosted Ubuntu L0 documentation validation downloaded 276 MB in 12 seconds at 22.4 MB/s and completed package setup in 84
seconds. Subsequent reference generation exposed the missing `epstopdf` dependency, which a complete local TeX
installation had masked. The explicit dependencies and setup command checks address this environment gap.

Validation is mocked and trace-independent. No local package installation, network benchmark, container build, compiler
suite, or reference/PDF build was run. Python, uv, and MSYS2 setup definitions compare equal to their pre-change
definitions. The new focused test file is included in L0's existing CI-bootstrap test target.

`$PYTHON` below denotes the absolute shared `.venv/bin/python` path.

| Directory | Command                                                                        | Outcome                                                                                       |
| --------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Root      | `$PYTHON -m pytest -q -n 0 scripts/tests/test_ci_docs_toolchain.py --tb=short` | 34 passed in 0.28 seconds; unchanged cases reused after adding diagnostic-artifact assertions |
| `l0/`     | `$PYTHON tests/test_release_tag_policy.py`                                     | Passed                                                                                        |
| Root      | `actionlint -color`                                                            | Passed                                                                                        |
| Root      | `python3 scripts/check_adr_impact.py --all-active`                             | Passed                                                                                        |

After adding failure-log retention checks, the focused command
`$PYTHON -m pytest -q -n 0 scripts/tests/test_ci_docs_toolchain.py -k every_docs_producer --tb=short` passed all five
producer cases in 0.16 seconds; the other 29 unchanged cases retain their preceding passing result.

Passing results remain valid after documentation formatting and plan closure because their tested source, workflow,
dependency, and toolchain inputs have not changed. Actual Ubuntu installation, throughput, and full reference builds
remain CI validation for the project team.
