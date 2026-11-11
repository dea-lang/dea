# L2 Design Decisions

Version: 2026-11-11

L2 begins with the documented language, ABI, ownership, separate-compilation, and native-preparation semantics of its L1
donor. The split changes compiler/target identity and physical ownership, not those algorithms or public APIs. Its
canonical `.l1` implementation is built by installed L1; `.l2` programs and `.l2m` target interfaces remain L2-owned.

See [l2/docs/decisions/0001-independent-canonical-compiler.md](../decisions/0001-independent-canonical-compiler.md),
[l2/docs/reference/architecture.md](architecture.md), and [l2/docs/reference/ownership.md](ownership.md). Future
language decisions require their own scoped work; no L1 feature plan is automatically migrated here.

## Integer boundaries

Signed unary negation preserves `tiny`, `short`, `int`, or `long` and checks that the result fits, including in basic
and unchecked pointer-runtime modes. Negating the minimum value produces a controlled arithmetic failure.

Both shift operands are normalized through the common-integer-type lattice. Counts outside `[0, width)` are arithmetic
errors, with 32-bit `int`/`uint` and 64-bit `long`/`ulong` domains. Signed left shift is checked mathematical
multiplication by `2^count`, including negative values; unsigned left shift discards high bits. Signed right shift is
arithmetic and unsigned right shift is logical. These checks are independent of pointer-checking mode, and do not expand
constant evaluation. See [l2/docs/reference/grammar.md](grammar.md#6-expressions) for the expression contract.

The shared shift boundary decision is recorded in
[docs/decisions/0028-integer-shift-boundaries.md](../../../docs/decisions/0028-integer-shift-boundaries.md).
