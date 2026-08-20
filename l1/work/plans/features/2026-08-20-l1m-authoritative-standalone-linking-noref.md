# Feature Plan

## Make `.l1m` Authoritative for Standalone Linking

- Date: 2026-08-20
- Status: Draft
- Title: Make `.l1m` Authoritative and Native Objects Opaque in Standalone Link Mode
- Kind: Feature
- Severity: High
- Stage: 1
- Parent Initiative: [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative]
- Subsystem: Separate compilation, module interfaces, lifecycle planning, and standalone linking
- Modules:
  - `l1/compiler/stage1_l0/src/analysis.l0`
  - `l1/compiler/stage1_l0/src/backend.l0`
  - `l1/compiler/stage1_l0/src/c_emitter.l0`
  - `l1/compiler/stage1_l0/src/cli_args.l0`
  - `l1/compiler/stage1_l0/src/compile_driver.l0`
  - `l1/compiler/stage1_l0/src/driver.l0`
  - `l1/compiler/stage1_l0/src/interface_emitter.l0`
  - `l1/compiler/stage1_l0/src/interface_fingerprint.l0`
  - `l1/compiler/stage1_l0/src/l1c_lib.l0`
  - `l1/compiler/stage1_l0/src/link_driver.l0`
  - `l1/compiler/stage1_l0/src/mi_utils.l0`
  - `l1/compiler/stage1_l0/src/module_graph.l0`
  - `l1/compiler/stage1_l0/src/module_interface.l0`
  - `l1/compiler/stage1_l0/src/module_lifecycle.l0` (new)
  - `l1/compiler/stage1_l0/src/object_metadata.l0`
  - `l1/compiler/stage1_l0/src/object_reader.l0`
  - `l1/compiler/stage1_l0/src/object_reader_elf.l0`
  - `l1/compiler/stage1_l0/src/object_reader_macho.l0`
  - `l1/compiler/stage1_l0/src/object_reader_pecoff.l0`
  - `l1/compiler/stage1_l0/src/object_reader_types.l0`
  - `l1/compiler/stage1_l0/src/parser/interface.l0`
  - `l1/compiler/stage1_l0/src/wrapper_emitter.l0`
  - `l1/docs/specs/compiler/module-visibility-and-imports.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/analysis_test.l0`
  - `l1/compiler/stage1_l0/tests/backend_test.l0`
  - `l1/compiler/stage1_l0/tests/c_emitter_test.l0`
  - `l1/compiler/stage1_l0/tests/cli_args_test.l0`
  - `l1/compiler/stage1_l0/tests/compile_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/driver_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_fingerprint_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_replay_test.l0`
  - `l1/compiler/stage1_l0/tests/interface_test.l0`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_compile_only_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_help_output_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_link_set_test.py`
  - `l1/compiler/stage1_l0/tests/link_driver_test.l0`
  - `l1/compiler/stage1_l0/tests/module_graph_test.l0`
  - `l1/compiler/stage1_l0/tests/module_lifecycle_test.l0` (new)
  - `l1/compiler/stage1_l0/tests/object_metadata_test.l0`
  - `l1/compiler/stage1_l0/tests/object_reader_test.l0`
  - `l1/compiler/stage1_l0/tests/wrapper_emitter_test.l0`
- Related:
  - [`l1/work/initiatives/0003-c-ffi.md`][c-ffi-initiative]
  - [`l1/work/plans/features/2026-04-24-c-ffi-extern-c-and-cstr-noref.md`][c-ffi-plan]
  - [`l1/work/plans/features/closed/2026-04-24-module-interface-emission-noref.md`][interface-emission]
  - [`l1/work/plans/features/closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md`][interface-fingerprints]
  - [`l1/work/plans/features/closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md`][lifecycle]
  - [`l1/work/plans/features/closed/2026-07-17-object-metadata-emission-and-readers-noref.md`][object-metadata]
  - [`l1/work/plans/features/closed/2026-07-17-compile-only-artifact-production-noref.md`][compile-only]
  - [`l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md`][link-set]
  - [`l1/work/plans/bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md`][link-hardening]
- Repro: `make -C l1 test-stage1`

## Summary

Make the existing sibling `.l1m` artifact the sole Dea semantic and lifecycle authority for standalone linking. Treat
the paired `.o` as an opaque native implementation payload and pass its original path to the host toolchain without
reading or classifying its bytes.

The reusable separate-compilation artifact remains a pair:

```text
foo.l1m = verified Dea interface, dependency, entry, and lifecycle metadata
foo.o   = opaque native implementation payload
```

The pair is caller-trusted rather than cryptographically or structurally bound. This removes the second metadata format
embedded in native objects, the ELF/Mach-O/PE-COFF readers, metadata retention anchors, exact-byte input snapshots, and
native-content policing. It preserves the actual semantic linker responsibilities: complete graph validation, entry
selection, ordered initialization/finalization, wrapper generation, and host linking.

This is a Feature rather than a Refactor because it changes the unpublished L1 object ABI and the observable validation
contract of standalone link and `--foreign-object`.

## Current State

Compile-only already publishes canonical sibling `.o + .l1m` artifacts. The interface carries module identity, the
public fingerprint, public declarations, and the existing `require` and `link` manifests. Standalone link deliberately
does not reopen `.l1m`; it reconstructs module identity, entry presence, provider expectations, and ordered imports from
`I8metadata` and `I7imports` records embedded in native objects.

That object-authoritative choice requires all of the following:

- portable metadata arrays and retention reads in generated C;
- native ELF, Mach-O, and PE/COFF readers;
- Dea/foreign/malformed object classification;
- foreign `main` and embedded linker-control checks;
- exact inspected-byte snapshots for every caller operand;
- object/interface agreement validation during compile-only publication.

The complexity is coherent under the current authority model, but the same Dea semantics already have a portable text
artifact. This feature changes the authority boundary instead of introducing another binding mechanism.

## Goals

1. Make a verified sibling `.l1m` the only Dea semantic input for each positional standalone-link object.
2. Keep native `.o`, archive, and runtime object bytes opaque to the Dea compiler.
3. Preserve source import side effects and exact first-occurrence lifecycle order.
4. Preserve the current `require`/`link` partition and public-fingerprint domain.
5. Reject a semantic dependency whose non-virtual provider is not transitively reachable through recorded lifecycle
   imports.
6. Preserve the iterative, stack-safe lifecycle traversal and exact reverse finalization.
7. Remove embedded object metadata, native-object readers, snapshots, and content classification completely.
8. State the weaker trusted-pair and foreign-input guarantees explicitly in CLI, ABI, and architecture documentation.

## Non-goals

1. Changing Dea source syntax or import side-effect semantics.
2. Deriving lifecycle edges from `require` or `link` records.
3. Discovering implicit standalone-link objects from interface records or search roots.
4. Merging the `require`, `link`, and ordered lifecycle-import views.
5. Adding archives, shared libraries, linker scripts, rpaths, or raw link options to `--foreign-object`.
6. Adding a package/build manifest, package manager, or dependency solver.
7. Preserving compatibility with existing unpublished Stage 1 artifacts.
8. Authenticating or cryptographically binding `.o` and `.l1m` bytes.

## Artifact Authority and Trust Model

For every positional Dea operand, standalone link must:

1. require a path that does not end in a separator and has a nonempty basename stem followed by the exact,
   case-sensitive terminal suffix `.o`;
2. derive the sibling interface by replacing only that suffix with `.l1m` in the same directory;
3. require both paths to resolve to regular files;
4. parse and verify only the `.l1m`;
5. retain the caller-selected `.o` as an opaque host-link input.

Sibling derivation is path-only and occurs before any module identity is available. Preserve the existing
`_mg_has_regular_extension()` conditions: the path is nonempty and does not end in a separator, and its final component
is strictly longer than `.o` and ends in that exact case-sensitive suffix. Thus `.o`, `dir/.o`, and `foo.o/` are
rejected. Remove only that suffix from the final component and append `.l1m`. A shared helper performs this
transformation without accepting a module name. The verified sibling header is authoritative regardless of the pair's
basename; standalone link has no independent "expected identity" derived from either native bytes or path spelling.

```text
mg_interface_path_from_object_path(object_path: string) -> string?
```

The helper returns an owned sibling path or `null` for a nonconforming suffix; callers retain mode-specific diagnostics.
Compile-only's existing module-aware artifact constructor delegates to it only after its separate module-name check.

Input symlinks remain allowed when they resolve to regular files. Output alias validation compares filesystem identities
and rejects an output alias of any caller native input, consumed `.l1m`, runtime link input, or resolved `dea_rt.h`
wrapper-compilation input. Concurrent symlink or target replacement is outside the trusted-input contract.

All Dea objects remain explicit CLI operands. An `import module`, `require`, or `link` record validates the supplied
set; it does not search for or add an object path.

No checksum, link fingerprint, native symbol, C data anchor, metadata section, or other mechanism binds the object bytes
to the interface bytes. Build systems, caches, and callers must create, copy, replace, and invalidate the pair together.
Mixed-generation pairs can fail at interface validation, fail at native link, or link successfully with incorrect native
behavior. That limitation is accepted and documented.

No interface-format version bump or new compatibility discriminator is introduced. Every Stage 1 artifact must be
rebuilt after this change. An old dependency-free, non-entry interface may be syntactically indistinguishable from a new
one, so clean rebuild is an external trust precondition rather than a compiler-enforced compatibility check.

## Canonical `.l1m` Contract

The canonical interface grammar becomes:

```text
interface-file :=
    "module" "interface" module-name ";"
    "fingerprint" fingerprint-string ";"
    [ "entry" ";" ]
    { "import" "module" module-name "==" fingerprint-string ";" }
    { "require" qualified-symbol "==" fingerprint-string ";" }
    { "link" qualified-symbol "==" fingerprint-string ";" }
    { exported-declaration }

qualified-symbol := module-name "::" symbol-name
```

The regions occur in exactly this order:

1. module header;
2. public-interface fingerprint;
3. zero or one `entry;` marker;
4. zero or more `import module` records in lifecycle order;
5. zero or more `require` records;
6. zero or more `link` records;
7. exported declarations in their existing canonical group order;
8. end of file.

`entry` uses exact artifact spelling even if the shared lexer represents it as an identifier. Duplicate `entry;`, an
`entry;` after a later region begins, returning to an earlier region, duplicate import providers, and trailing unknown
records are errors. The parser preserves import order and rejects duplicates rather than normalizing them. Missing or
wrong token shapes remain parser errors; fingerprint string spelling and algorithm support are preserved by parsing and
validated by `ifp_verify()` under `SIG-0280` and `SIG-0281`.

The emitter inserts blank lines canonically but whitespace is not semantically significant. Exported declaration order
remains unchanged: structs, enums, aliases, functions, consts, and lets, with names sorted within groups and existing
declaration-internal ordering retained.

### In-memory representation

Extend `ModuleInterface` with:

```text
has_entry: bool
module_imports: ordered vector of InterfaceModuleImport

InterfaceModuleImport:
    provider_module
    provider_fingerprint
```

This is separate from `ModuleGraphNode.direct_imports`. Source graph nodes continue to retain exact source declaration
order, including duplicates. Interface projection owns the canonical stable-deduplicated view, and parsed interfaces
store that canonical view directly.

Compiler-synthesized virtual providers are omitted from `import module`, `require`, and `link`; they have no sibling
native artifact or lifecycle record. Expanded interface validation rejects persisted virtual-provider records.

Provider uniqueness is an operational model invariant, not merely a text-parser invariant. `ifp_verify()` rejects a
programmatically constructed `ModuleInterface` containing repeated `module_imports` providers even when their
fingerprints agree. It also validates import fingerprint spelling, virtual-provider exclusion, and fingerprint
consistency across `module_imports`, `require`, and `link` before the interface can be registered.

## Dependency Views and Projection

The three records retain distinct meanings:

| Record            | Meaning                                                                    | Lifecycle effect                   |
| ----------------- | -------------------------------------------------------------------------- | ---------------------------------- |
| `require P::S`    | `P::S` is exposed through the consumer's public surface.                   | None by itself.                    |
| `link P::S`       | `P::S` is an implementation-used provider symbol not already in `require`. | None by itself.                    |
| `import module P` | The source directly imports object-backed `P`, including for side effects. | Ordered consumer-to-provider edge. |

The current `require`/`link` partition remains authoritative: public-surface symbol dependencies enter `require`, and
remaining implementation symbol dependencies enter `link`. `import module` is independently projected from resolved
source imports and is never reconstructed from either symbol tier.

Interface projection builds `module_imports` by walking `ModuleGraphNode.direct_imports` in order, omitting virtual
providers, retaining the first occurrence of each remaining provider, discarding later duplicates, and retaining
side-effect-only imports. It must not mutate or canonicalize the graph's exact source-order vector.

A provider may occur in `require` or `link` without appearing directly in that consumer's `import module` region. For
example, an inferred exported type may name a transitive nominal provider. Direct membership across all views is not an
invariant. Fingerprints must agree whenever the same provider appears in multiple views or symbol records.

## Public Fingerprint and Producer Phases

The existing public-interface fingerprint algorithm, domain, tagged spelling, and verification rules remain unchanged.
The fingerprint covers only the canonical exported declarations. It excludes:

- module identity and filesystem location;
- `entry`;
- `import module`;
- `require`;
- `link`;
- private implementation details;
- native-object contents.

Reordering direct imports changes `.l1m` bytes and can change observable lifecycle order without changing the public
fingerprint. No second link fingerprint is introduced.

Interface production must preserve this phase boundary:

1. project and canonicalize the public declaration surface;
2. assign the consumer's public fingerprint;
3. derive `has_entry` through the shared entry predicate;
4. derive the stable-deduplicated, virtual-filtered module imports;
5. populate expected provider fingerprints for `module_imports`, `require`, and `link` through one provider cache;
6. validate all operational manifests, including provider uniqueness and same-provider fingerprint consistency;
7. emit the canonical interface.

Provider expectations never participate in computing the consumer's fingerprint.

## Transitive Lifecycle-Provenance Invariant

After all sibling interfaces pass verification and all module identities are registered, every non-virtual provider
named by a consumer's `require` or `link` entries must satisfy both conditions:

1. the provider is present in the explicitly supplied Dea module set; and
2. the provider is reachable from the consumer by a nonempty path of existing `import module` edges.

Failure makes the link set invalid.

This is a validation rule, not an edge-construction rule. Standalone link must never convert a `require` or `link`
record into a lifecycle edge, add an implicit object, or invent initialization order. The check proves that the
independently recorded source-import graph contains the transitive provenance expected from compiler-produced
interfaces.

For example:

```text
app import module factory
factory import module model
app require model::Token
```

`model` is not a direct import of `app`, but it is valid because `app -> factory -> model` exists in the lifecycle
graph. That existing path guarantees `model` initializes before `app` and finalizes after it. The `require` record
contributes no lifecycle edge.

The validation is global and runs only after all verified interfaces are registered and the import graph has completed
acyclic lifecycle ordering. Its traversal scratch is independent of lifecycle planning. For each consumer with
non-virtual `require` or `link` providers, perform one iterative walk from that consumer's `module_imports` using a
fresh local visited set and explicit stack, then check every unique provider named by that consumer against the
resulting reachable set. The provenance walk must not read or mutate `LinkInput.visit_state`, the lifecycle frame stack,
or `LinkPlan.lifecycle_order`; discard its local scratch between consumers. Virtual providers are exempt because they
have no independent object lifecycle. Side-effect-only imports are valid without any corresponding `require` or `link`
records.

Where a provider appears in multiple manifest entries, every expectation must equal the verified public fingerprint of
the supplied provider interface.

## Standalone Verification Pipeline

Standalone link performs these phases in order:

01. Validate CLI operand roles and exact positional `.o` suffixes.
02. Validate regular-file status for original objects and derive sibling `.l1m` paths.
03. Read, UTF-8 validate, parse, and run `ifp_verify()` on every sibling interface.
04. Reject all interfaces if any interface fails; no unverified interface contributes graph state.
05. Register verified module identities and reject duplicates.
06. Validate import-provider presence and expected-versus-supplied fingerprints.
07. Resolve explicit or inferred entry selection.
08. Compute lifecycle order and reject import-graph cycles in one iterative traversal.
09. Validate transitive lifecycle provenance for every non-virtual `require` and `link` provider.
10. Generate and compile the wrapper.
11. Invoke the host linker with original native input paths.

Every positional Dea object's sibling `.l1m` is verified before registration. In particular, module identity, entry
presence, imports, and dependency expectations from an invalid interface are never visible to graph validation.
Within-interface provider disagreement has already failed as `SIG-0284` during `ifp_verify()`; `L1C-2102` is reserved
for comparison between an interface expectation and the one supplied, verified provider interface.

## Entry and Lifecycle Contract

`entry;` is present exactly when the module emits `I5entry`. Interface projection and backend generation consume one
shared entry predicate so the text artifact and native ABI cannot diverge.

Entry selection retains current behavior:

- with `--entry M`, `M` must be registered and carry `entry;`;
- without `--entry`, exactly one registered module must carry `entry;`;
- zero or multiple candidates fail with deterministic candidate spelling.

Entry selection precedes lifecycle traversal. Preserve current diagnostic precedence: when the same set has invalid
entry selection and an import cycle, `L1C-2104` is reported before `L1C-2103`.

Lifecycle edges come only from `import module` records and point from consumer to provider. `require` and `link` never
affect traversal order.

Preserve the current nonrecursive, three-state DFS. This one lifecycle traversal both detects cycles and constructs
lifecycle order; within lifecycle planning there is no earlier cycle pass, second visit state, or state reset:

1. visit the selected entry component first;
2. visit each module's imports in stored order;
3. append the module after all of its providers;
4. then visit every unvisited positional Dea root in CLI encounter order.

The implementation retains its explicit frame stack and 10,000-node stress coverage. Modules initialize once, diamond
dependencies remain deduplicated by visit state, and cycles produce deterministic path diagnostics. The wrapper calls
initializers in computed postorder, calls the selected `I5entry` only after all supplied Dea roots initialize, and calls
finalizers in exact reverse order.

## Native ABI Change

Remove the unpublished object infrastructure symbols and all associated generated data:

```text
I8metadata
I7imports
external C byte arrays carrying their records
volatile retention reads from I4init
```

Retain unchanged:

```text
I4init
I4fini
conditional I5entry
ordinary exported LBI symbols
```

No replacement data object or hash-named anchor is added. Extract the `I4init`, `I4fini`, and `I5entry` name helpers
from `object_metadata.l0` into `module_lifecycle.l0` before deleting metadata code.

## Compile-only Contract

Compile-only continues to stage and publish canonical sibling `.o + .l1m` outputs with endpoint rollback. Before
publication it validates:

- the staged object path is a regular file;
- the staged interface bytes equal the bytes selected for publication;
- the staged interface parses and passes `ifp_verify()`;
- the module identity and expected public fingerprint are correct.

It no longer inspects the staged object or proves object/interface agreement. Object-first/interface-second publication
and rollback remain sequential, not reader-atomic or crash-safe. External serialization remains required.

## Foreign-object Contract

`--foreign-object PATH` becomes a caller assertion that `PATH` is one host-compatible relocatable native object. Dea
checks that the path resolves to a regular file, does not alias the output, and is safe to render as a host command
word. It does not read the file or prove that it:

- is relocatable or host-compatible;
- is metadata-free;
- lacks `main` or reserved `__dea` symbols;
- lacks embedded linker controls.

Archives, shared libraries, linker scripts, response files, and raw host-link arguments remain outside this option's
supported contract even if a particular host toolchain happens to accept a mislabeled operand. Those surfaces remain
owned by the active external-library-linking plan.

Host-tool failures, duplicate symbols, entry collisions, architecture mismatches, and injected native controls are
outside Dea semantic validation and are reported through captured host diagnostics.

## Link Workspace, Paths, and Host Invocation

The new owned input model is:

```text
LinkInput:
    kind
    object_path
    interface_path: string?
    interface: ModuleInterface*?
    visit_state

Dea input:    interface_path != null, interface != null
foreign input: interface_path == null, interface == null
```

Each `LinkInput` owns its object path, optional sibling path, and optional verified interface. `LinkPlan.inputs` owns
all inputs; `modules_by_name` contains borrowed pointers to Dea inputs only. Successful parsing transfers the interface
out of its parse result, and input destruction calls `mi_free()` exactly once when the optional interface is present.

Retain the output-local `.l1c-link-*` scratch directory, fixed wrapper/log children, explicit ownership, captured
stdout/stderr, bounded nonrecursive cleanup, and cleanup diagnostics. Remove `input-N.o` snapshots and all exact-byte
claims.

The host linker writes directly to `OUTPUT`. Final executable publication remains nontransactional and has no rollback
protocol. A failed host link may replace or partially modify an existing regular output according to host-tool behavior.

Pass caller-selected native inputs through the existing host-safe path renderer. "Original paths" means the original
files rather than snapshots, not unnormalized command tokens. Preserve option-shaped path disambiguation and MSVC path
normalization.

Preserve final native-link operand order exactly:

```text
generated wrapper object
caller Dea and foreign native operands in exact interleaved CLI encounter order
runtime native inputs
optional non-MSVC host math-library argument
output arguments
```

Runtime inputs are last among native operands, not literally the final command words.

Before scratch allocation, Windows shell validation covers every caller- or environment-controlled host-command value
already known: compiler, parsed wrapper options, runtime include directory, runtime native inputs, output path, and
every original Dea or foreign object path. Sibling `.l1m` paths are not host-command words and do not enter this check.

After scratch allocation, the common executor validates each exact rendered compile or final-link command together with
its transaction-owned stdout and stderr paths immediately before invoking the host. This second validation covers the
generated wrapper and redirection paths that do not exist during pre-allocation validation.

Replace byte reads of the runtime archive and TinyCC runtime objects with regular-file checks. Runtime-include
resolution retains both the include directory used by the wrapper command and the exact validated `dea_rt.h` path.
Reading that header remains valid because it is a textual compile input, not an opaque native link input; before scratch
allocation, output-alias validation rejects an exact-path or filesystem-identity alias of it under `L1C-2105`. Caller
`.o` and `.l1m` paths use follow validation, so aliases resolving to regular files remain allowed. The transaction-owned
generated wrapper object must pass no-follow regular-file validation before final linking, so path substitution remains
rejected; the host linker owns its native-format validation.

## Diagnostic Migration

Record these provisional assignments in this plan when it opens. Update the live
[`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostics] only with the implementation, after rechecking every
assignment against the then-current catalog.

Interface parsing, decoding, and model verification use these exact dispositions:

| Code                                 | Disposition                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PAR-0565`                           | Retain for a missing or wrong public-fingerprint token shape. It does not validate fingerprint spelling.                                                                                                                                                                                                                          |
| `PAR-0572`                           | Retain for malformed operational-record shape not covered by a more specific code, including `entry` without its terminating `;`, missing `module` or provider after `import`, and an unsupported or trailing unknown interface record.                                                                                           |
| `PAR-0573`                           | Retain only for a missing exported-declaration name; do not reuse it for `entry` or `import module`.                                                                                                                                                                                                                              |
| `PAR-0574` / `PAR-0575` / `PAR-0576` | Reuse respectively for a missing `==`, provider fingerprint string, or terminating `;` in `import module`, `require`, and `link`. Reword the live catalog's `PAR-0574` subject from a dependency symbol to an interface dependency subject when implementation lands. These codes validate token shape, not fingerprint spelling. |
| `PAR-0578`                           | Provisionally assign to a duplicate operational interface record: a second `entry;` or a repeated provider in `import module`. When one record is both duplicate and misplaced, this diagnostic wins.                                                                                                                             |
| `PAR-0579`                           | Provisionally assign to a nonduplicate interface record appearing outside canonical region order.                                                                                                                                                                                                                                 |
| `DRV-0074`                           | Reuse when the required sibling `.l1m` is missing.                                                                                                                                                                                                                                                                                |
| `DRV-0075`                           | Reuse when the selected sibling `.l1m` is unreadable or does not resolve to a regular file.                                                                                                                                                                                                                                       |
| `DRV-0076`                           | Reuse when the selected sibling `.l1m` is not valid UTF-8.                                                                                                                                                                                                                                                                        |
| `SIG-0280` / `SIG-0281`              | Retain for malformed fingerprint spelling and unsupported fingerprint algorithms.                                                                                                                                                                                                                                                 |
| `SIG-0284`                           | Extend across `module_imports`, `require`, and `link` for conflicting expectations for one provider within one interface.                                                                                                                                                                                                         |
| `SIG-0285`                           | Provisionally assign to an invalid operational interface model, including an equal duplicate `module_imports` provider in a programmatic interface or a persisted virtual provider in any manifest.                                                                                                                               |

`PAR-0578` and `PAR-0579` complete the interface parser's originally reserved `PAR-0560..0579` range and do not overlap
the active C-FFI reservation at `PAR-0580..0599`.

Standalone link-driver diagnostics use these dispositions:

| Code       | Disposition                                                                                                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `L1C-2097` | Retain and reword for a positional or explicitly foreign native path that is invalid, missing, or does not resolve to a regular file. Remove unreadability, native-format, and inspection claims. |
| `L1C-2098` | Keep registered as `Reserved; former link-operand metadata-classification diagnostic, no longer emitted`.                                                                                         |
| `L1C-2099` | Keep registered as `Reserved; former explicit foreign-object main diagnostic, no longer emitted`.                                                                                                 |
| `L1C-2100` | Retain for two verified sibling interfaces declaring the same canonical module identity.                                                                                                          |
| `L1C-2101` | Retain and broaden to any non-virtual provider named by `import module`, `require`, or `link` but absent from the explicit supplied Dea set.                                                      |
| `L1C-2102` | Retain only for an expected provider fingerprint differing from the supplied verified provider interface. Within-interface conflicts use `SIG-0284`.                                              |
| `L1C-2103` | Retain for a cycle detected while computing lifecycle order.                                                                                                                                      |
| `L1C-2104` | Retain for explicit or inferred entry selection using `entry;`; it precedes cycle diagnostics.                                                                                                    |
| `L1C-2105` | Retain for output and output-parent validation, including exact and filesystem-identity aliases of consumed `.l1m` files and the resolved `dea_rt.h`.                                             |
| `L1C-2106` | Retain for host compiler and runtime input selection and Windows preflight.                                                                                                                       |
| `L1C-2107` | Retain for output-local scratch setup and wrapper-source writing, with snapshot language removed.                                                                                                 |
| `L1C-2108` | Retain for wrapper compilation or failure to produce a no-follow regular wrapper object; remove relocatable-format claims.                                                                        |
| `L1C-2109` | Retain for final host link, executable validation, or bounded scratch cleanup.                                                                                                                    |
| `L1C-2110` | Keep registered as `Reserved; former embedded linker-control carrier diagnostic, no longer emitted`.                                                                                              |
| `L1C-2111` | Provisionally assign to a supplied non-virtual `require`/`link` provider that is present but not transitively reachable through `import module` edges.                                            |

The active build/run plan's provisional `L1C-2110..2129` block is already stale because `L1C-2110` is registered. Rebase
that whole future block to `L1C-2130..2149` in the opening-time coordination change, subject to its existing
implementation-time recheck rule.

## Repository and Documentation Coordination

### Opening-time coordination

The change that opens this plan must:

1. add its path to `Open plans:` in [`l1/work/initiatives/0001-separate-compilation-and-linking.md`][initiative], update
   that initiative's version, and retain the reciprocal `Parent Initiative` metadata above;
2. add a clearly future-tense planned-transition and spawned-plan entry to Initiative 0001 without rewriting its current
   baseline, completed phases, resolved decisions, glossary, or existing ADR Impact as though implementation had landed;
3. add this active plan to `l1/docs/roadmap.md` and refresh the roadmap version;
4. record the provisional diagnostic assignments only in this plan, not in the live catalog; and
5. move the build/run plan's stale provisional diagnostic block to `L1C-2130..2149` so active reservations do not
   overlap this plan's provisional `L1C-2111`.

Opening the plan does not update normative current-state specifications, the live diagnostic catalog, accepted ADRs, or
Initiative 0001's implemented baseline. There are no separate prospective "interface/CLI contract drafts" to update.

After opening the plan, run `python3 scripts/check_adr_impact.py --all-active` from the repository root. Before
committing any opening, implementation, or closure change that modifies work documents or ADRs, stage the intended
document set and run `python3 scripts/check_adr_impact.py --staged`.

### Implementation and closure coordination

Before implementation code begins, rebase these active dependent work documents onto the planned future contract while
keeping implemented-current-state prose explicit:

1. [`l1/work/plans/features/2026-07-17-build-run-multi-cu-orchestration-noref.md`][build-run]: consume verified
   `module_imports`, remove object-metadata agreement and classification assumptions, keep pair stability as a caller
   trust obligation, and preserve source discovery versus standalone explicit closure.
2. [`l1/work/plans/features/2026-07-24-per-module-generated-c-mode-noref.md`][generated-c]: remove embedded metadata
   from the planned generated C identity while retaining lifecycle entry points and `.o + .l1m` publication.
3. [`l1/work/plans/features/2026-04-24-external-library-linking-cli-noref.md`][external-linking]: replace
   metadata-free-object and embedded-control enforcement assumptions with the caller-asserted foreign-object boundary;
   keep archives, libraries, scripts, and raw arguments on their typed future surface.
4. [`l1/work/initiatives/0003-c-ffi.md`][c-ffi-initiative], updating its `Version` to the amendment date whenever it is
   substantively changed, and its [`l1/work/plans/features/2026-04-24-c-ffi-extern-c-and-cstr-noref.md`][c-ffi-plan]:
   replace claims that Dea verifies a metadata-free C object with the caller assertion that `--foreign-object` names one
   host-compatible relocatable object. It remains outside Dea fingerprints, lifecycle, entry, and module identity, but
   Dea does not prove its format, symbols, or embedded controls.

As the implementation lands, update the following normative and status documents to describe implemented behavior:

- [`docs/specs/compiler/cli-contract.md`][cli-contract];
- [`docs/specs/compiler/diagnostic-code-catalog.md`][diagnostics];
- [`l1/docs/specs/compiler/module-interface-format.md`][interface-format];
- [`l1/docs/specs/compiler/module-visibility-and-imports.md`][module-visibility];
- [`l1/docs/specs/compiler/abi.md`][abi];
- [`l1/docs/reference/architecture.md`][architecture];
- [`l1/docs/reference/separate-compilation.md`][separate-compilation];
- [`l1/docs/reference/c-backend-design.md`][backend-design];
- [`l1/docs/reference/design-decisions.md`][design-decisions];
- [`l1/docs/project-status.md`][project-status];
- [`l1/docs/roadmap.md`][roadmap];
- CLI help emitted by `l1/compiler/stage1_l0/src/cli_args.l0`.

The visibility/import specification must distinguish the fingerprinted public-declaration surface from non-fingerprinted
entry and dependency regions, state that every resolved non-virtual source import is lifecycle-bearing, and define
first-occurrence interface canonicalization without changing exact source-import storage.

At implementation/closure, rewrite Initiative 0001's current baseline, completed phases, driver/interface/backend and
diagnostic sections, resolved decisions, glossary, and ADR Impact. Update any remaining current-state wording in
Initiative 0003. Complete the new and amended ADR work, add the closed plan to ADR-0003's `Related Plans`, update the
ADR index, move this plan from `Open plans:` to `Closed plans:`, and move the file to `features/closed/`.

## Implementation Sequence

### 1. Land planning coordination

Open this Feature plan through Initiative 0001 and the roadmap, add future-tense transition notes, move the stale
build/run diagnostic reservation, and record provisional diagnostics in this plan. Before code changes begin, rebase the
affected active plans and Initiative 0003 with its required `Version` refresh. Preserve implemented baselines, live
specifications, the diagnostic catalog, and accepted ADRs until code changes land. Keep the new L1 ADR number unassigned
while the plan is active.

### 2. Extract shared semantics

1. Move lifecycle symbol-name construction from `object_metadata.l0` into new `module_lifecycle.l0`.
2. Move the exact source-entry predicate from backend-private code into a shared analysis API and route backend bridge
   emission through it; interface projection begins consuming it in Step 3.
3. Move stable first-occurrence import projection, virtual filtering, and provider expectation population into analysis.
4. Route the legacy backend/object-metadata emission through the shared helpers and add focused analysis and lifecycle
   helper tests. This phase does not yet add `.l1m` fields or emitter consumption.

This phase changes no link authority and prevents interface/native divergence during migration.

### 3. Extend the interface model and wire format

1. Add `has_entry` and `module_imports` to `ModuleInterface`, cloning, and freeing.
2. Extend the parser with strict fixed-region handling and dedicated malformed-order/duplicate diagnostics.
3. Extend the emitter with canonical entry and ordered import regions.
4. Make interface projection and emission consume the shared entry/import helpers extracted in Step 2.
5. Keep public fingerprint computation unchanged.
6. Expand `ifp_verify()` for import-provider uniqueness, virtual-provider rejection, fingerprint spelling, and
   same-provider consistency across all operational manifests.
7. Update every hard-coded `.l1m` fixture and replay string needed by the stricter contract.

### 4. Integrate analysis and graph representations

1. Preserve `ModuleGraphNode.direct_imports` as exact source order with duplicates.
2. Populate canonical interface imports only during interface projection.
3. Extend `driver.l0` to retain parsed interface imports separately from source direct imports.
4. Keep standalone explicit-set validation separate from future build/run interface/object discovery.
5. Verify every selected sibling with `ifp_verify()` before graph registration.

### 5. Switch standalone link authority

1. Add the path-only terminal-suffix helper for `.o` to sibling `.l1m` derivation, preserving the existing nonempty
   basename-stem rule.
2. Replace `ObjectInspection` link inputs with the explicitly owned optional-interface model above; foreign inputs carry
   null interface fields.
3. Parse and verify the complete sibling-interface set before registration, then validate provider presence and
   expected-versus-supplied fingerprints.
4. Select entry before retaining the single iterative traversal that detects cycles and computes lifecycle order.
5. Validate transitive lifecycle provenance after successful acyclic ordering with per-consumer local iterative scratch
   independent of lifecycle visit state.
6. Remove input snapshots and pass original host-rendered paths in exact wrapper/caller/runtime native operand order.
7. Update output aliases, including the resolved runtime header, split Windows preflight at scratch allocation, retain
   runtime inputs, preserve no-follow wrapper validation, and keep direct nontransactional output.
8. Redefine `--foreign-object` as the documented caller assertion.

### 6. Remove embedded metadata and readers

1. Remove metadata emission and volatile anchors from backend/C emission.

2. Remove compile-only object inspection and metadata/interface comparison.

3. Delete:

   ```text
   l1/compiler/stage1_l0/src/object_metadata.l0
   l1/compiler/stage1_l0/src/object_reader.l0
   l1/compiler/stage1_l0/src/object_reader_types.l0
   l1/compiler/stage1_l0/src/object_reader_elf.l0
   l1/compiler/stage1_l0/src/object_reader_macho.l0
   l1/compiler/stage1_l0/src/object_reader_pecoff.l0
   ```

4. Delete only metadata/reader-specific tests after moving retained lifecycle-name and graph coverage.

5. Remove obsolete build registrations, imports, fixtures, diagnostic emission paths, and trigger tests; retain
   `L1C-2098`, `L1C-2099`, and `L1C-2110` as permanently reserved catalog entries with former meanings.

### 7. Complete documentation and ADR closure

Update all normative documents, current initiative baselines, project status, roadmap, live diagnostics, and residual
dependent-plan wording. When implementation and tests are complete, create the next available L1 ADR, amend the existing
ADRs identified below, add the ADR-0003 related-plan link, update the ADR indexes, link the closed plan, update
initiative membership, and move this plan to `features/closed/`.

## Test Migration

The existing standalone end-to-end suite proves the opposite authority model by deleting `.l1m` files before successful
links. Rewrite it rather than incrementally preserving those assumptions:

1. Retain interfaces in every successful standalone-link case.
2. Convert interface-free linking into a missing-sibling failure.
3. Replace stale embedded-object fingerprint cases with mismatched or stale sibling-interface cases.
4. Remove the exact inspected-byte snapshot race guarantee and test original-path host invocation instead. Every renamed
   or copied `.o` used by that probe receives the correspondingly named sibling `.l1m`.
5. Invert foreign-`main` and embedded-control cases so they prove that the final host command is reached. Do not require
   host success because native behavior is platform-specific.
6. Add one central positional-object opacity case: pair a verified sibling `.l1m` with a regular positional `.o` whose
   bytes are not a native object. Use a controlled compiler-driver probe that delegates the wrapper compilation to the
   real compiler, records the final command and original object path, emits a fixed captured diagnostic, and
   deliberately fails that final command. Require `L1C-2109`, bounded cleanup, and the absence of `L1C-2097`,
   `L1C-2098`, and `L1C-2110`, without depending on platform-specific treatment of malformed bytes.
7. Cover outputs naming or hard-linked to a consumed `.l1m` and to a temporary resolved `dea_rt.h`; never use the
   repository's actual runtime header as the destructive-alias fixture.
8. Preserve wrapper-first, exact interleaved caller encounter order, runtime-native-input order, optional math argument,
   and output arguments.
9. Preserve output-local scratch isolation, bounded cleanup, direct-output behavior, and captured host diagnostics.

Migrate metadata behavior across the full test surface, not only `object_metadata_test.l0` and `object_reader_test.l0`:

- rewrite semantic portions of `link_driver_test.l0` around verified `ModuleInterface` inputs;
- revise backend and C-emitter tests to retain lifecycle/entry assertions while removing metadata arrays and anchors;
- revise compile-driver tests for regular object plus verified interface staging;
- revise parser, fingerprint, replay, driver, graph, wrapper, CLI, and checked-in `.l1m` fixtures;
- update Python standalone-link fixtures and platform paths;
- add source-entry and stable import-projection coverage to `analysis_test.l0`;
- add `module_lifecycle_test.l0` as the home for lifecycle-symbol spelling, while `analysis_test.l0` owns the shared
  source-entry predicate and stable import projection;
- add an object-level negative symbol test to `l1c_stage1_compile_only_test.py` proving that `I8metadata` and
  `I7imports` are absent, using the repository's cross-platform symbol-tool conventions or an equivalently robust
  mechanism.

Required focused coverage:

01. exact grammar region order; exact `PAR-0572` handling for a missing `entry` terminator and missing `module` or
    provider after `import`; exact `PAR-0574`, `PAR-0575`, and `PAR-0576` handling for the shared provider-expectation
    tail; exact `PAR-0578` for duplicate `entry;` and import providers; exact `PAR-0579` for nonduplicate region
    regression; `PAR-0578` precedence when a record is both duplicate and misplaced; and EOF rejection;
02. interface round-trip preserving import order;
03. first-occurrence stable deduplication from duplicate source imports;
04. side-effect-only import retention, virtual-provider omission by projection, and `SIG-0285` for a parsed persisted
    virtual provider;
05. public fingerprint unchanged by entry, import order, and dependency-manifest changes;
06. shared entry predicate emitting both `entry;` and `I5entry`, including private eligible source `main`;
07. `ifp_verify()` before identity registration, plus `SIG-0285` for an equal duplicate import in a programmatically
    constructed interface;
08. same-provider expectation agreement across imports, `require`, and `link` under `SIG-0284`, distinct from supplied
    provider mismatch under `L1C-2102`, plus `SIG-0280` and `SIG-0281` respectively for malformed and unsupported
    `module_imports` provider fingerprints;
09. valid transitive nominal provider reachable through an intermediate import;
10. `L1C-2111` for a present but import-unreachable non-virtual `require` or `link` provider;
11. `L1C-2101` for an absent non-virtual provider named by any manifest;
12. import cycles and deterministic cycle paths, plus a cycle combined with invalid entry selection proving `L1C-2104`
    precedence;
13. selected-entry-first lifecycle, source-ordered siblings, disconnected CLI roots, diamonds initialized once, and
    exact reverse finalization;
14. preservation of the iterative 10,000-module lifecycle stress case;
15. exact `.o` suffix, rejection of `.o` and `dir/.o` as empty-stem basenames and `foo.o/` as a separator-terminated
    path, path-only sibling replacement, and success for an arbitrary-basename pair whose verified sibling header
    supplies identity;
16. compile-only wrong-identity rejection; standalone `DRV-0074` for a missing sibling, `DRV-0075` using a portable
    nonregular sibling, and `DRV-0076` for invalid UTF-8; plus malformed, bad-fingerprint, exact-output-aliased, and
    hard-link-output-aliased `.l1m` failures;
17. nullable foreign-interface fields, single ownership/freeing, and no-follow wrapper substitution rejection;
18. Windows pre-allocation validation over original object paths and other then-known command values, followed by
    post-allocation validation of generated wrapper and redirection paths, with host-safe path normalization;
19. foreign objects passed without content inspection, with foreign-`main` and embedded-control probes reaching the
    host;
20. a controlled compiler-driver probe proving that a regular malformed positional Dea `.o` paired with a verified
    sibling reaches the final host command through its original path, emits captured sentinel output, fails as
    `L1C-2109` rather than a retired preflight diagnostic, and leaves no scratch transaction;
21. exact native operand encounter order and copied/renamed-object sibling handling;
22. runtime and wrapper native inputs validated without byte reads, plus `L1C-2105` for exact and hard-link aliases of a
    temporary resolved `dea_rt.h`;
23. no native object readers, snapshots, metadata arrays, or retention reads remain referenced.

Run focused Stage 1 tests during migration, then execute the clean verification literally:

```text
make -C l1 clean
make -C l1 test-all
make -C l1 test-docker
```

The clean rebuild is part of the verification contract because no compatibility discriminator is added. Supported-host
evidence additionally requires green L1 CI for Linux x86-64, macOS Intel, macOS ARM64, and Windows UCRT64.

## Completion Criteria

01. `l1c --link` never reads native object or archive bytes.
02. Every positional `.o` requires and verifies one canonical sibling `.l1m` before graph registration.
03. Each interface satisfies operational provider uniqueness, virtual-provider exclusion, and same-provider consistency;
    the complete set satisfies provider presence, supplied fingerprint, entry, import-cycle, and transitive provenance
    validation in the specified diagnostic order.
04. `require` and `link` never create lifecycle edges.
05. Import order drives the same iterative lifecycle schedule as today.
06. Generated Dea objects expose lifecycle/entry symbols but no `I8metadata` or `I7imports`.
07. Object readers, object snapshots, metadata emitters, anchors, and all emission paths and trigger tests for the
    former metadata-classification, foreign-`main`, and embedded-control diagnostics are removed; `L1C-2098`,
    `L1C-2099`, and `L1C-2110` remain permanently registered with reserved former-meaning descriptions.
08. Compile-only retains endpoint rollback without claiming object/interface binding or reader-atomic publication.
09. Standalone scratch remains isolated and bounded while final output remains direct and nontransactional.
10. Final host commands preserve wrapper, exact interleaved caller-native, runtime-native, optional math-library, and
    output-argument order.
11. CLI help, diagnostics, specifications, ADRs, Initiatives 0001 and 0003, active dependent plans, status, and roadmap
    agree with the implemented authority and trust model.
12. Clean local and Linux-container suites pass, and the Linux, macOS Intel, macOS ARM64, and Windows UCRT64 L1 CI lanes
    are green.

## ADR Impact

- Decision: Make verified sibling `.l1m` files the sole Dea semantic and lifecycle authority for standalone linking,
  with caller-trusted opaque native pairs and foreign inputs.

  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: This reverses the durable object-authority and verified-native-input boundaries in ADR-0021 and ADR-0028.
    The closing change must allocate the next available L1 ADR, supersede both records, and restate retained graph,
    entry, lifecycle, wrapper, and host-link behavior.

- Decision: Extend the module interface with entry and ordered direct lifecycle-import records.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0014-module-interface-artifact.md`
  - Rationale: The interface artifact gains operational link records while retaining the existing public declarations
    and `require`/`link` partition.

- Decision: Make canonical sibling association operational during standalone link and validate semantic providers as
  transitively reachable through ordered lifecycle imports.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0018-canonical-artifact-association-and-module-graph.md`
  - Rationale: This preserves exact source imports separately from canonical interface imports and adds the durable
    transitive lifecycle-provenance invariant.

- Decision: Keep the public-interface fingerprint domain unchanged while excluding all operational manifests.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0019-whole-module-interface-fingerprints.md`
  - Rationale: Entry, ordered imports, `require`, and `link` remain outside public compatibility, and no second link
    fingerprint is introduced.

- Decision: Retain lifecycle and entry symbols while removing metadata symbols and retention reads from the module ABI.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0020-per-module-backend-and-lifecycle-abi.md`
  - Rationale: `I4init`, `I4fini`, and conditional `I5entry` remain normative; `I8metadata`, `I7imports`, and their
    anchors are retired without replacement.

- Decision: Retain compile-only endpoint rollback while dropping staged object-metadata/interface agreement proof.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md`
  - Rationale: Publication still stages and validates the interface and regular native output, but the pair is trusted
    and sequential rather than byte-bound or reader-atomic.

- Decision: Retain output-local standalone scratch ownership while removing input snapshots and preserving direct,
  nontransactional final output.

  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0029-output-local-standalone-link-transaction.md`
  - Rationale: Wrapper/log isolation and bounded cleanup remain useful independently of exact-byte object inspection;
    original host-rendered object paths replace transaction-owned snapshots.

- Decision: Preserve `-Cf` / `--foreign-object` as the explicitly typed native-object operand for L1 standalone linking.

  - Scope: Shared
  - Disposition: Covered by ADR
  - ADR: `docs/decisions/0003-shared-cli-contract.md`
  - Rationale: ADR-0003 owns the shared option spelling, typed operand role, encounter-order contract, and
    level-extension boundary. This feature changes L1 validation authority without changing that shared CLI identity.

## Accepted Consequences and Risks

1. A mixed-generation `.o + .l1m` pair can link successfully and produce incorrect native or lifecycle behavior.
2. Dea no longer detects native-format errors, foreign `main`, reserved symbol definitions, or embedded linker controls
   before host linking.
3. Caller paths can change between interface validation and host consumption; external serialization is required.
4. Old Stage 1 interfaces may not be distinguishable from new import-free/non-entry interfaces.
5. Direct host output can be partially replaced on failure according to host-tool behavior.
6. The implementation and maintenance surface becomes materially smaller, and Stage 2 does not need native object
   readers or a duplicate semantic metadata format.

[abi]: ../../../docs/specs/compiler/abi.md
[architecture]: ../../../docs/reference/architecture.md
[backend-design]: ../../../docs/reference/c-backend-design.md
[build-run]: 2026-07-17-build-run-multi-cu-orchestration-noref.md
[c-ffi-initiative]: ../../initiatives/0003-c-ffi.md
[c-ffi-plan]: 2026-04-24-c-ffi-extern-c-and-cstr-noref.md
[cli-contract]: ../../../../docs/specs/compiler/cli-contract.md
[compile-only]: closed/2026-07-17-compile-only-artifact-production-noref.md
[design-decisions]: ../../../docs/reference/design-decisions.md
[diagnostics]: ../../../../docs/specs/compiler/diagnostic-code-catalog.md
[external-linking]: 2026-04-24-external-library-linking-cli-noref.md
[generated-c]: 2026-07-24-per-module-generated-c-mode-noref.md
[initiative]: ../../initiatives/0001-separate-compilation-and-linking.md
[interface-emission]: closed/2026-04-24-module-interface-emission-noref.md
[interface-fingerprints]: closed/2026-07-17-interface-fingerprint-canonicalization-and-verification-noref.md
[interface-format]: ../../../docs/specs/compiler/module-interface-format.md
[lifecycle]: closed/2026-07-17-per-module-backend-and-lifecycle-entrypoints-noref.md
[link-hardening]: ../bug-fixes/closed/2026-07-27-stage1-standalone-link-hardening-noref.md
[link-set]: closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[module-visibility]: ../../../docs/specs/compiler/module-visibility-and-imports.md
[object-metadata]: closed/2026-07-17-object-metadata-emission-and-readers-noref.md
[project-status]: ../../../docs/project-status.md
[roadmap]: ../../../docs/roadmap.md
[separate-compilation]: ../../../docs/reference/separate-compilation.md
