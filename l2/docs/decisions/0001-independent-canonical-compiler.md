# ADR-0001: Independent Canonical L2 Compiler

- Decision date: 2026-10-10
- Last edited: 2026-10-10
- Status: Accepted

## Context

L2 begins as the mechanically retargeted former L1 Stage 2. Its implementation language and accepted target language are
distinct, even though the initial language semantics are substantively the same.

## Decision

The canonical compiler implementation is `.l1` under `compiler/src/`; build it with an explicitly supplied compatible
installed `L2_BOOTSTRAP_L1C`. Its upstream implementation-language interfaces use `.l1m`. The resulting `l2c` accepts
`.l2` source files and extensionless logical module names, emits/consumes `.l2m`, and uses L2-owned physical runtime and
stdlib copies. `.l0`, `.l1`, and other source suffixes are rejected as L2 source targets. Shared diagnostic families and
ABI semantics remain unchanged; level-specific driver diagnostics use `L2C-xxxx`.

L2 owns its tests, scripts, configuration, documentation, and generated artifacts. It must not symlink, read, or prepare
L2 programs from L1 checkout inputs or depend on sibling build outputs. Installed L1 is a construction dependency only.
No further language features or automatic migration of L1 feature plans is introduced.

## Rationale

Each level has an explicit compiler authority and owns its implementation, target standard library, runtime, and build
machinery. Mechanical copying preserves the proven behavior without requiring perpetual source parity between levels.

## Consequences

L2 has no second implementation, self-bootstrap gate, release productization, or hosted release workflows. Root shared
development tooling remains permitted; sibling compiler trees and local artifacts are not build inputs. The isolation
gate builds using an installed L1 toolchain with sibling trees inaccessible, then checks L2 target compilation without
invoking L1.

## Related Plans

- [work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../../work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  shared implementation and validation.

## Current Docs

- [l2/AGENTS.md](../../AGENTS.md)
- [l2/docs/roadmap.md](../roadmap.md)
- [docs/decisions/0022-single-compiler-level-lineage.md](../../../docs/decisions/0022-single-compiler-level-lineage.md)
