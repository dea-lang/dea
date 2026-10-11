# Tool Plan

## Canonical L1 install and distribution workflow

- Date: 2026-10-11
- Started: 2026-04-02
- Last reviewed: 2026-10-11
- Status: Completed
- Closed: 2026-10-11
- Title: Canonical L1 install and distribution workflow
- Kind: Tooling
- Severity: Medium
- Stage: Canonical
- Subsystem: Build workflow / install layout / distribution packaging / bootstrap docs

## Outcome

Canonical L1 installation, distribution packaging, offline documentation, and native artifact acceptance are complete.
Fresh builds and checkout-free verification passed on Linux x86_64, macOS Intel, macOS ARM, and Windows UCRT64 on
2026-10-11. The delivery contract is recorded in
[l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md][delivery]; the explicit upstream compiler contract is
recorded in [l1/docs/decisions/0001-bootstrap-adaptation-strategy.md][bootstrap]. No implementation or acceptance work
remains in this plan.

## Historical context

This plan began while L1 had an L0-implemented Stage 1 compiler and a self-hosted Stage 2 compiler. Its original scope
was to install and distribute Stage 2 only, using Stage 1 and the upstream L0 compiler for construction. The four
implementation phases below were complete, including documentation handoff and four-platform artifact acceptance, by
2026-10-09; formal closure was still pending.

The subsequent L1/L2 split moved the former Stage 2 compiler to L2 and retained the L0-implemented compiler as the sole
canonical L1 compiler. The completed productization work was then adapted back to that compiler under
[work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md][split]. Private construction,
semantic-input verification, provenance, and documentation became canonical and stage-free, using schema-2 records and
fresh prefixes. Installation ownership, recovery, relocation, and exact-artifact delivery guarantees were retained.
Fresh canonical acceptance completed on 2026-10-11, allowing this plan to close.

[l1/docs/decisions/0042-self-hosted-toolchain-delivery.md][historical-delivery] preserves the original Stage 2 delivery
decision; ADR-0043 records its canonical successor. Historical Stage 2 artifacts and acceptance are not reused as
canonical L1 evidence.

## Completed implementation phases

### Phase 1: Prefix and payload helpers

Established the prefix layout, ownership inventory, path validation, recoverable reinstall primitives, and standalone
packaged documentation. Added L1-specific launcher and activation behavior while preserving shared L0 defaults. Private
build-info overlays supplied package provenance and the installed-mode marker; native startup validated installation
state before exposing installed compiler commands.

### Phase 2: Install workflows

Added `make install` and inventory-only `make list-installed`. The original construction chain produced a separate
installed Stage 2 executable with matching semantic interfaces and runtime/stdlib rebuild inputs. Complete inventories
were published only after payload installation. Relocation, read-only prefixes, environment selection, and interrupted
installation recovery formed the installed-operation contract.

### Phase 3: Distribution packaging

Added `make dist`, archive naming and version metadata, curated payload exclusions, atomic `DIST_RESULT` handoff, and
`make smoke-dist` for the exact produced archive. Integrated mandatory matching Stage 2 offline HTML/full PDF and a
transportable acceptance harness with separate native build and fresh-host verification phases. Delivery covered Linux
x86_64, macOS Intel, macOS ARM, and Windows UCRT64; hosted release workflows and publication remained separate work.

### Phase 4: Documentation and contributor guidance

Documented bootstrap selection, installed operation, native preparation/cache behavior, diagnostics, package identity,
and distribution/documentation interfaces. Integrated focused productization coverage into normal validation and kept
actual artifact acceptance as a separate gate. Updated roadmap and status documentation, recorded the delivery and
bootstrap decisions, and handed the implemented commands and artifact contract to the release-workflow plan. The later
canonical split updated this completed scope before formal closure.

## Delivered scope

- Prefix installation and deterministic inventory-only listing use a curated payload and private installed-mode compiler
  construction. Explicit `L1_BOOTSTRAP_L0C` selection is authoritative; ambient `PATH` never supplies the bootstrap.
  Construction preserves repository development artifacts and verifies captured canonical semantic inputs.
- Ownership inventories validate paths, digests, modes, and installation state. Reinstalls preserve unrelated files,
  reject unowned collisions and unsafe aliases, and retain enough ownership information to recover interrupted writes.
  Installation is recoverable rather than atomic; concurrent upgrades and uninstall tooling are outside scope.
- Installed startup checks the physical executable prefix before CLI parsing, including help and version. Invalid or
  incomplete installation state reports `L1C-9515`; preparation failures retain their existing diagnostics. Installed
  operation does not require the source checkout, upstream compiler, Python, or Make.
- Launchers and activation scripts select installed roots, clear inherited development build roots, preserve explicit
  runtime/system/cache selectors, and support environment switching without duplicate prefix entries. Native Windows
  launchers preserve the calling environment and compiler exit status.
- Immutable payloads contain verified semantic interfaces, public headers, runtime/stdlib rebuild inputs, symbol
  manifests, notices, package identity, standalone instructions, and a smoke program. Native support is prepared in a
  separate writable cache; supported host compiler/linker tools remain necessary for native output.
- Distributions contain one `dea-l1/` root, complete inventory, matching provenance, and verified canonical offline HTML
  and full indexed PDF under `share/doc/dea/l1/autodocs/`. Direct installation may omit documentation. Build scratch,
  implementation/test trees, bootstrap compilers, and writable caches are excluded.
- Stage-free schema-2 install, documentation, result, and acceptance records require fresh prefixes and matching source,
  version, and documentation identity. Package versions default to `dev`; explicit versions do not imply stable language
  maturity or activate a hosted release line.
- Archive publication produces an atomic result record for the exact successful archive. Failed builds invalidate stale
  results. Safe extraction and exact-artifact smoke verification reject unsafe members and tampered or incomplete
  payloads before compiler execution.

The current inventory and preparation contracts are maintained in
[l1/docs/reference/productization-inventory.md][inventory] and [l1/docs/reference/stdlib-preparation.md][preparation].
Operational guidance lives in [l1/AGENTS.md][guidance] and [l1/docs/user/toolchain.md][toolchain].

## Workflow handoff

The implemented interface, invoked from `l1/`, is:

```sh
make install PREFIX=/absolute/fresh-prefix
make list-installed PREFIX=/absolute/fresh-prefix
make docs-artifacts DEA_DIST_VERSION=dev
make dist DEA_DIST_VERSION=dev DOCS_ARTIFACT=/absolute/dea_l1_autodocs.tar.gz DIST_RESULT=/absolute/result.json
make smoke-dist ARCHIVE=/absolute/archive.tar.gz
make test-productization-acceptance DOCS_ARTIFACT=/absolute/dea_l1_autodocs.tar.gz ACCEPTANCE_DIR=/absolute/new-evidence
```

Distribution consumes a previously verified documentation bundle and never invokes Doxygen or TeX implicitly.
`DIST_RESULT` identifies the successful archive; workflow consumers must check command success and read that record
rather than globbing archives or parsing log prose. The acceptance harness transports the exact archive, result, and
verification inputs between native build and fresh verification jobs.

[l1/docs/roadmap.md][roadmap], [l1/docs/project-status.md][status], and [MONOREPO.md][monorepo] record the delivered
capability. [work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md][release-workflows] owns hosted
snapshot/release workflow implementation, authoritative namespace verification, release notes, and publication
acceptance. Its canonical artifact prerequisites are satisfied. Tags, workflow dispatches, and publication still require
separate authorization; closing this plan does not activate the L1 release line.

## Verification evidence

The completed implementation established focused inventory, provenance, launcher, payload, installed-state, archive,
atomic-result, and acceptance-harness regressions, plus installed compiler and environment integration coverage.
Recovery cases cover interrupted metadata/payload writes, malformed state, unsafe paths, unowned collisions, and
retries. Fixture validation is distinct from actual artifact acceptance.

Fresh canonical verification recorded by
[work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md][split] on 2026-10-11 includes:

- Strict canonical HTML and the full indexed PDF passed with matching stage-free documentation provenance.
- L1 Productization Acceptance built `dev` archives on all four native platforms and verified them on fresh runners
  without checkout or bootstrap artifacts. Each verifier consumed the exact transported archive/result/harness evidence.
- Artifact checks passed relocation, immutable payload integrity, semantic-only operation without native tools,
  compilation, standalone linking, build/run, cold and warm native preparation, and runtime configuration coverage.
- Unified CI passed L1 `test-ci` on all four platforms, including normal, CI-only, trace, child-fixture, tooling, and
  product fixtures. These compiler gates supplement rather than replace artifact acceptance.

## ADR Impact

- Decision: Ship canonical L1 through one relocatable install-prefix and distribution contract.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0043-canonical-compiler-toolchain-delivery.md`
  - Rationale: ADR-0043 retargets the established integrity, ownership, provenance, offline documentation, and
    exact-artifact delivery contract to the sole L0-implemented compiler. Superseded ADR-0042 retains the former Stage 2
    decision history.
- Decision: Choose the L1 bootstrap compiler from repo-local L0 Stage 2 or `L1_BOOTSTRAP_L0C`, never ambient `PATH`.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0001-bootstrap-adaptation-strategy.md`
  - Rationale: The amended ADR-0001 records the explicit upstream compiler used for canonical L1 construction and
    installed operation independent of that upstream toolchain. Both ADRs link to this closed plan.

## References

[bootstrap]: ../../../../docs/decisions/0001-bootstrap-adaptation-strategy.md
[delivery]: ../../../../docs/decisions/0043-canonical-compiler-toolchain-delivery.md
[guidance]: ../../../../AGENTS.md
[historical-delivery]: ../../../../docs/decisions/0042-self-hosted-toolchain-delivery.md
[inventory]: ../../../../docs/reference/productization-inventory.md
[monorepo]: ../../../../../MONOREPO.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[release-workflows]: ../../../../../work/plans/tools/2026-05-12-l1-gha-release-snapshot-workflows-noref.md
[roadmap]: ../../../../docs/roadmap.md
[split]: ../../../../../work/plans/refactors/closed/2026-10-10-shared-l1-l2-canonical-compiler-split-noref.md
[status]: ../../../../docs/project-status.md
[toolchain]: ../../../../docs/user/toolchain.md
