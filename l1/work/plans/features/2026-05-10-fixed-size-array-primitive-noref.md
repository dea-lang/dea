# Feature Plan

## Add the fixed-size array primitive

- Date: 2026-05-10
- Status: Testing/Fixing
- Title: Add the fixed-size array primitive
- Kind: Feature
- Severity: High
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0004-array-primitives-and-unsafe-marker.md`
- Subsystem: Parser / typing / lowering / runtime / ARC / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/parser/expr.l0`
  - `l1/compiler/stage1_l0/src/parser/shared.l0`
  - `l1/compiler/stage1_l0/src/types.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/signatures.l0`
  - `l1/compiler/stage1_l0/src/locals.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/reference/ownership.md`
  - `l1/docs/reference/c-backend-design.md`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/specs/compiler/abi.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/trace`
- Related:
  - `l1/work/initiatives/0004-array-primitives-and-unsafe-marker.md`
  - `l1/work/plans/features/closed/2026-05-09-raw-pointer-indexing-semantics-noref.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: `make -C l1 test-stage1 TESTS="parser_test expr_types_test backend_test c_emitter_test interface_test"`

## Summary

Initiative `0004` Phase 3 adds the L1 fixed-size array primitive `T[N]`. Arrays are value types with positive
compile-time `int` lengths, contextual array literals, constructor expressions, deterministic zero/default
initialization, bounds-checked indexing, deterministic wrapper-struct C lowering, recursive ARC handling for all
supported value shapes, and heap allocation/drop support through `new T[N]` and `drop`.

This plan replaces the current unsupported-array placeholder with real parser, typing, backend, runtime, trace, and
reference-doc coverage. Dynamic arrays, slices/views, address-of, broader pointer arithmetic, array equality, generics
over `T` or `N`, unsafe uninitialized storage, sparse initialization, and block-level `unsafe {}` remain out of scope.

## Outcome

Implemented in the L1 Stage 1 bootstrap compiler on 2026-05-11. The implementation adds source-ordered array type
suffixes, semantic `TY_ARRAY`, contextual literals, array constructors, heap allocation/drop support, checked indexing
through `_rt_panic_oob`, generated array wrapper typedefs using the ABI type-component layer, flattened adjacent
multi-dimensional C storage, recursive retain/cleanup participation for array values, tests, diagnostics, and reference
docs.

## Current State

1. Type syntax currently rejects array-looking forms through the placeholder diagnostic `PAR-9401`.
2. `ptr[i]` is finalized by the Phase 2 pointer-indexing plan, but `T[N]` arrays do not exist.
3. L1 has recursive ownership support for several value shapes, but no array-shaped retain, release, cleanup, copy,
   assignment, or slot-replacement path.
4. The runtime has panic helpers, but no dedicated `_rt_panic_oob(dea_int index, dea_int length)` helper for generated
   array bounds checks.
5. [`abi.md`][abi] now defines a finalized type-component layer for generated type names, including array wrappers.

## Defaults Chosen

01. `T[N]` encodes both element type and length in the type. `T*[N]` means an array of `N` pointers to `T`, and `T[N]*`
    means a pointer to an array of `N` `T` values.
02. Nullable suffixes may follow array suffixes only where the existing nullable-value model permits them.
03. Array lengths are integer-literal metadata on semantic array types. Lengths must fit `int` and be `>= 1`; zero,
    negative, non-`int`-range, and malformed lengths are rejected.
04. Chained array suffixes use C-like source-order dimension semantics. `int[2][3]` is two rows of three `int` values,
    stored contiguously in row-major order.
05. Array literals use bracket syntax, for example `[a, b, c]`, and require a contextual `T[N]` target. Bare literals
    without a target are rejected.
06. Bare declarations remain illegal. Array declarations must use the existing `let name [: T] = expr` form so safe code
    never observes uninitialized array storage.
07. Array literals may be shorter than `N`; omitted elements are zero/default initialized. Empty `[]` is a valid
    all-zero/default initializer in a contextual array target. Literals longer than `N` are rejected.
08. Array constructor expressions use `T[N](arg)` syntax. The sole argument may be an array literal for the outer array
    shape, or a value of the outer array's element type `T` used as a uniform fill for every element. `T` may itself be
    an array type, so `int[10][20]([1, 2, 3])` broadcasts one contextually-built `int[20]` row.
09. `new T[N]` allocates zeroed wrapper storage and returns `T[N]*`. `new T[N](arg)` mirrors stack/value constructor
    rules for literal initialization or element-typed fill.
10. Each array instantiation lowers to a generated C wrapper struct with one `data[N]` field.
11. Indexing `arr[i]` and assigning `arr[i] = value` emit bounds checks before `.data[index]` access and evaluate base
    and index expressions exactly once.
12. `drop` on `T[N]*` runs element cleanup before freeing when `T` transitively owns ARC-managed data.
13. C FFI exposure is wrapper-struct based. A C-facing slice or buffer policy stays out of scope for this plan.

## Goal

1. Parse and resolve `T[N]`, nested pointer/array suffixes, and nullable interactions.
2. Add semantic array types with element type and positive length metadata.
3. Add contextual array literals with zero/default padding and element typing.
4. Add array constructor expressions for literal construction and element-typed fill.
5. Lower arrays as deterministic C wrapper structs and checked `.data` indexing.
6. Extend recursive retain, release, cleanup, copy, assignment, and slot replacement to arrays.
7. Support `new T[N]`, `new T[N](arg)`, `drop`, `sizeof(T[N])`, top-level `const` arrays, and deferred top-level `let`
   arrays.
8. Add `_rt_panic_oob(dea_int index, dea_int length)` to the runtime header and both runtime archives.
9. Document grammar, ownership, backend, standard-library, ABI, diagnostics, and roadmap changes.

## Implementation Phases

### Phase 1: Syntax and semantic types

Replace the unsupported-array placeholder with array suffix parsing for types and array constructor expressions. Store
parsed array suffixes in the AST, resolve them into semantic array types, and reject malformed or invalid lengths with
parser/type diagnostics instead of an internal-error placeholder.

Parser tests cover valid suffix ordering such as `T[N]`, `T*[N]`, `T[N]*`, multidimensional `T[M][N]`, and nullable
suffixes after arrays where allowed, plus malformed lengths, array constructor syntax, and removal of `PAR-9401` for
supported syntax.

### Phase 2: Array literals and typing

Add array literal AST nodes and contextual typing. A literal must have a contextual array target, must provide at most
`N` elements, and must type-check each explicit element against `T`. Missing trailing elements are zero/default
initialized. Empty `[]` is the canonical all-zero/default array literal. Extend compile-time-constant validation so
top-level `const` arrays are accepted when every explicit element is constant under existing rules.

Typing tests cover valid `T[N]`, invalid lengths, contextual literals, bare literal rejection, short literal
zero/default padding, empty literals, overflow length rejection, element type mismatches, nullable/pointer interactions,
`new T[N]`, `drop`, and `sizeof(T[N])`.

### Phase 3: Array constructors

Add array constructor expressions using type-call syntax over array types only. `T[N]([a, b])` constructs an array value
using the same contextual literal and zero/default padding rules as annotated `let` initialization. `T[N](value)`
constructs an array value by assigning the element-typed `T` value into every element; `T` may itself be an array type.
Constructors accept exactly one argument in this phase.

Constructor tests cover `int[3]([1, 2, 3])`, `int[1000]([1, 2])`, `byte[1024](0xFF)`, invalid `int[1, 2, 3]`, invalid
`int[1000]` as a value expression, invalid bare type-as-value use, invalid `let x: int[1000];`, wrong fill type, and
wrong constructor arity.

### Phase 4: ABI and C lowering

Use the finalized type-component layer from [`abi.md`][abi] for generated array wrapper names. That layer supersedes the
older provisional `B<len><name>` builtin spelling, length-prefixed `P`/`Q` modifiers, and packed array-dimension
payload. In the finalized grammar:

- builtins use lowercase one-byte sigils such as `i` for `int`, `h` for `byte`, and `c` for `string`
- `P`, `Q`, and `X` are prefix modifiers that recurse into the immediately following component without their own length
- `A<dim>_<element>` encodes exactly one array dimension, with the underscore terminating the decimal dimension
- multidimensional arrays chain one `A` per source-order dimension, so modifiers can appear between dimensions naturally
- nominal types use one `M` module section with length-prefixed module components, followed by `S<len><struct-name>` or
  `E<len><enum-name>`

Exact wrapper-name examples:

- `byte[1024]` -> `__deaA1024_h`
- `int[2][3]` -> `__deaA2_A3_i`
- `int*[2][3]` -> `__deaA2_A3_Pi`
- `demo.main::Point[4]` -> `__deaA4_M4demo4mainS5Point`

The underscore after each array dimension is required because array dimensions are unbounded decimal numbers. A spelling
such as `A13i` is ambiguous; `A13_i` unambiguously means `array[13] of int`.

Emit one wrapper typedef per array instantiation:

```c
typedef struct __dea... {
    T data[N];
} __dea...;
```

Backend and C-emitter tests cover deterministic typedef names, wrapper field layout, parameter passing, returns,
top-level `const` arrays, deferred top-level `let` arrays, whole-array assignment, `sizeof(T[N])`, the exact wrapper
names above, and `int[2][3]` lowering as `data[2][3]` rather than nested wrapper fields.

ABI release notes for the implementation must call out that generated array wrapper names use the finalized
type-component layer from [`abi.md`][abi], including lowercase builtin sigils, prefix `P`/`Q`/`X` modifiers, and one
`A<dim>_` constructor per source-order array dimension. No additional `abi.md` amendment is required unless the
implementation discovers a mismatch with that finalized grammar.

### Phase 5: Bounds-checked indexing and runtime support

Add `_rt_panic_oob(dea_int index, dea_int length)` to `dea_rt.h`, the normal runtime archive, and the traced runtime
archive. Generated array reads and writes evaluate the base and index once, check `index < 0 || index >= N`, call
`_rt_panic_oob` on failure, and access `.data[index]` on success.

Index typing keeps `TYP-0210` for non-`int` index expressions. Existing pointer-index diagnostics `TYP-0211` and
`TYP-0213` to `TYP-0215` remain pointer-focused, with array-specific wording added only where behavior differs.

Runtime tests cover in-bounds reads/writes and out-of-bounds panic behavior through `_rt_panic_oob`.

### Phase 6: Recursive ARC and heap arrays

Extend recursive ownership operations so arrays work for strings, nullable ARC values, structs, and payload-carrying
enums. If implementation exposes enum value-copy gaps, fix those gaps inside this plan instead of narrowing array
support.

For array instantiations whose element type has ARC data:

- copied source elements are retained before destination elements are released,
- cleanup iterates elements in reverse index order,
- whole-array assignment uses alias-safe ordering by retaining the source array, releasing the old destination array,
  then copying the wrapper value,
- element replacement reuses the existing slot-replacement discipline for `T`,
- `drop` on `T[N]*` cleans elements before freeing the allocation.

Heap allocation mirrors stack/value construction. `new T[N]` and `new T[N]()` zero/default initialize the full wrapper.
`new T[N]([a, b])` copies the literal prefix and zero/default pads the rest. `new T[N](value)` fills every element from
the element-typed value. `new T[N](a, b, c)` is rejected.

ARC trace tests cover `string[N]`, nullable string arrays, structs containing strings, payload enum arrays, whole-array
assignment alias ordering, element replacement, scope cleanup, return moves, and heap `new`/`drop` cleanup.

### Phase 7: Multidimensional arrays

Support composed fixed-size arrays such as `T[M][N]`. Source dimension order follows the written order, so `int[2][3]`
is two rows of three `int` values. Lowering must store multidimensional arrays as a single contiguous row-major wrapper
shape. Nested literals are contextualized recursively, so `let m: int[2][3] = [[1, 2, 3], [4, 5, 6]];` initializes both
rows exactly, and shorter nested literals zero/default pad at their own level.

Tests cover stack and heap multidimensional arrays, nested contextual literals, row-major indexing, bounds checks at
each dimension, wrapper names with repeated dimensions, and ARC cleanup for nested arrays of managed element types.

### Phase 8: Docs and integration

Update [`grammar.md`][grammar], [`design-decisions.md`][design-decisions], [`ownership.md`][ownership],
[`c-backend-design.md`][backend-design], [`standard-library.md`][standard-library], [`abi.md`][abi],
[`diagnostic-code-catalog.md`][diag-catalog], and [`roadmap.md`][roadmap]. Keep docs phrased as current behavior only
after implementation lands; until then, this plan remains the lifecycle artifact for the intended work.

Document deferred follow-ups without implementing them in this plan: unsafe-only `undefined` uninitialized memory,
`undefined` as a constructor/literal tail base state, and sparse indexed constructors such as
`int[1000](0: -1, 499: 102)`.

## Diagnostics

1. Provisionally reserve `PAR-0620` to `PAR-0639` for array type and array literal syntax diagnostics. Supported array
   syntax should replace the current `PAR-9401` placeholder; internal-error codes should remain reserved for impossible
   compiler states.
2. Provisionally reserve `TYP-0800` to `TYP-0819` for array semantic diagnostics, including invalid length, unsupported
   element type if one is discovered, literal without contextual array type, literal overflow, literal element mismatch,
   constructor arity/type mismatch, and invalid array/index combinations.
3. Keep `TYP-0210` for non-`int` index expressions.
4. Preserve `TYP-0211` and `TYP-0213` to `TYP-0215` for pointer-index cases.
5. Add runtime/build diagnostics only if implementation discovers a compiler-facing failure path beyond ordinary runtime
   panic behavior.
6. Re-check these provisional reservations against the live diagnostic catalog at implementation time before assigning
   final numbers; if any suggested slots were used in the meantime, choose fresh unused blocks then.

## Non-Goals

1. Dynamic arrays, variable-length arrays, slices/views, or shared buffers.
2. Address-of (`&`) or pointer arithmetic beyond existing `ptr[i]`.
3. Array equality operators.
4. Generics over `T` or `N`.
5. Unsafe uninitialized memory and the future `undefined` keyword.
6. Sparse indexed array constructors or named-index initialization.
7. General type-as-call constructors for non-array types.
8. Block-level `unsafe {}` or new unsafe call-site enforcement.
9. A C-facing slice/buffer FFI policy.

## Verification Criteria

1. Parser tests cover array suffix ordering, malformed lengths, nested pointer/array suffixes, multidimensional
   suffixes, array literal parsing, array constructor parsing, and removal of the unsupported-array placeholder for
   valid syntax.
2. Type tests cover valid and invalid `T[N]`, contextual literals, bare literal rejection, short literal zero/default
   padding, empty literals, overflow rejection, element mismatches, constructor mismatches, nullable/pointer
   interactions, `new T[N]`, `drop`, and `sizeof(T[N])`.
3. Backend and C-emitter tests cover wrapper typedef names, field layout, bounds-check emission, single evaluation of
   base/index for reads and writes, constructor lowering, element-typed fill, array assignment, parameter passing,
   returns, top-level `const` arrays, deferred top-level `let` arrays, and multidimensional row-major layout.
4. Runtime tests cover in-bounds reads/writes and out-of-bounds panic behavior.
5. ARC trace tests cover array cleanup and copy behavior for strings, nullable ARC values, structs, payload enums,
   nested arrays, element replacement, return moves, and heap `new`/`drop`.
6. Documentation updates cover grammar, design decisions, ownership, C backend, standard library, ABI, diagnostics, and
   roadmap entries.
7. `make -C l1 test-stage1` passes.

## Post-Implementation Findings

The first implementation landed on 2026-05-11 and the planned test suite (`make -C l1 test-stage1`, 43 tests) passes. A
post-merge review surfaced the following gaps. The correctness defects were handled by a follow-up implementation pass;
remaining items below are coverage and cleanup observations rather than known correctness blockers.

### Resolved follow-up findings

The 2026-05-11 FSA follow-up resolves the correctness and portability defects from the first review:

1. Multidimensional constructor fill now follows Reading B: `T[N](value_of_T)` accepts `T` as an array type, so
   `int[10][20]([1, 2, 3])` broadcasts one contextually-built `int[20]` row.
2. Builtin and alias type-as-value mistakes now use the same `TYP-0151` diagnostic family.
3. Indexed values in call arguments remain value expressions; only explicit `T[N](...)` type calls parse as array
   constructors.
4. Nullable arrays use array-aware optional-wrapper keys and emit array typedef dependencies before wrappers that store
   them.
5. Empty array literals lower to C99-compatible `{0}` initializers.
6. `TYP-0805` uses one message for constructor and allocation arity failures.
7. Invalid array lengths no longer cascade into a misleading unknown-type diagnostic.

The follow-up also adds focused coverage for `PAR-0622`, `PAR-0623`, `TYP-0800` through `TYP-0807`, array interface
round-tripping, nullable-array C wrapper ordering, ABI wrapper-name examples, nested-index bounds checks, and a runtime
`_rt_panic_oob` failure path.

### Remaining observations

- The plan listed `l1/compiler/stage1_l0/src/locals.l0` as a target module, but the implementation still did not need a
  locals-specific change. Existing semantic and backend tests cover array-typed locals at the typing/lowering boundary;
  a future trace-focused cleanup test could make that more explicit for ARC-heavy local scopes.
- ARC trace coverage for fixed-size arrays remains thinner than the original verification wish list. Backend tests cover
  recursive retain/cleanup emission for nested managed arrays, but no dedicated trace fixture asserts the runtime event
  sequence.
- `be_emit_lvalue` materializes side-effectful pointer-index read bases into temps as part of its single-evaluation
  discipline. This is defensible, but it remains a behavioral-shape change from the pre-array pointer-index lowering.

[abi]: ../../../docs/specs/compiler/abi.md
[backend-design]: ../../../docs/reference/c-backend-design.md
[design-decisions]: ../../../docs/reference/design-decisions.md
[diag-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../../../docs/reference/grammar.md
[ownership]: ../../../docs/reference/ownership.md
[roadmap]: ../../../docs/roadmap.md
[standard-library]: ../../../docs/reference/standard-library.md
