# Feature Plan

## Explain native preparation validation work

- Date: 2026-09-24
- Status: Completed
- Title: Explain native preparation validation decisions, costs and provider selection
- Kind: Feature
- Severity: Medium
- Stage: 1
- Subsystem: Compiler driver / native preparation / capability reporting
- Modules:
  - `l1/compiler/stage1_l0/support/preparation/identity.h`
  - `l1/compiler/stage1_l0/support/preparation/storage.h`
  - `l1/compiler/stage1_l0/src/preparation/consumer.l0`
  - `l1/scripts/check_preparation_reuse.py`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_reuse_report_test.py`
- Related:
  - [l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md][identity-adr]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/work/plans/features/closed/2026-09-13-warm-preparation-validation-reuse-noref.md][warm-validation]
- Repro: `python3 l1/scripts/check_preparation_reuse.py --c-compiler clang --expect observe --observability-scenarios`

## Summary

Expose why a prepared native profile still performs toolchain observation, input hashing or artifact validation. Add
machine-readable debug records to existing `-vvv` output and paired local reporter scenarios without changing cache
keys, memo authority, provider precedence or normal compiler output.

## ADR Impact

- Decision: Add debug observations without changing preparation authority or reuse policy.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: Measurements and explanations expose the accepted preparation architecture without changing its durable
    identity, validation, storage or provider-selection decisions.

## Implementation

1. Emit schema-versioned JSON decisions for Dea input memos, toolchain observations, artifact validation and profile
   selection, including deterministic first-field metadata differences.
2. Measure inclusive preparation spans, individually labeled discovery probes and categorized content hashing. Record
   bytes actually supplied to SHA-256 without treating those bytes as total filesystem I/O.
3. Explain explicit-system-root suppression and selected `std.*`/`sys.*` providers at debug verbosity, including the
   narrower meaning of `--no-auto-prepare`.
4. Extend the reporter with monotonic command timing and opt-in paired warm, cwd, copied-cache, memo-free and explicit
   system-root scenarios. Keep cache copying an experimental observation rather than a portability promise.
5. Document the records and validate deterministic parsing, partial failures, unchanged preparation behavior and
   reporter isolation without wall-time thresholds.

## Non-goals

- Do not change native identity, memo or manifest schemas.
- Do not authorize copied caches across hosts or weaken changed-toolchain and corrupt-artifact detection.
- Do not add Docker automation or frontend, C compilation and linker phase profiling.
- Do not add or reassign diagnostics.

## Verification Criteria

- Existing capability classifications, profile keys and preparation counters retain their meanings.
- Debug output identifies memo/profile decisions, first metadata differences, probe purposes, inclusive spans, hash
  categories and selected bundled providers.
- Paired reporter scenarios preserve raw commands/logs and compare identities and providers without timing thresholds.
- Focused preparation tests and the L1 normal validation suite pass.

## Outcome

- Added schema-versioned debug observations for memo and profile decisions, deterministic metadata differences,
  inclusive preparation spans, labeled probes, categorized hashing and selected bundled providers.
- Kept normal output, preparation counters, cache identities, validation rules and provider precedence unchanged.
- Extended the local reuse reporter with monotonic command duration, structured observation summaries and isolated
  paired warm, cwd, copied-cache, memo-free and explicit-system-root scenarios.
- Documented the observation contract, timing nesting, byte-accounting limits and reporter workflow in the preparation
  reference.
- Independent review corrected six observability gaps: nondebug collection overhead, memo rejection classification,
  semantic and failed-analysis provider coverage, partial timeout parsing, explanatory Markdown comparisons and explicit
  unavailable-scenario reporting. Controlled-clock and native memo fixtures cover the corrected boundaries.

## Validation

- Focused preparation support, identity, ownership, managed-consumer and reporter tests passed.
- The live Clang reporter completed all 15 base and observability invocations, preserving raw logs and separate cache
  copy durations.
- `make -C l1 clean test` passed 84 Stage 1 tests, environment stackability, four examples and six Docker/Wine tests.
- `make -C l1 test-stage1-trace-smoke` passed all six focused trace checks with no leaked object or string pointers.
- After independent-review corrections, the six focused support, identity, ownership, preparation, managed-consumer and
  reporter suites passed, including 12 reporter unit tests. The live Clang reporter again passed all 15 invocations.
- Final normal validation reused those six unchanged passing suites and ran `make -C l1 test` with `TESTS` selecting the
  remaining 78 discovered cases. All 84 cases, environment stackability, four examples and six Docker/Wine checks
  passed. The trace-independent reporting corrections did not require another dedicated trace sweep.
- Review corrections passed the copyright, ADR Impact, Markdown and whitespace checks.

[identity-adr]: ../../../../docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[warm-validation]: 2026-09-13-warm-preparation-validation-reuse-noref.md
