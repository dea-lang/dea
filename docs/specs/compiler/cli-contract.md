# Dea Compiler CLI Contract

Version: 2026-08-30

This document defines the shared command-line contract for Dea compilers. It covers behavior common to the current L0
Stage 1, L0 Stage 2, and L1 Stage 1 implementations. A level may add a documented mode or option without changing the
meaning of the shared surface.

Canonical level-specific detail:

- [l0/docs/specs/compiler/cli-contract.md](../../../l0/docs/specs/compiler/cli-contract.md): complete L0 Stage 1/Stage 2
  contract
- [l1/docs/project-status.md](../../../l1/docs/project-status.md): current L1 bootstrap scope and delivery status
- [docs/specs/compiler/diagnostic-code-catalog.md](diagnostic-code-catalog.md): shared CLI and compiler diagnostic codes

## 1. Operating Model

- Modes are selected with flags. At most one primary mode may be selected.
- `--build` is the default when no primary mode is given.
- Exactly one source target is required, except that `--help` and `--version` short-circuit target validation and L1
  `--link` consumes one or more positional Dea object paths instead.
- Runtime arguments for `--run` follow a `--` separator. The separator is invalid in other modes.
- CLI argument errors exit with status 2; analysis, compilation, or standalone-link failures exit with status 1;
  successful operations exit with status 0. `--run` forwards the child program's exit status.

## 2. Shared Modes

| Mode        | Aliases            | Purpose                                                         |
| ----------- | ------------------ | --------------------------------------------------------------- |
| `--run`     | `-r`               | Build and run one source target                                 |
| `--build`   |                    | Build one executable                                            |
| `--compile` | `-c`               | Reserved in L0; compile one module without linking in L1        |
| `--link`    | `-k`               | L1-only: link verified Dea interfaces with opaque native inputs |
| `--gen`     | `-Gc`, `--codegen` | Emit generated C                                                |
| `--check`   | `--analyze`        | Parse and analyze                                               |
| `--tok`     | `--tokens`         | Dump lexer tokens                                               |
| `--ast`     |                    | Dump the parsed AST                                             |
| `--sym`     | `--symbols`        | Dump module-level symbols                                       |
| `--type`    | `--types`          | Dump resolved top-level types                                   |

The dump modes are developer-facing; their text formats are not stable interfaces. All current compilers recognize
`--compile` / `-c`. L0 Stage 1 and Stage 2 report `L0C-9510` without analysis or artifact production. L1 Stage 1
implements the endpoint-rollback compile-only artifact set in section 7 and additionally implements `--emit-interface` /
`-Gi`, which emits the target module's textual `.l1m` interface. L1 Stage 1 also implements the standalone `--link` /
`-k` mode in section 8.

### L1 generated-C mode

L1 `l1c --gen MODULE [-I ROOT]... [-o FILE]` resolves `MODULE` from source and emits exactly that module's C translation
unit. Imported modules prefer the first selected verified interface in ordered `-I` roots and fall back to source only
when no interface is selected. A selected valid `.l1m` is sufficient without a sibling `.o` or `.c`; a malformed
selected interface is authoritative and fails without source fallback.

The output contains the selected module's definitions, imported declarations and required transparent types,
always-present `I4init` and `I4fini`, and conditional `I5entry`. It contains no imported definitions, dependency
lifecycle calls, process `main`, executable wrapper, embedded interface text, or native metadata. Without `-o`, output
goes to stdout. With `-o`, the value is the exact output file; generation creates no companion artifacts and never
invokes the host compiler or linker. `--keep-c` and host-tool-only controls remain invalid with `--gen`.

For identical source, resolved graph, verified interfaces, fingerprints, compiler version, and byte-affecting settings,
the selected module C is byte-identical across `--gen`, `--compile --keep-c`, `--build --keep-c`, and `--run --keep-c`.
Output paths, caller mode, and invocation-private workspace names do not enter those bytes. Build/run retention copies
the exact module bytes submitted to the host compiler; it does not regenerate or rewrite them. The separately compiled
`__dea_wrapper.c` is link-orchestration output and has no generated-C or compile-only counterpart.

### L1 multi-compilation-unit build and run

L1 `--build` and `--run` resolve the requested source target through the canonical module graph with interface-first
imports and source fallback only when no interface is selected. Each source-backed node is generated and compiled once
as its own module translation unit in deterministic dependency-first order. An interface-backed provider contributes its
verified `.l1m` plus the original opaque sibling `.o`; the pair must remain stable from selection through final-link
submission, and callers must serialize externally against same-stem publication or replacement.

The requested source target is always the entry selection, so `--entry` remains standalone-link-only. The target must
itself carry an eligible `I5entry`; another linked module's entry cannot substitute. Repeatable `--foreign-object` /
`-Cf`, `-l`, `-L`, `--rpath` / `-Rr`, and `--link-arg` / `-Cl` inputs are valid in build and run. The source target is
expanded into the dependency-ordered Dea object set at its encounter position; every other link input retains its
relative position around that expansion.

`--build -o PATH --keep-c` retains exact generated C beneath `PATH.dea-c/`; default output uses the same suffix on the
default executable name. `--run --keep-c` retains beneath `<canonical-target>.dea-c/` in the invocation directory and
continues to ignore `-o`. Module files mirror dotted module paths, and `__dea_wrapper.c` is stored at the root. The
retained root must be absent; setup or copy failure reports `L1C-2132` and rolls back compiler-created entries. The
otherwise legal root module name `__dea_wrapper`, including ASCII case variants, is rejected only when build/run keep-C
is requested because its canonical C path may collide with the reserved wrapper filename on case-insensitive
filesystems.

Run mode launches the temporary executable without a shell, forwards every argument after `--` unchanged, returns the
program status, and removes the executable with the rest of the private workspace. Failure to start the executable is
reported separately as `L1C-2133`.

## 3. Shared Options

The current shared option surface is:

- `--help` / `-h`, `--version` / `-V`, counted `--verbose` / `-v`, and `--log` / `-Vl`
- repeatable project and system roots through `--project-root` / `-Rp` and `--sys-root` / `-Rs`; L1 `--link` rejects
  both because it consumes objects without resolving source
- repeatable compile/generated-C interface paths through `--interface-path` / `-I`; L1 consumes them in declaration
  order for build, run, compile-only, and generated-C modes, while L0 retains the syntax for its reserved compile mode
- `--output` / `-o` for artifact-producing modes; L1 also accepts it with `--compile`, `--emit-interface`, and `--link`
- `--c-compiler` / `-Cc`, `--c-options` / `-Co`, and `--runtime-include` / `-Ri` for build/run, L1 compile-only, and L1
  standalone linking; in standalone link mode, C options apply only while compiling the generated wrapper and are not
  forwarded to the final host-link command. `--runtime-lib` / `-Rl` is valid for build/run and L1 standalone linking
- repeatable L0 `--c-source PATH` / `--c-source=PATH` / `-Cs PATH` / `-Cs=PATH` for build/run; every value remains one
  intact host-compiler argument, and the generated C source precedes additional sources in occurrence order
- `--no-line-directives` / `-NLD`, `--trace-arc` / `-Va`, `--trace-memory` / `-Vm`, `--unchecked` / `-Su`, and
  `--check-basic` / `-Sb` for generated-C modes, including L1 compile-only; L1 standalone linking additionally accepts
  the trace and checking controls to select its runtime link inputs
- `--keep-c` / `-Gk` for build/run and L1 compile-only
- `--all-modules` / `-a` for token, AST, symbol, and type dumps
- `--include-eof` for token dumps
- repeatable L1 `--foreign-object PATH` / `--foreign-object=PATH` / `-Cf PATH` / `-Cf=PATH` for build, run, and
  standalone linking; optional `--entry MODULE` / `--entry=MODULE` / `-e MODULE` remains standalone-link-only
- repeatable L1 external-link controls for build, run, and standalone linking: `-l LIBRARY` / `-lLIBRARY`,
  `-L DIRECTORY` / `-LDIRECTORY`, `--rpath RPATH` / `--rpath=RPATH` / `-Rr RPATH` / `-Rr=RPATH`, and
  `--link-arg ARGUMENT` / `--link-arg=ARGUMENT` / `-Cl ARGUMENT` / `-Cl=ARGUMENT`

Using a mode-scoped option with an incompatible mode is a CLI argument error. In L1, interface paths are valid with
`--build`, `--run`, `--compile`, and `--gen`; in L0 they remain valid only with the reserved `--compile` mode.
Incompatible interface-path uses produce `L0C-2031` or `L1C-2031`; L1 external-link controls outside `--build`, `--run`,
and `--link` produce `L1C-2070`.

The conventional driver spellings `-g` and `-S` remain reserved for debug information and assembly output; syntactically
complete uses produce `L0C-2032` or `L1C-2032`. L0 also recognizes `-L` and `-l` as reserved and reports `L0C-2032`,
while L1 implements them as external-library search and selection controls.

Multi-letter short options are exact, case-sensitive tokens. Value-taking namespaced options accept a following value or
`=VALUE`, but not an attached suffix. Canonical `-I`, `-L`, and `-l` accept directly attached or following values; their
`-I=...`, `-L=...`, and `-l=...` forms are invalid. `-e` accepts only a following value. Only the counted `-vv...` form
is a short-option cluster; other clusters are invalid. `-V` is explicitly assigned to version; unassigned bare namespace
prefixes such as `-C` and `-R` are not options. L1 implements the exact namespaced `-Rr` and `-Cl` spellings; L0 leaves
them unknown because their capabilities are L1-specific today.

L1 places all Dea objects, foreign objects, libraries, library search paths, runtime search paths, and raw host-driver
arguments in one encounter-ordered typed stream. `--link-arg` contributes exactly one intact compiler-driver argument;
it is not implicitly rewritten as a native-linker option. Object-suffixed `-l` values, raw words, and `-Wl,` payload
segments, plus response-file, object-file-list, or driver-config indirection, are rejected with `L1C-2071`; callers use
positional Dea objects or `--foreign-object` for relocatables. This is a conservative syntactic boundary across compiler
families. Archive and shared-library arguments such as `.a`, `.so`, `.dylib`, `.lib`, and `.dll` remain valid raw driver
inputs. Rpaths are lowered only for recognized GCC and Clang driver names, exact `cc`, and TinyCC on non-Windows hosts;
unsupported families, Windows, and comma-containing TinyCC rpaths report `L1C-2072`. The canonical GNU-style `-l` / `-L`
lowering is unavailable for the MSVC driver family and reports the same code; an explicit `.lib` may still be one raw
driver input when the selected MSVC invocation accepts it. On native Windows, `%`, `!`, literal `"`, carriage returns,
and line feeds in build/run external-link values report `L1C-2106` before source compilation; exact rendered command and
capture values are checked again before execution.

## 4. Level-Scoped Environment

Each compiler uses its level prefix for environment-backed defaults:

| Purpose              | L0                   | L1                   |
| -------------------- | -------------------- | -------------------- |
| Compiler home        | `L0_HOME`            | `L1_HOME`            |
| System/stdlib roots  | `L0_SYSTEM`          | `L1_SYSTEM`          |
| C compiler           | `L0_CC`              | `L1_CC`              |
| C compiler options   | `L0_CFLAGS`          | `L1_CFLAGS`          |
| Runtime include path | `L0_RUNTIME_INCLUDE` | `L1_RUNTIME_INCLUDE` |
| Runtime library path | `L0_RUNTIME_LIB`     | `L1_RUNTIME_LIB`     |

The level-specific C compiler variable has highest precedence. Automatic detection then tries `tcc`, `gcc`, `clang`, and
`cc` from `PATH`, followed by `$CC`. C options from the level-specific environment variable are placed before options
supplied through `--c-options`.

## 5. Target and Source-Path Rules

- Absolute targets and targets containing a path separator are treated as file paths.
- Relative targets beginning with `.` or `..` resolve from the current directory.
- Dotted module names map to source-tree path components and search system roots before project roots.
- A plain filename or module name resolves using the active level's source extension (`.l0` or `.l1`).
- Repeated system or project roots preserve declaration order within their root group.

## 6. Native Build/Run Temporary Workspace

Each L0 Stage 2 or L1 Stage 1 `--build` or `--run` command owns one private temporary workspace for the complete native
operation. The command creates the workspace after CLI and source-target validation, passes it through graph analysis,
compilation, and linking, keeps it through child execution for `--run`, and releases it from one cleanup path. L0 also
completes entry validation before allocation; L1 validates the graph-selected target entry before final linking. It
passes the workspace through its compile and link helpers. Subordinate helpers do not create or independently clean
another build/run workspace.

- The temporary parent uses `TMPDIR`, `TEMP`, `TMP`, `/tmp`, then `.` in that order. An absent, nonexistent, or
  non-directory candidate falls through. A filesystem inspection error is fatal. Once an existing directory is selected,
  canonical resolution or trust validation failure is fatal rather than falling through to another candidate.
- Workspace creation uses the selected parent's canonical path and reserves a new directory exclusively. On an actual
  POSIX host, every directory from the filesystem root through that parent must be owned by the effective user or root;
  every group- or other-writable directory must have the sticky bit. The private workspace requests mode `0700`. On an
  actual MinGW host, creation uses the native directory path and assumes the selected parent's ACL is trusted. These
  policies follow the compiled host, not `L0_PLATFORM`, `L1_PLATFORM`, or another target-behavior alias.
- Workspace and fixed-child path construction also follows actual-host separator semantics. In particular, a `\` byte at
  the end of a POSIX parent name remains a literal filename byte and cannot move the workspace to a sibling path.
- The containment guarantee covers scratch paths selected or explicitly supplied by the driver: generated C, compiler
  stdout and stderr captures, temporary objects and interfaces, generated wrappers, and temporary run executables.
  `--keep-c` and caller-selected build outputs retain their documented external paths and behavior.
- The L0 driver does not change the host compiler's current directory. L1 source-module compilation runs the host
  compiler from the workspace so canonical module-relative C/object names remain stable; wrapper compilation and final
  link retain their existing invocation context. Neither driver rewrites the host temporary-directory environment,
  normalizes arbitrary path-bearing C options, or claims containment of auxiliary files independently created by the
  host compiler.
- Cleanup is bounded and no-follow: it removes only registered regular children and then the empty owned directory. It
  does not recursively delete unexpected contents or follow a substituted symlink or reparse-point directory. An
  incompletely cleaned workspace is retained for inspection.
- Temporary-parent inspection, workspace setup, parent-trust validation, and exclusive-reservation failures report
  `L0C-9513` or `L1C-9513`. Cleanup failures report `L0C-9514` or `L1C-9514` together with the retained workspace path.
- Cleanup failure changes a successful primary result to status 1. An existing compilation or launch failure, or a
  nonzero child-program status, remains the command result. A successfully produced retained output remains available in
  either case.

This workspace contract does not apply to the Python L0 Stage 1 compiler. L1 compile-only keeps the output-local
transaction described in section 7, and L1 standalone linking keeps the output-local transaction described in section 8;
neither operation is routed through the native build/run workspace.

## 7. L1 Compile-Only Artifact Set

The L1 Stage 1 compile-only form is:

```text
l1c -c MODULE [-I ROOT]... [-o CANONICAL_OBJECT_PATH] [-Gk]
```

- `MODULE` resolves to one source implementation. Non-virtual imports must resolve from verified `.l1m` interfaces;
  compile-only does not fall back to provider source.
- Without `--output`, the current directory is the artifact root and the canonical dotted module path supplies the stem.
  With `--output`, the value must be non-empty, must not end in `/` or `\`, and must name an `.o` file; replacing only
  that final suffix selects its `.c` and `.l1m` companions. Empty values, trailing separators, directories,
  extensionless values, and other suffixes report `L1C-2033`, not a generic module-identity diagnostic.
- Existing output-parent components are trusted directory inputs. Directory validation follows aliases using
  `std.fs::is_dir()` semantics, and missing descendants beneath an existing directory alias are created recursively.
  Dangling and non-directory aliases are rejected. Final `.c`, `.o`, and `.l1m` destinations plus transaction, backup,
  validation, and cleanup paths use no-follow classification; an existing artifact symlink is rejected with `L1C-2033`.
- The compiler always stages one generated-C file, one relocatable object, and one verified textual interface. Ordinary
  `-c` publishes the reusable `.o` and `.l1m` pair; `--keep-c` also publishes the exact staged `.c`. The mode does not
  invoke the final host linker or compile imported modules.
- Before publication, the staged object must be a regular file and the staged interface bytes must equal the selected
  publication bytes, parse, pass interface verification, and carry the expected module identity and public fingerprint.
  The compiler does not inspect native object contents or prove that the object and interface bytes agree.
- The staged files and any backups of the selected destinations share an exclusively reserved sibling transaction
  directory. Existing selected destinations move to recovery names before publication, the object is published before
  the interface, and a recoverable publication failure restores the previous selected set.
- Within the transaction, generated C, object, and interface staging uses the canonical dotted module path. The host
  compiler runs from the transaction root and receives stable module-relative C and object paths, so random transaction
  identities and caller-selected destination prefixes do not enter those compiler input/output arguments. Compiler paths
  with relative directory components and relative runtime-include paths are first resolved against the invocation
  directory. Bare compiler names are frozen to an absolute invocation-time command-search result; POSIX preserves empty
  and relative `PATH` components, while Windows preserves `PATHEXT` ordering and the current-directory policy selected
  by `NoDefaultCurrentDirectoryInExePath`, including any explicit empty or relative `PATH` component. An unresolved bare
  name fails before transaction allocation. Arbitrary relative path-bearing `L1_CFLAGS` / `--c-options` values instead
  resolve from the private transaction; callers that need invocation-relative raw host options must pass absolute paths.
  For debug-producing GNU-style options such as `-g`, `-g3`, and `-ggdb`, a compiler identified as Clang or GCC by its
  configured name or canonical filesystem target records the private debug compilation directory as stable `.` metadata.
  Conventional target-prefixed, numeric-version-suffixed, and MinGW `-posix` / `-win32` driver names are included in
  that recognition. On Darwin, the standard `gcc` and `cc` hard links to `/usr/bin/clang` are classified as Clang by
  filesystem identity. The driver still invokes the originally selected executable spelling. Opaque compiler wrappers
  whose canonical target is not recognizably Clang or GCC receive no debug path remapping guarantee.
- This staging contract excludes random transaction identities and caller-selected destination prefixes from the
  compiler paths controlled by the driver. It does not guarantee byte-identical native objects: a host toolchain may
  encode timestamps, environment details, absolute paths from raw options or headers, toolchain configuration, or other
  data outside the driver's control. Generated-C modes retain exact C-byte identity for the same resolved inputs and
  code-generation options.
- Publication guarantees operation endpoints, not an atomic reader-visible snapshot. Successful return leaves the
  complete new selected set; recoverable failure returns with the exact prior selected set restored; rollback failure
  retains recovery files. During sequential backup, publication, or rollback, paths may be temporarily absent or may
  expose different generations. Concurrent readers and same-stem writers require external serialization.
- Without `--keep-c`, the canonical `.c` companion is not a destination: the compiler does not classify, back up,
  create, overwrite, remove, or restore that path. Any pre-existing file or non-regular path there remains untouched.
- Host-compilation failure leaves destinations unchanged. Publication failure reports `L1C-2035` after a successful
  restore; rollback failure reports `L1C-2036` and retains recovery files for inspection.
- Raw host-C options that request auxiliary files do not add those files to the artifact set. If such a file prevents
  empty-directory cleanup, the compiler reports and retains the transaction directory instead of deleting it
  recursively.
- `--runtime-lib`, external-library options, and runtime program arguments remain invalid because compile-only neither
  links nor runs.

## 8. L1 Standalone Link Mode

The implemented L1 Stage 1 form is:

```text
l1c -k DEA_OBJECT... [-Cf C_OBJECT]... [-l LIBRARY]... [-L DIRECTORY]...
    [-Rr RPATH]... [-Cl LINK_ARG]... [-e MODULE] -o OUTPUT
```

- At least one positional Dea object and exactly one non-empty output path are required. Positional Dea objects,
  explicit foreign objects, libraries, search paths, rpaths, and raw host-driver arguments may be interleaved; the final
  host-link command retains their encounter order.
- Each positional path must have a nonempty basename stem and the exact case-sensitive terminal suffix `.o`. Replacing
  only that suffix with `.l1m` in the same directory selects the required sibling interface. Both paths must resolve to
  regular files; `.o`, `dir/.o`, separator-terminated paths, and other suffixes are rejected. The verified sibling
  header, not the pair's basename or native bytes, supplies the canonical module identity.
- The driver reads, UTF-8 validates, parses, and verifies every sibling `.l1m` before registering any module identity.
  Interfaces carry authoritative entry presence, ordered lifecycle imports, `require` / `link` expectations, and public
  provider fingerprints. Native `.o` bytes are opaque and are passed by original caller-selected path to the host
  toolchain without Dea format, symbol, metadata, or embedded-control inspection.
- `--foreign-object` / `-Cf` is repeatable and asserts that its regular-file path names one host-compatible relocatable
  native object. Dea does not prove the format, architecture, relocatability, symbols, absence of `main`, absence of
  reserved names, or absence of embedded linker controls. Archives, shared libraries, linker scripts, response files,
  and raw host-link arguments remain outside this option's supported contract even if a host accepts a mislabeled path.
- External libraries and their search paths enter through `-l` and `-L`. `--rpath` / `-Rr` translates one load-time
  runtime search directory for the selected supported compiler family. `--link-arg` / `-Cl` contributes one unchanged
  host compiler-driver word; object-suffixed library/raw inputs and response, file-list, or driver-config indirection
  are rejected, while direct archive and shared-library words are allowed. These external controls are CLI/build-tool
  configuration and do not become Dea module identities, `.l1m` records, lifecycle edges, or automatically discovered
  dependencies.
- `--entry` / `-e` may appear at most once and requires a canonical dotted module name. Without it, exactly one verified
  interface must carry `entry;`. With it, the named supplied module's verified interface must carry `entry;`.
- Module identities must be unique. Every non-virtual provider named by `import module`, `require`, or `link` must be in
  the explicit supplied Dea set with the exact expected public fingerprint. Ordered `import module` records alone form
  lifecycle edges and must be acyclic. Each non-virtual `require` / `link` provider must additionally be transitively
  reachable from its consumer through one or more lifecycle-import edges; those semantic records never add objects or
  lifecycle edges.
- The generated wrapper owns process `main`, initializes runtime arguments, calls every Dea initializer in deterministic
  dependency-first order, calls the selected entry bridge, and calls every finalizer in the exact reverse order. Foreign
  objects receive no generated lifecycle or entry calls.
- The output parent must already exist and resolve to a directory. The output itself must be absent or a regular file;
  aliases and other non-regular final objects are rejected. Output aliases of a caller native input, consumed `.l1m`,
  runtime native input, or the resolved `dea_rt.h` wrapper input are rejected. Wrapper and capture artifacts live in an
  exclusively created `.l1c-link-...` transaction beside the output and are cleaned on success and failure; there are no
  caller-input snapshots. The host linker writes the executable directly to `OUTPUT`, so final executable replacement is
  not transactional.
- Normal compiler families receive the selected regular runtime archive as an exact path. Under the compatibility
  exception defined for TinyCC, L1 uses the complete variant-matched regular runtime object set when available;
  otherwise it attempts the same exact archive selection. These native inputs are not byte-inspected. `L1_CFLAGS` and
  `--c-options` configure wrapper compilation and are not appended as final-link command words. Because the resulting
  wrapper object is opaque, compiler options may still cause the host compiler to encode toolchain-specific linker
  controls that the final linker honors; those effects are caller-trusted. The final command places the wrapper first,
  then the encounter-ordered user link stream, then the selected runtime native inputs by exact path, followed by the
  ordinary non-MSVC math-library and output arguments. A user `-L` therefore cannot shadow the selected runtime.
- Until native Windows process spawning replaces `cmd.exe`, exact standalone-link command words and redirection paths
  containing `%`, `!`, `"`, carriage return, or line feed are rejected before scratch allocation.

The detailed artifact, validation, ordering, transaction, and portability contracts live in
[l1/docs/reference/separate-compilation.md](../../../l1/docs/reference/separate-compilation.md).

## 9. Compatibility Rule

Equivalent behavior keeps the same flag names, aliases, option ordering, exit-code meanings, and diagnostic meanings
across stages and levels. A level may recognize a shared spelling while reporting that its capability is unavailable,
but it must not reinterpret that spelling. A level-specific extension must be documented in the shared contract and in
its owning level's live docs before it is treated as public behavior.
