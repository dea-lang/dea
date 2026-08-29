# Feature Plan

## Public C Runtime Declaration Header

- Date: 2026-08-29
- Status: Completed
- Title: Add a public L0 C runtime declaration header
- Kind: Feature
- Severity: Medium
- Stage: Shared
- Subsystem: C runtime / C FFI / installation and distribution
- Target release: L0 2.1.0
- Modules:
  - `l0/compiler/shared/runtime/dea_rt.h`
  - `l0/compiler/shared/runtime/l0_runtime.h`
  - `l0/examples/c_interop`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_runtime_public_header.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_source_scope.py`
  - `l0/compiler/stage2_l0/tests/l0c_build_run_test.py`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_install_prefix_test.py`
  - `l0/tests/test_make_dea_build_workflow.py`
  - `l0/tests/test_make_dist_workflow.py`
- Related:
  - `l0/docs/decisions/0005-extern-func-ffi-boundary.md`
  - `l0/docs/decisions/0025-runtime-trace-source-provenance.md`
  - `l1/docs/decisions/0027-runtime-archive-and-trace-selection-boundary.md`
- Repro: `cd l0/examples/c_interop && l0c --run --c-source c_add.c --c-source c_multiply.c c_interop`

## Summary

Add `dea_rt.h` as L0's public declaration-only C runtime header. Additional C translation units include `dea_rt.h`,
while generated L0 C continues to include `l0_runtime.h` exactly once and therefore remains the single owner of the
header-only runtime implementation.

This is a backward-compatible public C API addition and targets L0 2.1.0 under Semantic Versioning. It is not a 2.0.1
patch because it adds an installed header, `dea_*` aliases, and supported external `rt_*` linkage.

## ADR Impact

- Decision: Keep L0's runtime implementation header-only while adding a public declaration-only C FFI header.
  - Scope: L0
  - Disposition: New ADR
  - ADR: `l0/docs/decisions/0027-public-c-runtime-header.md`
  - Rationale: The installed public-header boundary, symbol ownership model, and cross-level compatibility promise are
    durable L0 architecture.
- Decision: Preserve generated Dea trace provenance while declaration-only C callers use stable runtime wrapper symbols.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0025-runtime-trace-source-provenance.md`
  - Rationale: Direct C callers cannot consume generated-code location macros without leaking private `_rt_*`
    interfaces, so the existing trace contract needs an explicit FFI-wrapper rule.

## Compatibility Contract

1. `dea_rt.h` provides the L1-compatible subset of `dea_*` types, value macros, and `rt_*` functions supported by L0.
2. Existing `l0_*` names remain canonical in L0 and `dea_*` spellings are source aliases.
3. Portable C shared between L0 and L1 uses `dea_*`, public `rt_*`, and `DEA_*` value macros only.
4. Compiler-private `_rt_*` helpers, allocation-tracker structures, level-mangled record tags, configuration macros, and
   runtime packaging are outside the cross-level compatibility surface.
5. The common subset is source and representation compatible; L0 and L1 objects or runtime implementations are not
   binary-interchangeable.
6. L0 retains its generated-translation-unit implementation owner. L1 retains its `libdea_rt*.a` archive model.
7. The exact portable subset comprises all shared scalar `dea_*` types; `dea_string`; `dea_opt_bool`, `dea_opt_byte`,
   `dea_opt_int`, and `dea_opt_string`; the corresponding `DEA_*` string/optional macros; and identically typed common
   `rt_*` string, process/environment, scalar-time, file-content, stream/I/O, memory, and hash functions. The
   level-record functions `rt_time_unix`, `rt_time_monotonic`, and `rt_file_info` are L0-only at the C source level
   because their struct tags differ from L1. L1's wider optional and numeric-printing APIs are not supplied by L0.

## Implementation

- Move L0 ABI type declarations into `dea_rt.h`, retain the existing `l0_*` names, and add corresponding `dea_*` aliases
  plus storage-free `L0_*` and `DEA_*` string/optional value macros.
- Declare the `rt_*` functions represented by `sys.rt`, `sys.memory`, and `sys.hash`. Keep `_rt_*` helpers and tracker
  details private to `l0_runtime.h`.
- Include `dea_rt.h` from `l0_runtime.h`, remove duplicate type declarations, externalize the public `rt_*`
  implementations, and make accidentally external compiler helpers private.
- For trace-sensitive functions, provide stable external wrappers for foreign C while preserving the generated-C macros
  that capture Dea source locations.
- Update the C interop example, installed/distribution assertions, runtime tests, stable docs, and generated API source
  coverage.

## Verification Criteria

- Two additional C translation units can include `dea_rt.h` and link with one generated L0 translation unit without
  duplicate definitions.
- Both `l0_*` and `dea_*` type spellings compile; the documented common `dea_*`/`rt_*` subset agrees with L1.
- Public `rt_*` symbols link in normal, traced, basic-checked, and unchecked builds without changing generated trace
  provenance.
- Stage 1 and Stage 2 run the updated C interop example and print the expected results.
- Install-prefix and distribution layouts contain `shared/runtime/dea_rt.h`.
- Strict docs generation and the full trace-sensitive L0 validation suite pass.

## Non-Goals

- Splitting L0 into a compiled runtime archive.
- Making L0 and L1 runtime binaries interchangeable.
- Publishing L0 2.1.0, creating a release tag, or performing any remote write.

## Completion Notes

- Added declaration-only `dea_rt.h`, made `l0_runtime.h` include it as the single generated-translation-unit
  implementation owner, externalized public `rt_*` symbols, and retained private `_rt_*` helpers.
- Preserved generated Dea trace provenance through macros while adding stable foreign-C wrapper symbols with the
  documented `<runtime>:0` fallback.
- Updated the C interop example, installed/distribution coverage, generated API source coverage, stable docs, ADR-0025,
  and new ADR-0027. The compatibility surface and L0 2.1.0 minor-version target are explicit.
- Added cross-mode linking tests that type-check and resolve every public runtime symbol plus a portable-source and ABI
  layout comparison against L1. The focused suite passed under tcc and clang.
- Validation passed: strict docs generation; 1,489 Stage 1 tests; all 56 Stage 2 tests; all examples and workflow/
  distribution tests; and all 33 Stage 2 trace checks with no leaks.
- An independent read-only review found one test-strength gap. The typed-link, diagnostic-as-error, and cross-level
  layout coverage resolved it; the reviewer's final follow-up found no remaining defect.
