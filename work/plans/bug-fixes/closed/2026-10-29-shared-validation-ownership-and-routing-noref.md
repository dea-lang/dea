# Bug Fix Plan

## Keep predecessor validation independent of successor changes

- Date: 2026-10-29
- Status: Completed
- Title: Align validation ownership and CI routing with level dependencies
- Kind: Bug Fix
- Severity: High
- Scope: Shared
- Targets:
  - L0 independent validation
  - L1 compatibility validation
  - Repository validation and Unified CI routing
- Origin: Cross-level runtime checks in the L0 suite
- Porting rule: Move checks to their owning level or shared tooling; change no compiler or runtime behavior.
- Target status:
  - L0 independent validation: Implemented
  - L1 compatibility validation: Implemented
  - Repository validation and Unified CI routing: Implemented
- Subsystem: Test ownership / runtime compatibility / CI selection
- Modules:
  - `.github/workflows/ci.yml`
  - `Makefile`
  - `l0/Makefile`
  - `l1/Makefile`
  - `l2/Makefile`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage1_py/tests/cli/test_stage2_trace_log_checker.py`
  - `l1/tests/test_predecessor_compatibility.py`
  - `scripts/tests/test_ci_bootstrap.py`
  - `scripts/tests/test_shuffle_sources.py`

## Root cause

L1 widened time parameters to `long`, while an L0-hosted comparison still assumed identical L0/L1 signatures. L1-only CI
skipped that comparison. Rewritten history later hid the push comparison base from checkout; conservative routing
selected L0 and exposed the stale assumption. L0 also hosted a trace-checker comparison and shared repository checks
that inspected successor inputs.

## Scope and approach

1. Keep L0 header, linking, trace, and signature checks independent of L1 files. Move runtime and trace compatibility
   checks into L1, explicitly preserving the different time signatures and the supported common C subset.
2. Move the monorepo source-selection check into shared tooling. Run shared test modules in a repository gate instead of
   attributing their failures to a level's validation.
3. Recover missing push bases by exact object ID; compare pull requests from their merge base. Retain conservative
   selection with an explicit reason when an endpoint cannot be recovered.
4. Select downstream validation when predecessor construction or runtime inputs change. Successor-only changes never
   select predecessor compiler validation. Preserve the explicit L2 enablement policy.
5. Update the compatibility contract, validation ownership guidance, and executable routing regressions.

No language, compiler, runtime ABI, diagnostic code, release, or publication changes are required.

## Verification criteria

- The original failure is reproduced before correction; focused L0 and L1 checks then pass with their actual selected C
  compiler recorded.
- L0 checks pass when successor inputs are inaccessible; L1 checks reject incompatible common signatures and accept the
  documented time-width difference.
- Routing covers level-only changes, downstream consequences, shared changes, recovered and unavailable push bases,
  pull-request merge bases, and disabled/enabled L2 selection.
- Shared repository checks pass through their new entry point; level Make targets retain their own checks.
- Documentation links, C documentation, ADR Impact, whitespace, and root pre-commit checks pass. Hosted native results
  remain separate evidence; this local repair does not authorize a push or workflow dispatch.

## ADR Impact

- Decision: Attribute validation to its subject and follow predecessor dependencies when selecting CI workloads.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0027-validation-ownership-and-dependency-routing.md`
  - Rationale: Test ownership and downstream selection establish a lasting repository boundary that prevents successor
    changes from invalidating predecessor suites.
- Decision: Limit portable runtime compatibility to explicitly identical signatures while retaining level-specific time
  widths.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0027-public-c-runtime-header.md`
  - Rationale: The public-header contract needs its intentional time-width exception recorded without changing L0
    behavior.

## Outcome and verification

L0 declaration, linking, and trace checks retain their own coverage without reading successor files. L1's normal tooling
gate now owns the explicit common signatures, intentional time differences, common layouts, selected inherited private
helpers, and predecessor trace-format comparisons. Shared checks run through root aggregates and the native Unified CI
repository steps. CI follows construction dependencies and recovers comparison evidence before falling back.

Local validation used macOS Intel and `/usr/bin/clang`, Apple Clang 17.0.0. The original incompatible time-signature
failure was reproduced before correction. Verification commands and outcomes:

- From `l0/`,
  `L0_CC=/usr/bin/clang ../.venv/bin/python -m pytest -q -n 0 compiler/stage1_py/tests/backend/test_runtime_public_header.py compiler/stage1_py/tests/cli/test_stage2_trace_log_checker.py`:
  18 passed. The same checks passed under `/usr/bin/sandbox-exec` with `file-read*` denied for both successor subtrees.
- From `l1/`,
  `L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang ../.venv/bin/python -m pytest -q -n 0 tests/test_predecessor_compatibility.py`:
  10 passed. A temporary incorrect common signature was rejected by the actual C compiler, confirming that excluding the
  intentional time difference does not hide general signature drift.
- From the root, `.venv/bin/python -m pytest -q -n 0 scripts/tests`, followed by focused revalidation of the updated
  `scripts/tests/test_ci_docs_toolchain.py`: 665 cases validated, one skipped. The focused module passed all 39 cases.
  Routing coverage includes real Git recovery from a local rewritten remote, unavailable endpoints, PR merge bases,
  level-local selection, predecessor consumers, shared changes, and both L2 defaults.
- `l1/tests/test_docgen_make.py` passed in the focused routing and compatibility run; from `l0/`,
  `../.venv/bin/python tests/test_release_tag_policy.py` passed.
- `python3 scripts/check_c_docs.py`, ADR Impact, repository-link validation, staged whitespace, and root pre-commit
  passed.

Hosted `Unified CI` verification on 2026-10-29 passed the repository checks, `make -C l0 test-extended`, and
`make -C l1 test-ci` on all four native platforms:

| Platform       | Selected C compiler                  |
| -------------- | ------------------------------------ |
| Linux x86_64   | `/usr/bin/gcc`, Ubuntu GCC 15.2.0    |
| macOS Intel    | `/usr/bin/clang`, Apple Clang 17.0.0 |
| macOS ARM      | `/usr/bin/clang`, Apple Clang 21.0.0 |
| Windows UCRT64 | `/ucrt64/bin/gcc`, MSYS2 GCC 16.2.0  |

Each platform ran both level delegates and the separate repository-check step. L1's tooling gate passed the relocated
predecessor compatibility checks. Strict L0 and L1 documentation validation and ADR Impact also passed. L2 remained
disabled. The local successor-denial check above separately establishes L0 test independence.
