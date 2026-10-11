# Refactor Plan

## Canonical L1/L2 compiler split and L1 delivery retargeting

- Date: 2026-10-10
- Status: Completed
- Closed: 2026-10-11
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
  - L1: Implemented; canonical compiler, delivery, documentation, and fresh four-platform artifact acceptance passed.
  - L2: Implemented; installed/development construction, exhaustive native CI, and both isolation phases passed.
  - Shared tooling: Implemented; focused regressions and explicit four-platform Unified CI passed.

## Summary

The refactor retained the L0-implemented canonical `l1c`, moved the former L1 Stage 2 into the independent
L1-implemented `l2c`, and retargeted completed L1 installation/distribution machinery. It established one canonical
compiler per level after L0 while preserving L0's two-stage bootstrap model and the transplanted compiler semantics.
Each successor owns its target support and has an explicit predecessor construction dependency.

L1 0.1.0 remains the intended future canonical L1 development-toolchain release. The split and fresh product acceptance
were prerequisites for implementing its hosted release workflows; both prerequisites completed on 2026-10-11.

## ADR Impact

- Decision: One canonical compiler per level after L0, with explicit upstream toolchain dependencies.
  - Scope: Dea-wide
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0022-single-compiler-level-lineage.md`
  - Rationale: The accepted lineage preserves L0's bootstrap model and defines canonical successor ownership.
- Decision: Canonical L1 delivery and matching stage-free offline references retain productization safeguards.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md`
  - Rationale: Canonical construction, artifact identity, and fresh native acceptance satisfy the recorded delivery
    boundary.
- Decision: L2 owns its target inputs and builds through an explicit installed or development L1 toolchain.
  - Scope: L2
  - Disposition: Amend ADR
  - ADR: `l2/docs/decisions/0001-independent-canonical-compiler.md`
  - Rationale: Explicit same-run development reuse preserves independent L2 target ownership and installed isolation.

## Implementation

1. Flattened canonical compiler paths to `l1/compiler/{src,support,tests,scripts}` and the corresponding L2 paths.
   Retained L1 `.l0` and L2 `.l1` implementation sources. Removed intra-L1/L2 stage selection, parity, and triple
   bootstrap while preserving L0's stage model.
2. Retargeted L1 installation to private canonical construction with an installed build-info overlay. Preserved
   semantic-input verification, prefix ownership/recovery, immutable inputs, writable caches, optional verified install
   docs, and mandatory verified distribution docs. Stage-free schema-2 installation, documentation, distribution, and
   acceptance identities use fresh prefixes and reject obsolete schema-1 stage artifacts.
3. Physically copied target support into L2, including its stdlib, runtime, and native support. Required explicit
   `L2_BOOTSTRAP_L1C`, installed by default with optional `L2_BOOTSTRAP_MODE=development` for a generated development
   toolchain. Retargeted source/interface suffixes to `.l2`/`.l2m`, compiler identity to `l2c`, and driver diagnostics
   to equivalent `L2C-xxxx` codes. Preserved extensionless logical targets, ABI, algorithms, and shared diagnostics.
4. Retargeted live docs, applicable open plans, skills, selectors, workspace membership, editor identities, shared
   compiler contracts, and existing CI. Preserved earlier closed plans, attachments, and historical acceptance as
   historical records. Kept L1 feature plans owned by L1 pending individual review.
5. Reused explicit same-run L0/L1 predecessor outputs in Unified CI, preparing a missing development bootstrap once and
   rejecting invalid handoffs. Retained standalone L2's installed bootstrap and made Docker isolation independently
   opt-in. Central L2 routing defaults off, with `default`/`on`/`off` manual overrides; an enabled default selects
   L2/shared-tooling changes.

## Diagnostic Planning

The refactor copied established L1 compiler/driver numeric identities into the L2C family with the same meanings. This
mechanical level namespace required no new diagnostic area, unrelated renumbering, or speculative code-block
reservation. Emitted L2 codes were reconciled with
[docs/specs/compiler/diagnostic-code-catalog.md](../../../../docs/specs/compiler/diagnostic-code-catalog.md); shared
families retained their existing applicability.

## Verification Criteria

Acceptance required the following compiler, product, independence, and repository gates:

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
- L2 source discovery and focused test routing, preserved L0 stage selectors, portable path checks, ADR Impact,
  whitespace, and root pre-commit. Simulated Windows paths do not replace native Windows validation.

## Findings and Decisions

- Canonical authority and physical ownership are separate from implementation-language reuse. Each level owns its
  compiler, target stdlib, runtime, native support, tests, and build outputs. The L2 transplant retained its proven
  semantics and implementation ABI helpers without introducing a second L2 implementation or a perpetual parity gate.
- L1 delivery requires construction for installed operation. Installation uses two private L0 constructions, including
  the installed-mode overlay, records the actual construction command and runtime controls, and verifies the installed
  semantic graph against immutable captured inputs. Relocation and exact artifact identity remain acceptance boundaries;
  historical Stage 2 acceptance cannot establish them for the new canonical product.
- L2 construction requires a complete compatible predecessor. Explicit development mode accepts canonical L1 identity,
  native binary, public headers, semantic interfaces, and a host-compatible launcher. Bootstrap environments discard
  unrelated input overrides and keep upstream writable preparation caches under L2's build directory. L2 target
  operations use L2-owned inputs; installed/development selection does not permit implicit sibling or PATH fallback.
- Source identity and logical module resolution remain distinct. Existing suffixless output files preserve logical
  module resolution; explicit paths and existing suffixed files reject wrong source extensions before module fallback,
  including files shadowing dotted-module names. `.l2m` consumers remain usable after provider source removal.
- Coordinated CI reuse is limited to validated predecessor outputs within one checkout, runner, and invocation.
  Intentional construction fixtures retain their builds; standalone L2 CI and Docker isolation retain installed L1
  construction, including a separate Bookworm bootstrap for isolation. Automatic routing and default manual selection
  share the initially disabled L2 setting; explicit manual `off` always suppresses L2.
- Compiler correctness, isolated L2 ownership, and delivered L1 artifact acceptance require distinct evidence. Matching
  verified offline HTML and full PDF are mandatory for distributions and optional for direct installs. Introducing L2
  neither freezes L1 nor transfers its feature backlog automatically.

## Verification Evidence

The following records summarize validation completed for the refactor. Local native checks used macOS Intel with Python
3.14 and Apple Clang 17; Linux checks used Debian Bookworm with GCC 12. Commands identify reproducible gates or their
constituent checks. Local aggregate coverage combined successful constituents, retaining unaffected results after
focused corrections; final hosted acceptance exercised the complete required gates.

### Local compiler correctness

- `make -C l1 build check-examples` passed the canonical build, all 23 bundled semantic interfaces, and all four
  examples. L1 `compiler/scripts/run_tests.py --include-ci-only` passed 86 runner cases; the remaining
  preparation-identity case passed through its direct native invocation.
- L1 `compiler/scripts/run_trace_tests.py` passed all 47 default cases and both `--children` fixtures with no leaked
  objects or strings. `make -C l1 test-env` passed. Together with normal/CI-only cases and tooling/product fixtures,
  these covered the constituents of `make -C l1 test-ci`.
- L0 Stage 1 passed 1,614 cases; L0 Stage 2 passed 58 cases and all eight examples. Runtime-build controls passed 13
  cases. Distribution, installation/build layout, fallback, release-tag policy, and source-selector workflow checks
  passed. The 34 leak-free cases from `make -C l0 test-stage2-trace` completed constituent coverage of
  `make -C l0 test-extended`.

### Local L1 delivery and documentation

- Documentation/productization fixtures passed 313 cases, with 14 native-Windows-only skips. Final installed semantic
  graph and payload/install regressions passed 57 cases; two real private-overlay/startup checks passed. A fresh
  `make -C l1 install PREFIX=<new-prefix>` passed both private constructions and installed graph verification with
  recorded `-O2` L0 native construction flags.
- Strict canonical HTML and full indexed PDF generation passed. The schema-2, stage-free `dev` bundle
  `dea_l1_autodocs.tar.gz` contained the complete references and `dea_l1_api_reference.pdf`. Required LaTeX/reference
  and index passes completed; the 1,410-page PDF had no undefined references. Both local native artifact builds consumed
  the same verified documentation bytes.
- macOS Intel exact-artifact acceptance used separate build and verification phases. The transported harness ran under
  `sandbox-exec` with failed-read probes for both checkouts and both installed bootstrap prefixes, and networking
  denied. It passed relocation with spaces, read-only inputs, semantic work without C tools, cold/warm preparation,
  compilation, linking, execution, and profile smoke.
- Linux x86_64 exact-artifact acceptance used separate Bookworm builder/verifier containers with GCC 12.2. The builder
  ran `productization_acceptance.py --phase build --directory <evidence>`; a fresh Python 3.14.8 verifier ran the
  transported harness with `--phase verify`, networking disabled, and only evidence/harness mounted. No checkout, L0, or
  L1 bootstrap was present. Native, relocation, semantic-only, standalone link, cold/warm preparation, build/run, and
  runtime-configuration smoke checks passed.

### Local L2 construction and independence

- Installed-bootstrap L2 `compiler/scripts/run_tests.py` passed all 66 normal and five CI-only cases.
  `compiler/scripts/run_trace_tests.py` passed all 47 default cases and both `--children` fixtures without leaks. The
  canonical build verified all 23 semantic interfaces; six tooling checks and all four examples passed. These covered
  the constituents of `make -C l2 test-ci` without relaxing timeout bounds.
- Reused-development L1 construction passed all 71 L2 normal/CI-only cases, 17 local trace cases, and both child trace
  fixtures. The full development-bootstrap trace gate was subsequently covered by the final hosted acceptance below.
- `L2_ISOLATION_BOOTSTRAP_PREFIX=<installed-linux-l1> make -C l2 test-isolation` passed with a fresh Bookworm prefix
  built using `docker build -f l1/Dockerfile` and container `make install`. Its construction image contained only L2,
  installed L1, and explicitly enumerated root tooling. Source-path, filesystem-support, language-identity, and both
  construction/operation isolation checks passed; the final hosted gate repeated both phases.
- `make -C l2 test-compiler TESTS=l2c_cleanup_policy_ice_test.py` passed against a fresh native L1 installation with
  `L1_CC`, `L2_CC`, and `L2_RUNTIME_CC` set to Clang.

### Local shared tooling and integration

- Focused CI/bootstrap checks passed 67 cases: 40 routing/delegate and 27 L2 construction cases. Coverage included
  central defaults, all manual overrides, shared/level/unrelated paths, unavailable diffs, same-run reuse, missing
  bootstrap preparation, invalid explicit paths, both modes, incomplete support, incompatible identities, environment
  sanitation, and paths with spaces.
- Canonical L1 build/tooling regressions passed nine cases; minimal Wine-context regressions passed six. Portable path
  checks covered POSIX, Windows, mixed separators, spaces, and distinct-path rejection. These and Windows launcher
  selection checks simulated Windows behavior; native Windows acceptance is recorded separately below.
- Root `make clean test` passed across L0, L1, and L2 on macOS Intel with explicit `L2_BOOTSTRAP_MODE=development`, the
  generated L1 launcher from the preceding level, and Clang for construction/target programs. Fresh installed-mode L2
  construction and source-path, filesystem-support, and language-identity checks also passed in a separate L2 build
  directory.
- Shared checks passed: 37 ADR-validator cases, source/plan selectors and stage rejection, both owned L1 diagnostic
  contracts, five cross-editor checks, seven VS Code checks, all workflow/action YAML parsing, and the offline workspace
  lock check.

### Final hosted acceptance (2026-10-11)

Explicitly dispatched Unified CI and fresh L1 Productization Acceptance passed against the same implementation tree on
Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64.

- Unified CI selected `platform=all`, `run_l2_ci=on`, and `l2_run_isolation=true`. L0 `test-extended` and L1/L2
  `test-ci` passed on all four platforms, including normal, CI-only, trace, child-fixture, tooling, and product
  fixtures. The coordinated development handoffs and native Windows launchers passed; documentation and ADR policy gates
  passed.
- The Linux `make -C l2 test-isolation` gate passed both phases with a fresh installed Bookworm L1 bootstrap.
  Construction denied access to sibling trees; operation omitted L0, L1, Python, and Make, cleared bootstrap/target
  caches, cold-prepared L2-owned stdlib/runtime, separately compiled and linked `.l2m` consumers after removing provider
  source, executed the result, and rejected `.l1` target input with `L2C-0011`.
- L1 Productization Acceptance used `package_version=dev`. Strict canonical HTML and the full indexed PDF passed, then
  all four native artifact builds and fresh-runner verifications passed. Verifiers consumed the exact transported
  archive/result/harness evidence without checkout or bootstrap artifacts and checked relocation, immutable inputs,
  semantic-only use, cold/warm native preparation, compilation, linking, execution, and runtime configuration.

## Outcome

The canonical compiler split, L1 delivery retargeting, coordinated CI reuse, and independent L2 target ownership are
complete. Final hosted validation satisfied the exhaustive native matrix, full development-bootstrap trace coverage,
both Linux isolation phases, and fresh canonical L1 artifact acceptance. No verification gate remains open for this
refactor. The compiler split and artifact-acceptance prerequisites for implementing the L1 release workflows are met.

## Exclusions and Follow-up

L1 snapshot/release workflow implementation and publication remain separate work under
[work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md](../../tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md).
The intended L1 0.1.0 development-toolchain release retains the seven-asset/four-platform contract and
`make_latest=false`.

New language features, automatic backlog migration, an L1 freeze, L2 productization, self-hosting, frozen-C bootstrap,
and profiles/composable-build implementation remain outside this refactor. Profiles remain intended for L1 first and
subsequent L2 porting. Hosted snapshot/release/docs-build workflows, release tags, and publication belong to separate
work. Public pushes, CI dispatches, tags, and publication retain their separate project maintainer authorization gates
under [AGENTS.md](../../../../AGENTS.md).
