# L2 Compiler Architecture

Version: 2026-10-10

The canonical `l2c` implementation uses L1 `.l1` modules under `compiler/src/`, compiled by an explicitly installed L1
toolchain through `scripts/build_l2c.py`. Its pipeline retains the proven lexer, parser, source/interface module graph,
name/signature resolution, local/type analysis, per-module C backend, compile/link drivers, and managed preparation.

L2 target discovery accepts `.l2` files and extensionless logical module names, never `.l0` or `.l1` source files.
Interfaces use `.l2m` in emission, imports, dependency graphs, artifact associations, and preparation. Implementation
construction uses upstream `.l1m` conventions instead. Shared ABI and fingerprint domains remain compatible; native
runtime headers may retain `l1_real.h`, and upstream fingerprint bridge symbols remain `l1c_interface_fingerprint_*`.
These names do not authorize loading another level's files.

Target stdlib/runtime inputs live in `compiler/shared/l2/stdlib/` and `compiler/shared/runtime/`; private compiler
support is in `compiler/support/`. No symlinks or sibling checkout/build dependencies are permitted. The root shared
Python environment, vendored tools, and generic development helpers remain identified monorepo tooling.

Use `make build`, `make use-dev`, canonical normal/trace targets, and `make test-isolation`. The isolated build supplies
an installed L1 compiler while sibling level trees are inaccessible, then proves `.l2` execution without invoking L1.
See [l2/AGENTS.md](../../AGENTS.md), [l2/docs/reference/c-backend-design.md](c-backend-design.md), and
[docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md).
