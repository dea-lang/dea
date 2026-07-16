# L1 Language and Runtime Design Decisions

Version: 2026-07-16

This document records current design rationale and policy decisions for Dea/L1 as implemented by the bootstrap compiler.

Related docs:

- compiler structure and pass flow: [architecture.md](architecture.md)
- backend lowering details: [c-backend-design.md](c-backend-design.md)
- ownership and cleanup rules: [ownership.md](ownership.md)
- standard library surface: [standard-library.md](standard-library.md)

## 1. Scope and Goals

The current L1 bootstrap language aims to be:

- small but expressive
- practical for bootstrapping a later self-hosted compiler
- suitable for systems/runtime-oriented code
- explicit about safety boundaries
- portable through conservative C99 lowering

Policy: language-level behavior should avoid undefined behavior. Invalid programs should be rejected statically where
possible and otherwise fail in defined runtime ways.

## 2. Runtime Boundary Model

The current stack is intentionally layered:

1. L1 language and compiler
2. L1 stdlib modules under `compiler/shared/l1/stdlib/`
3. C runtime boundary through the public `compiler/shared/runtime/include/dea_rt.h` surface and the delivered runtime
   archives under `build/dea/lib/`

This keeps platform-specific behavior concentrated at the runtime boundary instead of leaking into core language
semantics.

## 3. Portability Policy

Generated code should stay within conservative C99 usage. Platform/compiler quirks belong in the runtime boundary, not
in the language definition.

Current policy also distinguishes between:

- conservative C99 usage that is acceptable as a lowering vehicle
- host/compiler behavior that is too vague to define L1 semantics directly

Where L1 semantics depend on properties not guaranteed uniformly by every C99 target, the backend must validate those
properties and reject unsupported targets rather than silently inheriting implementation-defined or underspecified host
behavior.

## 4. C ABI Naming Policy

Current L1 C ABI policy uses:

- `dea_*` for public generated/runtime C identifiers
- `DEA_*` for public generated/runtime preprocessor names
- `rt_*` for stable runtime API functions
- `_rt_*` for private runtime helpers

Historical `l0_*`, `L0_*`, `_l0_*`, and `_L0_*` names are not part of the current L1 ABI and should not be introduced in
new L1-emitted names. The emitter reserves both the historical prefixes and the current `dea` prefixes when mangling
user/source identifiers so generated C cannot collide with backend/runtime-owned namespaces.

The internal SipHash include now uses the level-local, future-neutral name `dea_siphash.h`, so L1 no longer carries a
legacy-prefixed include exception there.

## 5. Future Evolution

Near-term L1 evolution should preserve the current bootstrap implementation and semantics unless a targeted bug fix or a
decision-complete feature addition requires a deliberate change.

When `stage2_l1` is eventually implemented, it should preserve these language/runtime decisions unless the L1 reference
docs are intentionally revised.

## 6. Bootstrap Adaptation Strategy

The current L1 subtree is intentionally bootstrapped from the mature L0 toolchain rather than started from a blank
implementation.

Current policy:

- the runnable L1 compiler starts from copied L0 Stage 2 compiler sources and is retargeted inside `compiler/stage1_l0/`
- the current L1 reference set starts from copied L0 reference material and is rewritten to describe the real L1
  bootstrap tree
- copied implementation and docs are allowed to retain historical internal names when those names are merely bootstrap
  artifacts rather than user-facing semantics
- live L1-owned compiler helpers and tests should use L1-oriented names such as `l1c_*` / `l1c_lib_test` when the
  subject is the L1 compiler, even if the implementation source language remains `.l0`

Rationale:

- this keeps the first L1 compiler runnable early
- it preserves a known-good baseline while L1-specific divergence is still small
- it favors incremental retargeting over speculative greenfield design

## 7. Pointer and Ownership Policy

Current bootstrap policy includes:

- pointer types and ordered pointer/nullable suffix constructor stacks (`T*`, `T*?`, `T?*`, `T??`)
- dereference (`*expr`)
- pointer field access through the current compiler's auto-deref behavior
- postfix pointer indexing syntax (`ptr[index]`) in expressions
- explicit `new` / `drop` for heap object lifetime
- ARC-managed `string`

Equality operators (`==` and `!=`) on same-type pointer operands compare by reference identity. This contrasts with
§16's explicit refusal of `string` identity equality, as heap pointers do not share string's potential for deduplication
or re-homing. Ordered pointer comparisons remain rejected, as address ordering is not defined in L1.

No design decision has been finalized yet on whether address-of (`&`) will become part of the L1 language surface.

Current bootstrap status:

- `&` is reserved in the current implementation and is not yet assigned address-of semantics
- postfix pointer indexing is finalized as a raw-pointer operation: for `ptr: T*` and `index: int`, `ptr[index]` is
  accepted only inside `unsafe func` bodies and rejects nullable bases and `void*`
- ordinary pointer dereference (`*p`) and pointer field access remain available in safe code; only postfix pointer
  indexing is gated on `unsafe func`

`unsafe func` is a source-level contract boundary, not a promise that every build omits runtime diagnostics. In checked
runtime builds, pointer dereference, pointer field access, raw pointer indexing, and generated `drop` cleanup validate
allocation provenance, access range, writeability, and release state before touching storage. Raw allocations use
`rt_free`/`rt_realloc`; `new` allocations use the sized drop begin/finish protocol, which validates pointee extent and
alignment before cleanup. ARC/static string bytes are tracked read-only at the exposed byte pointer. External storage
requires explicit `rt_register_foreign`/`rt_unregister_foreign` lifetime registration, which never transfers ownership
or authorizes runtime release. `--check-basic` keeps exact-base hash validation, quarantine, generation caches, null
checks, double-drop and untracked-drop diagnostics, exact-base ARC/static string read-only protection, and alignment
checks for hash-miss accesses while compiling out the interior-pointer treap. In `--unchecked` builds, pointer-access
validations compile out and raw pointer indexing lowers to direct C pointer arithmetic and dereference; the
`unsafe func` author is then solely responsible for the range/provenance proof.

The L1 runtime archives and tcc object variants use content-sensitive configuration stamps. Compiler selection, runtime
flags, mode defines, and baked quarantine settings therefore trigger the necessary rebuilds, while repeating an
identical configuration remains a no-op. Runtime allocation benchmarks use monotonic wall time and observable pointer
escapes so optimized unchecked loops retain their measured work.

The native L1 Stage 1 compiler is itself an L0 program. Its default compiler-build runtime uses basic pointer validation
and a 256-record quarantine limit, retaining core checked-runtime diagnostics without the full interior-pointer index.
`L1_COMPILER_RT_CHECK_BASIC`, `L1_COMPILER_RT_UNCHECKED`, `L1_COMPILER_RT_QUARANTINE_MAX_BYTES`, and
`L1_COMPILER_RT_QUARANTINE_MAX_COUNT` configure only that native compiler binary. They do not change the full checked
default of L1 runtime archives or the runtime mode selected for programs produced by `l1c`.

## 7.1 Fixed-Size Array Policy

Fixed-size arrays are first-class value types spelled `T[N]`, where `N` is a positive compile-time `int` constant
expression. The current direct source subset is an integer literal or a visible top-level `const` reference; referenced
scalar constants may themselves use the supported compile-time scalar expression subset. Suffix order is
source-significant across pointer, nullable, and array suffixes: `T*[N]` is an array of pointers, `T[N]*` is a pointer
to an array, `T?*` is a pointer to optional storage, and `T*?` is an optional pointer. Adjacent dimensions preserve
C-like source order, so `int[2][3]` is two rows of three `int` values.

Array literals (`[a, b]`) are contextual only and have no standalone type. They are accepted only when the expected type
is a fixed-size array `T[N]`, reject overlong element lists, and zero/default-pad omitted trailing elements. Expected
fixed-size array contexts include annotated locals, assignments, function parameters, struct constructor fields, enum
payload fields, `new` initializer fields, return expressions, and explicit array constructors. A slice target `T[]` is
not an array-literal context; users must first create a fixed array value, then use an approved fixed-array-to-slice
conversion context.

Array constructor expressions are restricted to array type calls with one argument, either `T[N]([ ... ])` or
`T[N](value)` for fill. The fill value has the element type `T`, and `T` may itself be an array type:
`int[10][20]([1, 2, 3])` contextually builds one `int[20]` row and broadcasts that row across the ten outer elements.
Array lengths resolve to concrete values before signature and backend lowering.

Array indexing is safe: generated code evaluates the base and index once, checks `index < 0 || index >= N`, and calls
`_rt_panic_oob(index, N)` on failure. Raw pointer indexing has no source-level upper bound; checked builds may still
catch invalid allocation/range/provenance at runtime, while unchecked builds trust the `unsafe func` contract.

## 7.2 Slice Policy

Slices are first-class non-owning views spelled `T[]`. A slice is a descriptor `{ dea_int len; T *data; }` copied by
value with no retain, release, or cleanup for the descriptor itself; ownership of the pointed-to storage stays with the
underlying fixed array. Compiler-materialized fixed-array rvalues used as slice backing storage still follow normal
array cleanup rules when their element type transitively contains ARC-managed data. The initial surface supports `T[]`,
`T*[]`, and `T?[]`; `T[]?` and `T[]*` are rejected so the non-owning escape restrictions are not weakened. The
inferred-length form `T[_]` is reserved and rejected by the parser, never `T[]`.

Because slices do not own their storage and this stage has no borrow or lifetime analysis, they are accepted only as
local variables, parameters, and call arguments. They are rejected as function return types, returned expressions,
struct fields, top-level `let` bindings, and enum (heap) payload fields.

A fixed array `T[N]` converts to `T[]` only in known slice target contexts: function arguments, annotated local
initialization, and assignment to an existing slice variable. There is no unconstrained `T[N] -> T[]` decay, keeping
ownership explicit. The conversion forms a descriptor from the array length and a pointer to the array's storage.

`len(x)` returns the `int` length of a fixed array, slice, or string. `slice(x)`, `slice(x, start)`, and
`slice(x, start, count)` build a `T[]` over a fixed array or slice; the third argument is `count`, not an end index.
Index, `start`, and `count` operands must be `int`. Slice indexing and slice-range construction are bounds-checked with
`_rt_panic_oob` before any pointer arithmetic or dereference, and a zero-length result uses `len = 0` and `data = NULL`.

- `ptr[index] = value` follows the same slot-replacement ARC discipline as other ordinary assignments when `T`
  transitively contains ARC-managed data

## 8. Function Pointer Types

L1 supports function pointer types with the spelling `func(T1, T2) -> U` and `unsafe func(T1, T2) -> U`. The
zero-argument form is `func() -> U`, and `void` remains the result type for functions that do not return a value. Bare
references to top-level functions have the function pointer type matching their signature, so they can be stored in
variables, passed as arguments, returned, and called indirectly.

Function pointer types are pointer-valued ABI objects. Generated C represents each distinct signature with a
`dea_func_*` typedef over a plain C function pointer. Two function pointer types are compatible only when parameter
arity, parameter types, result type, and the presence or absence of the `unsafe` marker match exactly.

Nullability follows the existing `T?` model. Because `func(...) -> U?` means a non-null function pointer returning
nullable `U`, a nullable function pointer is written with parentheses: `(func(...) -> U)?`. The same rule applies to
unsafe function pointers, for example `(unsafe func(void*) -> int)?`. Nullable function pointer values use the same
`NULL` niche representation as object pointers. Equality operators compare function pointer identity for same-signature
operands; ordered comparisons remain rejected.

The current `unsafe` marker is a function-level contract marker, not a call-site gate. Safe code may still call an
`unsafe func` value today; the marker exists to distinguish source-unsafe raw-memory contracts in signatures and
interfaces.

Lambdas, closures, method pointers, and C variadic function pointer types are intentionally out of scope for the current
bootstrap feature.

## 8.1 L1 Variadic Functions

L1-defined variadic functions use a single trailing parameter `name: T...`; function pointer types mirror the spelling
as `func(Prefix, T...) -> U`. Inside the callee the parameter has effective type `T[]`, so ordinary `len`, indexing, and
slice assignment rules apply. Variadic function types remain distinct from fixed `func(Prefix, T[]) -> U` types even
though both lower their final C parameter to the same slice descriptor ABI.

Calls provide the fixed prefix plus zero or more `T` values. The caller materializes those values into an owned
fixed-array pack and passes a non-owning slice descriptor, so callee mutation changes the pack copy rather than the
original argument values. A final `pack...` instead forwards a compatible slice or fixed array directly and therefore
keeps normal slice aliasing. Spread must be the complete variadic tail, and named variadic calls are rejected.

The LBI encodes the variadic final parameter with `V`, preserving link and function-type identity. Variadic
`extern func` declarations remain rejected because C variadic ABI rules belong to the separate C FFI initiative.

## 9. Nullability, Casts, and Introspection

Current policy:

- `?` is a unary type suffix constructor applied left-to-right with other suffixes
- `null` is the only empty value of a nullable type
- a value of type `T` may be used in a `T?` context, including returns, assignments, and arguments; generated code wraps
  the value as present
- casts with `as` are explicit and checked by the type system/runtime helpers where required
- integer casts may target nullable integer types directly when the same cast to the nullable inner type is valid; for
  example, `0 as ulong?` and `9999999999 as long?` are accepted and apply the same range-checking behavior as
  `0 as ulong` and `9999999999 as long` before wrapping
- the current nullable-integer cast rule unwraps exactly one nullable layer and is scoped to builtin integer payload
  types; it does not yet mean that every implicit widening conversion composes with `as`
- `expr?` is the null-propagation operator

Nested nullable types are preserved. `T??` is distinct from `T?` and can represent outer null, outer present with inner
null, and outer present with an inner `T` value. Likewise, suffix order is semantic: `T?*` is a pointer to an optional
`T`, while `T*?` is an optional pointer to `T`.

Equality operators (`==` and `!=`) are accepted between two operands of the same nullable type `T?`, provided the inner
type `T` itself supports equality. The semantics follow a three-valued rule:

- both operands null returns `true` (for `==`) or `false` (for `!=`)
- exactly one operand null returns `false` (for `==`) or `true` (for `!=`)
- both operands non-null return the result of the inner `T == T` or `T != T` comparison

The rule is strict: `T? == T` and `T == T?` are rejected even when `T` supports equality. Users must cast explicitly to
reach a same-type pair, for example `x as T? == y` or `x == y as T`, depending on the side whose type they want to move.
Nullable-pointer operands use the pointer-null niche representation only when the nullable payload is immediately a
non-nullable pointer or function pointer, as in `T*?` and `(func() -> T)?`. `T*??` uses an outer wrapper so it can
distinguish outer null from an outer-present inner null pointer.

For non-pointer nullable values, and for nested nullable values whose outer layer cannot use a pointer niche, generated
C uses wrapper representations rather than exposing host-specific niche assumptions.

Future direction: broaden the cast rule so `expr as U` is valid whenever there is an explicit cast target `V` for the
operand and `V` can be implicitly widened to `U`. That would make the current integer-to-optional-integer behavior one
instance of a general "explicit conversion followed by implicit widening" rule, covering future cases such as broader
numeric widenings or nullable pointer-family widenings when those conversions are deliberately added.

## 10. The `dea` Prelude Module

The compiler synthesizes one implicit module, `dea`, for language-level primitives.

Current contents:

- `dea::sizeof`
- `dea::ord`
- `dea::is`
- `dea::len`
- `dea::slice`

Current policy:

- `dea` is a virtual module owned by the compiler, not a source file loaded from disk
- `dea` is opened into every module automatically
- `dea` has the lowest import precedence, so user locals and explicit imports shadow it normally
- `dea::sizeof`, `dea::ord`, `dea::is`, `dea::len`, and `dea::slice` remain the stable qualified escape hatch when user
  code intentionally reuses those names
- this behavior does not change the surface grammar: `dea` is a semantic prelude mechanism, not a special import syntax
- qualified `dea::*` intrinsics are always available even when the unqualified names are shadowed
- shadowing uses the normal name-resolution rules and warning behavior rather than bespoke intrinsic-specific fallback
- `dea::is(value, Variant)` compares enum tags only and does not evaluate or synthesize payload values for `Variant`
- `sizeof`, `ord`, `is`, `len`, and `slice` do not accept named arguments

Rationale:

- keep intrinsics in the normal symbol/module system instead of hard-coding bare names
- avoid hijacking user-defined functions named `sizeof`, `ord`, or `is`
- preserve ergonomic unqualified use for bootstrap-stage code while keeping an explicit disambiguation path
- leave room for future compiler-owned type aliases and other prelude-level symbols without introducing a synthetic
  source file

## 10.1 Named Arguments

Function calls, struct constructors, and enum-variant constructors may use named arguments in the form `name: value`.

Current policy:

- an argument list must be entirely positional or entirely named
- every required parameter, struct field, or enum payload label must appear exactly once
- source evaluation order is preserved even when named arguments are lowered into declaration order for calls and
  constructors
- compiler intrinsics such as `sizeof`, `ord`, and `is` do not accept labels
- function-pointer calls do not accept named arguments because the pointer type does not carry source parameter names

Rationale:

- make the call-site rule deterministic without optional/default-argument semantics
- preserve side-effect order independently of backend reordering needs
- keep compiler-owned intrinsics separate from user-defined functions that happen to use the same names

## 11. Integer and Failure Semantics

The bootstrap compiler keeps integer behavior defined rather than inheriting host-C vagueness:

- implemented builtin integer names are `tiny`, `short`, `int`, `long`, `byte`, `ushort`, `uint`, and `ulong`
- `tiny` is 8-bit signed semantics
- `byte` is 8-bit unsigned semantics
- `short` is 16-bit signed semantics
- `ushort` is 16-bit unsigned semantics
- `int` is 32-bit signed semantics
- `uint` is 32-bit unsigned semantics
- `long` is 64-bit signed semantics
- `ulong` is 64-bit unsigned semantics
- overflow-sensitive arithmetic and narrowing go through checked runtime helpers
- integer literals that fit `int` remain ordinary `int` literals
- integer literals outside `int` are carried as opaque bigint payloads until a contextual `uint`, `long`, or `ulong`
  target is known
- fitting integer literals may be used in narrower typed integer contexts without a runtime check, while nonliteral
  narrowing and cross-signedness conversions require an explicit cast
- an explicit cast between builtin integer types is compile-time evaluable when its operand is a compile-time constant;
  the value must fit the target range and never wraps
- explicit integer casts to nullable integer targets, such as `0 as ulong?`, use the same checked conversion policy as
  casts to the inner type and then produce a present nullable value
- binary `&`, `|`, `^`, `<<`, and `>>` use the same common-integer-type lattice as the other integer binary operators
- unary `~` preserves the operand's integer type; the backend casts the promoted C result back to that L1 type
- right shift follows the signedness of the normalized operand type, so signed shifts are arithmetic and unsigned shifts
  are logical on supported targets
- integer division by zero is a defined runtime error, not host-C undefined behavior

That policy is part of the language contract even though the current implementation is lowered through C.

At the stdlib layer, integer helper contracts belong in `std.integer`; copied modules such as `std.time` may consume
those helpers, but they should not own general-purpose arithmetic utilities. The unsuffixed helper names remain the
shared `int` surface. L1-only `uint`, `long`, and `ulong` helpers use explicit `_ui`, `_l`, and `_ul` suffixes so wider
fixed widths do not shadow or blur the shared API. Signed `long` helpers follow the same checked representability policy
as the `int` helpers, while unsigned helpers use plain `div_*` / `mod_*` names and omit signed-only concepts such as
`sign`, `abs`, `ediv`, and `emod`.

Floating-point helpers belong in `std.real` with their runtime C FFI backed by `sys.real`. Explicit `_f` and `_d`
suffixes prevent shadowing and ambiguity between `float` and `double`. To minimize runtime footprints, the host math
library (`-lm`) and the `l1_real.h` C wrapper are only linked and included when the compilation unit actually uses
`sys.real`, rather than treating every float-using program as a math-library consumer.

## 12. Floating-Point Semantics and Backend Contract

L1 now includes builtin `float` and `double` types and floating-point (FP) literals. Their semantic contract is
intentionally narrow and must not be left as an accident of generated C.

Current policy:

- `float` and `double` are builtin noninteger numeric types
- unsuffixed real literals denote `double`
- a trailing `f` or `F` denotes `float`
- floating arithmetic is non-panicking
- floating division by zero is defined and does not panic
- on supported targets, floating arithmetic uses IEEE-style non-trapping behavior with signed zero, infinities, and NaNs
- integer checked arithmetic and floating arithmetic remain distinct lowering paths
- floating `/` does not route through checked integer helpers
- the language-level meaning of floating operations belongs to L1 and is not delegated to unspecified host C behavior

Current conversion and typing policy stays intentionally narrow:

- implicit `float -> double` widening is allowed
- implicit `double -> float` is not allowed
- implicit `int -> float` and `int -> double` are not generally allowed
- implicit `float -> int` and `double -> int` are not allowed
- mixed integer and real binary arithmetic requires an explicit cast to a matching floating type
- explicit numeric `as` casts among `int`, `float`, and `double` are part of the current bootstrap surface
- `float` to/from `double` casts are compile-time evaluable for constant operands; integer/real cross-casts remain
  outside the `const` initializer subset

Direct integer literal conversion is a narrow contextual rule:

- an integer literal expression may be used directly in a typed `float` or `double` context when the literal value is
  representable by the target real type
- this rule applies to parenthesized integer literals and unary-minus integer literals
- this rule applies to annotated `let` initializers, function call arguments, return expressions, and constructor
  arguments where the destination type is known
- this rule does not apply to nonliteral integer expressions or variables
- this rule does not create general implicit `int -> float` or `int -> double` promotion
- mixed integer and real binary arithmetic still requires an explicit cast to a matching floating type

Current operator policy for real values:

- unary `-` is allowed for `float` and `double`
- binary `+`, `-`, `*`, and `/` require matching real types after the allowed `float -> double` widening step
- `float op double` and `double op float` widen to `double`
- comparison operators on real values follow the same narrow compatibility rule and yield `bool`

Current backend contract for FP-using programs:

- `float` lowers to C `float`
- `double` lowers to C `double`
- the lowered C types must have the required binary-radix representation and precision expected by the L1 types they
  stand for
- the target must provide infinities and NaNs for the lowered types
- floating arithmetic must be non-trapping in ordinary execution
- backend modes or optimization assumptions that would invalidate NaN, infinity, signed-zero, or ordinary ordered
  comparison semantics relied on by L1 are not valid for FP-using programs
- if these requirements are not met, the backend must reject programs that use `float` or `double`

Rationale:

- Dea/L1 wants defined behavior rather than ambient host-language folklore
- plain C lowering is acceptable only when the target contract that makes it sound is stated explicitly
- rejecting unsupported FP targets is cleaner than pretending every C99 target means the same thing
- keeping the conversion lattice narrow avoids accidental promotion creep in the bootstrap compiler

Consequences:

- floating `/ 0.0` is a language-defined non-panicking operation on supported targets
- FP support is conditional on backend validation rather than assumed on every possible C99 target
- future backend or optimization changes must preserve the stated FP contract rather than silently weakening it

## 13. I/O and Runtime API Shape

Bootstrap-stage tooling intentionally favors simple whole-file and console APIs over richer streaming abstractions. That
is sufficient for compiler bootstrapping, diagnostics, and current examples while keeping the language/library surface
narrow.

Current `std.io` numeric output policy follows the same explicit suffix convention as the rest of the L1 numeric stdlib
surface:

- `int`, `string`, and `bool` keep the copied ergonomic spellings such as `print_i`, `print_s`, and `print_b`
- L1-only fixed-width integer output uses `_ui`, `_l`, and `_ul` for `uint`, `long`, and `ulong`
- floating output uses `_f` and `_d` for `float` and `double`
- stdout and stderr expose the same one-value numeric families, with newline variants using the existing `printl_*` /
  `err_printl_*` naming pattern
- pair-print helpers are not expanded cartesian-style for every numeric type; callers can compose labels with
  single-value print helpers

Current stdin token policy keeps parsing layered:

- `read_delim`, `read_delim_any`, and `read_delim_ws` own token extraction from stdin
- typed integer reads use `read_delim_ws` plus the matching `std.text` parser
- integer parsing remains in `std.text`, not in `std.io`
- float/double reads are deferred until the library has an explicit floating-point parsing contract

## 14. Name Disambiguation

Qualified references (`module.path::Name`) are the current cross-module disambiguation mechanism.

The compiler also synthesizes one implicit module, `dea`, for language-level primitives. Its exports are opened into
every module at the lowest precedence, so user locals and explicit imports shadow `dea` with the normal `RES-0021`
warning. `dea::sizeof`, `dea::ord`, and `dea::is` remain the stable qualified escape hatch when user code intentionally
reuses those names.

Rationale:

- keep open imports ergonomic for simple programs
- provide an explicit escape hatch for ambiguity
- avoid introducing more namespace surface before it is needed

## 15. Numeric Literal Representation in L1

L1 introduces numeric types that are not native to the L0 implementation language, including implemented integer forms
such as `uint`, `long`, and `ulong`, plus the implemented floating-point forms `float` and `double`.

Current decision:

- integer literals outside Dea's 32-bit `int` range are represented inside the compiler as opaque bigint payloads
  carrying sign, significant digits, and base (`2`, `8`, `10`, or `16`)
- the compiler does not perform compile-time arithmetic on bigint payloads; it only performs textual range checks where
  a contextual integer target is known
- 32-bit `int` compile-time constants can fold checked arithmetic, non-negative bitwise/shift operations, short-circuit
  boolean operators, scalar equality/comparison, and selected scalar casts
- overflow, invalid shifts, divide/modulo by zero, and unsupported bitwise operands are non-evaluable rather than
  compiler failures
- generated C reconstructs equivalent literal spellings from the stored payload/base pair and adds destination-aware C
  suffixes or macros where required
- IR and semantic nodes remain typed, so the payload encoding is an internal implementation detail rather than a
  language-level contract

For floating-point literals and expressions, the current bootstrap compiler adds the following rule:

- Stage 1 does not perform arithmetic evaluation of floating-point expressions unless it can guarantee results identical
  to the L1 floating-point contract

Rationale:

- C99 literal syntax such as `1L`, `1.0f`, and `1.0` is already well-defined
- correctness and constant folding can be delegated to the downstream C compiler in the bootstrap stage only where that
  delegation remains consistent with the stated L1 contract
- this keeps the implementation surface small and avoids blocking L1 feature work on arbitrary-precision constant
  infrastructure
- a later structured constant representation can be introduced without changing the typed IR shape

Consequences:

- compile-time constant folding for non-native numeric types is intentionally unavailable in the current bootstrap
  compiler
- code generation must preserve literal value/base information and emit an equivalent typed C spelling faithfully
- the compiler and emitted C must not disagree about the meaning of floating literals, arithmetic, division by zero, or
  non-finite results

Future direction:

- when L1 needs target-independent constant evaluation or richer compile-time semantics, migrate the payload
  representation to an APInt/APFloat-style structured form that carries explicit type/width/value information

## 16. String Value Semantics

`string` is an ARC-managed value type. Two `string` values are language-equivalent when their byte contents are equal;
their runtime representation (static versus heap, deduplicated or not) is not observable through the language.

Current policy:

- equality (`==`, `!=`) on `string` compares by content bytes, backed by the runtime helper `rt_string_equals`
- equality is consistent across `==`, `case` arms over `string`, and `std.string::eq_s`
- ordered comparisons (`<`, `<=`, `>`, `>=`) on `string` use byte-wise lexicographic ordering through
  `rt_string_compare`
- ordered comparisons are consistent across the operators and `std.string::cmp_s`
- string identity, meaning whether two values refer to the same runtime instance, is intentionally not exposed through
  any operator, cast, or intrinsic
- any future need for instance equality will be satisfied through an explicit `sys.*` helper with documented
  implementation-defined semantics, not through a new operator

Rationale:

- identity-based equality would leak backend representation choices such as literal deduplication and static-versus-heap
  selection into user-observable semantics, contradicting the UB-free/defined-semantics policy stated in §1
- value equality is the only semantic consistent with existing `case`-over-string behavior and with the backend's
  freedom to evolve dedup and arena strategies

The top-level `==`, `!=`, `<`, `<=`, `>`, and `>=` operators are now wired for `string` operands in the current
bootstrap compiler. Top-level `+` also accepts `string + string` and yields a fresh owned `string` result with ordinary
ARC behavior; neither operand is mutated or consumed.

## 17. Top-level `const` and `let`

L1 distinguishes between two top-level binding forms:

- `let NAME [: T] = EXPR;` for ordinary top-level bindings, which may have run-time initializers and are mutable by
  default
- `const NAME: T = EXPR;` for compile-time-known bindings whose initializer must stay inside the existing static
  initializer subset

Current policy:

- top-level `const` requires an explicit type annotation
- top-level `const` initializers may use literals, `null`, bare zero-argument enum variants, constructor calls whose
  arguments are themselves constant, visible scalar `const` references, supported checked scalar operators, and the
  selected compile-time scalar casts described in Sections 11 and 12
- compile-time scalar casts cover builtin integer-to-integer casts with target-range checking, `float` to/from `double`,
  and identity casts for `bool` and `string`; other cast families remain outside the accepted constant subset
- scalar, string, and bool `const` values may be referenced from constant-value grammar contexts such as array bounds
  and `case` arms, with the explicit declaration type controlling semantic classification
- top-level `const` lowers to `static const` generated C declarations under the existing `dea_*` ABI naming scheme
- assignment to a top-level `const` binding, including field assignment through a value-typed `const`, is rejected
- block-local `const` is still deferred; only top-level `const` is accepted today

Rationale:

- this keeps the current compile-time-known path explicit
- requiring an explicit type keeps the accepted constant subset deterministic during bootstrap and avoids depending on a
  broader compile-time evaluator, which is not yet a priority for L1

## 18. Comparison Operator Scope

The grammar admits `==`, `!=`, `<`, `<=`, `>`, `>=` between any operand types. The type checker intentionally restricts
which operand types each operator accepts; this section records the deliberate rejections.

Ordered comparison on `bool` is not accepted:

- `bool < bool`, `bool <= bool`, `bool > bool`, and `bool >= bool` are rejected as non-numeric operands
- the rejection is a design choice, not a deferred feature: booleans are two labels, not a scalar ordering, and a
  defined `true > false` meaning would add a footgun without a corresponding use case
- the rejection diagnostic is `TYP-0170`, consistent with other non-numeric operand rejections on the relational
  operators
- callers who want to route on a boolean value should use `if` / `case (b) { true => ...; false => ...; }` or compare
  equality (`b == true`, `b != false`, or the simpler `b` / `!b` expressions)

Equality on `bool` remains accepted, unchanged:

- `bool == bool` and `bool != bool` return `bool`
- this matches `case (b) { true => ...; }` dispatch and the general policy of treating `bool` as a scalar tag for
  equality but not for ordering

Rationale:

- The Dea policy prefers a compile-time rejection over a defined-but-misleading ordering
