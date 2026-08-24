# Bug Fix Plan

## Isolate definite-liveness state across alternative branches

- Date: 2026-08-24
- Status: Completed
- Title: Analyze each if, match, and case alternative from the same incoming ownership state
- Kind: Bug Fix
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - L0 Python Stage 1
  - L0 Stage 2
  - L1 Stage 1
- Origin: Use the existing L0 Python Stage 1 and L1 Stage 1 `if` snapshot/restore logic plus the Python `case` flow as
  the starting model, then define one shared alternative-branch meet rule.
- Porting rule: Share the same incoming-state isolation and fallthrough meet semantics; preserve target-specific
  constant-flow capabilities without allowing one alternative to seed another.
- Target status:
  - L0 Python Stage 1: Implemented
  - L0 Stage 2: Implemented
  - L1 Stage 1: Implemented
- Subsystem: Definite liveness / Ownership flow / Statement analysis
- Modules:
  - `l0/compiler/stage1_py/l0_expr_types.py`
  - `l0/compiler/stage2_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
- Test modules:
  - `l0/compiler/stage1_py/tests/backend/test_codegen_overflow_and_control_flow.py`
  - `l0/compiler/stage1_py/tests/integration/test_case_statement.py`
  - `l0/compiler/stage2_l0/tests/expr_types_test.l0`
  - `l0/compiler/stage2_l0/tests/l0c_stage2_arc_trace_regression_test.py`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_arc_trace_regression_test.py`
- Related:
  - `work/plans/bug-fixes/closed/2026-04-10-shared-self-hosted-stage1-statement-parity-audit-noref.md`
  - `work/plans/bug-fixes/closed/2026-04-10-shared-match-exhaustiveness-return-path-parity-noref.md`
  - `work/plans/bug-fixes/closed/2026-06-22-shared-for-header-and-statement-flow-safety-noref.md`
- Repro: Drop a pointer before an `if` or exhaustive `match`, revive it in only the first alternative, leave the other
  alternative unchanged, and dereference it afterward; affected analyzers can incorrectly accept the dereference.

## Summary

Definite-liveness analysis must check mutually exclusive alternatives from the same incoming state and meet only their
reachable fallthrough states afterward. L0 Stage 2 checks the `else` branch after the mutated `then` state. All three
frontends check `match` arms sequentially without restoring the pre-match state, so revival or drop in one arm can
contaminate later arms and the post-match result.

L0 Python Stage 1 and L1 Stage 1 already isolate `if` alternatives, and Python Stage 1 isolates `case` alternatives.
Those correct paths provide implementation patterns but do not cover the shared `match` gap.

## ADR Impact

- Decision: Compute definite liveness as a meet of independently analyzed reachable alternatives.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is the standard interpretation of the existing dropped-variable safety rule and changes no ownership
    syntax, runtime ABI, or control-flow language semantics.

## Current State and Root Cause

1. L0 Stage 2 snapshots the incoming `if` state and the completed `then` state but does not restore the incoming state
   before checking `else`.
2. The Python and both native `match` paths enter each arm with whatever outer-binding state the previous arm left.
3. Pattern scopes protect arm-local declarations but do not protect mutations to bindings in outer scopes.
4. Return-flow/exhaustiveness logic is computed separately and therefore does not automatically select the correct set
   of fallthrough ownership states.

## Scope of This Fix

1. Snapshot the incoming liveness stack once for each alternative statement.
2. Restore that state before checking every `if`, `match`, and `case` alternative.
3. Collect only reachable fallthrough states; exclude returning or stopping branches from the post-statement meet.
4. Include the unchanged incoming state for an absent `else` or other implicit fallthrough path.
5. Preserve constant-condition pruning and unreachable diagnostics without letting dead branches mutate live state.
6. Keep pattern-local bindings scoped to their arms while meeting changes to outer bindings.
7. Add revive/drop permutations, returning arms, wildcard arms, and nested alternative regressions.

## Target-Specific Work

1. L0 Python Stage 1: retain correct `if`/`case` behavior and fix `match` arm isolation.
2. L0 Stage 2: fix both `if` and `match`, then audit `case` against the common helper.
3. L1 Stage 1: retain correct `if` behavior and fix `match`; audit its extended constant-flow cases.

## Diagnostics

No new codes are required. Reuse `TYP-0150` for uses not definitely alive and preserve existing unreachable and
missing-return codes.

## Non-Goals

1. Replacing loop fixed-point analysis.
2. Adding path-sensitive value predicates beyond existing constant conditions.
3. Changing `drop`, assignment-revival, or branch syntax.

## Verification

1. Assert revival in only one fallthrough alternative does not make a binding definitely alive afterward.
2. Assert a returning alternative is excluded from the post-statement meet.
3. Assert revival in every reachable alternative permits the later use.
4. Run focused expression and ownership trace tests for all targets, followed by root `make test-all` and L0 triple
   bootstrap.

## Verification Criteria

1. No alternative observes outer-binding liveness mutations from a sibling alternative.
2. Post-statement liveness is the meet of exactly the reachable fallthrough states.
3. All three frontends agree on diagnostics for the shared L0-compatible fixture set.

## Implementation Outcome

1. L0 Stage 2 restores the incoming liveness stack before checking `else`, matching the existing Python and L1 rule.
2. All three match analyzers restore the incoming state before every reachable arm and meet only reachable fallthrough
   states, including the implicit path of a non-exhaustive match.
3. Returning and stopping alternatives are excluded from post-statement meets; explicit exhaustive `case` statements
   with no fallthrough now restore the incoming state and propagate `STOPS`.
4. Unreachable wildcard match arms and L1 always-false case arms remain type-checked, but cannot emit liveness errors,
   mutate the outgoing meet, or export `break` and `continue` states.
5. Shared fixtures cover sibling contamination, partial revival/drop, all-arm revival, returning arms, wildcard arms,
   exhaustive stopping cases, nested loop captures, and L1 impossible case values.

## Verification Outcome

1. Focused Python, L0 Stage 2, and L1 Stage 1 expression-analysis suites passed.
2. The complete L0 and L1 ARC/memory regression scripts passed with branch-revival runtime coverage.
3. Repository-root `make clean test-all` passed: 1,461 L0 Python tests, all 55 L0 Stage 2 tests, triple bootstrap, all
   33 L0 broad trace targets, all 67 L1 Stage 1 tests, and all 44 L1 broad trace targets completed successfully.
4. The required independent read-only review found three additional dead-branch/stop-flow gaps, verified their fixes
   with targeted falsification probes, and reported no remaining actionable findings.
