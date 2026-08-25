# ADR-0013: Compiler Diagnostic Collection, Parser Recovery, and Phase Barriers

- Decision date: 2026-06-09
- Last edited: 2026-08-25
- Status: Accepted

## Context

Early Dea frontends exposed lexer and parser failures through single-error states or public exceptions. That design made
the first malformed token terminate useful frontend work, prevented a compilation from reporting independent syntax
errors together, and gave callers different success contracts across L0 Stage 1, L0 Stage 2, and L1 Stage 1.

Diagnostic collectors replaced those public failure channels and enabled partial parsing, but useful recovery requires
structural boundaries. Top-level-only recovery ejects the parser from a function after a malformed statement.
Synchronization that consumes an opening brace loses the corresponding block boundary. Conversely, recovery that keeps
unwinding nested unclosed blocks at end-of-file can emit the same block-close diagnostic once per nesting level.

The compiler also needs a clear phase boundary. A partial syntax tree is valuable for diagnostics and tooling, but it is
not a valid input to semantic analysis or code generation while recoverable frontend errors remain.

## Decision

The diagnostic collector is the authoritative public channel for lexer and parser errors. Lexer and parser APIs return
their available token or partial-parse state together with accumulated diagnostics; public single-error enums and
exceptions are not the compilation-success contract. Internal parser control flow may still use a private
synchronization mechanism.

The parser recovers at both top-level declaration boundaries and statement boundaries within the current block.
Statement synchronization preserves structural delimiters: it may stop at an opening brace or a recognized statement
start, and it does not consume a closing brace that belongs to the current block. Recovery must either advance or stop,
so malformed input cannot create a non-progress loop.

An unmatched statement-block close at end-of-file is terminal for parser recovery. The first failed close emits the
existing block-close diagnostic and marks parsing aborted; nested block loops, statement synchronization, and the
top-level loop honor that state and return their partial result without re-emitting the same end-of-file condition.

Recoverable lexical errors do not impose a pre-parse barrier, and a recoverable syntax error does not stop later parser
recovery. Parsing continues far enough to build useful partial structure and collect independent diagnostics. Semantic
analysis and code generation, however, do not run when the accumulated diagnostics contain errors.

The contract is behavioral across stages. Implementations may use different internal exception, nullable-result, token,
or collector representations, but they preserve the same recovery boundaries, terminal conditions, diagnostic codes, and
downstream gates.

## Rationale

- A collector allows one compilation to report several actionable errors while retaining stable phase and code
  identities.
- Declaration and current-block statement boundaries are the narrowest recovery points that preserve surrounding source
  structure without pretending malformed expressions are valid.
- Preserving braces prevents one local syntax error from turning valid statements inside the same function into spurious
  top-level diagnostics.
- Treating end-of-file as terminal after an unmatched block close reports the structural problem once and guarantees
  termination.
- Returning partial parse state serves diagnostics and future editor use, while the later phase gate prevents malformed
  structure from influencing semantic or backend behavior.

## Consequences

- Parser result types own diagnostics and partial syntax state; callers determine failure from the collector.
- Lexer diagnostics propagated through parser APIs remain lexer diagnostics rather than being recast as parser errors.
- Every synchronization loop requires explicit progress, brace-preservation, and end-of-file invariants.
- A failed statement does not abort the containing function when a safe statement boundary can be found.
- The parser may run after recoverable lexer errors, but the analyzer and backend never run on a unit whose collector
  contains errors.
- L0 Stage 1 remains the behavioral oracle where physical implementation differs, and native stages require parity
  coverage for recovery and diagnostic ordering.
- Logical lexer-error wrapper behavior and code-point column rules remain governed by ADR-0009; this ADR governs the
  broader collector, parser recovery, and phase-gating contract.

## Related Plans

- [l0/work/plans/refactors/closed/2026-02-24-stage2-lexer-parser-diag-unification.md](../../l0/work/plans/refactors/closed/2026-02-24-stage2-lexer-parser-diag-unification.md):
  established the Stage 2 collector result and top-level recovery surface
- [l0/work/plans/refactors/closed/2026-03-01-stage1-diagnostics.md](../../l0/work/plans/refactors/closed/2026-03-01-stage1-diagnostics.md):
  made diagnostics authoritative in Stage 1 and added declaration and statement recovery
- [work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md](../../work/plans/bug-fixes/closed/2026-06-07-stray-keyword-diagnostics-and-stmt-recovery-noref.md):
  restored statement-level recovery parity in the self-hosted parsers
- [work/plans/bug-fixes/closed/2026-06-08-shared-parser-recovery-noref.md](../../work/plans/bug-fixes/closed/2026-06-08-shared-parser-recovery-noref.md):
  preserved block structure during synchronization
- [work/plans/bug-fixes/closed/2026-06-09-shared-stop-parsing-at-eof-block-close-noref.md](../../work/plans/bug-fixes/closed/2026-06-09-shared-stop-parsing-at-eof-block-close-noref.md):
  made end-of-file terminal after an unmatched statement-block close
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog
- [l1/work/plans/bug-fixes/closed/2026-08-25-stage1-case-stray-else-recovery-boundary-noref.md](../../l1/work/plans/bug-fixes/closed/2026-08-25-stage1-case-stray-else-recovery-boundary-noref.md):
  preserved rejected `else` tokens as L1 Stage 1 `case` recovery boundaries for dedicated diagnostics

## Current Docs

- [docs/decisions/0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md](0009-logical-lexer-error-recovery-tokens-and-codepoint-columns.md):
  lexer-to-parser recovery-token and deferred-diagnostic contract
- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): authoritative
  diagnostic code meanings and phase ownership
- [l0/docs/reference/architecture.md](../../l0/docs/reference/architecture.md): L0 frontend phase and result
  architecture
- [l0/docs/specs/compiler/stage1-contract.md](../../l0/docs/specs/compiler/stage1-contract.md): Stage 1 diagnostic and
  parse-result contract
- [l0/docs/specs/compiler/stage2-contract.md](../../l0/docs/specs/compiler/stage2-contract.md): Stage 2 diagnostic and
  parse-result contract
