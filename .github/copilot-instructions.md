# Dea monorepo Copilot instructions

Start by reading `CLAUDE.md` at the repository root. If you are changing a language subtree, then read that level's
`CLAUDE.md` as well: `l0/CLAUDE.md` for Dea/L0 work or `l1/CLAUDE.md` for Dea/L1 work. Keep this file as a short router;
use the `CLAUDE.md` files as the maintained source of detailed workflow and policy guidance.

## Build, test, and lint commands

The root `Makefile` is monorepo maintenance only:

```bash
make help
make venv
make test-all
make clean
make clean-all
```

Do not use the root `Makefile` as a dispatcher for level-specific build or test commands. `cd` into the relevant level
directory first. Root `make test-all` is reserved for full validation across every registered level.

### `l0/`

Common build and bootstrap flows:

```bash
cd l0
make use-dev-stage1
make use-dev-stage2
source build/dea/bin/l0-env.sh
make PREFIX=/tmp/l0-install install
make dist
```

Primary test entrypoints:

```bash
cd l0
make test-stage1
make test-stage2
make test-stage2 TESTS="driver_test l0c_build_run_test"
make test-stage2-trace
make triple-test
make test-workflows
make -j test-all
```

Single-test examples:

```bash
cd l0
../.venv/bin/python -m pytest compiler/stage1_py/tests/lexer/test_lexer.py
../.venv/bin/python -m pytest -k "test_name" compiler/stage1_py/tests
make test-stage2 TESTS="driver_test"
make test-stage2-trace TESTS="l0c_lib_test"
```

Lint / hooks (run from the monorepo root):

```bash
uv run --group dev pre-commit install -c .pre-commit-config.yaml
uv run --group dev pre-commit run --all-files -c .pre-commit-config.yaml
```

### `l1/`

Bootstrap and test flows:

```bash
cd l1
make use-dev-stage1
source build/dea/bin/l1-env.sh
make test-stage1
make test-stage1 TESTS="parser_test"
```

`l1/` bootstraps with the repo-local upstream L0 Stage 2 compiler at `../l0/build/dea/bin/l0c-stage2` by default. Use
`L1_BOOTSTRAP_L0C=/path/to/l0c-stage2` to override that explicitly.

## High-level architecture

This repository is a monorepo for the Dea language family. The root owns shared orchestration and shared docs/work
policy, but real implementation workflows are level-local.

- `l0/` is the active compiler project. It contains:
  - the Stage 1 reference compiler in Python
  - the Stage 2 self-hosted compiler in Dea/L0
  - shared runtime and stdlib trees
  - the main docs, tests, and release workflows
- `l1/` is a bootstrap scaffold. Its Stage 1 compiler is written in Dea/L0 and is built using the upstream L0 Stage 2
  toolchain.

For L0, the important big picture is the staged bootstrap chain: Stage 1 (Python) is the reference implementation and
Stage 2 mirrors the same pass structure through code generation and driver execution, both ultimately targeting a single
C99 translation unit. Use `l0/docs/reference/architecture.md` and `l0/CLAUDE.md` for the maintained pass-level details.

## Key conventions

- Treat Stage 1 as the oracle for equivalent Stage 2 behavior, diagnostics, and emitted text.
- Equivalent Stage 2 diagnostics must reuse the exact Stage 1 diagnostic code.
- The repo is a single `uv` workspace; the shared virtual environment is repo-local at `./.venv` (or `../.venv` from a
  level directory) and is reused across all levels. The root `Makefile` owns `make venv`; level Makefiles delegate.
- Root `docs/` and `work/` are for Dea-wide or monorepo-wide material only; level-owned docs and plans stay inside the
  corresponding subtree.
- For `l1/`, do not rely on whichever `l0c` happens to be active on `PATH`; use the repo-local default or
  `L1_BOOTSTRAP_L0C`.
- If a task changes behavior, commands, docs ownership, stdlib, runtime, or diagnostics, check the relevant `CLAUDE.md`
  and referenced docs before editing.
