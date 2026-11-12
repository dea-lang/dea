# Dea/L0 Release Notes

This directory contains the curated release body for each Dea/L0 stable release. A stable `l0-vX.Y.Z` tag must have a
matching `X.Y.Z.md` file, and the release workflow publishes that file unchanged as the GitHub release description.

New releases and snapshots carry the Stage 2 reference as `dea_l0_stage2_api_reference-<TAG>.pdf`, the offline HTML/PDF
bundle `dea_l0_stage2_autodocs-<TAG>.tar.gz`, and the separate Chirpy export `dea_l0_stage2_api_reference-<TAG>.tar.gz`,
alongside four platform compiler archives and `SHA256SUMS`. Compiler archives embed the same verified offline bundle.
Historical releases retain their original mixed-reference assets. External importers must adopt the new export filename
before the first publication using this contract.

## Release Preparation

Follow the shared versioned release preparation process in
[MONOREPO.md](../../../MONOREPO.md#versioned-release-preparation). Metadata, canonical notes, and final current-release
documentation must be in the validated tree on `main` before tagging; retain `X.Y.Z.dev0` in package metadata. The asset
inventory above and unchanged canonical release body are L0-specific requirements.

The authorization rules in [AGENTS.md](../../../AGENTS.md#remote-and-publication-authorization) and
[l0/AGENTS.md](../../AGENTS.md#release-and-documentation-publication) apply throughout. The durable identity and
publication contract is recorded in
[l0/docs/decisions/0017-release-identity-integrity-and-immutable-publication.md](../decisions/0017-release-identity-integrity-and-immutable-publication.md).

## Releases

- [l0/docs/releases/2.2.0.md](2.2.0.md)
- [l0/docs/releases/2.1.1.md](2.1.1.md)
- [l0/docs/releases/2.1.0.md](2.1.0.md)
- [l0/docs/releases/2.0.0.md](2.0.0.md)
- [l0/docs/releases/1.1.0.md](1.1.0.md)
- [Dea/L0 1.0.0 on GitHub](https://github.com/dea-lang/dea/releases/tag/l0-v1.0.0)
