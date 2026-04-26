# CLAUDE.md

Guidance for Claude Code and AI agents working in the `l0/` subtree of the Dea monorepo.

Read `../CLAUDE.md` first for monorepo-wide policy, commit conventions, shared `.venv`, and root planning guidance.

Run commands from the `l0/` directory.

## Project Overview

Dea/L0 is a small, safe, C-family systems language compiling to C99.

- **Core principle:** No undefined behavior in the language itself.
- **Stage 1:** Compiler pipeline in Python (lexer → parser → AST → semantic passes → C codegen).
- **Stage 2:** Self-hosting compiler (L0-in-L0) with frontend, backend, `--gen`, `--build`, and `--run` implemented.
- **Subsystems:** Grammar/semantics, backend/codegen, driver/build/module layout, and stdlib.

## Documentation — Read On Demand

Detailed information lives in `docs/`. **Before answering questions about grammar, architecture, backend design, or
implementation status, read the relevant doc file(s).**

| Doc file                                   | Covers                                                        |
| ------------------------------------------ | ------------------------------------------------------------- |
| `docs/reference/architecture.md`           | Compiler pipeline, passes, data flow, file layout             |
| `docs/specs/compiler/diagnostic-format.md` | Normative diagnostic output format (header, snippet, gutter)  |
| `docs/specs/compiler/stage1-contract.md`   | Stage 1 compact contract, interfaces, guarantees, doc routing |
| `docs/reference/c-backend-design.md`       | C backend architecture, emission strategy                     |
| `docs/reference/design-decisions.md`       | Runtime, pointer model, integer model, I/O, rationale         |
| `docs/reference/grammar.md`                | Formal EBNF grammar                                           |
| `docs/project-status.md`                   | Implementation status, known limitations, roadmap             |
| `docs/reference/standard-library.md`       | stdlib module reference (`std.*`, `sys.*`)                    |
| `docs/reference/ownership.md`              | Ownership rules for `new`/`drop`, ARC strings, and containers |
| `docs/specs/runtime/trace.md`              | Trace flags, generated defines, runtime trace contract        |

Documentation policy:

- `docs/README.md` for stable-doc placement, naming, metadata standards, and attic rules.
- `work/README.md` for plan/proposal placement, lifecycle rules, and templates.
- **Metadata:** Reference/Specs must have `Version: YYYY-MM-DD`. Plans (Bug Fix/Feature/Refactor/Tool) must use the
  standard metadata block (Date, Status, Kind, etc.).
- Archived/obsolete document policy details live in `docs/README.md`.
- **Maintenance:** If you change stdlib or ARC behavior, you MUST update the corresponding `.md` in `docs/` in the same
  PR.

Also see: `../CONTRIBUTING.md`, `../SECURITY.md`.

## Environment & Setup

- **Virtual Environment:** Always use `make venv` as the primary developer setup entrypoint. It validates Python 3.14+,
  reuses the shared monorepo `../.venv` if present, uses `uv` when available, and falls back to a plain
  `python3 -m venv` workflow with dependencies extracted from `pyproject.toml`. You can run it either from `l0/` or from
  the monorepo root, where the root `Makefile` delegates `make venv` to each registered level.
- **Manual Environment Setup:** If you are not using `make venv`, prefer
  `UV_PROJECT_ENVIRONMENT=../.venv uv sync --group dev --group docs` (uses `pyproject.toml` and `uv.lock`) or fall back
  to `python3 -m venv ../.venv && source ../.venv/bin/activate` and install the dev + docs dependency groups from
  `pyproject.toml` manually. The project is not an installable Python package (`[tool.uv] package = false`); there is no
  `pip install -e .` step.
- **Windows Host Setup:** For Windows validation, use an MSYS2 `UCRT64` shell with MinGW-w64 GCC and GNU Make on `PATH`.
  `MINGW64` is supported as an alternate environment. Source-tree Stage 1 usage is available through
  `./scripts/l0c.cmd`, while repo-local and install-prefix workflows now generate `l0-env.cmd` plus the selected
  `l0c.cmd` alias for native `cmd.exe` usage. Keep the fallback under `scripts/`: the root-level `l0c` name is reserved
  for the selected dev or installed compiler command.
- **Environment Variables:** Source `build/dea/bin/l0-env.sh` only for the repo-local Dea build workflow in POSIX/MSYS2
  bash, or `call build\dea\bin\l0-env.cmd` in `cmd.exe`. For an installed Stage 2 prefix, source
  `<PREFIX>/bin/l0-env.sh` in POSIX/MSYS2 bash or `call <PREFIX>\bin\l0-env.cmd` in `cmd.exe`. For source-tree usage,
  invoke `./scripts/l0c` or `scripts\l0c.cmd` directly; those wrappers derive `L0_HOME` on their own.
- **Pre-commit hooks:** Install from the monorepo root with
  `uv run --directory l0 --group dev pre-commit install -c .pre-commit-config.yaml` after `make venv`. Two hooks run on
  every commit: `mdformat` (auto-reformats `.md` files; config in `pyproject.toml`) and `copyright-headers` (validates
  source file copyright notices). If mdformat reformats a file, stage the changes and re-commit.

## Commands

Run L0-specific commands from the `l0/` directory. The monorepo root `Makefile` only owns `help`, `venv`, `clean`, and
`clean-all`. For normal development, prefer the repo-local switchable `l0c` alias:

```bash
make use-dev-stage2 # or `make use-dev-stage1`; each builds and installs the launcher automatically
source build/dea/bin/l0-env.sh
make PREFIX=/tmp/l0-install install
source /tmp/l0-install/bin/l0-env.sh
```

On Windows `cmd.exe`, use `call build\dea\bin\l0-env.cmd` for the repo-local workflow and `call <PREFIX>\bin\l0-env.cmd`
for an installed prefix.

`make install` requires an explicit `PREFIX=...`; it does not default to a repo-local install root. Both `install` and
`dist` default to `L0_CFLAGS=-O2` when the variable is unset; `install-dev-stage*` targets do not, for fast iteration.
Use `make list-installed PREFIX=...` to list files placed by a previous `make install`.

The source-tree `./scripts/l0c` entrypoint is Stage 1 only and is mainly useful for bootstrap mechanics, internal
tooling, and Stage 1-focused testing:

```bash
./scripts/l0c -P examples --run hello     # build + run
./scripts/l0c -P examples --build hello   # build executable
./scripts/l0c -P examples --gen hello     # emit C only
./scripts/l0c -P examples --check hello   # parse + type-check
./scripts/l0c -P examples --tok hello     # dump tokens
./scripts/l0c -P examples --ast hello     # pretty-print AST
./scripts/l0c -P examples --sym hello     # dump symbols
./scripts/l0c -P examples --type hello    # dump resolved top-level types
python scripts/gen_docs.py --strict    # generate docs; fail on warnings and synthetic __padN__ regressions
python scripts/gen_docs.py --pdf       # also build/copy build/docs/pdf/dea_l0_api_reference.pdf
python scripts/gen_docs.py --pdf-fast  # faster preview PDF build (single pdflatex pass)
make help                         # show the repo-local developer workflow targets
make venv                         # create or reuse the shared ../.venv
make check-examples               # run latest-stage --check across `examples/*.l0`; fail on warnings or errors
make docker CMD=test-all          # explicitly run a make target inside the repo-owned Linux test container
make docker CMD=test-all DOCKER_L0_CC=gcc
```

Verbosity: `-v` (info), `-vvv` (debug).

C compiler selection: `-c <compiler>`. Auto-detection order (used by `l0c` and Stage 1 tests): `$L0_CC`, then `tcc`,
`gcc`, `clang`, `cc` from PATH, then `$CC`.

Trace toggles (codegen/build/run): `--trace-arc`, `--trace-memory`.

For direct Stage 2 artifact usage, use:

```bash
python scripts/build_stage2_l0c.py # build the stage 2 compiler and place it under build/dea/bin/l0c-stage2
./build/dea/bin/l0c-stage2 --check -P examples hello # run the stage 2 compiler directly
./build/dea/bin/l0c-stage2 --build -P examples hello # build directly with the stage 2 compiler
./build/dea/bin/l0c-stage2 --run -P examples hello # build and run directly with the stage 2 compiler
make use-dev-stage2 # build, install, and select the Stage 2 launcher under build/dea/bin
source build/dea/bin/l0-env.sh # activate the repo-local Dea build workflow in your shell
make PREFIX=/tmp/l0-install install # install the self-hosted Stage 2 compiler under one prefix
make test-all # run the full Stage 1 + Stage 2 validation suite, including example checks
make triple-test # run the strict triple-bootstrap regression
```

Stage 2 currently implements analysis/dump modes plus `--gen`, `--build`, and `--run`.

Generated API documentation is written under `build/docs/` and is not part of the hand-authored `docs/` tree. Native
Doxygen LaTeX output is generated under `build/docs/doxygen/latex/`; use `python scripts/gen_docs.py --pdf` to build
`refman.pdf` and copy it into `build/docs/pdf/dea_l0_api_reference.pdf` if a local TeX toolchain is installed. For
faster local previews, `python scripts/gen_docs.py --pdf-fast --latex-only` performs a single-pass PDF build. After each
successful docs run, generated artifacts are mirrored to a stable preview tree under `build/preview/` (`html/`,
`markdown/`, `pdf/`), which is overwritten by the next successful run. Use `-v` / `--verbose` with `scripts/gen_docs.py`
to show m.css warnings and LaTeX build output directly. Release/manual publishing is handled by
`.github/workflows/l0-docs-publish.yml`; PR validation is handled by `.github/workflows/l0-docs-validate.yml`.

### Testing

```bash
make use-dev-stage1                                   # builds and switches the repo-local `l0c` to Stage 1
source build/dea/bin/l0-env.sh
make test-stage1                                      # recommended Stage 1 test entrypoint
../.venv/bin/python -m pytest -n auto compiler/stage1_py/tests
../.venv/bin/python -m pytest compiler/stage1_py/tests/lexer/test_lexer.py
../.venv/bin/python -m pytest -k "test_name" compiler/stage1_py/tests
```

For Stage 2 (`compiler/stage2_l0`) changes, finalization checks should include:

```bash
make test-stage2
make test-stage2-trace
make check-examples
make triple-test # this is included in test-stage2 but can be run separately if needed
```

Full Stage 1 + Stage 2 validation can be run in parallel (recommended finalization step before commit) with:

```bash
make -j test-all # runs all tests in parallel, including Stage 1, Stage 2, example checks, and trace tests
```

For workflow and distribution tooling validation:

```bash
make test-dea-build                                   # validate Make build and install-prefix workflows
make test-dist-fallback                               # validate provenance fallback without Git
make test-workflows                                   # run all workflow and distribution tests
```

To regenerate Stage 2 backend golden C fixtures from Stage 1:

```bash
make refresh-goldens                                  # regenerate Stage 2 backend golden C fixtures
```

These Make targets are self-contained repo-local workflows: they ensure `../.venv`, prepare the Stage 2 artifact under
`DEA_BUILD_DIR` (default=`build/dea`), and scrub installed-prefix `L0_*` env leakage before running.

`run_trace_tests.py` is an important finalization gate because it validates ARC/memory traces and leak triage across all
Stage 2 tests.

The root `Dockerfile` is a supported Linux test environment, but Docker use is always explicit. Prefer
`make docker CMD=test-all` when you want the containerized workflow; do not add Docker as an implicit dependency of the
default host-side `make` targets. If the container needs a specific compiler, pass `DOCKER_L0_CC=...`; do not reuse the
host `L0_CC` setting automatically.

For Stage 1 ownership-sensitive changes (ARC lowering, `drop` behavior, container ownership paths), run targeted ARC
trace tests from `compiler/stage1_py/tests/backend/test_trace_arc.py` and prefer the full file when touching shared ARC
pathways.

When adding or moving tests, follow `compiler/stage1_py/tests/README.md` for placement and naming rules.

Requires pytest >= 9.0.3, pytest-xdist >= 3.5, and a C compiler. Compiler auto-detection follows the logic defined in
the Commands section.

## Critical Constraints

- Assignment is a statement, not an expression.
- `match` is statement-only.
- `case` is statement-only (scalar/string dispatch).
- `with` provides deterministic resource cleanup (inline `=>` or `cleanup` block).
- No generics, traits, or macros in Stage 1.
- Qualified names: single `module::Name` form only.

## Ownership Guardrails

- No `&` (address-of) operator.
- Auto-dereference: `ptr.field` works without `(*ptr).field`.
- Treat `docs/reference/ownership.md` as normative for ownership and memory-management behavior.
- Normal L0 assignment over ARC-managed strings is usually compiler-balanced; avoid manual retain/release in regular
  assignment paths.
- Raw-memory/container internals require explicit ownership discipline (release before zero/remove, and clear owner
  contracts for moved bytes).
- If observed behavior contradicts ownership docs, report with a minimal `.l0` reproducer, generated C excerpt, and
  trace output.

## Diagnostic Codes

Format: `[XXX-NNNN]` (e.g., `[TYP-0158]`). Before adding a new code, confirm it is unused:

```bash
rg -n 'XXX-NNNN' compiler/stage1_py compiler/stage2_l0 docs
```

- Equivalent Stage 2 conditions MUST reuse the exact Stage 1 code, not just the same family. This includes user-facing
  diagnostics and `ICE-xxxx`.
- Never reuse a Stage 1 code with a different meaning in Stage 2.
- New codes are allowed only for Stage 2-only conditions with no Stage 1 equivalent.
- When porting Stage 1 behavior, treat Stage 1 code meaning as the oracle and preserve the same numeric code for the
  equivalent condition.

## Shared Monorepo Policy

Git conventions, documentation standards, and shared plan-placement policy are owned by `../CLAUDE.md`. Follow those
rules here unless this file defines a narrower L0-specific requirement.

### Definition of Done

1. **No UB:** Emitted C99 must be memory-safe and UB-free.
2. **Trace Validated:** `run_trace_tests.py` must pass with zero leaks.
3. **English Only:** All code names and comments MUST be in English.
4. **Tests Updated:** All relevant tests must be added/updated in the same PR.
5. **Documentation Updated:** If behavior changes, corresponding `.md` in `docs/`
6. **Diagnostic Codes:** Equivalent Stage 2 conditions reuse Stage 1 codes exactly, including `ICE-xxxx`; new codes are
   globally unique and verified by search.
7. **Plans Documented:** For non-trivial changes or bug fixes a plan must be documented in `work/plans/` with a clear
   execution path and expected outcomes. Active plans live at the category root (for example `work/plans/features/` or
   `work/plans/tools/`); closed plans are `git mv`-ed into `<category>/closed/` with cross-references updated. See
   `work/README.md` for naming, placement, and closing workflow rules.
