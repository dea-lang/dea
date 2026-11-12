# Bug Fix Plan

## Canonical distribution architecture

- Date: 2026-11-13
- Status: Completed
- Title: Normalize L0 distribution architecture in metadata and archive names
- Kind: Bug Fix
- Severity: High
- Stage: 2
- Subsystem: Distribution packaging and release validation
- Modules:
  - `l0/scripts/dist_tools_lib.py`
- Test modules:
  - `l0/tests/test_dist_tools_lib_fallback.py`
  - `l0/tests/test_release_tag_policy.py`

## Summary

Windows distributions record the native architecture as `AMD64` and use `windows-amd64` in archive names, while release
and snapshot checksum validation requires `windows-x86_64`. This blocks publication after successful builds and smoke
tests. Canonicalize package architecture without changing L0's metadata format, OS spelling, or raw compiler host
provenance.

## ADR Impact

- Decision: Use canonical architecture tokens for L0 package metadata and archive identity.
  - Scope: L0
  - Disposition: Amend ADR
  - ADR: `l0/docs/decisions/0023-toolchain-installation-and-distribution-layout.md`
  - Rationale: Architecture naming refines the existing distribution metadata and filename contract.

## Implementation

1. Shared architecture normalization between the `VERSION` writer and archive-name builder: `amd64` maps to `x86_64` and
   `aarch64` maps to `arm64`; preserve other lower-case sanitized architecture tokens.
2. Regression coverage checks native Windows host spelling, canonical POSIX spellings, aliases, and unchanged raw
   compiler provenance.
3. Checksum tests generate compiler filenames through the production builder and execute both publication fragments,
   including rejection of a missing Windows archive.
4. Current packaging documentation, the distribution ADR, and the 2.2.0 tooling migration notes describe the contract.

## Verification

- Before the fix, the new regressions rejected `arch: AMD64` and reproduced the publisher's missing Windows archive.
- From `l0/`, `make test-dist-fallback test-release-tags` passed after the fix. Coverage includes nine simulated host
  spellings and both release/snapshot checksum fragments. These are local fixture checks, not native Windows execution.
- Root `python3 scripts/check_adr_impact.py --all-active` passed before closure.
- Native Windows archive construction and smoke validation remain hosted checks after a separately authorized push.
- No compiler/runtime semantics or trace inputs change. Tags, pushes, workflow dispatch, and publication remain outside
  this local repair's scope.
