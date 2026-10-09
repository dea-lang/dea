# ADR-0001: Bootstrap Adaptation Strategy

- Decision date: 2026-04-02
- Last edited: 2026-10-09
- Status: Accepted

## Context

The Dea/L1 compiler needed to get runnable quickly. The question was whether to start from scratch, write L1 in some
other language, or reuse the mature L0 toolchain as a starting point.

## Decision

L1 starts as a retargeted copy of the L0 Stage 2 compiler rather than a greenfield implementation:

- The runnable L1 compiler (`compiler/stage1_l0/`) starts from copied L0 Stage 2 sources and is retargeted to emit L1
  semantics.
- The L1 reference docs start from copied L0 reference material and are rewritten to describe the real L1 bootstrap
  tree.
- Copied implementation and docs are allowed to retain historical internal names (e.g., `l0_*` prefixes) when those
  names are bootstrap artifacts rather than user-facing semantics.
- Live L1-owned helpers and tests should use L1-oriented names (`l1c_*`, `l1c_lib_test`) when the subject is the L1
  compiler.

Select the upstream compiler explicitly. Local development defaults to the repo-local L0 Stage 2 compiler at
`../l0/build/dea/bin/l0c-stage2`, relative to `l1/`. `L1_BOOTSTRAP_L0C` overrides that path; an invalid explicit
selection fails without falling back to the default or searching ambient `PATH` for `l0c`. Windows selection supports
the corresponding `.cmd` wrapper. Prepare the development default with `make -C ../l0 use-dev-stage2`.

Delivery construction follows the explicit chain: upstream L0 compiler -> L1 Stage 1 -> repository-mode L1 Stage 2 seed
-> self-built, installed-mode L1 Stage 2 executable. The installer prepares an absent default upstream through L0's
`venv` and `install-dev-stage2` targets, preserving the L0 development alias. It builds the L1 stages in disposable
repo-local scratch and requires the seed to reproduce Stage 1's complete bundled semantic interface set byte-for-byte
before building the delivered executable. Neither the active L1 development alias nor existing development binaries
select the delivered stage or get replaced by packaging.

The installed compiler runs independently of L0, L1 Stage 1, and the Stage 2 seed. Its native startup, semantic
commands, and bundled-support preparation do not invoke Python, `uv`, or Make. Native output and preparation still
require a compatible host C compiler/linker and preparation host tools. Python-based installation and artifact
verification remain separate tooling operations. The delivery contract is recorded in
[l1/docs/decisions/0042-self-hosted-toolchain-delivery.md][delivery].

## Rationale

- Copying a known-good baseline keeps the first L1 compiler runnable early, before any L1-specific divergence
  accumulates.
- Incremental retargeting is safer than speculative greenfield design when the L1/L0 semantic delta is still small and
  being discovered.
- The copied baseline provides a regression anchor: divergence from L0 behavior must be intentional and documented.
- Explicit compiler selection makes the construction chain reproducible and prevents an activated installation or
  unrelated `PATH` alias from silently choosing the bootstrap compiler.
- A self-built delivery compiler and matching semantic interfaces separate construction dependencies from installed use.

## Consequences

- Building L1 requires the explicit upstream compiler contract in [l1/AGENTS.md][guidance]; installed use does not
  require the bootstrap chain or source checkout.
- L1-specific divergence from L0 semantics is documented in `l1/docs/reference/design-decisions.md` as it is introduced.
- Shared plans at the root `work/` level own decisions that apply to both levels; L1-only plans stay in `l1/work/`.

## Related Plans

- [work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md][scaffold]
- [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization]: bootstrap contract amendment;
  documentation handoff and plan closure remain active.

## Current Docs

- [l1/docs/reference/design-decisions.md][design-decisions]: §6 (bootstrap adaptation strategy)
- [l1/AGENTS.md][guidance]: explicit upstream selection.
- [l1/docs/reference/productization-inventory.md][inventory]: private bootstrap chain and installed dependency boundary.

[delivery]: 0042-self-hosted-toolchain-delivery.md
[design-decisions]: ../reference/design-decisions.md
[guidance]: ../../AGENTS.md
[inventory]: ../reference/productization-inventory.md
[productization]: ../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
[scaffold]: ../../../work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md
