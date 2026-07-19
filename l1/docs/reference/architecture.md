# L1 Compiler Architecture

Version: 2026-07-19

This is the canonical architecture document for the current Dea/L1 bootstrap compiler.

Today there is one implemented compiler pipeline:

- `compiler/stage1_l0/` contains the runnable L1 compiler implemented in Dea/L0.
- `compiler/stage2_l1/` is reserved for the future self-hosted compiler and is not implemented yet.
- `compiler/shared/l1/stdlib/` and `compiler/shared/runtime/` are the current copied stdlib/runtime source inputs
  consumed by the bootstrap toolchain.
- `build/dea/include/` and `build/dea/lib/` are the repo-local runtime delivery outputs consumed by Stage 1 `--build` /
  `--run`.

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
  +-- `--emit-interface` --> interface_emitter.l0 + module_interface.l0 --> textual `.l1m`
  |
  +-- `--gen` / `--build` / `--run` --> backend.l0 + c_emitter.l0 --> single C99 translation unit
                                          |
                                          v
                                   build_driver.l0 --> host C compiler / executable launch
```

Internal analysis entry points can build a deterministic `ModuleGraph` from an entry source, ordered interface roots, a
resolution policy, and an optional artifact root. The entry stays source-backed. Imported modules prefer the first
matching `.l1m`; `MRP_REQUIRE_INTERFACE` rejects a missing interface, while `MRP_ALLOW_SOURCE_FALLBACK` retains the
existing source-root precedence when no interface exists. Programmatic interface registries use the same graph model.

The driver closes over both interface dependency tiers. `require` providers are activated for semantic replay, while
`link` providers remain graph obligations without entering the consumer's semantic environment. Source nodes retain
their direct imports in declaration order, separately from sorted graph enumeration and interface manifests. The
ordinary CLI pipeline above is still source-based.

Current CLI entry point: `compiler/stage1_l0/src/l1c.l0`.

The CLI parser reserves `-c` / `--compile` and repeatable `-I` / `--interface-path` values for separate compilation, but
dispatch currently reports `L1C-9510` before analysis or artifact creation. A later compile-only tranche connects that
surface to the internal resolver and transactional artifact writer. L1 follows the shared exact-token short namespaces
for roots, host-C controls, runtime paths, generated C, and log presentation; reserved canonical debug/assembly/link
flags report `L1C-2032` rather than acquiring L1-specific meanings.

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

### 2.5 Local Resolution (`locals.l0`, `scope_context.l0`, `sem_context.l0`)

- Builds per-function lexical scope state.
- Tracks local bindings and control-flow-sensitive semantic context.

### 2.6 Expression Typing (`expr_types.l0`)

- Checks expression and statement typing.
- Validates return-path and cleanup-path requirements.
- Produces semantic diagnostics without crashing the compiler.

### 2.7 Interface Projection (`interface_emitter.l0`, `module_interface.l0`, `mi_utils.l0`)

- Projects exported declarations from a completed analysis result.
- Classifies resolved cross-module symbol uses into public-surface `require` and implementation-tier `link` records.
- Emits deterministic textual `.l1m` artifacts through the internal `--emit-interface` mode.
- Parses the constrained interface grammar for round-trip validation and graph-backed internal replay.

### 2.8 Backend (`backend.l0`, `c_emitter.l0`, `string_escape.l0`)

- Consumes typed analysis results and emits one C99 translation unit.
- Delegates backend-specific behavior to [c-backend-design.md](c-backend-design.md).

### 2.9 Driver and CLI (`driver.l0`, `l1c_lib.l0`, `cli_args.l0`, `build_driver.l0`)

- Coordinates the pass pipeline.
- Builds and exposes the deterministic module graph, canonical artifact associations, and active cloned interfaces.
- Exposes resolution-aware internal entry points with ordered interface roots, caller-selected source fallback, and an
  optional artifact root.
- Implements CLI mode dispatch and host compiler execution.
- Reserves compile-only mode and interface-path syntax while keeping the unimplemented path gated before analysis.
- Produces generated C, built executables, or direct runs depending on CLI mode.

## 3. Core Data Flow

Primary aggregates in the current implementation include:

- token streams from `tokens.l0`
- parsed AST nodes from `ast.l0`
- parsed and active module interfaces from `module_interface.l0`
- `ModuleGraph`, `ModuleGraphNode`, `ModuleOrigin`, `ModuleDependency`, and `ModuleArtifactPaths` from `module_graph.l0`
- module and symbol environments from `name_resolver.l0`
- typed semantic state from `analysis.l0`
- projected module interfaces carrying populated `require` and `link` dependency tiers
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

1. The current L1 compiler is bootstrap-only and implemented in Dea/L0.
2. Import closure construction is explicit and checked before later semantic passes; each canonical module has one
   source, interface, registry, or virtual origin in the module graph.
3. Source locations are propagated for diagnostics.
4. Diagnostic columns follow a logical-source contract: every non-newline Unicode code point, including ASCII horizontal
   tabs, advances the stored column by exactly one; UTF-8 continuation bytes do not advance it. Snippet rendering
   normalizes displayed source lines to the same model (each tab is printed as a single space) so the caret underline
   and the displayed line always agree, independent of terminal tab-stop behavior. Unicode display-width handling is out
   of scope for this contract.
5. Semantic failures are reported as diagnostics rather than internal crashes on normal invalid input paths.
6. Generated output is currently one C99 translation unit.
7. Interface emission, graph enumeration, and artifact association are deterministic. Direct source-import edges
   preserve declaration order and duplicates.
8. `.l1m` artifacts are available to internal resolution-aware APIs but are not normal compile/build/run inputs yet.
9. Any future `stage2_l1` implementation should match the public L1 language/runtime behavior documented here and in the
   other L1 reference documents.

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
- `l1c.l0`
- `l1c_lib.l0`
- `lexer.l0`
- `locals.l0`
- `mi_utils.l0`
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

Shared support modules live under `compiler/stage1_l0/src/util/`.

## 6. Host and Toolchain Assumptions

- Source decoding is UTF-8 with optional BOM stripping; the shared language vocabulary remains ASCII-only. See
  [docs/specs/language/source-text-and-language-vocabulary.md](../../../docs/specs/language/source-text-and-language-vocabulary.md).
- L1 source modules use the `.l1` extension.
- The bootstrap compiler implementation remains `.l0` source code.
- `--build` and `--run` require a host C99 toolchain.
- Local bootstrap builds use `../l0/build/dea/bin/l0c-stage2` by default unless overridden with `L1_BOOTSTRAP_L0C`.
