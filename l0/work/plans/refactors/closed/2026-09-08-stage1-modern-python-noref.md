# Refactor Plan

## Modernize Stage 1 Python within the existing runtime baseline

- Date: 2026-09-08
- Status: Completed
- Title: Modernize Stage 1 annotations and structural dispatch with Python 3.15 compatibility validation
- Kind: Refactor
- Severity: Low
- Stage: 1
- Subsystem: Python compiler implementation and local compatibility validation
- Modules:
  - `l0/compiler/stage1_py/`
  - `.github/workflows/ci.yml`
- Test modules:
  - `l0/compiler/stage1_py/tests/ast/test_annotations.py`
  - `l0/compiler/stage1_py/tests/diagnostics/test_diagnostic_annotations.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_type_formatting.py`
  - `l0/compiler/stage1_py/tests/type_checker/test_expr_typechecker_basic.py`
  - `l0/compiler/stage1_py/tests/cli/test_docgen_python_filter.py`
- Related:
  - [l0/docs/reference/architecture.md](../../../../docs/reference/architecture.md)

## Summary

Use the modern Python features that simplify the Stage 1 implementation while retaining the Python 3.14 minimum,
compiler semantics, diagnostic output, and generated C. Validate Python 3.15 independently before considering any future
baseline change.

## ADR Impact

- Decision: Express existing Stage 1 implementation contracts using modern Python annotations and structural dispatch.
  - Scope: N/A
  - Disposition: ADR not warranted
  - ADR: None
  - Rationale: This is an internal syntax refactor and additional compatibility validation. It preserves the existing
    runtime baseline, compiler architecture, language semantics, and external contracts.

## Execution Path

1. Replace legacy typing containers and optional types in production modules; use collection ABCs for callable and
   sequence annotations. Use native deferred annotations while preserving signature introspection at import cycles.
2. Name qualified semantic table and dependency graph keys with `l0_symbols.SymbolKey`; runtime keys remain tuples.
3. Convert expression inference and semantic type formatting to keyword class patterns, preserving order, caching,
   recursion, unknown-node fallbacks, and diagnostic behavior.
4. Validate Python 3.15 locally, retaining the existing Python 3.14 CI matrix and shared workspace minimum.
5. Add focused regression tests, refresh architecture guidance, validate generated documentation and compiler parity,
   and obtain an independent read-only review. Fix confirmed findings before closure.

## Non-Goals

- No change to L0 or Stage 2 language semantics, runtime ownership, diagnostic codes, or generated C conventions.
- No synthetic generic abstractions, template-string processor, lazy imports, frozen mappings, or sentinels.
- No raised Python minimum, remote workflow dispatch, push, or publication.

## Verification Criteria

- Normal monorepo `make test` validation after `make clean`; the refactor is trace-independent because runtime ownership
  and emission logic are unchanged. Existing focused ARC regression tests remain included.
- Byte-for-byte equality against the pre-refactor Stage 1 C output for the complete self-hosted compiler.
- Focused coverage for nested type formatting, subclass dispatch, cached expressions, and signature introspection.
- Strict documentation generation including the rendered type alias and union annotations.
- Python 3.15 compatibility testing and informational startup measurements where a local interpreter is available.
- Independent review, resolved findings, ADR validation, staged whitespace checks, and pre-commit before a local commit.

## Outcome and Validation

The production annotation migration is complete: 434 legacy container/optional forms were replaced, and
`collections.abc` owns callable/sequence imports. Expression inference and type formatting now use structural matching;
other dispatch remains unchanged. Qualified semantic keys use `SymbolKey` without changing their tuple representation.
Python 3.15 compatibility was validated locally; the existing Python 3.14 CI workflow is retained.

An independent read-only reviewer found two signature-introspection regressions. Both were fixed: backend cleanup
helpers now import `WithItem`, and the diagnostic token parameter retains a whole quoted annotation across the lexer
import cycle. Regression tests cover both boundaries. The reviewer then rechecked 1,286 production objects with zero
annotation-evaluation failures and reported no remaining actionable findings.

Validation completed on the local Intel macOS host:

- Root `make clean`, followed by `PYTEST_XDIST_AUTO_NUM_WORKERS=4 make test`: passed. This included 1,523 Stage 1 tests,
  58 L0 Stage 2 runner cases including triple bootstrap, 73 L1 runner cases, environment/workflow checks, and examples.
- After the review fixes, from `l0/`,
  `../.venv/bin/python -m pytest -n 4 -q --quiet-progress compiler/stage1_py/tests/ast compiler/stage1_py/tests/diagnostics compiler/stage1_py/tests/backend/test_trace_arc.py compiler/stage1_py/tests/cli/test_docgen_python_filter.py`:
  323 passed on Python 3.14.6. The earlier normal suite result was retained, with the changed annotation/import
  boundaries revalidated by this focused run.
- Full Stage 1 suite under an isolated official Python 3.15.0rc2 interpreter with the repository's locked dependencies:
  1,525 passed. Only temporary macOS framework linkage was relocated; the shared Python 3.14 environment was retained.
- Stage 1 `--gen -Rp compiler/stage2_l0/src l0c` output matched the pre-refactor output byte-for-byte on Python 3.14 and
  Python 3.15, covering the complete self-hosted compiler translation unit.
- From `l0/`, `../.venv/bin/python scripts/gen_docs.py --strict --no-latex`: passed after the review fixes. Generated
  Markdown/HTML includes the type alias and union annotations.
- The CI workflow matches the pre-modernization version byte-for-byte. YAML parsing and shell syntax checks passed.

### Informational CLI measurements

The following medians use 11 warm samples per variant after one warm-up, alternating invocation order, after the heavy
compiler tests finished. Commands invoke Stage 1 directly; `--check` targets `l0/examples/hello.l0`. The baseline uses
the original production Python files, and all variants share the current unchanged L0 source inputs.

| Command              | Python 3.14.6 before | Python 3.14.6 after | Python 3.15.0rc2 after |
| -------------------- | -------------------- | ------------------- | ---------------------- |
| `--help`             | 185.37 ms            | 184.08 ms           | 188.19 ms              |
| `--check` on `hello` | 257.29 ms            | 256.83 ms           | 234.77 ms              |

The refactor is effectively neutral for these Python 3.14 startup probes. Python 3.15 improves the small check command
but not help startup; these measurements do not establish overall compiler throughput. The Python 3.14 minimum remains
unchanged, with Python 3.15 independently validated. Raw samples and temporary interpreters are not repository
artifacts.
