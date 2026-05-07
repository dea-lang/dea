# Feature Plan

## Add named arguments for functions and constructors

- Date: 2026-04-22
- Status: Draft
- Title: Add named arguments for functions and constructors
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Parser / typing / lowering / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/docs/reference/grammar.md`
  - `l1/docs/reference/design-decisions.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/l0c_lib_test.l0`
- Related:
  - `l1/docs/roadmap.md`
  - `l1/docs/reference/design-decisions.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

L1 calls are positional-only today. This plan adds named arguments in call and constructor argument lists using the
syntax `name: value`, for example `move_point(p: mypoint, x: 0.0, y: -3.1)`.

The requested rule is intentionally strict: a call is either fully positional or fully named. Mixed positional/named
calls are rejected. Calling a variadic function with named arguments is out of scope here and is a separate follow-up
plan; it is not a sequencing dependency on the standalone variadic-functions plan, since both features independently
reject the cross-feature combination.

## Current State

1. `parser.l0` already uses `:` in parameter declarations and struct fields, but not inside call-site argument lists.
2. Call typing and constructor typing are strictly positional; argument order must match the declaration order.
3. Backend lowering assumes the source argument order is already the callee order.
4. The roadmap lists named arguments as backlog work with no active dedicated plan.

## Defaults Chosen

1. Named-argument syntax is `label: expr` inside the ordinary argument list delimiters.
2. The feature applies to top-level function calls and constructor calls that already use call syntax.
3. Calls are all-or-nothing: every argument in the call is positional or every argument is named.
4. Named arguments may appear in any source order. Resolution maps them onto declaration order by label.
5. Source evaluation order remains left-to-right as written, even when lowering must reorder values to match declaration
   order. This matches the dominant convention in modern languages with named or reorderable arguments — Python, C#,
   Kotlin, Swift, Scala, Ruby, Dart, and OCaml all evaluate call arguments in source order; C++ is the cautionary
   counterexample with unspecified cross-argument order.
6. Every declared parameter/constructor field must be supplied exactly once. Unknown labels, duplicates, and omissions
   are rejected.
7. Variadic-call interaction is explicitly out of scope for this plan.

## Goal

1. Parse and preserve named-argument labels in the AST.
2. Resolve named arguments against function parameters and constructor fields.
3. Lower named calls without changing source evaluation order.
4. Document the syntax and the all-or-nothing rule in the L1 grammar and design references.

## Implementation Phases

### Phase 1: Parser and AST

Extend the call/new-argument parser so each argument can carry an optional label. Reject mixed labeled and unlabeled
arguments in one call. Preserve labels in the AST so later phases can diagnose duplicates, unknown labels, and omissions
precisely.

### Phase 2: Typing and resolution

Teach `expr_types.l0` to:

- resolve named function-call arguments against parameter names,
- resolve named constructor-call arguments against the declared field order of the constructed type,
- reject duplicate or unknown labels,
- reject missing required arguments,
- keep positional calls unchanged.

### Phase 3: Lowering

When a named call arrives out of declaration order, lower it through temporaries as needed so source expressions still
evaluate left-to-right while the callee receives values in declaration order. Constructor lowering should follow the
same rule.

### Phase 4: Docs and tests

1. Update `l1/docs/reference/grammar.md` with named-call syntax.
2. Update `l1/docs/reference/design-decisions.md` to record the all-or-nothing rule and left-to-right evaluation
   contract.
3. Update `l1/docs/roadmap.md` to move this topic from bare backlog to an active standalone plan with a cross-reference.
4. Add parser, typing, backend, and end-to-end coverage for function and constructor calls.

## Diagnostics

1. This feature is likely to need dedicated parse-time diagnostics for malformed labeled arguments and dedicated typing
   diagnostics for duplicate, unknown, or missing labels and for mixed positional/named calls.
2. Provisionally reserve `PAR-0540` to `PAR-0559` for named-argument syntax diagnostics and `TYP-0760` to `TYP-0779` for
   named-argument typing and resolution diagnostics.
3. Re-check these provisional reservations against the live catalog at implementation time before assigning final
   numbers; if any of the suggested slots were used in the meantime, choose a different free block then.

## Non-Goals

1. Default argument values.
2. Partial naming (for example "first positional, then named") in a single call.
3. Variadic-call interaction.
4. Renaming or aliasing parameter names at the public API boundary.
5. Literal struct/enum syntax with `{}`; this plan is call-site syntax only.

## Verification Criteria

1. Fully positional calls keep their current behavior.
2. Fully named function and constructor calls parse, type-check, and lower correctly.
3. Mixed positional/named calls are rejected with clear diagnostics.
4. Lowering preserves left-to-right source evaluation order.
5. `l1/docs/reference/grammar.md`, `l1/docs/reference/design-decisions.md`, and `l1/docs/roadmap.md` reflect the new
   syntax and rules.
