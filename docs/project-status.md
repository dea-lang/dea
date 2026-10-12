# Dea Project Status

Version: 2026-10-12

This document summarizes the current status of the Dea project at the monorepo level.

The repository contains one active release line, Dea/L0, and independent development levels L1 and L2. L0 remains the
current stable toolchain. L1 has one compiler implemented in L0; L2 has one compiler implemented in L1. L1 0.1.0 is the
intended future canonical L1 development-toolchain release. Fresh canonical artifact acceptance and hosted
snapshot/versioned-release acceptance are complete; L1 publication remains pending.

## Scope and Canonical References

Use this file as the Dea-wide status snapshot. For more specific details, use:

- [MONOREPO.md](../MONOREPO.md) for monorepo layout and root workflow.
- [work/plans/](../work/plans/) for active and closed Dea-wide plans.
- [l0/docs/project-status.md](../l0/docs/project-status.md) for the current L0 implementation and release status.
- [l0/docs/releases/2.0.0.md](../l0/docs/releases/2.0.0.md) for L0 2.0.0 changes and migration guidance.
- [l0/docs/releases/2.1.1.md](../l0/docs/releases/2.1.1.md) for the current L0 2.1.1 release and compatibility guidance.
- [l1/docs/project-status.md](../l1/docs/project-status.md) for the current L1 implementation and delivery status.
- [l1/README.md](../l1/README.md) for the current L1 development and installation entry point.
- [l2/docs/project-status.md](../l2/docs/project-status.md) for independent L2 construction and validation.
- [docs/specs/compiler/cli-contract.md](specs/compiler/cli-contract.md) for the shared compiler CLI contract.

## Current Repository Shape

The monorepo currently contains:

- `l0/` as the implemented language, compiler, runtime, docs, examples, and release subtree.
- `l1/` as the L0-implemented canonical L1 toolchain subtree.
- `l2/` as the L1-implemented canonical L2 toolchain subtree.
- `editors/` for shared Dea/L0, Dea/L1, and Dea/L2 syntax highlighting, fallback modes, navigation indexes, the
  in-repository Tree-sitter grammar, fixtures, and focused validation.
- `scripts/` for monorepo-owned automation and shared helper modules.
- `docs/` for Dea-wide and monorepo-wide stable documentation.
- `work/` for Dea-wide and monorepo-wide plans/proposals.
- `tools/` for vendored third-party dependencies.

L1 and L2 each own `compiler/src/`, `compiler/support/`, `compiler/tests/`, and `compiler/scripts/`. Their target
stdlibs and runtimes live under each level's `compiler/shared/` tree. L1 compiler implementation sources remain `.l0`;
L2 compiler implementation sources remain `.l1`. L2 program sources use `.l2` and interfaces `.l2m`.

## Language-Level Status

### Dea/L0

L0 is the current release-bearing level.

Its repository status today is:

- self-hosted through Stage 2,
- the canonical public CLI and user documentation surface,
- validated through the existing L0 test, bootstrap, packaging, and docs workflows,
- versioned under the `l0-v*` / `l0-snapshot-*` release namespace,
- stable at released version `2.1.1`, retaining its namespaced CLI aliases, wildcard-only `case` defaults, and checked
  runtime pointer validation modes.

L0 2.1.1 fixes ARC cleanup for comparison temporaries in both compiler stages and improves AddressSanitizer test
validation. It preserves the L0 2.1.0 language and public interfaces.

L0 2.1.0 adds the installed public C runtime header, vector self-alias safety, semantic optional hashes,
sanitizer-visible quarantine lifetimes, and cohesive compiler modules in both stages. Python 3.14 remains the Stage 1
minimum. The existing L0 language and CLI contract is unchanged from 2.0.0.

### Dea/L1

L1 supports canonical development and standalone installation/distribution. Publication remains pending.

Its repository status today is:

- maintained as a separate language subtree under `l1/`,
- constructed through an explicit L0 compiler, with one canonical repo-local `l1c` and no stage selection,
- validated through normal suites, environment/bootstrap integration, target examples, and ARC/memory trace checks,
- using `.l0` for the compiler implementation and `.l1` for the L1 stdlib, examples, and language fixtures,
- carrying implemented post-L0 language work such as wider numeric types, real literals, bitwise operators, top-level
  `const` with checked scalar constant expressions, string value comparisons, nullable/pointer identity equality, named
  arguments, the `is(...)` enum tag intrinsic, function pointer and L1-defined variadic function types, `unsafe func`,
  raw-pointer indexing inside unsafe functions, fixed-size arrays, non-owning slices with `len`/`slice`, and
  single-statement `while` / `for` / `match` bodies,
- emitting and verifying deterministic textual `.l1m` module interfaces that are authoritative for interface-backed
  imports and standalone-link semantics,
- supporting per-module `--gen`, compile-only `.o + .l1m` publication, verified standalone `--link`, and
  multi-compilation-unit `--build` / `--run` across mixed source/interface graphs, with encounter-ordered external
  libraries, search paths, rpaths, and raw host-driver arguments in every link-involving mode,
- shipping bootstrap-oriented stdlib growth such as `std.real`, wider integer I/O/math helpers, and the new `std.types`
  value-type helper surface,
- supporting private installed-compiler construction, verified bundled semantic inputs, stage-free schema-2 inventory
  and offline HTML/PDF documentation, local distribution archives, and reusable archive smoke validation.

Fresh canonical L1 artifact acceptance passed on Linux x86_64, macOS Intel/ARM, and Windows UCRT64 on 2026-10-11,
including verification without checkout or bootstrap compilers. Historical Stage 2 acceptance is retained separately;
compiler CI alone does not establish artifact or publication readiness.

The unified `ci.yml` routes L1 changes through `l1-ci.yml`. Its `make test-ci` gate covers canonical normal tests,
CI-only cases, environment/bootstrap integration, ARC/memory traces, child fixtures, and examples on Linux, macOS, and
Windows. Manual platform, compiler, and Make-target selection remain available.

L1 snapshot, tag-triggered release, and reusable documentation workflows are implemented with local syntax and policy
validation. They retain exact source/version/docs handoff, four fresh verification jobs, seven assets, and
`make_latest=false`. Hosted snapshot and versioned-release acceptance passed on 2026-10-12. Versioned releases now
require curated notes at the selected source revision and append generated commit history after that content; this
composition has focused local coverage. See [l1/docs/releases/README.md](../l1/docs/releases/README.md) and
[work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md](../work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md).
Activation, namespace checks, tags, dispatches, and publication remain separately gated; L0 is still the release line.
The workflow plan is closed, with its release and curated-note policies recorded in
[docs/decisions/0023-l1-release-workflow-policy.md](decisions/0023-l1-release-workflow-policy.md).

### Dea/L2

L2 starts from the former L1 Stage 2 and owns physical copies of its implementation support, target stdlib, and runtime.
Its canonical `l2c` accepts `.l2` programs and emits `.l2m` interfaces with the inherited language semantics. The split
adds no language feature and creates no perpetual cross-level parity gate.

Building L2 requires `L2_BOOTSTRAP_L1C` pointing to an installed canonical L1 toolchain. L1 compiles the `.l1`
implementation and implementation tests; `l2c` handles `.l2` target fixtures and examples. Ordinary L2 compilation and
native preparation use only L2-owned inputs. L2 CI provides four-platform native validation and a Linux isolation gate
that excludes sibling checkouts during construction and excludes the bootstrap compiler during operation. Unified CI
skips L2 on pushes and pull requests. Manual Unified CI runs expose a `Run L2 CI` boolean flag (`run_l2_ci`), which
defaults to false; enable it to include L2 validation. The standalone `L2 CI` workflow remains available for manual
runs. L2 installation, productization, and hosted releases are outside this split.

## Release Model

The Dea monorepo uses separate release lines for each language level:

- L0 releases use `l0-v*` and `l0-snapshot-*`.
- Future L1 releases will use `l1-v*` and `l1-snapshot-*`.

L1 construction consumes L0 as an upstream compiler toolchain; installed use is independent of that bootstrap chain.
Local development defaults to the repo-local L0 Stage 2 build, while reproducible CI/release-oriented bootstrap flows
should use an explicit upstream L0 compiler path.

## Shared Monorepo State

The monorepo now has a small but real shared top-level layer:

- root `work/plans/` for Dea-wide planning,
- root `docs/` for Dea-wide status and reference documents,
- root `editors/` for distinct L0/L1/L2 editor identities backed by shared TextMate, Vim, Emacs, Universal Ctags, and
  the in-repository `editors/tree-sitter-dea/` L1-superset grammar package,
- root `AGENTS.md` for monorepo-wide workflow policy,
- root `Makefile` for shared `help`, `venv`, `test`, `test-extended`, `clean`, and `clean-all`,
- root `scripts/dea_tooling/` for shared launcher/bootstrap helpers.

This shared layer is intentionally narrow. Most compiler, language, runtime, and user-facing documentation remains owned
by the relevant level subtree.

## Current Project Posture

- Dea/L0 `2.1.1` is the stable release line. User-visible fixes and future compatibility changes remain governed by L0
  semantic versioning and Stage 1/Stage 2 parity.
- Dea/L1 remains open to feature development. Its current direction is maintained in
  [l1/docs/roadmap.md](../l1/docs/roadmap.md); profiles/composable builds remain intended for L1 first and later L2
  porting, with no implementation advanced by the split.
- Dea/L2 is independently maintained under the canonical compiler lineage recorded in
  [docs/decisions/0022-single-compiler-level-lineage.md](decisions/0022-single-compiler-level-lineage.md).
