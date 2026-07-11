# ADR-0007: Case Default Arm `_ =>` Wildcard Migration

- Decision date: 2026-06-07
- Last edited: 2026-07-11
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

The rollout is level-specific today: L0 Stage 1 and Stage 2 remain in Phase 1 for compatibility, while L1 Stage 1
completed Phase 2 on 2026-06-09. In L0, the default arm is one slot regardless of spelling: a value arm after either
spelling is `PAR-0234`, a second default is `PAR-0236`, and either spelling counts toward `PAR-0240`. In L1, only `_ =>`
occupies that slot; `else` in a `case` is diagnosed as an unmatched `else` rather than a deprecated default.

## Rationale

- `case` and `match` now share one catch-all spelling, removing a gratuitous inconsistency.
- Phase 1 closes the dangling-`else` hole without a flag-day break: the only hard error is the configuration that was
  already silently ambiguous, and no in-tree source currently matches it.
- Staging the change keeps every committed step warning-clean or warning-only rather than error-breaking, because CI
  does not treat warnings as errors and `else` remains valid until Phase 2.
- Reusing the existing wildcard and match-arrow tokens avoids any lexer or keyword change.

## Consequences

- L0 programs using the `else` default emit `PAR-0242` and continue compiling; the dangling-`else` ambiguity remains
  guarded by `PAR-0243`.
- L1 accepts only `_ =>` defaults. `PAR-0237`, `PAR-0242`, and `PAR-0243` are therefore L0-only diagnostics.
- The L0 grammar retains `DefaultArm ::= WildcardArm | ElseArm`; the L1 grammar contains only the wildcard form.
- The AST default-arm representation remains spelling-neutral, so L1 Phase 2 required no AST reshape.
- Production compiler sources and ordinary fixtures use `_ =>`; L0 retains dedicated deprecated-spelling tests and the
  parser compatibility surface.

## Related Plans

- [work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md](../../work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md):
  introduced `_ =>`, the `PAR-0242` deprecation, and the `PAR-0243` guard across L0 Stage 1/Stage 2 and L1 Stage 1
- L1 Phase 2 removed the deprecated spelling from the L1 parser on 2026-06-09.

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): registers the L0-only
  transitional diagnostics and shared wildcard-default meanings
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): L0 transitional `case` grammar
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): L1 Phase 2 `case` grammar
