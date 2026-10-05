# Dea monorepo Copilot instructions

Start by reading `AGENTS.md` at the repository root. If you are changing a language subtree, then read that level's
`AGENTS.md` as well: `l0/AGENTS.md` for Dea/L0 work or `l1/AGENTS.md` for Dea/L1 work. Keep this file as a short router;
use the `AGENTS.md` files as the maintained source of detailed workflow and policy guidance.

## Build, test, and lint commands

The root `Makefile` is monorepo maintenance only:

```bash
make help
make venv
make test
make test-extended
make clean
make clean-all
```

Do not use the root `Makefile` as a dispatcher for level-specific build or test commands. `cd` into the relevant level
directory first. Root `make test` and `make test-extended` delegate to the corresponding target in every registered
level. L0 `test-extended` includes its Stage 2 trace sweep; L1 `test-extended` is the broad local-normal gate. Use
`make -C l1 test-ci` for exhaustive L1 validation.

### `l0/`

Common build and bootstrap flows:

```bash
cd l0
make use-dev-stage1
make use-dev-stage2
source build/dea/bin/l0-env.sh
make PREFIX=/tmp/l0-install install
make docs-artifacts DOC_STAGE=stage2 DEA_DIST_VERSION=dev
DOCS_ARTIFACT="$PWD/build/docs/artifacts/dea_l0_stage2_autodocs.tar.gz" DEA_DIST_VERSION=dev make dist
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
make -j test
make -j test-extended
```

Use `test` for confidently trace-independent L0 work and `test-extended` when L0 trace coverage is required.

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
make use-dev-stage2
source build/dea/bin/l1-env.sh
make test-stage1
make test-stage2
make test-stage2-trace
make triple-test
make test-stage1 TESTS="parser_test"
make test
make test-extended
make test-ci
```

In L1, `test` is the fast representative development gate, `test-extended` runs the Stage 1 and Stage 2 normal suites
without CI-only cases, and `test-ci` is the exhaustive hosted gate. For trace-, bootstrap-, environment-, and
preparation-sensitive changes, run the affected focused targets locally. Use `test-ci` when hosted equivalence or
exhaustive L1 coverage is needed; it adds CI-only normal tests, environment/bootstrap, trace suites, child fixtures, and
triple bootstrap to `test-extended`.

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
- `l1/` has an L0-written Stage 1 oracle and a mechanical self-hosted L1 Stage 2 port. Stage 1 bootstraps through L0
  Stage 2; explicit development selection uses `use-dev-stage1` or `use-dev-stage2`.

For L0, the important big picture is the staged bootstrap chain: Stage 1 (Python) is the reference implementation and
Stage 2 mirrors the same pass structure through code generation and driver execution, both ultimately targeting a single
C99 translation unit. Use `l0/docs/reference/architecture.md` and `l0/AGENTS.md` for the maintained pass-level details.

## Key conventions

- Treat Stage 1 as the oracle for equivalent Stage 2 behavior, diagnostics, and emitted text.
- Equivalent Stage 2 diagnostics must reuse the exact Stage 1 diagnostic code.
- The repo is a single `uv` workspace; the shared virtual environment is repo-local at `./.venv` (or `../.venv` from a
  level directory) and is reused across all levels. The root `Makefile` owns `make venv`; level Makefiles delegate.
- Root `docs/` and `work/` are for Dea-wide or monorepo-wide material only; level-owned docs and plans stay inside the
  corresponding subtree.
- For `l1/`, do not rely on whichever `l0c` happens to be active on `PATH`; use the repo-local default or
  `L1_BOOTSTRAP_L0C`.
- If a task changes behavior, commands, docs ownership, stdlib, runtime, or diagnostics, check the relevant `AGENTS.md`
  and referenced docs before editing.
