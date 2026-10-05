# Tool Plan

## Add L1 snapshot and release GHA workflows

- Date: 2026-06-22
- Last reviewed: 2026-10-05
- Status: Draft (workflow implementation blocked on L1 productization)
- Title: Add L1 snapshot and release GHA workflows
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L1 snapshot GHA workflow (`.github/workflows/l1-snapshot.yml`)
  - L1 release GHA workflow (`.github/workflows/l1-release.yml`)
  - Monorepo release-line policy
- Origin: Root monorepo CI policy. Workflow files live at `.github/workflows/` and the release-line gating rules live in
  `MONOREPO.md`; both are monorepo-owned.
- Porting rule: Shared. Trigger, namespace, and publication policy belong here. L1 install layout, archive construction,
  launcher behavior, and installed smoke tests remain owned by the L1 productization plan.
- Target status:
  - L1 snapshot GHA workflow: Blocked on install/dist and artifact smoke contract
  - L1 release GHA workflow: Blocked on the same prerequisites
  - Monorepo release-line policy: Existing gate implemented; refinement pending
- Subsystem: GitHub Actions / release tagging / monorepo release-line policy
- Modules:
  - `.github/workflows/l1-snapshot.yml`
  - `.github/workflows/l1-release.yml`
  - `MONOREPO.md`
  - `docs/project-status.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - local workflow syntax and trigger/version/release-note policy validation
  - installed/archive smoke entrypoint supplied by L1 productization
  - separately authorized hosted snapshot and release acceptance checks
- Related:
  - [work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md][ci-release-plan]
  - [l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization]
  - [MONOREPO.md][monorepo]
  - [AGENTS.md][agent-policy] (remote and publication authorization)

## Dependency Statement

The closed [work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md][ci-release-plan] completed Phase 3 by
recording the release-line gate in [MONOREPO.md][monorepo]. Its Phase 4 deferred L1 release/snapshot workflows. This
plan owns that deferred work and the gate's implementation details.

Workflow creation remains blocked until
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization] lands `make install`, `make dist`,
and a reproducible smoke-testable artifact contract. The productization plan's current Stage 1 package, version input,
archive layout, and installed preparation behavior are the handoff contract below. Confirm its final implementation and
update its link if the plan moves to `closed/` before beginning workflow work.

The existing gate also requires documented release notes, tag gating, reproducible smoke tests, and continued exclusive
reservation of `l1-v*` / `l1-snapshot-*`. Recheck authoritative remote tags before activation; a historical namespace
check or an empty local tag list does not establish the current remote state.

## Current State

Reviewed on 2026-10-05 against the local checkout:

1. `MONOREPO.md` contains the four release-line gating conditions. No L1 release or snapshot workflow exists.
2. `l1-ci.yml` supports Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. Its current default toolchains are GCC
   on Linux/Windows and Apple Clang on macOS.
3. L1 supports both compiler stages and strict self-hosting validation. The productization plan nevertheless explicitly
   selects Stage 1 for the first distributable bootstrap toolchain; packaging must not follow the active development
   alias.
4. The productization plan remains Draft. `l1/Makefile` has no `install`, `list-installed`, or `dist` target. Its
   documented archive and smoke contract is not yet an implemented workflow dependency.
5. L0 release/snapshot workflows provide examples for tag handling, matrix builds, artifact staging, and publication.
   Their docs, Pages, PDF, and blog machinery is outside this plan's scope. L0 snapshot's empty `ref` input selects the
   repository default branch, rather than a hard-coded `main`.
6. Project-status docs still identify L0 as the active release line. L1 packaging and workflow availability must not
   silently change its bootstrap maturity claim.

## Defaults Chosen

1. Use separate manually dispatched snapshot and tag-triggered release workflows, with the same four host platforms as
   current L1 CI. Recheck runner labels and supported compiler versions at implementation time.
2. Publish only L1 distribution archives initially. Each archive contains its own `VERSION` and install manifest; do not
   upload four colliding assets named `VERSION`. There is no docs build or publication job.
3. Snapshot tags use `l1-snapshot-YYYYMMDD-HHMM-<shorthash>` with a UTC timestamp. Releases accept only `l1-vX.Y.Z`,
   with nonnegative numeric components and no leading zeros except zero itself. The broad `l1-v*` event filter requires
   explicit validation before building or publishing; prerelease version suffixes are outside this scope.
4. Snapshots are GitHub Pre-releases; versioned releases are GitHub Releases. Both titles and notes identify the payload
   as an L1 Stage 1 bootstrap toolchain. GitHub release type does not establish language/toolchain stability. Set
   `make_latest` to false so L1 bootstrap publication does not replace L0 as the repository's latest release.
5. Consume L1's install/dist and smoke helpers; do not reimplement payload construction or compiler smoke logic in YAML.
   Use read permissions for build jobs and grant `contents: write` only to tag/publication jobs.

## Artifact and Build Handoff

Before writing workflow YAML, establish the exact build and smoke commands from the landed productization work:

- Build the repo-local upstream L0 Stage 2 compiler from the selected source revision and select it through
  `L1_BOOTSTRAP_L0C`; never use ambient `l0c` or infer L1 versions from L0 tags. Record the actual host C compiler and
  supported version, following `l1/AGENTS.md`. Running the packaged compiler must not require L0, Python, uv, or Make;
  native operations still require the supported host C/linker/preparation tools.
- Run `make dist` from `l1/`. Stable tags map `l1-vX.Y.Z` to `DEA_DIST_VERSION=X.Y.Z`; snapshot tags map
  `l1-snapshot-...` to `DEA_DIST_VERSION=snapshot-...`. `RELEASE_VERSION` may be a workflow variable but is not the
  packaging API. Retain the bootstrap label and upstream/compiler provenance in both cases.
- Consume the emitted archive path, fail if it is missing or ambiguous, and require exactly one `dea-l1/` archive root.
  Current planned names are `dea-l1-bootstrap_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>.tar.gz` for Linux/macOS and `.zip`
  for Windows, with UTC build time and normalized host tokens. The productization helper owns these details.
- Use its smoke entrypoint to extract into an unrelated path containing spaces, invoke installed launchers without
  activation or source-worktree dependencies, check `--help` / `--version`, and compile/run the bundled stdlib-using
  program. Include standalone linking and native Windows launcher coverage as supplied by productization.
- Check the shipped semantic interfaces, input inventory, and rebuild sources. Native support is prepared into a
  separate writable cache; the installed payload stays unchanged. Reuse productization's cold-cache, warm-cache, and
  relocation checks rather than assuming a shipped runtime archive or copied native profile.
- Give each matrix artifact a unique host identifier. Publication requires all four expected archives to pass smoke
  checks, with matching L1 version and source provenance; reject missing, duplicate, or unexpected assets.

## Release Notes and Retry Policy

Fetch sufficient history and tags for the selected source revision. For snapshots, choose the nearest reachable prior L1
snapshot or version tag using Git graph distance (`git describe --tags --abbrev=0` with both namespace patterns and
excluding the current tag). For versioned releases, use only prior valid `l1-vX.Y.Z` tags so a recent snapshot does not
truncate the release notes. Exclude malformed version tags. If no eligible prior tag exists, generate an initial-release
summary from history through the selected revision. Include the full commit range: shared monorepo changes can affect
L1, so tag scoping does not imply a path filter. Test mixed L0/L1 tags, the first L1 publication, and a source branch
whose newer repository tags are not ancestors.

Resolve the source ref once and build that immutable revision on every platform. Reuse an existing snapshot tag only
when it points to that revision; never move tags. A newly dispatched snapshot can have a new timestamp and therefore a
new tag. Job reruns must retain the preparation job's original identity. Check existing releases before upload: resume a
draft for the same tag, serialize publication per tag, and leave an already published release unchanged. A mismatched
published asset set requires explicit recovery rather than silently replacing assets. Failed builds leave publication
incomplete; do not delete tags automatically.

## Goal

1. Document the pre-implementation prerequisites without requiring workflows to exist first.
2. Implement and locally validate both workflows after productization lands.
3. Exercise hosted publication through separately authorized snapshot and release milestones.
4. Update delivery documentation and close this plan with its ADR only when the acceptance criteria are met.

## Implementation Phases

### Phase 1: Refine the readiness gate

Update `MONOREPO.md` to distinguish prerequisites for adding workflows from hosted acceptance after they exist. The
pre-implementation checklist is:

- [ ] L1 install/dist is implemented and its artifact contract is stable.
- [ ] The exact archive-path output and reusable installed/archive smoke command are documented and work from a clean,
  relocated prefix on the supported host matrix.
- [ ] Version conversion, release-note baselines, tag validation, and publication behavior are documented as above.
- [ ] The reserved namespaces remain dedicated to L1 and their authoritative remote state has been checked.

This documentation phase can proceed now. Workflow review and manual dispatch are post-implementation checks, not
conditions for writing the first workflow. Keep the existing productization prerequisite in force.

### Phase 2: Add `l1-snapshot.yml`

After Phase 1's prerequisites pass:

- Define `workflow_dispatch` inputs `ref` (optional string, empty means the repository default branch), `snapshot_tag`
  (optional explicit tag in the chosen format), and `publish_release` (boolean, default `true`). An explicit tag with an
  immutable `ref` supports review of the exact tag/target before dispatch and repeatable retries. Validate its format
  and abbreviated source identity before tag creation. With `publish_release=false`, the workflow still pushes a
  snapshot tag and creates/uploads a draft release; it only skips final publication. It is not a dry run.
- `prepare-snapshot`: Resolve the requested ref, validate the supplied tag or derive the UTC snapshot tag, derive the
  package version, create/push the tag, and expose immutable source and tag outputs. Preserve automatically generated
  identity across full reruns, using the original workflow run's creation time rather than the job's current clock.
  Apply the identity and retry rules above.
- `build-dist`: Use all four platforms, the L1 toolchain setup, `DEA_DIST_VERSION`, emitted archive path, and installed
  smoke entrypoint from the handoff. Upload an archive only after its smoke check succeeds.
- `publish-release`: Require every build, download and validate the complete asset set, generate scoped notes, create or
  resume the matching draft pre-release, upload archives, and publish only when `publish_release` is true. Set
  `make_latest=false`.

GitHub manual dispatch requires the workflow to be present on the default branch. Plan the initial remote installation
and subsequent branch dispatch in that order; a branch-only new workflow is not sufficient for the first hosted check.

### Phase 3: Add `l1-release.yml`

Use `push` on `l1-v*` tags, validate the strict version format before any release side effects, and build the tagged
revision on the same four platforms. Convert the tag to `DEA_DIST_VERSION` using the handoff above. Require all smoke
checks and the complete asset set before creating/resuming the draft GitHub Release and publishing it with
`prerelease=false` and `make_latest=false`. Apply the same retry rules and the version-release notes baseline.

Complete local syntax and policy checks for both workflows before proposing any remote installation, dispatch, or tag
push. These local checks establish implementation readiness; they do not establish hosted publication success.

### Phase 4: Hosted acceptance, documentation, and closure

Follow [AGENTS.md][agent-policy] for every remote action. Implementation authorization does not authorize publication.
Before a workflow-dispatching/public/deployment write, present its exact action, destination, source, and known tag,
release, and asset effects for fresh project maintainer confirmation. Stable release tag creation requires a separate
explicit request naming the exact tag and target commit; its push requires separate fresh confirmation. Snapshot
dispatch approval must cover its automatic tag creation/push and draft or public pre-release effects. For agent-executed
snapshot acceptance, prepare the exact `snapshot_tag` and immutable `ref` for the required tag-creation request, then
obtain fresh confirmation for the dispatch that pushes that tag. Approval of one action does not cover reruns or
follow-up writes.

Exercise one authorized snapshot and one deliberately prepared versioned release on all four platforms. Do not create a
dummy stable tag solely to close the plan. If either hosted check is deferred, record local implementation as complete
and the corresponding acceptance milestone as pending, leaving this plan open.

Update `MONOREPO.md`, `docs/project-status.md`, `l1/docs/project-status.md`, and `l1/docs/roadmap.md` when workflows
land and again as hosted acceptance completes. Distinguish available workflows, verified publication, and bootstrap
product maturity. Record commands, platforms, workflow names, and outcomes without commit identifiers or individual run
links. At closure, create the repository/tooling ADR, update its index, move this plan to `closed/`, and repair incoming
links.

## ADR Impact

- Decision: Establish an L1 bootstrap release line with level-qualified tags, separate snapshot/release workflows, and
  four-platform archive-only delivery.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: This defines durable monorepo publication policy, including release identity, asset completeness,
    bootstrap maturity labeling, and preserving L0's latest-release status. L1 payload and cache design remain owned by
    productization and its level-specific ADRs.

## Non-Goals

- L1 docs build, PDF rendering, blog dispatch, or Pages deployment.
- Changes to L0 release workflows or the historical-only bare `v*` namespace.
- Package registries, bundled host toolchains, or publication of installed native caches.
- Implementing install/dist, changing the selected Stage 1 payload, or changing `l1-ci.yml` validation coverage.
- Declaring L1 language/toolchain stability merely because a GitHub Release exists.

## Verification Criteria

1. Local workflow validation covers syntax, all four platforms, event/input definitions, strict release tag validation,
   tag-to-`DEA_DIST_VERSION` mapping, release-note baselines, and draft/publication branching. Use small policy fixtures
   or mocked GitHub operations for first-publication and rerun cases; local checks must not create remote tags/releases.
2. Both workflows consume the landed L1 build/archive/smoke contract and publish only after all four artifacts pass.
   Installed execution is independent of the source checkout and bootstrap/build tools, with native support prepared
   outside the payload. The explicit build-time upstream L0 compiler remains permitted and required.
3. A separately authorized manual snapshot creates the intended tag and publishes a Pre-release with all expected
   archives. Verify that `publish_release=false` retains a draft using local mocks or an explicitly approved hosted
   draft exercise. A draft exercise still has remote side effects.
4. A separately authorized versioned tag push builds and publishes the intended GitHub Release with all four archives.
   Neither L1 release type replaces L0's latest-release selection.
5. No L0 dist assets, L0 release-note baselines, docs, PDFs, Pages, or blog publishing enter the L1 release jobs.
6. Delivery docs accurately distinguish implementation and hosted verification. Both hosted milestones, the ADR, and
   link updates are complete before plan closure.

[agent-policy]: ../../../AGENTS.md
[ci-release-plan]: closed/2026-04-02-l1-ci-release-line-noref.md
[monorepo]: ../../../MONOREPO.md
[productization]: ../../../l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
