# Refactor Plan

## Canonical L1/L2 compiler split and L1 delivery retargeting

- Date: 2026-10-10
- Status: In Progress
- Title: Canonical L1/L2 compiler split and L1 delivery retargeting
- Kind: Refactor
- Severity: High
- Stage: Shared
- Scope: Shared
- Targets:
  - L1 canonical compiler and distribution.
  - L2 canonical compiler and independent owned support.
  - Shared repository tooling, guidance, and validation.
- Origin: Approved compiler-lineage decision.
- Porting rule: Mechanically transplant the former L1 Stage 2 into L2; preserve semantics and physical ownership.
- Target status:
  - L1: Implemented; local compiler and macOS Intel/Linux artifact gates passed; remaining native acceptance pending
  - L2: Implemented; installed-bootstrap baseline and opt-in isolation passed; coordinated development hosted CI pending
  - Shared tooling: Implemented; focused regressions passed; explicit hosted validation of the new tree pending

## Summary

Retain the L0-implemented canonical `l1c`, move the former L1 Stage 2 into the independent L1-implemented `l2c`, and
retarget completed L1 installation/distribution machinery. L1 0.1.0 is the intended future canonical L1
development-toolchain release. The split must complete and fresh product acceptance must pass before hosted L1 release
workflows are implemented.

## ADR Impact

- Decision: One canonical compiler per level after L0, with explicit upstream toolchain dependencies.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0022-single-compiler-level-lineage.md`
  - Rationale: The approved lineage supersedes the universal two-stage policy while retaining L0's existing model.
- Decision: Canonical L1 delivery and matching stage-free offline references retain productization safeguards.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md`
  - Rationale: The new artifact requires explicit construction, identity, and acceptance boundaries.
- Decision: L2 owns its target inputs and builds through an explicit installed or development L1 toolchain.
  - Scope: L2
  - Disposition: Amend ADR
  - ADR: `l2/docs/decisions/0001-independent-canonical-compiler.md`
  - Rationale: Preserve the independent target boundary while permitting explicit same-run development bootstrap reuse.

## Implementation

1. Flatten canonical compiler paths to `l1/compiler/{src,support,tests,scripts}` and the corresponding L2 paths. Keep L1
   `.l0` and L2 `.l1` implementation sources. Remove L1 intra-level stage selection, parity, and triple bootstrap.
2. Build the installed L1 artifact in private scratch with an installed overlay; preserve semantic-input verification,
   prefix ownership/recovery, immutable inputs, writable caches, optional install docs and mandatory verified dist docs.
   New install/docs identities use stage-free schema 2 and fresh prefixes; reject obsolete schema-1 stage artifacts.
3. Physically copy target support into L2. Require explicit `L2_BOOTSTRAP_L1C`, installed by default with optional
   `L2_BOOTSTRAP_MODE=development` for a generated development toolchain; use `.l2`/`.l2m`, `l2c`, and equivalent
   `L2C-xxxx` codes. Preserve extensionless logical targets, ABI, algorithms, and shared diagnostics.
4. Retarget live docs, applicable open plans, skills, selectors, workspace membership, editor identities, and existing
   CI. Preserve closed plans, attachments, and historical acceptance. Keep L1 features owned by L1 pending individual
   review.
5. Reuse explicit same-run L0/L1 predecessor outputs in Unified CI. Prepare a missing development bootstrap once; reject
   invalid handoffs. Keep standalone L2's installed bootstrap and make Docker isolation explicitly opt-in. Central L2
   routing defaults off, with `default`/`on`/`off` manual overrides; an enabled default selects L2/shared-tooling
   changes.

## Diagnostic Planning

Copy the established L1 compiler/driver numeric identities into the new L2C family with the same meanings. This is a
mechanical level namespace, not a new diagnostic area; no unrelated code is renumbered and no speculative block is
reserved. Reconcile emitted L2 codes with the live shared catalog. Shared families retain existing applicability.

## Verification Criteria

- Canonical L1 build and representative language/diagnostic, separate compile/link, stdlib/runtime, and trace checks.
- Product fixtures, generated-reference coverage, strict HTML/full PDF, installed startup and relocation, semantic input
  integrity, inventory recovery, exact archive selection/result/evidence, and failure/unsafe archive rejection.
- Fresh native artifact build/verify evidence on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. A local
  combined run does not establish checkout absence; old Stage 2 acceptance does not cover the retargeted compiler.
- Independent L2 build with installed L1 and sibling checkouts/artifacts inaccessible; target execution without L1.
  Include valid `.l2`, invalid `.l0`/`.l1`/other suffixes, logical targets, `.l2m` interfaces, and separate
  compile/link.
- Same-run predecessor handoffs, missing-bootstrap preparation, invalid explicit selection, and installed/development
  bootstrap modes. Central L2 routing defaults and manual overrides, unavailable diff endpoints, and default-disabled
  Docker isolation retain native compiler and intentional construction coverage.
- Explicit Unified CI against the finalized tree with `platform=all`, `run_l2_ci=on`, and `l2_run_isolation=true`.
  Default routing does not establish acceptance for these changes.
- L2 source discovery and focused test routing, preserved L0 stage selectors, portable path tests, ADR Impact,
  whitespace, and root pre-commit. Simulated Windows paths do not replace native Windows validation.

## Evidence and Remaining Work

### Implementation

Both levels now have canonical source, support, launcher, build, test, and target-input ownership. L1 installation uses
two private L0 constructions, including the installed-mode overlay, records the actual construction command and runtime
controls, and checks the installed semantic graph against immutable captured inputs. Schema-2 inventory, documentation,
distribution, and acceptance identities reject former stage artifacts. L2 requires an explicit L1 bootstrap, installed
by default or a complete generated development toolchain in explicit development mode, and preserves implementation ABI
helpers while separating `.l2` programs and `.l2m` interfaces. Unified CI passes predecessor paths between delegates
without redundant L1 installation; intentional construction fixtures retain their builds. Linux Docker isolation is
opt-in and keeps its installed Bookworm bootstrap. Automatic L2 routing and default manual selection share one initially
disabled setting; explicit manual `off` always suppresses L2.

Workspace, CI routing, editor associations, selectors, guidance, shared contracts, active-plan metadata, and the
required ADRs are updated. Other feature plans remain owned by L1. Existing Stage 2 product evidence remains historical
and does not satisfy canonical acceptance.

### Completed local validation

The native host is macOS Intel with Python 3.14 and Apple Clang 17. Linux checks use Debian Bookworm with GCC 12.
Commands below are the reproducible gate or its constituent checks; successful unaffected constituents are reused
instead of repeating an entire aggregate after a focused correction.

- `make -C l1 build check-examples`: current canonical build, all 23 bundled semantic interfaces, and all four examples
  passed.
- L1 `compiler/scripts/run_tests.py --include-ci-only`: 86 cases passed; the remaining preparation-identity case passed
  through its direct native invocation after allowing the required macOS `sysctl` query outside the filesystem sandbox.
- L1 `compiler/scripts/run_trace_tests.py`: all 47 default cases passed with no leaked objects or strings; the largest
  log contained over 20 million events. `--children` passed both independently compiled child fixtures with no leaks.
  `make -C l1 test-env` passed. Together with the normal/CI-only cases and the tooling/product fixtures, these complete
  the constituent checks of `make -C l1 test-ci`.
- L1 documentation/productization fixtures: 313 passed, with 14 native-Windows-only skips. The final installed semantic
  graph and payload/install regressions passed 57 cases. Two real private-overlay/startup tests passed; a fresh final
  `make -C l1 install PREFIX=<new-prefix>` also passed both private constructions and installed graph verification with
  recorded `-O2` L0 native construction flags.
- Strict canonical HTML and full indexed PDF generation passed. The schema-2, stage-free `dev` bundle
  `dea_l1_autodocs.tar.gz` contains the complete references and `dea_l1_api_reference.pdf`; all required LaTeX/reference
  and index passes completed. The PDF has 1,410 pages and no undefined references. Both native artifact builds consume
  these exact verified documentation bytes.
- macOS Intel exact-artifact acceptance passed for a freshly built schema-2 `dev` archive. Build and verification ran
  separately. The transported verification harness ran under `sandbox-exec`, with explicit failed-read probes for both
  checkouts and both installed bootstrap prefixes, plus denied networking. It passed relocation with spaces, read-only
  input checks, semantic work without C tools, cold/warm preparation, compilation, linking, execution, and profile
  smoke. The accepted archive SHA-256 is `3471fb4c64180760978e66b3db18ee5501621871d0c4492518cc52917f7e4d0f`.
- Linux x86_64 exact-artifact acceptance passed with GCC 12.2 in separate Bookworm builder/verifier containers. The
  builder ran `productization_acceptance.py --phase build --directory <evidence>` against the current sources and the
  same verified documentation bundle. A fresh Python 3.14.8 verifier ran the transported harness with `--phase verify`,
  networking disabled, and only the evidence/harness mounted; no checkout, L0, or L1 bootstrap was present. All native,
  relocation, semantic-only, standalone link, cold/warm preparation, build/run, and runtime-configuration smoke checks
  passed. The accepted archive SHA-256 is `e988b17b7c3c8ca012342778f6b7b53028013fb137c786bdab1749bf6fdfc8b7`.
- L1 canonical build/tooling regressions passed nine cases; the minimal Wine-context regressions passed six. Portable
  path checks include POSIX, Windows, mixed separators, spaces, and distinct-path rejection; these are simulations of
  Windows spelling, not native Windows execution.
- Installed-bootstrap L2 baseline, `compiler/scripts/run_tests.py`: all 66 normal cases and all five CI-only cases
  passed. Focused reruns cover the final source-path correction, migrated fixture expectations, native support fixtures,
  and construction/preparation checks; unchanged AST, type, and backend results remain applicable. No timeout bounds
  were relaxed. Existing suffixless output files preserve logical module resolution; explicit paths and existing
  suffixed files reject wrong source extensions before module fallback, including shadowing dotted-module names.
- Installed-bootstrap L2 baseline, `compiler/scripts/run_trace_tests.py`: all 47 default cases and both `--children`
  fixtures passed with no leaks. The final canonical build verified all 23 semantic interfaces; six tooling tests and
  all four examples passed. These complete the constituent checks of `make -C l2 test-ci`.
- Reused-development L1 construction passed all 71 L2 normal/CI-only cases, 17 trace cases, and both child trace
  fixtures. The complete development-bootstrap trace gate remains pending. Required acceptance comes from explicit
  hosted CI against the new tree.
- The opt-in `L2_ISOLATION_BOOTSTRAP_PREFIX=<installed-linux-l1> make -C l2 test-isolation` passed using a fresh
  Bookworm prefix from `docker build -f l1/Dockerfile` and container `make install`. The construction image contains
  only L2, the installed L1 prefix, and explicitly enumerated root tooling; its available tooling and source-path,
  filesystem-support, and language-identity checks passed. A separate operation image omits L1, L0, Python, and Make,
  clears bootstrap/target caches, cold-prepares L2-owned stdlib/runtime, produces and consumes `.l2m` after removing the
  provider source, links/runs the result, and rejects a `.l1` input with `L2C-0011`.
- Focused CI/bootstrap checks passed all 67 cases: 40 routing/delegate cases and 27 L2 construction cases. They cover
  central defaults, all manual overrides, shared/level/unrelated paths, unavailable diffs, same-run reuse, missing
  bootstrap preparation, invalid explicit paths, both modes, incomplete support, incompatible identities, environment
  sanitation, and paths with spaces. Windows launcher selection is simulated, not native Windows validation.
- `make -C l2 test-compiler TESTS=l2c_cleanup_policy_ice_test.py` passed the actual cleanup-policy ICE regression
  against a fresh native L1 installation, with `L1_CC`, `L2_CC`, and `L2_RUNTIME_CC` set to Clang.
- Root `make clean test` passed on macOS Intel across L0, L1, and L2 with explicit `L2_BOOTSTRAP_MODE=development`, the
  generated L1 launcher from the preceding level, and Clang for construction/target programs. Fresh installed-mode L2
  construction and source-path, filesystem-support, and language-identity checks also passed using a separate L2 build
  directory.
- L0 Stage 1: all 1,614 cases passed. L0 Stage 2 passed all 58 cases, and all eight examples passed. Runtime-build
  controls passed 13 cases. Distribution, installation/build layout, fallback, release-tag policy, and source-selector
  workflow checks all passed. `make -C l0 test-stage2-trace` passed all 34 cases with no leaks. These complete the
  constituent checks of `make -C l0 test-extended`, reusing the unchanged Stage 2 trace evidence.
- Shared checks passed: 37 ADR-validator tests, source/plan selectors and stage rejection, both owned L1 diagnostic
  contracts, five cross-editor checks, seven VS Code checks, all workflow/action YAML parsing, and the offline workspace
  lock check. No closed plans or historical attachments were modified.

### Outstanding verification and release prerequisites

Run Unified CI explicitly against the finalized tree with `platform=all`, `run_l2_ci=on`, and `l2_run_isolation=true`.
This must validate predecessor reuse and exhaustive L2 coverage across the native matrix, including both Linux isolation
phases. Previous hosted evidence and default-disabled automatic routing do not satisfy this gate. The earlier Ubuntu
builder license/notice omission and Windows extensionless installed-launcher invocation have local corrections awaiting
this hosted validation.

Fresh macOS ARM and Windows UCRT64 artifact build/checkout-free verification and hosted product acceptance remain
separate native gates. Keep this plan and the productization/release prerequisites open until all required fresh
evidence exists. Public pushes and workflow dispatches require separate fresh project maintainer confirmation. L1 0.1.0
release workflows, the seven-asset/four-platform contract with `make_latest=false`, and publication remain separate
future work.

## Exclusions and Follow-up

No new language feature, automatic backlog migration, L1 freeze, L2 productization, self-hosting, frozen-C bootstrap, or
profiles/composable-build implementation. Profiles remain intended for L1 first and subsequent L2 porting. Do not add
hosted snapshot/release/docs-build workflows, tags, or publication. Public pushes and CI dispatches retain separate
project maintainer authorization under [AGENTS.md](../../../AGENTS.md).
