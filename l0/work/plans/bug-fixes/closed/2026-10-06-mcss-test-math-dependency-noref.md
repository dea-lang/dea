# Bug Fix Plan

## Isolate optional math tools from m.css compatibility tests

- Date: 2026-10-06
- Status: Closed
- Title: Remove host Ghostscript discovery from Doxygen compound-name tests
- Kind: Bug Fix
- Severity: Medium
- Stage: 1
- Subsystem: Test tooling
- Modules:
  - `l0/compiler/stage1_py/tests/cli/test_docgen_mcss_compat.py`
- Repro: `make test` in `l0/` fails during test collection with a libgs discovery error.

## Findings and implementation

The compound-name regression imports the full m.css renderer during collection. Its optional `latex2svg` dependency
probes Ghostscript and raises when libgs 10 is installed outside `/usr/lib` and `/usr/lib64` and a recent `dvisvgm` is
unavailable. Compound-name checks do not render math.

Load the renderer in a module-scoped fixture with scoped empty math-module substitutes. Restore both substituted module
entries and the entire import path, including the plugin path appended by m.css. Unexpected math usage must fail, and
production documentation rendering keeps its real dependencies.

## Validation

- Reproduced the reported collection error with the focused compatibility test file.
- The existing four compatibility cases pass after isolating imports.
- A direct loader check with native-library discovery forced to raise succeeds and confirms restoration of `sys.path`
  and both optional math-module entries.
- Full L0 `make test` passes: 1,575 Stage 1 tests, 58 Stage 2 tests including triple bootstrap, all 8 examples, runtime
  build-flag tests, distribution packaging, build/install workflows, distribution fallback, release policy, and source
  shuffling checks.
- Markdown formatting, whitespace, copyright headers, and ADR impact checks pass.

Validation used GCC 14.2.0 with `L0_CC=gcc`. Native checks ran outside the sandbox's UID remapping to preserve actual
filesystem ownership for compiler temporary-directory checks. This test-only change is trace-independent.

## ADR Impact

- Decision: Isolate unused optional rendering tools in compound-name unit tests.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a local test-fixture correction with no production compiler or documentation-renderer design
    change.
