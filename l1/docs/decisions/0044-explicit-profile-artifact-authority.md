# ADR-0044: Explicit Profile Artifact Authority

- Decision date: 2026-10-19
- Last edited: 2026-10-21
- Status: Accepted

## Context

Managed preparation combines a native payload with automatic identity, freshness, lookup and storage policy. External
composition needs a complete caller-owned artifact whose creation and selection do not require a managed cache or the
original bundled installation sources.

## Decision

Expose `--create-profile -o PATH` and `--profile PATH` for compile, link, build and run. Publish schema-1 `profile.json`
with an independently maintained Dea compilation-contract version, frozen ordered configuration, copied public headers,
canonical module/interface/object inventory, selected runtime inputs and payload digests. Creation shares the existing
constructor, builds in owned sibling staging and publishes only to an absent destination.

Managed, command-private and explicit creation project their policy-resolved inputs through one frozen configuration
helper. Managed and public validation share payload record/role/duplicate, containment/regular-file and selected
size/digest mechanics. Schema parsing, expected inventory, header completeness, hash scheduling, diagnostics and
publication remain policy-owned. Managed schema-1 `manifest.json` and public schema-1 `profile.json` remain distinct;
managed entries keep toolchain-owned headers rather than copying the public artifact tree.

Selection is exact and read-only. Restore one configuration before preflight/frontend/native work; preserve explicit
provider precedence and semantic/lifecycle validation. Never discover, repair, substitute or write managed state. The
caller maintains suitable external compiler/SDK/environment inputs and creates a new artifact when those change.
Recognized path options become absolute external references; reject unsupported response/configuration and opaque
forwarding forms rather than reinterpret them against another cwd.

Bump the Dea contract for incompatible interface/fingerprint, codegen ABI, public-header/runtime or lifecycle/wrapper
protocol changes. Serialization uses its own schema version. Neither version nor a payload digest establishes native
semantic authenticity or arbitrary ABI compatibility.

## Rationale

A public artifact boundary makes manual compile/link composition use the same compiler, constructor and verified linker
as convenient builds. Keeping explicit caller stability separate from managed observation avoids promising freshness
without performing the observations needed to establish it.

## Consequences

Profiles can move on the same host with suitable unchanged external dependencies and do not need the creating cache or
original bundled inputs. Changing a profile means constructing a new destination. Cross-host distribution and automatic
toolchain mutation detection remain outside the contract. Shared construction and validation do not grant managed
freshness authority to an explicit success, route managed inputs through the public option whitelist, or change either
manifest format. Dependency discovery remains a later phase of the active initiative.

## Related Plans

- [l1/work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md][managed-client]

- [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan]

- [l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md][profile-review]

- [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]

## Current Docs

- [l1/docs/reference/explicit-profiles.md][profiles]
- [l1/docs/reference/stdlib-preparation.md][preparation]
- [docs/specs/compiler/cli-contract.md][cli]

[cli]: ../../../docs/specs/compiler/cli-contract.md
[initiative]: ../../work/initiatives/0010-explicit-profiles-and-composable-builds.md
[managed-client]: ../../work/plans/refactors/closed/2026-10-21-managed-profile-client-integration-noref.md
[preparation]: ../reference/stdlib-preparation.md
[profile-plan]: ../../work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[profile-review]: ../../work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md
[profiles]: ../reference/explicit-profiles.md
