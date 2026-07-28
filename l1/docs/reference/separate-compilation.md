# L1 Separate Compilation and Standalone Linking

Version: 2026-07-28

This document describes the implemented Dea/L1 Stage 1 path from one-module compilation to a verified standalone
executable. It is the current behavioral reference for `l1c --compile` and `l1c --link`.

Ordinary `--gen`, `--build`, and `--run` remain source-based, legacy single-translation-unit flows. They do not yet
reuse the separate-compilation graph or standalone-link executor.

Related canonical documents:

- shared CLI surface and exit-code rules: [docs/specs/compiler/cli-contract.md][cli]
- L1 symbol, fingerprint, and object-metadata ABI: [l1/docs/specs/compiler/abi.md][abi]
- textual interface format: [l1/docs/specs/compiler/module-interface-format.md][interface-format]
- compiler pipeline and ownership: [l1/docs/reference/architecture.md][architecture]
- generated-C and runtime-link details: [l1/docs/reference/c-backend-design.md][backend]
- shared diagnostic meanings: [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]

## 1. Implemented Workflow

Compile each source-backed module against verified textual interfaces:

```text
l1c --compile MODULE [-I INTERFACE_ROOT]... [-o CANONICAL_OBJECT_PATH] [-Gk]
```

Each successful invocation publishes a reusable `.o` plus `.l1m` pair. `--keep-c` additionally publishes the exact
generated `.c`. Compile-only requires `.l1m` providers for every non-virtual import and does not fall back to provider
source.

Link an explicitly supplied object set:

```text
l1c -k DEA_OBJECT... [-Cf C_OBJECT]... [-e MODULE] -o OUTPUT
```

`--link` / `-k` requires at least one positional Dea object and exactly one non-empty output path. Positional Dea paths
and repeatable `--foreign-object PATH` / `--foreign-object=PATH` / `-Cf PATH` / `-Cf=PATH` operands retain their CLI
encounter order. `--entry MODULE` / `--entry=MODULE` / `-e MODULE` is optional, accepts one canonical dotted module
name, and may appear at most once.

Source roots, system roots, interface roots, `--keep-c`, `--all-modules`, `--include-eof`, runtime arguments after `--`,
and analysis-only options are not valid link inputs. Host compiler/options, runtime include/library paths, trace flags,
`--unchecked`, and `--check-basic` remain valid because the wrapper must be compiled and the matching runtime variant
must be linked. `L1_CFLAGS` and `--c-options` configure wrapper compilation only; they are never forwarded to the final
host-link command. External `-L`, `-l`, rpath, and raw host-link argument surfaces remain reserved.

## 2. Artifact Authorities

The two phases deliberately use different authorities:

- Compile-only resolves source plus verified `.l1m` interfaces, generates one module translation unit, and embeds the
  resulting module identity, whole-interface fingerprint, entry flag, and ordered direct object-backed imports in the
  object.
- Standalone link reads only the explicitly supplied relocatable objects. It does not reopen `.l1` source or `.l1m`
  interfaces, discover objects by module name, or infer additional link inputs from the filesystem.

Every independently compiled Dea object must define a complete `I8metadata` identity record, an `I7imports` ordered
import record, exactly one `I4init`, exactly one `I4fini`, and an `I5entry` exactly when its identity carries
`HAS_ENTRY`. The object reader validates those relationships before returning valid Dea metadata.

## 3. Tri-State Object Classification

Each link operand is inspected exactly once by the bounded ELF, Mach-O, or standard little-endian COFF reader. File
access failures, unsupported containers, corrupt tables, archives, shared libraries, import objects, and executables are
object-read failures rather than metadata classifications.

| Reader result            | Positional Dea operand                                                | Explicit `--foreign-object`                                                  |
| ------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `ValidDeaMetadata`       | Accepted and registered under its canonical module identity           | Rejected; foreign spelling cannot bypass graph, fingerprint, or entry checks |
| `NoDeaMetadata`          | Rejected with guidance to use `--foreign-object`                      | Accepted unless the normalized object defines process symbol `main`          |
| `MalformedDeaMetadata`   | Rejected with the reader's metadata reason                            | Rejected; malformed Dea evidence is never treated as metadata absence        |
| Object/container failure | Rejected before graph, wrapper, transaction, or host-link work begins | Rejected before graph, wrapper, transaction, or host-link work begins        |

Independent of metadata classification, the readers normalize format-recognized embedded linker-control carriers: ELF
`SHT_LLVM_DEPENDENT_LIBRARIES`, Mach-O `LC_LINKER_OPTION`, and PE/COFF `.drectve`, including `.drectve` reached through
the standard decimal or LLVM base-64 string-table section-name encodings. Their presence rejects either operand role
with `L1C-2110`. Directive payloads are neither interpreted nor allowlisted, so hidden libraries, entry overrides, and
raw host-link options cannot bypass the typed CLI boundary.

The normalized `__dea` prefix is reserved. Any external definition under it is Dea evidence, so a supported object with
such a definition but without one complete consistent metadata pair classifies as malformed, not foreign. A foreign
object may provide ordinary unmangled C symbols used by current `extern func` declarations, but it never acquires Dea
module, dependency, fingerprint, lifecycle, or entry semantics.

The generated wrapper owns process `main`; a foreign object defining normalized `main` is rejected before host linking.

## 4. Graph, Fingerprint, and Entry Checks

After classification and before scratch allocation, the driver enforces:

1. Each canonical Dea module identity occurs exactly once. Repeating one path or supplying different objects with the
   same identity is the same duplicate-module error.
2. Every ordered import in every Dea object's metadata names one supplied Dea provider. Foreign objects cannot satisfy
   module edges because they have no canonical identity.
3. Every consumer's stored expected fingerprint exactly equals the supplied provider object's own embedded
   whole-interface fingerprint.
4. The complete supplied dependency graph is acyclic. Cycle diagnostics use canonical module names rather than input
   path spellings.
5. Without `--entry`, exactly one supplied Dea object must carry `HAS_ENTRY`; zero or multiple candidates fail, and
   multiple candidates are listed in canonical sorted order.
6. With `--entry`, the selected module must be present and carry `HAS_ENTRY`. Valid metadata guarantees that its exact
   module-owned `I5entry` symbol is present.

Extra explicitly supplied Dea objects remain part of the link set even when the selected entry component does not depend
on them. Unresolved ordinary C symbols, object architecture mismatches, and other failures not expressible in Dea
metadata remain host-link failures with the host tool's output preserved.

## 5. Deterministic Lifecycle Order

The driver computes lifecycle order once:

1. Visit the selected entry module's component first.
2. Follow each module's embedded direct imports in their recorded source order.
3. Append each module after all of its dependencies, yielding dependency-first order.
4. After the entry component, visit each still-unvisited positional Dea object in CLI encounter order, again following
   its ordered dependencies first.
5. Include every Dea module exactly once. Foreign objects never enter lifecycle order.

The generated C wrapper defines the only process-level `main(int argc, char **argv)`. It calls:

```text
_rt_init_args(argc, argv)
I4init for every module in dependency-first order
the selected module's I5entry
I4fini for every module in exact reverse order
return the normalized I5entry status
```

Only the selected entry bridge is declared and called. Module-local lifecycle functions continue to act only on storage
owned by their translation unit; they do not call dependency lifecycle functions themselves.

## 6. Wrapper Compilation and Final Host Link

The link driver resolves the host compiler, runtime include directory, public `dea_rt.h`, and runtime link inputs before
creating scratch state. It then:

1. writes `wrapper.c`;
2. compiles it alone to `wrapper.o`;
3. requires the compiler result to be a regular relocatable object;
4. writes one transaction-owned `input-N.o` snapshot from the exact bytes read and inspected for each typed user input;
5. invokes the host driver with `wrapper.o`, those snapshots in typed CLI encounter order, the selected runtime inputs,
   and the caller-selected output; and
6. requires the final output to be a regular file.

Non-MSVC command construction also supplies `-lm` unconditionally because object metadata does not record whether a
separately compiled module uses `sys.real`. Host stdout and stderr are captured and replayed under the normal logging
and failure policy. Raw C options do not enter the final command and therefore cannot smuggle additional objects,
archives, libraries, or linker controls around `--foreign-object`; object-embedded controls are rejected separately
during classification, and the generated wrapper object is inspected again before final linking. The current tranche
does not accept archives or libraries through `--foreign-object`. Relative input names beginning with a host-option or
response-file marker are rendered as explicit filesystem paths before invocation; MSVC also receives rooted slash paths
with native separators. Transaction snapshots close the inspection-to-link race: the host driver consumes the exact
bytes that passed classification and graph validation, even if a caller path is concurrently replaced.

On native Windows the current shell transport rejects exact command words and redirection paths containing `%`, `!`,
literal `"`, carriage return, or line feed. Standalone mode validates compiler paths, output/runtime paths, and parsed
`L1_CFLAGS` / `--c-options` words before scratch allocation, then rechecks the exact execution boundary. This prevents
`cmd.exe` environment expansion, delayed expansion, and quote-context termination until the driver has a direct
process-spawn transport. Diagnostics render rejected C0 bytes as hexadecimal escapes so blocked values cannot create
synthetic diagnostic lines.

Runtime mode selects `libdea_rt.a`, `libdea_rt_traced.a`, `libdea_rt_check_basic.a`, or `libdea_rt_unchecked.a`. Normal
compiler families always receive the selected archive as one exact path; the driver does not reduce it to a `-L` / `-l`
lookup.

ADR-0027 defines one compatibility carve-out. When the selected compiler family is TinyCC and the complete
variant-matched repo-local raw runtime object set exists, the driver links those objects directly. This accommodates
hosts such as Darwin where TinyCC emits ELF while the platform archives contain Mach-O objects. If the raw set is
unavailable, the driver falls back to validating and passing the selected archive by exact path. The carve-out does not
change the normal compiler-family contract or authorize arbitrary raw runtime inputs.

## 7. Output-Local Transaction

Standalone link uses a bounded transaction beside `OUTPUT`:

1. The output parent must already exist and resolve to a directory. Existing aliases in that caller-selected parent
   chain are trusted.
2. The final output itself is classified without following aliases and must be absent or a regular file. Directories,
   symlinks, reparse points, devices, and other objects are rejected. An existing regular output that is the same
   filesystem object as any caller input or selected runtime input is also rejected, including hard-link aliases.
3. Object classification, graph and entry validation, compiler selection, runtime include/link-input validation, and
   output validation all complete before scratch allocation.
4. The driver exclusively creates `.l1c-link-<pid>-<seconds>-<nanoseconds>-<attempt>` under the output parent. Attempts
   `0` through `99` are bounded; exhaustion fails without an unchecked fallback.
5. The transaction owns `wrapper.c`, `wrapper.o`, `compile.stdout`, `compile.stderr`, `link.stdout`, `link.stderr`, and
   one bounded `input-N.o` snapshot for each caller input. Original caller-supplied objects and the final executable
   remain outside it.
6. POSIX creation requests mode `0700`, subject to the process umask. MinGW creates the directory with inherited parent
   access control and retains no-follow reparse-point classification for cleanup.
7. Cleanup removes only known regular children without following aliases, then removes the verified empty directory. It
   never recursively deletes. Unexpected or substituted contents cause failure and retain the transaction path for
   inspection.
8. Cleanup failure returns nonzero even after a successful host link. A successfully produced executable remains at the
   requested path.

The host linker writes directly to `OUTPUT`. Existing-file replacement, partial host-link output, and rollback of the
final executable are not transactionally wrapped.

## 8. Current Boundary

Standalone linking is implemented; source fan-out for ordinary `--build` and `--run` is not. Those modes still generate
one legacy whole-program C translation unit. The later build/run orchestration can reuse the verified link planner and
executor while supplying scratch paths under its own invocation workspace.

External libraries, library search paths, rpaths, raw host-driver arguments, static/shared-library production, C++
interoperation, and object discovery remain outside the implemented standalone-link surface.

[abi]: ../specs/compiler/abi.md
[architecture]: architecture.md
[backend]: c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[interface-format]: ../specs/compiler/module-interface-format.md
