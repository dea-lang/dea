# L1 Compiler Architecture

Version: 2026-07-26

This is the canonical architecture document for the current Dea/L1 bootstrap compiler.

Today there is one implemented compiler pipeline:

- `compiler/stage1_l0/` contains the runnable L1 compiler implemented in Dea/L0.
- `compiler/stage2_l1/` is reserved for the future self-hosted compiler and is not implemented yet.
- `compiler/shared/l1/stdlib/` and `compiler/shared/runtime/` are the current copied stdlib/runtime source inputs
  consumed by the bootstrap toolchain.
- `build/dea/include/` and `build/dea/lib/` are the repo-local runtime delivery outputs consumed by Stage 1.
  Compile-only needs the headers but does not link the runtime archive.

Related canonical docs:

- Backend lowering and generated C details: [c-backend-design.md](c-backend-design.md)
- Language/runtime rationale and policy: [design-decisions.md](design-decisions.md)
- Bootstrap status snapshot: [l1/docs/project-status.md](../project-status.md)
- Shared CLI behavior: [docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md)

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
  +-- internal module API --> backend_generate_module --> one selected module C99 translation unit
  |
  +-- `--compile` --> one source-backed module + interface-backed imports
  |                         |
  |                         v
  |                  `.o` / `.l1m` publication with endpoint rollback
  |                  (`--keep-c` also publishes `.c`)
  |
  +-- `--gen` / `--build` / `--run` --> backend_generate --> legacy whole-program C99 translation unit
                                          |
                                          v
                                   build_driver.l0 --> host C compiler / executable launch
```

The implemented object-inspection path is independent of CLI dispatch:

```text
Relocatable object
  |
  v
object_reader.l0
  |
  +--> object_reader_elf.l0
  +--> object_reader_macho.l0
  +--> object_reader_pecoff.l0
  |
  v
Container format + defined symbols + Dea metadata classification
```

Internal analysis entry points can build a deterministic `ModuleGraph` from an entry source, ordered interface roots, a
resolution policy, and an optional artifact root. The entry stays source-backed. Imported modules prefer the first
matching `.l1m`; `MRP_REQUIRE_INTERFACE` rejects a missing interface, while `MRP_ALLOW_SOURCE_FALLBACK` retains the
existing source-root precedence when no interface exists. Programmatic interface registries use the same graph model.

The driver closes over both interface dependency tiers. `require` providers are activated for semantic replay, while
`link` providers remain graph obligations without entering the consumer's semantic environment. Source nodes retain
their direct imports in declaration order, separately from sorted graph enumeration and interface manifests. The
ordinary build/run CLI pipeline above is still source-based; compile-only instead requires verified interfaces for
non-virtual imports.

The internal module-generation branch selects one canonical source-backed target from the completed analysis result. It
emits target definitions, external declarations for provider-owned source and interface values and functions consumed by
that target, external `I8metadata` and `I7imports` records, always-present external `I4init` and `I4fini`, and
conditional external `I5entry`. It emits no process `main`, global init chain, or dependency lifecycle calls.
Compile-only connects this branch to host object compilation and sequential artifact publication with endpoint rollback.
Multi-CU build/run dispatch remains a future tranche.

The format-neutral object reader classifies a supported relocatable object as valid Dea metadata, no Dea metadata, or
malformed Dea metadata. File access failures and unsupported or corrupt containers are separate object-read errors. The
reader also exposes exact defined-symbol lookup for the later link-set tranche. It does not invoke host inspection tools
or reinterpret a malformed Dea object as foreign-compatible absence.

Every selected filesystem or registry interface is checked before it enters that graph. The driver parses the wire
model, confirms the declared module identity, validates the module and dependency fingerprint envelopes, recomputes the
whole-module SipHash-1-3 fingerprint, and rejects a mismatch before registration, normalization, activation, or semantic
replay. Source projection computes its own fingerprint from the exported surface, then fills each dependency entry with
the corresponding provider module fingerprint; dependency records do not feed back into the consumer's own digest.

Current CLI entry point: `compiler/stage1_l0/src/l1c.l0`.

The CLI implements `-c` / `--compile` with repeatable `-I` / `--interface-path` roots. It resolves one source-backed
target, requires verified interfaces for non-virtual imports, and publishes the sibling `.o` and `.l1m` pair without
linking. `--keep-c` adds the exact generated `.c` used for host compilation. L1 follows the shared exact-token short
namespaces for roots, host-C controls, runtime paths, generated C, and log presentation; reserved canonical
debug/assembly/link flags report `L1C-2032` rather than acquiring L1-specific meanings.

Compile-only follows trusted directory aliases while validating and recursively creating the destination parent.
Dangling and non-directory aliases are rejected. Final `.c`, `.o`, and `.l1m` destinations and transaction, backup,
validation, and cleanup paths retain no-follow classification, so artifact symlinks are rejected.

The driver reserves one exclusive transaction directory beside the requested destinations. Generated C, the object, the
interface, and any backups of selected destinations remain on the same filesystem so publication and rollback use
sequential renames. Successful return leaves the complete new selected set, and a recoverable publication failure
returns with the exact prior set restored. During publication or rollback, paths may be absent or from different
generations; this is not a reader-visible snapshot, and concurrent readers or same-stem writers require external
serialization.

Without `--keep-c`, destination validation and publication never inspect or modify the canonical `.c` path. A successful
rollback reports a publication failure; if rollback itself fails, the compiler retains recovery files and reports
`L1C-2036` instead of discarding them. Cleanup is deliberately non-recursive: an auxiliary file requested through raw
host-C options is reported and retained with the transaction directory rather than silently removed.

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
- Populates each dependency entry with its provider module's tagged fingerprint.
- Emits deterministic textual `.l1m` artifacts through the internal `--emit-interface` mode.
- Parses the constrained interface grammar and verifies operational inputs before graph-backed internal replay.

### 2.8 Backend (`backend.l0`, `c_emitter.l0`, `string_escape.l0`)

- Consumes typed analysis results through the legacy `backend_generate` whole-program API or the target-aware
  `backend_generate_module` API.
- Keeps module definitions scoped to the selected source-backed target while declaring imported source and interface
  values and functions under provider-owned names.
- Emits external per-module `I4init` / `I4fini` lifecycle functions and an optional external `I5entry` bridge without
  process-wrapper or cross-module orchestration.
- Delegates backend-specific behavior to [c-backend-design.md](c-backend-design.md).

### 2.9 Object Metadata and Readers (`object_metadata.l0`, `object_reader*.l0`)

- Encodes and decodes the fixed version 1 identity and ordered-import records.
- Converts verified `sip13:` interface fingerprints to and from their raw little-endian 64-bit representation.
- Reads bounded section, symbol, and string tables from supported ELF, Mach-O, and standard COFF relocatable objects.
- Applies only exact format-specific aliases: Darwin TinyCC ELF `___dea...` / `_main`, one Mach-O or COFF I386 leading
  underscore, and one leading `#` on COFF ARM64EC function symbols.
- Resolves metadata arrays through their defining sections with checked offset, count, and length arithmetic.
- Validates metadata/lifecycle/entry consistency and exposes exact defined-symbol lookup.

### 2.10 Driver and CLI (`driver.l0`, `l1c_lib.l0`, `cli_args.l0`, `build_driver.l0`)

- Coordinates the pass pipeline.
- Builds and exposes the deterministic module graph, canonical artifact associations, and active cloned interfaces.
- Exposes resolution-aware internal entry points with ordered interface roots, caller-selected source fallback, and an
  optional artifact root.
- Implements CLI mode dispatch and host compiler execution.
- Implements compile-only interface resolution, object-only host compilation, and artifact publication with endpoint
  rollback.
- Produces generated C, module artifacts, built executables, or direct runs depending on CLI mode.

## 3. Core Data Flow

Primary aggregates in the current implementation include:

- token streams from `tokens.l0`
- parsed AST nodes from `ast.l0`
- parsed and active module interfaces from `module_interface.l0`
- `ModuleGraph`, `ModuleGraphNode`, `ModuleOrigin`, `ModuleDependency`, and `ModuleArtifactPaths` from `module_graph.l0`
- module and symbol environments from `name_resolver.l0`
- typed semantic state from `analysis.l0`
- projected module interfaces carrying populated `require` and `link` dependency tiers
- encoded module identity and ordered-import records from `object_metadata.l0`
- format-neutral object information and metadata classifications from `object_reader.l0`
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
06. Ordinary build/run CLI generation remains one legacy whole-program C99 translation unit; compile-only uses the
    internal module API to emit one selected source-backed module translation unit.
07. Interface emission, graph enumeration, and artifact association are deterministic. Direct source-import edges
    preserve declaration order and duplicates.
08. An interface is registered or cached only after its declared identity and whole-module fingerprint are verified.
09. `.l1m` artifacts are normal compile-only dependency inputs but are not consumed by `--build` or `--run` yet.
10. The entire normalized `__dea` prefix is reserved; a supported relocatable object with any external definition under
    that prefix cannot be classified as metadata-free, even when the suffix is not valid LBI.
11. Object readers check all container and record bounds before slicing or allocating and never invoke host inspection
    commands.
12. Compile-only publishes `.o` and `.l1m` as its reusable artifact set and adds `.c` only with `--keep-c`. Successful
    return leaves the complete new selected set; recoverable failure leaves or restores the exact prior set; failed
    rollback retains recovery files. Sequential publication does not provide a reader-visible snapshot.
13. Any future `stage2_l1` implementation should match the public L1 language/runtime behavior documented here and in
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
- `locals.l0`
- `mi_utils.l0`
- `module_graph.l0`
- `module_interface.l0`
- `name_resolver.l0`
- `object_metadata.l0`
- `object_reader.l0`
- `object_reader_elf.l0`
- `object_reader_macho.l0`
- `object_reader_pecoff.l0`
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

Shared support modules live under `compiler/stage1_l0/src/util/`.

The L1-owned Stage 1 support translation unit under `compiler/stage1_l0/support/` supplies the small allocation-free C
ABIs used for interface fingerprinting and compile-only publication filesystem operations.

## 6. Host and Toolchain Assumptions

- Source decoding is UTF-8 with optional BOM stripping; the shared language vocabulary remains ASCII-only. See
  [docs/specs/language/source-text-and-language-vocabulary.md](../../../docs/specs/language/source-text-and-language-vocabulary.md).
- L1 source modules use the `.l1` extension.
- The bootstrap compiler implementation remains `.l0` source code.
- `--compile`, `--build`, and `--run` require a host C99 toolchain.
- Local bootstrap builds use `../l0/build/dea/bin/l0c-stage2` by default unless overridden with `L1_BOOTSTRAP_L0C`.
