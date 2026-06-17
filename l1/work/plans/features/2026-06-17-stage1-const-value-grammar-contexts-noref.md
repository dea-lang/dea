# Feature Plan

## Compile-time constant values in array bounds and `case` arms

- Date: 2026-06-17
- Status: Draft
- Title: Compile-time constant values in array bounds and `case` arms
- Kind: Feature
- Severity: High
- Stage: L1
- Subsystem: Parser / AST / type resolution / const evaluation / case checking / backend / docs
- Modules:
  - `l1/compiler/stage1_l0/src/ast.l0`
  - `l1/compiler/stage1_l0/src/parser.l0`
  - `l1/compiler/stage1_l0/src/type_resolve.l0`
  - `l1/compiler/stage1_l0/src/expr_types.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/docs/reference/grammar.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/parser_test.l0`
  - `l1/compiler/stage1_l0/tests/type_resolve_test.l0`
  - `l1/compiler/stage1_l0/tests/expr_types_test.l0`
- Related:
  - `l1/work/plans/features/closed/2026-04-18-l1-const-declarations-noref.md`
  - `l1/docs/roadmap.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`
- Repro: None

## Summary

Named compile-time constants cannot currently appear in positions where the grammar expects a constant value. The parser
rejects array type suffixes that carry an identifier instead of an integer literal, and case arms that carry a named
constant instead of a literal. This plan extends those two grammar contexts to accept constant-expression syntax and
moves type/value validation from parse time to semantic time, leaving a clean path for future arithmetic const
expressions.

## Current State

1. `ps_parse_type` accepts only an integer-literal token inside an array type suffix `T[...]`. Any identifier token
   causes a `PAR-0620` parse error rather than a semantic error.

2. Case arm parsing accepts only literal tokens (`CaseLiteral`). Named constants cannot start a case arm.

3. `TYP-0800` fires for any non-literal array length, including named constants that would have a known value.

4. The following valid fragment is rejected today:

   ```dea
   const NUM_LANG: int = 25;
   const messages: string[NUM_LANG] = [...];
   ```

5. There is no central constant evaluator; const-initializer validation uses inline checks in the type resolver.

## Goal

Allow named compile-time constants wherever the source grammar accepts a constant value, starting with:

1. Fixed-size array type suffixes: `string[NUM_LANG]`.
2. `case` arm values: `OK => ...`.

Do not change runtime semantics. Do not add arithmetic or full constexpr evaluation in this pass.

## Non-Goals

- General constexpr functions.
- Arbitrary compile-time expression evaluation or arithmetic (`T[A + B]`, `T[A * 2]`).
- Non-constant `let` variables in array lengths or case arms.
- Aggregate constants as array lengths or case arm values.
- Changes to match-pattern semantics.
- Symbolic array bounds in emitted ABI or interface signatures; resolved lengths stay concrete integers.

## Design

### ConstValue

Introduce a shared semantic concept `ConstValue` to represent compiler-known values after semantic resolution. The
minimum set of kinds:

- `int` (required for array bounds)
- `byte`, `bool`, `string`, `float`, `double` (required for case arms)
- `bigint`, `null` only if already meaningful in L1 const initializers

Aggregate/constructor constant support for const initializers remains separate; array bounds and case arms use narrower
domains.

### Constant-expression contexts

Define distinct contexts rather than one undifferentiated rule:

| Context                 | Accepted domain                                                        |
| ----------------------- | ---------------------------------------------------------------------- |
| Array bound             | positive compile-time `int` constant                                   |
| Case arm                | compile-time scalar/string/bool constant comparable with the scrutinee |
| Const initializer       | existing top-level const initializer subset (unchanged)                |
| Interface const literal | serialized already-accepted constant values (unchanged)                |

Initial source expression subset for array bounds and case arms:

- integer, string, byte, bool, float, or double literal
- identifier referring to a visible `const`
- qualified identifier referring to a visible `const`

Leave the evaluator dispatch structured for future binary-op support without redesigning the AST.

## Implementation Phases

### Phase 1: AST changes

Extend `TypeSuffix` to retain an expression reference for array bounds before resolution:

```text
TypeSuffix {
    kind
    array_len: int          // resolved value or 0 until resolved
    array_len_expr: ExprId  // points to literal or name/reference; null/invalid when not applicable
    span
}
```

- `T[25]`: `array_len_expr` points to an integer literal; `array_len` may be 25 immediately.
- `T[N]`: `array_len_expr` points to a name/reference expression; `array_len` is 0 until resolution.
- `T[]` (slice): no `array_len_expr`.

The parser must not resolve names; name resolution happens in semantic phases.

### Phase 2: Parser changes

**Array type suffix.** Change the parse rule from:

```ebnf
ArraySuffix ::= "[" IntLiteral "]"
```

to:

```ebnf
ArraySuffix ::= "[" ConstIntExpr "]"
```

where `ConstIntExpr` (for this pass) accepts an integer literal, an identifier, or a qualified identifier. Implement
this with a small dedicated helper (`ps_parse_const_value_expr` or similar) rather than invoking the full expression
parser inside type syntax. Keep parser errors only for syntactically invalid forms; do not fire `PAR-0620` merely
because the token is an identifier.

Also update any lookahead or helper that recognizes array constructors (`int[3](...)`) so it also recognizes
`int[N](...)`. Do not leave a split where type annotations accept `T[N]` but constructors require an integer literal.

**Case arm.** Change the parse rule from:

```ebnf
CaseLiteral ::= IntLiteral | FloatLiteral | ByteLiteral | StringLiteral | BoolLiteral
CaseArm     ::= CaseLiteral "=>" Stmt
```

to:

```ebnf
CaseArmValue ::= ConstScalarExpr
CaseArm      ::= CaseArmValue "=>" Stmt
```

where `ConstScalarExpr` accepts all literal tokens already accepted today, plus identifier and qualified identifier.
Update case arm recovery/lookahead so identifiers can start case arms. Do not fire `PAR-0238` for a bare identifier in
case arm position.

### Phase 3: Const evaluator

Add a small reusable evaluator module or well-factored entry point in the semantic passes:

```text
const_eval_expr(ctx, expr_id) -> ConstValue?
const_eval_int_bound(ctx, expr_id) -> int?
const_eval_case_value(ctx, expr_id) -> ConstValue?
```

Initial support:

- All literal kinds (integer, string, byte, bool, float, double, null as applicable)
- Name reference to a `const` declaration: evaluate the const's initializer and cache the result
- Qualified name reference to a `const` declaration: same

Cache the evaluated result on the symbol or in a side table to avoid repeated evaluation. Detect cycles:

```dea
const A: int = B;
const B: int = A;  // cycle
```

Design the dispatch so that future binary-op support is a local addition:

```text
binary op:
    evaluate lhs
    evaluate rhs
    apply checked compile-time operation
```

### Phase 4: Semantic array-bound resolution

During type resolution, call `const_eval_int_bound` on the `array_len_expr` and apply:

- value must be compile-time known
- value must be `int`
- value must be positive

For imported constants, apply the same evaluator if the interface carries enough information; otherwise emit a clear
diagnostic with a TODO comment for cross-module resolution.

### Phase 5: Semantic case-arm checking

During case checking, call `const_eval_case_value` on each arm value and apply:

- value must be compile-time known
- value kind must be allowed for case arms (scalar/string/bool, not aggregate)
- value must be comparable to the scrutinee using existing case rules
- duplicate evaluated arm values must be rejected (extend `TYP-0108` to cover const-evaluated duplicates)

### Phase 6: Docs and tests

1. Update `l1/docs/reference/grammar.md`:

   ```ebnf
   ArraySuffix  ::= "[" ConstIntExpr "]"
   CaseArmValue ::= ConstScalarExpr
   ```

   Add a note: a compile-time constant expression is resolved semantically; in this stage, the accepted subset is
   literals and references to visible `const` declarations; future stages may extend this to arithmetic and selected
   pure compile-time operators.

2. Update `docs/specs/compiler/diagnostic-code-catalog.md` with any new or changed codes.

3. Add positive tests:

   ```dea
   // array bound from named const
   module test;
   const N: int = 3;
   let xs: int[N] = [1, 2, 3];
   ```

   ```dea
   // array bound in function parameter
   module test;
   const N: int = 3;
   func f(xs: int[N]) -> int { return 0; }
   ```

   ```dea
   // named const in case arm (int)
   module test;
   const OK: int = 200;
   func f(status: int) -> int {
       case (status) { OK => return 1; _ => return 0; }
   }
   ```

   ```dea
   // named const in case arm (string)
   module test;
   const QUIT: string = "quit";
   func f(cmd: string) -> int {
       case (cmd) { QUIT => return 1; _ => return 0; }
   }
   ```

4. Add negative tests:

   ```dea
   // non-const let in array bound
   module test;
   let N: int = 3;
   let xs: int[N] = [1, 2, 3];
   // expected: array length is not a compile-time constant
   ```

   ```dea
   // zero array bound
   module test;
   const N: int = 0;
   let xs: int[N] = [];
   // expected: array length must be positive
   ```

   ```dea
   // wrong type array bound
   module test;
   const N: string = "3";
   let xs: int[N] = [1, 2, 3];
   // expected: array length constant is not an int
   ```

   ```dea
   // non-const let in case arm
   module test;
   let OK: int = 200;
   func f(status: int) -> int {
       case (status) { OK => return 1; _ => return 0; }
   }
   // expected: case arm value is not a compile-time constant
   ```

   ```dea
   // duplicate case arm value after const evaluation
   module test;
   const A: int = 1;
   const B: int = 1;
   func f(x: int) -> int {
       case (x) { A => return 1; B => return 2; _ => return 0; }
   }
   // expected: duplicate case arm value
   ```

## Diagnostics

The new diagnostics fall into existing SIG and TYP families. No new family is introduced; reserve unused codes in nearby
existing ranges.

**SIG family (const evaluation):**

- `SIG-0201`: Compile-time constant cycle: const definition directly or indirectly refers to itself.

  Suggest reusing the unused slot immediately following `SIG-0200` ("const initializer must be compile-time constant").
  Re-check this slot against the live catalog at implementation time before assigning.

**TYP family (array bound const errors), near the existing `TYP-08xx` array range:**

- `TYP-0815`: Array length expression is not a compile-time constant.

- `TYP-0816`: Array length constant is not an `int`.

- `TYP-0817`: Array length constant is not positive.

  `TYP-0800` ("Array length must be a positive `int` literal") changes meaning to cover only syntactically un-parseable
  or trivially non-constant forms; the semantic cases above replace its role for name-reference inputs.

**TYP family (case arm const errors), near the existing `TYP-0106`-`TYP-0111` case range:**

- `TYP-0112`: Case arm value is not a compile-time constant.
- `TYP-0113`: Case arm value is an aggregate constant and cannot be used as a scalar case arm value.

All provisional slot suggestions above must be re-checked against the live catalog at implementation time; any conflicts
require choosing a different free slot at that point.

**Diagnostics ownership:**

- Parser: syntax errors only; does not report "expected integer" merely because the token is an identifier.
- Semantic/type resolver: reports all non-constant, wrong-type, non-positive, unresolved, or unsupported
  constant-expression errors.

## Interface/Import Considerations

For array types in `.l1m` interface signatures, emit resolved numeric lengths (`string[25]`, not `string[NUM_LANG]`).
For exported `const` declarations, keep or improve canonical literal serialization so downstream modules can evaluate
references to imported constants. If imported const values are not yet available through the interface format, implement
local/module constants first and emit a clear diagnostic plus TODO for cross-module const references.

## Acceptance Criteria

1. The following program compiles without error:

   ```dea
   const NUM_LANG: int = 25;
   const hello_world_messages: string[NUM_LANG] = [...];
   ```

2. `T[N]` works in type annotations and array constructor syntax wherever `T[25]` worked.

3. Named `const` references work as `case` arm values for scalar/string/bool constants.

4. Non-`const` names are rejected semantically, not syntactically.

5. Resolved semantic types contain concrete array lengths.

6. A central constant evaluator or clearly factored evaluator entry point exists so future `T[A * 2]` support does not
   require AST redesign.

7. All positive and negative tests listed in Phase 6 pass.

8. Grammar documentation reflects the new `ConstIntExpr` and `ConstScalarExpr` forms.
