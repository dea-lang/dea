# ADR-0007: Case Default Arm `_ =>` Wildcard Migration

- Decision date: 2026-06-07
- Last edited: 2026-08-29
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
- Phase 2: mechanically rewrite the remaining in-tree `case ... else` sites to `_ =>`, remove `else` as a `case` default
  entirely, and retire the old-spelling diagnostics `PAR-0237`, `PAR-0242`, and `PAR-0243`.

The rollout is complete. L0 Stage 1, L0 Stage 2, and L1 Stage 1 accept only `_ =>` as the `case` default arm. A value
arm after `_ =>` is `PAR-0234`, a second `_ =>` is `PAR-0236`, and `else` in a `case` is diagnosed as an unmatched
`else` (`PAR-0123`).

## Rationale

- `case` and `match` now share one catch-all spelling, removing a gratuitous inconsistency.
- Phase 1 closed the dangling-`else` hole without a flag-day break: the only hard error was the configuration that was
  already silently ambiguous, and no in-tree source matched it.
- Staging the change kept every committed step warning-clean or warning-only until source migration made Phase 2 safe.
- Reusing the existing wildcard and match-arrow tokens avoids any lexer or keyword change.

## Consequences

- Every current compiler stage accepts only `_ =>` defaults; an unmatched `else` reports `PAR-0123`.
- `PAR-0237`, `PAR-0242`, and `PAR-0243` are retired and remain unavailable for reassignment under the diagnostic-code
  stability policy.
- The L0 and L1 grammars both use `CaseStmt ::= "case" "(" Expr ")" "{" CaseArm* WildcardArm? "}"`.
- The AST default-arm representation remains spelling-neutral, so Phase 2 required no AST reshape.
- Production compiler sources and ordinary fixtures use `_ =>`; the compatibility parser branches and dedicated
  deprecated-spelling tests are removed.

## Related Plans

- [work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md](../../work/plans/features/closed/2026-06-07-case-default-arm-wildcard-phase1-noref.md):
  introduced `_ =>`, the `PAR-0242` deprecation, and the `PAR-0243` guard across L0 Stage 1/Stage 2 and L1 Stage 1
- [work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md](../../work/plans/refactors/closed/2026-06-08-migrate-case-else-defaults-to-wildcard-noref.md):
  canonicalized in-tree `case` defaults before terminal grammar removal
- [l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md](../../l1/work/plans/features/closed/2026-06-08-case-else-removal-l1-phase2-noref.md):
  removed the deprecated spelling from the L1 parser
- [l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md](../../l0/work/plans/features/closed/2026-06-08-case-else-removal-l0-phase2-noref.md):
  completed the migration in L0 Stage 1 and Stage 2 and retired the transitional diagnostics
- [l1/work/plans/bug-fixes/closed/2026-08-25-stage1-case-stray-else-recovery-boundary-noref.md](../../l1/work/plans/bug-fixes/closed/2026-08-25-stage1-case-stray-else-recovery-boundary-noref.md):
  preserved rejected `else` tokens as L1 Stage 1 `case` recovery boundaries without restoring the old default spelling
- [work/plans/bug-fixes/closed/2026-08-29-shared-editor-case-default-parity-noref.md](../../work/plans/bug-fixes/closed/2026-08-29-shared-editor-case-default-parity-noref.md):
  aligned the shared structural grammar and wildcard highlighting with the completed migration

## Current Docs

- [docs/specs/compiler/diagnostic-code-catalog.md](../specs/compiler/diagnostic-code-catalog.md): shared diagnostic
  registry with wildcard-only `case` meanings
- [l0/docs/reference/grammar.md](../../l0/docs/reference/grammar.md): L0 wildcard-only `case` grammar
- [l1/docs/reference/grammar.md](../../l1/docs/reference/grammar.md): L1 wildcard-only `case` grammar
