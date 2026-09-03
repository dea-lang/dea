# ADR-0017: Documentation Publication Ownership and Cross-Repository Boundary

- Decision date: 2026-07-13
- Last edited: 2026-09-03
- Status: Accepted

## Context

Dea generates several documentation surfaces from canonical repository sources: validation output, standalone HTML, PDF
reference material, and a transformed Markdown tree suitable for a Jekyll/Chirpy destination. The initial publication
workflow coupled those responsibilities to a particular destination repository by checking it out, changing its managed
subtree, committing, and pushing from Dea's workflow.

That coupling made destination credentials part of Dea documentation production, let missing blog configuration fail an
otherwise valid build, and assigned branch and deployment choices to the wrong repository. Destination-specific
normalization also risked changing canonical generated Markdown solely to satisfy one site's renderer. Finally,
cross-repository writes and deployment-triggering operations require a stronger authorization boundary than local
generation or validation.

## Decision

The Dea repository owns:

- canonical documentation sources;
- validation of documentation generation;
- standalone Dea-owned documentation outputs;
- destination-neutral generated Markdown; and
- explicit export artifacts for downstream consumers.

Validation workflows never publish or perform cross-repository writes.

Destination-specific transformations, such as Chirpy front matter, permalink rewriting, and renderer-specific fragment
targets, are confined to the corresponding export step. They do not change the canonical generated Markdown or
standalone documentation solely to satisfy the downstream renderer.

Blog export is opt-in. When selected, Dea produces a complete archive as a workflow artifact and, when applicable, a
release asset. Missing destination repository or credential configuration does not make canonical documentation
production fail.

Dea may send an optional notification that an export is available, but it does not directly check out, modify, commit,
or push the destination repository. Each destination repository owns import selection, version tracking, branch choice,
commit creation, validation, and deployment under its own instructions and authorization policy.

Producing an artifact does not authorize publication. Any public, cross-repository, workflow-dispatching, or
deployment-triggering write requires the explicit and fresh authorization defined by the repository's remote publication
policy.

## Rationale

- Separating production from publication keeps canonical docs generation useful without destination credentials or
  availability.
- Artifact exchange is a stable boundary between independently governed repositories.
- Destination-local ownership of import, commit, and deployment respects that repository's branch, review, and release
  rules.
- Export-only normalization prevents one renderer's constraints from degrading other generated surfaces.
- Opt-in dispatch and explicit authorization make the external side effect visible instead of treating it as an
  incidental consequence of validation.

## Consequences

- Pull-request and ordinary validation jobs can generate and test documentation without publishing it.
- The Dea publication workflow may publish Dea-owned artifacts and Pages surfaces only through their explicit
  publication paths.
- Downstream documentation synchronization consumes an archive rather than relying on direct Dea writes to the
  destination working tree.
- Optional notification configuration can be absent without breaking canonical artifacts.
- The destination determines its own branch, commit message, validation, deployment, and version-marker behavior.
- Changes to a destination renderer are implemented in the exporter or destination import path, not by rewriting the
  canonical generated source unless the canonical output is itself wrong.
- Agents and maintainers treat local builds, artifact creation, dispatch, cross-repository commits, and public
  deployment as separate authorization boundaries.

## Related Plans

- [l0/work/plans/tools/closed/2026-03-04-release-oriented-docs-publishing-automation-noref.md](../../l0/work/plans/tools/closed/2026-03-04-release-oriented-docs-publishing-automation-noref.md):
  introduced generated HTML, PDF, and blog export publication surfaces
- [l0/work/plans/bug-fixes/closed/2026-03-21-chirpy-blog-export-link-target-parity-noref.md](../../l0/work/plans/bug-fixes/closed/2026-03-21-chirpy-blog-export-link-target-parity-noref.md):
  made blog publication opt-in and confined Chirpy compatibility fixes to the exporter
- [l0/work/plans/tools/closed/2026-03-23-decouple-chirpy-blog-publishing-noref.md](../../l0/work/plans/tools/closed/2026-03-23-decouple-chirpy-blog-publishing-noref.md):
  replaced direct destination writes with artifact exchange and optional notification
- [work/plans/tools/closed/2026-07-13-remote-publication-authorization-guardrails-noref.md](../../work/plans/tools/closed/2026-07-13-remote-publication-authorization-guardrails-noref.md):
  established the explicit authorization boundary for cross-repository and deployment-triggering writes
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the historical decision into the ADR catalog

## Current Docs

- [AGENTS.md](../../AGENTS.md): authoritative remote and publication authorization policy
- [CLAUDE.md](../../CLAUDE.md): compatibility router that surfaces critical publication safeguards
- [l0/docs/README.md](../../l0/docs/README.md): L0 documentation generation and publication surfaces
- [.github/workflows/l0-docs-validate.yml](../../.github/workflows/l0-docs-validate.yml): non-publishing validation
  workflow
- [.github/workflows/l0-docs-publish.yml](../../.github/workflows/l0-docs-publish.yml): explicit artifact, Pages,
  release, and optional downstream-notification workflow
