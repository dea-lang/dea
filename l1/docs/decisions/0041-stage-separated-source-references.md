# ADR-0041: Stage-Separated Source References

- Decision date: 2026-10-06
- Last edited: 2026-10-06
- Status: Accepted

## Context

L1 has a bootstrap compiler written in L0 and a self-hosted compiler written in L1. Both share the bundled L1 standard
library and native implementation support. Some support lives physically under Stage 1 while both builders consume it.
Offline reference consumers need an independently usable document matching the compiler they receive.

## Decision

Select the stage before source inventory construction and Doxygen execution. Stage 1 and Stage 2 have independent XML,
HTML, Markdown, LaTeX, PDF, search, reports, and preview trees. Each document repeats the shared standard library,
runtime API, and explicitly selected native support. Only Stage 1 includes its native fingerprint bridge and internal
headers. L1 owns its generator and adapters; it does not import an L0-root-bound generator or mutate vendored m.css.

Distribute only Stage 2 references with Stage 2 tooling. A strict HTML and full indexed PDF build produces one offline
archive with `html/`, `pdf/`, and a schema-1 manifest. Numeric stage, package version, source revision/dirty state,
selected-input digest, tool provenance, success flags, and complete payload digests define its identity. Consumers
verify this identity and all files before use. A failed selected-stage invocation invalidates its prior archive without
removing the other stage or previously successful reference trees.

## Rationale

Independent databases prevent symbol resolution and search from depending on a sibling compiler. Explicit native input
ownership follows actual build contracts instead of directory names. Source-derived signatures preserve L0/L1 syntax
while C-like filtered declarations permit Doxygen rendering. Strict source-function coverage catches silent filtering
loss. Offline artifact verification separates local generation from platform packaging and publication.

## Consequences

- HTML generation does not need TeX or an installed compiler; distributable bundles require complete PDF tools.
- Stage 1 references remain developer artifacts. Productization and hosted workflows consume the Stage 2 bundle through
  an explicit handoff and remain separate implementation work.
- Consumers reject mismatched source/version identity, partial evidence, unsafe archive members, malformed manifests,
  corruption, missing local files, escaping links, and remote assets.
- Same-stage concurrent builds require different output parents; stage selection preserves sibling outputs.
- Remote publication remains governed by the repository's separate authorization and publication policy.

## Related Plans

- [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][source-plan]

## Current Docs

- [l1/docs/README.md][docs-guide]
- [l1/docs/project-status.md][project-status]

[docs-guide]: ../README.md#generated-source-references
[project-status]: ../project-status.md
[source-plan]: ../../work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md
