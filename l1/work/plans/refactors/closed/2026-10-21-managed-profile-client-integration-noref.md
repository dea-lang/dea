# Refactor Plan

## Integrate managed preparation with the shared profile model

- Date: 2026-10-21
- Status: Completed
- Title: Make managed preparation a client of shared profile configuration and payload validation
- Kind: Refactor
- Parent Initiative: `l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md`
- Priority: Medium
- Subsystem: Native preparation, profile construction, payload validation and managed cache policy
- Modules:
  - `l1/compiler/src/preparation.l0`
  - `l1/compiler/src/preparation/frontend.l0`
  - `l1/compiler/src/preparation/consumer.l0`
  - `l1/compiler/support/preparation_support.c`
  - `l1/compiler/support/preparation/construction.h`
  - `l1/compiler/support/preparation/profile.h`
  - `l1/compiler/support/preparation/storage.h`
  - `l1/compiler/support/preparation/identity.h`
  - `l1/compiler/support/preparation/build.h`
- Test modules:
  - `l1/compiler/tests/preparation_construction_test.py`
  - `l1/compiler/tests/preparation_support_test.py`
  - `l1/compiler/tests/preparation_identity_test.py`
  - `l1/compiler/tests/preparation_ownership_test.py`
  - `l1/compiler/tests/preparation_clang_compatibility_test.py`
  - `l1/compiler/tests/preparation_profile_test.py`
  - `l1/compiler/tests/preparation_test.l0`
  - `l1/compiler/tests/fixtures/preparation/construction.l0`
  - `l1/compiler/tests/fixtures/preparation/inventory_mutation.c`
  - `l1/compiler/tests/l1c_preparation_test.py`
  - `l1/compiler/tests/l1c_managed_preparation_test.py`
  - `l1/compiler/tests/l1c_profile_test.py`
  - `l1/compiler/tests/l1c_profile_variants_test.py`
  - `l1/compiler/tests/l1c_installed_preparation_test.py`
- Related:
  - [l1/work/plans/refactors/closed/2026-09-30-profile-construction-boundary-noref.md][boundary-plan]
  - [l1/work/plans/features/closed/2026-09-30-explicit-profile-artifacts-noref.md][profile-plan]
  - [l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md][profile-review]
  - [l1/docs/reference/stdlib-preparation.md][preparation]
  - [l1/docs/reference/explicit-profiles.md][profiles]
- Repro: From `l1/`, use the explicit toolchain selections and validation commands below to verify shared construction,
  managed warm reuse, exact explicit selection and malformed-inventory refusal.

## Summary

Completed Phase C of [l1/work/initiatives/0010-explicit-profiles-and-composable-builds.md][initiative]. Managed,
command-private and explicit profile creation now share frozen configuration projection; managed and public inventory
validation share payload mechanics. Separate adapters retain managed freshness/storage authority and caller-owned
explicit artifact authority. CLI behavior, cache/public formats, provider precedence, diagnostics and failure ownership
are unchanged.

## ADR Impact

- Decision: Share profile construction inputs and payload validation while retaining separate public and managed
  authority.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0044-explicit-profile-artifact-authority.md`
  - Rationale: Record the delivered managed-client boundary without changing exact, read-only explicit selection or the
    public artifact format.
- Decision: Retain observed managed identity, conservative reuse admission and disposable memo policy.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0039-native-preparation-identity-and-reuse-boundary.md`
  - Rationale: Shared artifact code cannot make an explicit success evidence of managed freshness or weaken existing
    toolchain observation.
- Decision: Preserve manifest-certified warm semantic validation and full validation on every construction path.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0040-warm-preparation-semantic-validation-reuse.md`
  - Rationale: Moving validation must preserve the existing warm short circuit and miss, force, private-fallback and
    failure classifications.

## Findings and Implementation

`construction.h` owns `pc_construction_inputs`, used after managed resolution or explicit policy admission. It copies
selected compiler/archiver, ordered generated/runtime options, stable runtime-isolation marker, roots, modules,
interface digests and codegen settings. Both adapters continue through `pc_begin_construction` and `pr_construct`; the
constructor does not reread ambient defaults. Direct construction recreates its own legacy-Clang runtime-isolation
scratch from the frozen descriptor after the original resolution context is released.

`storage.h` owns `pc_payload_record`, `pc_payload_regular` and `pc_payload_digest`. Managed completion/lookup and public
publication/selection share record, expected-role, duplicate, containment, regular-file and selected size/digest checks.
The constructor uses the same containment/file-kind check when producing its inventory. Managed schema parsing, selected
semantic binding, metadata-assisted hashing, memo access and diagnostics remain with its adapter. Public strict fields,
copied headers, complete tree, alias refusal, role-specific hash scheduling and diagnostics remain with its adapter. The
public publication loop safely defers missing or malformed runtime record fields to inventory validation.

Managed schema-1 `manifest.json` still binds `D`, `N`, identity and exact selected semantic bytes; reliable artifact
metadata may satisfy warm checks. Managed headers remain toolchain inputs. Public schema-1 `profile.json` still records
the Dea contract, frozen configuration and copied headers without managed observations or original bundled inputs.
Managed entries do not become public profiles, and the explicit option whitelist does not constrain managed
response/configuration handling. An explicit success does not authorize managed reuse.

`pr_prepare` retains identity, lookup, complete miss validation, eligibility, lock/recheck, force and fallback. Managed
completion retains input freshness, completion-marker publication and recovery. The constructor borrows its destination;
callers retain publication, failure evidence and eventual cleanup. Command-private support outlives its final native
consumer. Explicit payloads remain read-only, with existing output/temp overlap refusal and no managed fallback.

The private `inventory_mutation.c` fixture injects malformed completed constructor inventories into both publication
adapters without a production test ABI. Missing/nonarray/duplicate/wrong-role/path/size/digest cases refuse completion
with managed `L1C-2153` or public `L1C-2183`; managed failure retains payload evidence without a marker or memo, while
public failure cleans registered staging contents and retains unexpected evidence. Regression assertions also preserve
managed record extensions and contained file aliases, strict public alias refusal, and public native versus compile-only
hash scheduling without memos.

## Verification Evidence

Validation ran on macOS Intel (`x86_64` Darwin) with `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`),
explicitly selected as `L0_CC`, `L1_CC` and `L1_RUNTIME_CC`. Bootstrap selection was the primary checkout's
`/Users/guglielmo/devel/googlielmo/DEA/l0/build/dea/bin/l0c-stage2`. The compiler was freshly built in this worktree
after offline synchronization of the shared virtual environment. Subsequent `make -o` commands reused that unchanged
build. Hash snapshots of the changed production/tests, Git status/diff review and frozen validation inputs together
established that production, test, build and dependency inputs remained unchanged through the successful checks. TinyCC
0.9.28rc was also exercised by identity and native runtime coverage.

| Check                                 | Result                                                                                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make -o venv -o build test-extended` | Passed: docgen 46; compiler normal 85; examples 4; Docker-Wine runner tests 6; tooling 181 with 1 skipped; productization fixtures 289 with 14 skipped. |
| Focused CI-only preparation cases     | Passed: `preparation_identity_test`, `preparation_ownership_test`, `l1c_installed_preparation_test` and `l1c_preparation_test`.                         |
| Focused preparation trace             | Passed: `preparation_test`, zero leaked object/string pointers across 1,181,370 events.                                                                 |
| Constructor trace                     | Passed with `L1_CONSTRUCTION_TRACE=1`, including success/failure cleanup.                                                                               |
| Direct native checks                  | Constructor, support, public profile and Clang compatibility checks passed; corresponding normal-suite replay also passed.                              |
| Independent reviews                   | Production correctness and path-portability reviews found no correctness issues.                                                                        |

The normal and focused suites cover cold/force/private preparation, manifest-certified warm reuse, identity and
ineligibility, locking/recovery, provider/lifecycle and retained-C behavior, exact profile selection, variants and
ownership. Warm checks retain zero bundled re-analysis and native preparation build work; hash scheduling and counters
are unchanged. No speedup is claimed or inferred from this refactor.

Portable Windows drive/UNC, mixed separators, spaces, case and distinct-path negatives passed through
`preparation_profile_test.check_windows_path_spellings`. These are simulated Windows path checks on the native macOS
host. POSIX symlink checks remain host-gated. There was no Phase C native Windows, macOS ARM or Linux/GCC execution; the
Docker daemon was unavailable. The Docker-Wine runner tests above validate tooling behavior and do not establish Linux
native execution. Native Windows filesystem/alias behavior remains unverified for this refactor. Prior Phase B
Windows/macOS ARM evidence belongs to
[l1/work/plans/bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md][profile-review] and is not Phase C
validation.

The focused identity run required the execution environment to permit the native `kern.osversion` observation. The same
supported compiler and policy passed once that observation was available; no production behavior was relaxed.

### Reproduction

From `l1/`, select an available supported bootstrap explicitly, then use the same native compiler across build and
checks. The commands below reproduce the validation selection; `-o` is appropriate only after the fresh build when its
inputs remain unchanged.

```sh
export L1_BOOTSTRAP_L0C=/absolute/path/to/l0c-stage2
export L0_CC=/usr/bin/clang L1_CC=/usr/bin/clang L1_RUNTIME_CC=/usr/bin/clang
export L1_TEST_JOBS=2
make build
make -o venv -o build test-extended
make -o venv -o build -o runtime test-compiler TESTS="preparation_identity_test preparation_ownership_test l1c_installed_preparation_test l1c_preparation_test"
make -o venv -o build -o runtime test-compiler-trace TESTS="preparation_test"
L1_CONSTRUCTION_TRACE=1 ../.venv/bin/python compiler/tests/preparation_construction_test.py
```

## Diagnostic Codes

The live [docs/specs/compiler/diagnostic-code-catalog.md][diagnostics] was rechecked. No code assignment or meaning
changed: managed `L1C-2150` through `L1C-2159` and public `L1C-2180` through `L1C-2185` retain their classifications and
precedence. Shared validation returns failure to the originating adapter; malformed publication tests assert managed
`L1C-2153` and public `L1C-2183` separately.

## Conclusions

Phase C is complete. ADR-0044 records the shared managed-client boundary; ADR-0039 and ADR-0040 continue to govern
managed observation/memo authority and manifest-certified warm semantic validation.
[l1/docs/reference/architecture.md][architecture] and [l1/docs/reference/stdlib-preparation.md][preparation] describe
the delivered internal boundary. The explicit-profile reference was audited and needed no external contract change.

Initiative 0010 remains active for Phase D semantic dependency discovery. This refactor adds no CLI mode, schema or
contract version, cache migration, locator/export mode, dependency scanner, native authenticity guarantee or cross-host
compatibility claim. Older entries remain untouched; compiler/source content changes legitimately select new `D` and `N`
identities. Production Make adoption, L0/L2 implementation, L2 profile adoption and release/publication work remain
separately scoped.

[architecture]: ../../../../docs/reference/architecture.md
[boundary-plan]: 2026-09-30-profile-construction-boundary-noref.md
[diagnostics]: ../../../../../docs/specs/compiler/diagnostic-code-catalog.md
[initiative]: ../../../initiatives/0010-explicit-profiles-and-composable-builds.md
[preparation]: ../../../../docs/reference/stdlib-preparation.md
[profile-plan]: ../../features/closed/2026-09-30-explicit-profile-artifacts-noref.md
[profile-review]: ../../bug-fixes/closed/2026-10-19-explicit-profile-review-gaps-noref.md
[profiles]: ../../../../docs/reference/explicit-profiles.md
