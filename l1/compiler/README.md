# L1 Canonical Compiler

The sole `l1c` implementation lives in `src/` and is written in Dea/L0 (`.l0`). Native support, implementation tests,
and runners live in `support/`, `tests/`, and `scripts/`. Target stdlib/runtime inputs are physically owned under
`shared/`; accepted source files use `.l1` and target interfaces use `.l1m`.

Run `make build`, `make test-compiler TESTS="parser_test"`, and appropriate `test-compiler-trace` from `l1/`. See
[l1/AGENTS.md](../AGENTS.md) for the explicit upstream toolchain and validation contract. The compiler has no
intra-level stage selection or self-bootstrap requirement.
