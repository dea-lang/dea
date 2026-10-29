# Dea Project Status

Version: 2026-10-29

This document summarizes the current status of the Dea project at the monorepo level.

The repository contains the stable Dea/L0 release line, the Dea/L1 development release line, and the independent L2
development level. L0 2.1.1 remains the stable toolchain. L1 0.1.0 is the current published development release, with
one canonical compiler implemented in L0. L2 has one compiler implemented in L1. Artifact and hosted release-workflow
acceptance are complete for the published L1 baseline; newer source-tree changes require their own release acceptance.

## Scope and Canonical References

Use this file as the Dea-wide status snapshot. For more specific details, use:

- [MONOREPO.md](../MONOREPO.md) for monorepo layout and root workflow.
- [work/plans/](../work/plans/) for active and closed Dea-wide plans.
- [l0/docs/project-status.md](../l0/docs/project-status.md) for the current L0 implementation and release status.
- [l0/docs/releases/2.0.0.md](../l0/docs/releases/2.0.0.md) for L0 2.0.0 changes and migration guidance.
- [l0/docs/releases/2.1.1.md](../l0/docs/releases/2.1.1.md) for the current L0 2.1.1 release and compatibility guidance.
- [l1/docs/releases/0.1.0.md](../l1/docs/releases/0.1.0.md) for the current L1 development release and compatibility
  limitations.
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

L0 is the current stable release line.

Its repository status today is:

- self-hosted through Stage 2,
- its own public CLI and user documentation surface,
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

L1 0.1.0 was published on 2026-10-13 as the canonical development toolchain, with standalone platform archives and
matching offline documentation. It does not promise stable language, module-interface, or binary compatibility. See
[the published release](https://github.com/dea-lang/dea/releases/tag/l1-v0.1.0).

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
- enforcing borrowed-slice backing lifetimes through aliases, control flow, and descriptor stores,
- supporting caller-owned explicit native profiles, structured OS/I/O errors, filesystem mutations and owned directory
  traversal, and `long` time seconds with monotonic sleep and deadlines,
- supporting private installed-compiler construction, verified bundled semantic inputs, stage-free schema-2 inventory
  and offline HTML/PDF documentation, local distribution archives, and reusable archive smoke validation.

Fresh canonical L1 artifact acceptance passed on Linux x86_64, macOS Intel/ARM, and Windows UCRT64 on 2026-10-11,
including verification without checkout or bootstrap compilers. Historical Stage 2 acceptance is retained separately;
compiler CI alone does not establish artifact or publication readiness.

Unified CI runs the `.github/actions/l1-ci` delegate for L1 changes and relevant predecessor/shared construction
changes. Its `make test-ci` gate covers canonical normal tests, CI-only cases, environment/bootstrap integration,
ARC/memory traces, child fixtures, and examples on Linux, macOS, and Windows. Shared repository checks run separately.
The standalone `l1-ci.yml` workflow retains manual platform, compiler, and Make-target selection.

L1 stabilization has a finite compiler/tool capability target. Dynamic byte buffers, file handles, secure entropy and
temporary objects, shell-free processes and pipes, typed string formatting, and semantic dependency discovery remain
planned. Acceptance programs, the capability audit, documentation, and fresh artifact acceptance complete that target.
Generic streams, networking, JSON, file watching, concurrency, owned slices, and broader language expressiveness belong
to deferred L2 work. See [l1/docs/roadmap.md](../l1/docs/roadmap.md).

L1 snapshot, tag-triggered release, and reusable documentation workflows are implemented with local syntax and policy
validation. They retain exact source/version/docs handoff, four fresh verification jobs, seven assets, and
`make_latest=false`. Hosted snapshot and versioned-release acceptance passed on 2026-10-12. Versioned releases now
require curated notes at the selected source revision and append generated commit history after that content; this
composition has focused local coverage. See [l1/docs/releases/README.md](../l1/docs/releases/README.md) and
[work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md](../work/plans/tools/closed/2026-05-12-l1-gha-release-snapshot-workflows-noref.md).
L1 0.1.0 is published; subsequent tags, dispatches, and publication actions remain separately gated. L0 remains the
stable release line. The workflow plan is closed, with its release and curated-note policies recorded in
[docs/decisions/0023-l1-release-workflow-policy.md](decisions/0023-l1-release-workflow-policy.md).

### Dea/L2

L2 starts from the former L1 Stage 2 and owns physical copies of its implementation support, target stdlib, and runtime.
Its canonical `l2c` accepts `.l2` programs and emits `.l2m` interfaces with the semantics inherited at the split.
Subsequent L1 improvements do not automatically change L2. Sustained L2 feature work follows a selected stable L1
baseline and explicit activation; the split creates no perpetual cross-level parity gate.

Building L2 requires explicit `L2_BOOTSTRAP_L1C`, using an installed canonical L1 toolchain by default or a generated
development toolchain with `L2_BOOTSTRAP_MODE=development`. L1 compiles the `.l1` implementation and implementation
tests; `l2c` handles `.l2` target fixtures and examples. Ordinary L2 compilation and native preparation use only
L2-owned inputs. L2 CI provides four-platform native validation and a Linux isolation gate that excludes sibling
checkouts during construction and excludes the bootstrap compiler during operation. Unified CI uses the central
`L2_CI_DEFAULT_ENABLED` setting, currently false, for pushes and pull requests. Manual `run_l2_ci` selection accepts
`default`, `on`, or `off`. When enabled, L2 runs for its own changes and affected predecessor/shared construction
inputs. Linux isolation is a separate opt-in gate. The standalone `L2 CI` workflow remains available for manual runs. L2
installation, productization, and hosted releases are outside this split.

## Release Model

The Dea monorepo uses separate release lines for each language level:

- L0 releases use `l0-v*` and `l0-snapshot-*`.
- L1 development releases use `l1-v*` and `l1-snapshot-*`.

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
- root `scripts/tests/` for repository checks, run once by root test aggregates and separately in Unified CI,
- root `scripts/dea_tooling/` for shared launcher/bootstrap helpers.

This shared layer is intentionally narrow. Most compiler, language, runtime, and user-facing documentation remains owned
by the relevant level subtree.

## Current Project Posture

- Dea/L0 `2.1.1` is the stable release line. User-visible fixes and future compatibility changes remain governed by L0
  semantic versioning and Stage 1/Stage 2 parity.
- Dea/L1 follows the finite stabilization target in [l1/docs/roadmap.md](../l1/docs/roadmap.md). New capabilities
  require an explicit scope amendment; defects in the selected contracts remain stabilization work.
- Dea/L2 retains its independent compiler and maintenance workflows. Sustained feature development remains deferred as
  described in [l2/docs/roadmap.md](../l2/docs/roadmap.md).
