# L2 Design Decisions

Version: 2026-10-10

L2 begins with the documented language, ABI, ownership, separate-compilation, and native-preparation semantics of its L1
donor. The split changes compiler/target identity and physical ownership, not those algorithms or public APIs. Its
canonical `.l1` implementation is built by installed L1; `.l2` programs and `.l2m` target interfaces remain L2-owned.

See [l2/docs/decisions/0001-independent-canonical-compiler.md](../decisions/0001-independent-canonical-compiler.md),
[l2/docs/reference/architecture.md](architecture.md), and [l2/docs/reference/ownership.md](ownership.md). Future
language decisions require their own scoped work; no L1 feature plan is automatically migrated here.
