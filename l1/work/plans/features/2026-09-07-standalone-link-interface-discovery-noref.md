# Feature Plan

## Discover standalone-link providers through interfaces and managed stdlib artifacts

- Date: 2026-09-07
- Status: Draft
- Title: Add default managed stdlib discovery and explicit interface search roots to L1 standalone linking
- Kind: Feature
- Severity: Medium
- Stage: L1
- Subsystem: Compiler CLI / standalone linking / module graph / interface discovery
- Modules:
  - `l1/compiler/stage1_l0/src/cli_args/`
  - `l1/compiler/stage1_l0/src/link_driver/inputs.l0`
  - `l1/compiler/stage1_l0/src/link_driver/model.l0`
  - `l1/compiler/stage1_l0/src/link_driver/plan.l0`
  - `l1/compiler/stage1_l0/src/link_driver/provenance.l0`
  - `l1/compiler/stage1_l0/src/link_driver/toolchain.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
- Test modules:
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_build_run_multi_cu_test.py`
  - `l1/compiler/stage1_l0/tests/fixtures/separate_compilation/`
- Related:
  - [l1/work/plans/features/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][stdlib-preparation]
  - [docs/specs/compiler/cli-contract.md][cli-contract]
  - [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]
  - [l1/docs/reference/separate-compilation.md][separate-compilation]
  - [l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md][interface-authority]
  - [l1/docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md][external-inputs]
- Repro: `l1c --link build/modules/demo.o -I build/modules -o demo` currently rejects the interface-path option.

## Summary

Enable standalone linking to discover required Dea providers from verified module interfaces. Managed stdlib discovery
is enabled by default, independently of `-I`; explicit `-I` roots add project, third-party, or caller-selected stdlib
providers. Explicit objects take precedence over ordered `-I` roots, followed by managed stdlib providers.

The companion preparation plan supplies matching installed or cached stdlib/runtime artifacts and automatically prepares
missing managed support when permitted. Implement this plan's interface-assisted discovery foundation first, then
integrate that service. The final behavior and verification criteria include both changes; default managed discovery
must not be gated on the presence of `-I`.

The reusable module contract remains a verified `.l1m` interface paired with an opaque sibling `.o`. Link only modules
required by the dependency closure, rather than every module present in an interface root or cache.

## Current State

- `--link` rejects `-I` with `L1C-2031`.
- The caller currently supplies the complete set of Dea objects explicitly, including required stdlib providers.
- The linker verifies sibling interfaces, module identities, fingerprints, entry selection, lifecycle ordering, and
  `require`/`link` provenance. Native objects remain opaque caller-trusted inputs.
- Foreign objects and external libraries are explicitly owned by the CLI's ordered native-input stream.

## Intended User Interface

With matching managed stdlib/runtime support, a program whose remaining dependencies are bundled modules links without
an interface-path option:

```sh
l1c --link build/modules/demo.o -o demo
```

The linker reads `demo.l1m`, discovers the required bundled providers, and uses matching installed or cached artifacts.
Missing managed support is prepared automatically unless preparation has been disabled. Project and third-party
dependencies still require explicit objects or additional interface roots:

```sh
l1c --link build/modules/demo.o -I build/modules -o demo
```

These examples describe the planned behavior, not currently available CLI capabilities.

## Defaults Chosen

### Provider discovery and precedence

1. Register and validate all explicitly supplied Dea objects before resolving missing providers. Preserve their original
   paths and their authority over discovered providers. Duplicate explicit identities remain errors.
2. Follow verified `import module` records recursively for non-virtual dependencies. Search for missing providers in
   explicit `-I` roots in declaration order, then in the matching managed stdlib root when enabled.
3. Managed discovery is limited to the bundled stdlib/system providers. With no `-I`, explicit objects and the managed
   stdlib remain available; arbitrary project directories are not implicitly searched.
4. Treat the first selected interface as authoritative and require its sibling object. Invalid interfaces, missing
   sibling objects, identity failures, or fingerprint mismatches fail without searching for a replacement in a later
   root or the cache.
5. For managed stdlib artifacts, finish any permitted preparation before selecting complete provider pairs. Automatic
   preparation cannot repair or replace an invalid explicitly selected provider.
6. Discover each dependency once. Do not add unrelated cached modules. `require` and `link` expectations remain semantic
   checks; they do not independently introduce objects or lifecycle edges.

### Ordering and validation

Insert discovered objects in dependency order immediately before the first explicit root needing them. Preserve relative
order among all explicit operands, including foreign objects and native-library controls. Retain existing entry
selection, duplicate-identity checks, lifecycle ordering, cycle detection, fingerprint validation, and `require`/`link`
reachability and provenance rules.

Keep foreign objects, native libraries, their search paths, rpaths, and raw link arguments explicit. Native object bytes
remain opaque. No `.l1m` format or object ABI change is required.

### Managed preparation and manual controls

Use the companion plan's configuration selection, cache roots, preparation coordination, and stderr verbosity contract.
Discovery may use installed artifacts or cached variants. If required managed artifacts are missing, prepare them and
continue the original link command. Only the required providers enter the final link set even when preparation builds a
complete stdlib configuration.

- `--no-auto-prepare` permits managed discovery and reuse, but reports the exact preparation command on a miss.
- `--no-stdlib-cache` disables managed discovery and preparation. The caller then supplies required providers explicitly
  or through `-I`.
- Application and third-party dependencies must already have compiled objects. Standalone linking does not compile their
  sources or rebuild caller-supplied objects for a different C compiler.
- Explicit runtime overrides retain their authority. Managed stdlib discovery and runtime selection are related
  services, but neither permits changing explicit caller inputs.

## Compatibility

Existing complete explicit link commands remain valid and preserve explicit-provider precedence and native-input order.
An invocation without `-I` may now succeed when its missing providers are bundled stdlib modules; requiring those
modules to be explicitly listed is intentionally relaxed. A missing project or third-party provider still fails without
an explicit object or suitable `-I` root.

The new managed-preparation exception is confined to compiler-owned stdlib/runtime support. Document this exception in
the standalone-link mode contract while preserving the separate-compilation boundary for user dependencies.

## Implementation Phases

1. Permit `-I` with standalone link, update help and mode validation, and establish explicit-provider registration
   before recursive interface-assisted discovery.
2. Integrate authoritative ordered lookup, dependency deduplication, object insertion, and all existing semantic checks.
   Cover these with caller-prepared provider fixtures before depending on the managed cache.
3. Integrate the companion preparation service as the default final provider source, with no `-I` prerequisite. Apply
   matching configuration selection, automatic preparation, and the two manual-control flags.
4. Update the shared CLI contract, relevant diagnostic descriptions, and L1 separate-compilation docs when the feature
   lands. Document both no-`-I` stdlib linking and additional provider discovery through `-I`.

## ADR Impact

- Decision: Discover managed stdlib providers by default and use explicit interface roots for additional standalone-link
  providers.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md`
  - Rationale: Extend provider discovery while retaining verified interface authority and opaque native inputs. Managed
    stdlib discovery works without `-I`; explicit search roots extend lookup. Preserve ADR-0036's external-input
    ownership and encounter-order contract.

## Diagnostic Planning

Reuse existing interface, missing-object/provider, identity, fingerprint, cycle, entry, and provenance diagnostics.
Update `L1C-2031` to accept `--interface-path` in standalone-link mode. Preparation, coordination, and managed-cache
failures use the companion plan's provisionally reserved `L1C-2150` through `L1C-2169` area; this plan does not reserve
a second block.

Recheck all reservations and candidate reused codes against
[docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] at implementation time. A default managed-cache miss that
can be prepared is progress, not a missing-provider error. An invalid earlier explicit provider remains an error even
when a usable managed provider exists.

## Non-Goals

- Compiling application or third-party dependency sources during standalone linking.
- Automatically discovering foreign objects or native libraries.
- Searching arbitrary project directories without an explicit root.
- Linking every module in an interface root or cache.
- Relaxing interface authority or proving native object compatibility.
- Implementing a separate cache or preparation mechanism from the companion plan.

## Verification Criteria

01. The CLI accepts `--link ... -I ...` and documents the option. Other incompatible mode/option combinations remain
    rejected as specified.
02. A demo link without `-I` discovers required bundled `std.*` and `sys.*` providers and matching runtime support. A
    cold managed configuration prepares automatically; a warm invocation reuses it.
03. Ordered `-I` roots discover transitive project/third-party providers. Without those roots or explicit objects, a
    missing non-bundled provider fails rather than being compiled from source.
04. Explicit providers win over `-I` and managed providers, including when their operands occur after consumers.
    Duplicate explicit module identities still fail.
05. The first selected interface remains authoritative. Bad interfaces, absent sibling objects, wrong identities, and
    fingerprint mismatches are not hidden by later roots or usable cached alternatives.
06. Transitive and shared dependencies are included once, unrelated providers are excluded, and discovered objects
    appear before the first explicit root that needs them without changing relative explicit-operand order.
07. Cycles, entry ambiguity, invalid entry selection, and unreachable or inconsistent `require`/`link` expectations
    remain covered. Initialization/finalization ordering and explicit native-library ordering remain unchanged.
08. `--no-auto-prepare` still discovers matching managed providers and fails only when preparation is needed.
    `--no-stdlib-cache` disables that provider source while explicit and `-I` workflows remain usable.
09. Complete explicit no-`-I` link commands remain valid. New no-`-I` success cases are limited to missing managed
    bundled providers; the mode does not rebuild caller-supplied objects or compile non-bundled sources.
10. Shared build/run link planning and generated-C behavior retain their existing regression coverage.

During implementation, run focused CLI, graph, link, and cache-integration tests followed by L1 `make test-all`, ADR
validation, and required pre-commit checks. Recording this Draft plan requires documentation validation only.

[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-inputs]: ../../../docs/decisions/0036-ordered-external-link-inputs-and-cli-only-dependency-ownership.md
[interface-authority]: ../../../docs/decisions/0030-authoritative-module-interfaces-and-opaque-native-link-inputs.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
[stdlib-preparation]: 2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
