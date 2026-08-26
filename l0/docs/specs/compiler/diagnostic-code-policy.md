# Diagnostic Code Policy

Version: 2026-08-26

Normative L0 Stage 1/Stage 2 supplement for compiler diagnostic-code assignment and reuse.

## Related Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md):
  normative shared registry of diagnostic code identifiers, levels, and meanings.
- [diagnostic-format.md](diagnostic-format.md): output rendering format for diagnostics.
- [stage1-contract.md](stage1-contract.md): Stage 1 compiler contract and stable external behavior.

This document supplements the shared diagnostic code catalog by defining how L0 Stage 2 reuses or allocates codes
relative to the L0 Stage 1 oracle.

## Core Rule

For any Stage 2 condition that is equivalent to an existing Stage 1 condition, Stage 2 MUST reuse the exact same
diagnostic code.

This applies to all diagnostic families, including internal compiler errors (`ICE-xxxx`).

## Equivalent Condition

An equivalent condition is defined by semantic meaning or invariant, not by implementation site.

Equivalent examples:

- the same parser rejection,
- the same signature or type-checking failure,
- the same backend invariant failure during equivalent lowering,
- the same CLI-mode failure with the same user-visible meaning.

Non-equivalent examples:

- a Stage 2-only NYI mode with no Stage 1 counterpart,
- a new implementation invariant introduced only by Stage 2 architecture,
- a new behavior added after Stage 1 feature freeze.

## Reuse Rules

1. Stage 2 MUST reuse the exact Stage 1 `XXX-NNNN` code for equivalent conditions.
2. Stage 2 MUST NOT repurpose an existing Stage 1 code with a different meaning.
3. Family parity alone is insufficient; `TYP-*` or `ICE-*` similarity does not satisfy this policy.
4. If no Stage 1 equivalent exists, Stage 2 MAY introduce a new code, provided it is unused across the repository.

## ICE Rule

`ICE-xxxx` codes are part of the same parity contract.

When Stage 2 ports a Stage 1 backend or emitter invariant:

- reuse the Stage 1 `ICE-xxxx` number if the invariant is equivalent,
- allocate a new unused `ICE-xxxx` number only if the invariant is genuinely Stage 2-only,
- never reuse a Stage 1 ICE number for a different invariant.

## Search and Allocation

Before assigning or changing a diagnostic code, search Stage 1, Stage 2, tests, and docs:

```bash
rg -n 'XXX-NNNN' compiler/stage1_py compiler/stage2_l0 docs
```

The search result is the registry of existing meaning. Code allocation is invalid if the same numeric code is already
used with a different meaning elsewhere in the repository.

## Examples

- Valid reuse: `L0C-9510` in Stage 2 for the same compile-mode NYI condition implemented by Stage 1.
- Invalid reuse: assigning Stage 2 `ICE-1300` to a new emitter precondition if Stage 1 already uses `ICE-1300` for a
  different backend invariant.
