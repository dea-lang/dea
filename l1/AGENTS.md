# AGENTS.md

Guidance for AI agents working in the `l1/` subtree of the Dea monorepo.

Read `../AGENTS.md` first for monorepo-wide policy, commit conventions, planning policy, shared `.venv`, and quality
standards.

Run commands from the `l1/` directory.

## Project Overview

Dea/L1 is in bootstrap-scaffold status.

- `compiler/stage1_l0/` is the initial L1 compiler seed implemented in Dea/L0.
- `compiler/stage2_l1/` is a placeholder for the future self-hosted L1 compiler.
- `compiler/shared/runtime/` is the copied shared runtime tree.
- `compiler/shared/l1/stdlib/` is the copied L1 stdlib seed.

## Bootstrap Contract

- Local development defaults to the repo-local upstream L0 Stage 2 compiler at `../l0/build/dea/bin/l0c-stage2`.
- Prepare that default with `make -C ../l0 use-dev-stage2`.
- Override the upstream compiler explicitly with `L1_BOOTSTRAP_L0C=/path/to/l0c-stage2`.
- Do not rely on whichever `l0c` happens to be active on `PATH`.

## Commands

```bash
make venv
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --help
l1c --version
make check-examples
make test-stage1
make test
make test-stage1-trace
make test-stage1-trace-smoke
make test-stage1-trace-all
make test-all
make test-ci
```

`make test` combines the normal Stage 1, environment-stackability, and example validation without the dedicated broad
ARC/memory trace sweep. Use it for confidently trace-independent work. `make test-all` adds the default dedicated trace
sweep and remains the full local/Docker backstop.

`make test-stage1-trace` is the default ARC/memory trace suite and skips intentionally slow trace cases such as
`math_runtime_compile_test`. Use `make test-stage1-trace-all` to include those slow trace checks, or pass a slow test
explicitly with `TESTS="math_runtime_compile_test"` when investigating it.

`make test-stage1-trace-smoke` retains the focused ARC/memory trace subset for quick developer diagnostics. The
`make test-ci` target delegates to `make test-all` on every supported host, so hosted Windows, Linux, and macOS
validation all run the full normal suite plus the default dedicated trace sweep.

## Current Scope

- This subtree is bootstrap-only for now.
- There is no L1 install/dist/release/docs-publish workflow yet.
- Keep root `README.md` and existing L0 user-facing docs unchanged unless the task explicitly requires a minimal
  consistency fix.

## Documentation Link Style

- This guidance is L1-only. Do not apply it to `l0/` or to monorepo-root docs by default.
- For new Markdown documents under `l1/docs/` and `l1/work/`, prefer CommonMark/GFM reference-style links over inline
  `[text](path)` links when linking repository files.
- Keep reference ids short and readable, typically one or two words joined with hyphens, such as
  `[interface-fingerprints]` or `[runtime-library]`.
- Do not include dates, numeric plan/initiative prefixes, `noref`, or file extensions in reference ids unless a real
  uniqueness conflict leaves no cleaner option.
- Reuse one reference id per target within a file, and place the reference definitions at the end of the document.
- This is a preferred style for new L1 docs and work docs. It is not a blanket backfill requirement for existing closed
  plans, and it does not require rewriting existing initiative documents unless the task explicitly asks for it.
