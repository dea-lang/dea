# Bug Fix Plan

## Safe level cleanup targets

- Date: 2026-10-10
- Status: Completed
- Title: Safe and complete cleanup across language levels
- Kind: Bug Fix
- Severity: High
- Stage: Shared
- Scope: Shared
- Subsystem: Build cleanup tooling
- Modules: `scripts/dea_tooling/cleanup.py`, `l0/Makefile`, `l1/Makefile`, `l2/Makefile`
- Test modules: `scripts/tests/test_cleanup.py`
- Targets:
  - L0 cleanup targets and direct cleanup API
  - L1 cleanup targets
  - L2 cleanup targets
- Origin: L0 cleanup contract and shared Python implementation
- Porting rule: All levels use the same deletion validation and target semantics.
- Target status:
  - L0: Implemented
  - L1: Implemented
  - L2: Implemented
- Repro: `make -n -C l1 clean-runtime L1_BUILD_DIR=`

## Summary

Preserve the distinction between standard local cleanup and complete configured build-tree cleanup. Reject unsafe paths
before any deletion, retain custom layout support, and propagate deletion failures.

## ADR Impact

- Decision: Repair existing cleanup semantics and enforce deletion boundaries.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is a bounded build-tooling correctness fix, with no compiler or architectural contract change.

## Findings and implementation

- L0 previously permitted source directories as cleanup destinations and suppressed deletion errors.
- L1/L2 full cleanup previously left custom compiler artifacts, and empty runtime roots expanded to system paths.
- Standard cleanup previously missed hidden build artifacts.
- Shared destination validation and deletion helpers are used across level Make targets and L0's direct cleanup API.
- All destinations are validated before deletion. Empty, root, external, source-owned, and symlink/junction roots are
  rejected.
- Keep `clean` scoped to standard build outputs and known transient executables; `clean-all` also removes the complete
  selected build tree. Runtime cleanup removes its generated objects, libraries, and copied public headers only.

## Verification and outcome

- Root `make clean` completed for all three levels. Root `make test` then passed for L0, L1, and L2 with
  `L0_CC=/usr/local/bin/tcc`, `L0_ASAN_CC=/usr/bin/clang`, `L1_CC=/usr/bin/clang`, `L1_RUNTIME_CC=/usr/bin/clang`,
  `L2_CC=/usr/bin/clang`, `L2_RUNTIME_CC=/usr/bin/clang`, and
  `L2_BOOTSTRAP_L1C=/private/tmp/dea-l1-split-optimized/bin/l1c`. Python was 3.14.7, TinyCC was 0.9.28rc on x86_64
  Darwin, and Apple Clang was 17.0.0 with the required configuration support.
- The initial root `make clean test` run without `L0_ASAN_CC` failed two existing quarantine ASan cases: the
  TinyCC-selected binaries emitted no sanitizer diagnostics. Explicit Clang ASan selection resolved the validation
  configuration; no sanitizer implementation or test was changed.
- The shared cleanup suite passed 101 tests, with one inapplicable L0 runtime-only case skipped. It ran through each
  level's normal tooling gate. Coverage includes absolute and relative custom paths with spaces, complete tree removal,
  hidden files, rejected source/root/external/traversal paths, aliases, repeated cleanup, unexpected executable
  directories, runtime-header boundaries, and deletion errors.
- An L2-only fixture checkout passed 43 cleanup tests and skipped 59 cases requiring absent siblings or inapplicable
  level targets. The L2 Docker allowlist includes this generic regression file without adding sibling trees.
- Synthetic Windows path checks cover mixed separators, spaces, source-name case, drive paths, and UNC paths. Native
  Windows validation and the Docker isolation gate were not run; native validation was on macOS Intel.
- The selected gate is normal `test`: this change only affects cleanup and its tests, with no compiler, runtime, or
  trace behavior changes. No ADR is required. Current cleanup semantics are documented in `MONOREPO.md`.
