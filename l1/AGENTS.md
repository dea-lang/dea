# AGENTS.md

Assistant guidance for the Dea/L1 subtree.

Read `../CLAUDE.md` first for monorepo-wide policy, then read `CLAUDE.md` in this directory for the L1 bootstrap
workflow.

Important rules surfaced here so they are not missed:

- Do not change the root `README.md` narrative away from its current L0 focus in this bootstrap tranche.
- Keep existing L0 user-facing docs unchanged unless a minimal consistency fix is required.
- Use the explicit L1 bootstrap contract: repo-local `../l0/build/dea/bin/l0c-stage2` by default, or `L1_BOOTSTRAP_L0C`
  when provided.
- For new Markdown docs under `l1/docs/` and `l1/work/`, prefer short reference-style file links with end-of-file
  definitions; this L1-only preference does not force backfills of existing closed plans or initiative docs.
