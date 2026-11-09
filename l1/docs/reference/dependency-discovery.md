# L1 Semantic Dependency Discovery

Version: 2026-11-09

`--scan-deps` exposes the canonical resolver's semantic dependencies for external compilation scheduling. It emits
[P1689R5][p1689] JSON, version 1, revision 0. The report describes future compile actions, not the inputs actually
consumed by a later compiler invocation. Installed `l1c` needs neither Python nor Make.

## Scan contract

```sh
mkdir -p build
l1c --scan-deps app -Rp src --artifact-root build/modules -o build/dependencies.json
l1c --scan-deps app -Rp src -I vendor --profile build/profile --artifact-root build/modules
```

The target remains source-backed. Imported modules use existing interface-first resolution, with explicit `-I` roots
before bundled/profile interfaces and source fallback only when no authoritative interface was selected. Malformed
selected interfaces fail. `--artifact-root` maps canonical dotted names to future sibling `.o` and `.l1m` paths; it
neither creates these outputs nor adds an interface search root. Scans perform analysis and interface validation without
host compiler probes, native preparation, or managed native-cache access. Explicit profile selection verifies the
inventory without rereading original bundled source files.

Without `-o`, stdout contains one UTF-8 JSON document; diagnostics remain on stderr. With `-o`, publication follows
successful analysis and serialization and protects selected source/interface/profile inputs. The report parent directory
must already exist. A failed scan returns nonzero; callers must stop rather than consume a report from an earlier
successful invocation. Argument errors exit 2, while analysis and report errors exit 1.

On Windows, `l1c` inherits its L0 host's narrow command-line and filesystem APIs. Arbitrary Unicode filesystem paths are
not supported independently of the active code page. Use ASCII paths for portable Windows discovery and native
compilation. The Python adapter's Unicode path handling does not widen this compiler boundary; L1 programs' UTF-8
filesystem APIs are a separate runtime contract.

## P1689 projection

Each selected source module contributes one rule in deterministic dependency-first order:

| Field            | Meaning                                                                                        |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `work-directory` | Absolute invocation directory anchoring relative paths.                                        |
| `primary-output` | Planned object path under the artifact root.                                                   |
| `outputs`        | Planned sibling interface path.                                                                |
| `provides`       | Canonical `logical-name`, selected `source-path`, and planned `compiled-module-path`.          |
| `requires`       | Canonical provider names and selected or planned interface paths needed by strict compilation. |

Requirements include transitive closure through source and prebuilt providers, including graph-loaded link-only
interfaces. A prebuilt provider has no invented source action. Virtual modules impose no filesystem obligation.
Conflicting output ownership is rejected. Darwin and Windows conservatively reject case-fold-equivalent output names,
even where a particular filesystem could distinguish them; this output restriction does not redefine file identity.
Essential scheduling facts use core fields; any `_dea_` annotations can be removed without changing the build. The
report is not replacement `.l1m` link metadata: fingerprints, ordered lifecycle imports, provider validation and entry
selection still belong to interfaces and `l1c --link`.

This is a P1689R5 projection, not a claim of ISO standardization or automatic CMake integration. Retained-C discovery,
arbitrary per-module destinations and compile-time consumed-input reports are outside this version.

## Separate input sets

Discover using project sources and intentional prebuilt roots. Compile with the same prebuilt roots in the same order,
then append the generated-interface root. Do not feed previous generated interfaces into discovery unless intentionally
selecting them as prebuilt inputs. Otherwise, adding an import in a source provider could be hidden by its older
interface. Explicitly passing that root to `-I` retains ordinary interface-first behavior.

Before compilation, validate that no canonical generated-root interface candidate exists for a report-selected prebuilt
provider. This includes regular files, symlinks, dangling links, directories and aliases, even when an earlier prebuilt
root would currently mask the candidate. Choose a fresh artifact root or clean the conflicting output explicitly. The
adapter does not delete old artifacts; unrelated leftovers are permitted. Serialize discovery, preflight and the
complete inner build against other writers to the same generated root.

## Optional GNU Make adapter

[l1/scripts/p1689_make.py][adapter] uses only Python's standard library. It reads the core report and caller-selected
artifact root, validates mappings and existing prebuilt interfaces, and writes a Make fragment:

```sh
python3 l1/scripts/p1689_make.py build/dependencies.json --artifact-root build/modules -o build/dependencies.mk
```

GNU Make 4.3 or newer is required; macOS system Make is insufficient. Use `gmake` on macOS and MSYS2's
`/usr/bin/make.exe` with a UTF-8 locale on Windows to preserve recipe paths. `DEA_TEST_MAKE` selects the executable for
both compiler integration and adapter tests; an invalid explicit selection fails. L1 CI provisions GNU Make on macOS and
pins MSYS2 Make with `LC_ALL=C.UTF-8` on Windows. The fragment exposes `DEA_OBJECTS`, `DEA_INTERFACES` and
`DEA_LINK_DEPS` for Make prerequisites, plus shell-quoted `DEA_OBJECT_ARGS` for the final link command. Each explicit
grouped rule covers the module's object/interface pair and calls the caller's `DEA_COMPILE` macro with the shell-quoted
source path, primary object destination and canonical module name as `$(1)`, `$(2)` and `$(3)`. The example compiles the
canonical name with the same ordered discovery roots, preserving dotted module identity. The caller never derives the
object destination from `$@`. A missing peer forces the whole action even when only the surviving peer is requested.
Parallel consumers wait for the paired action to complete.

The adapter validates the whole report before accepting a fragment and preserves its timestamp when bytes are unchanged.
Every source action and the final link depend on that fragment. A changed graph or selected provider therefore rebuilds
conservatively even when the new input is older than current outputs. Run a fresh scan and adaptation before every inner
Make build; do not create a self-remaking included-file loop. Stop after any failed scan, preflight or adapter
invocation.

The project supplies `DEA_CONFIG_STAMP` for compiler/options/profile/root changes and `DEA_COMPILE_DEPS` for native
headers and other compilation inputs. Header changes must recompile affected pairs. Final-link dependencies additionally
cover caller-selected runtime libraries, prebuilt objects and foreign inputs. Semantic-only bundled interfaces need not
have sibling objects. The adapter does not discover native dependencies or execute compiler commands.

The executable depends on the current source-object set plus the fragment, so implementation-only edits relink and
removed source objects stop participating. Pass the same canonical target to discovery and final `--link --entry`; never
infer the entry from rule order or imported modules. A target without eligible `main` fails linking.

The executable example is [l1/compiler/tests/fixtures/dependency_discovery/Makefile][example], with its project-owned
outer driver. Its `inputs` configuration carries scan/compile source and interface roots, while `link_inputs` contains
only link-valid interface/profile selection. `native` and `link_native` separately scope native options. Its lock
encloses scanning, adaptation, configuration publication and inner Make. This demonstrates the supported composition
boundary; it is not production compiler/stdlib build adoption.

JSON path encoding, Make token escaping and shell argument quoting are separate contracts. The adapter supports spaces,
UTF-8 Unicode, quotes and `#`. It rejects control characters, `$`, `%`, `*`, `?`, brackets, commas, parentheses, `|`,
`;`, literal POSIX backslashes and non-drive colons. Windows drive/UNC paths use native separator semantics. Recipes
assume a POSIX-compatible shell, including MSYS2 on Windows; the compiler report itself retains broader JSON path
support. Literal `include` filenames leave drive colons unescaped; Windows command-line Make goals use forward
separators to match the generated targets. Unsupported adapter paths fail before fragment publication. Native-platform
comparisons use native filesystem semantics; simulated Windows checks do not establish native Windows execution.
Timestamp-based rebuilding can recompile consumers when identical interface bytes are republished. Content-preserving
interface writes, per-symbol invalidation and a persistent incremental database remain separate work.

[adapter]: ../../scripts/p1689_make.py
[example]: ../../compiler/tests/fixtures/dependency_discovery/Makefile
[p1689]: https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2022/p1689r5.html
