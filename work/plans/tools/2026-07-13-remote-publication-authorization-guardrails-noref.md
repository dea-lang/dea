# Tool Plan

## Establish risk-tiered remote and publication authorization guardrails

- Date: 2026-07-13
- Status: In Progress
- Title: Establish risk-tiered remote and publication authorization guardrails
- Kind: Tooling
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - Dea repository-wide agent guidance
  - Dea planning, finalization, and documentation-refresh skills
  - `googlielmo/gwz-blog` publication guidance
- Origin: Dea root agent policy, with repository-local release and blog deployment effects documented at their owning
  surfaces
- Porting rule: Share the authorization invariants exactly; adapt only the repository-specific destinations and
  automatic effects
- Target status:
  - Dea repository-wide agent guidance: In Progress
  - Dea planning, finalization, and documentation-refresh skills: In Progress
  - `googlielmo/gwz-blog` publication guidance: In Progress
- Subsystem: Agent authorization policy / release safety / cross-repository publication
- Modules:
  - `CLAUDE.md`
  - `AGENTS.md`
  - `l0/CLAUDE.md`
  - `l0/AGENTS.md`
  - `.agents/skills/create-dea-plan/SKILL.md`
  - `.agents/skills/finalize-dea-work/SKILL.md`
  - `.agents/skills/refresh-stale-docs/SKILL.md`
  - `googlielmo/gwz-blog` `AGENTS.md`
- Test modules:
  - Dea Markdown and pre-commit validation
  - authorization-policy scenario review
  - `googlielmo/gwz-blog` instruction-diff validation
- Related:
  - `l0/work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md`

## Summary

Repository edits, local commits, remote pushes, tags, releases, workflow dispatches, and public deployments have
different risk and authorization boundaries. Existing guidance covers local finalization but does not state those
boundaries strongly enough at every relevant entry point. This plan makes the shared policy explicit in Dea, records the
release-specific automatic effects in L0, and adds an exact-copy review and publication gate to the distinct
private-source workflow used by `googlielmo/gwz-blog`.

The already-published Dea/L0 1.1.0 release, tag, documentation, synchronized API content, and blog announcement remain
unchanged. This plan governs future work only.

## Current State

1. Dea's commit guidance defines local validation and commit conventions but does not explicitly separate a local commit
   from authority to push it.
2. L0 release automation turns a stable tag push into an immutable public release, release assets, Pages deployment, and
   a downstream blog synchronization dispatch.
3. The blog's private source repository deploys the public site as an automatic effect of eligible pushes to its main
   branch.
4. Plans can describe publication phases without a standard requirement to mark them as manual user-approval gates.
5. Agent review, CI success, and command-escalation approval are not user review or publication authorization, but the
   current skills do not state that distinction consistently.

## Defaults Chosen

1. Analysis, tests, builds, and explicitly requested local edits stay within the requested task scope. `Organize` and
   `review` are read-only; `draft` authorizes only the named draft.
2. An implementation or finalization request may include a local commit when repository conventions call for one. It
   never implies permission to push.
3. Any push requires an explicit user request. Public, cross-repository, workflow-dispatching, or deployment-triggering
   writes additionally require fresh confirmation immediately before execution with the exact destination, pending
   changes, command, and downstream effects.
4. A public branch push is valid only when repository instructions designate that public destination and the checked out
   branch already tracks that exact public remote and branch. Ad hoc refspecs, `HEAD:<branch>`, upstream changes, and
   `pushRemote` overrides cannot bypass this requirement.
5. Tag creation requires a separate, explicit request naming the tag and target; implementing a plan that mentions the
   tag does not satisfy that gate. A release-tag push always has a separate fresh confirmation gate that lists the tag,
   target, remote URL, and every known automatic effect.
6. Blog material remains a draft until the user reviews the exact final copy. Any content change invalidates that
   review. Promotion and live deployment require a fresh statement that the reviewed copy is clear to publish.
7. A plan describes intended work but grants no remote authority. Sandbox, tool, CI, or escalation approval grants
   technical capability only and cannot satisfy a user-approval gate.

## Goal

1. Establish one authoritative authorization contract for Dea agents.
2. Make L0 release consequences visible before any tag or public push is considered.
3. Make Dea planning, finalization, and documentation-refresh skills preserve the manual publication boundary.
4. Make the blog's private-source workflow require exact-copy review and explicit live-publication approval.
5. Produce reviewable local commits in both repositories without changing any remote state.

## Implementation Phases

### Phase 1: Establish the Dea policy

- Add the authoritative risk tiers and confirmation rules to root `CLAUDE.md`.
- Surface the non-negotiable remote, tag, cross-repository, and deployment rules in root `AGENTS.md`.
- Add L0-specific warnings that stable tag publication creates the GitHub release and assets, deploys Pages, and
  dispatches synchronization work into the blog repository.
- Preserve inherited root behavior for L1 and other agent guidance rather than duplicating the policy unnecessarily.

### Phase 2: Reinforce lifecycle skills

- Require explicit manual approval gates in plans that mention pushes, tags, releases, dispatches, deployments, or
  cross-repository writes.
- Define user review as review of the exact content; do not substitute agent review, tests, or CI.
- Make the finalization workflow stop after a local commit and handoff, report the upstream and pending range, and keep
  publication-dependent plans active.
- State that documentation refreshes and local documentation commits do not authorize remote synchronization or
  publication.

### Phase 3: Guard blog publication

- Document that eligible pushes to private `googlielmo/gwz-blog` main trigger deployment of the public site.
- Keep new announcements under `_drafts/` until the user reviews the exact copy.
- State that `publish-draft.sh` is a mechanical promotion helper, not authorization to publish.
- Require explicit approval for first-person copy and fresh confirmation before promotion or a deployment-triggering
  push.

### Phase 4: Validate and create local commits

- Run Dea whitespace, Markdown, and pre-commit checks against the changed guidance, skills, and this plan.
- Fast-forward the persistent blog worktree from its private upstream only while it is clean, then validate its
  instruction-only diff with `git diff --check`. No site build is required for ignored agent-guidance paths.
- Create one local Dea commit and one local blog commit using each repository's conventions.
- Report both exact diffs, commit identifiers, configured upstreams, and unpushed ranges. Do not push or change upstream
  configuration.

### Phase 5: Manual review and separately authorized publication

This phase is a manual user-approval gate. Keep this plan active after the local commits.

- The user reviews the exact Dea and blog policy changes.
- Any request to push identifies the repository, configured upstream, branch, pending range, exact command, and known
  deployment effects.
- Public, cross-repository, tag, release, workflow-dispatching, or deployment-triggering operations require a fresh
  confirmation immediately before execution.
- Close this plan only after the reviewed changes are pushed through separately authorized operations and both remote
  results are verified, or after the user explicitly defers or cancels a target.

## Non-Goals

- Rolling back, correcting, replacing, or republishing any Dea/L0 1.1.0 artifact.
- Changing compiler, language, standard-library, CLI, API, release-workflow, or blog-site behavior.
- Altering remote URLs, branch upstreams, workflow triggers, release tags, releases, Pages, or live content.
- Treating this implementation request as authority for either repository push.

## Verification Criteria

1. The policy rejects a push from Dea `dev`, which tracks private `origin/dev`, to public `dea-lang/main` even if a plan
   describes that mirror.
2. An instruction to implement an entire release plan stops before any public mirror, tag creation, tag push, release,
   workflow dispatch, or deployment.
3. A proposed release-tag push presents the exact tag, target, remote URL, command, release and asset creation, Pages
   deployment, and downstream blog dispatch before requesting fresh permission.
4. A blog draft cannot move to `_posts/` or reach the live site until the user reviews its exact content and explicitly
   authorizes publication; changed copy must be reviewed again.
5. First-person blog copy is never published without explicit user approval.
6. Sandbox, tool, CI, or command-escalation approval cannot satisfy any remote or publication gate.
7. Local Dea and blog commits exist for review, both remain unpushed, and the existing release and live blog artifacts
   remain unchanged.
