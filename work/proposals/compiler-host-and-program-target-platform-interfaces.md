# Compiler-Host and Program-Target Platform Interfaces Proposal

Version: 2026-07-26

Status: Proposed

Scope: Shared

## Summary

Dea currently reaches Linux, macOS, and MinGW by lowering conservatively to C99 while selecting POSIX or Win32
operations inside compiler and runtime sources. That is sufficient for the validated hosts, but it is not yet a
portability interface: a non-Windows build usually falls into a POSIX branch, and compiler logic also embeds assumptions
about paths, shells, temporary directories, executable suffixes, compiler arguments, object containers, and hosted C
library services.

This proposal separates two independent porting axes:

1. the **compiler host**, where a Dea compiler executable runs and obtains source, writes output, and optionally invokes
   a C toolchain or a child program;
2. the **program target**, where generated Dea code and its runtime execute.

Each axis receives a private, statically linked C99 interface with explicit capabilities and exactly one selected
provider. Toolchain and object-format policy form a third, target-facing profile rather than being inferred from the
compiler host. POSIX and MinGW become reference providers, hosted ISO C99 becomes an intentionally reduced provider, and
freestanding C99 becomes a provider contract plus a repository-owned conformance implementation.

This is a direction proposal, not an implementation plan and not an accepted public ABI. It adds no Dea syntax, `std.*`
surface, dynamic plugin mechanism, or newer C requirement. If accepted, the work should proceed through focused shared
plans that preserve current behavior while moving platform details behind the proposed boundaries.

## Current Problem

The design documents already say that generated code should remain conservative C99 and that platform-specific behavior
belongs at a C runtime boundary. The implementation does not consistently provide a replaceable boundary yet:

- The L0 runtime used to build both native compilers includes Win32 headers when `_WIN32` is defined and otherwise
  includes POSIX headers. File access, process execution, process identifiers, clocks, and metadata are implemented
  directly in the header.
- The L1 runtime is split into useful concern-specific translation units, but its public `dea_rt.h` still includes
  hosted and OS headers and exposes private implementation types such as `FILE *` and `time_t`.
- L0 Stage 2 and L1 Stage 1 build drivers encode temporary-root discovery, PID/time-based names, POSIX and `cmd.exe`
  quoting, executable lookup, null-device names, suffixes, and compiler-family argument conventions.
- L1 compile-only adds four narrow filesystem operations in `l1/compiler/stage1_l0/support/interface_fingerprint.c`;
  that translation unit selects Win32 or an unconditional POSIX branch and has no third provider.
- L1 compile-only can inspect relocatable ELF, Mach-O, and selected PE/COFF objects. A target using another container
  cannot complete the current object-validation path even if its C compiler can consume generated source.

Consequently, a third port must edit compiler/runtime core files, and an unknown platform can fail through missing POSIX
headers rather than through a deliberate unsupported-platform decision.

## Vocabulary and Independence

- **Build platform:** the platform on which a compiler binary or runtime archive is produced.
- **Compiler host:** the platform on which the compiler binary executes.
- **Program target:** the platform on which generated code executes.
- **Compiler-host provider:** an implementation of the services used by compiler logic.
- **Target-runtime provider:** an implementation of the low-level services used by generated programs and the Dea
  runtime.
- **Target-toolchain profile:** policy for producing and inspecting target artifacts, including compiler/linker
  arguments, runtime artifacts, startup, ABI validation, and object-container adapters.

A native build may select the same platform family for all three roles, but the contracts remain distinct. For example,
a POSIX compiler host may invoke an embedded cross-compiler, link a freestanding target-runtime provider, and inspect an
ARM ELF object. Conversely, a compiler port to a non-POSIX hosted system may still produce binaries for an existing
POSIX target.

No provider selection may infer the program target merely from the compiler host.

## Goals

1. Permit a new compiler host without editing compiler algorithms or adding another platform branch throughout the
   compiler.
2. Permit a new generated-program target without editing the public Dea language ABI or pretending that every target has
   files, processes, clocks, or an operating system.
3. Let a reduced compiler host support useful frontend and generated-source modes without claiming build, run, or
   transactional publication.
4. Keep generated C and platform-neutral runtime declarations within conservative C99.
5. Make missing capabilities explicit and testable instead of silently selecting POSIX behavior or fabricating values.
6. Preserve existing POSIX and MinGW behavior as reference implementations.
7. Keep cross-target toolchain, startup, ABI, and object-inspection policy separate from host filesystem/process
   services.

## Non-Goals

- Implementing either interface in this proposal.
- Making a full compiler practical on a device that cannot supply source storage, diagnostics, or the services required
  by the selected compiler mode.
- Defining one binary runtime archive that runs on every C99 implementation.
- Guaranteeing filesystem transactions, symlink handling, directories, or process control through ISO C alone.
- Supporting every object container, calling convention, C compiler command line, MCU, or RTOS in the first
  implementation.
- Adding public capability queries, conditional imports, target annotations, or other Dea language/stdlib features.
- Loading providers dynamically or selecting between several providers during one process.
- Changing current runtime semantics merely to accommodate a weak provider.

## Common Provider Model

Both interfaces should use flat, statically linked C99 functions rather than function-pointer tables:

- the contract is declared by a versioned private header;
- a build selects and links exactly one implementation;
- values crossing the boundary are fixed-width integers, explicit byte spans, opaque handles where necessary, and small
  result records defined by the private header;
- Dea ARC values, `FILE *`, `time_t`, `struct stat`, Win32 handles, and provider-specific error objects never cross the
  boundary;
- every provider exposes its interface version and capability bits;
- every operation distinguishes success, ordinary absence/collision where relevant, unsupported capability, invalid
  input, and provider/operating-system failure;
- provider-owned resources have explicit close/release operations and remain valid only for their documented lifetime.

The exact symbol spellings, numeric values, and header locations should be fixed by the first implementation plan after
checking existing private ABI namespaces. The provisional names in this proposal are `dea_compiler_host.h` and
`dea_runtime_platform.h`.

Recognized POSIX and Windows builds may continue to auto-select their existing provider for compatibility. Any other
platform must select a provider explicitly or fail configuration with a clear unsupported-host/target message. An
`#else` branch must never mean "assume POSIX."

## Compiler-Host Interface

### Boundary

Compiler implementations should depend on one internal Dea facade backed by the private `dea_compiler_host.h` interface.
Compiler algorithms should not call OS-facing `sys.rt` operations directly or encode shell, temporary-root, suffix, or
path-separator policy.

The compiler-host contract is grouped by capability so a partial port remains useful.

### Storage and paths

The storage group should provide:

- read a byte sequence from a source path;
- write or replace a regular output file where ordinary mode semantics permit it;
- remove a regular file;
- classify a path without following a link-like object;
- create one directory exclusively, preserving collision/error distinction;
- move one regular file to an absent destination on the same storage domain;
- remove one empty real directory;
- identify absolute paths, separators, parents, and joins according to the selected host provider.

Paths cross the C boundary as byte spans with embedded NUL rejected. A provider documents how those bytes map to its
native namespace. This proposal does not silently define every Dea string as a native path or settle a universal path
encoding; a later implementation plan must preserve existing source-path behavior while making translation explicit.

### Private workspaces

The workspace group should reserve an exclusively owned workspace as one provider operation. Compiler logic supplies a
purpose and optional preferred parent but does not construct names from `TMPDIR`, `/tmp`, `TEMP`, PIDs, timestamps, or
random suffixes. The provider returns an owned workspace handle/path and defines cleanup operations.

This group is separate from ordinary file I/O because secure reservation, permissions, cleanup, and same-storage
publication cannot be reconstructed portably from C99 `fopen`.

### Processes and tools

The process group should provide:

- executable lookup without `command -v`, `where.exe`, or shell parsing;
- launch from an argument vector rather than one quoted command string;
- explicit working directory and environment overrides;
- stdout/stderr inheritance, redirection, or capture;
- a normalized distinction between launch failure, ordinary exit, signal/exception termination when the provider can
  represent it, and unsupported execution;
- child execution for `--run` as a distinct capability from invoking a build tool.

Compiler code describes a semantic compile/link request to a target-toolchain profile. The profile produces the argument
vector; the host provider launches it. This prevents platform process semantics and target compiler syntax from becoming
one abstraction.

### Basic host data

The remaining groups cover console byte I/O, compiler arguments, environment lookup, and wall/monotonic time where
available. Compiler algorithms must not use a PID or clock merely to simulate exclusive workspace creation.

### Mode capability floor

The initial capability model should express at least:

| Compiler operation     | Required host capabilities                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| Tokenize, parse, check | source reads and diagnostic output                                                                           |
| Emit an interface      | frontend capabilities plus output writes                                                                     |
| Generate C             | frontend capabilities plus output writes                                                                     |
| Build                  | generated-C capabilities plus private workspace, tool invocation, and a target-toolchain profile             |
| Run                    | build capabilities plus child execution                                                                      |
| L1 compile-only        | output-parent and transactional storage operations, tool invocation, and a supported target-object inspector |

A mode whose requirements are unavailable fails before analysis or mutation with one capability diagnostic. Partial
providers do not expose a degraded interpretation of the same mode.

## Program-Target Runtime Interface

### Split the public ABI from platform services

Generated code should continue to call the stable `rt_*` and private `_rt_*` runtime surface. That surface should be
implemented by a platform-neutral runtime core which calls one private `dea_runtime_platform.h` provider.

The raw provider contract should be shared across L0 and L1 wherever its fixed-width, byte-oriented operations permit
that. Each level keeps its existing public runtime ABI and may use a level-local adapter, but a platform port should not
have to reimplement the same allocator, console, clock, or filesystem mechanics merely because both language levels are
installed. Extracting L0's currently header-defined OS calls into linkable hooks is therefore part of adopting this
boundary; it does not require merging the L0 and L1 runtime cores.

The generated-code ABI header should contain only target-neutral C99 types, declarations, constants, and inline helpers.
Hosted and OS headers, stream objects, native time types, platform handles, and trace output implementation belong in
runtime-private headers and provider sources. `dea_rt.h` may remain the compatibility umbrella, but including it from
generated C must not itself select POSIX or Win32.

### Required target services

A usable general Dea runtime provider must supply:

- allocate, reallocate, and release storage with the alignment required by the runtime;
- panic/abort and normal termination hooks;
- startup integration that initializes the runtime and invokes the generated program lifecycle;
- a minimal raw diagnostic-write hook suitable for panic and optional trace output.

A real embedded provider may implement allocation with a fixed arena or RTOS allocator. A target that supplies no
allocation can support only a separately defined allocation-free subset; this proposal does not claim that ordinary Dea
programs become heapless automatically.

### Optional target capabilities

Optional groups should include:

- console byte input, output, and flushing;
- filesystem byte streams, metadata, and deletion;
- wall time, monotonic time, calendar conversion, and local-time information;
- program arguments, environment values, and process identity;
- child/shell execution;
- pseudorandom seeding and, if later needed, entropy;
- floating-point math support.

The existing public runtime wrapper maps an unavailable operation to its existing failure shape when one exists: `null`,
`false`, `-1`, or a supported-query result such as `monotonic_supported() == false`. An operation with no failure
representation must fail through a deterministic "platform capability unavailable" panic rather than return a fabricated
PID, timestamp, argument, or successful result.

This policy requires no new public capability API. A later proposal may add one only if real portable applications need
to select behavior dynamically.

### Startup

Target-neutral generated code should expose one reserved internal program-run operation that performs runtime
initialization, module initialization, the optional program entry, module finalization, and result propagation. Its
exact C symbol is deferred to the linking/wrapper implementation plan.

- A hosted startup provider implements C `main(argc, argv)` and forwards arguments.
- An embedded provider calls the program-run operation from a reset handler, RTOS task, firmware hook, or application
  callback.
- Per-module objects retain their platform-neutral lifecycle symbols and do not acquire a process-level `main`.

## Target-Toolchain Profile

Host services cannot by themselves describe a cross target. A separate target-toolchain profile should own:

- a stable target/profile identifier;
- target ABI requirements and validation probes;
- source, object, archive, executable, and auxiliary suffixes;
- semantic compile and link requests translated into argument vectors;
- runtime include and library artifacts;
- hosted or embedded startup selection;
- target linker policy and required system libraries;
- object-container inspector selection and symbol-decoration rules.

The compiler host launches the resulting argument vectors but does not interpret them. The target-runtime provider
implements program services but does not decide how the compiler executable launches tools.

ELF, Mach-O, and supported PE/COFF inspectors remain built-in profiles. A target using another object format must add a
bounded object-reader adapter before object-validating modes can accept its artifacts. Generated C followed by an
external build system remains the universal escape hatch when no operational toolchain or inspector profile exists.

## Generic Hosted-C99 Profiles

"Generic C99" means portable source against a stated ISO C implementation profile. It does not mean a universal object
ABI or a promise that ISO C provides operating-system services.

### Program target

A real generic hosted-C99 target-runtime provider is feasible and should be included. Using only the hosted ISO C99
library, it can provide:

- heap allocation, reallocation, and release;
- ARC, strings, hashing, and other platform-neutral runtime core behavior;
- panic, abort, normal exit, console streams, and flushing;
- `main` arguments and environment lookup;
- basic whole-file reading, writing, and deletion through C streams;
- coarse wall time, with a zero subsecond component when no finer source exists;
- the existing pseudorandom behavior;
- C99 mathematical functions when the target passes Dea's floating-point validation.

It must report these capabilities unavailable unless an explicit extension provider supplies them:

- directory creation, enumeration, and removal;
- reliable rich file metadata, link/reparse classification, and no-follow access;
- atomic/no-clobber publication and private transaction workspaces;
- process identity;
- monotonic time;
- normalized tool or child-process execution;
- platform ACL, permission, durability, and crash-recovery guarantees.

The provider should not use ISO C `system()` as proof of a normalized process capability: the presence, command
language, status encoding, and quoting rules of the command processor remain implementation-defined.

### Compiler host

A reduced generic hosted-C99 compiler-host provider is also feasible. It may use C streams for source and output files,
the standard streams for diagnostics, `getenv` for configuration, and ordinary `main` arguments. It can support frontend
modes, interface emission, and generated-C output within the storage behavior it advertises.

It must not claim build, run, or transactional compile-only merely because ISO C exposes `system()` and `rename()`.
Those modes require provider extensions for argument-vector process launch, private workspaces, path classification, and
the publication semantics their contracts require.

## Freestanding-C99 Profile

Freestanding C99 is feasible as a port contract, not as a universal ready-to-run provider. The freestanding standard
does not guarantee heap allocation, stdio, files, time, math, an environment, or hosted `main`.

The repository should include a conformance provider and harness that:

- supplies a fixed-pool allocator and reallocator suitable for focused tests;
- supplies panic/termination capture and a custom startup entry;
- optionally supplies a bounded byte console;
- advertises filesystem, process, environment, PID, and clock services as unavailable;
- builds the platform-neutral runtime core without POSIX or Win32 headers;
- runs a small generated program through the target-neutral program entry.

Real MCU and RTOS ports replace those hooks with board, firmware, vendor-library, or RTOS implementations. No particular
board or RTOS is selected by this proposal.

## Target Validation

C99 alone does not guarantee every representation required by Dea. A target profile must validate, before accepting
affected programs or building its runtime:

- availability and exact widths of 8-, 16-, 32-, and 64-bit integer types;
- supported `size_t`, pointer width, pointer/integer conversion, and runtime allocation-record layout assumptions;
- required alignment behavior;
- compiler support for the C99 features emitted by the backend;
- IEEE-style `float` and `double` behavior when a program uses those types;
- target endianness and object-container support where artifact inspection depends on them;
- target startup and calling-convention compatibility.

An unsupported property is rejected explicitly. Generic source portability must never weaken Dea semantics by silently
adopting an implementation-defined representation.

## Provider Selection and Packaging

A future implementation plan should define the concrete build layout, but every port bundle should identify:

- its compiler-host implementation, if any;
- its target-runtime implementation, if any;
- capability declarations and interface versions;
- one or more target-toolchain profiles;
- startup adapters;
- required object-reader adapters;
- conformance-test entry points.

Build configuration selects one compiler-host provider for each compiler binary and one target-runtime/toolchain profile
for each generated program. POSIX and MinGW defaults preserve today's native workflows. A generic hosted-C99 provider is
selected deliberately; it is not an excuse to guess at unsupported services. An unknown platform with no selected
provider fails early.

The interfaces remain private implementation boundaries. Installing a target port may deliver runtime headers, archives,
configuration, and startup objects, but does not make the private provider hooks part of the Dea language or the stable
C FFI.

## Error and Diagnostic Policy

- Compiler capability failures occur before analysis or output mutation and identify the missing mode capability and
  selected host/target profile.
- Runtime optional-service failures use existing public failure representations where possible.
- Runtime calls with no failure representation panic deterministically when their provider capability is absent.
- Provider-specific error values may be attached to internal diagnostics but do not replace stable Dea diagnostic
  meanings.
- This proposal reserves no diagnostic codes. Each implementation plan must re-check the live catalog before adding
  codes.

## Alternatives

### Continue adding platform conditionals

Rejected. It keeps the current platforms working but makes every new port edit shared compiler/runtime code and leaves
unknown hosts on an accidental POSIX path.

### Treat ISO C99 as a complete OS abstraction

Rejected. Hosted C99 provides useful allocation, streams, environment, time, and math facilities, but not the
filesystem, process, workspace, metadata, or atomicity contracts required by all compiler modes. Freestanding C99
provides still less.

### Reuse one interface for compiler host and program target

Rejected. A compiler host needs source/workspace/tool-launch semantics, while a generated program may run without a
filesystem or process model. Cross compilation also requires the two selections to differ.

### Use callback tables

Deferred. Function tables permit runtime injection and multiple instances, but static C symbols are smaller, easier to
dead-strip, friendlier to embedded linkers, and sufficient for one provider per compiler binary or target program.

### Expose the provider through `std.fs` or `sys.rt`

Rejected. The compiler needs stronger private semantics than the current public filesystem surface, and target providers
should remain replaceable without adding language-level APIs.

## Validation for Future Implementation

An implementation based on this proposal is complete only when:

01. platform-neutral compiler code contains no OS calls, shell quoting, `/tmp`, `NUL`, executable lookup commands, or
    platform suffix selection;
02. generated-code/runtime ABI headers contain no POSIX or Win32 declarations and no `FILE *` or `time_t` boundary;
03. POSIX and MinGW reference providers preserve existing behavior and pass their current matrices;
04. a direct provider conformance suite covers success, ordinary absence/collision, unsupported capability, invalid
    input, and provider failure;
05. reduced-host tests prove that supported frontend/generated-source modes work and stronger modes fail before
    mutation;
06. the generic hosted-C99 target runs representative allocation, string, console, file, time, random, and supported
    math scenarios without POSIX or Win32 APIs;
07. the freestanding conformance provider links and runs a generated program through custom startup;
08. incompatible integer, pointer, floating-point, toolchain, and object-format profiles are rejected explicitly;
09. a cross-target scenario demonstrates that compiler-host and program-target selection are independent;
10. a source audit confirms that platform conditionals occur only in providers, target profiles, object adapters, and
    narrowly documented compiler/toolchain probes.

## Adoption Sequence

If this direction is accepted, implementation should be split into focused shared plans:

1. define private interface contracts, capability/result conventions, provider selection, and conformance harnesses;
2. extract L0 runtime host dependencies so both native compiler binaries can link a replaceable compiler-host provider;
3. migrate compiler storage, workspace, process, and path policy behind the compiler-host facade;
4. split the L1 target runtime into a platform-neutral core and POSIX, MinGW, hosted-C99, and freestanding-conformance
   providers;
5. separate hosted `main` from the target-neutral program lifecycle;
6. introduce target-toolchain profiles and preserve generated-C external-build fallback;
7. prove the boundaries with reduced-host, generic hosted-C99, freestanding, and cross-target validation.

Each plan must keep L0/L1 porting rules explicit. The future L1 Stage 2 compiler should consume the settled interfaces
rather than reintroduce Stage 1 platform logic.

## Decision Criteria

This proposal is ready for acceptance when:

1. compiler-host and program-target selection are agreed to be independent;
2. partial compiler-host modes and optional target capabilities have defined failure behavior;
3. hosted-C99 and freestanding-C99 claims match what those C implementation profiles actually guarantee;
4. the private/static interface posture is accepted;
5. current POSIX and MinGW behavior can be preserved through reference providers;
6. future linking and Stage 2 work can consume the boundaries without fixing a process-level `main` or host toolchain
   policy into target-neutral code.

## Proposal Lifecycle

1. Keep this document under `work/proposals/` while the direction remains proposed.
2. Do not describe the private interfaces or generic profiles as implemented or supported targets yet.
3. Link future portability, runtime, linking, compile-driver, and Stage 2 plans to this proposal rather than duplicating
   the two-axis model.
4. On acceptance, graduate the settled boundaries into shared architecture decisions and level-specific runtime,
   compiler, ABI, and platform documentation.
5. Open implementation plans only after re-checking current build topology, diagnostic reservations, target ABI
   assumptions, and active linking/self-hosting plans.

## Related Work

- [L0 language and runtime design decisions][l0-design] describe the small C kernel/runtime boundary and conservative
  C99 lowering.
- [L1 language and runtime design decisions][l1-design] require platform quirks to remain outside language semantics and
  unsupported targets to be rejected.
- [L0 stdlib module boundaries][stdlib-boundaries] distinguish console I/O from filesystem operations specifically to
  support targets without filesystems.
- [Transactional compile-only publication][compile-publication] defines the current trusted-parent, POSIX, and MinGW
  boundary that a compiler-host provider must preserve.
- [L1 compiler ABI][l1-abi] defines portable lifecycle and metadata symbols plus the currently supported object
  containers.
- [Link-set driver and wrapper plan][link-wrapper] owns future process-level wrapper and link orchestration.
- [Per-module generated-C plan][per-module-gen] preserves generated C as the external-build fallback.
- [L1 Stage 2 self-hosting plan][stage2] must not mechanically copy accidental Stage 1 platform assumptions.
- [L1 project status][l1-status] records the current validated host/toolchain posture.

[compile-publication]: ../../l1/docs/decisions/0022-transactional-compile-only-artifact-publication.md
[l0-design]: ../../l0/docs/reference/design-decisions.md
[l1-abi]: ../../l1/docs/specs/compiler/abi.md
[l1-design]: ../../l1/docs/reference/design-decisions.md
[l1-status]: ../../l1/docs/project-status.md
[link-wrapper]: ../../l1/work/plans/features/closed/2026-07-17-link-set-driver-and-wrapper-noref.md
[per-module-gen]: ../../l1/work/plans/features/closed/2026-08-21-per-module-generated-c-foundation-noref.md
[stage2]: ../plans/features/2026-07-11-shared-l1-stage2-self-hosting-port-noref.md
[stdlib-boundaries]: ../../l0/docs/decisions/0015-stdlib-module-boundaries.md
