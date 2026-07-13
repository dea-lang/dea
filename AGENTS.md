# AGENTS.md

Assistant guidance for the Dea monorepo.

Read `CLAUDE.md` first for monorepo structure, then read the level-local guide before changing a language subtree.

The root `Makefile` is monorepo-only orchestration (`help`, `venv`, `test-all`, `clean`, `clean-all`). Focused
level-specific commands still run inside the level directory.

For Dea/L0 work, use `l0/AGENTS.md`.

For Dea/L1 work, use `l1/AGENTS.md`.

Non-negotiable remote and publication rules from `CLAUDE.md`:

- "Organize" and "review" are read-only. "Draft" authorizes only the named draft; plans do not authorize release-tag
  creation, remote writes, or publication.
- A local commit never authorizes a push. Pushes require an explicit request and verification of the checked-out
  branch's configured upstream.
- Public, cross-repository, workflow-dispatching, or deployment-triggering writes require fresh user confirmation
  immediately before execution, with the exact target, pending changes, and downstream effects disclosed.
- Never push a public branch unless this repository's instructions designate that target and the checked-out branch
  tracks the exact public remote and branch. Do not bypass this safeguard with an ad hoc refspec or upstream change.
- Creating a release tag requires an explicit request naming the tag and target. Pushing it always requires a separate,
  fresh confirmation that discloses all publication effects.
- Agent review, tests, CI, sandbox approval, credentials, or tool approval never substitute for user review or
  authorization.
