# ADR-0001: Foundational L0 Language Contract

- Decision date: 2025-12-06
- Last edited: 2026-05-20
- Status: Accepted

## Context

Dea/L0 was started from scratch in December 2025 as a small systems language intended to eventually host its own
compiler (Stage 2). All foundational architectural decisions were made informally during the first week of development
and recorded in a single design document (2025-12-06), before any formal planning infrastructure existed.

The core question: what non-negotiable invariants must L0 maintain regardless of how the language evolves later?

## Decision

Six mutually reinforcing constraints were adopted as the foundational contract:

1. **UB-free semantics**: language-level behavior must avoid undefined behavior. Invalid programs are rejected
   statically or fail with a defined runtime abort; host C UB must never be the outcome.

2. **Three-layer runtime boundary**: all platform quirks and allocator behavior are quarantined in a small C kernel. L0
   language semantics and the L0 runtime (written in L0) stay above the kernel boundary and remain UB-free. The three
   layers are: (a) L0 language + compiler, (b) L0 runtime/stdlib written in L0, (c) C kernel, the only layer that calls
   `malloc`, `fopen`, platform APIs, or uses C-specific types.

3. **No address-of operator**: `&` is excluded. All pointer values originate from kernel/runtime functions; L0 code
   treats pointers as opaque handles to heap storage. This eliminates stack-address lifetime hazards entirely from the
   language semantics layer.

4. **Fixed-width integer model**: `int` is defined as exactly 32-bit signed two's complement. `byte` is 8-bit unsigned.
   The backend emits fixed-width C typedefs (`int32_t`, `uint8_t`) and never bare `int`/`long`. L0 integer semantics are
   independent of host C integer widths (LP64, LLP64, etc.).

5. **Conservative C99 backend**: generated C targets a strict C99 subset. No GCC/MSVC extensions, no `__attribute__`, no
   nonstandard keywords. Toolchain-specific behavior is isolated to the C kernel. This keeps the generated C portable
   across compilers including TinyCC.

6. **Whole-file I/O at the language boundary**: early-stage tooling uses `rt_read_file_all` / `rt_write_file_all`; no
   streaming, no file handles at the L0 surface. Sufficient for a bootstrap compiler; avoids premature API surface
   complexity.

## Rationale

- UB-free semantics: a language that compiles to C can still have well-defined semantics. Quarantining UB in the kernel
  means L0 reasoning stays clean even though the output is C.
- Three-layer boundary: concentrating UB-risk code in one place makes it auditable and replaceable without touching
  language semantics.
- No address-of: eliminates an entire class of lifetime bugs during the bootstrap phase; any future `&` would require
  non-UB semantics and is explicitly deferred.
- Fixed-width integers: a bootstrap compiler must not produce programs whose behavior depends on the C compiler's
  integer model. Portability is guaranteed by definition rather than by luck.
- Conservative C99: TinyCC was an early explicit target; staying within the standard subset was the only way to
  guarantee compatibility across the range of potential downstream toolchains.
- Whole-file I/O: avoids designing a streaming or handle-based API before the language semantics are stable; the
  compiler only needs to read and write complete files.

## Consequences

- ARC string management (introduced 2025-12-29) was designed to stay above the kernel boundary: `rt_string_retain` and
  `rt_string_release` in the C kernel; ARC insertion logic in Stage 1 Python and later Stage 2 L0. See
  [ADR-0008](0008-arc-ownership-model.md).
- `new`/`drop` heap memory (introduced 2025-12-19) follows the same pattern: allocation through `rt_alloc` in the
  kernel, L0 semantics on top.
- The `with` statement (introduced 2026-02-08) was designed as the L0-level abstraction for deterministic cleanup,
  expressible entirely without `&` or stack-address exposure.
- The `int` = 32-bit decision drove the integer UB-helper layer (2025-12-17): `rt_div`, `rt_mod`, shift-range checks,
  all in the C kernel. See [ADR-0003](0003-integer-model.md).
- The conservative C99 rule outlasted the bootstrap phase and became a normative constraint on Stage 2 codegen. See
  [ADR-0011](0011-c-emission-strategy.md).

## Related Plans

None (pre-plan era). These decisions predate the formal planning infrastructure introduced in February 2026.

## Current Docs

- [l0/docs/reference/design-decisions.md](../reference/design-decisions.md): §1 (scope/goals), §2 (runtime boundary), §3
  (pointer model), §7 (integer model), §8 (toolchain/portability)
- [l0/docs/reference/c-backend-design.md](../reference/c-backend-design.md): C99 subset target, typedef mapping,
  toolchain abstraction
- [l0/docs/reference/architecture.md](../reference/architecture.md): three-layer pipeline structure
