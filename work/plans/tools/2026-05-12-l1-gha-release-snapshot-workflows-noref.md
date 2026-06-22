# Tool Plan

## Add L1 snapshot and release GHA workflows

- Date: 2026-06-22
- Status: Draft
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
- Porting rule: Shared. The workflow triggers, tag namespaces, and release-line rules are monorepo policy. L1-local
  build logic (install-prefix layout, dist archive shape, launcher behavior) is consumed from L1's own productization
  plan but not forked in the workflow files.
- Target status:
  - L1 snapshot GHA workflow: Pending
  - L1 release GHA workflow: Pending
  - Monorepo release-line policy: Pending
- Subsystem: GitHub Actions / release tagging / monorepo release-line policy
- Modules:
  - `.github/workflows/l1-snapshot.yml`
  - `.github/workflows/l1-release.yml`
  - `MONOREPO.md`
  - `docs/project-status.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
- Test modules:
  - workflow trigger and tag-policy validation (manual GHA dispatch check)
  - dist archive smoke tests (consumed from the productization plan)
- Related:
  - `work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md`
  - `l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`
  - `MONOREPO.md` (release-line gating policy)

## Dependency Statement

This plan implements Phases 3 and 4 of the closed
\[`work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md`\][ci-release-plan]. In that plan's terms:

- Phase 3 (release-line gating policy) is complete — the policy is written into `MONOREPO.md`.
- Phase 4 (release/snapshot workflows) was explicitly deferred until readiness. This plan defines and implements the
  readiness gate and the workflows themselves.

The four conditions from the gating policy are:

1. L1 install/dist artifact contract defined and stable. → **Prerequisite:**
   \[`l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`\][productization] must land with
   `make install`, `make dist`, and a smoke-testable artifact layout before this plan can ship the workflows.
2. Artifact smoke-testable from clean prefix. → Consumed from (1).
3. Release notes, tag gating, and smoke-test flow documented and reproducible in CI. → Defined in this plan.
4. `l1-v*` / `l1-snapshot-*` namespaces reserved and unused. → **Already true** since the closed plan verified this.

This plan therefore depends on the L1 productization plan landing first.

## Current State

1. `MONOREPO.md` contains the release-line gating policy with four conditions. No L1 release or snapshot workflow
   exists.
2. L1 has a working CI workflow (`l1-ci.yml`) with a four-platform matrix (Linux, macOS Intel, macOS ARM, Windows
   UCRT64).
3. L0 has mature `l0-release.yml` and `l0-snapshot.yml` workflows that serve as the reference pattern: tag-triggered
   stable release and `workflow_dispatch` snapshot with tag creation, multi-platform dist build, docs build, asset
   upload, draft release/pre-release, and publication.
4. The L1 productization plan (`l1/work/plans/tools/2026-04-02-l1-bootstrap-productization-noref.md`) is still Draft.
   Its `make install` and `make dist` targets do not exist yet, so there is no install-prefix artifact or dist archive
   to publish.
5. L1 does not yet have a docs publication pipeline or API reference docgen analogous to L0's `l0-docgen-blog` tooling.
   The L0 release/snapshot workflows include docs build and blog-dispatch steps that L1 should not replicate until L1
   has its own docs productization story.
6. `docs/project-status.md` and `l1/docs/project-status.md` state that L1 is not release-bearing. This remains true;
   this plan does not change that claim until the prerequisites exist.

## Defaults Chosen

1. **Follow the L0 workflow pattern, not the L0 workflow code.** L1 workflows should reuse the same structural approach
   (tag trigger for releases, `workflow_dispatch` for snapshots, multi-platform matrix, archive upload + smoke test +
   release publication) but must not copy L0 docs-publish, blog-dispatch, or PDF rendering steps that L1 does not yet
   own.
2. **Minimal platform matrix.** The L1 release and snapshot matrices should match the `l1-ci.yml` four-platform set
   (Linux x86_64, macOS Intel, macOS ARM, Windows UCRT64). Narrower than L0's only where L1 lacks platform support.
3. **No docs build in the first release/snapshot workflow.** L1 has no docgen or API reference pipeline. The first
   workflows publish only the distribution archive and a `VERSION` metadata file. Docs publication is deferred to a
   follow-up plan once L1 has its own docgen tooling.
4. **Snapshot tag format:** `l1-snapshot-YYYYMMDD-HHMM-<shorthash>`, matching the L0 convention with `l1-` prefix.
5. **Release tag format:** `l1-v<semver>`, matching `l1-v*` pattern.
6. **Pre-release naming:** L1 snapshots publish as GitHub Pre-releases. L1 stable releases publish as GitHub Releases.
   Both follow the L0 pattern.
7. **Consume `make install` and `make dist` from the productization plan.** The workflows call these targets; they do
   not reimplement install/dist logic in YAML.

## Goal

1. Define and document the readiness gate that unlocks L1 release/snapshot workflow creation.
2. Implement `l1-snapshot.yml` once the productization plan has landed and the gating conditions are met.
3. Implement `l1-release.yml` once the same conditions are met.
4. Update monorepo and L1-local docs to reflect the new workflows.

## Implementation Phases

### Phase 1: Define the readiness gate (documentation only, no workflow)

Before any workflow YAML is written, update `MONOREPO.md` to refine the existing gating policy with the specific
checklist that this plan establishes. The checklist should enumerate:

- [ ] L1 productization plan is implemented (`make install` and `make dist` exist and produce a smoke-testable artifact
  from a clean prefix).
- [ ] `l1-snapshot.yml` / `l1-release.yml` draft workflow files have been reviewed and the trigger tags match the
  reserved namespaces.
- [ ] Snapshot tag creation (`workflow_dispatch` → tag push) has been tested via manual dispatch on a branch.
- [ ] Documented smoke-test flow for both snapshot and release artifacts.

This phase produces no workflow files. It updates `MONOREPO.md` and, if needed, the L1 project-status docs.

### Phase 2: Add `l1-snapshot.yml`

Once the readiness gate is satisfied, add `.github/workflows/l1-snapshot.yml` with:

- **Trigger:** `workflow_dispatch` with optional `ref` input (defaults to `main`), matching the L0 snapshot pattern.
- **Permissions:** `contents: write` (to push snapshot tags and create pre-releases).
- **Jobs:**
  - `prepare-snapshot`: Creates and pushes the `l1-snapshot-<stamp>-<hash>` tag (idempotent; errors if the same tag
    exists on a different commit).
  - `build-dist`: Multi-platform matrix (Linux x86_64, macOS Intel, macOS ARM, Windows UCRT64). Checks out at the
    snapshot ref, prepares the toolchain, runs `make dist` with `DEA_DIST_VERSION` set appropriately, resolves the
    archive path, runs the archive smoke test (consumed from the productization plan), and uploads the archive as a
    workflow artifact.
  - `publish-release`: Downloads all dist artifacts, generates release notes from `git log` since the last tag in the
    `l1-v*` / `l1-snapshot-*` namespace, ensures a draft GitHub Pre-release exists for the snapshot tag, uploads all
    assets, and publishes the pre-release (gated by an `inputs.publish_release` flag, default `true`).

Key differences from the L0 snapshot workflow:

- No docs build job. No PDF rendering. No blog-dispatch step.
- The `build-dist` matrix runs `make dist` from `l1/`, not `l0/`.
- The smoke test validates the L1 artifact layout, not the L0 layout.
- Release notes cover only the distance from the previous L1 tag, not the L0 tag history.

### Phase 3: Add `l1-release.yml`

Add `.github/workflows/l1-release.yml` with:

- **Trigger:** `push` on `l1-v*` tags.
- **Permissions:** `contents: write`.
- **Jobs:**
  - `build-dist`: Same matrix and structure as the snapshot `build-dist`, but builds against the tagged commit and
    passes `RELEASE_VERSION=${{ github.ref_name }}`.
  - `publish-release`: Downloads dist artifacts, generates release notes, ensures a draft GitHub Release (not
    Pre-release) exists, uploads assets, and publishes the release.

Key differences from the L0 release workflow:

- No `check-pages-availability` job. No `build-docs` job. No `deploy-pages` job. No PDF/blog rendering.
- No `publish-release` docs-asset staging or checksum generation for docs-related files.
- Release notes scope is limited to L1-relevant tag history.

### Phase 4: Update monorepo and L1 docs

After at least one successful manual snapshot run:

- Update `MONOREPO.md` to note that L1 snapshot/release workflows exist and reference the gating conditions they
  satisfy.
- Update `docs/project-status.md` to mention the new workflows in the L1 validation and delivery sections.
- Update `l1/docs/project-status.md` to list the snapshot and release workflows under delivery and validation.
- Update `l1/docs/roadmap.md` to mark the plan as completed once all phases are done (snapshot and release workflows
  exist and have been exercised at least once).

## Non-Goals

- L1 docs build, PDF rendering, blog dispatch, or Pages deployment. These are deferred until L1 has its own docgen
  tooling.
- Replicating the L0 release workflow's docs-asset staging or checksum generation for non-dist assets.
- Any change to L0's release ownership or workflow layout.
- Package management, manifests, or registry integration.
- Changing the monorepo rule that bare `v*` tags are historical-only.
- Modifying the existing `l1-ci.yml` bootstrap validation workflow.
- Implementing `make install` or `make dist` — those belong to the productization plan.

## Verification Criteria

1. A manual `workflow_dispatch` of `l1-snapshot.yml` creates a valid `l1-snapshot-<stamp>-<hash>` tag pushed to the
   remote, builds and smoke-tests dist archives on all four platforms, and publishes a GitHub Pre-release with the
   artifacts attached.
2. A push of an `l1-v*` tag triggers `l1-release.yml`, which builds dist archives on all four platforms and publishes a
   GitHub Release (not Pre-release) with artifacts attached.
3. Neither workflow includes a docs build, PDF, or blog-dispatch step.
4. `MONOREPO.md`, `docs/project-status.md`, and `l1/docs/project-status.md` correctly describe the new workflows and do
   not claim L1 is a release-bearing product beyond what the workflows support.
5. The L1 snapshot and release workflows do not reference or consume L0 dist artifacts, L0 docs rendering, or L0 tag
   namespaces.
6. The gating policy in `MONOREPO.md` remains consistent with the workflow implementations.

## Open Design Constraints

1. The snapshot and release workflows must not be created before the L1 productization plan has landed `make install`
   and `make dist`. Attempting to create them earlier would produce workflows that cannot be validated end-to-end.
2. If the L1 docs productization story matures before this plan ships Phase 2/3, a minimal docs build step (e.g.
   generating `l1c --help` or a version page) may be added to the workflow scope by agreement between this plan and the
   docs plan. Until then, the first workflows ship without any docs publication.
3. The workflow trigger tags (`l1-v*`, `l1-snapshot-*`) must not be used for any other purpose before the first
   deliberately prepared L1 release or snapshot.
4. Root workflow files remain monorepo-owned even when they primarily serve `l1/`.
