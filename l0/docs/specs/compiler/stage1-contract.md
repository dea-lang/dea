# L0 Stage 1 Compiler Contract

Version: 2026-08-29

This document is the compact Stage 1 contract and navigation index.

Canonical ownership:

- Shared CLI contract (mode flags, options, targets, identity, exit codes): [cli-contract.md](cli-contract.md)
- Architecture and pass flow: [reference/architecture.md](../../reference/architecture.md)
- C backend behavior and lowering details: [reference/c-backend-design.md](../../reference/c-backend-design.md)
- Language/runtime rationale and future evolution: [reference/design-decisions.md](../../reference/design-decisions.md)
- Shared source-text and language-vocabulary policy:
  [docs/specs/language/source-text-and-language-vocabulary.md](../../../../docs/specs/language/source-text-and-language-vocabulary.md)
- Diagnostic code assignment and cross-stage parity: [diagnostic-code-policy.md](diagnostic-code-policy.md)

## 1. Scope

Stage 1 is the Python compiler (`compiler/stage1_py`) that:

- parses and analyzes L0 modules,
- lowers analyzed programs to one C99 translation unit,
- optionally invokes a host C compiler.

The end-to-end flow is:

1. `Lexer.tokenize()`
2. `Parser.parse_module()`
3. `NameResolver.resolve()`
4. `SignatureResolver.resolve()`
5. `LocalScopeResolver.resolve()`
6. `ExpressionTypeChecker.check()`
7. `Backend.generate()`

## 2. Stable External Interfaces

### 2.1 CLI

Entry point: `compiler/stage1_py/l0c.py`

The shared CLI surface (mode flags, global options, mode-scoped options, target rules, identity strings, and exit codes)
is normatively defined in [cli-contract.md](cli-contract.md).

Stage 1-specific notes:

- Debug-dump options `--all-modules` / `-a` and `--include-eof` apply to `tok`, `ast`, `sym`, and `type` modes as
  defined in the shared contract.
- `--keep-c` with `--run` writes `./a.c` by default, or `<output>.c` when `-o` is also given.

#### 2.1.1 Compiler temporary safety

- On POSIX, Stage 1 resolves the selected temporary directory before creating anonymous generated C or an anonymous
  `--run` executable. Every directory from the resolved temporary parent through the filesystem root must be owned by
  the effective user or root; a group- or other-writable component must have the sticky bit. Failure reports `L0C-9511`
  and the host compiler is not invoked.
- Windows retains the supported-host assumption that the selected temporary directory is protected by trusted ACLs.
- Anonymous generated C is created with `tempfile.mkstemp()` in the explicitly validated directory, written as UTF-8
  through the returned descriptor, and closed before host compilation.
- Temporary-source setup or write failure reports `L0C-9511`. Source-removal failure reports `L0C-9512`, includes the
  retained path, and makes the build fail even when host compilation succeeded. If setup or writing fails and cleanup
  also fails, both diagnostics are emitted.
- A caller-visible build executable already produced before source-cleanup failure is retained. Caller-selected
  `--keep-c` paths and the existing temporary run-executable cleanup lifecycle are otherwise unchanged.

### 2.2 Source/module contract

- Source encoding: UTF-8; UTF-8 BOM is accepted and stripped by the driver. The language vocabulary remains ASCII-only.
- Module file extension: `.l0`.
- Module mapping: dotted name -> path segments (for example, `std.io` -> `std/io.l0`).
- Declared `module ...;` name must match the loaded module name.

### 2.3 Backend output contract

- Stage 1 emits a single C99 translation unit.
- When trace flags are enabled, generated C emits `L0_TRACE_ARC` and/or `L0_TRACE_MEMORY` defines before including
  `l0_runtime.h`.
- Generated C owns the header-only implementation through `l0_runtime.h`. Additional `--c-source` translation units use
  declaration-only `dea_rt.h`; they must not include `l0_runtime.h`.
- Backend details are canonical in [reference/c-backend-design.md](../../reference/c-backend-design.md).
- Trace details are canonical in [specs/runtime/trace.md](../runtime/trace.md).

## 3. Current Core Data Shapes (Exact Names)

These names are externally relevant for contributors; details live in code.

### 3.1 Token model (`l0_lexer.py`)

`Token` fields:

- `kind`
- `text`
- `line`
- `column`
- `diagnostic` / `diagnostics` (only set on `LEXER_ERROR` wrapper tokens)
- `recovery` (optional parser-visible logical token for recoverable lexer diagnostics)

Token kind enum: `TokenKind`. Important current names include:

- punctuation/operators: `SEMI`, `EQ`, `EQEQ`, `NE`, `MODULO`, `ARROW_FUNC`, `ARROW_MATCH`, `DOUBLE_COLON`
- logical operators: `ANDAND`, `OROR`, `BANG`
- reserved tokens: `AMP`, `PIPE`, `CARET`, `TILDE`, `LSHIFT`, `RSHIFT`, `FUTURE_EXTENSION`
- `CLEANUP` keyword token for `with ... cleanup`.
- `LEXER_ERROR`: lexer diagnostic wrapper with a full diagnostic span and optional logical recovery token. The lexer
  does not emit recoverable wrapper diagnostics directly; the parser emits each wrapper diagnostic once. Wrappers with
  recovery behave as that recovered token to parser decisions, and wrappers without recovery are skipped. Lexer errors
  do not gate the parser phase, but accumulated errors still gate later semantic and codegen phases.

### 3.2 AST model (`l0_ast.py`)

AST nodes are Python `@dataclass` types (not frozen).

Important exact field names:

- `Module.decls`
- `Import.name`
- `Block.stmts`
- `IfStmt.cond`, `IfStmt.then_stmt`, `IfStmt.else_stmt`
- `ForStmt.init`, `ForStmt.cond`, `ForStmt.update`
- `WithStmt.cleanup_body`
- `CaseArm.literal`
- `VariantPattern.vars`
- `IndexExpr.array`
- `FieldAccessExpr.obj`
- `CastExpr.target_type`
- `TypeRef.module_path`, `TypeRef.name_qualifier`

## 4. Required Behavioral Guarantees

1. Driver import closure is explicit and cycle-checked (`ImportCycleError`).
2. User-facing failures are surfaced as diagnostics (lexer/parser exceptions are converted by driver).
3. Assignment remains statement-only in syntax.
4. Open import semantics remain default name-resolution behavior.
5. Nullability remains explicit in type syntax (`?`).
6. Backend emits deterministic single-unit C layout.

## 5. Known Stage 1 Constraints

1. No address-of (`&`) operator.
2. No generics/traits/macros.
3. Index syntax exists in AST/type-checking, but arrays/slices are not implemented, so index typing currently rejects
   non-supported targets.
4. Reserved operators/tokens are lexed for diagnostics and future expansion.

## 6. Documentation Routing

Use the narrowest canonical document for each question:

- Pass sequencing, module ownership, and frontend architecture:
  [reference/architecture.md](../../reference/architecture.md)
- Lowering policy, generated C layout, ARC/cleanup behavior, runtime calls:
  [reference/c-backend-design.md](../../reference/c-backend-design.md)
- Trace flags and runtime trace behavior: [specs/runtime/trace.md](../runtime/trace.md)
- Pointer/nullability model rationale, integer model rationale, stage-2 design direction:
  [reference/design-decisions.md](../../reference/design-decisions.md)
