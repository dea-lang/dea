# AGENTS.md

Read [AGENTS.md](../AGENTS.md) first. Run L2 commands from `l2/`.

## Canonical Compiler and Ownership

`l2c` is the sole L2 compiler. Its implementation and implementation tests use `.l1` under `compiler/src/` and
`compiler/tests/`. Accepted L2 programs, fixtures, examples, and owned stdlib use `.l2`; generated target interfaces use
`.l2m`. `.l0`, `.l1`, and other source suffixes are rejected as L2 inputs; extensionless logical module names remain
supported. L2C diagnostics preserve the corresponding L1C numeric meanings; shared diagnostic families remain shared.

The physical L2 stdlib/runtime/support copies belong to L2. Never resolve `.l2` imports or preparation inputs from L1,
symlink sibling sources, or borrow sibling target build outputs. An explicitly selected L1 development toolchain is
permitted only for `.l1` compiler construction and implementation tests. No intra-L2 stages, parity, or triple bootstrap
exist.

## Bootstrap and Commands

Supply a compatible L1 toolchain explicitly; installed mode is the default, with no sibling-checkout or ambient PATH
fallback:

```sh
export L2_BOOTSTRAP_L1C=/absolute/installed-l1/bin/l1c
make venv
make build
make use-dev
make test
make test-extended
make test-compiler TESTS="parser_test"
make test-compiler-trace TESTS="lexer_test"
make test-compiler-trace-children
make test-ci
L2_ISOLATION_BOOTSTRAP_PREFIX=/absolute/installed-bookworm-l1 make test-isolation
```

For coordinated development reuse, first build L1, then explicitly select its generated launcher and mode:

```sh
export L2_BOOTSTRAP_MODE=development
export L2_BOOTSTRAP_L1C=/absolute/checkout/l1/build/dea/bin/l1c
make build
make test
```

Development mode requires the adjacent native binary, public headers, and semantic interfaces. The launcher supplies its
matching L1 source/build roots; unrelated active-shell roots and runtime overrides are removed, and upstream preparation
caches remain under L2's build directory. Invalid explicit selection fails without fallback.

`test-isolation` is the Docker Linux gate and requires an installed Linux/Bookworm-compatible L1 prefix through
`L2_ISOLATION_BOOTSTRAP_PREFIX`, separately from native macOS/Windows prefixes. Native four-platform compiler CI remains
distinct from this Linux isolation proof. Docker isolation never runs by default: explicitly request `run_isolation` in
standalone L2 CI or `l2_run_isolation` in Unified CI. Unified uses same-run development L1 handoffs; standalone L2 CI
retains an installed bootstrap. Unified's central L2 default remains off, with `default`/`on`/`off` manual choices.

The upstream compiler builds the `.l1` implementation using its selected L1 interfaces and native facilities. Set
`L1_CC` for that construction, and `L2_CC`/`L2_RUNTIME_CC` for L2 native target operations. Use supported GCC or Clang
16+ (Apple Clang must provide the required configuration controls); inspect the actual compiler executable/version in
all builders. The inherited legacy Clang limitation is not resolved by this split.

The built `l2c` operates on L2 programs using L2-owned support without invoking L1. `test-isolation` must deny access to
sibling level trees/artifacts while retaining only identified generic monorepo tools, shared Python environment, and
vendored dependencies. A path audit alone is insufficient; run the isolated build and target program checks.

## Validation and Planning

`test` is the fast gate; `test-extended` covers the broad normal suite. `test-ci` includes applicable CI-only cases,
trace sweeps, and child fixtures. Trace slow cases use explicit selectors or `test-compiler-trace-all`. Resolve test
ownership by the subject, not the filename suffix: `.l1` implementation tests use the installed L1 builder, while `.l2`
fixtures exercise `l2c`. Ownership failures in generated L2 programs need `.l2` reproducers; compiler implementation
failures may need `.l1` reproducers. Follow root portable path-comparison rules.

L2 has no distribution/release productization in this split. No compiler suite proves L1 artifact acceptance. Keep L1
feature plans in L1 until individually reassigned. New L2 plans omit `Stage` metadata, live under `l2/work/plans/`, and
link from [l2/docs/roadmap.md](docs/roadmap.md). Architectural records belong in `l2/docs/decisions/` with normal ADR
Impact and index rules. Shared work uses one root plan. Generic skills remain in `.agents/skills/`.
