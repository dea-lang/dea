# ADR-0002: ARC Ownership Model

- Decision date: 2025-12-29
- Last edited: 2026-05-20
- Status: Accepted

## Context

Dea languages allocate heap-managed values (strings, and future reference-counted types). A memory management discipline
was needed that is safe, deterministic, and implementable without a garbage collector or a tracing runtime.

The L0 ARC ownership model was established when ARC-managed strings were introduced on 2025-12-29. L1 was designed to
adopt the same model with no semantic divergence, making ARC a Dea-wide contract rather than an L0-specific detail.

## Decision

All Dea language levels use automatic reference counting (ARC) as the memory management contract for heap-managed types:

- Every assignment to an ARC-managed slot retains the incoming value and releases the previous occupant
  (slot-replacement semantics).
- Temporaries produced during expression evaluation are retained on materialization and released after the statement
  that consumes them.
- Parameters of ARC-managed type are borrowed (not retained on entry) unless they are reassigned inside the function
  body, in which case an entry retain is inserted defensively.
- The `with` statement provides deterministic cleanup at block exit.
- `drop` frees `new`-allocated heap objects early; it operates on raw pointers, not on ARC-managed values.
- Compiler backends (Stage 1 and Stage 2) insert all retain/release calls; user code does not call them directly.

The runtime kernel (written in C) owns the retain/release primitives. Semantic details for each level are in
`l0/docs/reference/ownership.md` (the normative L0 source; L1 adopts the same rules).

## Rationale

- ARC is simpler to implement than tracing GC and requires no stop-the-world pauses or runtime scanning.
- Compiler-inserted calls keep user code ARC-clean without manual retain/release discipline.
- A single shared model across Dea levels avoids inventing different memory contracts for each level.
- The runtime kernel boundary keeps reference-count manipulation in auditable C, not scattered through generated output.

## Consequences

- Every Dea backend must correctly handle ARC cleanup across all control-flow paths: `if`, `while`, `for`, `with`,
  `match`, `break`, `continue`, `return`, and the null-propagation operator `?`.
- The slot-replacement rule is normative: reassignment of an ARC-managed variable always releases the old value before
  retaining the new one.
- L1 inherits the same ARC contract as L0 with no changes; L1-specific types that are ARC-managed follow the same rules.

## Related Plans

None (pre-plan era for the foundational contract; see L0 ADR-0008 for L0-specific fix plans).

## Current Docs

- [l0/docs/reference/ownership.md](../../l0/docs/reference/ownership.md): normative ARC rules, slot-replacement
  contract, borrowed parameter discipline, `with` and `drop` semantics
- [l0/docs/decisions/0008-arc-ownership-model.md](../../l0/docs/decisions/0008-arc-ownership-model.md): L0-scoped ADR
  with full rationale and related bug-fix plans
