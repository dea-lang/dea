# L2 Bundled Interfaces and Native Preparation

Version: 2026-10-10

The L2 builder supplies public headers and verified bundled `.l2m` interfaces from L2-owned `.l2` stdlib sources.
Semantic operations consume those interfaces independently of native preparation. Target `l2c --prepare-stdlib` derives
native stdlib/runtime support from physical L2-owned inputs into the selected writable cache. No L1 source, `.l1m`
target interface, runtime source tree, or compiler invocation participates in ordinary L2 target preparation.

`L2_STDLIB_CACHE` selects an explicit cache, subject to the same managed-identity, integrity, locking, and reuse rules
as the inherited preparation contract. `L2_CC`, `L2_CFLAGS`, runtime selectors, and CLI options describe L2 target host
tools. The implementation build instead uses the installed L1 toolchain and its normal L1 native facilities.

Retain the initial compatible ABI names, including `l1_real.h`, without treating those names as sibling ownership. L2
installation/productization is outside this milestone. See
[docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md) for preparation options and failure
contracts, and [l2/AGENTS.md](../../AGENTS.md) for isolation validation.
