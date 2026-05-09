# L1 Initiative 0004 - Array Primitives and Unsafe Marker

- Version: 2026-05-08
- Status: Active
- Kind: Initiative
- Open plans: (none)
- Closed plans:
  - `l1/work/plans/features/closed/2026-05-08-unsafe-function-marker-noref.md`

## Summary

Introduce a first-class fixed-size array primitive `T[N]` to the L1 surface, finalize the existing `ptr[i]` raw-pointer
indexing semantics, and add an `unsafe` function modifier that marks functions with unchecked caller-side contracts. The
three pieces are sequenced together because the marker must exist before raw-pointer indexing is treated as a stable
language feature, and pointer indexing should be contract-final before arrays use the same index syntax in safe,
bounds-checked form.

This initiative executes under the L1 roadmap ([`l1/docs/roadmap.md`][roadmap]).

## Motivation

The current L1 stdlib implements `ArrayBase`, `Vector`, `HashMap`, `HashSet`, and similar containers on top of raw
pointer manipulation through the `rt_*` runtime helpers. There is no first-class typed array primitive today, so:

- internal fixed-size buffers such as lookup tables, parser stacks, and hash bucket arrays are heap-allocated through
  `new` plus raw-pointer arithmetic, paying allocation cost and cleanup burden where stack-resident value storage would
  be enough
- raw-memory helper calls are not syntactically distinguishable from ordinary safe calls at declaration or function
  pointer boundaries, weakening the audit trail around the UB-free invariant from
  [`l1/docs/reference/design-decisions.md`][design-decisions] §1
- `ptr[i]` already parses, type-checks for pointer receivers, and lowers to C indexing, but its long-term contract is
  still intentionally unfinished in the reference docs

A first-class fixed-size array fills the gap for value-typed, stack-friendly buffers. An `unsafe` modifier formalizes
the audit boundary around raw-pointer operations. Together they let stdlib internals migrate cleanly: most fixed-size
typed-buffer cases move to `T[N]`, and residual raw-pointer code lives behind explicit `unsafe func` declarations.

## Scope

In scope:

- `unsafe` keyword and function modifier, including declaration syntax and function-pointer types
- marking raw-memory functions with unchecked caller-side contracts as `unsafe func`
- finalizing `ptr[i]` typing, diagnostics, single-evaluation lowering, and documentation
- a new `T[N]` fixed-size array primitive: value-typed, bounds-checked, and ARC-aware for any element type that
  transitively contains ARC-managed data
- array literal expression syntax for contextual initialization
- heap allocation and `drop` support for `T[N]*`
- updates to [`grammar.md`][grammar], [`design-decisions.md`][design-decisions], [`ownership.md`][ownership],
  [`c-backend-design.md`][backend-design], [`standard-library.md`][standard-library], [`abi.md`][abi],
  [`diagnostic-code-catalog.md`][diag-catalog], and [`roadmap.md`][roadmap]

Out of scope:

- block-level `unsafe { }`
- address-of operator `&`
- pointer arithmetic outside existing dereference and `ptr[i]`
- variable-length arrays, dynamic-size primitive arrays, slice/view types, shared buffers, and multidimensional arrays
- new enum value semantics beyond whatever recursive ARC/value-copy support already requires for existing enum values
- array element-wise equality operators
- generics over `T` or `N`
- block-local uninitialized `let`; array examples must use explicit initializers unless a separate feature changes the
  current `let name = expr` grammar

## Key Decisions

### `unsafe` modifier semantics

`unsafe` is a public-contract marker, not a propagating call-graph context.

- `unsafe func name(...)` declares that the function has preconditions or invariants the caller is responsible for
  upholding.
- `unsafe func(...)` and `func(...)` are distinct function pointer types. No implicit conversion is allowed in either
  direction.
- Bare references to top-level `unsafe func`s have type `unsafe func(...) -> U`, parallel to existing function-pointer
  reference rules from [`design-decisions.md`][design-decisions] §8.
- Safe functions may call `unsafe func` values in this initiative; the marker documents unchecked caller-side contracts
  and preserves the function-pointer type distinction, but it does not require unsafe call sites.
- Ordinary pointer dereference (`*p`) and pointer field access (`p.field`) remain accepted in safe code. Current L1
  treats dereference-as-rvalue as a place copy and recursively retains ARC fields, so examples such as `let x = *p;`
  remain safe when `p` is a valid initialized pointer.

This means marking a runtime binding as `unsafe extern func` is documentation and type-surface information in this
initiative. A future block-level `unsafe { }` feature may tighten call-site marking, but it is intentionally not part of
this initiative. Any future attempt to gate ordinary dereference needs a separate pointer-provenance design that can
distinguish safe heap object pointers from unchecked raw pointers.

### Module rename: `sys.unsafe` -> `sys.memory`

Adding `unsafe` as a hard keyword conflicts with the existing `sys.unsafe` module path component, since module paths are
made of identifiers and reserved words are not valid identifiers. The shared module is renamed to `sys.memory`.

The `memory` name keeps the path short while still describing the module contents: heap allocation, byte manipulation,
element addressing, and byte-level I/O over caller-supplied raw buffers. Function names inside the module are unchanged.
The `rt_*` prefix is the stable runtime API convention from [`design-decisions.md`][design-decisions] §4 and matches the
C-side runtime symbols.

Migration touchpoints include:

- `l0/compiler/shared/l0/stdlib/sys/unsafe.l0` -> `l0/compiler/shared/l0/stdlib/sys/memory.l0`
- `l1/compiler/shared/l1/stdlib/sys/unsafe.l1` -> `l1/compiler/shared/l1/stdlib/sys/memory.l1`
- the module declaration inside that file
- all stdlib importers in L0 and L1 currently using `sys.unsafe`: `std.array`, `std.vector`, `std.hashmap`,
  `std.hashset`, `std.linear_map`, `std.text`, and `std.io`
- examples, fixtures, tests, and docs that mention `sys.unsafe`
- any qualified references of the form `sys.unsafe::rt_*`

The rename lands as a precursor patch before `unsafe` becomes a keyword, so the import-path migration is validated
independently of the keyword change.

### `sys.memory` function-level marking

The runtime bindings in `sys.memory` are not uniformly unsafe. The marking follows the contract rule: `unsafe` is used
when a call has caller-side preconditions the type system cannot check.

`unsafe extern func`:

- `rt_realloc`
- `rt_free`
- `rt_memcpy`
- `rt_memset`
- `rt_memcmp`
- `rt_array_element`
- `rt_stdin_read`
- `rt_stdout_write`
- `rt_stderr_write`

Plain `extern func`:

- `rt_alloc`
- `rt_calloc`

`rt_alloc` and `rt_calloc` validate invalid sizes at the runtime boundary and have defined observable outcomes: valid
pointer, `null`, or panic. Use of returned pointers through ordinary dereference keeps existing value-copy semantics;
unchecked pointer indexing is finalized in a later phase.

### Type suffix grammar

`T[N]` extends the existing type-suffix model. Suffixes apply strictly left-to-right:

```ebnf
Type             ::= UnsuffixedType TypeSuffix* NullableSuffix?
TypeSuffix       ::= "*" | "[" IntLiteral "]"
FuncPointerType  ::= "unsafe"? "func" "(" TypeList? ")" "->" Type
```

`T*[N]` is an array of `N` pointers to `T`. `T[N]*` is a pointer to an array of `N` `T` values. `N` is an `IntLiteral`,
must fit `int`, and must be `>= 1`; zero-length arrays are rejected at type formation.

### Array literal syntax

Array literals use bracket syntax and require a contextual `T[N]` target:

```ebnf
PrimaryExpr ::= ... | "[" ExprList? "]"
ExprList    ::= Expr ("," Expr)*
```

The element count must exactly match `N`. An unannotated literal with no inference target is a typing diagnostic,
parallel to bare `null`. An empty `[]` literal is valid only with a contextual `T[0]` target, but `T[0]` is rejected, so
empty array literals always diagnose in this initiative.

Top-level `const` arrays are allowed when every element expression is compile-time constant under the existing `const`
rules extended to array literals. Non-constant top-level `let` arrays use the existing deferred-initialization path.

### `T[N]` lowering and value semantics

Lower `T[N]` to a generated C wrapper struct whose single field is the native C array:

```c
typedef struct __dea...array... { T data[N]; } __dea...array...;
```

The exact wrapper name is owned by the LBI type-instantiation amendment in [`abi.md`][abi]; this initiative does not
reuse a new sigil until the ABI spec reserves and defines it. The wrapper preserves the expected `sizeof` and alignment
properties for supported targets, and the backend must reject unsupported host layouts rather than silently changing L1
semantics.

Arrays are value types:

- assignment, parameter passing, and return copy or move the full wrapper value
- returning an owned local `T[N]` is treated as a move, parallel to existing owned-local return handling
- `new T[N]` yields `T[N]*` and allocates zeroed wrapper storage through existing `new` lowering
- `drop` on `T[N]*` must run element cleanup when `T` transitively contains ARC-managed data, then free the allocation

Indexing `arr[i]` and assigning `arr[i] = v` are always bounds-checked:

```c
if (i < 0 || i >= N) _rt_panic_oob(...);
```

Bounds checking is independent of `unsafe`; `T[N]` is a safe primitive. Base and index expressions are evaluated exactly
once for reads and writes, matching the current side-effect-preserving pointer-index lvalue lowering.

### Recursive ARC handling

`T[N]` supports element types whose values transitively contain ARC-managed data. The array machinery extends the
existing recursive ownership model used for structs, enums, nullable non-pointers, and `string`.

For any array instantiation whose element type has ARC data:

- copied source elements are retained before destination elements are released
- destination elements are released before overwrite or scope cleanup
- cleanup iterates elements in reverse index order, then delegates to the existing value cleanup for `T`
- assignment uses alias-safe whole-array ordering: retain the source array, release the old destination array, then copy
  the wrapper value
- element write `arr[i] = v` performs the bounds check once, then uses the existing slot-replacement discipline for `T`

This covers direct `string[N]`, nullable string arrays, structs containing strings, and enums with string-bearing
payloads when those enum values are otherwise supported by the existing value semantics.

### `ptr[i]` final semantics

Pointer indexing already exists in the bootstrap compiler. This initiative finalizes it as raw-pointer indexing with the
following contract:

- for `e: *T` and `i: int`, `e[i]` lowers to direct C indexing (`e[i]`, equivalent to `*(e + i)`)
- `T` must be sized and must not be `void`-shaped
- `e: *T?` rejects directly; callers must unwrap before indexing
- no bounds check is emitted
- read and write forms are accepted only inside `unsafe func` bodies
- write forms reuse the existing slot-replacement discipline when `T` transitively contains ARC data
- base and index expressions are evaluated exactly once

Existing invalid-index diagnostics are updated so they no longer imply indexing is wholly unsupported.

### Index type

The index type for both `T[N]` and `*T` indexing is `int` for this initiative, matching the locked stdlib index type. A
future extension may parameterize array index type for very large arrays without promoting `int` everywhere, but this
initiative does not freeze syntax for that direction.

## Phases

Each phase is expected to spawn a plan under `l1/work/plans/`. Phases are sequenced by dependency and each preserves the
UB-free invariant independently.

### Phase 1: `unsafe` modifier

Assumption:

1. The shared `sys.unsafe` -> `sys.memory` rename is already complete across L0 and L1.

Plan:

1. Add the `unsafe` keyword, declaration modifier, and function-pointer type carry.

Annotate the nine raw-pointer-precondition runtime helpers as `unsafe extern func`, leaving `rt_alloc` and `rt_calloc`
plain. Add `unsafe` flags to AST/function/type metadata, signature collection, type equality/formatting, interface
emission/parsing, and C declaration emission where function types appear.

Do not gate ordinary pointer dereference in this phase. Existing `*p` and `p.field` value semantics remain valid safe
code when the pointer is valid.

Compiler-side touches include `tokens.l0`, `lexer.l0`, `ast.l0`, `parser.l0`, `parser/decl.l0`, `parser/shared.l0`,
`types.l0`, `type_resolve.l0`, `signatures.l0`, `expr_types.l0`, `interface_emitter.l0`, `module_interface.l0`,
`backend.l0`, and `c_emitter.l0`.

Plan artifacts:

- `l1/work/plans/features/2026-05-08-unsafe-function-marker-noref.md`

### Phase 2: finalize `ptr[i]` semantics

Finalize the existing postfix indexing implementation for raw pointers. Type rules require:

- `*T` receiver
- non-nullable receiver
- sized, non-`void` element type
- `int` index
- enclosing `unsafe func`

Lowering remains direct C indexing for reads and writes. The backend must preserve single evaluation of side-effectful
base and index expressions. ARC-containing element assignments reuse the same slot-replacement path as dereference and
field assignment.

Tests extend typing, backend, and C-emitter coverage for:

- accepted read and write forms in `unsafe func`
- rejection outside `unsafe func`
- rejection for `*T?`, `void*`, non-pointer bases, and non-`int` indexes
- single-evaluation lowering for side-effectful base/index expressions
- scalar and ARC-containing element writes

Plan artifact: TBD.

### Phase 3: `T[N]` primitive

Introduce the array type, wrapper-struct lowering, bounds-checked indexing, recursive ARC handling, array literal
syntax, heap allocation/drop support, and the `_rt_panic_oob` runtime helper.

Implementation work includes:

- parse and resolve array type suffixes, storing array length and element type in semantic type metadata
- add array literal AST nodes, contextual typing, length checks, and compile-time-constant validation for `const`
- emit deterministic array wrapper typedefs under the LBI type-instantiation rules
- implement recursive retain/release/cleanup/copy for arrays whose element type has ARC data
- implement checked array read/write lowering with single evaluation
- support `new T[N]` and `drop` cleanup for `T[N]*`
- document FFI exposure: `T[N]` crosses C as a wrapper struct, not a bare C array; FFI users should use `*T` plus length
  until a later FFI-specific array policy exists

Compiler-side touches include `ast.l0`, `parser.l0`, `parser/expr.l0`, `parser/shared.l0`, `types.l0`,
`type_resolve.l0`, `expr_types.l0`, `signatures.l0`, `locals.l0`, `backend.l0`, `c_emitter.l0`, `interface_emitter.l0`,
and `module_interface.l0`.

Runtime touches include `compiler/shared/runtime/include/dea_rt.h`, `libdea_rt.a`, and `libdea_rt_traced.a`.

Tests add array-specific typing/backend/runtime cases under `compiler/stage1_l0/tests/`, including trace coverage for
recursive ARC retain/release ordering and heap `new`/`drop` array cleanup.

Plan artifact: TBD.

## Phase Planning Notes

1. **Diagnostic codes.** New diagnostics are needed for unsafe/plain function pointer mismatch, malformed array type
   length, array literal length mismatch, array literal without contextual type, invalid pointer-index base,
   pointer-indexing outside `unsafe func`, and unsupported array element type if implementation discovers a Phase 3
   limitation. Codes should be assigned against the live [`diagnostic-code-catalog.md`][diag-catalog] during phase
   planning.
2. **C ABI type-instantiation spelling.** The array wrapper name requires a formal LBI amendment. Phase 3 must update
   [`abi.md`][abi] before emitting generated names for array instantiations.
3. **Payload-carrying enum arrays.** Recursive ARC/value support is the accepted direction. If implementation reveals
   enum value-copy gaps not specific to arrays, the Phase 3 plan must close those gaps first rather than narrow the
   array feature.
4. **Stdlib unsafe marking shape.** Phase 1 must decide function-by-function which raw-memory helpers and wrappers truly
   expose unchecked caller-side preconditions. Public safe wrapper APIs should remain plain `func` unless their caller
   contract truly has unchecked preconditions.

## References

- [`l1/docs/reference/grammar.md`][grammar] §1.3, §3, §4, §5.2, §6
- [`l1/docs/reference/design-decisions.md`][design-decisions] §1, §4, §7, §8, §11, §16
- [`l1/docs/reference/ownership.md`][ownership] §2, §4.1, §6, §7, §8
- [`l1/docs/reference/c-backend-design.md`][backend-design]
- [`l1/docs/reference/standard-library.md`][standard-library]
- [`l1/docs/specs/compiler/abi.md`][abi]
- [`docs/specs/compiler/diagnostic-code-catalog.md`][diag-catalog]
- [`l1/docs/project-status.md`][project-status]
- [`l1/docs/roadmap.md`][roadmap]

[abi]: ../../docs/specs/compiler/abi.md
[backend-design]: ../../docs/reference/c-backend-design.md
[design-decisions]: ../../docs/reference/design-decisions.md
[diag-catalog]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[grammar]: ../../docs/reference/grammar.md
[ownership]: ../../docs/reference/ownership.md
[project-status]: ../../docs/project-status.md
[roadmap]: ../../docs/roadmap.md
[standard-library]: ../../docs/reference/standard-library.md
