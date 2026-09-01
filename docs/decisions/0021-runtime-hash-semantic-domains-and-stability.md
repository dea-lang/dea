# ADR-0021: Runtime Hash Semantic Domains and Stability

- Decision date: 2026-09-01
- Last edited: 2026-09-01
- Status: Accepted

## Context

The L0 and L1 runtimes expose tagged 32-bit hashes for scalar values, strings, raw data, and optional values. Type tags
keep unrelated value families in distinct SipHash input domains. Optional scalar wrappers are serialized from their
semantic fields so inactive C payload bytes and padding cannot affect the result.

Historical `rt_hash_opt_string` behavior treated an absent optional and a present empty string as the exact same tagged
input: the string tag, the optional flag, and zero payload bytes. Source comments and a regression test recorded that
behavior, but no design rationale justified discarding optional presence. A short-lived documentation update promoted
the collision into a public statement while the surrounding hash contract still lacked a clear stability boundary.

The correction must distinguish semantic presence without changing language equality, public runtime signatures,
ordinary string hashes, present optional-string hashes, the SipHash algorithm, container key behavior, or the separate
canonical fingerprints used for L1 interfaces and object metadata.

## Decision

Runtime hashes represent semantic values rather than incidental C object representations. Equal semantic values must
produce equal hashes. Type identity and optional presence are intentional hash input domains.

For strings, the runtime uses these conceptual domains:

- ordinary `string`: `STRING`
- present `string?`: `STRING | OPTIONAL`
- absent `string?`: `STRING | OPTIONAL | ABSENT`

Both levels reserve private hash flag bit `0x08` for `ABSENT`. A present optional string keeps the existing
`STRING | OPTIONAL` path and hashes its byte contents unchanged. An absent optional string hashes empty contents under
`STRING | OPTIONAL | ABSENT`. Optional boolean, byte, and integer hashing keeps its existing canonical semantic-wrapper
serialization; this decision does not redesign those functions around the new flag.

Repeated hashes of an equal value are deterministic within one runtime process. The result remains 32-bit, so distinct
values and distinct input domains may still collide. Exact numeric hash values are not stable identifiers and must not
be persisted or used as compatibility fingerprints. Hash values and accidental collisions are not API guarantees across
runtime versions, implementations, keys, or process executions.

This is a compatible 2.x runtime behavior correction. It does not change optional or string equality, language syntax,
runtime ABI signatures, `std.hashmap` or `std.hashset` string-key behavior, compiler bootstrap semantics, L1 interface
fingerprints, or object-metadata fingerprints.

## Rationale

- Optional presence is semantic state, so absent and present values should not feed SipHash the exact same tagged byte
  sequence.
- A reserved domain flag expresses absence without inventing a payload sentinel or changing string bytes.
- Leaving the present branch unchanged preserves every existing present optional-string hash under the same runtime key.
- Retaining canonical scalar serialization preserves the fix for padding and inactive-payload dependence.
- Stating a domain-separation contract avoids claiming that a 32-bit hash can make collisions mathematically impossible.
- Keeping exact outputs unstable leaves room for runtime keys and hash implementations to evolve without turning hashes
  into persistence or compatibility formats.

## Consequences

- The hash of an absent optional string changes relative to the historical runtime; present optional-string and ordinary
  string hashes do not change.
- L0 and L1 reserve one additional private hash flag bit and must keep the semantic domain mapping in parity.
- Focused tests require deterministic repeat calls and a representative difference between absent and present-empty
  optional strings under the current runtime key.
- Tests may lock domain routing, but must not claim that arbitrary distinct values can never collide after the 32-bit
  fold.
- Future runtime hash or key changes must preserve equal-value hashing and intentional type/presence domain separation,
  while exact numeric results remain non-contractual.

## Related Plans

- [work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md](../../work/plans/bug-fixes/closed/2026-09-01-shared-builtin-and-runtime-contract-observability-noref.md):
  established the shared hash ABI coverage, corrected optional scalar representation hashing, and finalized
  optional-string presence domains

## Current Docs

- [l0/docs/reference/design-decisions.md](../../l0/docs/reference/design-decisions.md): L0 runtime hash value policy
- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md): L0 `sys.hash` contract
- [l1/docs/reference/design-decisions.md](../../l1/docs/reference/design-decisions.md): L1 runtime hash value policy
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md): L1 `sys.hash` contract
