# L0 Compiler Architecture

Version: 2026-11-12

This is the canonical architecture document for the current compiler pipeline. Stage 1 remains the reference
implementation and Stage 2 mirrors the same pass structure through code generation and driver execution.

Related canonical docs:

- Backend lowering and generated C details: [l0/docs/reference/c-backend-design.md](c-backend-design.md)
- Language/runtime rationale and future evolution: [l0/docs/reference/design-decisions.md](design-decisions.md)
- Compact contract/index: [l0/docs/specs/compiler/stage1-contract.md](../specs/compiler/stage1-contract.md)
- Shared source-text policy:
  [docs/specs/language/source-text-and-language-vocabulary.md](../../../docs/specs/language/source-text-and-language-vocabulary.md)
- Shared CLI contract: [l0/docs/specs/compiler/cli-contract.md](../specs/compiler/cli-contract.md)

## 1. High-Level Pipeline

Both stages resolve the source import closure, analyze it, and emit one C99 translation unit. Stage 1 implements this
pipeline in Python; Stage 2 implements it in L0. Native build and run modes then pass the generated C to a host
compiler.

### 1.1 Stage 1 Reference Pipeline

```
Source (.l0)
  |
  v
Lexer.tokenize() -> Token stream
  |
  v
Parser.parse_module() -> AST
  |
  v
NameResolver.resolve() -> ModuleEnv per module
  |
  v
SignatureResolver.resolve() -> func/struct/enum/let type tables
  |
  v
LocalScopeResolver.resolve() -> FunctionEnv per function
  |
  v
ExpressionTypeChecker.check() -> expression types + semantic diagnostics
  |
  v
Backend.generate() -> single C99 translation unit
  |
  v
Host C compiler -> executable (run/build commands)
```

Pass coordination entry point: `L0Driver.analyze()` in `compiler/stage1_py/l0_driver.py`.

### 1.2 Stage 2 Current Pipeline

```
Source (.l0)
  |
  v
lexer.l0 -> Token stream
  |
  v
parser.l0 -> arena-backed AST
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
expr_types.l0 -> expression types + semantic diagnostics
  |
  v
backend.l0 -> backend/* + c_emitter/* -> single C99 translation unit
  |
  v
build_driver.l0 + compiler_filesystem.l0
  -> command-owned workspace + host C compiler invocation (`--build` / `--run`)
  |
  v
Executable launch (`--run`)
```

The Stage 2 CLI enters through `compiler/stage2_l0/src/l0c.l0`. It exposes the same public modes as Stage 1: `--check`,
`--tok`, `--sym`, `--type`, `--ast`, `--gen`, `--build`, and `--run`. The reserved `--compile` / `-c` mode reports
`L0C-9510` without producing artifacts.

For `--build` and `--run`, the driver validates the source and entry point before creating a private temporary
workspace. Generated C, host-compiler output captures, and the temporary run executable live there until the command
finishes. Caller-selected executables and `--keep-c` outputs remain at their public paths.

`build_driver.l0` coordinates compilation and execution. The compiler-private `compiler_filesystem.l0` module manages
workspace creation and cleanup, including temporary-parent validation, exclusive directory creation, and bounded cleanup
that does not follow symlinks. Its native support in `support/compiler_filesystem.c` provides host filesystem
primitives. These services are internal to the compiler; they do not extend the public runtime or standard library.

### 1.3 Compiler Construction and Delivery

Stage 1 builds the initial Stage 2 compiler from L0 sources. Stage 2 can then compile itself; `make triple-test` checks
that repeated self-builds reach the required fixed point. The bootstrap procedure and reproducibility checks are
documented in [l0/compiler/stage2_l0/README.md](../../compiler/stage2_l0/README.md).

The toolchain has three delivery workflows. Run the following commands from `l0/`:

- **Development:** `make use-dev-stage2` builds Stage 2 and selects it as the repo-local `l0c`. Activate the launcher
  with `source build/dea/bin/l0-env.sh`. Use `make use-dev-stage1` to select the Python compiler instead.
- **Installation:** `make install PREFIX=/absolute/prefix` bootstraps Stage 2, rebuilds it with itself, and installs the
  compiler with its standard library and runtime assets. `PREFIX` is required. Activate the installed launcher with
  `source /absolute/prefix/bin/l0-env.sh`.
- **Distribution:** `make dist DOCS_ARTIFACT=/absolute/matching-docs-bundle.tar.gz` packages the relocatable Stage 2
  toolchain and offline documentation under a `dea-l0/` archive root. Archives use `.tar.gz` on POSIX hosts and `.zip`
  on Windows. Build the matching documentation bundle first with `make docs-artifacts DOC_STAGE=stage2`; packaging does
  not invoke TeX.

See [l0/README.md](../../README.md#install) for setup instructions, including Windows shell commands, and
[l0/docs/README.md](../README.md) for documentation bundle and version requirements.

## 2. Pass Responsibilities

### 2.1 Lexer (`l0_lexer.py`)

- Converts UTF-8 source text to `Token` list.
- Uses `l0_types.py`'s `L0_PRIMITIVE_TYPES` as the shared Stage 1 authority for builtin token reservation, parser type
  lookahead, and semantic type construction. Native Stage 2 mirrors that authority in `builtin_types.l0`.
- Tracks `line`/`column`; columns count Unicode code points.
- Handles keywords, literals, operators, punctuation, and comment skipping.
- Wraps recoverable lexer diagnostics in `LEXER_ERROR` tokens with optional logical recovery tokens. Invalid-character
  runs (`LEX-0040`) have no recovery token and are skipped logically; malformed literals and integer diagnostics recover
  as literal tokens where possible.
- Keeps unterminated block comments (`LEX-0070`) as unrecoverable trivia diagnostics.

### 2.2 Parser (`l0_parser.py`)

- Recursive-descent parser producing `l0_ast.py` dataclass nodes.
- Reads tokens through logical accessors: wrappers with recovery behave as the recovered token, wrappers without
  recovery are skipped, and each wrapped lexer diagnostic is emitted once.
- Parses module header, imports, declarations, statements, expressions, and type refs.
- Assignment is statement-only syntax (`AssignStmt`).
- Emits `ParseError` for parse failures.

### 2.3 Name Resolver (`l0_name_resolver.py`)

- Builds `ModuleEnv` maps for all modules in a `CompilationUnit`.
- Collects locals and opens imported symbols (open import semantics).
- Tracks ambiguous imports and emits resolver diagnostics.

### 2.4 Signature Resolver (`l0_signatures.py`)

- Resolves top-level type references.
- Populates:
  - `func_types`
  - `struct_infos`
  - `enum_infos`
  - `let_types`
- Detects alias cycles and value-type dependency cycles.

### 2.5 Local Scope Resolver (`l0_locals.py`)

- Builds lexical scope trees for non-extern functions.
- Produces `FunctionEnv` keyed by `(module_name, func_name)`.

### 2.6 Expression Type Checker (`l0_expr_types.py`)

- Infers/checks expression and statement types.
- Validates control-flow requirements (for example non-void return paths).
- Tracks expression types in `AnalysisResult.expr_types`.
- Records variable-resolution origin in `AnalysisResult.var_ref_resolution`.
- Appends semantic diagnostics.
- `l0_expr_types.py` coordinates explicit `l0_check_*` collaborators; Stage 2 `expr_types.l0` coordinates `expr_types.*`
  modules. State owns lexical/liveness stacks and diagnostic replay. Lookup, compatibility, pattern validation, and
  expression liveness are lower-level responsibilities. Expression inference and statement/loop flow each retain their
  mutually recursive algorithms.
- Pattern validation precedes arm traversal; exhaustiveness reporting follows it. The split preserves diagnostic
  ordering, source spans, and fixed-point liveness behavior.

### 2.7 Backend and C emission

- Consumes a typed `AnalysisResult` and emits C99.
- Canonical backend details are maintained only in [l0/docs/reference/c-backend-design.md](c-backend-design.md).

### 2.8 Stage 2 Driver (`build_driver.l0`, `compiler_filesystem.l0`)

- Coordinates host compilation and child execution after analysis and entry-point validation.
- Owns one private native workspace for each `--build` or `--run` command and keeps it alive through the complete
  operation.
- Registers only driver-selected scratch children and removes them with bounded no-follow cleanup. Setup/trust failures
  report `L0C-9513`; incomplete cleanup reports `L0C-9514` and retains the workspace.
- Implements the detailed safety and result contract in
  [docs/specs/compiler/cli-contract.md](../../../docs/specs/compiler/cli-contract.md#6-native-buildrun-temporary-workspace).

## 3. Core Data Flow

Primary aggregate: `AnalysisResult` (`l0_analysis.py`).

Important tables:

- `module_envs`
- `func_types`
- `struct_infos`
- `enum_infos`
- `func_envs`
- `let_types`
- `expr_types`
- `var_ref_resolution`
- `intrinsic_targets`
- `diagnostics`

Compilation closure container: `CompilationUnit` (`l0_compilation.py`), containing:

- `entry_module`
- `modules` (transitive import closure)

## 4. Invariants

1. Stages are explicit and ordered as in the pipeline above.
2. Import closure is explicit and cycle-checked in the driver.
3. Source locations are propagated for diagnostics.
4. Semantic errors accumulate as diagnostics; they do not crash the compiler.
5. Generated output target for both stages is one C99 translation unit.
6. Stage 1 remains the oracle for exact Stage 2 backend behavior, diagnostics, and emitted text on equivalent paths.

## 5. File/Module Layout

Stage 1 sources live under `l0/compiler/stage1_py/`; Stage 2 sources live under `l0/compiler/stage2_l0/src/`. The table
maps CLI, semantic analysis, backend, and C emission responsibilities to their implementation modules:

| Responsibility                      | Stage 1 owners                                                                                                               | Stage 2 owners                                                                                                                             |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| CLI grammar and dispatch            | `l0c.py` dispatches; `l0_cli_args.py` parses; `l0_cli_diagnostics.py` renders diagnostics                                    | `cli_args.l0` parses; `cli_args.model`, `presentation`, `tokens`, and `validate` own options/lifecycle and parsing policy                  |
| Analysis commands and native builds | `l0_cli_context.py`, `l0_cli_commands.py`, `l0_cli_build.py`                                                                 | `l0c_lib.l0`; `build_driver.l0` coordinates `build_driver.state`, `input`, `options`, `platform`, `toolchain`, and `workspace`             |
| Expression and statement typing     | `l0_expr_types.py` assembles `l0_check_state`, `lookup`, `compat`, `patterns`, `liveness`, `expr`, and `flow`                | `expr_types.l0` coordinates the corresponding `expr_types.*` owners plus top-level `initializers`                                          |
| Backend generation                  | `l0_backend.py` assembles `l0_backend_state`, `convert`, `lifetime`, `initializers`, `ordering`, `lowering`, and `module`    | `backend.l0` coordinates `backend.state`, `convert`, `lifetime`, `initializers`, `ordering`, `lowering`, and `output`                      |
| C syntax and output                 | `l0_c_emitter.py` assembles `l0_c_builder`, `state`, `names`, `types`, `values`, `statements`, `cleanup`, and `declarations` | `c_emitter.builder`, `state`, `names`, `types`, `wrappers`, `values`, `statements`, `lifetime`, and `declarations`; no root emitter facade |

In each table cell, abbreviated suffixes share the first module prefix. Stage 1 uses explicit collaborators with only
their actual dependencies. Expression inference and semantic type formatting use structural pattern matching with
keyword fields. Type annotations use built-in generic containers, union syntax, and native deferred evaluation; quoted
annotations at `TYPE_CHECKING`-only import boundaries allow signature introspection without runtime imports.
`l0_symbols.SymbolKey` names the `(module_name, declaration_name)` tuple used by semantic tables and dependency graphs;
runtime keys remain ordinary tuples.

Stage 2 uses acyclic imports and canonical type owners:

- `cli_args.model` declares `CliMode`, `CliOptions`, and `CliParseResult` and owns their lifecycle.
- `build_driver.state` declares prepared input and owns its release operations.
- `expr_types.state` declares checker/flow models and owns checker construction, stacks, and destruction.
- `backend.state` declares backend/loop models and owns backend construction and destruction.
- `c_emitter.builder` owns `CCodeBuilder`; `c_emitter.state` owns `CEmitter` and its lifetime.

Consumers import these owners directly because L0 imports do not re-export names. Implementation children never import
their root facade. Root `cli_args`, `build_driver`, `expr_types`, and `backend` declare only coarse pass/command
entrypoints. Recursive lowering stays together: scheduled cleanup can lower statements, and expression lowering can emit
control flow. The larger lowering modules therefore represent one algorithm rather than unrelated responsibilities.

`build_driver.l0` retains the complete build/run workspace transaction and cleanup epilogue. Host command construction
belongs to `build_driver.toolchain`, and native compilation within a borrowed workspace belongs to
`build_driver.workspace`. `compiler_filesystem.l0` remains the canonical compiler-private workspace-policy owner;
`support/compiler_filesystem.c` provides actual-host filesystem primitives.

## 6. Host/Toolchain Assumptions

- Stage 1 requires Python 3.14 or newer.
- Windows shared tooling uses native CPython with the MSYS2 shell and C toolchain. See
  [MONOREPO.md](../../../MONOREPO.md#windows-python-environments) for provisioning and CI interpreter ownership.
- Source decoding is UTF-8 with optional BOM stripping; the language vocabulary remains ASCII-only.
- Module names use identifier segments separated by dots.
- `run` and `build` require an entry `main` function in the entry module.
- C target is C99 and host compiler is selected from CLI/env or PATH.
