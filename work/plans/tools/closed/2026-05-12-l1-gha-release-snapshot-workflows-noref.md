# Tool Plan

## Add L1 snapshot and release GHA workflows

- Date: 2026-10-12
- Last reviewed: 2026-10-12
- Status: Completed
- Title: Add L1 snapshot and release GHA workflows
- Kind: Tooling
- Scope: Shared
- Severity: Medium
- Stage: Shared
- Targets:
  - L1 snapshot GHA workflow (`.github/workflows/l1-snapshot.yml`)
  - L1 release GHA workflow (`.github/workflows/l1-release.yml`)
  - Reusable L1 docs build (`.github/workflows/l1-docs-build.yml`)
  - Curated L1 versioned-release notes (`l1/docs/releases/`)
  - Monorepo release-line policy
- Origin: Root monorepo CI policy. Workflow files live at `.github/workflows/` and the release-line gating rules live in
  `MONOREPO.md`; both are monorepo-owned.
- Porting rule: Shared. Trigger, namespace, and publication policy belong here. L1 install layout, archive construction,
  launcher behavior, and installed smoke tests remain owned by the L1 productization plan.
- Target status:
  - L1 snapshot GHA workflow: Implemented and verified through hosted acceptance
  - L1 release GHA workflow: Core workflow verified through hosted acceptance; curated notes locally validated
  - L1 docs build integration: Canonical strict HTML/full-PDF handoff verified during hosted acceptance
  - Monorepo release-line policy: Curated-note policy documented; publication remains separately gated
- Subsystem: GitHub Actions / release tagging / monorepo release-line policy
- Modules:
  - `.github/workflows/l1-snapshot.yml`
  - `.github/workflows/l1-release.yml`
  - `.github/workflows/l1-docs-build.yml`
  - `scripts/l1_release.py`
  - `scripts/tests/test_l1_release.py`
  - `l1/Makefile`
  - `MONOREPO.md`
  - `docs/project-status.md`
  - `l1/docs/project-status.md`
  - `l1/docs/roadmap.md`
  - `l1/docs/releases/README.md`
  - `l1/docs/releases/X.Y.Z.md` (planned per prepared version)
- Test modules:
  - local workflow syntax and trigger/version/release-note policy validation
  - installed/archive smoke entrypoint supplied by L1 productization
  - separately authorized hosted snapshot and release acceptance checks
- Related:
  - [work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md][ci-release-plan]
  - [l1/work/plans/tools/closed/2026-04-02-l1-bootstrap-productization-noref.md][productization]
  - [l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md][autodocs]
  - [l0/work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md][l0-release-plan]
  - [l0/docs/releases/README.md][l0-release-notes]
  - [MONOREPO.md][monorepo]
  - [AGENTS.md][agent-policy] (remote and publication authorization)

## Completion

Completed on 2026-10-12. The snapshot, versioned-release, and reusable documentation workflows are implemented; hosted
acceptance passed on all four platforms. Curated versioned-release notes are implemented and locally validated.
[docs/decisions/0023-l1-release-workflow-policy.md][release-adr] records the release and note-composition policies;
delivery documentation, the ADR index, and plan links are updated. Publication remains separate release preparation and
requires its own authorization.

This plan began while L1 had two stages and initially depended on Stage 2 productization. The L1/L2 split retargeted
that delivery foundation to the sole L0-implemented L1 compiler before the release workflows were implemented. The
implementation phases below preserve that progression; historical Stage 2 evidence is not canonical L1 acceptance.

## Split prerequisite and delivery baseline

L1 0.1.0 must distribute the sole L0-implemented canonical `l1c` and matching stage-free schema-2 documentation. The
split and fresh canonical-artifact acceptance completed on 2026-10-11, satisfying this plan's implementation
prerequisites. Historical 2026-10-09 Stage 2 acceptance below remains prior-product evidence. The existing acceptance
workflow validates canonical artifacts. The three release/documentation workflows are implemented, locally validated,
and verified through hosted snapshot and versioned-release acceptance. Curated versioned-release notes are implemented
with focused local validation; publication remains separately gated.

Keep the exact immutable source/version/docs handoff, four platforms, seven assets, reserved L1 namespaces,
`make_latest=false`, safe retries, and separate authorization gates. No workflow dispatch, release tag, push, or
publication is authorized by this plan. Retargeting is tracked in
[work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md](../../refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md).

## Dependency Statement

The closed [work/plans/tools/closed/2026-04-02-l1-ci-release-line-noref.md][ci-release-plan] completed Phase 3 by
recording the release-line gate in [MONOREPO.md][monorepo]. Its Phase 4 deferred L1 release/snapshot workflows. This
plan owns that deferred work and the gate's implementation details.

The former Stage 2 installation/distribution and four-platform fresh-host acceptance were completed on 2026-10-09. That
implementation is retained and retargeted under the split plan. Canonical L1 uses stage-free schema-2 install,
documentation, result, and acceptance records. Fresh canonical artifact builds and checkout-free verification passed on
Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64. The current delivery contract is
[l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md][delivery] with the amended
[l1/docs/decisions/0001-bootstrap-adaptation-strategy.md][bootstrap]. The productization plan is closed with its
delivery and documentation handoff complete.

The old stage-separated reference plan is historical. Release integration consumes the newly generated canonical L1
HTML/full-PDF bundle matching the retained `.l0` compiler and its actual support. No old stage-selected bundle may be
relabeled. Generation and local acceptance do not depend on hosted release workflows.

The existing gate also requires documented release notes, tag gating, reproducible smoke tests, and continued exclusive
reservation of `l1-v*` / `l1-snapshot-*`. Recheck authoritative remote tags before activation; a historical namespace
check or an empty local tag list does not establish the current remote state.

## State at closure

Reviewed on 2026-10-12 against the completed split, canonical artifact acceptance, and installed release workflows:

1. The canonical split and artifact-acceptance prerequisites recorded in `MONOREPO.md` are met. L1 release/snapshot
   workflows are installed on `main`, and hosted snapshot/versioned-release acceptance passed on 2026-10-12. L1
   publication remains pending.
2. Existing L1 compiler CI and productization acceptance cover Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64.
3. L1 has one L0-implemented canonical compiler. Installation builds it privately and ignores development selections.
4. Installation/inventory/dist/smoke/evidence helpers retain their distinct responsibilities. The old native acceptance
   belongs to the Stage 2 artifact; fresh canonical product acceptance passed on all four native platforms.
5. L0 workflows provide examples, but Pages/blog work remains outside scope. L0 remains the active release line.
6. The L1 helper validates checked-in curated notes before versioned-release builds and appends generated commit history
   after that content. This behavior is locally validated; snapshots retain automatic notes.

## Defaults Chosen

1. Use separate manually dispatched snapshot and tag-triggered release workflows, with the same four host platforms as
   current L1 CI. Recheck runner labels and supported compiler versions when changing workflow environments.
2. Publish four L1 distribution archives, a separate canonical L1 HTML/PDF bundle, the canonical L1 PDF, and
   `SHA256SUMS`. Every compiler archive embeds the same verified canonical L1 HTML/PDF. Each archive contains its own
   `VERSION` and install manifest; do not upload four colliding assets named `VERSION`. Obsolete stage-selected docs are
   excluded from this set.
3. Snapshot tags use `l1-snapshot-YYYYMMDD-HHMM-<shorthash>` with a UTC timestamp. Releases accept only `l1-vX.Y.Z`,
   with nonnegative numeric components and no leading zeros except zero itself. The broad `l1-v*` event filter requires
   explicit validation before building or publishing; prerelease version suffixes are outside this scope.
4. Snapshots are GitHub Pre-releases; versioned releases are GitHub Releases. Release titles and notes headers use
   `Dea/L1 {version}`, with the package version rather than the level-prefixed tag. Release notes identify the payload
   as an L1 canonical L0-implemented development toolchain and state that release does not establish language/toolchain
   stability. Set `make_latest` to false so initial L1 publication does not replace L0 as the repository's latest
   release.
5. Consume L1's install/dist and smoke helpers; do not reimplement payload construction or compiler smoke logic in YAML.
   Use read permissions for build jobs and grant `contents: write` only to tag/publication jobs.
6. Versioned releases require checked-in curated notes using L0's version-to-file and heading conventions, followed by a
   generated commit-history section. Snapshots retain generated notes without requiring a curated version file.

## Artifact and Build Handoff

Consume the implemented contract in [l1/docs/reference/productization-inventory.md][inventory] and the validated
build/verify job pattern in [.github/workflows/l1-productization-acceptance.yml][acceptance-workflow]:

- Build the repo-local upstream L0 Stage 2 compiler from the selected source revision and select it through
  `L1_BOOTSTRAP_L0C`; productization owns the subsequent private canonical L1 repository/installed construction. Never
  use ambient `l0c`, select the payload through the development `l1c` alias, or infer L1 versions from L0 tags. Record
  the actual host C compiler and supported version, following `l1/AGENTS.md`. Running the packaged compiler must not
  require L0, Python, uv, or Make; native operations still require the supported host C/linker/preparation tools. The
  upstream L0 compiler and repository-mode construction artifacts are build-only dependencies, absent from the published
  payload.
- Run `make dist` from `l1/`. Stable tags map `l1-vX.Y.Z` to `DEA_DIST_VERSION=X.Y.Z`; snapshot tags map
  `l1-snapshot-...` to `DEA_DIST_VERSION=snapshot-...`. `RELEASE_VERSION` may be a workflow variable but is not the
  packaging API. Retain canonical L1 development identification and upstream/compiler provenance in both cases.
- Supply `DOCS_ARTIFACT=<downloaded-canonical-bundle>` from the docs job. Productization verifies schema 2, level,
  version, source identity, complete PDF status, and digests before embedding it. All platform builds consume identical
  docs bytes; compiler runners do not install TeX or regenerate documentation.
- Supply a unique `DIST_RESULT` path and consume the versioned JSON result after successful `make dist`. Verify schema 2
  with no stage field, version, host, and provenance, fail if the archive path is missing or ambiguous, and require
  exactly one `dea-l1/` archive root. Implemented names are `dea-l1-lang_<version>_<os>-<arch>_<YYYYMMDD-HHMMSS>.tar.gz`
  for Linux/macOS and `.zip` for Windows UCRT64, with UTC build time and normalized host tokens. The productization
  helper owns these details.
- Direct local smoke uses `make smoke-dist ARCHIVE=<archive-from-DIST_RESULT>` to extract into an unrelated path
  containing spaces, invoke installed launchers without activation or source-worktree dependencies, check `--help` /
  `--version`, and compile/run the bundled stdlib-using program. Require the installed canonical L0-implemented `l1c`
  and reject obsolete stage-bearing artifacts. Include standalone linking and native Windows launcher coverage as
  supplied by productization. Require offline canonical L1 HTML/PDF and the matching docs manifest in the extracted
  archive, with no obsolete stage-selected docs.
- Check the shipped semantic interfaces, input inventory, and rebuild sources. Native support is prepared into a
  separate writable cache; the installed payload stays unchanged. Reuse productization's cold-cache, warm-cache, and
  relocation checks rather than assuming a shipped runtime archive or copied native profile.
- Give each matrix artifact a unique host identifier. Publication requires all four expected archives to pass smoke
  checks, with matching L1 version and source provenance; reject missing, duplicate, or unexpected assets.

### Validated commands and transported evidence

Run build commands from `l1/` at the selected immutable source. Set `DEA_DIST_VERSION` from the validated tag mapping
above and use that same value for the docs job and every native build. Record the actual native compiler executable and
version on each runner, then set `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC` explicitly. The validated families are GCC on
Linux/Windows UCRT64 and Apple Clang on macOS; recheck supported versions and runner labels when changing workflows. On
Windows preserve checkout source bytes with `core.autocrlf=false` before checkout and use native UCRT64 Python.

The docs job runs:

```bash
make docs-artifacts DEA_DIST_VERSION="$DEA_DIST_VERSION"
```

Its bundle is `build/docs/artifacts/dea_l1_autodocs.tar.gz`. Set `L1_DOCS_RELEASE_TAG` to the selected tag for
release-oriented generation. Native build jobs download those same bundle bytes to an absolute `DOCS_ARTIFACT` path. For
an explicitly prepared upstream, run from `l1/` with the selected native compiler environment:

```bash
make -C ../l0 venv DEA_BUILD_DIR=build/dea
make -C ../l0 install-dev-stage2 DEA_BUILD_DIR=build/dea
export L1_BOOTSTRAP_L0C="$PWD/../l0/build/dea/bin/l0c-stage2"
```

The public installer can also prepare the absent repo-local default without changing its development alias. An invalid
explicit override fails; neither route uses ambient `l0c`.

For direct local reproduction, `make dist` accepts an absolute, unique `DIST_RESULT` destination and emits the archive
path in that schema-2 JSON. `make smoke-dist ARCHIVE=<absolute-path-from-result>` verifies the exact produced archive.
For workflow transport, use the existing orchestrator instead of rebuilding or hand-assembling evidence:

```bash
make test-productization-acceptance ACCEPTANCE_PHASE=build \
  DEA_DIST_VERSION="$DEA_DIST_VERSION" DOCS_ARTIFACT="$DOCS_ARTIFACT" \
  ACCEPTANCE_DIR="$ACCEPTANCE_DIR"
```

`ACCEPTANCE_DIR` must be an absolute new directory for this host, including on retries. The helper invokes the same
`dist` implementation with its own unique result destination and retains:

| Evidence                        | Consumer contract                                                                                                      |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| One native distribution archive | Exact basename, byte size, and digest from the original result; no glob-based selection.                               |
| `result.json`                   | Original schema-2 `DIST_RESULT`, including package/host/provenance and docs source/bundle digest.                      |
| `harness/`                      | Six standard-library-only Python files copied by the helper; transport the directory intact.                           |
| `acceptance.json`               | Created only after successful verification; schema 2, `status: passed`, archive digest, version, OS, and architecture. |

Upload build evidence as `l1-dist-evidence-<attempt>-<os>-<arch>` for exactly `linux-x86_64`, `macos-x86_64`,
`macos-arm64`, and `windows-x86_64`. On a fresh matching verification runner, download only that evidence, set `L1_CC`
and `L1_RUNTIME_CC` to supported native tools, and run from an unrelated working directory:

```bash
python3 -I "$ACCEPTANCE_DIR/harness/productization_acceptance.py" \
  --phase verify --directory "$ACCEPTANCE_DIR"
```

Use native UCRT64 `python` instead of `python3` on Windows. Verification requires Python's standard library and native
host tools; it does not require Make, docs generators, the checkout or bootstrap compilers. Preserve native host tooling
needed for preparation identity, including Linux `ldd`/`readelf`, macOS `otool`, and Windows system/UCRT64 runtime DLL
availability. The smoke helper owns the restricted semantic-only environment and private cache.

Keep `result.json` unchanged after transport: its original absolute archive path records construction, while the
verifier locates that basename inside the evidence directory and checks size/digest. Retain build/smoke logs and
host-specific acceptance reports as workflow evidence, separate from the seven release assets. Publication must match
all four successful reports to the archive bytes being staged, verify the expected host set, shared package/source
identity, and identical `docs_bundle_sha256` against the docs job, and reject missing, duplicate, stale, or unexpected
evidence. Never combine reports and archives from different attempts. A combined local acceptance run does not replace
these fresh jobs.

## Canonical L1 Documentation and Release Assets

The implemented reusable `l1-docs-build.yml` has read-only repository permissions and explicit immutable `source_ref`,
package version and release tag inputs. Release callers select canonical L1 references and require strict HTML plus full
PDF generation. Use Linux with Doxygen, Graphviz, the shared docs dependencies, vendored m.css, and TeX, following L0's
toolchain setup. Invoke `make docs-artifacts DEA_DIST_VERSION=<version>` with `L1_DOCS_RELEASE_TAG` set to the selected
tag. Upload the verified `dea_l1_autodocs.tar.gz` as `l1-autodocs-<attempt>`; expose the PDF from that same bundle, not
a separately regenerated build. No Pages artifact/deployment or blog export is required.

The generation plan owns the exact bundle layout and manifest. `build-docs` must finish before `build-dist` starts, and
publication needs successful docs, all four dist builds, and all four fresh-host verification jobs. Missing,
preview-only, obsolete-stage-selected, wrong-source, or wrong-version docs fail the workflow; there is no silent
compiler-only release fallback.

Stage release assets under these names, where `<TAG>` is the selected `l1-v...` or `l1-snapshot-...` tag:

- Four host distribution archives reported by their `DIST_RESULT` records.
- `dea_l1_autodocs-<TAG>.tar.gz`, containing offline HTML, the full PDF, and docs manifest.
- `dea_l1_api_reference-<TAG>.pdf`, byte-identical to the PDF in that bundle and each platform archive.
- `SHA256SUMS`, covering all six assets above with bare filenames and excluding itself.

Generate checksums after the complete set has been validated, then attach all seven files before publication. Draft
retry rules cover documentation assets as well as compiler archives; an existing published release remains immutable.
Obsolete stage-selected bundles are rejected; generate a fresh canonical L1 bundle.

## Release Notes and Retry Policy

### Curated versioned-release notes

Reuse the conventions established by [l0/docs/releases/README.md][l0-release-notes] and
[.github/workflows/l0-release.yml][l0-release-workflow]: each `l1-vX.Y.Z` tag requires a checked-in
`l1/docs/releases/X.Y.Z.md` file whose first line is exactly `# Dea/L1 X.Y.Z`. Maintain `l1/docs/releases/README.md` as
the release-notes index and author the prose by themes relevant to Dea users, including compatibility or migration
guidance where needed. Keep the existing canonical L0-implemented development-toolchain notice immediately after the
heading, including the statement that release does not declare language or toolchain stability.

The authoring contract and index are in [l1/docs/releases/README.md][l1-release-notes]. Per-version prose is prepared
and reviewed before its release tag; this implementation does not pre-author a future release or modify earlier
releases.

Read and validate the file from the same immutable source revision used by the builds. The `validate-release` job must
reject missing or empty notes, a mismatched heading, a missing development notice, or a body with no curated content
before documentation and distribution jobs start. There is no automatic commit-log-only fallback for a versioned release
with invalid notes. The publisher and matching draft retries must use the same source-bound content.

Preserve the checked-in Markdown as the opening release body, then append a blank-line-separated `## Commit history`
section containing `Changes since <baseline>:` (with the baseline formatted as code) and generated commit bullets. For
the first release, use `Initial L1 publication, including changes since L1 was introduced:` in that same section. Both
introductory phrases end with a colon for versioned releases and snapshots. The resulting order is:

1. The single `# Dea/L1 X.Y.Z` heading from the curated file, matching the GitHub release title.
2. The development-toolchain notice from that file.
3. The complete curated release notes, preserving their wording and section order.
4. `## Commit history`, the baseline or initial-publication paragraph, and the generated commit list.

L0 publishes its checked-in file as the entire body; L1 retains the generated history as an appended section. Do not
generate a second title or notice, place the baseline paragraph before the curated text, or write the generated section
back into the curated source file. Snapshots keep their current generated title, notice, and history; they do not
require or borrow a curated versioned-release file. Note composition does not add release assets or change the
immutable-publication policy.

### Generated history and retries

Fetch sufficient history and tags for the selected source revision. For snapshots, choose the nearest reachable prior L1
snapshot or version tag using Git graph distance (`git describe --tags --abbrev=0` with both namespace patterns and
excluding the current tag). For versioned releases, use only prior valid `l1-vX.Y.Z` tags so a recent snapshot does not
truncate the release notes. Exclude malformed version tags. If no eligible prior tag exists, start with the first
reachable commit introducing the `l1/` subtree (the April 2, 2026 bootstrap scaffold), including that commit, and end at
the selected revision. Exclude history preceding L1. Include the full commit range without a path filter: shared
monorepo changes can affect L1. Test mixed L0/L1 tags, the first L1 publication with and without pre-L1 history, and a
source branch whose newer repository tags are not ancestors.

Resolve the source ref once and build that immutable revision on every platform. Reuse an existing snapshot tag only
when it points to that revision; never move tags. A newly dispatched snapshot can have a new timestamp and therefore a
new tag. Job reruns must retain the preparation job's original identity. Check existing releases before upload: resume a
draft for the same tag, serialize publication per tag, and leave an already published release unchanged. A mismatched
published asset set requires explicit recovery rather than silently replacing assets. Failed builds leave publication
incomplete; do not delete tags automatically.

## Implementation and validation

The three workflows use [scripts/l1_release.py][release-policy] for immutable source/tag identity, strict version
mapping, release-note baselines, cross-host evidence validation, and draft publication. Each executable job begins with
`Show inputs`, logging the JSON input context and appending it to the job summary before checkout. The reusable docs job
reports its own source/version/tag inputs.

For versioned releases, `prepare` validates the curated file directly from the selected Git commit before writing
identity outputs. This gates documentation and native builds. Publication reads that same immutable file again and
appends generated history; moving branches and uncommitted note edits cannot change the selected prose. UTF-8 content,
line endings, and intentional whitespace in the curated body are preserved.

Snapshot preparation uploads the original run identity before creating its tag. Full reruns restore that identity
instead of resolving a moving branch again; automatic tags use the original run creation time. If no original identity
was retained, a rerun fails and requires a new dispatch. Documentation, build evidence, reports, and logs carry the run
attempt in their artifact names. Rerun all jobs after failure: partial reruns cannot combine prior-attempt artifacts
with new builds. Build and verification jobs retain read-only repository permissions; write permission is limited to
snapshot tag creation and publication.

Publication revalidates exact archive/result/report identity, the four-host set, clean selected source, matching docs
bundle and embedded PDF bytes, and the transported harness before staging seven assets. Windows result paths are parsed
with Windows path semantics on the Linux publisher. Matching draft retries may replace recognized older timestamped
archives; unexpected assets or mismatched draft identity fail. Uploaded asset sizes and digests must match the complete
staged set before publication. Already published releases are never modified. Both release types use
`make_latest=false`.

Local validation passed:

- `actionlint .github/workflows/l1-snapshot.yml .github/workflows/l1-release.yml .github/workflows/l1-docs-build.yml`.

- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_l1_release.py l1/tests/test_productization_acceptance.py l1/tests/test_distribution.py`:
  145 cases passed, including mocked GitHub effects, isolated Git-history fixtures, seven-asset aggregation, failed and
  stale evidence, and draft retries. Windows archive/path fixtures are simulated on the local host; these results do not
  establish native Windows workflow execution.

- `.venv/bin/python -m pytest -q -n 0 l1/tests/test_compiler_tooling.py scripts/tests/test_cleanup.py`: 113 cases passed
  and the inapplicable L0 `clean-runtime` case was skipped.

- `.venv/bin/python -m pytest -q -n 0 scripts/tests/test_l1_release.py`: 66 cases passed for the current release helper,
  including early rejection of invalid notes, immutable-source selection across preparation and draft retries, exact
  curated-text preservation and composition order, colon-terminated introductions, and snapshots without curated files.
  This reuses the existing Git fixtures and mocked GitHub boundary; it performs no remote publication.

- `.venv/bin/python l0/tests/test_release_tag_policy.py`, active-plan ADR validation, staged whitespace checks, and
  repository pre-commit hooks passed.

The policy suite is included in L1 `test-tooling`. Hosted acceptance passed on 2026-10-12 for `L1 Snapshot Release` and
`L1 Release`: strict documentation generation, Linux x86_64, macOS Intel/ARM, Windows UCRT64 builds, fresh verification
jobs, and all seven assets completed successfully. Versioned releases also verified matching `Dea/L1 {version}`
titles/headers and the previous-version baseline. The first-publication baseline is covered by local Git-history
fixtures and a repository-history check.

The hosted evidence covers the earlier generated-note workflows and unchanged artifact behavior. Curated-note
composition is locally validated, and delivery docs describe its authoring and publication contract. This documentation
closure reuses those results because the covered code, tests, workflows, and artifact contracts are unchanged.
[docs/decisions/0023-l1-release-workflow-policy.md][release-adr] records the completed policy. L1 publication remains a
separate gated action; recheck its remote namespaces before activation.

## Outcome

The implemented workflows consume canonical L1 productization and documentation, retain immutable release identity,
require complete four-platform evidence, and publish the seven validated assets. Snapshot and versioned-release
milestones passed. Versioned releases now preserve reviewed source-bound notes before generated history. The ADR and
current delivery docs record these contracts, completing this plan's scope.

## Implementation Phases

### Phase 1: Establish prerequisites

The release-line gate was documented before workflow implementation. Former Stage 2 productization passed native
acceptance on 2026-10-09. After the L1/L2 split, canonical L1 passed fresh four-platform artifact acceptance on
2026-10-11, including matching stage-free schema-2 documentation and verification without checkout or bootstrap
artifacts. This satisfied the implementation prerequisites.

### Phase 2: Add `l1-snapshot.yml`

Implemented on 2026-10-11 and verified through hosted acceptance on 2026-10-12. Manual dispatch resolves and retains
source/tag identity, then sequences canonical docs, four native builds, fresh verification jobs, asset checks, and
draft/pre-release publication. Optional `ref`, `snapshot_tag`, and `publish_release` inputs follow the identity, retry,
and authorization contracts above. Every executable job reports its inputs in its log and summary.

### Phase 3: Add `l1-release.yml`

Implemented on 2026-10-11 and verified through hosted acceptance on 2026-10-12. A versioned tag triggers strict
validation and the same documentation/build/verification handoff before publication with `prerelease=false` and
`make_latest=false`. The shared helper preserves tag-to-package-version mapping, scoped history, and safe draft retries.

### Phase 3 follow-up: Add curated versioned-release notes

Implemented and locally validated on 2026-10-12. The L1 release-notes index and authoring guide reuse L0 conventions.
Preparation validates immutable-source notes before builds; publication preserves their complete content and appends
generated history with colon-terminated introductions. Existing Git-history fixtures and the mocked publication boundary
cover invalid notes, source selection, ordering, text preservation, baselines, and retries. Snapshots remain automatic.

### Phase 4: Hosted acceptance, documentation, and closure

Completed on 2026-10-12. Snapshot and versioned-release acceptance verified strict docs, all four native builds and
fresh verification jobs, and all seven release assets. Focused local validation covers curated-note composition; the
earlier hosted evidence remains applicable to unchanged build/asset behavior. Delivery docs and links are updated, and
[docs/decisions/0023-l1-release-workflow-policy.md][release-adr] is indexed with its link to this closed plan.

## Release preparation

L1 publication remains pending outside this completed implementation and acceptance scope. Before activation, recheck
authoritative `l1-v*` and `l1-snapshot-*` tags and confirm the selected source and workflow revisions. Prepare and
review the version's curated notes, add its release-index entry, and commit them before selecting the tag.

Follow [AGENTS.md][agent-policy] for each remote action. Pushes, dispatches, tag creation, and tag pushes require their
respective explicit authorizations; show the exact destination, source, and downstream effects. Snapshot dispatch with
`publish_release=false` still creates/pushes a tag and uploads a draft. Implementation evidence and plan closure do not
authorize publication, and no duplicate acceptance release is required solely to close this plan.

## ADR Impact

- Decision: Establish an L1 development release line with level-qualified tags, separate snapshot/release workflows, and
  four-platform delivery with matching canonical L1 HTML/PDF artifacts.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0023-l1-release-workflow-policy.md`
  - Rationale: This defines durable monorepo publication policy, including release identity, asset completeness,
    development maturity labeling, and preserving L0's latest-release status. L1 payload and cache design remain owned
    by productization and its level-specific ADRs.
- Decision: Require canonical checked-in notes for each L1 versioned release and append generated history after the
  curated content, while keeping snapshots automatic.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0023-l1-release-workflow-policy.md`
  - Rationale: Note sourcing, early validation, and deterministic composition are shared workflow publication policy.
    ADR-0023 records this contract, reusing L0's conventions and documenting L1's history appendix.

## Non-Goals

- Implementing L1 source filters/renderers within workflow YAML; consume the dedicated documentation-generation plan.
- obsolete stage-selected doc release assets, blog dispatch, or Pages deployment.
- Changes to L0 release workflows or the historical-only bare `v*` namespace.
- Package registries, bundled host toolchains, or publication of installed native caches.
- Implementing install/dist, changing the selected canonical L0-implemented payload, or changing `l1-ci.yml` validation
  coverage.
- Declaring L1 language/toolchain stability merely because a GitHub Release exists.

## Verification Criteria

1. Local workflow validation covers syntax, all four platforms, event/input definitions, strict release tag validation,
   tag-to-`DEA_DIST_VERSION` mapping, release-note baselines, and draft/publication branching. Use small policy fixtures
   or mocked GitHub operations for first-publication and rerun cases; local checks must not create remote tags/releases.
2. Both workflows consume the landed L1 build/archive/smoke and documentation contracts and publish only after all four
   compiler archives and the matching complete canonical L1 HTML/PDF pass validation. Installed execution is independent
   of the source checkout and bootstrap/build tools, with native support prepared outside the payload. The explicit
   build-time upstream L0 compiler remains permitted and required. Fresh verification jobs download only transported
   evidence; publication requires four matching `status: passed` acceptance reports and checks their archive digests,
   host identities, and package version against the exact staged assets. Cross-platform aggregation also checks shared
   source identity and docs-bundle digest against the docs job; the per-host verifier alone does not establish those
   cross-job equalities.
3. A separately authorized manual snapshot creates the intended tag and publishes a Pre-release with all expected
   archives. Verify that `publish_release=false` retains a draft using local mocks or an explicitly approved hosted
   draft exercise. A draft exercise still has remote side effects.
4. A separately authorized versioned tag push builds and publishes the intended GitHub Release with all four archives.
   Neither L1 release type replaces L0's latest-release selection.
5. No L0 dist/docs assets, L0 release-note baselines, obsolete stage-selected docs, Pages, or blog publishing enter the
   L1 release jobs. Tests verify docs-before-dist ordering, wrong/stale docs rejection, all seven release files,
   checksum coverage, and identical canonical L1 PDF bytes in standalone, docs-bundle, and platform-archive forms.
6. Versioned releases require valid curated notes at the selected immutable source before builds begin. The published
   body preserves that content, includes one matching heading and development notice, and places the generated baseline
   paragraph and commit list after all curated notes under `## Commit history`. Snapshots still work without curated
   files; existing published releases remain unchanged.
7. Delivery docs distinguish implementation, hosted verification, and publication. The curated notes follow-up, both
   hosted milestones, the ADR, and link updates are complete; publication remains separately gated.

[acceptance-workflow]: ../../../../.github/workflows/l1-productization-acceptance.yml
[agent-policy]: ../../../../AGENTS.md
[autodocs]: ../../../../l1/work/plans/tools/closed/2026-10-05-l1-stage-separated-autodocs-noref.md
[bootstrap]: ../../../../l1/docs/decisions/0001-bootstrap-adaptation-strategy.md
[ci-release-plan]: 2026-04-02-l1-ci-release-line-noref.md
[delivery]: ../../../../l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md
[inventory]: ../../../../l1/docs/reference/productization-inventory.md
[l0-release-notes]: ../../../../l0/docs/releases/README.md
[l0-release-plan]: ../../../../l0/work/plans/tools/closed/2026-07-13-release-1-1-0-preparation-noref.md
[l0-release-workflow]: ../../../../.github/workflows/l0-release.yml
[l1-release-notes]: ../../../../l1/docs/releases/README.md
[monorepo]: ../../../../MONOREPO.md
[productization]: ../../../../l1/work/plans/tools/closed/2026-04-02-l1-bootstrap-productization-noref.md
[release-adr]: ../../../../docs/decisions/0023-l1-release-workflow-policy.md
[release-policy]: ../../../../scripts/l1_release.py
