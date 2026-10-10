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
  - L2: Implemented; exhaustive compiler and two-phase container isolation gates passed
  - Shared tooling: Implemented; focused regressions passed

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
- Decision: L2 owns its target inputs and builds only through an installed L1 toolchain.
  - Scope: L2
  - Disposition: Covered by ADR
  - ADR: `l2/docs/decisions/0001-independent-canonical-compiler.md`
  - Rationale: Record the initial independent level boundary without a duplicate implementation plan.

## Implementation

1. Flatten canonical compiler paths to `l1/compiler/{src,support,tests,scripts}` and the corresponding L2 paths. Keep L1
   `.l0` and L2 `.l1` implementation sources. Remove L1 intra-level stage selection, parity, and triple bootstrap.
2. Build the installed L1 artifact in private scratch with an installed overlay; preserve semantic-input verification,
   prefix ownership/recovery, immutable inputs, writable caches, optional install docs and mandatory verified dist docs.
   New install/docs identities use stage-free schema 2 and fresh prefixes; reject obsolete schema-1 stage artifacts.
3. Physically copy target support into L2. Require explicit installed `L2_BOOTSTRAP_L1C`; use `.l2`/`.l2m`, `l2c`, and
   equivalent `L2C-xxxx` codes. Preserve extensionless logical targets, ABI, algorithms, and shared diagnostics.
4. Retarget live docs, applicable open plans, skills, selectors, workspace membership, editor identities, and existing
   CI. Preserve closed plans, attachments, and historical acceptance. Keep L1 features owned by L1 pending individual
   review.

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
- L2 source discovery and focused test routing, preserved L0 stage selectors, portable path tests, ADR Impact,
  whitespace, and root pre-commit. Simulated Windows paths do not replace native Windows validation.

## Evidence and Remaining Work

### Implementation

Both levels now have canonical source, support, launcher, build, test, and target-input ownership. L1 installation uses
two private L0 constructions, including the installed-mode overlay, records the actual construction command and runtime
controls, and checks the installed semantic graph against immutable captured inputs. Schema-2 inventory, documentation,
distribution, and acceptance identities reject former stage artifacts. L2 requires an explicit installed L1 bootstrap
and preserves implementation ABI helpers while separating `.l2` programs and `.l2m` interfaces.

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
- L2 `compiler/scripts/run_tests.py`: all 66 normal cases and all five CI-only cases passed. Focused reruns cover the
  final source-path correction, migrated fixture expectations, native support fixtures, and construction/preparation
  checks; unchanged AST, type, and backend results remain applicable. No timeout bounds were relaxed. Existing
  suffixless output files preserve logical module resolution; explicit paths and existing suffixed files reject wrong
  source extensions before module fallback, including shadowing dotted-module names.
- L2 `compiler/scripts/run_trace_tests.py`: all 47 default cases and both `--children` fixtures passed with no leaks.
  The final canonical build verified all 23 semantic interfaces; six tooling tests and all four examples passed. These
  complete the constituent checks of `make -C l2 test-ci`.
- `L2_ISOLATION_BOOTSTRAP_PREFIX=<installed-linux-l1> make -C l2 test-isolation` passed. The fresh Bookworm build
  contains only L2, the installed L1 prefix, and explicitly enumerated root tooling; its tooling and source-path,
  filesystem-support, and language-identity checks passed. A separate operation image omits L1, L0, Python, and Make,
  clears bootstrap/target caches, cold-prepares L2-owned stdlib/runtime, produces and consumes `.l2m` after removing the
  provider source, links/runs the result, and rejects a `.l1` input with `L2C-0011`.
- L0 Stage 1: 1,601 cases passed in the broad run; all 14 trace-checker tests passed after correcting the three failures
  caused by the moved L1 checker path. L0 Stage 2 passed all 58 cases, and all eight examples passed. Runtime-build
  controls passed 13 cases. Distribution, installation/build layout, fallback, release-tag policy, and source-selector
  workflow checks all passed. `make -C l0 test-stage2-trace` passed all 34 cases with no leaks. These complete the
  constituent checks of `make -C l0 test-extended`, reusing the unchanged successful Stage 1 cases after the focused
  trace-checker path correction.
- Shared checks passed: 37 ADR-validator tests, source/plan selectors and stage rejection, both owned L1 diagnostic
  contracts, five cross-editor checks, seven VS Code checks, all workflow/action YAML parsing, and the offline workspace
  lock check. No closed plans or historical attachments were modified.

### Outstanding verification and release prerequisites

Fresh macOS ARM and Windows UCRT64 artifact build/checkout-free verification require their native environments. Hosted
canonical compiler and product acceptance remain unexecuted; no workflow dispatch is authorized by this implementation.
Keep this plan and the productization/release prerequisites open until all required fresh evidence exists. L1 0.1.0
release workflows, the seven-asset/four-platform contract with `make_latest=false`, and publication remain separate
future work.

## Exclusions and Follow-up

No new language feature, automatic backlog migration, L1 freeze, L2 productization, self-hosting, frozen-C bootstrap, or
profiles/composable-build implementation. Profiles remain intended for L1 first and subsequent L2 porting. Do not add
hosted snapshot/release/docs-build workflows, tags, pushes, dispatches, or publication. Those actions retain separate
project-maintainer authorization under [AGENTS.md](../../../AGENTS.md).
