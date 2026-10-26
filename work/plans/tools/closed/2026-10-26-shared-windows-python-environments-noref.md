# Tool Plan

## Explicit Windows Python environments

- Date: 2026-10-26
- Status: Completed
- Title: Native Windows tooling and full MSYS2 Stage 1 coverage
- Kind: Tooling
- Priority: Medium
- Subsystem: Shared environment provisioning and Windows CI
- Scope: Shared
- Targets:
  - Shared Make environment
  - Windows CI and standalone artifact consumers
  - L0 supported-host guidance
- Origin: Shared environment and CI provisioning
- Porting rule: Windows uses explicit native tooling; POSIX behavior is preserved.
- Target status:
  - Shared Make environment: Implemented
  - Windows CI and standalone artifact consumers: Implemented
  - L0 supported-host guidance: Implemented
- Modules:
  - `Makefile`
  - `l0/Makefile`
  - `l1/Makefile`
  - `l2/Makefile`
  - `scripts/ci_bootstrap.py`
  - `scripts/check_windows_python.py`
  - `.github/actions/`
  - `.github/workflows/`
- Test modules:
  - `scripts/tests/test_ci_bootstrap.py`
  - `l0/compiler/stage1_py/tests/cli/`
- Related:
  - [l0/docs/decisions/0021-supported-host-and-release-tiers.md](../../../../l0/docs/decisions/0021-supported-host-and-release-tiers.md)

## Summary

Use native Windows CPython for the shared uv environment, builds, docs, and normal validation. Add a separately
provisioned full L0 Stage 1 pass under UCRT64 Python, retaining the same collection, expectations, and pytest options.
The extra interpreter must not multiply native compiler or trace suites. No compiler diagnostics change.

## ADR Impact

- Decision: Separate native Windows repository tooling from MSYS2 Stage 1 interpreter coverage.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0025-windows-python-environment-ownership.md`
  - Rationale: Environment ownership and the dependency-authority boundary are lasting shared tooling policy.
- Decision: Reconcile L0 Windows supported-host and release tiers with native tooling and two-interpreter coverage.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0021-supported-host-and-release-tiers.md`
  - Rationale: The existing host tier decision currently designates MSYS2 Python as primary.

## Implementation

1. Forward Windows Make interpreter selection to uv and reject wrong-family shared environments.
2. Provision native tooling deliberately in Windows consumers. Export locked dependencies once during separate temporary
   MSYS2 provisioning, then invoke that interpreter directly with the canonical Stage 1 pytest settings.
3. Audit manual Windows lanes and documentation-inventory path assertions; preserve all behavioral checks.
4. Refresh live guidance and ADRs, validate locally, and commit the completed implementation.

## Findings

- The existing native Windows documentation-inventory failure was reported in both
  `test_explicit_identity_covers_only_matching_occurrences` variants. Current local Doxygen 1.18.0 checks pass; this
  does not establish that Windows XML identity matching is repaired. Preserve all identity and signature assertions.
- The temporary export uses uv's default pip requirements format, avoiding format-option spelling differences between
  older and current uv versions. The frozen export leaves both dependency-authority files unchanged.

## Verification

The normal cross-cutting `test` tier applies: environment selection and CI orchestration do not change compiler or
runtime semantics, trace invocation, or trace inputs. Dedicated trace validation is not required. This is not an
example-only change.

On macOS with native Python 3.14.7 and Apple Clang 17.0.0, the following root gate passed across all three levels:

```sh
make clean test L2_BOOTSTRAP_MODE=development L2_BOOTSTRAP_L1C="$PWD/l1/build/dea/bin/l1c" \
  L0_CC=clang L1_CC=clang L1_RUNTIME_CC=clang L2_CC=clang L2_RUNTIME_CC=clang \
  PYTEST_XDIST_AUTO_NUM_WORKERS=4
```

It includes 1,659 Stage 1 tests with four workers, 58 Stage 2 cases, all selected L1/L2 compiler cases and examples,
workflow and productization fixtures, and documentation checks. L0/L1 documentation selections passed 269/208 tests; L2
tooling passed 134 tests with one platform skip.

Additional evidence:

- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py scripts/tests/test_ci_docs_toolchain.py`: 231
  passed, also covered by the root gate.
- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_docgen_function_inventory.py scripts/tests/test_docgen_inputs.py`:
  51 passed with Doxygen 1.18.0, including both previously failing identity-test variants.
- `uv export --frozen --all-groups --no-emit-workspace --output-file /tmp/dea-msys2-requirements-probe.txt`: successful
  pip-compatible export; `pyproject.toml` and `uv.lock` bytes remain unchanged.
- Orchestration regressions execute POSIX and simulated Windows Make selection, reject the wrong environment family,
  test drive/UNC paths with mixed separators and spaces plus distinct paths, exercise legacy selector routing, and
  verify the MSYS2 target invokes only its explicit interpreter without installing dependencies.
- All workflow/action YAML parsed. Bash syntax checks passed for 146 scripts after replacing GitHub expressions with
  fixture values. A starting-tree comparison confirmed unchanged POSIX workflow steps across nine Windows consumers; the
  standalone L0 matrix regression separately executes Linux/macOS selections.
- All four ADR indexes match their files. Active/staged ADR Impact, staged whitespace, and root pre-commit gates pass.

## Interpreter-probe isolation

Recursive GNU Make may surround correctly selected interpreter paths with directory messages when it inherits
`MAKELEVEL=1 MAKEFLAGS=w`. The test probe uses `--no-print-directory` and retains exact assertions for both selected
paths. Direct and recursive cases cover all four Makefiles and both simulated host branches without weakening path or
environment-family checks. From `l0/`, `make test-ci-bootstrap` passes all 253 checks with prepared native Python 3.14.7
and offline dependencies. This focused evidence validates probe isolation; simulated branches do not establish native
Windows interpreter execution, filesystem behavior, or provisioning times.

## Remaining platform evidence

- No real Windows execution was available locally. Simulated Windows checks do not establish interpreter execution,
  native artifact acceptance, or resolution of the earlier inventory identity failures. Linux commands were inspected
  and their shared POSIX branch exercised on macOS; no native Linux run was performed.
- Real Windows setup and second-pass timings remain unmeasured until an authorized Windows execution is available. Prior
  native Stage 1 observations were 46-83 seconds with four workers; these are not MSYS2 estimates.
- Remote pushes, workflow dispatch/reruns, publication, and deployment are outside this local implementation.
