# Bug Fix Plan

## Shared builtin inventory and runtime contract observability

- Date: 2026-09-01
- Status: Completed
- Title: Canonicalize optional hash semantics, centralize builtin type-name inventories, and close runtime contract
  observability gaps
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L0 Stage 1, Stage 2, shared header runtime, and hash extern surface
  - L1 Stage 1, shared archive runtime, and hash extern surface
  - Shared checked-runtime and generated-C contract documentation
- Origin: L1 randomized source review findings and their L0 counterparts
- Porting rule: Keep level-specific builtin inventories explicit while sharing one inventory inside each compiler; port
  runtime observability and hash-contract coverage mechanically unless the L0 header and L1 archive shapes require a
  documented harness difference.
- Target status:
  - L0 Stage 1, Stage 2, shared header runtime, and hash extern surface: Implemented
  - L1 Stage 1, shared archive runtime, and hash extern surface: Implemented
  - Shared checked-runtime and generated-C contract documentation: Implemented
- Subsystem: Tokens / Builtin types / C emission / Checked runtime / Hash runtime / Tests
- Modules:
  - `l0/compiler/stage1_py/l0_lexer.py`
  - `l0/compiler/stage1_py/l0_parser.py`
  - `l0/compiler/stage1_py/l0_types.py`
  - `l0/compiler/stage2_l0/src/builtin_types.l0`
  - `l0/compiler/stage2_l0/src/tokens.l0`
  - `l0/compiler/stage2_l0/src/types.l0`
  - `l0/compiler/stage2_l0/src/type_resolve.l0`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l0/compiler/stage2_l0/src/parser/expr.l0`
  - `l1/compiler/stage1_l0/src/builtin_types.l0`
  - `l1/compiler/stage1_l0/src/tokens.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/parser/expr.l0`
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l1/compiler/shared/runtime/src/dea_rt_alloc.c`
  - `l1/compiler/shared/runtime/src/dea_rt_hash.c`
  - `l0/compiler/shared/l0/stdlib/sys/hash.l0`
  - `l1/compiler/shared/l1/stdlib/sys/hash.l1`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `docs/decisions/0021-runtime-hash-semantic-domains-and-stability.md`
  - `l0/docs/reference/architecture.md`
  - `l0/docs/reference/design-decisions.md`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/architecture.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/standard-library.md`
- Test modules:
  - `l0/compiler/stage1_py/tests/test_builtin_inventory.py`
  - `l0/compiler/stage1_py/tests/backend/test_hash_runtime.py`
  - `l0/compiler/stage1_py/tests/backend/test_runtime_quarantine_asan.py`
  - `l0/compiler/stage1_py/tests/c_emitter/test_c_emitter_runtime_contracts.py`
  - `l0/compiler/stage2_l0/tests/builtin_types_test.l0`
  - `l0/compiler/stage2_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/builtin_types_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/hash_runtime_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_quarantine_asan_test.py`
- Related:
  - `work/plans/features/closed/2026-06-30-shared-runtime-pointer-access-validation-noref.md`
  - `work/plans/bug-fixes/closed/2026-07-11-shared-checked-runtime-review-gaps-noref.md`
  - `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - `docs/decisions/0021-runtime-hash-semantic-domains-and-stability.md`
  - `l0/docs/reference/standard-library.md`
  - `l1/docs/reference/standard-library.md`
- Repro: compare the literal builtin-name predicates in tokens, types, and parser lookahead; compare absent and present
  optional-string hash domains; then run generated pointer, drop, allocation, and hash probes against checked,
  zero-retention, unchecked, and AddressSanitizer configurations

## Summary

A bounded L1 source review reported four non-defect observations: duplicated builtin type names, checked-runtime
quarantine masking sanitizer lifetime probes, generated C calls that static source-call searches cannot enumerate, and
an extern-only hash module whose C implementation was outside the seed-body review. The L1 duplicate is present in three
inventory consumers, not only `tokens.l0`; L0 repeats its smaller inventory across the corresponding layers. Both
runtimes also share the quarantine and hash implementation patterns, while all three backends emit runtime calls as
downstream C text.

The investigation demonstrated that optional scalar hashes include inactive payload bytes and C struct padding, so two
equal values crossing the C ABI can hash differently. A follow-up provenance review also found that `rt_hash_opt_string`
historically fed an absent optional and a present empty string into the exact same tagged hash domain. Source comments
and a regression test recorded that behavior, but no design rationale justified discarding the semantic presence state.
The final correction canonicalizes scalar representations, gives optional-string absence its own hash subdomain,
centralizes each level's builtin type-name inventory, makes sanitizer-backed lifetime probes observable with and without
quarantine retention, locks representative generated runtime calls to their size, alignment, provenance, ownership, and
drop contracts, and adds explicit declaration/implementation and edge-case coverage for the hash extern surface. It
preserves the intended language contracts and non-sanitized runtime behavior except for the deliberately corrected
optional hash results.

## ADR Impact

- Decision: Keep checked-runtime quarantine compatible with sanitizer lifetime diagnostics.

  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0010-checked-runtime-pointer-access-validation.md`
  - Rationale: ADR-0010 already establishes checked-by-default access validation, bounded quarantine semantics, and the
    checked runtime's role as a temporal-safety backstop; sanitizer observability is an implementation and verification
    refinement of that accepted contract.

- Decision: Give absent optional strings a distinct runtime hash input domain.

  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0021-runtime-hash-semantic-domains-and-stability.md`
  - Rationale: The closure gate requires a separate durable record because this closed plan already carries an
    independent ADR-covered quarantine decision. ADR-0021 records the cross-level semantic-domain and hash-stability
    policy without changing language equality, the runtime ABI, the hash algorithm, or compiler/object fingerprints.

## Current State

1. L1 spells the builtin type-name set independently in token reservation, the canonical type predicate, and parser type
   lookahead. The same three literals contain repeated integer names. L0 has no repeated entries, but still owns three
   independently maintained copies of its builtin set.
2. Checked runtimes retain released raw and `new` storage in quarantine. That improves runtime diagnostics but can keep
   a direct stale C access addressable during an AddressSanitizer probe. Tests do not currently exercise both retained
   and zero-retention lifetime cases.
3. Emitter helpers generate `_rt_check_ptr_site`, `_rt_check_index_ptr_site`, `_rt_drop_begin_impl`,
   `_rt_drop_finish_impl`, and `_rt_alloc_obj*` calls as text. Production-source caller searches therefore cannot prove
   all emitted argument contracts.
4. The eleven `sys.hash` declarations have matching-looking runtime definitions, but L1 has no focused behavior suite
   equivalent to L0's partial hash tests, and neither level explicitly locks all declarations to C signatures plus
   empty-option, null-pointer, zero-length-data, and deterministic behavior. Falsification probes demonstrated that
   `rt_hash_opt_bool`, `rt_hash_opt_byte`, and `rt_hash_opt_int` hash inactive payload bytes and padding directly, so
   semantically equal option values can produce different hashes across the C ABI. Historical `rt_hash_opt_string`
   behavior also discards semantic presence by hashing both an absent optional and a present empty string as
   `STRING | OPTIONAL` plus zero payload bytes.

## Scope of This Fix

1. Introduce one lightweight builtin-name predicate per level and route token reservation, type recognition, and parser
   type lookahead through it. Add exhaustive positive and representative negative tests.
2. Detect AddressSanitizer builds in both runtimes and poison quarantined payload storage until eviction, unpoisoning it
   before the underlying C allocation is released. Add supported-host probes for default retention and an explicit
   zero-retention configuration; skip only when the selected C toolchain cannot build and run ASan.
3. Extend emitter and generated-C tests with representative direct, indexed, allocation, and drop paths. Assert exact
   extent, alignment, access-mode, provenance, and begin-before-cleanup/finish-after-cleanup arguments, then run the
   matching runtime behaviors.
4. Canonicalize optional scalar wrappers before hashing so inactive payloads and padding do not affect the result. Give
   absent optional strings a reserved `ABSENT` subdomain while preserving the existing present optional-string path. Add
   hash ABI and behavior probes in both levels, type-check all eleven extern signatures against the runtime header or
   generated calls, and cover empty option values, null pointer failures, zero-length non-null data, and repeated
   deterministic results.
5. Update affected stable documentation and ADR related-plan evidence. No compiler diagnostic codes are required.

## Non-Goals

- Changing the language-level builtin inventories.
- Removing or retuning checked-runtime quarantine defaults.
- Claiming that a bounded generated-C inventory enumerates every future backend output.
- Redesigning the hash algorithm, key policy, optional scalar hashing, equality semantics, or compiler/object
  fingerprint paths.
- Adding a new compiler diagnostic category or code.

## Verification Criteria

- Every builtin type accepted by one level's resolver is reserved and recognized by parser type lookahead through the
  same predicate; non-builtin identifiers remain available.
- ASan detects a direct stale payload access while checked quarantine retains the allocation and when retention is set
  to zero; ordinary checked tests retain their existing runtime diagnostics.
- Representative generated C calls pass the exact runtime-required size, alignment, index element size, access mode,
  allocation family, and drop begin/finish sequencing in L0 Stage 1, L0 Stage 2, and L1 Stage 1.
- All eleven `sys.hash` declarations type-check against their C implementations in both level shapes, and focused
  behavior covers empty options, null pointers, zero-length data, and deterministic repeat calls.
- Optional-string presence participates in the hash input domain: the present branch retains `STRING | OPTIONAL`, while
  absence uses `STRING | OPTIONAL | ABSENT`. Representative absent and present-empty hashes differ under the current
  deterministic runtime key without claiming that arbitrary 32-bit collisions are impossible.
- Focused compiler/runtime tests, trace-sensitive suites, level-appropriate aggregate validation,
  `python3 scripts/check_adr_impact.py --all-active`, `git diff --check`, and changed-file pre-commit checks pass.

## Outcome

- Added one canonical builtin-name inventory to the Python L0 bootstrap compiler and to each native L0/L1 compiler.
  Token reservation, parser lookahead, semantic recognition, type construction, and resolver paths now consume those
  inventories; the repeated L1 integer entries and incomplete expression-side list are gone.
- AddressSanitizer builds now poison quarantined user payloads and unpoison them immediately before allocator release.
  Retained blocks report `use-after-poison`; a zero-retention configuration reports ordinary heap use-after-free.
- Added exact emitted-C assertions for checked direct/indexed accesses, allocation, and drop begin/finish calls in all
  three backends. The review found their production argument contracts correct, so no emitter behavior changed.
- Verified all eleven L1 `sys.hash` declarations against typed C definitions and expanded L0 edge coverage. A
  falsification probe exposed representation-dependent optional-scalar hashes; both runtimes now zero inactive payloads
  and wrapper padding before hashing.
- Reserved flag bit `0x08` for optional-string absence in both runtimes. Present optional strings retain their existing
  `STRING | OPTIONAL` input domain, while absence uses `STRING | OPTIONAL | ABSENT`; language equality, ordinary string
  hashing, container behavior, and compiler/object fingerprinting remain unchanged.
- Refreshed the hash contracts, builtin-inventory architecture notes, checked-runtime sanitizer behavior, and ADR-0010.
  No compiler diagnostic codes or language-level builtin sets changed.

## Verification

- Focused L0 Stage 1: `20 passed`; focused native L0 Stage 2: `3 passed`; focused L1 compiler/runtime: `5 passed`.
- Root `make test-all`: L0 passed `1505` Stage 1 tests, `57` Stage 2 suites, all workflow/example checks, and `34` trace
  suites; L1 passed `72` normal suites, environment/example checks, and `45` trace suites. Every trace suite reported
  zero leaked object and string pointers.
- The final optional-string domain correction passed the focused L0 hash suite (`9` tests) and the focused L1 hash
  runtime suite before the full cross-level aggregate.
- After independent read-only review hardened ASan capability detection, the focused L0 harness passed `2` tests and the
  focused L1 harness passed its single test with the support runtime compiled and executed first.
- Retained and zero-retention ASan probes passed in both level-specific harnesses; hash ABI, deterministic edge, and
  failure-contract probes passed.
- `python3 scripts/check_adr_impact.py --all-active`, the repository copyright check, changed-file `mdformat --check`,
  and `git diff --check` passed.
- `make -C l0 docs` passed in strict mode after the final hash-contract documentation update.
