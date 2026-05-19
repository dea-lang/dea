# L0 Language and Runtime Design Decisions

Version: 2026-05-19

This document records rationale and policy decisions.

Canonical ownership boundaries:

- Compiler architecture and pass flow: [reference/architecture.md](architecture.md)
- C backend implementation/lowering details: [reference/c-backend-design.md](c-backend-design.md)
- Stage 1 contract/index: [specs/compiler/stage1-contract.md](../specs/compiler/stage1-contract.md)
- Stage 2 contract/index: [specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md)

## 1. Scope and Goals

The language aims to be:

- small but expressive,
- practical for a self-hosting compiler,
- suitable for systems programming and runtime implementation,
- explicit about safety constraints,
- portable via conservative C99 lowering.

Core policy: language-level behavior should avoid undefined behavior; failures are rejected statically or become defined
runtime aborts.

## 2. Runtime Boundary Model

We keep a layered boundary:

1. L0 language + compiler.
2. L0 std/runtime libraries.
3. Small C kernel/runtime interface (`runtime/l0_runtime.h`).

Design intent:

- language semantics stay stable,
- platform-specific behavior stays quarantined in the C runtime boundary,
- generated C remains conservative and portable.

## 3. Pointer Model and Address-of Decision

### 3.1 Current pointer model

Current L0 model includes:

- pointer types (`T*`, nullable `T*?`),
- dereference (`*expr`),
- field access with pointer auto-deref behavior (`ptr.field`).

### 3.2 No address-of operator

`&` is intentionally excluded in L0.

Rationale:

- avoids exposing stack-address lifetime hazards,
- keeps ownership/lifetime rules simpler during bootstrap,
- keeps boundary complexity concentrated in runtime/kernel APIs.

### 3.3 No raw pointer arithmetic contract

Pointer arithmetic is not part of L0 surface semantics.

Pointer indexing is also not implemented in L0. Index syntax remains in the frontend AST/checker as preparatory surface
for future array work, but array/slice types do not exist in the language today, so every user-facing indexing
expression is currently rejected during semantic analysis.

## 4. Nullability, Casts, and Introspection

### 4.1 Nullability policy

- `T?` encodes nullable/optional values, `null` is the only empty value of a nullable type.
- Non-pointer nullable values are represented by wrapper forms in generated C (e.g., `l0_opt_*` structs).
- Nullable pointers use pointer-null representation (niche optimization).

### 4.2 Cast policy (`as`)

Casts are explicit and checked by type rules and runtime helpers where needed.

Important intent:

- narrowing and wrap/unwrap semantics are explicit,
- invalid casts are compile-time errors,
- runtime checks are used for defined-failure cases (panic), not UB.

### 4.3 Null propagation operator

The try expression syntax (`expr?`) propagates null out of the current function (returns early) and provides nullable
short-circuiting behavior with explicit type semantics.

### 4.4 Language intrinsics and type introspection

- `sizeof` exists as a language intrinsic and returns `int`.
- `ord` is a language intrinsic for enum tag introspection and returns `int`.

## 5. Early I/O Model

Stage-1/early-stage tooling intentionally prefers whole-file and simple console operations over complex streaming APIs.

Rationale:

- enough for compiler bootstrapping and diagnostics,
- avoids premature API surface complexity.

Concrete runtime API names are available in the `sys.rt` module and implemented in
`compiler/shared/runtime/l0_runtime.h`.

See also: [reference/standard-library.md](standard-library.md) for the current `std`/`sys` module API surface.

## 6. Name Disambiguation via Qualified References

Qualified names (`module.path::Name`) are used for cross-module disambiguation when open imports conflict.

Rationale:

- preserve open-import ergonomics for simple programs,
- provide explicit escape hatch for ambiguity,
- avoid introducing aliases/namespaces too early.

## 7. Integer Model Rationale

L0 semantics intentionally avoid inheriting host-C integer vagueness.

Policy:

- `int` is defined as 32-bit signed semantics,
- `byte` is 8-bit semantics,
- runtime helpers enforce defined behavior for overflow/division/mod edge cases.

At the stdlib layer, shared integer helper contracts belong in `std.integer`; modules such as `std.time` may consume
those helpers, but they should not own general-purpose arithmetic utilities. The `std.integer` surface remains
integer-focused.

Implementation details of generated helpers and typedef mapping are canonical in
[reference/c-backend-design.md](c-backend-design.md) and `compiler/shared/runtime/l0_runtime.h`.

## 8. Toolchain and Portability Policy

Policy-level decision:

- generated C should stay within conservative C99 usage,
- backend behavior should be deterministic and easy to reason about,
- platform/compiler specifics should be isolated to runtime boundary code.

Operational backend rules belong in [reference/c-backend-design.md](c-backend-design.md).

## 9. Future Evolution

Planned direction:

1. Keep L0 minimal and stable.
2. Expand language features in Dea/L1 when semantics are decision-complete.
3. Continue keeping unsafe/platform-specific details behind explicit runtime boundaries.

## 10. Comparison Operator Scope

The grammar admits `==`, `!=`, `<`, `<=`, `>`, `>=` between any operand types. The type checker intentionally restricts
which operand types each operator accepts; this section records the deliberate rejections.

Ordered comparison on `bool` is not accepted:

- `bool < bool`, `bool <= bool`, `bool > bool`, and `bool >= bool` are rejected as noninteger operands,
- the rejection is a design choice, not a deferred feature: booleans are two labels, not a scalar ordering, and a
  defined `true > false` meaning would add a footgun without a corresponding use case,
- the rejection diagnostic is `TYP-0170`, consistent with other noninteger operand rejections on the relational
  operators,
- callers who want to route on a boolean value should use `if` / `case (b) { true => ...; false => ...; }` or compare
  equality (`b == true`, `b != false`, or the simpler `b` / `!b` expressions).

Equality on `bool` remains accepted, unchanged:

- `bool == bool` and `bool != bool` return `bool`,
- this matches `case (b) { true => ...; }` dispatch and the general policy of treating `bool` as a scalar tag for
  equality but not for ordering.

Rationale:

- The Dea policy prefers a compile-time rejection over a defined-but-misleading ordering.

## 11. String Equality and Ordering

Values of type `string` are ARC-managed immutable byte sequences. Programs compare them for sameness of content, not for
identity of the underlying runtime instance, so their runtime representation (static versus heap, deduplicated or not)
is not observable through operators.

Current policy:

- equality (`==`, `!=`) on `string` compares by content bytes, backed by the runtime helper `rt_string_equals`.
- ordered comparisons (`<`, `<=`, `>`, `>=`) on `string` compare by byte-wise lexicographic order, backed by the runtime
  helper `rt_string_compare`.
- concatenation (`+`) on `string` accepts `string + string`, backed by the runtime helper `rt_string_concat`, and
  returns a fresh owned `string` result without mutating or consuming either operand.
- equality, ordering, and concatenation are consistent across the top-level operators and the corresponding `std.string`
  helper surface.
- string identity, meaning whether two values refer to the same runtime instance, is intentionally not exposed through
  any operator, cast, or intrinsic.

Rationale:

- value-based comparison is the only semantic consistent with `case`-over-string dispatch and with the backend's freedom
  to evolve dedup and arena strategies.
- `rt_string_concat` centralizes allocation and copy behavior, so operator lowering and library helper composition share
  the same ARC ownership contract by construction.
