# L1 Separate Compilation, Build, Run, and Standalone Linking

Version: 2026-08-23

This document describes the implemented Dea/L1 Stage 1 path from per-module generated C and one-module compilation to an
interface-authoritative executable. It is the current behavioral reference for `l1c --gen`, `l1c --compile`,
`l1c --build`, `l1c --run`, and `l1c --link`. Generated-C, compile-only, build, and run all consume the same per-module
backend operation; build/run add graph fan-out and reuse the verified link planner, lifecycle wrapper, and executor.

Related canonical documents:

- shared CLI surface and exit-code rules: [docs/specs/compiler/cli-contract.md][cli]
- L1 symbol and fingerprint ABI: [l1/docs/specs/compiler/abi.md][abi]
- textual interface format: [l1/docs/specs/compiler/module-interface-format.md][interface-format]
- compiler pipeline and ownership: [l1/docs/reference/architecture.md][architecture]
- generated-C and runtime-link details: [l1/docs/reference/c-backend-design.md][backend]
- shared diagnostic meanings: [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics]

## 1. Implemented Workflow

Generate one source-backed module, with interface-first imports and source fallback only when no interface is selected:

```text
l1c --gen MODULE [-I INTERFACE_ROOT]... [-o EXACT_C_PATH]
```

The target itself must resolve from source. A selected valid imported `.l1m` is sufficient without native siblings.
Generation writes only stdout or the exact requested file, creates no companions, and never invokes a host compiler or
linker.

Compile each source-backed module against verified textual interfaces:

```text
l1c --compile MODULE [-I INTERFACE_ROOT]... [-o CANONICAL_OBJECT_PATH] [-Gk]
```

Each successful invocation publishes a reusable `.o` plus `.l1m` pair. `--keep-c` additionally publishes the exact
generated `.c`. Compile-only requires `.l1m` providers for every non-virtual import and does not fall back to provider
source.

Build or run a source-rooted graph:

```text
l1c --build MODULE [-I INTERFACE_ROOT]... [-Cf C_OBJECT]... [-o OUTPUT] [-Gk]
l1c --run MODULE [-I INTERFACE_ROOT]... [-Cf C_OBJECT]... [-Gk] [-- PROGRAM_ARG...]
```

Both modes expand the requested source target under `MRP_ALLOW_SOURCE_FALLBACK`. The first selected interface is
authoritative and contributes its original opaque sibling `.o`; otherwise a provider may fall back to source and is
compiled once into the invocation workspace. Source nodes compile dependency-first with direct-import order as the
deterministic tie-breaker. The requested target is the explicit link entry and must itself define an eligible bridge;
`--entry` is invalid. Foreign objects are caller-asserted opaque inputs and retain their relative declaration order.

Build writes the requested or default executable. Run writes a temporary executable, launches it directly with exact
post-`--` arguments, returns its status, and cleans it. Build keep-C retains `OUTPUT.dea-c/`; run keep-C retains
`<canonical-target>.dea-c/`. Both trees mirror dotted module paths and contain root `__dea_wrapper.c`; the destination
must be absent and contains only exact generated C bytes. A root module named `__dea_wrapper` remains buildable and
runnable without retention, but it and its ASCII case variants report `L1C-2132` with keep-C because both canonical
outputs may claim the root wrapper path on case-insensitive filesystems.

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
must be linked. `L1_CFLAGS` and `--c-options` configure wrapper compilation and are never forwarded as final-link
command words. The wrapper object is opaque, however, so caller-selected compiler options may encode toolchain-specific
linker controls that the final linker honors. External `-L`, `-l`, rpath, and raw host-link argument surfaces remain
reserved; effects carried through the caller-controlled wrapper compilation are trusted rather than inspected.

## 2. Artifact Authority and Trusted Pair

Compile-only resolves one source module against verified `.l1m` providers, generates one module C translation unit, and
publishes a canonical sibling `.o + .l1m` pair. The interface carries module identity, the public fingerprint, `entry;`,
ordered direct lifecycle imports, and `require` / `link` expectations. The object carries native definitions plus
`I4init`, `I4fini`, and conditional `I5entry`, but no embedded Dea metadata.

Before publication the staged object must be a regular file. The staged interface bytes must equal the selected
publication bytes, parse, pass full verification, and carry the expected identity and public fingerprint. Compile-only
does not inspect the staged object's bytes or prove object/interface agreement. Endpoint rollback remains sequential,
not reader-atomic or crash-safe.

Generated C and the object use their canonical module-relative names inside the private compile transaction. The host
compiler runs from that transaction root and receives paths such as `pkg/sub.c` and `pkg/sub.o`, independently of the
random transaction identity and caller destination. Known relative compiler and runtime-include paths retain their
invocation-directory meaning. Bare compiler names are frozen to the invocation-time command-search result, including
explicit empty and relative search components, before the working-directory change. For debug-producing GNU-style
options such as `-g`, `-g3`, and `-ggdb`, a configured name, canonical filesystem target, or recognized Darwin system
alias identity that identifies Clang or GCC records the private debug compilation directory as stable `.` metadata;
invocation retains the selected compiler alias. Opaque wrappers are outside this recognition boundary. These measures
prevent driver-controlled transaction and destination paths from entering native metadata, but they do not guarantee
byte-identical objects because the host toolchain controls all other native contents. Byte comparisons under an
available recognized toolchain serve as regression evidence for this path neutrality. Every generated-C mode retains
exact C-byte identity for the same resolved inputs and code-generation options.

For standalone link, every positional operand must have a nonempty basename stem followed by the exact case-sensitive
terminal suffix `.o`. Replacing only that suffix with `.l1m` in the same directory selects the required sibling. `.o`,
`dir/.o`, separator-terminated paths, and other suffixes are rejected. Both paths must resolve to regular files; input
symlinks are allowed when their targets are regular.

The verified sibling is the sole Dea semantic and lifecycle authority. The pair's basename does not independently
constrain module identity. All Dea objects remain explicit CLI operands: interface imports and dependencies validate the
supplied set but never search for or add native paths.

The pair is caller-trusted. No checksum, native symbol, data anchor, metadata section, or other mechanism binds its two
files. Build systems and callers must create, copy, replace, invalidate, and keep the pair stable together from
selection through link submission. Concurrent target replacement is outside the contract for standalone link, build, and
run. Mixed-generation pairs may fail interface validation, fail at the host link, or link successfully with incorrect
native behavior.

## 3. Opaque Native Input Boundary

Dea performs no Dea-side reads of caller Dea or foreign object bytes, compiled wrapper bytes, runtime archive bytes, or
TinyCC runtime-object bytes during standalone link, build, or run.

- A positional Dea `.o` is an opaque native payload paired with its verified interface.
- `--foreign-object` asserts that one regular-file path names a host-compatible relocatable object. The foreign input
  has no Dea identity, fingerprint, dependency, lifecycle, or entry semantics.
- Dea does not prove native format, architecture, relocatability, symbols, absence of `main`, absence of reserved
  `__dea` definitions, or absence of embedded linker controls for either input role.
- Archives, shared libraries, linker scripts, response files, rpaths, and raw host-link arguments remain outside
  `--foreign-object` even if a host toolchain accepts a mislabeled operand.

Native-format errors, duplicate symbols, entry collisions, architecture mismatches, hidden controls, and unresolved C
symbols are host-tool concerns. Their captured diagnostics are preserved under `L1C-2109`.

## 4. Interface Verification, Graph, and Entry Checks

Before scratch allocation, the driver performs these phases in order:

1. validate CLI operand roles, exact positional `.o` suffixes, and regular-file status;
2. derive, read, UTF-8 validate, parse, and run full interface verification on every sibling `.l1m`;
3. reject the complete set if any interface fails, so unverified identities never enter graph state;
4. register canonical module identities and reject duplicates;
5. require every non-virtual provider named by `import module`, `require`, or `link` to be explicitly supplied and to
   carry the exact expected verified public fingerprint;
6. resolve explicit or inferred entry selection from `entry;` records;
7. compute lifecycle order and reject lifecycle-import cycles in one iterative traversal; and
8. require every non-virtual `require` / `link` provider to be transitively reachable from its consumer through a
   nonempty path of existing `import module` edges.

Within-interface provider disagreement fails earlier under `SIG-0284`. `L1C-2102` is reserved for comparison between an
interface expectation and the supplied provider interface. `require` and `link` never create lifecycle edges or implicit
objects. The provenance walk uses fresh local iterative scratch per consumer and does not mutate lifecycle visit state
or order.

Without `--entry`, exactly one verified interface must carry `entry;`; multiple candidates are reported
deterministically. With `--entry`, the named supplied interface must carry `entry;`. Entry selection precedes lifecycle
cycle detection, so `L1C-2104` wins when the same set also contains a cycle.

Extra explicitly supplied Dea roots remain in the link set even when the selected entry component does not depend on
them.

## 5. Deterministic Lifecycle Order

Standalone link retains one nonrecursive, three-state depth-first traversal:

1. Visit the selected entry module's component first.
2. Follow each module's `import module` records in stored order.
3. Append each module after all of its providers, yielding dependency-first order.
4. After the entry component, visit each still-unvisited positional Dea root in CLI encounter order.
5. Include every Dea module exactly once. Foreign inputs never enter lifecycle order.

Build/run derives the same dependency-first lifecycle relation from the canonical source/interface graph, following each
node's ordered direct imports and compiling source-backed nodes in that order. Because its requested source target
defines the complete graph root, it has no standalone-style extra positional Dea roots. Both paths pass the resulting
order to the same wrapper emitter.

The generated C wrapper defines process `main(int argc, char **argv)`. It calls:

```text
_rt_init_args(argc, argv)
I4init for every module in dependency-first order
the selected module's I5entry
I4fini for every module in exact reverse order
return the normalized I5entry status
```

Only the selected entry bridge is declared and called. Module-local lifecycle functions act only on storage owned by
their translation unit; they do not call dependency lifecycle functions themselves.

## 6. Wrapper Compilation and Final Host Link

Before scratch allocation, the link driver resolves and validates the host compiler, parsed wrapper options, runtime
include directory, exact public `dea_rt.h`, runtime native inputs, output path, and every original caller object path.
Runtime archives and TinyCC runtime objects are checked as regular files rather than read.

The driver then:

1. writes `wrapper.c`;
2. compiles it alone to `wrapper.o`;
3. requires the compiler result to be a no-follow regular file;
4. invokes the host driver with `wrapper.o`, every original Dea and foreign native path in exact interleaved CLI order,
   the selected runtime native inputs, the optional non-MSVC math-library argument, and the output arguments; and
5. requires the final output to be a regular file.

There are no caller-input snapshots. "Original path" means the original caller-selected file rather than copied bytes;
the existing host-safe renderer still disambiguates option-shaped paths and normalizes MSVC paths.

On native Windows the current shell transport rejects exact command words and redirection paths containing `%`, `!`,
literal `"`, carriage return, or line feed. Each source-object transaction validates its resolved compiler, working
directory, complete command, and capture names before invocation. Pre-allocation link validation covers every caller- or
environment-controlled value already known; after allocation, the common executor validates each exact rendered
wrapper-compile or final-link command together with its transaction-owned capture paths immediately before invocation.

Runtime mode selects `libdea_rt.a`, `libdea_rt_traced.a`, `libdea_rt_check_basic.a`, or `libdea_rt_unchecked.a`. Normal
compiler families receive one exact archive path. Under ADR-0027, TinyCC receives the complete variant-matched raw
runtime object set when available, with exact archive fallback. Native runtime inputs are opaque and the carve-out does
not authorize arbitrary public raw runtime inputs.

## 7. Output-Local Transaction

Standalone link uses a bounded transaction beside `OUTPUT`:

1. The output parent must already exist and resolve to a directory. Existing aliases in that caller-selected parent
   chain are trusted.
2. The final output itself is classified without following aliases and must be absent or a regular file. Directories,
   symlinks, reparse points, devices, and other objects are rejected.
3. An existing output may not be the same filesystem object as an original caller native input, a consumed `.l1m`, a
   selected runtime native input, or the exact resolved `dea_rt.h`, including hard-link aliases.
4. Interface, graph, entry, compiler/runtime, Windows preflight, and output validation complete before allocation.
5. The driver exclusively creates `.l1c-link-<pid>-<seconds>-<nanoseconds>-<attempt>` under the output parent. Attempts
   `0` through `99` are bounded; exhaustion fails without an unchecked fallback.
6. The transaction owns only `wrapper.c`, `wrapper.o`, `compile.stdout`, `compile.stderr`, `link.stdout`, and
   `link.stderr`. Original caller inputs and the final executable remain outside it.
7. Cleanup removes only known regular children without following aliases, then removes the verified empty directory. It
   never recursively deletes. Unexpected or substituted contents cause failure and retain the transaction path.
8. Cleanup failure returns nonzero even after a successful host link. A successfully produced executable remains at the
   requested path.

The host linker writes directly to `OUTPUT`. Existing-file replacement, partial host-link output, and rollback of the
final executable are not transactionally wrapped.

## 8. Current Boundary

Per-module `--gen`, compile-only, multi-CU build/run, and standalone linking are implemented. Build/run source fan-out
re-analyzes each source-backed graph node as a one-module entry against authoritative and already staged provider
interfaces, compiles it into private `.c`, `.o`, and `.l1m` companions, combines those with authoritative
interface/object providers and foreign objects through the verified link planner, and supplies all wrapper/capture paths
from its command-owned native workspace. `backend_generate_module(...)` is the only production C-generation entrypoint;
the legacy whole-program generator and backend-owned process wrapper have been removed.

For identical source, resolved graph, verified interfaces, fingerprints, code-generation settings, and compiler version,
`--gen`, compile-only keep-C, build keep-C, and run keep-C expose byte-identical module C. Build/run retention copies
the exact compiler input after linking, interface/object providers require and produce no C, and `__dea_wrapper.c`
remains outside module identity as a separate link-orchestration artifact.

External libraries, library search paths, rpaths, raw host-driver arguments, static/shared-library production, C++
interoperation, and object discovery remain outside the implemented standalone-link surface.

[abi]: ../specs/compiler/abi.md
[architecture]: architecture.md
[backend]: c-backend-design.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[diagnostics]: ../../../docs/specs/compiler/diagnostic-code-catalog.md
[interface-format]: ../specs/compiler/module-interface-format.md
