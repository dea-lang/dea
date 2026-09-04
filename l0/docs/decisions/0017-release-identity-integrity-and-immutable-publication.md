# ADR-0017: Release Identity, Integrity, and Immutable Publication

- Decision date: 2026-03-16
- Last edited: 2026-09-04
- Status: Accepted

## Context

An L0 release publishes compiler binaries, generated documentation, integrity metadata, and downstream documentation
updates. Early release automation used date-shaped `v*` tags and generated release notes from Git history. Later work
introduced semantic versions, curated release notes, versioned documentation artifacts, a public monorepo namespace, and
immutable GitHub releases.

These pieces form one public contract. If tag identity, reviewed content, artifact completeness, or publication timing
are inferred independently from workflow implementation, a release can be duplicated, published partially, or changed
after users begin relying on it.

## Decision

An official stable L0 release follows this contract:

1. Its identity is a stable `l0-vX.Y.Z` tag in the public `dea-lang/dea` repository. The private development repository
   is not a second release target.
2. The tag maps one-to-one to checked-in `l0/docs/releases/X.Y.Z.md` notes. The first heading must name the same
   version, and the workflow publishes that reviewed file unchanged as the release body.
3. The exact tag target must pass the required validation before publication. Publication authorization is separate from
   preparing or validating the release.
4. The workflow assembles a draft containing the complete release set before making it public: four supported platform
   archives, `dea_l0_api_reference-<TAG>.pdf`, `dea_l0_api_reference-<TAG>.tar.gz`, and `SHA256SUMS`.
5. `SHA256SUMS` covers every staged release asset except itself and records bare filenames without a `./` prefix.
   SHA-256 is the baseline integrity mechanism; artifact signing remains a separate future decision.
6. Once published, a release is immutable. Workflows may update assets only while the release remains a draft and must
   reject attempts to mutate an existing published release.
7. Manual snapshots use a workflow-created tag in the separate `l0-snapshot-*` namespace, assemble the same artifact
   matrix, and are explicit prerelease flows. They may remain draft-only when publication is not requested and do not
   acquire stable-release identity.

## Rationale

- A namespaced semantic-version tag unambiguously identifies the language level and release.
- Checked-in, reviewed notes provide a reproducible public description instead of deriving user-facing content from
  implementation history.
- Draft-first assembly makes artifact completeness and checksum coverage testable before publication becomes externally
  visible.
- A sole public target and immutable publication rule prevent divergent copies and post-publication replacement of
  artifacts users may already have verified.
- A separate snapshot namespace preserves an exploratory distribution path without weakening stable release semantics.

## Consequences

- Release validation must reject malformed tags, missing or mismatched notes, incomplete asset sets, and checksum
  manifests that omit staged assets.
- Release documentation and workflow changes must preserve the tag-to-notes mapping and complete seven-asset baseline
  unless a later ADR deliberately changes the release contract.
- API-reference filenames include the release tag so downloaded documentation remains attributable to one release.
- Operators must finish review, CI, asset assembly, and publication authorization before the draft is published.
- Published releases are never repaired in place. A correction requires a new release identity.
- Snapshot workflows remain visibly prerelease and may publish generated notes rather than the stable release's curated
  note contract.

## Related Plans

- [l0/work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md](../../work/plans/tools/closed/2026-03-16-github-release-workflow-noref.md):
  introduced the multi-platform release and snapshot workflows
- [l0/work/plans/tools/closed/2026-05-01-immutable-release-workflows-noref.md](../../work/plans/tools/closed/2026-05-01-immutable-release-workflows-noref.md):
  adopted draft-first assembly, checksum completeness, and published-release immutability
- [l0/work/plans/tools/closed/2026-05-07-versioned-api-reference-export-archive-noref.md](../../work/plans/tools/closed/2026-05-07-versioned-api-reference-export-archive-noref.md):
  gave both API-reference artifacts release-specific identities
- [l0/work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md](../../work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md):
  established stable tag validation, curated notes, and the sole public release target
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the accumulated release contract into this ADR

## Current Docs

- [l0/docs/releases/README.md](../releases/README.md): stable tag and canonical release-note mapping
- [l0/docs/releases/2.0.0.md](../releases/2.0.0.md): current curated stable release body and integrity guidance
- [l0/docs/project-status.md](../project-status.md): current release, validation, and platform status
- [.github/workflows/l0-release.yml](../../../.github/workflows/l0-release.yml): stable draft-first release enforcement
- [.github/workflows/l0-snapshot.yml](../../../.github/workflows/l0-snapshot.yml): manual snapshot and prerelease flow
