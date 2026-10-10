# Dea Repository Instructions

Read [AGENTS.md](../AGENTS.md), then the owning level's guidance: [l0/AGENTS.md](../l0/AGENTS.md),
[l1/AGENTS.md](../l1/AGENTS.md), or [l2/AGENTS.md](../l2/AGENTS.md). Use [MONOREPO.md](../MONOREPO.md) for root
workflows and release boundaries.

L0 retains Python Stage 1, self-hosted Stage 2, stage selection, parity, and triple bootstrap. L1 has one `.l0`
implementation compiling `.l1`; L2 has one `.l1` implementation compiling `.l2` and requires an explicitly installed
`L2_BOOTSTRAP_L1C`. Keep target stdlib/runtime sources physically owned by their level. Do not infer ownership from a
source suffix alone or load sibling checkout artifacts from L2.

Run focused commands inside the owning level. L0 uses `test-stage1`/`test-stage2`; L1/L2 use `test-compiler`,
`test-compiler-trace`, `test`, `test-extended`, and `test-ci`. L1 artifact acceptance is separate from compiler CI; L2
isolation uses `test-isolation`. Root `make venv` owns the one shared `.venv` and `uv.lock`.

Generic skills stay under `.agents/skills/`. Preserve root ADR Impact, historical-record, commit, remote/publication,
and portable path-comparison policies. Never claim simulated Windows checks are native validation, or ordinary compiler
checks are fresh-host distribution acceptance. Existing release namespaces do not authorize tags or publication.
