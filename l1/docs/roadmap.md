# Dea/L1 Roadmap

Version: 2026-04-27

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
  [design-decisions](reference/design-decisions.md) unless the reference set is deliberately updated.
- The L1 public C ABI should continue using the `dea_*` / `DEA_*` naming policy. Historical `l0_*` names are not part of
  the current L1 ABI, and the internal SipHash helper now uses the level-local `dea_siphash.h` name.
- The first L1 productization steps should remain bootstrap-oriented until a later plan explicitly makes L1 a release
  line.

## Completed milestones

<details>
<summary>These are the major completed milestones that shape the current L1 baseline (click to expand).
</summary>

- Feature [2026-04-03-dea-virtual-module-noref](../work/plans/features/closed/2026-04-03-dea-virtual-module-noref.md)
  introduced the compiler-synthesized `dea` prelude module that contains `sizeof` and `ord` intrinsics.
- Feature
  [2026-04-04-l1-dea-c-abi-prefix-migration-noref](../work/plans/features/closed/2026-04-04-l1-dea-c-abi-prefix-migration-noref.md)
  moved L1 public generated/runtime C ABI names to `dea_*` / `DEA_*`.
- Feature
  [2026-04-04-l1-prefixed-int-literals-noref](../work/plans/features/closed/2026-04-04-l1-prefixed-int-literals-noref.md)
  added hexadecimal, binary, and octal integer literals for L1.
- Feature
  [2026-04-04-l1-small-int-builtins-on-dea-abi-noref](../work/plans/features/closed/2026-04-04-l1-small-int-builtins-on-dea-abi-noref.md)
  added `tiny`, `short`, and `ushort` builtin integer types.
- Feature
  [2026-04-10-l1-numeric-literal-lexer-groundwork-noref](../work/plans/features/closed/2026-04-10-l1-numeric-literal-lexer-groundwork-noref.md)
  established the broader numeric-literal lexer/token groundwork.
- Feature
  [2026-04-04-l1-float-double-literals-noref](../work/plans/features/closed/2026-04-04-l1-float-double-literals-noref.md)
  added builtin `float` and `double` types plus real literals.
- Feature
  [2026-04-13-l1-float-backend-contract-followup-noref](../work/plans/features/closed/2026-04-13-l1-float-backend-contract-followup-noref.md)
  defined the L1 floating-point semantic and C backend contract.
- Feature [2026-04-14-l1-std-real-module-noref](../work/plans/features/closed/2026-04-14-l1-std-real-module-noref.md)
  added the `std.real` / `sys.real` floating-point library surface, scoped runtime helper inclusion, and math-library
  linkage gating.
- Feature
  [2026-04-13-l1-uint-long-ulong-bigint-builtins-noref](../work/plans/features/closed/2026-04-13-l1-uint-long-ulong-bigint-builtins-noref.md)
  added `uint`, `long`, and `ulong` through contextual bigint literals.
- Feature
  [2026-04-14-l1-std-math-wide-integer-followup-noref](../work/plans/features/closed/2026-04-14-l1-std-math-wide-integer-followup-noref.md)
  added L1-only `std.math` helper families for `uint`, `long`, and `ulong`.
- Feature
  [2026-04-18-l1-bitwise-operators-noref](../work/plans/features/closed/2026-04-18-l1-bitwise-operators-noref.md) added
  `&`, `|`, `^`, `~`, `<<`, and `>>` with parser precedence, integer typing, and direct C lowering.
- Feature
  [2026-04-18-string-equality-operators-noref](../work/plans/features/closed/2026-04-18-string-equality-operators-noref.md)
  wired `==` and `!=` over `string` operands through typing and the C backend via `rt_string_equals`.
- Feature
  [2026-04-18-string-relational-operators-noref](../work/plans/features/closed/2026-04-18-string-relational-operators-noref.md)
  wired `<`, `<=`, `>`, and `>=` over `string` operands through typing and the C backend via `rt_string_compare`.
- Feature
  [2026-04-23-single-statement-loop-and-match-bodies-noref](../work/plans/features/closed/2026-04-23-single-statement-loop-and-match-bodies-noref.md)
  relaxed `while`, `for`, and `match` arm bodies from `Block` to `Stmt` while preserving body-local scope and cleanup.
- Feature
  [2026-04-18-l1-const-declarations-noref](../work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md)
  added top-level `const` declarations with explicit types, compile-time-constant initializers, and `static const` C
  emission.
- Feature
  [2026-04-17-l1-let-non-constant-initializers-noref](../work/plans/features/closed/2026-04-17-l1-let-non-constant-initializers-noref.md)
  added deferred module-init lowering for non-constant top-level `let` initializers and restored `std.real` NaN/infinity
  constants.
- Feature
  [2026-04-19-nullable-identity-equality-noref](../work/plans/features/closed/2026-04-19-nullable-identity-equality-noref.md)
  added strict `T? == T?` equality with same-inner-type payload comparison and explicit-cast requirement for cross-form
  `T? vs T` compares.
- Feature
  [2026-04-19-pointer-identity-equality-noref](../work/plans/features/closed/2026-04-19-pointer-identity-equality-noref.md)
  added `==` and `!=` over same-type non-nullable `T*` operands using reference identity.
- Feature [2026-04-20-is-intrinsic-noref](../work/plans/features/closed/2026-04-20-is-intrinsic-noref.md) introduced the
  `is(x, Variant)` intrinsic for payload-ignoring enum tag comparison, including qualified variant references and
  enum-returning call expressions in first position.
- Feature
  [2026-04-18-l1-function-pointer-types-noref](../work/plans/features/closed/2026-04-18-l1-function-pointer-types-noref.md)
  added first-class `func(...) -> T` function pointer types, indirect calls, nullable function pointers, and
  same-signature identity comparisons.
- Refactor
  [2026-04-24-runtime-static-library-split-noref](../work/plans/refactors/closed/2026-04-24-runtime-static-library-split-noref.md)
  moved the copied L1 runtime from header-only inclusion to public headers plus normal/traced runtime archives and
  completed Initiative [0002-runtime-static-library](../work/initiatives/0002-runtime-static-library.md).
- Feature
  [2026-04-24-export-manifests-and-aliased-imports-noref](../work/plans/features/closed/2026-04-24-export-manifests-and-aliased-imports-noref.md)
  added module-level export manifests plus alias and selective import resolution for the separate-compilation
  initiative.

</details>

## Active initiatives

- Initiative [0001-separate-compilation-and-linking](../work/initiatives/0001-separate-compilation-and-linking.md)
  covers separate compilation, interface verification, and external-library linking.
- Initiative [0003-c-ffi](../work/initiatives/0003-c-ffi.md) adds the typed C boundary: `extern "C"` declarations,
  `cstr`, and the closed FFI-safe surface.

## Active standalone plans

- Tool
  [2026-04-02-l1-bootstrap-productization-noref](../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md)
  defines the first L1 bootstrap install/dist/product workflow.
- Tool
  [2026-04-17-l1-child-process-trace-support-noref](../work/plans/tools/2026-04-17-l1-child-process-trace-support-noref.md)
  adds child-process trace capture support for Stage 1 runtime fixtures.
- Feature
  [2026-04-22-string-concatenation-operator-noref](../work/plans/features/2026-04-22-string-concatenation-operator-noref.md)
  adds the first `string + string` concatenation plan and ARC result-ownership contract.
- Feature [2026-04-22-variadic-functions-noref](../work/plans/features/2026-04-22-variadic-functions-noref.md) scopes
  variadic support to L1-defined functions and leaves C variadic FFI under Initiative `0003`.
- Feature [2026-04-22-named-arguments-noref](../work/plans/features/2026-04-22-named-arguments-noref.md) adds
  `name: value` call-site arguments for functions and constructors.
- Feature
  [2026-04-22-anonymous-embedded-struct-members-noref](../work/plans/features/2026-04-22-anonymous-embedded-struct-members-noref.md)
  defines `_ : StructType` as a single first-position anonymous embedded struct member with promoted field access.
- Feature
  [2026-04-24-lbi-symbol-mangling-and-linkage-noref](../work/plans/features/2026-04-24-lbi-symbol-mangling-and-linkage-noref.md)
  adopts `__dea...` LBI emitted names and export-driven backend linkage.
- Feature
  [2026-04-24-module-interface-emission-noref](../work/plans/features/2026-04-24-module-interface-emission-noref.md)
  introduces deterministic textual `.l1m` interface emission and loading.
- Feature
  [2026-04-24-separate-compilation-driver-surface-noref](../work/plans/features/2026-04-24-separate-compilation-driver-surface-noref.md)
  adds `-c`, `-I`, and the compile-orchestration driver surface for separate compilation.
- Feature
  [2026-04-24-interface-fingerprints-and-object-metadata-noref](../work/plans/features/2026-04-24-interface-fingerprints-and-object-metadata-noref.md)
  adds `.l1m` fingerprints, consumer verification, and provider-object metadata checks.
- Feature
  [2026-04-24-multi-cu-initialization-and-link-order-noref](../work/plans/features/2026-04-24-multi-cu-initialization-and-link-order-noref.md)
  adapts `_dea_init` ordering and executable-wrapper initialization to the multi-CU build model.
- Feature
  [2026-04-24-external-library-linking-cli-noref](../work/plans/features/2026-04-24-external-library-linking-cli-noref.md)
  adds `-l`, `-L`, `--rpath`, and `--link-arg` as the external-library linking surface.
- Feature [2026-04-24-c-ffi-extern-c-and-cstr-noref](../work/plans/features/2026-04-24-c-ffi-extern-c-and-cstr-noref.md)
  adds `extern "C"` declarations, `cstr`, and the typed non-variadic C boundary.

## Backlog

These items are future directions that need plans or initiatives before implementation. Items with partial current
coverage call out the implemented baseline so the backlog does not imply missing work where L1 already has a narrower
surface.

### Language core

- Separate compilation, interface verification, and external-library linking are tracked by Initiative
  [0001-separate-compilation-and-linking](../work/initiatives/0001-separate-compilation-and-linking.md).
- Runtime-library split from header-only inclusion to real archives is tracked by Initiative
  [0002-runtime-static-library](../work/initiatives/0002-runtime-static-library.md).
- Full C FFI, including C boundary string design and C variadic FFI, is tracked by Initiative
  [0003-c-ffi](../work/initiatives/0003-c-ffi.md).
- String operators: `==`, `!=`, `<`, `<=`, `>`, and `>=` now compare `string` values by content bytes through
  `rt_string_equals` and `rt_string_compare`, consistent with `case`-over-string lowering, `std.string::eq_s`, and
  `std.string::cmp_s`. String concatenation via `+` is tracked by Feature
  [2026-04-22-string-concatenation-operator-noref](../work/plans/features/2026-04-22-string-concatenation-operator-noref.md),
  which is intended to settle the ARC result-ownership design.
- Varargs are split explicitly: L1-defined variadic functions are tracked by Feature
  [2026-04-22-variadic-functions-noref](../work/plans/features/2026-04-22-variadic-functions-noref.md), while C variadic
  FFI remains part of Initiative [0003-c-ffi](../work/initiatives/0003-c-ffi.md).
- Lambdas/closures, including capture, ownership, and lowering rules.
- Generics and generic modules.
- Typed arrays, buffers, shared buffers, and slices as general language features. The current `std.array` / `std.vector`
  surface is library-level storage, not typed language-level arrays or slices.
- Unsafe module boundaries and raw pointer operations, including address-of (`&`) semantics and pointer indexing /
  addressing gates. Current `sys.unsafe` is a low-level runtime binding only. Same-type non-null pointer identity
  equality is implemented; ordered pointer comparisons remain rejected.
- `_` struct-member semantics are tracked by Feature
  [2026-04-22-anonymous-embedded-struct-members-noref](../work/plans/features/2026-04-22-anonymous-embedded-struct-members-noref.md),
  which fixes `_ : StructType` as a single first-position anonymous embedded struct member and defines its construction,
  field-access, layout, and ABI rules.
- Named arguments for functions and constructors are tracked by Feature
  [2026-04-22-named-arguments-noref](../work/plans/features/2026-04-22-named-arguments-noref.md).
- Literal struct/enum syntax using `{}` and named fields. Constructor-call syntax exists today; literal syntax does not.
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

- Self-hosted `stage2_l1` compiler implementation and eventual Stage 1/Stage 2 parity validation.
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
- General RTTI/reflection beyond a narrow `is` predicate.
- Traits, interfaces, or mixins.
- Macros.
- Alternate non-C backends such as LLVM, WASM/JS, JVM, or Go.
- Package management, manifests, and dependency resolution.
