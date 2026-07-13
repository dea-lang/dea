# Dea/L1 Roadmap

Version: 2026-07-12

This is the live direction document for the Dea/L1 subtree. It records the current L1 position, the assumptions that
constrain future work, completed milestones that shape the baseline, active work, and backlog items that have not yet
been promoted to initiatives or plans.

L1 is currently a bootstrap subtree, not a release-bearing product. L0 remains the active user-facing release line while
L1 carries post-L0 language growth and bootstrap compiler work.

## Current position

- `compiler/stage1_l0/` is the only implemented L1 compiler today.
- `compiler/stage2_l1/` is a placeholder for a future self-hosted L1 compiler.
- The current L1 runtime and stdlib inputs live under `compiler/shared/runtime/` and `compiler/shared/l1/stdlib/`.
- The current backend emits one C99 translation unit per program.
- L1 local development defaults to the repo-local upstream L0 Stage 2 compiler at `../l0/build/dea/bin/l0c-stage2`, or
  an explicit `L1_BOOTSTRAP_L0C` override.
- Exact generated-C golden-file parity and L1 triple-bootstrap are not part of the current Stage 1 contract.

## Roadmap assumptions

- L1 should preserve the current bootstrap compiler and documented semantics unless a targeted bug fix, planned feature,
  or accepted initiative changes them.
- L1 work stays in `l1/` unless it is genuinely Dea-wide or shared with L0; shared work belongs under root `work/`.
- Closed plans document shipped L1 baseline decisions. Draft plans and active initiatives describe intended work, not
  implemented behavior.
- Any future `stage2_l1` implementation should preserve the L1 language/runtime decisions documented in
  [design-decisions] unless the reference set is deliberately updated.
- L1-defined source symbols use the unified recursive LBI grammar from
  [2026-05-11-unified-lbi-mangling-noref][unified-lbi-mangling]: value symbols use `N` terminals with trailing function
  type components where needed, nominal types use `S` / `E`, and compiler-generated module lifecycle helpers use `I`.
  Runtime/public helper families retain their documented `dea_*`, `DEA_*`, `rt_*`, and `_rt_*` roles. Historical `l0_*`
  names are not part of the current L1 ABI.
- The first L1 productization steps should remain bootstrap-oriented until a later plan explicitly makes L1 a release
  line.

## Completed milestones

<details>
<summary>These are the major completed milestones that shape the current L1 baseline (click to expand).
</summary>

- Feature [2026-04-03-dea-virtual-module-noref][virtual-module] introduced the compiler-synthesized `dea` prelude module
  that contains `sizeof` and `ord` intrinsics.
- Feature [2026-04-04-l1-dea-c-abi-prefix-migration-noref][abi-prefix] moved L1 public generated/runtime C ABI names to
  `dea_*` / `DEA_*`.
- Feature [2026-04-04-l1-prefixed-int-literals-noref][prefixed-literals] added hexadecimal, binary, and octal integer
  literals for L1.
- Feature [2026-04-04-l1-small-int-builtins-on-dea-abi-noref][small-int] added `tiny`, `short`, and `ushort` builtin
  integer types.
- Feature [2026-04-10-l1-numeric-literal-lexer-groundwork-noref][numeric-lexer] established the broader numeric-literal
  lexer/token groundwork.
- Feature [2026-04-04-l1-float-double-literals-noref][float-literals] added builtin `float` and `double` types plus real
  literals.
- Feature [2026-04-13-l1-float-backend-contract-followup-noref][float-backend] defined the L1 floating-point semantic
  and C backend contract.
- Feature [2026-04-14-l1-std-real-module-noref][real-module] added the `std.real` / `sys.real` floating-point library
  surface, scoped runtime helper inclusion, and math-library linkage gating.
- Feature [2026-04-13-l1-uint-long-ulong-bigint-builtins-noref][wide-int] added `uint`, `long`, and `ulong` through
  contextual bigint literals.
- Feature [2026-04-14-l1-std-math-wide-integer-followup-noref][wide-math] added L1-only `std.integer` helper families
  for `uint`, `long`, and `ulong`.
- Feature [2026-04-18-l1-bitwise-operators-noref][bitwise-operators] added `&`, `|`, `^`, `~`, `<<`, and `>>` with
  parser precedence, integer typing, and direct C lowering.
- Feature [2026-04-18-string-equality-operators-noref][string-equality] wired `==` and `!=` over `string` operands
  through typing and the C backend via `rt_string_equals`.
- Feature [2026-04-18-string-relational-operators-noref][string-relational] wired `<`, `<=`, `>`, and `>=` over `string`
  operands through typing and the C backend via `rt_string_compare`.
- Feature [2026-04-22-string-concatenation-operator-noref][string-concat] wired `string + string` through
  `rt_string_concat`, yielding a fresh owned result with ordinary ARC behavior.
- Feature [2026-04-23-single-statement-loop-and-match-bodies-noref][single-statements] relaxed `while`, `for`, and
  `match` arm bodies from `Block` to `Stmt` while preserving body-local scope and cleanup.
- Feature [2026-04-18-l1-const-declarations-noref][const-declarations] added top-level `const` declarations with
  explicit types, compile-time-constant initializers, and `static const` C emission.
- Feature [2026-04-17-l1-let-non-constant-initializers-noref][let-initializers] added deferred module-init lowering for
  non-constant top-level `let` initializers and restored `std.real` NaN/infinity constants.
- Feature [2026-04-19-nullable-identity-equality-noref][nullable-equality] added strict `T? == T?` equality with
  same-inner-type payload comparison and explicit-cast requirement for cross-form `T? vs T` compares.
- Feature [2026-04-19-pointer-identity-equality-noref][pointer-equality] added `==` and `!=` over same-type non-nullable
  `T*` operands using reference identity.
- Feature [2026-04-20-is-intrinsic-noref][is-intrinsic] introduced the `is(x, Variant)` intrinsic for payload-ignoring
  enum tag comparison, including qualified variant references and enum-returning call expressions in first position.
- Feature [2026-04-18-l1-function-pointer-types-noref][function-pointers] added first-class `func(...) -> T` function
  pointer types, indirect calls, nullable function pointers, and same-signature identity comparisons.
- Feature [2026-05-19-stage1-slices-len-slice-intrinsics-noref][stage1-slices] added Stage 1 slice types `T[]`,
  `dea::len`, and `dea::slice` as non-owning local/parameter/call descriptors over fixed arrays and slices.
- Feature [2026-04-22-variadic-functions-noref][variadic-functions] added L1-defined trailing `T...` parameters and
  function pointer types, slice-backed callee packs, zero-or-more positional trailing arguments, and explicit final
  `pack...` forwarding. C variadic FFI remains separate under Initiative [0003-c-ffi][c-ffi].
- Refactor [2026-04-24-runtime-static-library-split-noref][runtime-split] moved the copied L1 runtime from header-only
  inclusion to public headers plus normal/traced runtime archives and completed Initiative
  [0002-runtime-static-library][runtime-library].
- Refactor [2026-04-27-runtime-cu-resplit-noref][runtime-resplit] moved OS/process helpers and RNG into dedicated
  `dea_rt_sys.c` and `dea_rt_rand.c` runtime translation units.
- Feature [2026-04-24-export-manifests-and-aliased-imports-noref][export-imports] added module-level export manifests
  plus alias and selective import resolution for the separate-compilation initiative.
- Feature [2026-04-24-lbi-symbol-mangling-and-linkage-noref][symbol-linkage] adopted tagged-section LBI names for source
  symbols and module lifecycle helpers plus export-driven backend linkage.
- Feature [2026-04-24-module-interface-emission-noref][interface-emission] added deterministic textual `.l1m` interface
  emission, constrained parser round-trip support, and the internal `--emit-interface` mode.
- Refactor [2026-05-11-unified-lbi-mangling-noref][unified-lbi-mangling] collapsed the two-layer LBI scheme into a
  single recursive grammar, replacing the broad-`S` link-name layer with `N` / `S` / `E` / `I` terminals plus trailing
  type components for function signatures.
- Feature [2026-06-13-opaque-type-exports-and-layout-hiding-noref][opaque-exports] added `export opaque { T }`,
  exported-surface visibility checks, and opaque `.l1m` nominal declarations.
- Feature [2026-06-18-stage1-const-scalar-casts-noref][const-scalar-casts] added statically checked integer-family,
  `float`/`double`, and scalar identity casts to Stage 1 `const` initializers.
- Feature [2026-06-24-stage1-scalar-const-expression-flow-noref][scalar-const-flow] extended Stage 1 `const` evaluation
  with checked 32-bit `int` operators, short-circuit booleans, folded interfaces/static initializers, const-valued
  array/case contexts, and const-guided boolean liveness flow.
- The direct-interface replay tranche of Feature [2026-04-24-separate-compilation-driver-surface-noref][compile-driver]
  added dependency-free supplied-provider replay through semantic analysis and C generation, canonical metadata
  round-tripping, source/interface enum export parity, indexed active-provider state, and signed and aggregate literals.
- Bug Fix [2026-06-08-stage1-case-builtin-literal-support-noref][case-builtin-literals] made Stage 1 `case` arm literals
  follow equality comparability rules with warning-only always-false integer arms.
- Bug Fix [2026-06-17-stage1-contextual-array-literals-noref][contextual-array-literals] made Stage 1 check array
  literals against expected fixed-size array contexts before standalone inference.
- Bug Fix [2026-06-18-stage1-toplet-initializer-typing-noref][toplet-initializer-typing] made Stage 1 type-check
  top-level `let` initializer expressions before backend lowering records runtime initializer metadata.
- Bug Fix [2026-06-19-stage1-toplet-diagnostic-recovery-noref][toplet-diagnostic-recovery] preserved resolved top-level
  initializer diagnostics when signature resolution had already reported an error.

</details>

## Active initiatives

- Initiative [0001-separate-compilation-and-linking][separate-compilation] covers separate compilation, interface
  verification, and external-library linking.
- Initiative [0003-c-ffi][c-ffi] adds the typed C boundary: `extern "C"` declarations, `cstr`, and the closed FFI-safe
  surface.

## Completed initiatives

- Initiative [0002-runtime-static-library][runtime-library] split the L1 runtime from header-only inclusion into public
  headers plus normal and traced static archives.
- Initiative [0004-array-primitives-and-unsafe-marker][arrays-unsafe] added the function-level `unsafe` marker for
  raw-memory contracts, pointer-indexing, and fixed-size arrays.

## Active standalone plans

- Feature [2026-07-11-shared-l1-stage2-self-hosting-port-noref][stage2-self-hosting] ports the settled Stage 1 compiler
  to `.l1`, adds the Stage 2 build and test workflow, and establishes strict triple-bootstrap validation.
- Tool [2026-04-02-l1-bootstrap-productization-noref][bootstrap-productization] defines the first L1 bootstrap
  install/dist/product workflow.
- Tool [2026-04-17-l1-child-process-trace-support-noref][child-trace] adds child-process trace capture support for Stage
  1 runtime fixtures.
- Feature [2026-04-22-anonymous-embedded-struct-members-noref][embedded-members] defines `_ : StructType` as a single
  first-position anonymous embedded struct member with promoted field access.
- Feature [2026-04-24-separate-compilation-driver-surface-noref][compile-driver] adds `-c`, `-I`, and the
  compile-orchestration driver surface for separate compilation.
- Feature [2026-04-24-interface-fingerprints-and-object-metadata-noref][interface-fingerprints] adds `.l1m`
  fingerprints, consumer verification, and provider-object metadata checks.
- Feature [2026-04-24-multi-cu-initialization-and-link-order-noref][module-init] adapts `I4init` module lifecycle
  ordering and executable-wrapper initialization to the multi-CU build model.
- Feature [2026-04-24-external-library-linking-cli-noref][library-linking] adds `-l`, `-L`, `--rpath`, and `--link-arg`
  as the external-library linking surface.
- Feature [2026-04-24-c-ffi-extern-c-and-cstr-noref][ffi-cstr] adds `extern "C"` declarations, `cstr`, and the typed
  non-variadic C boundary.
- Refactor [2026-07-08-stage1-source-decomposition-noref][stage1-source-decomposition] decomposes oversized Stage 1
  production source modules while preserving public root imports and current compiler behavior.
- Feature [2026-06-21-cheap-string-slices-noref][cheap-string-slices] extends `dea::slice` to ARC-backed string views
  while preserving internal terminated copies for native runtime calls that require them.
- Feature [2026-06-30-runtime-pointer-access-validation-noref][runtime-pointer-validation] adds runtime pointer access
  validation to L1 under the shared Dea-wide pointer-safety plan; checked builds are the default and `DEA_RT_UNCHECKED`
  compiles validation out for release builds. The prebuilt archive runtime honors `DEA_RT_QUARANTINE_MAX_BYTES` and
  `DEA_RT_QUARANTINE_MAX_COUNT` environment overrides read once at first tracker use. The `l1c --check-basic` flag
  selects `libdea_rt_check_basic.a` and keeps exact-base validation while omitting the interior-pointer treap; the
  `l1c --unchecked` flag selects `libdea_rt_unchecked.a` and defines `DEA_RT_UNCHECKED` in generated C. Allocation
  provenance separates raw, `new`, ARC, static, and registered foreign storage: raw memory uses `rt_free`/`rt_realloc`,
  `new` uses extent-aware generated drop cleanup, and external lifetimes use
  `rt_register_foreign`/`rt_unregister_foreign` without transferring ownership. Content-sensitive runtime variant stamps
  rebuild archives and tcc objects when compiler flags or baked settings change.

## Backlog

These items are future directions that need plans or initiatives before implementation. Items with partial current
coverage call out the implemented baseline so the backlog does not imply missing work where L1 already has a narrower
surface.

### Language core

- Separate compilation, interface verification, and external-library linking are tracked by Initiative
  [0001-separate-compilation-and-linking][separate-compilation].
- Full C FFI, including C boundary string design and C variadic FFI, is tracked by Initiative [0003-c-ffi][c-ffi]. The
  proposed scoped conversion design is recorded in [cstr-and-c-string-guards][cstr-proposal].
- C variadic FFI remains a sibling tranche under Initiative [0003-c-ffi][c-ffi]; implemented L1-defined variadics do not
  use or expose the C varargs ABI.
- Lambdas/closures, including capture, ownership, and lowering rules.
- Generics and generic modules.
- Fixed-size typed arrays `T[N]`, raw-pointer indexing `ptr[i]` inside `unsafe func`, and the function-level `unsafe`
  marker shipped under Initiative [0004-array-primitives-and-unsafe-marker][arrays-unsafe]. First-class,
  escape-restricted slice types `T[]`, `len`, and `slice` shipped through Feature
  [2026-05-19-stage1-slices-len-slice-intrinsics-noref][stage1-slices]. Dynamic buffers, shared buffers, address-of
  (`&`), and broader pointer arithmetic remain backlog items. Current `std.array` / `std.vector` storage remains the
  library-level dynamic/container layer rather than a replacement for `T[N]` or `T[]`.
- `_` struct-member semantics are tracked by Feature
  [2026-04-22-anonymous-embedded-struct-members-noref][embedded-members], which fixes `_ : StructType` as a single
  first-position anonymous embedded struct member and defines its construction, field-access, layout, and ABI rules.
- Named arguments for function calls and struct/enum constructor calls are implemented by Feature
  [2026-04-22-named-arguments-noref][named-arguments]. Literal struct/enum syntax using `{}` and named fields remains
  future work; constructor-call syntax exists today.
- Compiler-generated `hash(T)` for struct and enum values, including its relationship to `sys.hash`, `std.hashmap`, and
  ABI stability.
- Diagnostic UX improvements: fuller messages, fix-it hints, parse recovery, and dedicated diagnostics for common
  unexpected-token cases such as `else` without `if`, `cleanup` without `with`, and stray semicolons.

### Standard library

- File-handle I/O: `open`, incremental `read` / `write`, append, and seek. Whole-file `std.fs::read_file` /
  `std.fs::write_file` and stdin/stdout byte helpers already exist.
- Directory traversal APIs. Current `std.fs` exposes path metadata and `is_dir`, but not directory iteration.
- Stream abstractions for files, standard streams, memory buffers, and later transport-backed endpoints.
- Data-format modules such as JSON and IFF.

### Runtime

- Runtime profiling hooks and reporting.
- Full call-stack tracing for runtime/compiler failure paths, separate from the current ARC and memory trace toggles.
- Custom allocators and arenas as a language/runtime facility, including their interaction with `new`, `drop`, ARC, and
  stdlib containers.

### Tooling and delivery

- Self-hosted `stage2_l1` compiler implementation and Stage 1/Stage 2 parity validation are tracked by Feature
  [2026-07-11-shared-l1-stage2-self-hosting-port-noref][stage2-self-hosting].
- Release-bearing L1 install, distribution, release, and docs-publishing workflows after the bootstrap productization
  plan lands.
- Broader L1 CI/CD and tooling beyond bootstrap packaging, including validation matrices and published artifact checks.

## Deferred direction

These items are known explicit deferrals: these are not currently planned for L1 and would require a future roadmap
update to be promoted to an initiative or plan:

- Advanced floating-point modules and intrinsics beyond the `std.real` / `sys.real` surface.
- File-watch APIs.
- Networking APIs.
- Concurrency runtime primitives, shared concurrent data structures, and CSP-style threads.
- General RTTI/reflection.
- Traits, interfaces, or mixins.
- Macros.
- Alternate non-C backends such as LLVM, WASM/JS, JVM, or Go.
- Package management, manifests, and dependency resolution.

[abi-prefix]: ../work/plans/features/closed/2026-04-04-l1-dea-c-abi-prefix-migration-noref.md
[arrays-unsafe]: ../work/initiatives/closed/0004-array-primitives-and-unsafe-marker.md
[bitwise-operators]: ../work/plans/features/closed/2026-04-18-l1-bitwise-operators-noref.md
[bootstrap-productization]: ../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[c-ffi]: ../work/initiatives/0003-c-ffi.md
[case-builtin-literals]: ../work/plans/bug-fixes/closed/2026-06-08-stage1-case-builtin-literal-support-noref.md
[cheap-string-slices]: ../work/plans/features/2026-06-21-cheap-string-slices-noref.md
[child-trace]: ../work/plans/tools/2026-04-17-l1-child-process-trace-support-noref.md
[compile-driver]: ../work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md
[const-declarations]: ../work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md
[const-scalar-casts]: ../work/plans/features/closed/2026-06-18-stage1-const-scalar-casts-noref.md
[contextual-array-literals]: ../work/plans/bug-fixes/closed/2026-06-17-stage1-contextual-array-literals-noref.md
[cstr-proposal]: ../work/proposals/cstr-and-c-string-guards.md
[design-decisions]: reference/design-decisions.md
[embedded-members]: ../work/plans/features/2026-04-22-anonymous-embedded-struct-members-noref.md
[export-imports]: ../work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md
[ffi-cstr]: ../work/plans/features/2026-04-24-c-ffi-extern-c-and-cstr-noref.md
[float-backend]: ../work/plans/features/closed/2026-04-13-l1-float-backend-contract-followup-noref.md
[float-literals]: ../work/plans/features/closed/2026-04-04-l1-float-double-literals-noref.md
[function-pointers]: ../work/plans/features/closed/2026-04-18-l1-function-pointer-types-noref.md
[interface-emission]: ../work/plans/features/closed/2026-04-24-module-interface-emission-noref.md
[interface-fingerprints]: ../work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md
[is-intrinsic]: ../work/plans/features/closed/2026-04-20-is-intrinsic-noref.md
[let-initializers]: ../work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md
[library-linking]: ../work/plans/features/2026-04-24-external-library-linking-cli-noref.md
[module-init]: ../work/plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md
[named-arguments]: ../work/plans/features/closed/2026-04-22-named-arguments-noref.md
[nullable-equality]: ../work/plans/features/closed/2026-04-19-nullable-identity-equality-noref.md
[numeric-lexer]: ../work/plans/features/closed/2026-04-10-l1-numeric-literal-lexer-groundwork-noref.md
[opaque-exports]: ../work/plans/features/closed/2026-06-13-opaque-type-exports-and-layout-hiding-noref.md
[pointer-equality]: ../work/plans/features/closed/2026-04-19-pointer-identity-equality-noref.md
[prefixed-literals]: ../work/plans/features/closed/2026-04-04-l1-prefixed-int-literals-noref.md
[real-module]: ../work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md
[runtime-library]: ../work/initiatives/closed/0002-runtime-static-library.md
[runtime-pointer-validation]: ../work/plans/features/closed/2026-06-30-runtime-pointer-access-validation-noref.md
[runtime-resplit]: ../work/plans/refactors/closed/2026-04-27-runtime-cu-resplit-noref.md
[runtime-split]: ../work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md
[scalar-const-flow]: ../work/plans/features/closed/2026-06-24-stage1-scalar-const-expression-flow-noref.md
[separate-compilation]: ../work/initiatives/0001-separate-compilation-and-linking.md
[single-statements]: ../work/plans/features/closed/2026-04-23-single-statement-loop-and-match-bodies-noref.md
[small-int]: ../work/plans/features/closed/2026-04-04-l1-small-int-builtins-on-dea-abi-noref.md
[stage1-slices]: ../work/plans/features/closed/2026-05-19-stage1-slices-len-slice-intrinsics-noref.md
[stage1-source-decomposition]: ../work/plans/refactors/2026-07-08-stage1-source-decomposition-noref.md
[stage2-self-hosting]: ../../work/plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
[string-concat]: ../work/plans/features/closed/2026-04-22-string-concatenation-operator-noref.md
[string-equality]: ../work/plans/features/closed/2026-04-18-string-equality-operators-noref.md
[string-relational]: ../work/plans/features/closed/2026-04-18-string-relational-operators-noref.md
[symbol-linkage]: ../work/plans/features/closed/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md
[toplet-diagnostic-recovery]: ../work/plans/bug-fixes/closed/2026-06-19-stage1-toplet-diagnostic-recovery-noref.md
[toplet-initializer-typing]: ../work/plans/bug-fixes/closed/2026-06-18-stage1-toplet-initializer-typing-noref.md
[unified-lbi-mangling]: ../work/plans/refactors/closed/2026-05-11-unified-lbi-mangling-noref.md
[variadic-functions]: ../work/plans/features/closed/2026-04-22-variadic-functions-noref.md
[virtual-module]: ../work/plans/features/closed/2026-04-03-dea-virtual-module-noref.md
[wide-int]: ../work/plans/features/closed/2026-04-13-l1-uint-long-ulong-bigint-builtins-noref.md
[wide-math]: ../work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md
