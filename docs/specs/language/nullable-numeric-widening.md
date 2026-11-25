# Nullable numeric widening

Version: 2026-11-25

This is the Dea-wide language contract. Each level supplies its own numeric types, type-based implicit widening pairs
and supported nullable depths. Compiler conformance is tracked in
[work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md][plan].

## Conversion of a value

1. **Nullable injection** converts a value of any type `T` to `T?` by constructing a present value containing the
   original value. When `T` is itself nullable, the new outer layer is present even when its payload is absent.
2. **Lifted widening** applies when the level already permits a type-based implicit numeric widening from `S` to `T`.
   The corresponding conversion from `S?` to `T?` maps absence to absence. For a present source, it widens the payload
   and constructs a present destination. This rule applies recursively to matching nullable layers.
3. **Additional destination layers** are introduced by injection *after* widening through the source layers. Every
   additional layer is present. An implicit conversion must preserve each existing layer and its presence state.

Evaluate the source expression exactly once, including when its value is absent. Only a present numeric payload is
widened. The conversion preserves the numeric value and introduces no runtime failure.

For example, a `byte??` has three distinguishable states where nested nullables are supported. Conversion to `int??`
preserves outer absence, outer presence with inner absence, or two present layers containing the widened byte.
Conversion to `int???` wraps each of those results in one more present layer.

## Examples

| Source   | Destination | Implicit result                                                                               |
| -------- | ----------- | --------------------------------------------------------------------------------------------- |
| `byte`   | `int`       | Ordinary numeric widening                                                                     |
| `byte`   | `int?`      | A present widened integer                                                                     |
| `byte?`  | `int?`      | Absence, or a present widened integer                                                         |
| `byte?`  | `byte??`    | A present outer layer containing the original optional                                        |
| `byte?`  | `int??`     | A present outer layer containing the widened optional, including when that optional is absent |
| `byte??` | `int??`     | Both layers preserved                                                                         |
| `byte??` | `int???`    | Both layers preserved inside a new present layer                                              |
| `int?`   | `long?`     | Lifted where the level permits `int` to widen to `long`                                       |
| `float?` | `double?`   | Lifted where the level permits `float` to widen to `double`                                   |
| `int?`   | `byte?`     | Rejected because the payload would narrow                                                     |
| `byte?`  | `int`       | Rejected because a layer would be removed                                                     |
| `byte??` | `int?`      | Rejected because a layer would be removed despite the permitted payload widening              |

## Where the rule applies

All contexts that permit implicit assignment conversions use this rule, including initializers, assignments, arguments
and returns. An explicit `as` cast to a destination reachable by the new implicit conversion accepts the same source and
produces the same value under the level's existing cast rules.

Only type-based implicit numeric widenings and their recursive nullable liftings qualify. Nullable injection adds layers
around the result. Lifting injection itself would give the wrong outer presence in the `byte?` to `int??` example.
Contextual conversions of literal expressions and other assignment conversions do not supply a payload widening.
Existing numeric widening pairs, operator compatibility and promotion, nullable equality, and other explicit cast rules
retain their own definitions. This rule grants no covariance to pointers, arrays, slices or other type constructors.

The decision and rationale are recorded in [docs/decisions/0029-lifted-nullable-numeric-widening.md][adr].

[adr]: ../../decisions/0029-lifted-nullable-numeric-widening.md
[plan]: ../../../work/plans/features/2026-11-25-shared-nullable-numeric-widening-noref.md
