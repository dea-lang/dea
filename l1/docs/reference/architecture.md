# L1 Compiler Architecture

Version: 2026-09-01

This is the canonical architecture document for the current Dea/L1 bootstrap compiler.

Today there is one implemented compiler pipeline:

- `compiler/stage1_l0/` contains the runnable L1 compiler implemented in Dea/L0.
- `compiler/stage2_l1/` is reserved for the future self-hosted compiler and is not implemented yet.
- `compiler/shared/l1/stdlib/` and `compiler/shared/runtime/` are the current copied stdlib/runtime source inputs
  consumed by the bootstrap toolchain.
- `build/dea/include/` and `build/dea/lib/` are the repo-local runtime delivery outputs consumed by Stage 1.
  Compile-only needs the headers but does not link the runtime archive; standalone link needs the public header and
  selected runtime link inputs.

Related canonical docs:

- Backend lowering and generated C details: [c-backend-design.md](c-backend-design.md)
- Separate-compilation and standalone-link behavior:
  [l1/docs/reference/separate-compilation.md](separate-compilation.md)
- Language/runtime rationale and policy: [design-decisions.md](design-decisions.md)
- Bootstrap status snapshot: [l1/docs/project-status.md](../project-status.md)
- Shared CLI behavior: [docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md)
- External native-library workflow: [l1/docs/user/linking.md](../user/linking.md)

## 1. High-Level Pipeline

### 1.1 Current Implemented Pipeline

```
Source (.l1)
  |
  v
lexer.l0 -> Token stream
  |
  v
parser.l0 -> AST
  |
  v
driver.l0 + module_graph.l0 -> deterministic source/interface module graph
  |
  v
name_resolver.l0 -> ModuleEnv per module
  |
  v
signatures.l0 -> func/struct/enum/let type tables
  |
  v
locals.l0 -> FunctionEnv per function
  |
  v
expr_types.l0 -> typed AnalysisResult + semantic diagnostics
  |
  +-- `--emit-interface` --> interface projection + canonical fingerprint --> textual `.l1m`
  |
  +-- `--gen` --> source target + interface-first/source-fallback imports
  |                  |
  |                  v
  |          backend_generate_module --> stdout or one exact C file
  |
  +-- `--compile` --> one source-backed module + interface-backed imports
  |                         |
  |                         v
  |          backend_generate_module --> module-relative host compilation
  |                         |
  |                         v
  |                  `.o` / `.l1m` publication with endpoint rollback
  |                  (`--keep-c` also publishes `.c`)
  |
  +-- `--build` / `--run` --> source/interface graph in private workspace
                                    |
                                    v
                         backend_generate_module once per source node
                                    |
                                    v
                    staged `.c` / `.o` / `.l1m` + opaque provider `.o`
                                    |
                                    v
                         common verified link plan + wrapper
                                    |
                                    v
                          host link / optional direct launch
```

The interface-authoritative standalone-link path is:

```text
Positional foo.o
  |
  v
derive sibling foo.l1m --> UTF-8 parse + ifp_verify
  |
  v
verified identity + entry + ordered lifecycle imports + provider expectations
  |
  v
link_driver.l0 --> graph/fingerprint/entry/provenance validation --> wrapper_emitter.l0
                                                        |
                                                        v
                         original opaque native paths --> host C compiler/linker
```

Internal analysis entry points can build a deterministic `ModuleGraph` from an entry source, ordered interface roots, a
resolution policy, and an optional artifact root. The entry stays source-backed. Imported modules prefer the first
matching `.l1m`; `MRP_REQUIRE_INTERFACE` rejects a missing interface, while `MRP_ALLOW_SOURCE_FALLBACK` retains the
existing source-root precedence when no interface exists. Programmatic interface registries use the same graph model.

The driver closes over both interface dependency tiers. `require` providers are activated for semantic replay, while
`link` providers remain graph obligations without entering the consumer's semantic environment. Source nodes retain
their direct imports in exact declaration order with duplicates. Interface projection independently emits a
first-occurrence, virtual-filtered ordered lifecycle-import view. Build/run expands the source target with
`MRP_ALLOW_SOURCE_FALLBACK`; compile-only requires verified interfaces for non-virtual imports.

Ordinary `--build` and `--run` validate the source target before reserving one command-owned temporary workspace, then
analyze the complete graph with workspace-backed canonical artifacts. Source-backed nodes compile once in deterministic
dependency order. Before generation, each source node is re-analyzed as a one-module entry with non-virtual imports
required to resolve from the original authoritative interface roots or already staged workspace `.l1m` files.
Interface-backed nodes contribute verified manifests plus original opaque sibling objects. The driver registers
generated C, objects, interfaces, captures, wrapper artifacts, and the temporary run executable, and keeps the workspace
alive through child execution. Caller-selected executables and retained `.dea-c` trees remain outside. Bounded no-follow
cleanup removes only registered regular files and known nested directories; unexpected or substituted contents retain
the workspace and report `L1C-9514`. Temporary-parent inspection, setup, canonical trust, or exclusive-reservation
failure reports `L1C-9513` and does not fall through to a later candidate. Cleanup changes success to status 1 but
preserves an already nonzero compilation, launch, or child-program result. Workspace and fixed-child construction uses
an actual-host filesystem primitive, so POSIX treats a trailing `\` in the canonical parent as a literal filename byte
rather than as permission to allocate a sibling path.

The internal module-generation branch selects one canonical source-backed target from the completed analysis result. It
emits target definitions, external declarations for provider-owned source and interface values and functions consumed by
that target, always-present external `I4init` and `I4fini`, and conditional external `I5entry`. It emits no process
`main`, global init chain, dependency lifecycle calls, `I8metadata`, `I7imports`, replacement anchors, or retention
reads. Compile-only connects this branch to host object compilation and sequential artifact publication with endpoint
rollback. Standalone link consumes verified sibling `.l1m` files for Dea semantics and passes the paired native objects
opaquely to the host. Build/run now supplies the same planner with its graph-expanded object set, explicit source-target
entry, and wrapper/capture paths owned by the command workspace.

Every selected filesystem or registry interface is checked before it enters that graph. The driver parses the wire
model, confirms the declared module identity, validates the module and dependency fingerprint envelopes, recomputes the
whole-module SipHash-1-3 fingerprint, and rejects a mismatch before registration, normalization, activation, or semantic
replay. Source projection computes its own fingerprint from the exported surface, then fills each dependency entry with
the corresponding provider module fingerprint; dependency records do not feed back into the consumer's own digest.

Current CLI entry point: `compiler/stage1_l0/src/l1c.l0`.

The CLI implements `--gen` and `-c` / `--compile` with repeatable `-I` / `--interface-path` roots. Generated-C resolves
one source-backed target, prefers selected interfaces for imports, falls back to source only when no interface is
selected, and emits one module to stdout or an exact output file without host compilation. Compile-only requires
verified interfaces for non-virtual imports and publishes the sibling `.o` and `.l1m` pair without linking. `--keep-c`
adds C bytes identical to `--gen` under the same resolved inputs and options. L1 follows the shared exact-token short
namespaces for roots, host-C controls, runtime paths, generated C, and log presentation. Canonical debug/assembly flags
remain reserved; external `-l`, `-L`, `-Rr` / `--rpath`, and `-Cl` / `--link-arg` controls are implemented only in
build, run, and standalone link.

Compile-only follows trusted directory aliases while validating and recursively creating the destination parent.
Dangling and non-directory aliases are rejected. Final `.c`, `.o`, and `.l1m` destinations and transaction, backup,
validation, and cleanup paths retain no-follow classification, so artifact symlinks are rejected.

The driver reserves one exclusive transaction directory beside the requested destinations. Generated C, the object, the
interface, and any backups of selected destinations remain on the same filesystem so publication and rollback use
sequential renames. Staged artifact names follow the canonical module-relative path, and the host compiler runs from the
transaction root with those stable relative C/object arguments, after freezing a bare compiler to its absolute
invocation-time command-search result. For debug-producing GNU-style options, the driver classifies Clang or GCC from
the configured name or canonical filesystem target while retaining the selected alias for invocation. Conventional
target, version, and MinGW thread-model suffixes are recognized; Darwin's standard Clang-backed `gcc` and `cc` hard
links are recognized by filesystem identity. Clang receives a stable debug compilation directory; GCC receives a
private-root prefix mapping and, on Darwin, forwards the stable compilation directory to Apple's external assembler so
relative `.file` entries are not expanded against the transaction root. These controls exclude driver-owned transaction
and destination paths but do not guarantee byte-identical host objects. Successful return leaves the complete new
selected set, and a recoverable publication failure returns with the exact prior set restored. During publication or
rollback, paths may be absent or from different generations; this is not a reader-visible snapshot, and concurrent
readers or same-stem writers require external serialization.

Without `--keep-c`, destination validation and publication never inspect or modify the canonical `.c` path. A successful
rollback reports a publication failure; if rollback itself fails, the compiler retains recovery files and reports
`L1C-2036` instead of discarding them. Cleanup is deliberately non-recursive: an auxiliary file requested through raw
host-C options is reported and retained with the transaction directory rather than silently removed.

The CLI also implements standalone
`l1c -k DEA_OBJECT... [-Cf C_OBJECT]... [-l LIBRARY]... [-L DIRECTORY]... [-Rr RPATH]... [-Cl LINK_ARG]... [-e MODULE] -o OUTPUT`.
For each exact positional `.o`, the driver derives and fully verifies the sibling `.l1m` before registering identities.
It verifies unique modules, provider presence and public fingerprints, entry selection, lifecycle-import cycles, and
transitive lifecycle provenance for semantic providers. `require` and `link` never create lifecycle edges. Dea and
foreign native bytes remain opaque; `--foreign-object` is a caller assertion rather than a content classification.

After validation, `link_driver.l0` records one deterministic dependency-first lifecycle order through an explicit
depth-first frame stack. It traverses the selected entry component first in interface import order, then visits
unvisited explicitly supplied Dea roots in positional order without consuming the native call stack.
`wrapper_emitter.l0` defines process `main`, initializes runtime arguments, calls every `I4init` in that order, calls
only the selected `I5entry`, and calls every `I4fini` in reverse. The plan retains a single encounter-ordered stream of
Dea objects, foreign objects, libraries, search paths, rpaths, and raw host-driver words. Only Dea inputs participate in
interface and lifecycle state; all other entries receive no generated calls.

Standalone link validates the compiler, runtime inputs, exact `dea_rt.h`, output parent, final output kind, and original
caller paths before reserving scratch state. Its exclusively created `.l1c-link-...` transaction sits beside the output
and owns only fixed wrapper and captured-output files. The host link consumes original caller native paths in typed
encounter order; there are no snapshots or exact-byte race claim. Cleanup removes only registered regular children
without following aliases and then removes the verified empty directory. Cleanup failure is result-bearing and retains
the bounded transaction, while the host linker writes directly to the caller-selected output. Output aliases of a caller
native input, consumed interface, runtime input, or resolved header are rejected before allocation. Native Windows also
rejects `%`, `!`, literal `"`, carriage-return, and line-feed bytes in parsed command words and redirection paths
because the current host-tool transport passes through `cmd.exe`; the exact rendered commands and capture paths are
checked again immediately before execution.

Raw link arguments are validated during CLI parsing: object-suffixed library/raw inputs must use a typed object role,
and response, file-list, or driver-config indirection is unavailable. Compiler-dependent rpath validation completes
before host compilation; recognized GCC and Clang driver names plus exact `cc` use repeated `-Xlinker` words, TinyCC
uses `-Wl,-rpath=...`, and unsupported or Windows combinations fail. Final linking emits the wrapper, the complete user
stream in place, exact selected runtime inputs, the ordinary non-MSVC math-library argument, and output controls in that
order.

Normal developer workflow:

```bash
make use-dev-stage1
source build/dea/bin/l1-env.sh
l1c --help
```

`make use-dev-stage1` auto-prepares the default repo-local upstream `../l0/build/dea/bin/l0c-stage2` when needed.

## 2. Pass Responsibilities

All current implementation modules live under `compiler/stage1_l0/src/`.

### 2.1 Lexer (`lexer.l0`, `tokens.l0`)

- Converts UTF-8 source text to token streams.
- Uses `builtin_types.l0` as the compiler-wide authority for builtin token reservation, parser type lookahead, and
  semantic type construction.
- Tracks source locations for diagnostics; columns count Unicode code points.
- Recognizes keywords, literals, punctuation, and operators.
- Keeps string source-body spelling separate from the decoded token value. Scalar `\x`, `\u`, and `\U` escapes
  contribute UTF-8 bytes, octal escapes remain byte-oriented, and invalid Unicode scalar values are rejected by the
  lexer. Semantic and interface consumers use the decoded value rather than reinterpreting source spelling.
- Wraps recoverable lexer diagnostics in `TT_LEXER_ERROR` tokens with optional logical recovery payloads.
  Invalid-character runs (`LEX-0040`) have no recovery payload and are skipped logically; malformed literals and numeric
  diagnostics recover as literal tokens where possible.

### 2.2 Parser (`parser.l0`, `ast.l0`)

- Produces the current AST for modules, declarations, statements, and expressions.
- Reads tokens through logical accessors: wrappers with recovery behave as the recovered token, wrappers without
  recovery are skipped, and each wrapped lexer diagnostic is emitted once.
- Enforces statement-vs-expression syntax boundaries such as assignment remaining statement-only.

### 2.3 Name Resolution (`name_resolver.l0`, `symbols.l0`)

- Builds module environments across the import closure.
- Populates selected provider environments from interfaces activated by the module graph.
- Resolves opened imports and reports ambiguity diagnostics.

### 2.4 Signature Resolution (`signatures.l0`, `type_resolve.l0`, `types.l0`)

- Resolves top-level type references.
- Populates function, struct, enum, and top-level binding type tables.
- Detects alias and type-dependency cycles.
- Finalizes semantic type trees after signature replay, materializing nominal kinds and transparent aliases across
  interface- and source-backed providers while preserving the parsed spelling in graph and projection interfaces.
- Validates each resolved interface surface against its own semantic `require` closure, following interface `require`
  edges and source direct imports but excluding `link` edges; violations report `RES-0040`.

### 2.5 Local Resolution (`locals.l0`, `scope_context.l0`, `sem_context.l0`)

- Builds per-function lexical scope state.
- Tracks local bindings and control-flow-sensitive semantic context.

### 2.6 Expression Typing (`expr_types.l0`)

- Checks expression and statement typing.
- Validates return-path and cleanup-path requirements.
- Enforces imported opaque layout visibility at the common expression-result boundary, preserving pointer-only handles
  while suppressing or deduplicating diagnostics during loop fixed-point and repeated ordinary inference.
- Produces semantic diagnostics without crashing the compiler.

### 2.7 Interface Projection (`interface_emitter.l0`, `interface_fingerprint.l0`, `interface_literal.l0`, `interface_order.l0`, `module_interface.l0`, `mi_utils.l0`)

- Projects exported declarations from a completed analysis result.
- Canonicalizes the exported surface and assigns its tagged whole-module fingerprint.
- Reuses `util/numbers.l0` for canonical integer text: the shared builtin range table bounds the implemented `long` /
  `ulong` domain before decimal normalization or bounded non-decimal multiply-add conversion.
- Collects one vector of borrowed declaration references and stable-sorts it by kind and name with an iterative
  bottom-up merge sort. Text emission and fingerprinting consume that same `O(N log N)` ordering, while freeing the
  wrappers never changes declaration ownership.
- Validates and measures recursive type payloads once into a checked preorder size plan, then streams the second pass
  directly using cached child sizes. Size overflow reports `SIG-0283`; no arbitrary type-depth limit is introduced.
- Classifies resolved cross-module symbol uses into public-surface `require` and implementation-tier `link` records.
- Derives `has_entry` and a stable first-occurrence, virtual-filtered ordered `module_imports` view from shared source
  semantics without changing exact source-import storage.
- Populates each dependency entry with its provider module's tagged fingerprint.
- Validates operational provider uniqueness, virtual-provider exclusion, and same-provider fingerprint consistency
  across module imports, `require`, and `link`.
- Emits deterministic textual `.l1m` artifacts through the internal `--emit-interface` mode.
- Parses the constrained interface grammar and verifies operational inputs before graph-backed internal replay.

### 2.8 Backend (`backend.l0`, `c_emitter.l0`, `string_escape.l0`)

- Consumes typed analysis results exclusively through the target-aware `backend_generate_module` API for every public
  generated-C, compile-only, build, and run path.
- Keeps module definitions scoped to the selected source-backed target while declaring imported source and interface
  values and functions under provider-owned names.
- Emits external per-module `I4init` / `I4fini` lifecycle functions and an optional external `I5entry` bridge without
  process-wrapper or cross-module orchestration.
- Preserves identical module C bytes across all four producer modes for identical semantic and code-generation inputs;
  build/run retain the exact staged compiler inputs while the standalone wrapper remains a separate artifact.
- Delegates backend-specific behavior to [c-backend-design.md](c-backend-design.md).

### 2.9 Module Lifecycle and Standalone Link (`module_lifecycle.l0`, `link_driver.l0`, `wrapper_emitter.l0`)

- Constructs canonical `I4init`, `I4fini`, and `I5entry` symbols without an object-metadata subsystem.
- Owns typed link inputs containing native paths or external driver controls plus optional verified Dea interfaces.
- Parses and verifies every sibling interface before identity registration.
- Validates provider presence, supplied interface fingerprints, entry, lifecycle cycles, and transitive provenance.
- Computes one nonrecursive deterministic lifecycle order and emits the process wrapper.
- Lowers external controls in place and passes caller/runtime native inputs opaquely in the documented order.

### 2.10 Driver and CLI (`driver.l0`, `l1c_lib.l0`, `cli_args.l0`, `build_driver.l0`)

- Coordinates the pass pipeline.
- Builds and exposes the deterministic module graph, canonical artifact associations, and active cloned interfaces.
- Exposes resolution-aware internal entry points with ordered interface roots, caller-selected source fallback, and an
  optional artifact root.
- Implements CLI mode dispatch and host compiler execution.
- Uses `compiler_filesystem.l0` as the internal filesystem boundary shared by native build/run workspace management,
  compile-only transactions, and standalone-link transactions.
- Implements compile-only interface resolution, object-only host compilation, and artifact publication with endpoint
  rollback.
- Implements build/run graph expansion, publication-free per-module compilation, common-link reuse, exact retained-C
  trees, and direct run-process invocation.
- Validates external-link option scope and raw-argument roles, and expands only the build/run Dea target inside the
  ordered link stream.
- Produces generated C, module artifacts, built executables, or direct runs depending on CLI mode.

## 3. Core Data Flow

Primary aggregates in the current implementation include:

- token streams from `tokens.l0`
- parsed AST nodes from `ast.l0`
- parsed and active module interfaces from `module_interface.l0`
- `ModuleGraph`, `ModuleGraphNode`, `ModuleOrigin`, `ModuleDependency`, and `ModuleArtifactPaths` from `module_graph.l0`
- module and symbol environments from `name_resolver.l0`
- typed semantic state from `analysis.l0`
- projected module interfaces carrying `has_entry`, ordered `module_imports`, and populated `require` / `link` tiers
- typed standalone inputs containing original native paths and optional verified sibling interfaces
- checked scalar constant values evaluated through `type_resolve.l0`

Important analysis tables include:

- `module_envs`
- `func_types`
- `struct_infos`
- `enum_infos`
- `func_envs`
- `let_types`
- `expr_types`
- `var_ref_resolution`
- `resolved_symbols`
- `intrinsic_targets`
- `diagnostics`

## 4. Invariants

01. The current L1 compiler is bootstrap-only and implemented in Dea/L0.
02. Import closure construction is explicit and checked before later semantic passes; each canonical module has one
    source, interface, registry, or virtual origin in the module graph.
03. Source locations are propagated for diagnostics.
04. Diagnostic columns follow a logical-source contract: every non-newline Unicode code point, including ASCII
    horizontal tabs, advances the stored column by exactly one; UTF-8 continuation bytes do not advance it. Snippet
    rendering normalizes displayed source lines to the same model (each tab is printed as a single space) so the caret
    underline and the displayed line always agree, independent of terminal tab-stop behavior. Unicode display-width
    handling is out of scope for this contract.
05. Semantic failures are reported as diagnostics rather than internal crashes on normal invalid input paths.
06. Build/run, `--gen`, and compile-only use the same internal module API. Build/run emits one translation unit per
    source-backed graph node in one private command-lifetime workspace; standalone link consumes explicit objects plus
    their required sibling interfaces.
07. Interface emission, graph enumeration, and artifact association are deterministic. Direct source-import edges
    preserve declaration order and duplicates.
08. An interface is registered or cached only after its declared identity and whole-module fingerprint are verified.
09. `.l1m` artifacts are normal compile-only, build/run, and standalone-link inputs and are the sole Dea
    semantic/lifecycle authority for every interface-backed native object.
10. Native caller and runtime inputs are opaque. Standalone link performs no object-format, symbol, metadata, or
    embedded-control inspection.
11. Compile-only publishes `.o` and `.l1m` as its reusable artifact set and adds `.c` only with `--keep-c`. Successful
    return leaves the complete new selected set; recoverable failure leaves or restores the exact prior set; failed
    rollback retains recovery files. Sequential publication does not provide a reader-visible snapshot or byte binding.
12. Standalone link accepts Dea semantics only from verified sibling interfaces; paired objects and explicit foreign
    inputs remain caller-trusted native payloads.
13. Standalone wrapper initialization is dependency-first and deterministic; finalization is its exact reverse. The
    selected entry bridge is the only Dea entry invoked, and the wrapper owns process `main`.
14. External host dependencies are explicit CLI/build-tool inputs, not module identities or `.l1m` dependency metadata.
    The selected runtime follows the user stream by exact path.
15. Any future `stage2_l1` implementation should match the public L1 language/runtime behavior documented here and in
    the other L1 reference documents.

## 5. File/Module Layout

Main current compiler modules under `compiler/stage1_l0/src/`:

- `analysis.l0`
- `ast.l0`
- `ast_printer.l0`
- `backend.l0`
- `build_driver.l0`
- `build_info.l0`
- `cli_args.l0`
- `codegen_options.l0`
- `compiler_filesystem.l0`
- `dea_prelude.l0`
- `diag_print.l0`
- `driver.l0`
- `expr_types.l0`
- `interface_emitter.l0`
- `interface_fingerprint.l0`
- `interface_literal.l0`
- `interface_order.l0`
- `l1c.l0`
- `l1c_lib.l0`
- `lexer.l0`
- `link_driver.l0`
- `locals.l0`
- `mi_utils.l0`
- `module_lifecycle.l0`
- `module_graph.l0`
- `module_interface.l0`
- `name_resolver.l0`
- `parser.l0`
- `parser/decl.l0`, `parser/expr.l0`, `parser/interface.l0`, `parser/shared.l0`, and `parser/stmt.l0`
- `scope_context.l0`
- `sem_context.l0`
- `signatures.l0`
- `source_paths.l0`
- `string_escape.l0`
- `symbols.l0`
- `tokens.l0`
- `type_resolve.l0`
- `types.l0`
- `wrapper_emitter.l0`

Shared support modules live under `compiler/stage1_l0/src/util/`.

The L1-owned Stage 1 support translation unit under `compiler/stage1_l0/support/` supplies the small compiler-private C
ABIs used for interface fingerprinting, canonical native temporary-parent validation, build/run workspace operations,
compile-only publication, and standalone-link transaction filesystem operations. `compiler_filesystem.l0` is the single
compiler-facing wrapper for the filesystem primitives; none of them extends the public runtime or standard library.

## 6. Host and Toolchain Assumptions

- Source decoding is UTF-8 with optional BOM stripping; the shared language vocabulary remains ASCII-only. See
  [docs/specs/language/source-text-and-language-vocabulary.md](../../../docs/specs/language/source-text-and-language-vocabulary.md).
- L1 source modules use the `.l1` extension.
- The bootstrap compiler implementation remains `.l0` source code.
- `--compile`, `--link`, `--build`, and `--run` require a host C99 toolchain.
- Local bootstrap builds use `../l0/build/dea/bin/l0c-stage2` by default unless overridden with `L1_BOOTSTRAP_L0C`.
