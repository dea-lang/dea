# Tool Plan

## Report native preparation capability in L1 CI

- Date: 2026-09-14
- Status: Completed
- Title: Report native preparation capability in L1 CI
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Native preparation validation and CI
- Modules:
  - `l1/scripts/check_preparation_reuse.py`
  - `.github/actions/l1-ci/action.yml`
  - `.github/workflows/ci.yml`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_reuse_report_test.py`
- Repro: `python3 scripts/check_preparation_reuse.py --c-compiler clang --expect available` from `l1/`.

## Summary

Add a bounded capability reporter beside the strict preparation integrations. The reporter resolves the exact requested
executable independently of the test fixtures' compiler fallback. Local input-stability and tool-observation failures
are inconclusive errors, not compatibility baselines. Integration includes the repaired Windows compiler probes and does
not change production preparation semantics.

## ADR Impact

- Decision: Expose existing preparation evidence as a CI capability report.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This tooling change measures the existing preparation contract without changing compiler semantics, cache
    policy, supported toolchains, or the validation matrix.

## Scope and approach

1. Copy toolchain inputs and use a fresh writable cache. Run a tiny `std.io` consumer in separate cold, ordinary warm,
   and guarded warm processes. Verify output, compiler identity, publication, validation counts and preparation work.
2. Change only a copied runtime header, require guarded rejection, then rebuild a new persistent key.
3. Distinguish available reuse, repeated successful private preparation, recognized unsupported resolution, unexpected
   errors and missing bootstrap. Preserve JSON, Markdown, and subprocess logs even when expectations fail.
4. Run reporting outside the test runner, including after Make failure, and publish summaries/artifacts on failure.
   Route action-only changes through unified CI. Keep all matrix changes separate.

## Verification criteria

- Exercise classification and failure publication with deterministic fixtures, including the investigation's error
  shapes, compiler substitution, malformed/missing counters, private repetition and invalidation regressions.
- Run the real reporter with the exact local compiler, then the normal L1 suite. This is trace-independent tooling;
  compiler sources, runtime behavior, strict tests and trace invocation remain unchanged.
- Validate workflow structure/routing and staged ADR, whitespace and pre-commit checks.

## Implementation and validation

### Initial reporter validation

- Added the reporter, focused falsification tests, CI summary publication, and action-only push/PR routing. Existing
  strict integrations, compiler sources, cache policy and both matrix definitions remain unchanged.
- The real `/usr/bin/clang` probe passed with Apple Clang 17 on macOS x86_64. Cold and invalidated ordinary runs each
  compiled 23 modules in 33 preparation build commands. Both warm modes performed zero module compilations and zero
  preparation build commands, with one native resolution and one bundled validation. Header invalidation rejected the
  old profile and rebuilt a new key. Ordinary warm discovery performed four probes and 47 artifact reads; guarded warm
  discovery performed four probes and zero artifact reads. These are observations, not portable thresholds.
- The six focused unit tests include 20 failure scenarios, exact executable attribution, private and unsupported
  outcomes, missing bootstrap, retained timeout output, and stale-report cleanup. They also passed via normal Stage 1
  test discovery. Real missing-compiler and missing-bootstrap CLI runs retained failing JSON and Markdown in observation
  mode.
- `actionlint .github/workflows/ci.yml` passed. Temporary workflow probes checked composite shell syntax, summary
  publication with present/missing reports in both shell scripts, and action-only push/PR routing. Windows path
  conversion was simulated locally; native hosted Windows execution subsequently passed as recorded below.
- A new complete reporter sequence using `--c-compiler /opt/local/bin/gcc-mp-15 --expect observe` passed as `private`
  with MacPorts GCC 15.2. Both ordinary processes successfully compiled 23 modules in 33 build commands, published no
  manifest, and reported `opaque subordinate compiler-tool wrapper cannot authorize persistent reuse`. Guarded reuse
  failed with `L1C-2159` and the same reason. This observed boundary differs from the investigation's archive-wrapper
  reason; the investigation's failed first invocation was not used as an expected compatibility outcome.
- The initial L1 `UV_CACHE_DIR=/tmp/dea-uv-cache make test` run passed 80 tests and failed the unchanged
  `preparation_identity_test.py` in `check_sdk_configuration`:
  `toolchain probe timed out: compiler implementation libraries` for Apple Clang. This remains an unexpected observation
  error, not an accepted private/unsupported outcome. The isolated
  `../.venv/bin/python compiler/stage1_l0/scripts/run_tests.py --verbose preparation_identity_test.py` rerun passed
  without source changes or relaxed assertions. The successful original cases were reused rather than repeating the full
  suite. A separate invocation of the same SDK library inspector also succeeded. The cause of the original timeout
  remains inconclusive.
- Completed the L1 normal checks skipped after that failure: `UV_CACHE_DIR=/tmp/dea-uv-cache make test-env` passed, and
  `../.venv/bin/python ../scripts/check_examples.py --compiler build/dea/bin/l1c-stage1 --examples-dir examples --extension .l1 --label 'L1 Stage 1'`
  passed all four examples using the already validated bootstrap artifact.
- L0 normal validation uses
  `UV_CACHE_DIR=/tmp/dea-uv-cache L0_TEST_JOBS=4 PYTEST_XDIST_AUTO_NUM_WORKERS=4 make test DEA_BUILD_DIR=build/ci-reporter-l0`
  to avoid changing the upstream compiler used by concurrent L1 tests. Its 1,526 Python tests, 58 Stage 2 tests
  (including strict triple bootstrap), eight examples and all workflow/distribution checks passed.
- Validation uses the trace-independent `test` tier: this change does not alter compiler/runtime behavior, ownership,
  generated code, trace inputs or trace invocation. Subsequent edits only closed/formatted documentation; code and tests
  remain unchanged from the passing focused checks and isolated rerun. Staged ADR, whitespace and pre-commit checks are
  required before the local commit. No remote write, hosted CI dispatch or matrix expansion is part of this change.

### Integrated CI verification

- The integrated root `make clean test` passed with Clang selected for both levels and four test workers: 1,526 L0
  Python tests, 58 L0 Stage 2 tests, 82 L1 normal tests, both levels' environment/workflow checks, and eight L0 plus
  four L1 examples. No dedicated trace sweep was needed because compiler/runtime sources and trace behavior are
  unchanged.
- The six reporter regression tests passed independently and through normal L1 test discovery. A real missing-compiler
  invocation failed as `error` and retained JSON and Markdown reports rather than claiming a compatibility outcome.
- The integrated real reporter passed `--expect available` with `/usr/bin/clang`, Apple Clang 17.0.0 (clang-1700.6.4.2),
  targeting macOS x86_64. Cold preparation compiled 23 modules with 33 build commands; ordinary and guarded warm runs
  reused the same persistent entry with zero compilations or build commands. Header invalidation rejected the old
  profile and rebuilt 23 modules under a new key. JSON, Markdown, command records and subprocess logs were retained,
  including the expected guarded failure.
- Workflow lint, action-only routing, shell syntax, and present/missing summary publication checks passed. Windows path
  conversion was simulated locally. All 88 local links in the edited documentation resolve.

The earlier successful hosted portability run did not contain this reporter. A subsequent Unified CI run included it and
passed all four platform jobs. Each reporter independently passed `--expect available` with the selected compiler:

| Platform              | Selected compiler                           | Persistent reuse |
| --------------------- | ------------------------------------------- | ---------------- |
| Linux x86_64          | GCC 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) | Available        |
| Windows UCRT64 x86_64 | GCC 16.1.0 (MSYS2 Rev5)                     | Available        |
| macOS Intel           | Apple Clang 17.0.0 (clang-1700.0.13.5)      | Available        |
| macOS ARM64           | Apple Clang 21.0.0 (clang-2100.1.1.101)     | Available        |

Both macOS reporters resolved `/usr/bin/clang`; Linux resolved `/usr/bin/gcc`, and Windows resolved
`D:/a/_temp/msys64/ucrt64/bin/gcc.EXE`. All four reported the same preparation results:

- Cold preparation compiled 23 modules with 33 build commands.
- Ordinary and guarded warm runs reused the same persistent entry with zero module compilations and build commands.
- A header edit caused guarded rejection, followed by ordinary preparation of 23 modules under a new persistent key.
- Every invocation performed one bundled validation and one native resolution.

Hosted summary publication succeeded on every platform. This verifies persistent reuse separately from overall suite
success; no private fallback was accepted. The results cover these tested configurations, not arbitrary compiler
versions or an expanded support matrix.
