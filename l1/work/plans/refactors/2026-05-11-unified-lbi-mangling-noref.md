# Refactor Plan

## Unify the LBI mangling scheme into a single recursive grammar

- Date: 2026-05-11
- Status: Draft
- Title: Unify the LBI mangling scheme into a single recursive grammar
- Kind: Refactor
- Severity: High
- Stage: L1
- Subsystem: Mangler / demangler / codegen / ABI spec
- Modules:
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/docs/specs/compiler/abi.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
- Related:
  - `l1/docs/specs/compiler/abi.md`
  - `l1/work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md`
- Repro: `make -C l1 test-stage1`

## Summary

The current LBI uses a two-layer scheme: a **link-name layer** (broad `S` sigil for functions, let bindings, structs,
and enums) plus a **type-component layer** (finer-grained `N` / `S` / `E` plus full type encodings). The split exists as
a compatibility scaffold. With no shipped binaries to preserve, the split costs more than it buys.

This refactor collapses both layers into one recursive grammar. Every LBI-mangled name uses a single end-to-end
encoding:

- Functions: `__deaM<...>N<name>F<arity><params><ret>`
- Plain bindings (`let`, `const`): `__deaM<...>N<name>`
- Struct types: `__deaM<...>S<name>`
- Enum types: `__deaM<...>E<name>`
- Module lifecycle: `__deaM<...>I<name>` (unchanged)

This is an ABI-breaking change at the symbol-name level. It must land before L1's first stable release.

## Current State

1. `cem_mangle_lbi` in `l1/compiler/stage1_l0/src/c_emitter.l0:400` emits `__deaM<...>S<name>` for every source-level
   entity — functions, let bindings, structs, and enums alike.
2. `cem_mangle_struct_name`, `cem_mangle_enum_name`, `cem_mangle_function_name`, and `cem_mangle_let_name` all delegate
   to `cem_mangle_lbi` with `"S"`, producing identical link-name shapes regardless of entity kind.
3. The type-component grammar is fully specified in `l1/docs/specs/compiler/abi.md` §Type-Component Layer but is not yet
   emitted into link names by the mangler.
4. There is no standalone demangler; the test suite in `l1/compiler/stage1_l0/tests/c_emitter_test.l0` validates mangled
   strings directly against expected literals.

## Defaults Chosen

1. `N` for all value entities (functions and plain bindings). A trailing type component distinguishes functions
   (present) from bindings (absent).
2. `S` for struct types, `E` for enum types — matching the type-component grammar already specified in `abi.md`.
3. `I` for lifecycle symbols — unchanged.
4. Plain bindings (`let`, `const`) do not encode their types. Rationale: bindings cannot be overloaded, so the type adds
   verbosity without capability. This follows the Itanium/Rust/Go convention; revisit only if a concrete use case
   appears that interface-file hashing cannot cover.
5. `unsafe func(...)` carries `X` in the trailing type component (e.g. `N<name>XF<arity>...`), making safe/unsafe
   mismatches link errors at the static-linker level for Dea-to-Dea calls.
6. The migration is a single atomic change. There is no parallel emission, dual demangling, or version negotiation
   period; L1 is pre-release.
7. `main` receives no special mangling case. It mangles as `__deaM4mainN4mainF0v` (or `F0i`, etc.) matching its declared
   return type. The codegen entry-point shim calls the correctly-mangled user `main` — this is already the implemented
   mechanism.

## Goal

1. Replace the broad-`S` link-name layer with the unified `N` / `S` / `E` / `I` terminal grammar.
2. Extend the mangler to emit trailing type components (function signatures) for value terminals.
3. Update all mangling tests to cover the worked-examples table verbatim.
4. Update `abi.md` to describe only the unified scheme; remove all two-layer scaffolding.
5. Verify that `dea_opt_s_*` / `dea_opt_e_*` helper-name generation still produces valid C identifiers.
6. Verify or add an interface-file format-version bump if the format records mangled names.

## Unified grammar

```ebnf
lbi-name        = "__dea" module-section terminal
module-section  = "M" (length identifier)+
terminal        = value | struct-type | enum-type | lifecycle
value           = "N" length identifier [ type-component ]
struct-type     = "S" length identifier
enum-type       = "E" length identifier
lifecycle       = "I" length identifier
type-component  = <as defined in l1/docs/specs/compiler/abi.md §Type-Component Layer>
```

Valid section orderings:

```text
M N            value (function or binding)
M S            struct type
M E            enum type
M I            lifecycle
```

## Worked examples

| Source                                    | Before                     | After                       |
| ----------------------------------------- | -------------------------- | --------------------------- |
| `main::main` (`func() -> void`)           | `__deaM4mainS4main`        | `__deaM4mainN4mainF0v`      |
| `std.math::abs` (`func(int) -> int`)      | `__deaM3std4mathS3abs`     | `__deaM3std4mathN3absF1ii`  |
| `std.io::prints` (`func(string) -> void`) | `__deaM3std2ioS6prints`    | `__deaM3std2ioN6printsF1cv` |
| `demo.main::Point` (struct)               | `__deaM4demo4mainS5Point`  | `__deaM4demo4mainS5Point`   |
| `demo.main::Color` (enum)                 | `__deaM4demo4mainS5Color`  | `__deaM4demo4mainE5Color`   |
| `demo.main::static` (`let` named static)  | `__deaM4demo4mainS6static` | `__deaM4demo4mainN6static`  |
| `unsafe func(int*) -> void` exported      | `__deaM<...>S<name>`       | `__deaM<...>N<name>XF1Piv`  |
| Lifecycle `demo.main::init`               | `__deaM4demo4mainI4init`   | `__deaM4demo4mainI4init`    |

## Implementation Phases

### Phase 1: Mangler and tests

1. Add `cem_mangle_lbi_type_component` (or equivalent) to `c_emitter.l0` to encode a function signature as a
   type-component string using the grammar already specified in `abi.md`.
2. Split `cem_mangle_lbi` into distinct helpers:
   - `cem_mangle_lbi_value` — emits `__deaM<...>N<name>` for bindings, `__deaM<...>N<name><type>` for functions.
   - `cem_mangle_lbi_struct` — emits `__deaM<...>S<name>`.
   - `cem_mangle_lbi_enum` — emits `__deaM<...>E<name>`.
   - Keep `cem_mangle_module_lifecycle_name` (already correct `I`).
3. Update `cem_mangle_struct_name`, `cem_mangle_enum_name`, `cem_mangle_function_name`, and `cem_mangle_let_name` to
   delegate to the new helpers.
4. Update `c_emitter_test.l0` to assert the new mangled shapes for all worked examples plus stress cases: deeply-nested
   types, long module paths, unsafe function pointers in nominal-type contexts.
5. Do **not** update `abi.md` yet — spec and code land together.

### Phase 2: Codegen sweep and helper audit

1. Run `make -C l1 test-stage1`. Regenerate golden files for any test that asserts mangled names as literals.
2. Grep the repo for `__deaM` literals in non-test sources (linker scripts, runtime headers, handwritten C bridges) and
   update each occurrence.
3. Audit `dea_opt_s_*` and `dea_opt_e_*` helper-name generation: `S` becomes `S` for structs (unchanged) and `E` for
   enums. Confirm helper identifier generation still produces valid C identifiers after the terminal-sigil change.
4. Check `interface_emitter.l0` and `module_interface.l0`: if interface files embed mangled names, bump the format
   version and invalidate any cached interface files in CI.
5. Verify debug-info round-trip: build a small binary, inspect symbol names under GDB/LLDB or `nm`, confirm the new
   names appear correctly.

### Phase 3: Spec and documentation

1. Rewrite `l1/docs/specs/compiler/abi.md` to describe only the unified scheme. The "Link-Name Layer" and
   "Type-Component Layer" section headings collapse into one. Remove or rewrite all text that justifies the two-layer
   split.
2. Update any internal docs or roadmap assumptions that reference `__deaM...S...` as the current LBI spelling.
3. Add a `CHANGELOG`-style note in the roadmap `Completed milestones` when this plan closes: "LBI mangling unified — old
   broad-`S` names are not produced or accepted."

### Phase 4: Cleanup

1. Remove `cem_mangle_lbi` (the old broad-`S` function) once all callers have migrated.
2. Confirm no feature flags or compatibility shims were introduced; this migration should be purely atomic.

## Diagnostics

No new diagnostic-code family is introduced by this refactor. All changes are in the mangler and codegen path, not in
the diagnostic reporting path.

## Non-Goals

1. Not a rework of the type-component grammar. Builtin sigils, modifier semantics, array layout, and function-type
   encoding all stay as currently specified in `abi.md`.
2. Not a rework of runtime helper names. `dea_opt_*`, `dea_func_*`, and other handwritten C names remain outside the
   LBI.
3. Not introducing overloading as a language feature.
4. Not changing C-level lowering of `unsafe` function pointers; they continue to share C typedef spellings.
5. Not changing the FFI / `extern` path; declarations that bypass LBI mangling continue to do so.
6. Not adding a `dea-demangle` tool in this plan. The demangling algorithm is described for documentation and
   future-tool purposes; a standalone CLI demangler is a separate deliverable.

## Risks and Mitigations

| Risk                                                                        | Mitigation                                                                                                                                                      |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mangled names exceed host C compiler identifier limits.                     | ISO C99 guarantees 31 significant chars; modern toolchains support thousands. Add a CI check that fails on names >2048 chars to catch pathological cases early. |
| Test fixtures miss a baked-in name and silently pass on stale data.         | Grep for `__deaM` literals before merging; verify each match is regenerated or explicitly updated.                                                              |
| Interface files embed mangled names and are not invalidated.                | Audit `interface_emitter.l0` and `module_interface.l0`; bump format version if needed.                                                                          |
| `dea_opt_e_*` helper names break when `S` → `E` for enums.                  | Audit helper-name generation before merge; the alphabet change is within `[A-Za-z0-9_]`, so breakage is unlikely but must be confirmed.                         |
| Debug info breaks subtly.                                                   | End-to-end test: build a small binary, verify function names resolve under GDB/LLDB.                                                                            |
| `unsafe` link-name awareness causes unexpected link errors in mixed builds. | Pre-merge: identify any place where a safe function pointer is currently assigned from an unsafe source and fix at the source.                                  |

## Open Questions

1. **Interface-file format bump.** Confirm whether `module_interface.l0` / `interface_emitter.l0` records mangled names
   or canonical source-level names. If the former, a format-version bump is required; if the latter, no action needed.
   Resolve during Phase 2.

2. **Generics and monomorphization.** Out of scope. The unified grammar is forward-compatible: monomorphized
   instantiations will encode type parameters as type components when generics land. No action now.

3. **Lifecycle symbols and types.** `I` stays untyped. If future lifecycle hooks need typing, the spec extends
   naturally. No action now.

## Verification Criteria

1. `make -C l1 test-stage1` passes with regenerated goldens.
2. A new test suite in `c_emitter_test.l0` covers every worked-example row verbatim, mangling each.
3. `abi.md` describes only the unified scheme; no references to a two-layer split remain.
4. No symbol in a clean build matches the old `__deaM...S...` pattern for non-struct entities.
5. `unsafe` function symbols carry `X` in their link names; a deliberate safe/unsafe mismatch between modules produces a
   link error rather than a silent C-level type-pun.
6. `dea_opt_e_*` helper names for enum types remain valid C identifiers after the `S` → `E` terminal change.
