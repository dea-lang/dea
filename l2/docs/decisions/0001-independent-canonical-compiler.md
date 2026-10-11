# ADR-0001: Independent Canonical L2 Compiler

- Decision date: 2026-10-10
- Last edited: 2026-10-11
- Status: Accepted

## Context

L2 begins as the mechanically retargeted former L1 Stage 2. Its implementation language and accepted target language are
distinct, even though the initial language semantics are substantively the same.

## Decision

The canonical compiler implementation is `.l1` under `compiler/src/`; build it with an explicitly supplied compatible
`L2_BOOTSTRAP_L1C`. The default `L2_BOOTSTRAP_MODE=installed` requires a complete installed L1 prefix. Explicit
`L2_BOOTSTRAP_MODE=development` permits a generated L1 development launcher with matching native binary, public headers,
and semantic interfaces for coordinated development and same-run Unified CI reuse. Its upstream implementation-language
interfaces use `.l1m`. The resulting `l2c` accepts `.l2` source files and extensionless logical module names,
emits/consumes `.l2m`, and uses L2-owned physical runtime and stdlib copies. `.l0`, `.l1`, and other source suffixes are
rejected as L2 source targets. Shared diagnostic families and ABI semantics remain unchanged; level-specific driver
diagnostics use `L2C-xxxx`.

L2 owns its tests, scripts, configuration, documentation, and generated artifacts. It must not symlink, read, or prepare
L2 programs from L1 checkout inputs or depend on sibling target build outputs. Explicitly selected L1 is a construction
dependency only; development selection has no implicit sibling-checkout or PATH fallback. Bootstrap environments discard
unrelated active-shell input roots and keep upstream writable preparation caches under L2's build directory. No further
language features or automatic migration of L1 feature plans is introduced.

## Rationale

Each level has an explicit compiler authority and owns its implementation, target standard library, runtime, and build
machinery. Mechanical copying preserves the proven behavior without requiring perpetual source parity between levels.

## Consequences

L2 has no second implementation, self-bootstrap gate, release productization, or hosted release workflows. Root shared
development tooling remains permitted. Sibling target inputs are never borrowed; the selected predecessor may provide
development construction inputs only in explicit development mode. Unified CI reuses validated predecessor paths on the
same runner and checkout without reinstalling L1; standalone L2 CI defaults to an installed bootstrap. The opt-in
isolation gate builds using an installed L1 toolchain with sibling trees inaccessible, then checks L2 target compilation
without invoking L1. Isolation is not a default CI workload; run it again for changes to construction or ownership
boundaries, since historical proof applies to the tested implementation.

## Related Plans

- [work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../../work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  completed independent target ownership, explicit installed/development construction, and native/isolation validation.

## Current Docs

- [l2/AGENTS.md](../../AGENTS.md)
- [l2/docs/roadmap.md](../roadmap.md)
- [docs/decisions/0022-single-compiler-level-lineage.md](../../../docs/decisions/0022-single-compiler-level-lineage.md)
