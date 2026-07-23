# Tool Plan

## Establish risk-tiered remote and publication authorization guardrails

- Date: 2026-07-13
- Status: Completed
- Title: Establish risk-tiered remote and publication authorization guardrails
- Kind: Tooling
- Scope: Shared
- Severity: High
- Stage: Shared
- Targets:
  - Dea repository-wide agent guidance
  - Dea planning, finalization, and documentation-refresh skills
  - High-level guidance for independently owned blog publication workflows
- Origin: Dea root agent policy, with L0 release effects documented at their owning Dea surfaces
- Porting rule: Apply the authorization invariants within Dea. Describe external blog workflows only through
  non-enforcing guidelines and defer to each repository's own instructions and tooling.
- Target status:
  - Dea repository-wide agent guidance: Implemented
  - Dea planning, finalization, and documentation-refresh skills: Implemented
  - High-level guidance for independently owned blog publication workflows: Implemented
- Subsystem: Agent authorization policy / release safety / cross-repository publication
- Modules:
  - `CLAUDE.md`
  - `AGENTS.md`
  - `l0/CLAUDE.md`
  - `l0/AGENTS.md`
  - `.agents/skills/create-dea-plan/SKILL.md`
  - `.agents/skills/finalize-dea-work/SKILL.md`
  - `.agents/skills/refresh-stale-docs/SKILL.md`
- Test modules:
  - Dea Markdown and pre-commit validation
  - authorization-policy scenario review
- Related:
  - `l0/work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md`

## Summary

Repository edits, local commits, remote pushes, tags, releases, workflow dispatches, and public deployments have
different risk and authorization boundaries. Existing guidance covers local finalization but does not state those
boundaries strongly enough at every relevant entry point. This plan makes the shared policy explicit in Dea, records the
release-specific automatic effects in L0, and records high-level review and authorization guidelines for independently
managed blog publication workflows. Those blog guidelines are advisory: Dea neither controls nor enforces another
repository's instructions, tooling, or operations.

The already-published Dea/L0 1.1.0 release, tag, documentation, synchronized API content, and blog announcement remain
unchanged. This plan governs future work only.

## Current State

1. Dea's commit guidance defines local validation and commit conventions but does not explicitly separate a local commit
   from authority to push it.
2. L0 release automation turns a stable tag push into an immutable public release, release assets, Pages deployment, and
   a downstream blog synchronization dispatch.
3. Blog publication may run through an independently governed repository whose pushes deploy public content. Dea can
   describe that risk but cannot enforce the external repository's workflow.
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
6. For blog or announcement work, Dea guidance recommends review of the exact final copy and fresh confirmation before
   promotion or deployment. Each separate repository owns and enforces its own publication workflow.
7. A plan describes intended work but grants no remote authority. Sandbox, tool, CI, or escalation approval grants
   technical capability only and cannot satisfy a user-approval gate.

## Goal

1. Establish one authoritative authorization contract for Dea agents.
2. Make L0 release consequences visible before any tag or public push is considered.
3. Make Dea planning, finalization, and documentation-refresh skills preserve the manual publication boundary.
4. Document high-level, non-enforcing review and approval guidance for blog publication in independently owned
   repositories.
5. Produce a reviewable local Dea policy commit without changing remote state.

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

### Phase 3: Document high-level blog publication guidance

- Explain that publication in a separate blog repository is governed by that repository's own instructions and workflow.
- Recommend exact-copy review and explicit user authorization before content promotion or a deployment-triggering
  operation.
- Treat these statements as advisory guidelines, not as enforcement or control over another repository.

### Phase 4: Validate and create local commits

- Run Dea whitespace, Markdown, and pre-commit checks against the changed guidance, skills, and this plan.
- Create one local Dea commit using the repository's conventions.
- Report the exact diff, commit identifier, configured upstream, and unpushed range. Do not push or change upstream
  configuration.

### Phase 5: Preserve remote authorization boundaries

- Completion of this plan depends only on the implemented and validated Dea guidance. It does not depend on changing,
  reviewing, or publishing another repository.
- Any future request to push identifies the repository, configured upstream, branch, pending range, exact command, and
  known deployment effects.
- Public, cross-repository, tag, release, workflow-dispatching, or deployment-triggering operations require a fresh
  confirmation immediately before execution.

## Non-Goals

- Rolling back, correcting, replacing, or republishing any Dea/L0 1.1.0 artifact.
- Changing compiler, language, standard-library, CLI, API, release-workflow, or blog-site behavior.
- Enforcing, changing, or verifying instructions or publication behavior in a separately owned blog repository.
- Altering remote URLs, branch upstreams, workflow triggers, release tags, releases, Pages, or live content.
- Treating this implementation request as authority for any repository push.

## Verification Criteria

1. The policy rejects a push from Dea `dev`, which tracks private `origin/dev`, to public `dea-lang/main` even if a plan
   describes that mirror.
2. An instruction to implement an entire release plan stops before any public mirror, tag creation, tag push, release,
   workflow dispatch, or deployment.
3. A proposed release-tag push presents the exact tag, target, remote URL, command, release and asset creation, Pages
   deployment, and downstream blog dispatch before requesting fresh permission.
4. Dea guidance recommends exact-content review and explicit publication authorization for blog material while making
   clear that a separate repository owns its workflow and enforcement.
5. No change to an independently owned blog repository is required or treated as a completion dependency.
6. Sandbox, tool, CI, or command-escalation approval cannot satisfy any remote or publication gate.
7. A local Dea policy commit exists for review, and the existing release and live blog artifacts remain unchanged by
   this work.

## Completion Notes

- Root Dea guidance now separates local work, private pushes, public writes, tags, releases, dispatches, and deployments
  into explicit authorization tiers.
- L0 guidance records the automatic release, asset, Pages, and downstream-dispatch effects of publishing a stable tag.
- Planning, finalization, and documentation-refresh skills preserve manual approval boundaries and distinguish technical
  capability from user authorization.
- Blog publication is covered only by high-level, non-enforcing guidance. Independently owned repositories remain
  responsible for their own instructions, workflows, and enforcement.
- The authorization scenarios were reviewed against the implemented Dea guidance. This agent workflow policy does not
  require an architectural ADR.
- `git diff --check`, Markdown formatting validation, staged whitespace validation, and root pre-commit checks passed
  for the completed plan.
