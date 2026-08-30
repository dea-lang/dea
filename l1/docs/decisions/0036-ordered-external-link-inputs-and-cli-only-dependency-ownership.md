# ADR-0036: Ordered External Link Inputs and CLI-Only Dependency Ownership

- Decision date: 2026-08-30
- Last edited: 2026-08-30
- Status: Accepted

## Context

L1 build, run, and standalone link already share one verified link planner for authoritative Dea interface/object pairs
and caller-asserted foreign relocatables. Binding modules also need native libraries, library search paths, runtime
search paths, and occasional host compiler-driver arguments. Those controls can be order-sensitive, and encoding them in
`.l1m` files would make Dea module identity responsible for host package and deployment policy.

The compiler must expose the native controls without letting raw arguments bypass the typed Dea-object and
foreign-object boundaries. It must also preserve exact runtime selection so a user library search path cannot shadow the
runtime archive or TinyCC compatibility inputs chosen by the driver.

## Decision

L1 accepts repeatable external-link controls in `--build`, `--link`, and `--run`:

- `-lNAME` and `-l NAME` select a native library.
- `-LDIR` and `-L DIR` add a native-library search path.
- `-Rr=DIR`, `-Rr DIR`, `--rpath=DIR`, and `--rpath DIR` add a runtime dynamic-library search path.
- `-Cl=ARG`, `-Cl ARG`, `--link-arg=ARG`, and `--link-arg ARG` add one intact host compiler-driver argument.

The parser records Dea objects, caller-asserted foreign objects, libraries, search paths, rpaths, and raw driver words
in one typed encounter-ordered stream. The common link executor lowers each entry at that position instead of sorting
inputs by category. Rpaths use a documented compiler-family lowering; Windows and unsupported compiler families reject
them before native linking rather than inventing an unverified spelling. A TinyCC rpath containing a comma is likewise
rejected because its comma-separated `-Wl` transport cannot preserve that value as one linker operand. The MSVC driver
family also rejects canonical `-l` / `-L` entries because its `/link` layout cannot preserve the shared ordered
driver-word semantics through a mechanical GNU-style translation; callers may supply an explicit accepted `.lib` as a
raw word.

`--link-arg` is an explicit one-word escape hatch, not an alternate object-input channel. Object-suffixed `-l` values,
raw words, and `-Wl,` payload segments are rejected with guidance to use a positional Dea object plus its sibling
`.l1m`, or `--foreign-object` for a caller-asserted foreign relocatable. Response-file, object-file-list, and
driver-config indirection are also rejected. The boundary is intentionally syntactic across compiler families; archive
and shared-library arguments remain valid native link inputs.

The driver appends its already validated runtime inputs by exact path after caller-selected inputs: one selected archive
for normal compiler families, or the complete variant-matched TinyCC raw-object set when available with exact-archive
fallback. User `-L` entries therefore cannot change which Dea runtime is selected.

External native dependencies remain invocation-owned. Dea adds no package manifest, per-module native-library
declaration, `.l1m` host-link record, or automatic dependency discovery. Existing `.l1m` `link` records continue to
describe Dea provider obligations only. Build tools and callers repeat the necessary CLI controls for each invocation.
Dea does not inspect native bytes for hidden linker controls; explicitly typed CLI entries are the supported request
surface, while any hidden controls are left to host-toolchain behavior.

## Rationale

- A single ordered stream preserves native linker semantics across standalone link and build/run.
- Typed object roles keep Dea identity and caller assertions auditable even when a raw host-driver escape hatch exists.
- CLI-owned dependencies avoid prematurely turning `.l1m` into a host package or deployment manifest.
- Exact runtime paths preserve the selected runtime variant independently of user search paths.
- Explicit compiler-family rpath handling fails predictably on hosts where no supported lowering exists.

## Consequences

- L1 binding workflows can use legacy unmangled `extern func` declarations with explicit native dependencies today; the
  typed `extern "C"` surface remains owned by Initiative 0003.
- Native library discovery, static-versus-dynamic choice, and load-time deployment remain host-toolchain concerns.
- Dynamic linking is load-time linking; this decision adds no `dlopen` or `LoadLibrary` runtime API.
- Future Stage 2 L1 implementations must preserve the option forms, ordering, validation, and runtime-selection
  behavior.
- Any future package or binding-local dependency metadata requires a separate decision and cannot silently reuse `.l1m`
  provider records.

## Related Plans

- [l1/work/initiatives/closed/0001-separate-compilation-and-linking.md](../../work/initiatives/closed/0001-separate-compilation-and-linking.md):
  completed separate-compilation and external-linking initiative
- [l1/work/plans/features/closed/2026-04-24-external-library-linking-cli-noref.md][external-linking]

## Current Docs

- [docs/specs/compiler/cli-contract.md][cli]: shared option spellings and L1 mode scope
- [l1/docs/user/linking.md][linking]: supported workflows, option forms, and platform expectations
- [l1/docs/reference/separate-compilation.md][separate-compilation]: common ordered link planning
- [l1/docs/reference/design-decisions.md][design-decisions]: L1 native dependency ownership policy
- [l1/docs/reference/architecture.md][architecture]: Stage 1 driver and common link-executor boundaries

[architecture]: ../reference/architecture.md
[cli]: ../../../docs/specs/compiler/cli-contract.md
[design-decisions]: ../reference/design-decisions.md
[external-linking]: ../../work/plans/features/closed/2026-04-24-external-library-linking-cli-noref.md
[linking]: ../user/linking.md
[separate-compilation]: ../reference/separate-compilation.md
