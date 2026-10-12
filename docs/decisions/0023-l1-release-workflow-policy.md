# ADR-0023: L1 Release Workflow Policy

- Decision date: 2026-10-12
- Last edited: 2026-10-12
- Status: Accepted

## Context

L1's canonical L0-implemented compiler has a validated installation/distribution contract and matching offline
documentation. Publishing it requires a separate monorepo workflow policy: immutable release identity, complete
four-platform assets, release-note ownership, and retries that preserve accepted evidence. Compiler CI alone does not
establish that the actual published archives work on fresh hosts.

L0 remains the established release line. L1 is a development toolchain, so a versioned GitHub Release must not imply
language stability or replace L0 as the repository's latest release. L0's checked-in release-note conventions provide an
authoring model; L1 also retains generated repository history after the curated content.

This decision governs shared release automation. Canonical L1 payload, bootstrap, cache, and installation semantics
remain owned by [l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md][delivery].

## Decision

### Release identity and maturity

- Use separate manually dispatched snapshot and tag-triggered versioned-release workflows, sharing a reusable canonical
  L1 documentation build.
- Reserve `l1-snapshot-YYYYMMDD-HHMM-<shorthash>` for snapshots, with a UTC timestamp and matching source abbreviation.
  Accept only `l1-vX.Y.Z` for versioned releases, with nonnegative numeric components and no leading zeros except zero.
  Validate the tag before build or publication effects. Package versions remove the `l1-` or `l1-v` prefix as
  appropriate.
- Resolve one immutable source revision for documentation, builds, verification, and publication. Never move an existing
  tag. Retain the original source/tag identity across full workflow reruns.
- Publish snapshots as pre-releases and versioned releases as non-prerelease GitHub Releases. Both use
  `make_latest=false`. Titles and note headings use `Dea/L1 {version}`, with the package version. The notes explicitly
  identify the canonical L0-implemented development toolchain and state that release does not declare language or
  toolchain stability.

### Evidence and assets

Build strict canonical L1 HTML/full PDF first from the selected source/version, then pass the identical verified bundle
to distribution builds on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. Reuse L1's productization helpers
and their explicit L0 bootstrap selection. Do not recreate payload or smoke-test logic in workflow YAML.

Each archive must pass verification on a separate fresh matching runner using transported archive/result/harness
evidence, without the source checkout or bootstrap artifacts. Publication validates all four successful reports against
the exact archives, package/source identities, and shared documentation digest. Keep each attempt's artifacts separate;
partial reruns must not mix prior evidence with new builds.

Publish exactly seven uploaded assets: four platform archives, the canonical HTML/PDF bundle, its byte-identical
standalone PDF, and `SHA256SUMS` covering the six payload files. Missing, duplicate, stale, mismatched, or unexpected
assets prevent publication. Build and verification jobs have read-only repository permissions; write permission is
limited to snapshot tag creation and release publication. Every executable job reports its inputs in its log and
summary.

### Curated notes and generated history

Each versioned release requires `l1/docs/releases/X.Y.Z.md` in the selected immutable source. Following L0 conventions,
its first line is exactly `# Dea/L1 X.Y.Z`, followed by the development-toolchain notice and curated release content.
Maintain the release-note index when preparing a version. Validate the source document before documentation and native
builds; reject missing, empty, invalid UTF-8, mismatched, or incomplete notes without a generated-only fallback.

Preserve the complete curated Markdown as the opening release body. Append a separate `## Commit history` section with
the generated introduction and commit list. Do not add another title or notice or write generated history into the
checked-in document. Preparation, publication, and matching draft retries read the same immutable source document.

For versioned releases, select the nearest reachable earlier valid `l1-vX.Y.Z` tag. Snapshots may also use a reachable
L1 snapshot tag. Exclude the current tag and unrelated level namespaces. If no eligible prior tag exists, include
history from L1's first reachable introduction commit through the selected revision. Include all repository changes in
the range because shared changes can affect L1.

The generated introduction is `Changes since <baseline>:` with the baseline formatted as code, or
`Initial L1 publication, including changes since L1 was introduced:`. Snapshots keep automatic titles, notices, and
history without requiring or borrowing a curated versioned-release file.

### Retry and publication boundaries

Serialize publication per tag. A matching draft can resume and replace its recognized assets, but conflicting identity
or unexpected assets require explicit recovery. Validate the complete uploaded asset set before publishing. Leave an
already published release unchanged, and never delete or retarget tags automatically after failure.

Snapshot `publish_release=false` still creates/pushes the snapshot tag and uploads a draft; it only suppresses final
publication. Local validation, acceptance, plan closure, and release preparation do not authorize remote writes. Apply
[AGENTS.md][agent-policy] separately to pushes, tag creation, tag pushes, dispatches, and publication. Pages, blog
exports, cross-repository writes, and changes to L0 release workflows are outside this release line's scope.

## Rationale

- Separate level-qualified workflows and explicit maturity labeling keep L1 delivery independent of L0's release line.
- One source/version/docs identity and fresh-host verification bind publication to the actual accepted artifacts.
- Reusing productization helpers preserves the established payload and installed-operation contract.
- Checked-in curated notes support review, while automatically appended history preserves traceability without making
  the source document a generated commit log.
- Immutable source selection, attempt isolation, and draft-only retries prevent moving branches or stale evidence from
  silently changing a release.
- Separate authorization preserves the distinction between preparing a release and publishing it.

## Consequences

- Every prepared version needs reviewed notes committed before its tag is selected; snapshots remain automatic.
- Versioned releases can fail early for missing or invalid notes. Moving branch content or uncommitted edits cannot
  substitute for notes at the selected source.
- A release requires all four platforms and complete canonical documentation; there is no compiler-only fallback.
- Failed attempts require full reruns with the retained identity. Published releases cannot be repaired in place by the
  workflow.
- Snapshot/versioned-release acceptance establishes the hosted workflow milestones. Curated-note composition has focused
  local validation. L1 publication remains separately gated and does not require a duplicate acceptance release solely
  for plan closure.

## Related Plans

- [work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md][workflow-plan]: implemented and
  validated the workflows, artifact handoff, retry policy, and curated-note composition.

## Current Docs

- [MONOREPO.md][monorepo]: release-line gating and workflow contract.
- [AGENTS.md][agent-policy]: remote and publication authorization.
- [l1/docs/releases/README.md][release-notes]: release-note authoring and generated-history contract.
- [l1/docs/reference/productization-inventory.md][inventory]: artifact layout and acceptance handoff.
- [docs/project-status.md][project-status]: current release-line and publication status.

[agent-policy]: ../../AGENTS.md
[delivery]: ../../l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md
[inventory]: ../../l1/docs/reference/productization-inventory.md
[monorepo]: ../../MONOREPO.md
[project-status]: ../project-status.md
[release-notes]: ../../l1/docs/releases/README.md
[workflow-plan]: ../../work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md
