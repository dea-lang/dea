# ADR-0027: Public C Runtime Header

- Decision date: 2026-08-29
- Last edited: 2026-08-29
- Status: Accepted

## Context

L0 emits one generated C translation unit whose inclusion of `l0_runtime.h` owns the complete header-only runtime.
Additional C translation units can be supplied with `--c-source`, but including `l0_runtime.h` in each of them repeats
runtime definitions and produces duplicate symbols. Re-declaring ABI types and functions by hand avoids the link error
but creates an unsupported, drifting FFI surface.

L1 already names its public C runtime header `dea_rt.h`. L0 needs a similarly named public interface while retaining its
deliberately different header-only implementation and existing `l0_*` ABI spellings.

## Decision

1. `compiler/shared/runtime/dea_rt.h` is L0's installed declaration-only C runtime interface beginning with L0 2.1.0. It
   may contain ABI type and struct definitions, function prototypes, and storage-free value macros, but no function
   bodies or file-scope object definitions.
2. Additional C translation units include `dea_rt.h`. Generated L0 C continues to include `l0_runtime.h` exactly once;
   `l0_runtime.h` includes `dea_rt.h` and owns the runtime implementation.
3. Public runtime functions use external `rt_*` symbols. Compiler helpers named `_rt_*`, allocation-tracker details,
   configuration machinery, and other implementation data remain private to `l0_runtime.h`.
4. Existing `l0_*` type names remain supported. Equivalent `dea_*` aliases and `DEA_*` value macros define the portable
   naming convention for C shared with L1.
5. The cross-level compatibility surface contains the shared scalar `dea_*` types, `dea_string`, four shared optional
   types, corresponding `DEA_*` storage-free value macros, and identically typed common `rt_*` functions. This is source
   compatibility plus compatible representation for those common types, not binary interchangeability of L0/L1 objects
   or runtime implementations.
6. Level-mangled records, `_rt_*` names, tracker structures, build-mode and tracing configuration macros, and runtime
   packaging are outside the cross-level surface. L0 retains generated-translation-unit ownership; L1 retains its
   runtime archive model.
7. Trace-sensitive generated calls keep location-capturing macros. The same public names also have stable external
   wrappers for foreign C callers, whose trace provenance is the explicit fallback `loc="<runtime>":0`.

Consequently, `rt_time_unix`, `rt_time_monotonic`, and `rt_file_info` are L0-specific C declarations despite matching
function names in L1, because their record tags are level-mangled. L1-only wider optionals and numeric print functions
are not added to L0.

## Rationale

- One declaration header lets arbitrarily many C translation units share the exact supported ABI without defining the
  runtime more than once.
- `dea_*` gives portable cross-level C a common vocabulary while preserving source compatibility for existing L0 code.
- Keeping the implementation header-only avoids adding an archive or linker-selection model to L0.
- A minor-version target correctly describes a backward-compatible public API and packaging addition; a 2.0.1 patch
  would understate the new supported surface.

## Consequences

- Install prefixes and distributions must include both `dea_rt.h` and `l0_runtime.h`.
- The `sys.rt`, `sys.memory`, and `sys.hash` extern inventory and the prototypes in `dea_rt.h` must remain synchronized.
- Foreign C must not include `l0_runtime.h` or depend on private `_rt_*` helpers.
- A symbol or type present only in one level is not implicitly part of the portable L0/L1 subset.
- Adding this interface does not publish L0 2.1.0 or authorize a release tag or remote write.

## Related Plans

- [l0/work/plans/features/closed/2026-08-29-public-c-runtime-header-noref.md](../../work/plans/features/closed/2026-08-29-public-c-runtime-header-noref.md):
  introduced the declaration boundary, compatibility contract, tests, and packaging coverage

## Current Docs

- [l0/docs/reference/c-backend-design.md](../reference/c-backend-design.md): generated-unit layout and foreign C use
- [l0/docs/reference/standard-library.md](../reference/standard-library.md): public runtime extern inventory
- [l0/docs/specs/runtime/trace.md](../specs/runtime/trace.md): generated and foreign-C trace provenance
- [l0/examples/c_interop/README.md](../../examples/c_interop/README.md): end-user additional-C example
