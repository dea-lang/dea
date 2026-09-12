# Refactor Plan

## Refine native preparation for correctness, economy and performance

- Date: 2026-09-13
- Status: Completed
- Title: Refine native preparation for correctness, economy and performance
- Kind: Refactor
- Severity: Medium
- Stage: 1
- Subsystem: Native preparation, semantic analysis reuse and compiler option observation
- Modules:
  - `l1/compiler/stage1_l0/src/preparation.l0`
  - `l1/compiler/stage1_l0/src/preparation/`
  - `l1/compiler/stage1_l0/src/build_driver.l0`
  - `l1/compiler/stage1_l0/src/driver/resolve.l0`
  - `l1/compiler/stage1_l0/support/preparation/`
  - `l1/compiler/stage1_l0/support/preparation_support.c`
- Test modules:
  - `l1/compiler/stage1_l0/tests/preparation_test.l0`
  - `l1/compiler/stage1_l0/tests/preparation_identity_test.py`
  - `l1/compiler/stage1_l0/tests/preparation_support_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_managed_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_preparation_test.py`
  - `l1/compiler/stage1_l0/tests/l1c_stage1_installed_preparation_test.py`
- Related:
  - [l1/work/plans/features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md][preparation-plan]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
- Repro: Run `make clean test-all` from `l1/`.

## Summary

Refine the completed lean native preparation implementation while preserving its public contract. The comparative review
found active shared toolchain machinery, small obsolete state, duplicated consumer and bundled-set analysis, and
repeated response/configuration parsing. Use bounded command-local ownership rather than another persistent cache.

The starting preparation core contains 5,030 physical source lines and 196,456 bytes. Source economy is a review
criterion; small owned records are acceptable when they remove repeated work and keep correctness explicit.

## ADR Impact

- Decision: Preserve bundled semantic authority and one local native cache while reusing command-local frontend results.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0038-bundled-semantic-inputs-and-local-native-preparation.md`
  - Rationale: The refactor preserves the existing ownership and preparation architecture.
- Decision: Preserve native reuse eligibility while sharing option-input parsing.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Command-local reuse removes repeated work without weakening observation or invalidation requirements.

## Implementation

1. Remove unread native identity/key memo copies, constant arguments, no-op calls, redundant validator parameters and
   error state. Preserve absent-manifest versus read-failure classification. Share repair diagnostics and compiler
   selection without changing precedence.
2. Retain the initial application `AnalysisResult`. After successful preparation, replace only managed native artifact
   associations and refresh subsequent managed search paths. Preserve semantic origins, source snapshots, explicit
   providers and final native sibling/provenance validation.
3. Validate the full bundled semantic graph once and return an owned dependency-ordered name vector. Release the graph
   and workspace before native compilation. The command owns the vector across lookup, locking, retries and fallback.
4. Cache parsed option files by lexical absolute path and syntax within native resolution. Expand direct and selected
   Clang configuration roots once, preserving occurrence order, cross-expansion paired options, relative include rules,
   `<CFGDIR>`, encodings and nesting limits. Keep original invocation words unchanged. Preserve selected file/directory
   dependencies and the existing fatal-error versus persistent-refusal policy. Release all records when native
   resolution finishes.

## Boundaries

Both original comparison branches remain unchanged. Work occurs in the current worktree on the requested follow-up
branch. No new CLI controls, diagnostic codes, cache schema, migration, persistent frontend cache, broader toolchain
eligibility policy, source-tree traversal optimization or remote operation is included. Existing compiler-owned input
hashing naturally changes the Dea identity when implementation sources change.

## Verification Criteria

- Restore applicable library replacement, nested Clang configuration, option-file encoding, SDK selection, implicit
  configuration creation and malformed structured memo regressions before restructuring the covered implementation.
- Require one parse per unique option file/syntax per command, preserving repeated argument occurrences. Check paired
  arguments, nesting limits, relative resolution, malformed inputs and invalidation on the next invocation.
- Require two application-entry analyses for a simple managed build/run, preserving intentional per-unit compilation,
  and one bundled umbrella analysis per preparation command, including fallback retries.
- Preserve zero managed generation/compilation on warm ordinary consumers and only requested managed C for warm keep-C.
- Retain complete semantic validation, explicit-provider precedence, invalid-input failure ordering, generated-C byte
  identity, runtime flag separation, corruption recovery, concurrency and private-support lifetime checks.
- Run focused preparation and provider/link tests, then `make clean test-all` from `l1/`, including relevant ownership
  traces. Require zero ARC/memory errors and leaks. Exercise available native compilers; record unavailable platforms.
- Use deterministic counts rather than timing thresholds. Run active/staged ADR checks, staged whitespace and root
  pre-commit before the local commit.

## Implementation Results

The command now retains the initial application analysis and binds only managed native sibling paths. Semantic graph
nodes, interfaces, name/signature tables, source snapshots and semantic origin paths retain their original ownership.
The complete bundled dependency order is copied into one owned name vector, after which the umbrella graph and workspace
are released. Native preparation borrows that order across cache decisions, locking, construction and private retries.

Native resolution owns one small option-input record. Parsed files are keyed by lexical absolute path and syntax; only
direct and selected configuration roots have flattened views. Repeated occurrences still contribute repeated arguments,
and recursive expansion always checks the existing nesting limit. Original compiler arguments and persistent
invalidation rules remain intact. New toolchain memos omit unused native identity copies; old extra fields remain valid.
Quoted empty operands and POSIX colon-containing relative filenames now retain their intended meaning.

The final production size comparison against the lean implementation is:

| Scope                                                               | Before lines | After lines | Line change | Byte change |
| ------------------------------------------------------------------- | -----------: | ----------: | ----------: | ----------: |
| All 15 changed production files                                     |        8,190 |       8,208 |         +18 |        -863 |
| Preparation core (three Dea modules and eight native support files) |        5,030 |       5,067 |         +37 |        +586 |

These are physical source lines, including comments and whitespace. The bounded owner records roughly offset the removed
plumbing in source size. The economy gain is removal of repeated analysis and file parsing, with stronger coverage of
the preserved contract; no large unused subsystem remains behind the smaller interface.

Deterministic regression assertions require two application-entry analyses instead of three, one complete bundled-set
validation per preparation command, and one parse per unique option file/syntax even when included repeatedly. Warm
ordinary consumers compile no managed modules, and warm keep-C analyzes and regenerates only the required bundled
closure.

## Regression Coverage

The restored identity regressions first passed against a frozen copy of the lean baseline's native service. They cover
an unchanged native driver whose private implementation library changes; nested Clang configuration comments,
continuations and `<CFGDIR>`; UTF-8, UTF-8 BOM and both UTF-16 byte orders; selected SDK metadata edits and removal;
creation of implicit configuration files; and parseable but structurally invalid memo observations.

Additional regressions pin command-local behavior: repeated includes and selected configuration roots preserve ordered
arguments; each file/syntax parses once; paired `-B` and `-target` arguments cross either side of an expansion boundary;
missing operands and malformed direct/nested configuration inputs fail; response includes use the invocation directory
while configuration includes use the including directory; and shallow prior parsing cannot bypass deeper nesting, cycles
or the option-file size limit. Subsequent commands observe edits, deletion and restoration. Legacy unused memo fields
still permit warm reuse, and newly written memos omit them.

The memo-shape fixture retains only its owned directory observations before establishing its warm baseline. It still
validates every observed component file. This prevents legitimate changes in unrelated live PATH/search directories from
changing discovery-probe counts during a record-acceptance assertion; separate tests continue to exercise real directory
and dependency invalidation.

The fixture also seals modified records with the native canonical JSON spelling, including control characters and
literal backslashes. Correctly sealed malformed structures therefore exercise schema validation rather than stopping at
the digest check. The structurally malformed subset also passes against the frozen lean baseline.

Linux validation uses real GCC through the repository Docker workflow. Debian Clang 14 lacks `--no-default-config`,
which the existing adapter uses, and the joined `--config=PATH` spelling used by the modern Clang fixtures. A comparison
with the lean baseline confirmed the same plain-resolution failure and joined-configuration refusal in both
implementations. Tests now assert that existing boundary explicitly, and run common response-file cases with GCC when
modern Clang configuration support is unavailable. Modern Clang configuration coverage remains exercised with Apple
Clang 17; no adapter policy changed.

MacPorts GCC 15.2.0 also passes a strict C99 native-service build, ordered nested response parsing and invalidation, and
actual private runtime compilation for default, traced, unchecked and basic checking variants. Its installed `ar` and
`as` shell wrappers prevent persistent reuse under the existing adapter policy, including when native Apple `ar` is
selected explicitly. Both refusal reasons and the resolved plain/nested identities match the lean baseline. Linux GCC
covers persistent reuse; the MacPorts checks retain this installation's private-support boundary.

Preparation integration fixtures now honor a configured GCC/Clang compiler instead of unconditionally choosing the first
Clang installation. Their archive requirement and separate TinyCC coverage remain explicit. The read-only-root fixture
checks actual write capability because privileged users can bypass mode bits. The installed late-write fixture uses a
nonempty directory in place of one declared interface output, so its post-begin storage failure and private retry are
exercised under ordinary and privileged users without relying on permission denial.

Frontend and integration assertions preserve semantic ownership during successful and partially failed native binding,
retain ordered names after validation cleanup, fail invalid application/provider inputs before preparation, and count
actual analysis starts. The installed read-only fixture forces a storage failure after native preparation begins and
proves its private retry reuses the bundled order. Warm ordinary consumers perform no individual bundled analyses or
native module compilations; warm keep-C regenerates exactly the required ten-module `std.io` closure. Existing explicit
provider precedence, complete-interface validation, generated-C identity, runtime-option separation, native corruption,
concurrency and private-support lifetime checks remain in place.

## Validation Record

The full `test-all` tier applies because the refactor changes owning frontend results and command-local allocation
lifetimes. Production sources and bootstrap build configurations remained unchanged after the clean builds. Successful
unchanged cases were retained; later fixture corrections, including their compiler selection, were validated with
focused reruns rather than repeating the aggregate suites.

From `l1/`, focused preparation checks covered `preparation_test`, `preparation_identity_test.py`,
`preparation_support_test.py`, `preparation_ownership_test.py` and all three preparation integration fixtures. The
provider/link selection also passed:

```bash
../.venv/bin/python compiler/stage1_l0/scripts/run_tests.py build_driver_test driver_test l1c_stage1_compile_only_test l1c_stage1_link_set_test l1c_stage1_generated_c_identity_test l1c_stage1_build_run_multi_cu_test l1c_stage1_installed_preparation_test l1c_stage1_bootstrap_interfaces_test
```

The macOS clean aggregate and remaining targets were run with:

```bash
caffeinate -i make clean test-all
caffeinate -i make test-env check-examples test-stage1-trace
```

The clean normal run passed 80 cases and exposed the new memo fixture's unrelated-directory assumption. A complete
identity run subsequently passed; the final canonical-seal and directory-isolation corrections passed their exact
focused checks. A later full identity attempt passed the corrected memo cases but encountered an existing compiler-probe
timeout under severe host contention. The unchanged SDK helper then passed all eight calls in isolation. Together with
the final preparation-fixture and support-fixture reruns, all 81 normal cases are covered. Environment stackability and
all four examples passed. All 46 default ARC/memory trace cases passed with zero errors, leaked objects or leaked
strings, including the changed preparation paths and the compiler-library trace. The intentionally slow math trace is
outside the default sweep; its ordinary runtime test passed.

Linux used the repository's Docker workflow with real GCC 12:

```bash
caffeinate -i make docker CMD=test-all DOCKER_CC=gcc L1_TEST_JOBS=4 L1_TRACE_TEST_JOBS=2
```

Its clean normal run passed 75 cases before reporting the four fixture issues described above and two unavailable
sanitizer checks. The corrected support case and three preparation integrations passed, covering all 79 normal cases
whose toolchain runtime is usable on this VM. A local snapshot retained the unchanged compiler builds for sequential
integration reruns and `make test-env check-examples test-stage1-trace`. The final test files were synchronized before
execution and their checksums verified. Environment stackability and all four examples passed. All 46 default ARC/memory
trace cases passed with zero errors, leaked objects or leaked strings, including the compiler-library trace.

The two Linux sanitizer oracles are unavailable on this VM. A trivial GCC 12 ASan program repeatedly emitted
`AddressSanitizer:DEADLYSIGNAL` before any Dea code. Clang 14 also failed intermittently during trivial-program startup
after its missing compiler runtime was installed in a separate disposable diagnostic container. No full-test retries
were used to select a lucky pass, and no kernel, ASLR or security settings were changed. Both sanitizer tests passed on
macOS. The diagnostic container was removed; the repository Docker configuration is unchanged. Windows coverage was
unavailable.

Additional checks passed: strict native C compilation with Apple Clang and MacPorts GCC 15, Clang static analysis with
zero diagnostics, native storage/integrity/coordination regressions, bounded read/hash probes, all four runtime variants
with Apple Clang and MacPorts GCC, and TinyCC's traced raw-object runtime path. Validation uses operation counts, not
wall-clock performance thresholds.

Finalization checks run from the monorepo root:

```bash
git diff --cached --check
python3 scripts/check_adr_impact.py --staged
uv run --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR)
```

Only documentation and Markdown formatting changed after the final affected test reruns. Production and test diff
identity was checked before staging; no relevant external modifications occurred. Both original branches and worktrees
remain unchanged. The temporary Linux validation containers and built snapshot image were removed after recording the
results. This cycle ends with one local commit and no remote writes.

[preparation]: ../../../../docs/reference/stdlib-preparation.md
[preparation-plan]: ../../features/closed/2026-09-07-stdlib-runtime-preparation-and-cache-noref.md
