# Bug Fix Plan

## Restore m.css configuration loading on Python 3.15

- Date: 2026-10-26
- Status: Completed
- Title: Restore m.css configuration loading on Python 3.15
- Kind: Bug Fix
- Scope: Shared
- Severity: Medium
- Targets:
  - Vendored m.css Doxygen renderer
  - Vendored m.css Python renderer
- Origin: Python 3.15 documentation validation failures on Windows
- Porting rule: Preserve each CLI's configuration formats while using the same modern import protocol.
- Target status:
  - Vendored m.css Doxygen renderer: Implemented
  - Vendored m.css Python renderer: Implemented
- Subsystem: Shared documentation tooling
- Modules:
  - `tools/m.css/documentation/doxygen.py`
  - `tools/m.css/documentation/python.py`
- Test modules:
  - `scripts/tests/test_docgen_function_inventory.py`

## Summary

Python 3.15 removed `SourceFileLoader.load_module()`, which both vendored m.css CLI entry points use to execute
configuration files. The tracked upstream baseline remains current and has the same defect. Both CLI entry points now
use the supported import specification and execution protocol while preserving module registration, configuration
overrides, relative paths, and extensionless Python-renderer configuration files. The repair covers the Python 3.15
rendering failure without changing the upstream baseline.

## ADR Impact

- Decision: Execute m.css configuration modules through the supported importlib specification and execution protocol.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This restores existing CLI behavior after a Python API removal without changing the documentation
    architecture, upstream baseline, or Windows interpreter-selection policy.

## Scope and verification

1. Register configuration modules before executing them with `exec_module()` and retain explicit source loaders for
   extensionless Python-renderer configurations.
2. Exercise both actual command-line entry points, configuration overrides, dataclasses that inspect their defining
   module, relative and absolute paths containing spaces, and configuration exceptions.
3. Add the Python renderer's Docutils dependency to the shared documentation group so its regression runs in CI.
4. Run focused documentation regressions on Python 3.14 and an isolated Python 3.15 environment, then record the local
   patch in the vendor inventory.

Compiler behavior, runtime ownership, Windows interpreter selection, and the separate XML identity-matching failures
remain outside this repair. The change is trace-independent.

## Results

- Both loaders register the configuration before execution, including dataclass annotation resolution. Explicit source
  loaders preserve Python-renderer configuration files without a `.py` extension. Configuration failures remove the
  failed module before propagating the original exception, matching normal import failure cleanup.
- Eight new CLI cases render configuration overrides or propagate configuration exceptions. They cover absolute and
  relative paths containing spaces and treat deprecation warnings as errors. The original loaders fail these cases on
  Python 3.14 because they use the deprecated API.
- Docutils is included in the shared documentation group. All pre-existing locked package versions and metadata remain
  unchanged. The temporary current `uv` accepts the updated lockfile with `uv lock --check --offline` and
  `uv sync --locked --all-groups --offline`.
- Native macOS x86_64 validation uses Python 3.14.7 and a separate temporary Python 3.15.1 environment with the same
  locked dependencies. Doxygen is version 1.18.0. No Windows interpreter-selection or compiler/runtime inputs changed.

The table records focused documentation validation. Select the matching prepared environment's interpreter as `$PYTHON`;
every selection uses `$PYTHON -m pytest -q -n 0 -p no:cacheprovider <selection> --tb=short` from its stated directory.

| Python | Directory       | Selection                                                                                                                                          | Outcome    |
| ------ | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| 3.14.7 | Repository root | `scripts/tests/test_docgen_function_inventory.py`                                                                                                  | 25 passed  |
| 3.14.7 | `l0/`           | `compiler/stage1_py/tests/cli/test_docgen_*.py`                                                                                                    | 173 passed |
| 3.14.7 | `l1/`           | `tests/test_docgen_*.py`                                                                                                                           | 112 passed |
| 3.14.7 | `l2/`           | `tests/test_docgen_native.py`                                                                                                                      | 3 passed   |
| 3.15.1 | `l1/`           | `tests/test_docgen_*.py ../scripts/tests/test_docgen_function_inventory.py ../scripts/tests/test_c_docs.py ../scripts/tests/test_docgen_inputs.py` | 184 passed |
| 3.15.1 | `l0/`           | `compiler/stage1_py/tests/cli/test_docgen_mcss_compat.py`                                                                                          | 4 passed   |

The suites cover documentation rendering and preserve the existing Dea and Doxygen anonymous-compound behavior. Native
Windows execution remains hosted validation; relative-path cases on macOS do not establish Windows behavior.
