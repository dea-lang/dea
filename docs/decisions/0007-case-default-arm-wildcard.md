# ADR-0007: Case Default Arm `_ =>` Wildcard Migration

- Decision date: 2026-06-07
- Last edited: 2026-06-08
- Status: Accepted

## Context

The `case` statement reused the `else` keyword for its default arm, and a `case` arm body is a bare `Stmt` with no
terminator. When an arm body is an unbraced `if`, a trailing `else` is grammatically ambiguous: the dangling `else` can
bind to the `if` or serve as the `case` default. A conventional recursive-descent parser resolves it silently as the
nearest `if`, stealing the intended `case` default and changing program meaning with no diagnostic.

The `match` statement already spells its catch-all arm `_ =>`, so `case` and `match` diverged on how a default arm is
written. The wildcard token and the match arrow already exist in every stage, so aligning `case` with `match` requires
no new tokens or keywords.

## Decision

`_ =>` becomes the canonical `case` default arm. The migration runs in two phases:

- Phase 1: introduce `_ => Stmt` as the canonical default (at most one default per `case`, in either spelling);
  deprecate the `else` default with warning `PAR-0242`; and reject the genuinely ambiguous configuration with error
  `PAR-0243` (an unbraced `if` *value-arm* body whose then-branch is immediately followed by `else`, where the `else`
  could still be the case default). The author resolves it by bracing the arm body or using a `_ =>` default.
  Default-arm bodies are not guarded, because once the default slot is taken a trailing `else` is unambiguous. `else`
  continues to parse so existing code keeps compiling.
- Phase 2: remove `else` as a `case` default entirely, drop `PAR-0243` (unreachable once `_` shares no token with `if`),
  and mechanically rewrite the remaining in-tree `case ... else` sites to `_ =>`.

The default arm is treated as a single slot regardless of spelling: a value arm after either spelling is `PAR-0234`, a
second default in any `_`/`else` combination is `PAR-0236`, and either spelling counts toward the at-least-one-arm rule
`PAR-0240`. `_` takes `=>`; the deprecated `else` does not. Per ADR-0005, L0 Stage 2 and L1 Stage 1 reuse the identical
diagnostic codes for these equivalent conditions.

## Rationale

- `case` and `match` now share one catch-all spelling, removing a gratuitous inconsistency.
- Phase 1 closes the dangling-`else` hole without a flag-day break: the only hard error is the configuration that was
  already silently ambiguous, and no in-tree source currently matches it.
- Staging the change keeps every committed step warning-clean or warning-only rather than error-breaking, because CI
  does not treat warnings as errors and `else` remains valid until Phase 2.
- Reusing the existing wildcard and match-arrow tokens avoids any lexer or keyword change.

## Consequences

- Programs using the `else` default now emit `PAR-0242`; they keep compiling until Phase 2 removes the spelling.
- The grammar carries a transitional `DefaultArm ::= WildcardArm | ElseArm` production and a `PAR-0243` disambiguation
  note in both level grammars; both are simplified in Phase 2.
- The AST default-arm representation is spelling-neutral (the warning is emitted at parse time), so Phase 2 removes the
  `else` spelling without an AST reshape.
- The in-tree `case ... else` source migration (about 95 default arms, mostly in the compilers' own `.l0` sources) is
  deferred to Phase 2.

## Related Plans

- [work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md](../../work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md):
  introduced `_ =>`, the `PAR-0242` deprecation, and the `PAR-0243` guard across L0 Stage 1/Stage 2 and L1 Stage 1

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): registers `PAR-0242`
  and `PAR-0243` and the generalized default-arm meanings
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): L0 transitional `case` grammar
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): L1 transitional `case` grammar
