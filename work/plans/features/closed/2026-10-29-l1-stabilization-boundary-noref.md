# Feature Plan

## Bound L1 stabilization and place successor work in L2

- Date: 2026-10-29
- Status: Completed
- Title: Define the L1 stabilization boundary and reassign successor capabilities to L2
- Kind: Feature
- Priority: High
- Scope: Shared
- Targets:
  - L1 roadmap, initiatives and feature plans
  - L2 roadmap, initiatives and deferred feature plans
- Origin: Project-wide capability allocation
- Porting rule: Reassign active scope explicitly; preserve completed predecessor history and independent target
  ownership.
- Target status:
  - L1: Complete
  - L2: Complete

## Summary

Create a finite L1 completion target for compilers and tools, including typed string formatting and explicit shell-free
process control. Move streams, file watching, networking, JSON and concurrency plans to L2. This is a planning-boundary
change, not completion of the remaining library features or activation of sustained L2 development.

## Delivered boundary

1. Establish the L1 stabilization initiative and public-API acceptance plan without duplicating existing plan ownership.
2. Move the five successor plans and wholly successor-owned active initiatives, restarting L2 initiative numbering at
   0001 and updating membership and links.
3. Remove escaping byte views, generic writer integration and concurrent in-memory process capture from L1 completion.
4. Align the coverage audit and both roadmaps with the finite target. Keep larger language features and C
   interoperability outside L1 stabilization.
5. Track the L1 borrowed-slice correction independently before library delivery.

## Verification

Markdown file links, ownership metadata, `python3 scripts/check_adr_impact.py --all-active`, staged ADR validation,
whitespace and root pre-commit passed. Draft capabilities remain distinct from delivered behavior. This boundary plan
establishes planning scope; the L1 bug-fix and existing feature plans own implementation evidence.

## ADR Impact

- Decision: Assign the bounded compiler/tool foundation to L1 and richer successor capabilities to L2.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/0026-l1-stabilization-boundary.md`
  - Rationale: Explicit feature placement preserves the independent compiler lineage while defining the predecessor
    baseline.
