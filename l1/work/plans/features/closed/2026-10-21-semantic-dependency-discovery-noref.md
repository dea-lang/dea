# Feature Plan

## Expose semantic dependencies through P1689R5 and a Make adapter

- Date: 2026-11-05
- Status: Completed
- Title: Add L1 semantic dependency discovery with a neutral P1689R5 report and external Make composition
- Kind: Feature
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Priority: Medium
- Subsystem: Compiler CLI, module resolution, separate compilation and external build integration
- Modules:
  - `l1/compiler/src/l1c_lib.l0`
  - `l1/compiler/src/cli_args/`
  - `l1/compiler/src/driver/resolve.l0`
  - `l1/compiler/src/module_graph.l0`
  - `l1/compiler/src/module_graph/order.l0`
  - `l1/compiler/src/preparation/consumer.l0`
  - `l1/compiler/src/dependency_report.l0`
  - `l1/scripts/p1689_make.py`
- Test modules:
  - `l1/compiler/tests/cli_args_test.l0`
  - `l1/compiler/tests/driver_test.l0`
  - `l1/compiler/tests/module_graph_test.l0`
  - `l1/compiler/tests/dependency_report_test.l0`
  - `l1/compiler/tests/l1c_dependency_discovery_test.py`
  - `l1/tests/test_p1689_make.py`
- Related:
  - `l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md`
  - `l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md`
  - `docs/specs/compiler/cli-contract.md`
  - `docs/specs/compiler/diagnostic-code-catalog.md`

## Summary

Implement Phase D of [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]: expose the
canonical resolver's scheduling facts as P1689R5, then consume that neutral report through an optional external GNU Make
adapter. The compiler owns semantic analysis and interface validation; the project owns native inputs, recipes,
freshness, scheduling and execution.

## ADR Impact

- Decision: Expose compiler-produced P1689R5 scheduling facts with an external Make consumer and optional explanatory
  Dea metadata.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0053-semantic-dependency-reports-and-external-make-composition.md`
  - Rationale: The public dependency boundary, extension rules and separation of compiler facts from build execution are
    lasting integration contracts. Share this decision with the parent initiative.
- Decision: Preserve interface-first provider authority while using separate discovery and compilation roots.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: The existing resolver already supplies the needed behavior. The adapter must distinguish its generated
    outputs from intentionally prebuilt inputs without adding source-over-interface precedence.
- Decision: Add a flag-selected L1 dependency-discovery mode and output-mapping option.
  - Scope: Shared
  - Disposition: Amend ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: Register the L1 extension while preserving existing option meanings, primary-mode grammar and exit codes.

## Delivered behavior

- `--scan-deps MODULE --artifact-root BUILD` is an L1-only primary mode. It emits UTF-8 P1689R5 version 1, revision 0 to
  stdout or exact `-o REPORT`, with ordinary CLI/analysis exit meanings and stderr diagnostics.
- Each selected source module contributes its planned object/interface pair in dependency-first order. Core `requires`
  contains complete interface closure, including paths reached through prebuilt and graph-loaded link-only providers.
  Prebuilt providers have no fabricated source action; virtual modules impose no file obligations. Registry-only graph
  providers are rejected by the projection rather than silently losing requirements. No Dea annotations are necessary.
- Scans use source fallback and retain interface-first imports, exact selected source paths and caller output mapping.
  Explicit profile selection verifies semantic inventory without host probes, managed native caches or original bundled
  sources. Output roots never become input roots implicitly.
- Report publication follows complete analysis and serialization. Selected inputs, aliases, profile payloads, paired
  output ownership and unusable output ancestors are protected. Publication uses a private sibling workspace and
  restores prior complete bytes on failure. A nonzero scan must stop the outer build; a retained earlier report is not
  accepted.
- Windows drive-relative paths are frozen to absolute paths for transport. Native separators remain distinct from JSON
  escaping. Darwin and Windows conservatively reject case-fold-equivalent output ownership, independently of exact file
  identity; literal POSIX backslashes remain ordinary filename bytes.
- `l1/scripts/p1689_make.py` validates core-only reports and canonical mappings, rejects duplicate/conflicting or
  missing providers, checks selected prebuilt candidates in the generated root, and publishes an
  unchanged-byte-preserving Make fragment. Malformed JSON includes duplicate keys and nonstandard numeric constants.
- Explicit GNU Make 4.3 grouped rules rebuild both `.o` and `.l1m` when either peer is missing, including requests for
  only the surviving peer. Separate prerequisite escaping and shell quoting preserve supported paths. Recipes receive
  source, primary object and canonical module name; dotted modules compile using the same ordered roots.
- The project-owned outer fixture locks discovery, adaptation, configuration publication and inner Make together.
  Compilation adds the validated generated-interface root after intentional prebuilt roots. Residual candidates for
  selected prebuilt providers fail before native actions, including dangling links, aliases and nonregular paths;
  unrelated leftovers are permitted. Nothing is pruned automatically.
- A fresh scan precedes every inner build. The fragment and caller configuration stamp invalidate all source actions and
  final linking on graph/selection changes, including older selected inputs and removed source objects. Native headers
  belong to compilation prerequisites; libraries, prebuilt objects and foreign inputs remain caller-owned link inputs.
  Final `--link --entry MODULE` selects exactly the scanned target.
- L1 CI provisions GNU Make on macOS. The adapter remains optional repository tooling and adds no installed-compiler
  Python or Make dependency.

The public contract, filename subset, examples and deferred scope are recorded in
[l1/docs/reference/dependency-discovery.md][discovery]. Existing generated-C, compile-only rollback, standalone-link,
lifecycle, provider-precedence and managed-profile contracts remain in force.

## Diagnostic assignments

The live catalog and active reservations were rechecked before assignment. `L1C-2200` reports invalid discovery CLI or
mapping configuration; `L1C-2201` reports conflicting/protected output paths or an unrepresentable provider mapping;
`L1C-2202` reports serialization/publication failures. `L1C-2203` through `L1C-2219` remain reserved. Resolution,
interface and profile failures retain existing codes. Adapter diagnostics are tooling errors, not compiler code
families.

## Verification

Validation tier: broad L1 normal coverage plus focused ownership traces, because the new report owns graph traversal,
serialization and command-lifetime buffers. Shared changes only document the L1 extension or provision its CI tool; no
predecessor or successor implementation changes are included.

Native local environment: macOS Intel, `/usr/bin/clang` (Apple Clang 17.0.0), verified `--no-default-config` support,
and GNU Make 4.4.1. Builds and compiler checks explicitly select `L0_CC`, `L1_CC` and `L1_RUNTIME_CC` as
`/usr/bin/clang`; `UV_CACHE_DIR=/tmp/dea-uv-cache` keeps tool caches writable in the isolated worktree.

- Focused compiler normal checks:
  `make -C l1 test-compiler TESTS="cli_args_test dependency_report_test driver_test module_graph_test"`, with the
  changed report test rerun after mapping/command-path hardening. All passed.
- Focused ownership traces: `make -C l1 test-compiler-trace TESTS="cli_args_test dependency_report_test"`, followed by
  the final report case through `compiler/scripts/run_trace_tests.py dependency_report_test` from `l1/`. Zero leaked
  object/string pointers. The report case covers serialization, complete command success, semantic failure, publication
  failure and protected-input rejection. The CLI trace remains valid with unchanged covered inputs.
- Adapter suite: `.venv/bin/python -m pytest -q -n 0 l1/tests/test_p1689_make.py`, 25 passed, including real grouped
  Make execution, alias serialization, failed-fragment preservation and simulated Windows drive/UNC/mixed paths.
- Compiler-produced integration: `.venv/bin/python l1/compiler/tests/l1c_dependency_discovery_test.py` passed clean,
  unchanged and incremental composition; dependency diamonds and prebuilt/link closure; stale generated interfaces
  versus explicit `-I`; old newly shadowing sources/providers without configuration changes; provider
  removal/restoration; source-to-profile/default bundled transitions; target-entry failures; missing peers; header/body
  edits; compile/scan failure preservation; stripped annotations; lifecycle output and retained module-C equality with
  explicit/managed compositions. The normal aggregate also covers the final fixture shell-quoting refinements.
- Shared CI configuration checks: `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_ci_bootstrap.py`, 277 passed.
- Normal L1 aggregate coverage: `make -C l1 test-extended` passed 114 documentation checks and 92 normal compiler cases.
  Two fixture/assertion failures were corrected: help now includes the new mode, and Make environment-expanded include
  paths preserve literal `#`. Both passed focused reruns through
  `.venv/bin/python l1/compiler/tests/l1c_help_output_test.py` and
  `.venv/bin/python l1/compiler/tests/l1c_dependency_discovery_test.py`. The other 92 results and the compiler ownership
  traces remain applicable because their code, toolchain and test inputs did not change.
- Remaining aggregate targets:
  `make -C l1 -o build check-examples test-docker-wine-runner test-tooling test-productization` uses the unchanged
  validated compiler: four examples, six runner checks, 46 tooling tests and 289 productization tests passed; 14
  platform-specific productization cases were skipped on this host.
- ADR Impact, staged whitespace and root pre-commit gates passed before the local commit.

Windows drive, UNC, mixed-separator and case behavior has portable simulated coverage; this is not native Windows
validation. Linux x86_64, macOS ARM64 and Windows UCRT64 execution, plus exhaustive L1 `test-ci` platform evidence,
remain initiative completion gates. Initiative 0010 therefore remains active. No remote writes, workflow dispatches,
releases or publication were performed.

## Deferred scope

No native host dependency discovery, persistent incremental database, per-symbol invalidation, content-preserving
interface publication, compile-time consumed-input reports, arbitrary per-module mappings, retained-C discovery,
production compiler/stdlib Make conversion, package manager, bootstrap conversion or L2 port. Public fingerprints alone
do not prove complete rebuild validity; P1689R5 does not imply automatic CMake integration or ISO standardization.

[discovery]: ../../../../docs/reference/dependency-discovery.md
[initiative]: ../../../initiatives/0010-explicit-profiles-and-composable-builds.md
