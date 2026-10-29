# ADR-0027: Validation Ownership and Dependency Routing

- Decision date: 2026-10-29
- Last edited: 2026-10-29
- Status: Accepted

## Context

L1 widened two time parameters while a comparison in L0's suite still required identical signatures. L1-only CI skipped
that comparison. Rewritten push history later made the comparison base unavailable, so conservative routing selected L0
and exposed the mismatch. The failing check validated a successor contract under the predecessor's name. Other shared
checks had also accumulated in level aggregates.

## Decision

1. A level validates its own behavior without reading successor source or artifacts. A successor owns comparisons
   against an explicitly supported predecessor contract. L1 owns runtime-header and trace-checker comparisons with L0.
2. Runtime compatibility covers a reviewed list of common signatures and representations. Intentional differences are
   explicit, including L0 `int` versus L1 `long` seconds for local time lookups. Private helpers do not become public
   API through comparison coverage.
3. Shared repository checks live under `scripts/tests/`. Root `make test` and `make test-extended` run them once before
   level delegates. Unified CI runs them in named repository-check steps on each selected native runner.
4. CI selects the changed level and consumers of affected predecessor compiler, runtime, or build inputs. Local tests,
   documentation, and CI delegates select their owning level; shared construction inputs select all enabled levels.
   Successor-only changes do not select predecessor compiler suites. L2 retains explicit enablement.
5. Push routing attempts to fetch an unavailable event base by exact object ID before comparing trees. Pull requests
   compare from their merge base. Missing comparison evidence produces an explanation and conservative validation of all
   enabled workloads.

## Rationale

Ownership makes a failure identify the contract that needs repair. Downstream routing tests the consequences of changing
a bootstrap compiler without treating a successor extension as a predecessor regression. Explicit compatibility lists
detect accidental drift while preserving deliberate level differences. Recovering comparison evidence avoids needless
work after history rewrites without silently skipping validation when recovery is impossible.

## Consequences

New shared checks must enter the repository gate instead of a predecessor aggregate. New predecessor construction paths
must be reflected in CI routing and its regression cases. Level-only local commands do not imply repository validation;
both remain available through root aggregates. This changes validation ownership and selection, not compiler or runtime
behavior, descriptor layout, or release authorization.

## Related Plans

- [work/plans/bug-fixes/closed/2026-10-29-shared-validation-ownership-and-routing-noref.md](../../work/plans/bug-fixes/closed/2026-10-29-shared-validation-ownership-and-routing-noref.md)

## Current Docs

- [AGENTS.md](../../AGENTS.md#validation-ownership)
- [MONOREPO.md](../../MONOREPO.md)
- [l0/docs/reference/standard-library.md](../../l0/docs/reference/standard-library.md)
- [l1/docs/reference/standard-library.md](../../l1/docs/reference/standard-library.md)
