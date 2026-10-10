# Bug Fix Plan

## Verify ASan instrumentation before accepting a compiler

- Date: 2026-10-10
- Status: Completed
- Title: Reject compilers that accept ASan flags without instrumenting memory accesses
- Kind: Bug Fix
- Severity: Medium
- Stage: Shared
- Scope: Shared
- Subsystem: Sanitizer test capability detection
- Modules: `scripts/asan_test_support.py`
- Test modules: `l0/compiler/stage1_py/tests/cli/test_asan_test_support.py`
- Targets:
  - L0 sanitizer harnesses
  - L1 sanitizer harnesses
  - L2 sanitizer harnesses
- Origin: Shared capability detector
- Porting rule: All consumers use the shared probe without level-specific compiler exclusions.
- Target status:
  - L0: Implemented
  - L1: Implemented
  - L2: Implemented
- Repro: `L0_CC=tcc make -C l0 test-stage1`

## Summary

The previous probe only compiled and ran an empty C program. TinyCC accepts sanitizer flags but does not instrument
memory accesses, so that probe falsely enabled tests that require ASan diagnostics. The shared detector now requires
successful normal startup and a nonzero exit with the expected ASan heap-buffer-overflow report from a deliberately
invalid read. Compiler selection and same-compiler retries remain unchanged.

## ADR Impact

- Decision: Strengthen the existing ASan capability check without changing compiler-selection policy.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This repairs test-tooling capability detection and does not change language, runtime, or compiler
    contracts.

## Scope and method

- Retain exact configured compiler identity and the same-compiler non-PIE retry.
- Preserve optional skips for an ordinary unsupported compiler and hard failures for an explicit ASan compiler request.
- Keep both probe executions bounded, capture the expected diagnostic, and disable core dumps through ASan options.
- Add regressions for ignored flags, unrelated crashes, zero-exit reports, timeouts, and working instrumentation.
- Document capability selection and run real TinyCC negative controls plus a Clang positive control.

## Verification evidence

- Native macOS controls used `/usr/local/bin/tcc` (0.9.28rc) and `/usr/bin/clang` (Apple Clang 17).

- Real detector controls rejected ordinary TinyCC with an optional skip, rejected explicit TinyCC ASan requests with
  `AsanUnavailableError`, and accepted Clang only after observing its heap-buffer-overflow diagnostic.

- Focused Stage 1 helper and quarantine tests passed with TinyCC: 10 passed, 2 expected ASan skips, and 6 subtests. The
  two quarantine tests also passed with `L0_ASAN_CC=/usr/bin/clang`.

- `L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang .venv/bin/python l1/compiler/tests/runtime_quarantine_asan_test.py`
  passed; the same command with TinyCC selected and `L1_ASAN_CC` unset reported the expected optional skip.

- With ordinary Clang selection and sanitizer overrides unset,
  `.venv/bin/python l1/compiler/tests/vector_aliasing_test.py` and
  `.venv/bin/python l2/compiler/tests/vector_aliasing_test.py` passed their sanitizer cases.

- This is trace-independent test-tooling work: it changes capability detection without changing compiler/runtime
  behavior, ARC or memory trace inputs, trace flags, or trace execution. The normal root gate plus focused sanitizer
  controls is the applicable validation tier. Native Linux and Windows execution were not performed.

- Root `make test` passed with `L0_CC=/usr/local/bin/tcc`, `L1_CC=/usr/bin/clang`, `L1_RUNTIME_CC=/usr/bin/clang`,
  `L2_CC=/usr/bin/clang`, `L2_RUNTIME_CC=/usr/bin/clang`, and
  `L2_BOOTSTRAP_L1C=/private/tmp/dea-l1-split-optimized/bin/l1c`. All three `L<N>_ASAN_CC` variables were explicitly
  unset. The invocation used `UV_OFFLINE=1`, `UV_CACHE_DIR=/private/tmp/dea-uv-cache`, and
  `PYTHON=/Users/guglielmo/.local/share/mise/installs/python/3.14.7/bin/python3`. L0 Stage 1 reported 1612 passed and 2
  expected ASan skips; Stage 2 passed all 58 tests. L1 and L2 normal compiler, tooling, and example gates passed,
  including L1 productization. These results cover the final code and test inputs.
