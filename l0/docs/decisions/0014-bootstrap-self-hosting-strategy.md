# ADR-0014: Bootstrap and Self-Hosting Strategy

- Decision date: 2026-03-11
- Last edited: 2026-07-27
- Status: Accepted

## Context

Once the Stage 2 L0 compiler was implemented in L0, the question became: how do we validate that Stage 2 and Stage 1
produce identical output, and that Stage 2 can compile itself reliably?

## Decision

Triple-bootstrap is the definitive correctness gate for self-hosting:

1. Stage 1 (Python) compiles Stage 2 (L0) and produces compiler A.
2. Compiler A compiles Stage 2 and produces compiler B.
3. Compiler B compiles Stage 2 and produces compiler C.

The retained C produced for compilers B and C must be byte-for-byte identical on every supported host and toolchain.
Native compiler artifacts are also compared when the host toolchain can provide a meaningful stable identity, using the
platform policy below.

`make triple-test` runs this check. It is a required finalization gate for any Stage 2 change.

### Platform-specific native identity

Native executable bytes can contain linker or loader metadata that differs even when the retained C and executable code
are stable. The bootstrap fixed point therefore applies these explicit policies:

- Linux compares normalized copies after removing unstable ELF metadata; raw retained-C identity remains mandatory.
- Intel Darwin uses deterministic linker settings and compares the resulting native artifacts.
- Apple Silicon keeps the Mach-O UUID and ad hoc signature required by the loader. Comparison operates on non-executable
  copies: strip the intact image, remove the residual signature, then neutralize the validated `LC_UUID` payload.
- Windows and TinyCC always compare retained C. Native comparison is skipped when the toolchain cannot produce stable
  executable bytes rather than treating nondeterministic PE or TinyCC metadata as compiler drift.

Normalization is bounded to known metadata and operates only on comparison copies. The executable artifacts themselves
must not be stripped, patched, or otherwise mutated merely to make the bootstrap comparison pass.

### Provenance boundary

Raw compiler B and compiler C builds use the checked-in Stage 2 source and omit build provenance so provenance cannot
perturb the fixed point. Repo-local, installed, snapshot, and release artifacts may embed provenance through a generated
`build_info.l0` source overlay supplied by artifact-producing tooling.

Provenance must not be injected into raw bootstrap generations, passed through wrapper-only state, or added by post-link
binary patching.

## Rationale

- A single bootstrap pass (Stage 1 to Stage 2 binary) only proves Stage 2 can be compiled. It does not prove that Stage
  2's output is correct.
- Two passes prove that Stage 2 can build itself, but do not establish a self-hosted fixed point.
- Three passes prove self-consistency: if generations 2 and 3 produce identical retained C, later generations have
  reached a stable compiler representation.
- Combining triple-bootstrap with Stage 1 and Stage 2 whole-compiler `--gen` diffs gives a full semantic-equivalence
  check.
- Separating retained-C identity from known native metadata prevents false failures without hiding compiler-output
  drift.
- Keeping provenance outside raw bootstrap generations preserves reproducibility while allowing shipped artifacts to
  identify their source and build environment.

## Consequences

- CI must run `make triple-test` on every Stage 2 change.
- Retained-C differences are always bootstrap failures.
- Each native toolchain follows an explicit compare, normalization, or waiver policy; a new host cannot silently relax
  native identity.
- Comparison normalization must reject malformed or unsupported artifact layouts rather than rewriting arbitrary bytes.
- Bootstrap compiler binaries retain the fallback `--version` identity, while artifact-producing builds can report
  embedded provenance.
- The triple-bootstrap check must pass before any release is cut.

## Related Plans

- [l0/work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md](../../work/plans/features/closed/2026-03-11-triple-bootstrap-self-hosting-noref.md):
  established the strict retained-C and native triple-bootstrap test
- [l0/work/plans/bug-fixes/closed/2026-03-11-stage2-triple-bootstrap-self-hosting-bug-fixes-noref.md](../../work/plans/bug-fixes/closed/2026-03-11-stage2-triple-bootstrap-self-hosting-bug-fixes-noref.md):
  fixed self-hosting bugs exposed by triple-bootstrap
- [l0/work/plans/features/closed/2026-03-12-stage2-build-info-version-output-noref.md](../../work/plans/features/closed/2026-03-12-stage2-build-info-version-output-noref.md):
  placed shipped-artifact provenance in a generated source overlay outside raw bootstrap generations
- [l0/work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md](../../work/plans/bug-fixes/closed/2026-03-13-linux-c99-compatibility-noref.md):
  retained strict C identity while normalizing unstable Linux native metadata
- [l0/work/plans/bug-fixes/closed/2026-03-13-windows-stage2-shell-test-regressions-noref.md](../../work/plans/bug-fixes/closed/2026-03-13-windows-stage2-shell-test-regressions-noref.md):
  established the Windows retained-C-only fallback when native PE output is unstable
- [l0/work/plans/bug-fixes/closed/2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref.md](../../work/plans/bug-fixes/closed/2026-03-17-darwin-arm64-triple-bootstrap-native-mismatch-noref.md):
  first isolated the Darwin arm64 native metadata mismatch
- [work/plans/bug-fixes/closed/2026-07-11-shared-ci-platform-portability-regressions-noref.md](../../../work/plans/bug-fixes/closed/2026-07-11-shared-ci-platform-portability-regressions-noref.md):
  preserved loader-required UUID and signature commands on Apple Silicon
- [l0/work/plans/bug-fixes/closed/2026-07-11-darwin-arm64-triple-bootstrap-uuid-normalization-noref.md](../../work/plans/bug-fixes/closed/2026-07-11-darwin-arm64-triple-bootstrap-uuid-normalization-noref.md):
  defined bounded comparison-copy normalization for Mach-O UUID metadata
- [work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md](../../../work/plans/tools/closed/2026-07-27-shared-historical-adr-backlog-publication-noref.md):
  promoted the audited bootstrap identity and provenance policy into this ADR

## Current Docs

- [l0/docs/specs/compiler/stage1-contract.md](../specs/compiler/stage1-contract.md): Stage 1 contract and parity
  guarantees
- [l0/docs/specs/compiler/stage2-contract.md](../specs/compiler/stage2-contract.md): Stage 2 provenance and
  raw-bootstrap fallback contract
- [l0/docs/reference/architecture.md](../reference/architecture.md): Stage 2 pipeline, bootstrap, and distribution
  architecture
- [docs/decisions/0001-two-stage-architecture.md](../../../docs/decisions/0001-two-stage-architecture.md): the broader
  two-stage architecture decision
