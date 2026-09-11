# Tool Plan

## Define the first L1 install/dist/bootstrap-product workflow

- Date: 2026-04-02
- Last reviewed: 2026-09-11
- Status: Draft
- Title: Define the first L1 install/dist/bootstrap-product workflow
- Kind: Tooling
- Severity: Medium
- Stage: L1
- Subsystem: Build workflow / install layout / distribution packaging / bootstrap docs
- Modules:
  - `l1/Makefile`
  - `l1/scripts/`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/source_paths.l0`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/compile_driver/compile.l0`
  - `l1/compiler/stage1_l0/src/link_driver/toolchain.l0`
  - `l1/compiler/shared/`
  - `l1/docs/`
  - `scripts/dea_tooling/`
- Test modules:
  - `l1/tests/test_bootstrap_productization.py` (new install/dist regression suite)
  - `l1/tests/test_env_stackability.py`
  - `l1/compiler/stage1_l0/tests/compiler_runtime_build_env_test.py`
  - `l1/compiler/stage1_l0/tests/runtime_build_config_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
- Related:
  - `work/plans/refactors/closed/2026-04-02-l1-bootstrap-scaffold-noref.md`
  - [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]
  - [work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md][release-workflows]
  - [MONOREPO.md][monorepo]

## Summary

The `l1/` subtree currently supports repo-local bootstrap development through `make build-stage1`, shell activation via
`build/dea/bin/l1-env.sh`, and `make test-stage1`. This plan adds a relocatable install-prefix workflow and a curated
distribution archive for that Stage 1 toolchain, with the semantic interfaces and stdlib/runtime rebuild inputs defined
below.

This plan defines that missing productization layer without changing the current scope claim: L1 remains a bootstrap
toolchain seed, not a release-bearing product. The goal is to make the Stage 1 compiler installable, runnable from an
installed prefix, and packageable as a curated bootstrap archive with explicit upstream-compiler provenance.

## Current State

1. `l1/` is bootstrap-only.
2. `make build-stage1` builds a repo-local `l1c-stage1` wrapper and native binary under `build/dea/bin/`, or the
   explicitly selected repo-local `L1_BUILD_DIR`.
3. `make test-stage1` validates the copied Stage 1 implementation tests using the upstream L0 compiler.
4. There is no `make install`, `make list-installed`, `make dist`, or release-artifact layout for L1.
5. Bootstrap correctness depends on the explicit upstream compiler contract:
   - local development defaults to `../l0/build/dea/bin/l0c-stage2`
   - reproducible overrides must use `L1_BOOTSTRAP_L0C`
   - the workflow must not rely on whichever `l0c` happens to be on `PATH`
6. Bootstrap supplies public headers and verified bundled semantic interfaces independently of native program runtime.
   `make runtime` remains the developer archive/raw-object workflow; stdlib sources live under
   `compiler/shared/l1/stdlib/`.
7. Shared tooling already has separate repo and prefix launcher/environment renderers. L1 currently uses the repo
   renderers; its build-layout validator deliberately rejects output directories outside the L1 source tree.
8. Automatic stdlib/runtime preparation and standalone-link discovery are implemented by the related preparation plan.
   Read-only installed fixtures contain semantic interfaces and rebuild inputs with no native profile requirement.

## Defaults Chosen

1. L1 remains bootstrap-only after this work; productization here does not imply stable-release readiness.
2. The default local upstream compiler remains repo-local `../l0/build/dea/bin/l0c-stage2`.
3. `L1_BOOTSTRAP_L0C` selects the compiler used to build the Stage 1 executable during install/dist preparation. The
   installed native `l1c` does not invoke L0, Python, `uv`, or Make to run or prepare bundled support. Native output and
   native cache preparation still require a compatible host C compiler/linker and the preparation service's host tools.
4. Ship Stage 1 explicitly, even if Stage 2 lands before implementation. Stage 2 packaging is a later scope change; this
   plan does not silently follow the active repo-local `l1c` alias.
5. Reuse shared prefix launcher/env rendering, bootstrap selection, and narrow file/archive helpers where applicable.
   Keep L1 payload selection and build policy under `l1/scripts/`; do not import the L0 distribution builder wholesale.
6. The first payload contains the compiler, verified bundled interfaces, public headers, stdlib/runtime rebuild sources,
   internal preparation headers and installation metadata. Native configurations are derived in the selected local cache
   on demand; no native stdlib objects or runtime archives are required in the installation.

## Dependency and Packaging Handoff

The install layout and packaging helpers can build on the completed preparation service and managed standalone-link
integration from
[l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]. That work
validated installed lookup against read-only fixtures independently of this installer, so there is no dependency cycle.

The preparation plan owns semantic/native identities, completion manifests, native compilation, per-key coordination,
reuse eligibility and local-cache selection. This plan owns the installed prefix, launchers, shipped input inventory,
archive construction and relocation. Copy the verified bootstrap semantic set exactly with its compiler-owned rebuild
inputs. Installation metadata identifies those shipped inputs, including `D` if supplied, without an installed native
key, completed native-profile export/import format, or installed-profile lookup. Packaging must not introduce a second
identity algorithm or advertise copied native cache state as portable.

## Installed Layout

`PREFIX` is required. Resolve a relative prefix against the L1 working directory and use a separate prefix-layout
resolver; never weaken the repo-local build-directory containment checks. Reject the source root and overlapping
source/build/payload paths that would overwrite build inputs or recursively copy the destination into itself.

The selected layout is:

| Prefix-relative path                                   | Contents                                                                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bin/l1c`, `bin/l1c-stage1`, `bin/l1c-stage1.native`   | Selected Stage 1 alias, prefix-relative launcher, and host native executable. Use the current native-artifact naming convention.                                 |
| `bin/l1-env.sh`                                        | Sourceable bash/zsh activation, including MSYS2 bash.                                                                                                            |
| `bin/l1c.cmd`, `bin/l1c-stage1.cmd`, `bin/l1-env.cmd`  | Windows launcher/activation counterparts; Windows aliases use copies as in the current workflow.                                                                 |
| `shared/l1/stdlib/`                                    | Bundled `std.*` and `sys.*` `.l1` sources with their module-relative paths.                                                                                      |
| `shared/runtime/`                                      | Runtime `src/`, `include/`, `internal/`, and symbol manifests needed by the preparation service.                                                                 |
| `interfaces/`                                          | Complete verified bundled semantic `.l1m` set, copied exactly from bootstrap using module-relative paths.                                                        |
| `include/`                                             | Public `dea_rt.h` and `l1_real.h`; rebuild-only internal headers remain under `shared/runtime/internal/`.                                                        |
| `VERSION`                                              | Human-readable package identity, bootstrap status, host target, and build provenance.                                                                            |
| `share/dea/l1/install-manifest.json`                   | Versioned inventory of payload files, file modes, relative alias targets, content digests, and compiler-owned input-set identity (including `D` where supplied). |
| `README.md`, `share/doc/dea/l1/bootstrap-toolchain.md` | Self-contained bootstrap installation/use/cache instructions with working payload or canonical repository links.                                                 |
| `share/dea/l1/smoke/hello.l1`                          | Small bundled smoke program importing a stdlib module and producing deterministic output.                                                                        |
| `LICENSE-MIT`, `LICENSE-APACHE`, `THIRD_PARTY_NOTICES` | Repository license and attribution files, plus any notices required by the shipped payload.                                                                      |

Resolve installed defaults from the launcher's own prefix: `L1_HOME` points to the prefix, source lookup uses
`shared/l1/stdlib`, and semantic discovery uses `interfaces`. Installed wrappers set their own `L1_HOME` and remove
inherited repo-local `L1_BUILD_DIR` from the child environment. Activation applies the same selection in the current
shell. Explicit system roots, runtime overrides, compiler options, and `L1_STDLIB_CACHE` remain authoritative; tests
distinguish deliberate overrides from leaked repo-local layout defaults.

Activation moves the selected prefix's `bin` directory to the front of `PATH`, removes duplicate entries for that
directory, and preserves the order of other entries. An already-present entry must still move forward when switching
back from another L1 prefix. Clear shell command caches where applicable. Windows compiler launchers scope environment
and helper-variable changes with `setlocal`, restore the calling environment with `endlocal`, and preserve the native
compiler's exit status on every path. Sourceable activation scripts intentionally update the caller's environment.

Use the shared prefix renderers, adding narrowly scoped L1 adaptation where needed. Do not embed build-worktree paths or
force `L1_BUILD_DIR` to the prefix as a way to route cache writes. All relative launcher and alias targets survive
moving the entire prefix, including paths containing spaces. Invocation from any current directory works without
activation; activation is a PATH/environment convenience, not a runtime prerequisite.

Installed payload files are read-only to compiler operations. Native consumers reuse valid support or prepare from
shipped inputs into `--stdlib-cache`, then `L1_STDLIB_CACHE`, then the installed per-user default. There is no installed
native lookup tier. Explicit unusable cache roots fail; an unavailable implicit default permits fresh private support
for automatic consumers. Explicit preparation requires a usable persistent destination. Forced replacement and manual
cache disposal preserve every installed input and must be externally serialized against cache consumers.

Compile-only selects the installed public headers and semantic set without native preparation. Build/link select
complete managed native profiles, including TinyCC raw objects, while preserving explicit runtime overrides. No path
requires `L1_BUILD_DIR` or silently falls back to an unqualified shipped archive.

Intact installed launchers and native executables establish prefix context independently of inventory validity and share
one internal native installation-state check before command dispatch, including `--help` and `--version`. Missing or
invalid metadata must not downgrade installed invocation to repository mode. Validate the inventory version, required
structure, and complete state without hashing the whole payload on every launch. This requires no new public CLI mode or
external interpreter; repository invocations retain their existing startup behavior.

## Install and Archive Defaults

1. `make install PREFIX=...` builds the explicit Stage 1 artifact and verified semantic set, then copies the curated
   compiler-owned input payload through one install helper. Do not copy the worktree's entire build/cache directory.
2. Install into an empty prefix or a prefix whose unrelated files do not collide with the selected payload.
   Reinstallation uses the existing L1 inventory: replace owned files and remove obsolete owned files, preserve
   unrelated files, and reject unowned collisions. Preflight inventory paths, alias targets, and destination parents
   before copying or deleting; never follow a substituted path outside the prefix. Payload files use ordinary writes;
   installation is externally serialized against consumers and does not promise atomic payload upgrade or rollback.
   After preflight, publish an incomplete inventory with previous and intended ownership before changing any payload
   file. Publish each inventory state by writing and closing a complete temporary metadata file in the same directory,
   then replacing the authoritative manifest atomically. Never truncate the authoritative inventory in place. If that
   metadata replacement fails, stop with the prior valid state intact; no payload mutation may precede successful
   incomplete publication. Retain the incomplete inventory throughout copying and obsolete-file removal, then publish
   the complete inventory only after verification succeeds. An interrupted final publication therefore leaves a valid
   incomplete record for retry. Temporary metadata is private install scratch, never a source of payload ownership or
   part of the exported artifact. This is a process-interruption recovery contract, not a power-loss durability promise.
3. `make list-installed PREFIX=...` reads the recorded inventory and prints sorted prefix-relative file paths. It does
   not build, prepare, scan a writable user cache, or claim unrelated prefix contents as installed files. Missing or
   malformed or incomplete inventory is an error. The manifest names itself but omits its own digest. Intact installed
   launcher entrypoints also refuse missing, malformed, or incomplete installation state with an actionable repair/retry
   message; this guard requires neither Python/Make nor a host C compiler. If interruption leaves a launcher or native
   executable missing or damaged, a host launch failure is acceptable; the retained inventory must still support
   installer retry.
4. `make dist` creates the same install tree under a private staging directory and archives it with exactly one
   top-level `dea-l1/` directory. Archive names are `dea-l1-bootstrap_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>` plus
   `.tar.gz` on Linux/macOS or `.zip` on Windows. Build time is UTC; target tokens are normalized for filenames. Emit
   the final archive path for later workflow consumption.
5. Take version metadata from an explicit `DEA_DIST_VERSION` or the repository's L1 version source; if neither exists,
   use `bootstrap-dev`. Validate filename components, retain the bootstrap status label for every version, and never
   infer version from L0 release tags. `VERSION` and the install manifest record source/build provenance, upstream L0
   compiler identity, Stage 1 compiler build options, host target, and shipped preparation-input identity. Provenance
   paths are informational and never used for runtime lookup. All public repository links use
   `https://github.com/dea-lang/dea`.
6. Include only the table's payload and needed notices. Exclude compiler implementation/test trees, unrelated examples,
   plans, repository metadata, virtual environments, tools, build scratch, user caches, retained generated C, docs
   generators, generated API sites, and PDFs. Check packaged documentation links rather than copying source docs with
   dangling repository-relative links.
7. The first supported native artifact matrix follows current L1 CI: Linux x86_64, macOS Intel and ARM, and Windows
   UCRT64. The artifact targets its build host family/architecture; portable archive layout does not imply native
   cross-platform compatibility or eliminate host C/system-library requirements.

## Goal

1. Define the first install-prefix layout for the L1 Stage 1 compiler.
2. Add install workflows that make the built compiler usable outside the repo-local build tree.
3. Add a minimal distribution archive workflow for the bootstrap-stage L1 toolchain.
4. Update L1-local docs so the install/dist/bootstrap workflow is documented consistently.

## Implementation Phases

### Phase 1: Implement prefix and payload helpers

Implement the selected layout, inventory, path validation, prefix launcher/env adaptation, and standalone packaged docs.
Keep these helpers testable with the existing read-only semantic/source payload fixtures. Do not expose a successful
install/dist command that omits their required artifacts.

### Phase 2: Add install workflows

Add the first L1 install-target surface, including:

- `make install PREFIX=...`
- `make list-installed PREFIX=...`
- installed launcher generation
- installed env activation scripts for the same shells already supported by the repo-local workflow

Use the implemented preparation service's input contract, build Stage 1 with the explicit upstream contract, copy its
verified semantic set and rebuild inputs, and mark the inventory complete only after the complete payload is installed.
Test relocated, read-only prefixes and controlled reinstall behavior.

### Phase 3: Add distribution packaging

Add `make dist` using the same payload builder, selected archive naming, version metadata, and exclusion rules. Extract
each archive to an unrelated directory and run the installed smoke workflow there. Keep archive creation local; this
phase creates no release tags, workflows, or published assets.

### Phase 4: Update documentation and contributor guidance

Update the L1-local docs and contributor guidance so they describe:

- repo-local bootstrap workflow
- install-prefix workflow
- dist archive workflow
- explicit upstream compiler override behavior via `L1_BOOTSTRAP_L0C`
- the distinction between building Stage 1 and running the packaged native compiler
- shipped read-only support, writable cache selection, configuration misses, and manual preparation controls

Add the new packaging regression suite to L1's normal validation with lightweight fixture tests and the relevant
installed/artifact smoke checks. Update roadmap/status docs only when implementation lands, then create/amend the
specified ADRs in the same change as plan closure.

## Diagnostic Planning

Install, list, and archive script failures use actionable tooling errors and nonzero exit status. The native installed
state guard uses the existing driver filesystem/environment diagnostic area: provisionally reserve nearby unused
`L1C-9515` for missing, unreadable, malformed, or incomplete installation metadata, with the prefix/inventory path,
reason, repair/retry guidance, and exit status 1. Re-check this reservation against
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostic-catalog] and active plans at implementation time, then
update the shared catalog and CLI contract. Preparation/configuration failures retain the companion preparation plan's
diagnostics; do not reuse its reserved numbers for installation state.

## ADR Impact

- Decision: Define a minimal install-prefix and distribution-artifact contract for the bootstrap-stage L1 compiler.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The relocatable prefix, curated semantic/source payload, inventory, archive naming, and read-only versus
    writable ownership become toolchain interfaces consumed by later release workflows. Cache algorithms remain owned by
    the preparation plan.
- Decision: Choose the L1 bootstrap compiler from repo-local L0 Stage 2 or `L1_BOOTSTRAP_L0C`, never ambient `PATH`.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0001-bootstrap-adaptation-strategy.md`
  - Rationale: ADR-0001 owns bootstrap adaptation and must distinguish the explicit upstream compiler used to construct
    Stage 1 from the self-contained native compiler used after installation.

## Non-Goals

- GitHub Release publishing for L1
- docs publishing or Pages deployment for L1
- any L1 Stage 2 / self-hosted compiler work
- a broad rewrite of the root `README.md`
- automatic inference of the upstream compiler from whichever `l0c` is active on `PATH`
- copying L0 release/docs machinery, adding an installer service, or bundling host compilers and SDKs
- implementing a second preparation/cache algorithm or shipping installed native profiles
- atomic installation, concurrent upgrades, uninstall tooling, or package-manager integration

## Verification Criteria

01. Install/dist construction honors an explicit `L1_BOOTSTRAP_L0C` and rejects an invalid override instead of using
    ambient `l0c`. Stage 1 identity is retained regardless of the active development alias.
02. A fresh install and a controlled reinstall produce exactly the curated owned payload; unrelated files survive, and
    unowned collisions, malformed inventories, substituted parents, and unsafe source/destination overlap fail before
    destructive copying. Inject interruption during initial inventory publication, payload copying/deletion, and final
    publication, including temporary metadata writes and failed replacements. Before the incomplete transition, the
    previous complete installation stays unchanged; after it, ownership remains recoverable for retry. `list-installed`
    and intact installed launcher entrypoints reject incomplete state until installation finishes, without external
    build tools. With intact entrypoint files, cover missing, unreadable, and malformed metadata through every installed
    launcher form, verify the startup diagnostic and status, and ensure invalid metadata never selects repository mode.
    Separately interrupt copying of launcher/native files, allow host launch failure, and verify unusability followed by
    successful installer retry. Repository `--help`, `--version`, and compilation still work without an install
    inventory.
03. Move both an installed tree and an extracted archive to paths containing spaces. Run `--version`, `--help`,
    `--check`, and `--gen` from an unrelated working directory without activation and without source-worktree access.
04. Compile the bundled stdlib-using smoke program, then standalone-link its object without `-I` and run the result.
    Exercise `--build` and `--run` too. No upstream L0, Python, or Make is needed by the installed compiler; the host
    C/linker/preparation tools remain available for native operations.
05. A read-only prefix containing no native stdlib/runtime support compiles the smoke module against its shipped
    semantic set. With an empty cache, `--no-auto-prepare` fails with guidance; ordinary build/run/link prepare matching
    support into the selected cache. Warm no-auto reuse succeeds, changing native configuration selects a new profile,
    and switching back reuses the original. Inspect actual headers and native link inputs; no installed archive may mask
    a miss. Exercise TinyCC with `L1_BUILD_DIR` absent and semantic-only use without native host tools.
06. Forced preparation and clearing/rebuilding a writable cache leave every installed payload digest unchanged. Invalid
    explicit providers/runtime overrides remain authoritative failures. A failed cache selection never writes into the
    prefix or silently chooses another writable root.
07. Installed wrappers override stale repo `L1_HOME`/`L1_BUILD_DIR` defaults while honoring explicit
    system/runtime/cache selectors. Activation works in bash, zsh, MSYS2 bash, and native `cmd.exe` where supported,
    with existing environment stackability and L0 activation coverage preserved. Test installed A -> B -> A and repo ->
    installed -> repo -> installed sequences, asserting resolved compiler identity, environment roots, and no duplicate
    entries for the selected directory. Native `cmd.exe` tests call installed launchers with sentinel parent environment
    values and verify their restoration plus compiler exit-code preservation on success and failure; activation still
    intentionally changes that parent environment.
08. `list-installed` is deterministic and does not invoke build tools or include writable-cache artifacts. Archive
    contents match the manifest, include one `dea-l1/` root, preserve executable/alias behavior, and contain no
    build-worktree dependencies or dangling documentation links.
09. Smoke-test the curated artifact on the supported host matrix and checking/trace selections relevant to prepared
    support. Missing or incompatible native support produces an actionable preparation/toolchain failure.
10. Local install/dist success closes only this plan's delivery contract. Release/snapshot workflows remain owned by
    their separate plan and publication authorization gates.

During implementation, run the new packaging regression suite, installed/extracted smoke workflows, relevant environment
and cache/driver tests, and L1's normal validation. Add full trace validation when changes affect runtime selection,
derived native configuration flags/artifacts, or compiler ownership, following the repository's scope rules; reuse
applicable just-completed checks. This Draft-plan refresh requires documentation checks only.

[diagnostic-catalog]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[monorepo]: ../../../../MONOREPO.md
[release-workflows]: ../../../../work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md
[stdlib-preparation]: ../features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
