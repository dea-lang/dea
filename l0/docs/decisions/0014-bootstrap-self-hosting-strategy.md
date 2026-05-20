# ADR-0014: Bootstrap and Self-Hosting Strategy

- Decision date: 2026-03-11
- Last edited: 2026-05-20
- Status: Accepted

## Context

Once the Stage 2 L0 compiler was implemented in L0, the question became: how do we validate that Stage 2 and Stage 1
produce identical output, and that Stage 2 can compile itself reliably?

## Decision

Triple-bootstrap is the definitive correctness gate for self-hosting:

1. Stage 1 (Python) compiles Stage 2 (L0) → produces binary A.
2. Binary A compiles Stage 2 → produces binary B.
3. Binary B compiles Stage 2 → produces binary C.

B and C must be byte-for-byte identical. If they differ, Stage 2 has a correctness bug (it produces different output
when compiled by different generations of itself).

`make triple-test` runs this check. It is a required finalization gate for any Stage 2 change.

## Rationale

- A single bootstrap pass (Stage 1 → Stage 2 binary) only proves Stage 2 can be compiled. It does not prove that Stage
  2's output is correct.
- Two passes prove that the Stage 2 binary is stable, but not that it is equivalent to Stage 1.
- Three passes (triple-bootstrap) prove stability of the self-hosted binary: if generations 2 and 3 agree, Stage 2 is
  self-consistent.
- Combining triple-bootstrap with Stage 1 ↔ Stage 2 whole-compiler `--gen` diffs gives a full semantic-equivalence
  check.

## Consequences

- CI must run `make triple-test` on every Stage 2 change.
- Platform-specific triple-bootstrap failures (Darwin arm64, Windows) are bugs to be tracked and fixed, not accepted
  divergences.
- The triple-bootstrap check must pass before any release is cut.

## Related Plans

- [l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md](../../work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md):
  established the triple-bootstrap test
- [l0/work/plans/bug-fixes/closed/2026-03-11-stage2-triple-bootstrap-self-hosting-bug-fixes-noref.md](../../work/plans/bug-fixes/closed/2026-03-11-stage2-triple-bootstrap-self-hosting-bug-fixes-noref.md):
  fixed self-hosting bugs exposed by triple-bootstrap
- [l0/work/plans/bug-fixes/closed/2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref.md](../../work/plans/bug-fixes/closed/2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref.md):
  Darwin arm64 triple-bootstrap native mismatch

## Current Docs

- [l0/docs/specs/compiler/stage1-contract.md](../specs/compiler/stage1-contract.md): Stage 1 contract and parity
  guarantees
- [docs/decisions/0001-two-stage-architecture.md](../../../docs/decisions/0001-two-stage-architecture.md): the broader
  two-stage architecture decision
