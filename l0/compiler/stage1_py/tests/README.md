# Stage 1 Tests Layout

This directory is the canonical map for Stage 1 Python compiler tests.

## Phase directories

- `cli/`: CLI command/flag/assumption tests (`l0c` behavior).
- `driver/`: `L0Driver` loading, module graph, imports, and end-to-end driver flow.
- `lexer/`: tokenization, lexical errors, and string token escaping.
- `parser/`: parser structure, grammar errors, and parser recovery behavior.
- `name_resolver/`: module environment/import symbol resolution and ambiguity.
- `signatures/`: top-level type/signature resolution.
- `locals/`: local scope resolution.
- `type_checker/`: expression and statement typing/semantic checks.
- `backend/`: C backend/codegen behavior and runtime compile/run coverage.
- `backend/codegen/`: `.l0` + `.expected` golden files for backend file-based tests.
- `c_emitter/`: low-level C emitter policies and invariants.
- `diagnostics/`: diagnostic code/reporting/internal compiler error formatting.
- `ast/`: AST span and printer shape checks.
- `integration/`: intentionally cross-phase tests (lexer/parser/type/backend combined).

Shared fixtures and helpers stay in `conftest.py` at this directory root.

## Where to put new tests

- Prefer the narrowest single-phase directory that matches the behavior under test.
- Use `integration/` only when the test intentionally spans multiple phases.
- Name test files as `test_<feature>.py`.
- Do not add `_l0_` to new test filenames.
- Keep backend golden I/O under `backend/codegen/`.

## Running tests

From the `l0/` directory:

```bash
cd compiler/stage1_py
pytest -n auto
pytest tests/lexer/test_lexer.py
pytest -k "pattern"
```

## Maintenance

- Update this file when adding a new test category/directory.
- If a test suite drifts across phases over time, move it to `integration/` rather than forcing a misleading phase
  folder.
