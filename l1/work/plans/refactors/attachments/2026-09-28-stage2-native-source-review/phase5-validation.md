# Phase 5 consolidated validation and closure

- Validation date: 2026-10-04
- Status: Complete
- Parent ledger: [l1/work/plans/refactors/attachments/2026-09-28-stage2-native-source-review/review.md][ledger]

## Scope and inventory

The consolidated source tree contains 119 production modules and 1,749 function bodies. Every current module has exactly
one completed disposition in the ledger, and every current function name appears in the review records. The 120 original
inventory rows retain the removed `util/path.l1` module; there are no missing, duplicate, or Pending entries. Phases 1
through 4 are complete.

Phase 5 changes documentation and lifecycle records only. It preserves the reviewed production sources, regression
tests, Stage 1 oracle, diagnostic/interface contracts, and strict bootstrap comparison policy. Input digests taken
before validation are retained in `/tmp/dea-phase5-review/validation-inputs.json`; the inventory audit is recorded in
`/tmp/dea-phase5-review/inventory.json`.

## Toolchain and procedure

Linux x86_64 with `/usr/bin/gcc`, Debian GCC 14.2.0-19, selected for `L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. The
repo-local `l0/build/dea/bin/l0c-stage2` supplies the upstream bootstrap compiler. Compiler/runtime flags retain their
repository defaults, including basic compiler checks and a quarantine count of 256. The shared Python environment and
four normal/trace workers come from the workspace activation script. No test selectors are supplied, so the exhaustive
gate includes the CI-only normal cases, both default trace suites, both stages' child fixtures, and strict triple
bootstrap.

From `l1/`:

```sh
source /workspace/.dea-tools/env.sh
KEEP_ARTIFACTS=1 L1_TRACE_ARTIFACT_DIR=/tmp/dea-phase5-review/traces \
  make test-ci > /tmp/dea-phase5-review/test-ci-unrestricted.log 2>&1
```

Trace artifacts use `/tmp/dea-phase5-review/traces`, a symlink to `/workspace/.dea-tools/phase5-traces` on the larger
workspace filesystem. Completed successful trace logs larger than 1 MiB are gzip-compressed only after their analyzer
result is reported. Decompressed SHA-256 verification precedes removal of each uncompressed copy;
`/tmp/dea-phase5-review/trace-compression.jsonl` retains sizes and digests. Active logs and analyzer reports remain
untouched.

Compiler validation runs outside the filesystem sandbox. The initial sandbox attempt stopped while building Stage 1: the
sandbox exposes `/` as owned by UID 65534, which fails the existing temporary-parent hierarchy check. Outside the
sandbox, `/` is owned by root and `/tmp` is root-owned with mode 1777. No compiler trust checks, filesystem ownership,
or permissions were changed. The initial failure is retained in `/tmp/dea-phase5-review/test-ci.log`.

## Consolidated results

| Check                                                  | Result                                                     |
| ------------------------------------------------------ | ---------------------------------------------------------- |
| Stage 1 complete normal suite, including CI-only cases | 87 passed, zero failed                                     |
| Stage 2 complete normal suite, including CI-only cases | 71 passed, zero failed                                     |
| Explicit Stage 1/Stage 2 parity                        | Passed                                                     |
| Stage 2 examples                                       | Four passed without warnings or errors                     |
| Docker/Wine runner regressions                         | Six passed                                                 |
| Stage 2/bootstrap tooling                              | 18 passed                                                  |
| Environment/bootstrap integration                      | Passed                                                     |
| Stage 1 default trace suite                            | 47 passed, zero failed; zero leaked object/string pointers |
| Stage 2 default trace suite                            | 47 passed, zero failed; zero leaked object/string pointers |
| Stage 1 child trace fixtures                           | Two passed; zero leaked object/string pointers             |
| Stage 2 child trace fixtures                           | Two passed; zero leaked object/string pointers             |

Strict bootstrap built A through Stage 1, B through A, and C through B. B and C preserve A's 137 retained C
translation-unit paths, and B/C C bytes match. The normalized native binaries are byte-identical at 4,381,592 bytes with
the existing GCC controls `-frandom-seed=l1c-stage2 -Wl,--build-id=none`. Retained evidence is under
`l1/build/dea/triple-bootstrap-5ojuie4j/`, including `native-controls.json`, `inputs.json`, generation inventories,
`normalized-native.json`, and per-step logs. The final self-built suite passed all 65 normal tests, followed by all four
examples without warnings or errors and the hello smoke run. The complete `make test-ci` invocation exited successfully.

The input-digest recheck confirms unchanged production sources, test fixtures, and tooling throughout validation;
`compiler/stage2_l1/README.md` is the only changed file among the recorded inputs. All 46 large trace logs were
compressed and verified: 8,416,730,632 original bytes are retained in 523,015,096 gzip bytes.

## Review outcomes and retained constraints

The completed review adopts typed constants, named constructors, native variadic matching, guarded bitwise operations,
typed cleanup flow, native interface comparisons, byte arithmetic, and scalar process-status storage. It removes an
unused path module and four unused CLI helpers. Earlier phase attachments retain the focused regressions, parity, trace,
bootstrap, and repeated performance/allocation evidence for those changes. Phase 5 introduces no executable changes
requiring new performance measurements.

Typed growable owning collections, explicit recursive cleanup, owned strings, numeric range helpers, ordered CLI
validation, and native filesystem/process/preparation/fingerprint bridges retain concrete ownership, diagnostic,
portability, or ABI purposes. The Phase 4 audit records those purposes. Generic owning collections, broader slice
lifetimes, direct address-taking, and dynamic enum comparisons remain observations for possible later language work. No
separate semantic defect or external follow-up was identified, and no unfinished in-scope work is deferred.

The existing ADR disposition remains `ADR not warranted`: these implementation choices preserve the accepted compiler
architecture and external contracts.

## Documentation and closure

The Stage 2 README, project status, architecture, roadmap, and parent ledger now describe the completed review and its
retained constraints. The plan is archived under `l1/work/plans/refactors/closed/`, its roadmap entry is completed, and
all incoming and relocated reference links are repaired. The stale project-status claim that self-hosting was not yet
available is corrected.

Closure checks passed: all 146 local link targets in the ten related documents resolve; active and staged ADR Impact
validation, staged whitespace, copyright headers, and Markdown formatting pass. The repository-root pre-commit command
uses the root configuration and all changed files. The final change contains only seven Markdown documents; validated
compiler sources, tests, and tooling remain unchanged.

[ledger]: review.md
