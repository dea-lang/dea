# Refactor Plan

## Prefer native `string` `+` operator over `std.string::concat_s` / `concat3_s` / `concat4_s` call-sites

- Date: 2026-04-30
- Status: Closed
- Title: Migrate native-code call-sites from `std.string::concat_s` / `concat3_s` / `concat4_s` helpers to the native
  `+` string concatenation operator, then retire `concat3_s` / `concat4_s` from the stdlib surface
- Kind: Refactor
- Scope: Shared
- Severity: Low
- Stage: Shared (L0 Stage 2 self-hosted, L1 Stage 1 self-hosted, shared stdlibs, examples, user-facing docs)
- Targets:
  - `l0/compiler/stage2_l0/` — source + tests
  - `l0/compiler/shared/l0/stdlib/std/` — stdlib internals that currently route through `concat*_s`
  - `l1/compiler/stage1_l0/` — source + tests
  - `l1/compiler/shared/l1/stdlib/std/` — mirrored stdlib internals
  - `examples/` under both `l0/` and `l1/`
  - User-facing docs under `l0/docs/` and `l1/docs/`
- Origin: `l0/work/plans/features/closed/...string-concatenation...` and the L1 predecessor landed native `+` for
  `string` in both levels (commits `6715650` for L0, `3ea0a8b` for L1). With both levels at parity, the `concat3_s` /
  `concat4_s` wrappers become a legacy spelling rather than a required indirection. `concat_s` itself remains the binary
  helper that backs the operator's lowering and stays in the public stdlib surface.
- Porting rule: Mechanical per-site conversion. L0 Stage 2 and L1 Stage 1 call-sites convert the same way; land them in
  mirrored chunks to keep the two self-hosted trees in lockstep. Do **not** delete `concat_s` itself — it remains the
  binary runtime helper and a public stdlib entry point. `concat3_s` / `concat4_s` are removed from the stdlib surface
  in the final phase, after every in-tree call-site has been migrated.
- Target status:
  - `l0/compiler/stage2_l0/`: Implemented
  - `l0/compiler/shared/l0/stdlib/std/`: Implemented
  - `l1/compiler/stage1_l0/`: Implemented
  - `l1/compiler/shared/l1/stdlib/std/`: Implemented
  - `examples/` (L0 + L1): No matching call-sites found
  - User-facing docs (L0 + L1): Implemented
- Subsystem: Self-hosted compiler sources, shared stdlib implementations, examples, user-facing docs
- Modules: enumerated at implementation time via `rg -l '\bconcat_s\b|\bconcat3_s\b|\bconcat4_s\b'` across the target
  subtrees — current baseline is ~469 occurrences across 24 `.l0` files in L0 Stage 2, ~604 across 28 files in L1 Stage
  1, plus stdlib internals (`path.l0`, `path.l1`) and examples/tests/fixtures (~104 across ~20 files).
- Test modules:
  - `l0/compiler/stage2_l0/tests/**/*.l0`
  - `l1/compiler/stage1_l0/tests/**/*.l0`

## Summary

Both L0 and L1 now accept the native `+` operator on `string` with the same lowering behavior as `concat_s` (and chained
applications cover the n-ary cases that `concat3_s` / `concat4_s` exist to compress). The wrappers therefore no longer
hide a capability gap — `concat3_s(a, b, c)` and `concat4_s(a, b, c, d)` just route a call through one extra layer that
linear `+` already expresses idiomatically.

This refactor converts call-sites in the native codebase to the native operator spelling, then retires `concat3_s` /
`concat4_s` from the stdlib surface in both levels. `concat_s` stays as the binary stdlib entry point and as the runtime
helper that `+` lowers to.

## Motivation

1. Readability: `a + b + c` reads more directly than `concat3_s(a, b, c)`. Every self-hosted compiler pass that builds
   diagnostic strings, qualified names, or emitted C fragments is affected.
2. Consistency with integer arithmetic and with the `==` / `!=` / `<` / `<=` / `>` / `>=` migration already landed in
   `2026-04-20-prefer-native-string-operators-noref.md` — strings should not be a special case for users reading the
   compiler sources or examples.
3. Removes a subtle didactic hazard: newcomers reading stdlib-heavy code could conclude that `+` on `string` is
   unsupported, even though it has been supported since this work unit.
4. Shrinks the stdlib surface by retiring two helpers (`concat3_s`, `concat4_s`) that exist only to paper over a
   capability gap that no longer exists.

## Conversion Rules

1. `concat_s(a, b)` → `a + b`.
2. `concat3_s(a, b, c)` → `a + b + c`.
3. `concat4_s(a, b, c, d)` → `a + b + c + d`.
4. `+` is left-associative; do not add extra parentheses around plain string concatenation chains. Preserve parentheses
   only when the surrounding expression context requires them.
5. Do not reformat surrounding code. Only the call expression changes.
6. Remove now-unused `import` / `use` of `concat3_s` / `concat4_s` from each edited file. Leave `concat_s` imports alone
   — the helper stays public and may still be referenced indirectly.
7. Any call-site where `concat_s` / `concat3_s` / `concat4_s` is passed as a first-class function value (callback table,
   comparator slot, etc.) stays. Operators are not function values in L0.
8. Tests that specifically exercise `concat_s` / `concat3_s` / `concat4_s` as public stdlib entry points stay until
   Phase 6, where the `concat3_s` / `concat4_s` tests are removed alongside their definitions.

## Non-Goals

1. Removing or deprecating `std.string::concat_s`. It remains the binary public stdlib entry point and the runtime
   helper that `+` lowers to.
2. Changing runtime helpers, ARC rules, or diagnostic codes.
3. Changing the operator's semantics or its lowering strategy.
4. Converting Stage 1 Python compiler sources — they are host-language Python.
5. Touching fixtures whose explicit purpose is to exercise the wrappers themselves (until Phase 6 retires the wrappers).

## Execution Plan

Work proceeds in phases. Each phase is verified independently before the next begins. Each chunk lands as its own commit
so any regression bisects cleanly.

### Phase 0 — Plan + baseline

This file. Snapshot exact baseline counts via `rg -nE '\bconcat[34]?_s\b'` and confirm the working tree is clean.

### Phase 1 — L0 stdlib internals (+ mechanical L1 stdlib port)

- Convert call-sites in `l0/compiler/shared/l0/stdlib/std/path.l0` (3 sites at baseline).
- Mechanically mirror the same edits in `l1/compiler/shared/l1/stdlib/std/path.l1`.
- Single commit covering both files.
- Verify: from `l0/` run `make test-stage1` and `make test-stage2`; from `l1/` run `make test-stage1`.

### Phase 2 — L1 stdlib remainder

Re-check via `rg` that no other L1 stdlib module still calls `concat3_s` / `concat4_s` outside `path.l1`. If any remain,
migrate them in one commit. Otherwise the phase is a no-op recorded inline in this plan.

### Phase 3 — L1 Stage 1 compiler (chunked)

Chunk boundaries (file lists resolved at execution time):

- **3a** examples / fixtures (`l1/.../examples/**`, `string_*_main.l1`)
- **3b** tests (`util_text_test.l0`, `math_test.l0`, `map_test.l0`, `parser_test.l0`, `diag_print_test.l0`, ...)
- **3c** compiler utility / support layer (small leaf modules, `l1c_lib.l0`)
- **3d** frontend (`lexer`, parser modules, `name_resolver.l0`, `type_resolve.l0`, `analysis.l0`, `ast_printer.l0`,
  `expr_types.l0`)
- **3e** driver / build (`driver.l0`, `build_driver.l0`)
- **3f** backend / emitter (`backend.l0`, `c_emitter.l0`)

One commit per chunk. Verify `l1/ make test-stage1` after every chunk; add `make test-stage1-trace` for chunks touching
runtime/codegen (3d, 3e, 3f).

### Phase 4 — L0 Stage 2 compiler (chunked)

Mirror of Phase 3 under `l0/compiler/stage2_l0/`:

- **4a** examples / fixtures
- **4b** tests
- **4c** compiler util / support
- **4d** frontend (`ast_printer`, `expr_types`, lexer/parser, `type_resolve`, `analysis`, `name_resolver`)
- **4e** driver / build (`driver`, `build_driver`)
- **4f** backend / emitter (`backend`, `c_emitter`)

One commit per chunk. Verify `l0/ make test-stage1` and `make test-stage2` after every chunk; `make test-all` at end of
phase.

### Phase 5 — Remaining call-sites

`rg -nE '\bconcat[34]?_s\b'` across the entire repo. Migrate any leftover `concat3_s` / `concat4_s` call-sites in
scripts, doc examples, or vendored corpora. Decide per-site whether `concat_s` stays (e.g., generator scripts that emit
Dea source code).

### Phase 6 — Retire `concat3_s` / `concat4_s` from stdlib surface

- Remove the function declarations and bodies from `l0/.../stdlib/std/text.l0` and `l1/.../stdlib/std/text.l1`.
- Remove any re-exports / symbol lists that mention them.
- Remove or fold the wrapper-targeted tests for `concat3_s` / `concat4_s`.
- Update stdlib reference docs in `l0/docs/reference/standard-library.md` and `l1/docs/reference/standard-library.md` if
  they list these symbols.
- `concat_s` is **kept**.
- A failing build here means a call-site was missed — fix forward, do not re-add the symbols.

## Verification

1. `make -C l0 test-stage1` and `make -C l0 test-stage2` after each L0-touching chunk.
2. `make -C l1 test-stage1` after each L1-touching chunk; `make -C l1 test-stage1-trace` for codegen-touching chunks.
3. `make -C l0 check-examples` and the L1 equivalent after example chunks.
4. `make -C l0 triple-test` after any Stage 2 backend/emitter chunk — strict triple-bootstrap regression must stay green
   because Stage 2 is rewriting many of its own sources.
5. `make -C l0 test-all` and `make -C l1 test-all` at the end of Phases 4 and 6.
6. Pre-commit from each affected level directory against the root config per `CLAUDE.md`.
7. Final `rg -nE '\bconcat[34]_s\b' -- ':!work/plans'` returns no matches anywhere in source, tests, examples, or docs.
8. Final `rg -nE '\bconcat_s\b'` inventory is limited to intentional survivors:
   - the public runtime helper definitions in `string.l0` / `string.l1`,
   - operator/helper parity fixtures such as `string_concat_main.l0` / `string_concat_main.l1`,
   - and targeted ARC/codegen/bootstrap regression tests that intentionally exercise the helper API or explicit
     empty-string behavior.

## Open Questions

1. Should `std.string::concat_s` itself eventually be retired in favor of `+`, leaving the runtime helper internal?
   Default answer: defer — this plan keeps the binary public entry point alongside the operator, mirroring the `eq_s` /
   `cmp_s` decision in `2026-04-20-prefer-native-string-operators-noref.md`.
2. Should the `+` operator grow an example or snippet in `l0/examples/` or `l1/examples/`? Default answer: not in this
   plan — the feature plans that landed `+` already carry driver fixtures.

## Work Completed

1. Replaced eligible `concat_s(...)`, `concat3_s(...)`, and `concat4_s(...)` call-sites with native `+` chains across L0
   Stage 2, L1 Stage 1, mirrored tests, and user-facing stdlib reference docs.
2. Removed `concat3_s` / `concat4_s` from `l0/compiler/shared/l0/stdlib/std/text.l0` and
   `l1/compiler/shared/l1/stdlib/std/text.l1`, along with their dedicated `util_text_test` coverage and doc entries.
3. Preserved intentional helper/operator coverage instead of force-converting it, including `string_concat_main`
   fixtures and ARC/codegen/bootstrap regression tests that explicitly exercise `concat_s`, `concat3_s`, or empty-string
   `+` behavior.
4. Updated `l0/docs/reference/ownership.md` and `l1/docs/reference/ownership.md` plus the shared bug-fix plan
   `work/plans/bug-fixes/closed/2026-04-30-shared-arc-owned-local-reassignment-semantics-noref.md` after the refactor
   exposed pre-existing ARC lowering bugs in L1 string reassignment paths.

## Completion Notes

The mechanical concat migration itself was straightforward. The hard part was validation: replacing wrapper calls with
native `+` exposed real ownership bugs in L1 code paths that rely on ARC-managed string replacement and optional-string
unwrapping. The final implementation therefore includes two small source-level workarounds in Stage 1 compiler code:

1. `build_driver.l0` now uses one-shot or branch-local string ownership for compiler/path resolution instead of keeping
   long-lived optional string locals alive across repeated `as string` unwraps.
2. `expr_types.l0` avoids self-referential string replacement and delayed optional-string unwraps in the diagnostic
   paths exercised by `expr_types_test` and `const`-assignment analysis.

Those fixes intentionally avoid reintroducing clone-like helpers. The broader language-level ARC assignment contract
remains documented as intended-valid in the ownership references, and the follow-up bug-fix plan remains the place to
finish compiler support for those source shapes without requiring workarounds.

## Final Verification

1. `make -C l0 test-all` — passed.
2. `make -C l1 test-all` — passed.
3. `../.venv/bin/python compiler/stage1_l0/scripts/run_test_trace.py mul_runtime_test`, `l0c_lib_test`, and
   `expr_types_test` followed by `check_trace_log.py --triage` — all reported `errors=0`, `warnings=0`, and zero leaked
   objects/strings.
4. `rg -n '\bconcat[34]_s\b' --glob '!work/plans/**' --glob '!**/closed/**'` — remaining hits are limited to intentional
   helper/regression tests outside the live self-hosted compiler and stdlib surfaces.
5. `rg -n '\bconcat_s\b' --glob '!work/plans/**' --glob '!**/closed/**'` — remaining hits are limited to the public
   helper definitions plus intentional helper/operator regression coverage; no active self-hosted compiler or
   user-facing doc/example call-sites remain.
