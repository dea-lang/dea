# Tool Plan

## Add L1 snapshot and release GHA workflows

- Date: 2026-06-22
- Last reviewed: 2026-10-05
- Status: In progress (Phase 1 complete; workflow implementation blocked on L1 productization)
- Title: Add L1 snapshot and release GHA workflows
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L1 snapshot GHA workflow (`.github/workflows/l1-snapshot.yml`)
  - L1 release GHA workflow (`.github/workflows/l1-release.yml`)
  - Reusable L1 docs build (`.github/workflows/l1-docs-build.yml`)
  - Monorepo release-line policy
- Origin: Root monorepo CI policy. Workflow files live at `.github/workflows/` and the release-line gating rules live in
  `MONOREPO.md`; both are monorepo-owned.
- Porting rule: Shared. Trigger, namespace, and publication policy belong here. L1 install layout, archive construction,
  launcher behavior, and installed smoke tests remain owned by the L1 productization plan.
- Target status:
  - L1 snapshot GHA workflow: Blocked on install/dist and artifact smoke; Stage 2 documentation generation is
    implemented
  - L1 release GHA workflow: Blocked on the same prerequisites
  - L1 docs build integration: HTML/PDF contract defined; generation implementation pending
  - Monorepo release-line policy: Refined prerequisites and hosted acceptance implemented
- Subsystem: GitHub Actions / release tagging / monorepo release-line policy
- Modules:
  - `.github/workflows/l1-snapshot.yml`
  - `.github/workflows/l1-release.yml`
  - `.github/workflows/l1-docs-build.yml`
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
  - [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs]
  - [MONOREPO.md][monorepo]
  - [AGENTS.md][agent-policy] (remote and publication authorization)

## Dependency Statement

The closed [work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md][ci-release-plan] completed Phase 3 by
recording the release-line gate in [MONOREPO.md][monorepo]. Its Phase 4 deferred L1 release/snapshot workflows. This
plan owns that deferred work and the gate's implementation details.

Workflow creation remains blocked until
[l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md][productization] lands `make install`, `make dist`,
and a reproducible smoke-testable artifact contract. The productization plan's self-hosted Stage 2 package, version
input, archive layout, and installed preparation behavior are the handoff contract below. Confirm its final
implementation and update its link if the plan moves to `closed/` before beginning workflow work.

[l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs] defines the separate Stage
1/Stage 2 HTML/PDF contract. This plan owns release integration of its Stage 2 bundle. Generation is implemented;
productization remains the workflow implementation prerequisite; Stage 1 docs remain separate developer outputs. Neither
docs generation nor its local acceptance depends on release workflows.

The existing gate also requires documented release notes, tag gating, reproducible smoke tests, and continued exclusive
reservation of `l1-v*` / `l1-snapshot-*`. Recheck authoritative remote tags before activation; a historical namespace
check or an empty local tag list does not establish the current remote state.

## Current State

Reviewed on 2026-10-05 against the local checkout:

1. `MONOREPO.md` contains the four release-line gating conditions. No L1 release or snapshot workflow exists.
2. `l1-ci.yml` supports Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. Its current default toolchains are GCC
   on Linux/Windows and Apple Clang on macOS.
3. L1 supports both compiler stages and strict self-hosting validation. Productization follows L0's delivery model:
   install/dist ship self-built Stage 2 only, while Stage 1 remains a bootstrap/development tool. Packaging must not
   follow the active development alias.
4. The productization plan remains Draft. `l1/Makefile` has no `install`, `list-installed`, or `dist` target. Its
   documented archive and smoke contract is not yet an implemented workflow dependency.
5. L0 release/snapshot workflows provide examples for tag handling, matrix builds, artifact staging, and publication.
   Their docs-build pattern informs the new L1 Stage 2 job; Pages and blog machinery remain outside scope. L0 snapshot's
   empty `ref` input selects the repository default branch, rather than a hard-coded `main`.
6. Project-status docs still identify L0 as the active release line. L1 packaging and workflow availability must not
   silently declare stable language/toolchain maturity.

## Defaults Chosen

1. Use separate manually dispatched snapshot and tag-triggered release workflows, with the same four host platforms as
   current L1 CI. Recheck runner labels and supported compiler versions at implementation time.
2. Publish four L1 distribution archives, a separate Stage 2 HTML/PDF bundle, the Stage 2 PDF, and `SHA256SUMS`. Every
   compiler archive embeds the same verified Stage 2 HTML/PDF. Each archive contains its own `VERSION` and install
   manifest; do not upload four colliding assets named `VERSION`. Stage 1 autodocs are excluded from this set.
3. Snapshot tags use `l1-snapshot-YYYYMMDD-HHMM-<shorthash>` with a UTC timestamp. Releases accept only `l1-vX.Y.Z`,
   with nonnegative numeric components and no leading zeros except zero itself. The broad `l1-v*` event filter requires
   explicit validation before building or publishing; prerelease version suffixes are outside this scope.
4. Snapshots are GitHub Pre-releases; versioned releases are GitHub Releases. Both titles and notes identify the payload
   as an L1 self-hosted Stage 2 development toolchain. GitHub release type does not establish language/toolchain
   stability. Set `make_latest` to false so initial L1 publication does not replace L0 as the repository's latest
   release.
5. Consume L1's install/dist and smoke helpers; do not reimplement payload construction or compiler smoke logic in YAML.
   Use read permissions for build jobs and grant `contents: write` only to tag/publication jobs.

## Artifact and Build Handoff

Before writing workflow YAML, establish the exact build and smoke commands from the landed productization work:

- Build the repo-local upstream L0 Stage 2 compiler from the selected source revision and select it through
  `L1_BOOTSTRAP_L0C`; productization owns the subsequent L1 Stage 1 -> Stage 2 seed -> self-built Stage 2 package chain.
  Never use ambient `l0c`, select the payload through the development `l1c` alias, or infer L1 versions from L0 tags.
  Record the actual host C compiler and supported version, following `l1/AGENTS.md`. Running the packaged compiler must
  not require L0, Python, uv, or Make; native operations still require the supported host C/linker/preparation tools.
  Stage 1 and the Stage 2 seed are build-only dependencies, absent from the published payload.
- Run `make dist` from `l1/`. Stable tags map `l1-vX.Y.Z` to `DEA_DIST_VERSION=X.Y.Z`; snapshot tags map
  `l1-snapshot-...` to `DEA_DIST_VERSION=snapshot-...`. `RELEASE_VERSION` may be a workflow variable but is not the
  packaging API. Retain Stage 2 development identification and upstream/compiler provenance in both cases.
- Supply `DOCS_ARTIFACT=<downloaded-stage2-bundle>` from the docs job. Productization verifies its stage, level,
  version, source identity, complete PDF status, and digests before embedding it. All platform builds consume identical
  docs bytes; compiler runners do not install TeX or regenerate documentation.
- Supply a unique `DIST_RESULT` path and consume the versioned JSON result after successful `make dist`. Verify
  `stage=2`, version, host, and provenance, fail if the archive path is missing or ambiguous, and require exactly one
  `dea-l1/` archive root. Current planned names are `dea-l1-lang_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>.tar.gz` for
  Linux/macOS and `.zip` for Windows, with UTC build time and normalized host tokens. The productization helper owns
  these details.
- Run `make smoke-dist ARCHIVE=<archive-from-DIST_RESULT>` to extract into an unrelated path containing spaces, invoke
  installed launchers without activation or source-worktree dependencies, check `--help` / `--version`, and compile/run
  the bundled stdlib-using program. Require installed `l1c` to select the self-built Stage 2 compiler and reject any
  Stage 1 payload. Include standalone linking and native Windows launcher coverage as supplied by productization.
  Require offline Stage 2 HTML/PDF and the matching docs manifest in the extracted archive, with no Stage 1 autodocs.
- Check the shipped semantic interfaces, input inventory, and rebuild sources. Native support is prepared into a
  separate writable cache; the installed payload stays unchanged. Reuse productization's cold-cache, warm-cache, and
  relocation checks rather than assuming a shipped runtime archive or copied native profile.
- Give each matrix artifact a unique host identifier. Publication requires all four expected archives to pass smoke
  checks, with matching L1 version and source provenance; reject missing, duplicate, or unexpected assets.

## Stage 2 Documentation and Release Assets

Add reusable `l1-docs-build.yml` with read-only repository permissions and explicit immutable `source_ref`, package
version, release tag, and stage inputs. Release callers always select Stage 2 and require strict HTML plus full PDF
generation. Use Linux with Doxygen, Graphviz, the shared docs dependencies, vendored m.css, and TeX, following L0's
toolchain setup. Invoke `make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=<version>` with `L1_DOCS_RELEASE_TAG` set
to the selected tag. Upload the verified `dea_l1_stage2_autodocs.tar.gz` as `l1-stage2-autodocs`; expose the PDF from
that same bundle, not a separately regenerated build. No Pages artifact/deployment or blog export is required.

The generation plan owns the exact bundle layout and manifest. `build-docs` must finish before `build-dist` starts, and
publication needs both successful docs and all four successful dist builds. Missing, preview-only, wrong-stage,
wrong-source, or wrong-version docs fail the workflow; there is no silent compiler-only release fallback.

Stage release assets under these names, where `<TAG>` is the selected `l1-v...` or `l1-snapshot-...` tag:

- Four host distribution archives reported by their `DIST_RESULT` records.
- `dea_l1_stage2_autodocs-<TAG>.tar.gz`, containing offline HTML, the full PDF, and docs manifest.
- `dea_l1_stage2_api_reference-<TAG>.pdf`, byte-identical to the PDF in that bundle and each platform archive.
- `SHA256SUMS`, covering all six assets above with bare filenames and excluding itself.

Generate checksums after the complete set has been validated, then attach all seven files before publication. Draft
retry rules cover documentation assets as well as compiler archives; an existing published release remains immutable.
Stage 1 HTML/PDF generation remains available for developers and separate validation, with no Stage 1 release asset.

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
2. Implement and locally validate both workflows after productization and Stage 2 documentation generation land.
3. Exercise hosted publication through separately authorized snapshot and release milestones.
4. Update delivery documentation and close this plan with its ADR only when the acceptance criteria are met.

## Implementation Phases

### Phase 1: Refine the readiness gate

Completed on 2026-10-05: `MONOREPO.md` now distinguishes prerequisites for adding workflows from hosted acceptance after
they exist. It records the productization handoff, separate publication authorization, and product maturity boundary.
The prerequisite checklist for Phases 2 and 3 remains:

- [ ] L1 install/dist is implemented and its artifact contract is stable.
- [ ] Stage 2 strict HTML/full-PDF generation and docs-bundle verification are implemented under the defined contract.
- [ ] The exact archive-path output and reusable installed/archive smoke command are documented and work from a clean,
  relocated prefix on the supported host matrix.
- [x] Version conversion, release-note baselines, tag validation, and publication behavior are documented as above.
- [ ] The reserved namespaces remain dedicated to L1 and their authoritative remote state has been checked.

Workflow review and manual dispatch are post-implementation checks, not conditions for writing the first workflow. The
productization prerequisite remains in force: the install/dist targets and reusable artifact smoke command are still
absent. Remote namespace verification remains pending until workflow activation. Existing project-status docs already
describe L1 delivery as unavailable and need no claim change for this phase.

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
- `build-docs`: After preparation, invoke the reusable Stage 2 docs build at the same immutable source/version/tag.
- `build-dist`: Use all four platforms, the L1 toolchain setup, `DEA_DIST_VERSION`, emitted archive path, and installed
  smoke entrypoint from the handoff. Wait for `build-docs`, download its verified bundle, and pass `DOCS_ARTIFACT`.
  Upload an archive only after its smoke check succeeds.
- `publish-release`: Require every build, download and validate the complete asset set, generate scoped notes, create or
  resume the matching draft pre-release, upload archives, and publish only when `publish_release` is true. Set
  `make_latest=false`.

GitHub manual dispatch requires the workflow to be present on the default branch. Plan the initial remote installation
and subsequent branch dispatch in that order; a branch-only new workflow is not sufficient for the first hosted check.

### Phase 3: Add `l1-release.yml`

Use `push` on `l1-v*` tags, validate the strict version format before any release side effects, and build the tagged
revision on the same four platforms. Convert the tag to `DEA_DIST_VERSION` using the handoff above. Require all smoke
checks and the complete seven-file asset set before creating/resuming the draft GitHub Release and publishing it with
`prerelease=false` and `make_latest=false`. Apply the same retry rules and the version-release notes baseline. Build
strict Stage 2 docs first through the same reusable job and pass its bundle into all dist builds.

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
land and again as hosted acceptance completes. Distinguish available workflows, verified publication, and development
product maturity. Record commands, platforms, workflow names, and outcomes without commit identifiers or individual run
links. At closure, create the repository/tooling ADR, update its index, move this plan to `closed/`, and repair incoming
links.

## ADR Impact

- Decision: Establish an L1 development release line with level-qualified tags, separate snapshot/release workflows, and
  four-platform delivery with matching Stage 2 HTML/PDF artifacts.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: This defines durable monorepo publication policy, including release identity, asset completeness,
    development maturity labeling, and preserving L0's latest-release status. L1 payload and cache design remain owned
    by productization and its level-specific ADRs.

## Non-Goals

- Implementing L1 source filters/renderers within workflow YAML; consume the dedicated documentation-generation plan.
- Stage 1 autodoc release assets, blog dispatch, or Pages deployment.
- Changes to L0 release workflows or the historical-only bare `v*` namespace.
- Package registries, bundled host toolchains, or publication of installed native caches.
- Implementing install/dist, changing the selected self-hosted Stage 2 payload, or changing `l1-ci.yml` validation
  coverage.
- Declaring L1 language/toolchain stability merely because a GitHub Release exists.

## Verification Criteria

1. Local workflow validation covers syntax, all four platforms, event/input definitions, strict release tag validation,
   tag-to-`DEA_DIST_VERSION` mapping, release-note baselines, and draft/publication branching. Use small policy fixtures
   or mocked GitHub operations for first-publication and rerun cases; local checks must not create remote tags/releases.
2. Both workflows consume the landed L1 build/archive/smoke and documentation contracts and publish only after all four
   compiler archives and the matching complete Stage 2 HTML/PDF pass validation. Installed execution is independent of
   the source checkout and bootstrap/build tools, with native support prepared outside the payload. The explicit
   build-time upstream L0 compiler remains permitted and required.
3. A separately authorized manual snapshot creates the intended tag and publishes a Pre-release with all expected
   archives. Verify that `publish_release=false` retains a draft using local mocks or an explicitly approved hosted
   draft exercise. A draft exercise still has remote side effects.
4. A separately authorized versioned tag push builds and publishes the intended GitHub Release with all four archives.
   Neither L1 release type replaces L0's latest-release selection.
5. No L0 dist/docs assets, L0 release-note baselines, Stage 1 autodocs, Pages, or blog publishing enter the L1 release
   jobs. Tests verify docs-before-dist ordering, wrong/stale docs rejection, all seven release files, checksum coverage,
   and identical Stage 2 PDF bytes in standalone, docs-bundle, and platform-archive forms.
6. Delivery docs accurately distinguish implementation and hosted verification. Both hosted milestones, the ADR, and
   link updates are complete before plan closure.

[agent-policy]: ../../../AGENTS.md
[autodocs]: ../../../l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md
[ci-release-plan]: closed/2026-04-02-l1-ci-release-line-noref.md
[monorepo]: ../../../MONOREPO.md
[productization]: ../../../l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md
