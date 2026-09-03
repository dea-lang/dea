# CLAUDE.md

Assistant guidance for the Dea/L0 subtree.

Read `AGENTS.md` in this directory first and treat it as the primary source of truth for project scope, commands,
architecture, testing, documentation, and constraints.

Important rules surfaced here so they are not missed:

- Follow the repo-local workflows and commands from `AGENTS.md`; do not invent alternate setup/build/test flows.
- Do not revert unrelated user changes.
- Do not amend commits unless explicitly asked.
- Follow the git conventions in `AGENTS.md`, including sentence-case commit summaries ending with a period and no
  `Co-Authored-By` lines.
- If changing documented behavior or ownership/stdlib/CLI/runtime behavior, update the corresponding docs in the same
  change.
- Pre-commit hooks may rewrite Markdown; if they do, stage the rewritten files and commit again.
- Follow the remote and publication authorization policy in the root `AGENTS.md`; a local commit, release plan, green
  CI, sandbox approval, or tool approval does not authorize a push or publication.
- Never push L0 commits to a public repository unless the instructions designate that target and the checked-out branch
  already tracks the exact public remote and branch.
- Creating an L0 release tag requires a separate, explicit request naming the tag and target; implementing a plan that
  mentions it is insufficient. Pushing it always requires fresh confirmation after disclosing the exact remote and all
  automatic effects.
- Pushing an `l0-v*` tag starts the release workflow. A valid stable tag publishes release assets and a GitHub release,
  deploys API documentation to Pages when enabled, and can dispatch a blog documentation update to another repository.
- Keep release and blog copy as drafts until the user reviews the exact final contents; any content change invalidates
  that review, and publication requires fresh confirmation.
