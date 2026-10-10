# ADR-0043: Canonical Compiler Toolchain Delivery

- Decision date: 2026-10-10
- Last edited: 2026-10-10
- Status: Accepted
- Supersedes: [ADR-0041](0041-stage-separated-source-references.md)
- Supersedes: [ADR-0042](0042-self-hosted-toolchain-delivery.md)

## Context

L1 productization already established installation ownership, relocation, semantic consistency, offline documentation,
and exact-artifact verification. The compiler-lineage split changes its delivery compiler, not those guarantees.

## Decision

Build the installed canonical L1 compiler directly from its L0 implementation with the explicitly selected upstream L0
compiler, private construction workspace, and installed build-info overlay. Do not rename a repository-mode binary. The
delivered compiler must regenerate and verify its bundled semantic interface set against canonical sources; matching
runtime/stdlib rebuild inputs and symbol manifests remain part of the curated immutable payload.

Keep `install`, inventory-only `list-installed`, `dist`, `smoke-dist`, fixture `test-productization`, and separate
`test-productization-acceptance` responsibilities. Preserve inventory recovery, unowned-collision rejection, safe
archive extraction, atomic `DIST_RESULT`, transportable evidence, and exact archive/source/version/docs/harness
identity. Installed startup validates the physical prefix before CLI parsing, including help/version, without Python,
Make, or bootstrap compilers. Native preparation uses a separate writable cache and normal host native tools.

Generate one canonical reference inventory from the retained `.l0` compiler and its actual native support, L1 stdlib,
and runtime. Stage-free schema-2 references contain strict offline HTML and a full indexed PDF. Direct install may omit
docs; every distribution requires the matching verified bundle. Install it under `share/doc/dea/l1/autodocs/`. Retain
all still-valid integrity and provenance contracts of the superseded records.

## Rationale

Each level has an explicit compiler authority and owns its implementation, target standard library, runtime, and build
machinery. Mechanical copying preserves the proven behavior without requiring perpetual source parity between levels.

## Consequences

Old Stage 2 artifact acceptance remains historical evidence. Retargeted artifacts require fresh native acceptance on
Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64, including checkout-free verification. Compiler test gates do
not establish artifact acceptance. Stage-bearing schema-1 install/docs artifacts are not relabeled or accepted as the
new stage-free schema-2 product; use fresh prefixes and regenerate matching documentation.

## Related Plans

- [work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../../work/plans/refactors/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md):
  compiler retargeting and new evidence.
- [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md](../../work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md):
  prior implementation and historical acceptance.

## Current Docs

- [l1/docs/reference/productization-inventory.md](../reference/productization-inventory.md)
- [l1/docs/user/toolchain.md](../user/toolchain.md)
