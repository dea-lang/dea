# Contributing to Dea/L0

Thanks for contributing! This document provides guidelines for contributing to the Dea/L0 project, including development
setup, coding conventions, and testing.

Dea/L0 now lives under `l0/` inside the Dea monorepo. Unless a section says otherwise, run the commands in this document
from the `l0/` directory.

## Scope and status

Dea/L0 remains experimental. `2.0.0` is the latest released, semantically versioned language line; it incorporates the
coordinated breaking CLI alias migration and wildcard-only `case` defaults. Language, compiler CLI, and runtime changes
must be documented and versioned; backward-incompatible changes are not introduced silently into an existing release
line.

Current work still prioritizes a solid compiler and language-design foundation. Internal refactors, API changes, and
design iterations are expected, while user-visible changes follow the level's semantic-versioning and Stage 1/Stage 2
parity rules.

The focus is on correctness, maintainability, and code quality over performance optimizations or feature completeness.

## Development setup

Prerequisites:

- A C99 compiler (e.g., GCC) for codegen tests and running compiled programs
- `make` (the primary developer workflow entrypoint)
- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv) is recommended, but not required (the `make venv` target uses it automatically
  when available, and falls back to plain `pip`)

For day-to-day development, the `tcc` C compiler is sufficient and fast for codegen tests. Build it from the
[mob development branch](https://repo.or.cz/tinycc.git) (`./configure && make && make install`) if you want to use it,
as distribution packages tend to ship an outdated version.

### Setting up the development environment

For normal development, start with `make venv`: it validates the Python version, creates the shared monorepo virtual
environment at `./.venv`, and installs all dev + docs dependency groups declared in the root `pyproject.toml`. The
monorepo is a single `uv` workspace; level-local `make venv` targets delegate to the root, so any of `make venv`,
`cd l0 && make venv`, or `cd l1 && make venv` converges on the same `./.venv`. `uv` is preferred when on `PATH`; when
absent, `make venv` falls back to `python -m venv` plus `pip install` of the same dependency-group specifiers.

### Pre-commit hooks

After running `make venv`, install the monorepo hooks once from the repository root:

```bash
uv run --group dev pre-commit install -c .pre-commit-config.yaml
```

Three hooks run on every commit:

- **mdformat** -- auto-formats all `.md` files (line wrap 120, numbered lists, GitHub Flavored Markdown). If it
  reformats a file, stage the changes and commit again.
- **copyright-headers** -- checks that tracked `.c`, `.h`, `.l0`, `.l1`, `.py`, `.sh` files have a copyright notice in
  the first 80 lines.
- **adr-impact** -- validates every active plan and initiative plus any added, renamed, or modified closed lifecycle
  document against the staged `## ADR Impact` contract. It also enforces same-change ADR and index evidence at closure.

### Building the compiler(s)

Select the repo-local switchable `l0c` alias (either Stage 1 or Stage 2) so you can use `l0c` in your terminal to test
the intended compiler stage. Each `use-dev-stage*` target builds and installs the corresponding launcher automatically.
For example, to use the Stage 2 L0 compiler:

```bash
make venv
make use-dev-stage2       # use `make use-dev-stage1` to switch to the Stage 1 Python compiler
source build/dea/bin/l0-env.sh
```

If you need both launchers at once (without selecting one), run `make install-dev-stages`. You can override the build
location by setting `DEA_BUILD_DIR`. Dev launchers are built without optimization flags; `make install` and `make dist`
default to `L0_CFLAGS=-O2`.

Note that there is also an internal `./scripts/l0c` entrypoint, which is source-tree Stage 1 only and is used by the
bootstrap mechanics, internal tooling, and Stage 1-focused test scripts. Unless you are working on these specific areas,
prefer the `l0c` alias after `make use-dev-stage*` to ensure you are testing the intended compiler stage.

To override the automatic C compiler selection (e.g., to use `gcc` instead of `tcc` if you have both installed), set the
`L0_CC` environment variable at any time. For example:

```bash
L0_CC=gcc make test-stage2
```

### Running tests

From the `l0/` directory:

```bash
make test-stage1  # runs the Stage 1 test suite (Python compiler)
make test-stage2  # runs the Stage 2 test suite (L0 compiler)
```

For Stage 1 (`compiler/stage1_py`) changes, you can also run specific tests with `pytest`:

```bash
../.venv/bin/python -m pytest compiler/stage1_py/tests/lexer/test_lexer.py
../.venv/bin/python -m pytest -k "test_name" compiler/stage1_py/tests
```

For Stage 2 (`compiler/stage2_l0`) changes, run one of the following Make targets depending on your needs:

```bash
make test-stage2  # runs the standard Stage 2 test suite
make test-stage2 TESTS="driver_test l0c_build_run_test" # runs a specific subset of Stage 2 tests
make test-stage2-trace  # runs the Stage 2 L0-based tests with trace collection and leak triage
make triple-test  # runs only the triple-bootstrap test
make test  # runs normal L0 validation without the dedicated broad trace sweep
make test-all  # runs normal validation plus the dedicated broad trace sweep
```

These Make targets are self-contained repo-local workflows: they ensure `../.venv`, prepare the Stage 2 artifact under
`DEA_BUILD_DIR` (defaults to `./build/dea`), and ignore any previously sourced installed-prefix `L0_*` env.

`make test-stage2-trace` is the required finalization gate when a Stage 2 change can affect runtime, ownership, emitted
lifetimes, trace infrastructure, or trace-eligible test inputs because it checks runtime trace health (including leak
triage) across the trace-eligible Stage 2 suite. Confidently trace-independent work can use `make test`; uncertain or
mixed work uses `make test-all`.

`make triple-test` is a focused test for the triple-bootstrap process, which is a critical end-to-end validation of the
compiler's ability to build itself and produce a stable artifact.

### Smoke test

Verify the compiler works end-to-end:

```bash
l0c --version # ensure the expected version is printed
l0c -Rp examples --run hello    # build and run hello.l0
l0c -Rp examples --check hello  # parse and type-check only
```

### Debugging

Use verbose flags to see compilation stages:

```bash
l0c -v -Rp examples --check hello     # info-level
l0c -vvv -Rp examples --check hello   # debug-level
```

## Making changes

1. Fork and create a topic branch.
2. Keep commits small and focused.
3. Add or update tests for behavior changes.
4. Update docs when changing user-visible behavior (syntax, diagnostics, CLI flags).

## Project structure

- `compiler/stage1_py/`: Stage 1 compiler (Python). This is the bootstrap implementation.
- `compiler/stage2_l0/`: Stage 2 compiler (L0). This is the self-hosted implementation.
- `compiler/shared/runtime/`: Runtime library code written in C.
- `compiler/shared/l0/stdlib/`: Dea/L0 standard library code.
- `examples/`: Example L0 programs.
- `docs/`: Design documents, grammar specification, architecture notes, and other documentation.
- `scripts/`: Utility scripts for development, testing, and maintenance.
- `tests/`: End-to-end tests that may involve both compiler stages or external tools.

## Coding conventions

- Prefer explicit, simple implementations over cleverness.
- Preserve existing grammar/AST shapes unless the change is staged and justified.
- Error handling: return structured diagnostics (`Diagnostic` objects); avoid silent failures.
- See `docs/reference/design-decisions.md` for rationale behind key language and compiler choices.

### Documentation and styling standards

- **Python:** Use Google Style docstrings (include `Args`, `Returns`, `Raises` sections).
- **C (.h/.c) & L0 (.l0):**
  - **Doxygen:** Use Javadoc format (`/** ... */` with `@param`, `@return` tags). Omit the `@brief` tag; rely on the
    first sentence for the brief description.
  - **License Headers:** Keep `SPDX-License-Identifier` and copyright headers in standard C block comments (`/* ... */`)
    at the top of the file, distinct from Doxygen blocks.
  - **Section Separators:**
    - **C/C++:** Banners must fit within a **79-character maximum line width**. For standard block comment separators,
      use exactly 73 equals signs (`=`):
      ```c
      /* =========================================================================
       * Section name
       * ========================================================================= */
      ```
    - **L0:** Use a shorter format to fit within a 40-character line width, with exactly 33 equals (`=`) or hyphen (
      `-`) signs. The title should stay within 33 characters (introduce a newline if longer).
      ```
      /* =================================
         Section Name
         ================================= */
      ```
      Notice the closing line has exactly 3 leading spaces and 33 signs before the `*/`.

### Commit messages

- Use sentence case with a period at the end (e.g., "Add `byte` type support.").
- For non-trivial changes, include a detailed body describing what changed.
- Use backticks for L0 code snippets and type names.
- AI tools and agents should not add Co-Authored-By lines to commits.

## Pull requests

A PR should include:

- What changed and why (1-3 paragraphs)
- Any relevant issue link(s)
- Tests: added/updated, and how to run them locally
- Notes on backward-compatibility (breaking vs non-breaking)

By submitting a contribution, you agree that it may be distributed under the project's dual license (MIT OR Apache-2.0),
consistent with the repository LICENSE files.

## AI-Assisted Contributions Policy

The use of AI or other automated tools to assist in writing code, documentation, or other project materials is
**encouraged** in order to experiment, iterate rapidly, and explore solutions more efficiently. Contributors remain
fully responsible for the correctness, rights to contribute and license, licensing compatibility, and security of their
contributions, regardless of the tools used.

**All contributions must comply with the project's licensing, contribution guidelines, and quality standards.**

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
