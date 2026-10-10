# CLAUDE.md

Assistant guidance for the Dea/L1 subtree.

Read `../AGENTS.md` first for monorepo-wide policy, then read `AGENTS.md` in this directory for the canonical L1
compiler workflow.

Important rules surfaced here so they are not missed:

- L0 remains the stable release line. L1 0.1.0 is the intended future canonical development-toolchain release.
- L1 has one compiler implemented in L0 under `compiler/`; use `build`, `use-dev`, and `test-compiler`.
- The former L1 Stage 2 belongs to L2. Keep L1 feature plans owned by L1 pending individual placement review.
- Keep existing L0 user-facing docs unchanged unless a minimal consistency fix is required.
- Use the explicit L1 bootstrap contract: repo-local `../l0/build/dea/bin/l0c-stage2` by default, or `L1_BOOTSTRAP_L0C`
  when provided.
- For new Markdown docs under `l1/docs/` and `l1/work/`, prefer short reference-style file links with end-of-file
  definitions; this L1-only preference does not force backfills of existing closed plans or initiative docs.
