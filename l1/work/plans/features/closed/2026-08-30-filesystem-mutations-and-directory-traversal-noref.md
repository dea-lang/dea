# Feature Plan

## Add filesystem mutations and directory traversal

- Date: 2026-10-24
- Last reviewed: 2026-10-24
- Status: Completed
- Title: Add path-level filesystem mutations and streaming directory traversal
- Kind: Feature
- Priority: High
- Stdlib Tier: 1
- Parent Initiative: `l1/work/initiatives/0005-filesystem-and-stream-io.md`
- Subsystem: Stdlib / runtime / filesystem
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/fs.l1`
  - `l1/compiler/shared/l1/stdlib/std/dir.l1`
  - `l1/compiler/shared/l1/stdlib/sys/fs.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/internal/dea_rt_fs.h`
  - `l1/compiler/shared/runtime/internal/dea_rt_fs_path.h`
  - `l1/compiler/shared/runtime/src/dea_rt_io.c`
  - `l1/compiler/shared/runtime/src/dea_rt_sys.c`
- Test modules:
  - `l1/compiler/tests/filesystem_runtime_test.l0`
  - `l1/compiler/tests/directory_runtime_test.l0`
  - `l1/compiler/tests/filesystem_native_test.py`
  - `l1/compiler/tests/filesystem_path_support_test.py`
  - `l1/compiler/tests/fixtures/filesystem_runtime/`
- Repro: From `l1/`, run
  `make test-compiler TESTS="filesystem_runtime_test directory_runtime_test filesystem_native_test"`.

## Scope and result

Implemented public `std.fs` metadata variants, native identity, absolute anchoring, existing-path canonicalization,
single and recursive mutations, explicit rename/replace, exclusive copying, and working-directory operations. `std.dir`
provides owned streaming cursors, copied entry names and cheap type hints, distinct entry/end/error results,
result-level cleanup, and materialized collections with composable comparator/default sorting. `sys.fs` transports
direct captured OS results.

The normative encoding, link, failure, lifetime, host-root, alias, and destination contracts are in
[l1/docs/reference/filesystem.md][filesystem]. Persistent metadata retains nullable `long` sizes and seconds; Windows
uses wide native APIs and FILETIME, and POSIX preserves filename bytes. Empty/NUL paths fail before filesystem calls.
Legacy whole-file helpers also share input validation and Windows wide paths without changing their signatures.

Recursive deletion never follows final/descendant links, closes owned traversal state on failure, preserves the first
error, and performs no rollback. It rejects roots and final dot/dot-dot components, and returns `ResourceExhausted`
beyond 256 child levels. Ancestors leading to the selected root must be trusted and stable; this is not a sandbox
against arbitrary concurrent rename or mount changes.

## Reference inventory and implementation method

| Reference                                                                                      | Applicable behavior and regression material                                                                                                        | Public adaptation                                                                                                                            |
| ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `compiler_support.c` path-kind, identity, absolute/canonical, mkdir/remove, and rename helpers | Follow/no-follow lookup, missing/error distinction, POSIX literal backslashes, native identities, existing-path resolution, destination conflicts. | Strict NUL/encoding boundary, direct `OsError`, wide Windows APIs, 128-bit Windows file IDs, and explicit public replacement policies.       |
| `preparation/platform.h::pc_list`                                                              | Host enumeration, dot omission, clean end versus error, iterator cleanup.                                                                          | Owned incremental `Dir`; no eager JSON or implicit sorting.                                                                                  |
| `compiler_filesystem_support_test.py` and `compiler_filesystem_test.l0`                        | Link/dangling/loop cases, aliases, absolute/canonical distinctions, Windows root spellings, cleanup, and literal-backslash parents.                | Generated L1 consumers plus direct runtime probes; private coarse errors, trusted-temp policy, and single-writer assumptions remain private. |

POSIX deletion uses descriptor-relative lookup and `O_NOFOLLOW`; Windows uses no-follow handles and holds visited
directories without delete sharing. Entry metadata is explicit; POSIX unknown type hints stay unknown. Native errors are
captured before cleanup. Existing runtime source/archive boundaries and symbol manifests include the new ABI.

Compiler consumers, private helper removal, bootstrap changes, L2 adoption, and the other stdlib plans are outside this
change. No compiler diagnostic codes were introduced or reassigned.

## Replacement and atomic capability decision

`rename` uses native entry renaming with replacement and host type rules. `replace` explicitly excludes real directories
and permits either an existing non-directory destination or an absent name. Neither copies across filesystems. POSIX
hard-link/same-entry alias moves are successful no-ops; Windows alias behavior remains native. `same_file` independently
answers followed identity and reports failed queries instead of false.

`copy_file` follows a regular source and exclusively creates a new destination. Existing names, including aliases, fail
without overwriting. Copying handles partial writes, captures read/write/close failures, and can leave a partial
destination for explicit recovery. No snapshot, metadata preservation, atomic publication, or durability is promised.

A separate atomic no-replace rename is deferred. Portable check-then-rename cannot enforce absence under competing
writers; Linux and Darwin exclusive variants need explicit capability/filesystem handling. The public API does not
inherit the compiler helper's single-writer assumption or claim atomic absence.

## ADR Impact

- Decision: Define path encoding, link policies, recursive mutation, and owned streaming iteration through public L1
  stdlib.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0046-filesystem-paths-and-owned-directory-traversal.md`
  - Rationale: These durable public contracts determine portable behavior independently of compiler-private helpers.
- Decision: Compare existing followed objects by native identity independently of spelling.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0047-followed-native-filesystem-identity.md`
  - Rationale: Native identity distinguishes aliases and preserves failed observations as structured errors.
- Decision: Separate call-time absolute anchoring from existing-path canonicalization.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0048-absolute-anchoring-and-existing-path-canonicalization.md`
  - Rationale: Existence, aliases, host roots, and process current-directory state require distinct contracts.
- Decision: Use native replacement policies, exclusive copying, and explicit atomic no-replace deferral.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/0049-filesystem-replacement-and-no-replace-capability.md`
  - Rationale: General callers cannot rely on the private compiler's single-writer assumption or implicit
    cross-filesystem copying.
- Decision: Preserve wide metadata while replacing the Windows narrow timestamp backend with native wide handle
  metadata.
  - Scope: L1
  - Disposition: Amend ADR
  - ADR: `l1/docs/decisions/0037-wide-filesystem-metadata.md`
  - Rationale: The existing width decision remains valid; its Windows range description must reflect FILETIME support.

## Initial implementation verification

Validation uses macOS Intel and `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`), selected explicitly through
`L0_CC`, `L1_CC`, and `L1_RUNTIME_CC`. The existing explicit L0 bootstrap compiler is reused without changing its
boundary.

- `make test-extended`: passed, including 89 normal compiler cases, 46 docgen tests, four examples, six Wine-runner
  tests, 181 tooling tests (one skipped), and 289 productization fixtures (14 skipped). This is fixture validation, not
  four-platform artifact acceptance.
- `python compiler/tests/filesystem_native_test.py`: passed against the final test additions, including native
  boundaries, permission-denied identity in both operand positions, injected generated directory failure traces, and
  checked/basic/unchecked public consumers.
- `python compiler/scripts/run_trace_tests.py filesystem_runtime_test directory_runtime_test`: both parent harness
  traces passed with zero leaked objects/strings. Their L0 harness sources and bootstrap dependencies remained
  unchanged; final L1 child traces and native boundary probes independently cover the final runtime.
- `python compiler/scripts/run_trace_tests.py --children filesystem_main directory_main`: both final generated L1 traces
  passed with zero leaked objects/strings and nonzero memory/ARC events.
- Native and injected-failure runtime probes under AddressSanitizer: passed, including traversal-depth cleanup. macOS
  leak detection was disabled because it is unavailable.
- Strict C99 runtime compilation with `/usr/bin/clang --no-default-config -Wall -Wextra -Werror`: passed.
- Existing compiler-private filesystem regression probes passed within the normal sweep; they remain reference evidence,
  not validation of the public Windows runtime.

Direct probes cover empty/NUL inputs across every boundary, saved errors, missing and POSIX permission-denied queries,
links and hard-link identity, existing destinations, replacement of a link without changing its target, no-follow tree
removal, partial creation/removal, traversal-depth exhaustion, cursor terminal states, partial writes, interruption,
zero progress, and close failures. Injected POSIX `EXDEV` confirms rename has no copy/delete fallback. Generated
programs cover all public APIs and checked/basic/unchecked runtime modes, exact sparse extents beyond 4 GiB, spelling
versus identity, Unicode/spaces, literal POSIX backslashes, and independent entry/collection string lifetimes. Child
ARC/memory analysis verifies generated ownership and cleanup. An injected traced runtime also verifies generated L1
materialization cleanup after partial iteration, native close failure, first-error precedence, and unknown type hints
without implicit metadata queries. Native AddressSanitizer probes check the C boundary and failure paths.

Native Windows, Linux, macOS ARM, and real cross-filesystem rename fixtures were unavailable locally. Windows
drive-relative/rooted/UNC/mixed-separator/Unicode and reparse cases are executable native-conditional tests, not claimed
Windows evidence. APFS rejected the non-UTF-8 filename fixture; byte-preserving `absolute` still passed, while
canonicalization of that uncreatable name remains unverified. macOS AddressSanitizer leak detection is unavailable;
ARC/memory analysis and explicit close/failure probes provide the recorded lifetime evidence. No push, tag, workflow
dispatch, artifact publication, or deployment was performed.

## Correctness and portability review

An independent review found Windows root parsing could admit device/UNC share roots, child joining could convert a bare
drive-relative path into a drive root, recursive creation normalized verbatim components, and fixtures relied on narrow
CRT arguments and POSIX prefix-creation behavior. These findings are repaired within the public filesystem runtime.
Generated directory ownership, sorting, partial-result cleanup, and close consumption required no semantic changes.

- The production spelling helpers now share one component-based root parser for recursive creation/removal. It
  recognizes both DOS device prefixes, case-insensitive UNC markers, separator runs, drive roots, and volume GUID roots;
  unsupported device namespaces and ambiguous ordinary Windows dot/space final components are rejected by recursive
  removal.
- Child joins preserve existing separators and bare drive-relative paths. POSIX root joining no longer introduces an
  extra leading slash; exactly two existing leading POSIX slashes retain their host-specific meaning. Recursive removal
  opens the parent with its original separator sequence intact.
- Recursive creation anchors ordinary Windows paths once and preserves canonical verbatim components without sending
  them through `GetFullPathNameW`. Native-conditional fixtures check a literal trailing-dot component.
- C and generated L1 probes decode ASCII hexadecimal path transport into UTF-8/native filename bytes. They no longer
  assume Windows narrow CRT arguments use UTF-8. Listing comparisons use bytes and cover trailing separators, extended
  paths, rooted paths, and bare drive-relative paths on native Windows. Windows normalized creation expectations are
  distinct from POSIX prefix side effects.
- The reference contract explicitly excludes concurrent in-place reparse-tag and mount changes from traversal safety.
  No-delete-sharing prevents directory-name replacement; it does not establish a complete sandbox.

Portable tests compile the actual production helper header under both Windows and POSIX spelling semantics. Independent
review also compiled the actual recursive-creation function with simulated host primitives: verbatim drive/UNC
components remain literal, ordinary drive-relative paths anchor once, and unsupported namespaces never reach directory
creation. These are simulated Windows checks; native Windows remains unavailable.

Post-review validation uses the same explicit Apple Clang and L0 bootstrap selection recorded above:

- `python compiler/scripts/run_tests.py filesystem_path_support_test filesystem_native_test filesystem_runtime_test directory_runtime_test io_runtime_test os_runtime_test runtime_symbol_manifest_test l1c_child_trace_runner_test`:
  all eight focused normal cases passed. After the final POSIX parent-spelling adjustment,
  `python compiler/scripts/run_tests.py filesystem_native_test io_runtime_test` passed both affected native/interface
  cases against rebuilt runtime archives.
- `python compiler/tests/filesystem_path_support_test.py`: both production spelling branches passed strict C99
  compilation and their simulated path regressions.
- `python compiler/scripts/run_trace_tests.py filesystem_runtime_test directory_runtime_test`: both parent harnesses
  passed with zero leaked objects/strings. This result remains valid after the final scalar POSIX adjustment because
  their L0 harness sources and bootstrap/compiler dependencies did not change; final native probes and L1 child traces
  cover the adjusted runtime.
- `python compiler/scripts/run_trace_tests.py --children filesystem_main directory_main`: both final generated L1 traces
  passed with zero leaked objects/strings and nonzero memory/ARC events.
- Final native and injected-failure probes passed AddressSanitizer with macOS leak detection disabled. Strict C99
  runtime compilation with `/usr/bin/clang --no-default-config -Wall -Wextra -Werror` also passed.

The initial aggregate evidence above records the original implementation. The post-review focused normal and trace
checks validate the repaired runtime and updated fixtures.

## Composable directory ownership and sorting

The public directory API uses `free_open_dir_result` and `free_entries_result`, hiding pointer-level close/free helpers.
Cleanup of failed opens performs no operation and returns `FsOk`; successful cursor cleanup always destroys the cursor,
returning any captured native close failure. Extracted cursor/collection pointers expire after cleanup. Owning entry
copies and saved names remain valid. Copies of a result alias one resource and require exactly one cleanup across all
aliases; cleanup is not idempotent and does not enforce a move.

`entries_sort(read_all(path), compare)` and `entries_sort_default(read_all(path))` replace `read_all_sorted`. Success
sorts the same collection and returns its pointer; failure passes through unchanged without comparator calls. The
default comparator calls `cmp_s` on names. Private iterative max-heapsort uses worst-case `O(n log n)` comparisons,
constant auxiliary entry storage, and no recursion. Equal-key order is unspecified. Comparators must define a consistent
ordering and must not mutate or free the collection.

This stdlib-only change preserves compiler/runtime interfaces and existing vector sorts. Reference examples establish
result cleanup before matching; error-aware cursor cleanup observes close failures while still releasing the wrapper.
Fallible work must precede resource creation or follow an established cleanup binding.

Validation uses macOS Intel with the explicit Apple Clang and L0 bootstrap selection recorded above:

- `python compiler/scripts/run_tests.py directory_runtime_test filesystem_native_test`: both passed, including
  checked/basic/unchecked consumers, private/removed export rejection, injected iteration/close failures, and the
  injected generated-L1 memory/ARC analysis.
- `python compiler/scripts/run_trace_tests.py directory_runtime_test`: passed with zero leaked objects/strings.
- `python compiler/scripts/run_trace_tests.py --children directory_main`: passed with zero leaked objects/strings and
  nonzero memory/ARC events. This covers result composition, alias identity/reassignment, retained entries, early-exit
  cleanup, default/custom/equal-key sorts, complete permutations, byte-sensitive names, and a comparison-count bound
  that rejects quadratic insertion sorting.
- `make test-docgen`: all 46 tests passed. Both reference examples type-check against current stdlib sources with
  explicit `--no-managed-stdlib --sys-root compiler/shared/l1/stdlib` inputs.
- Independent source and generated-C review found no actionable issue. Generated swaps retain before slot replacement,
  callback temporaries release on every branch, and result cleanup preserves close failures while destroying cursors.

Native Windows, Linux, and macOS ARM execution remain unavailable locally. The directory ownership and sorting
refinement requires no additional compiler/runtime source or ABI changes; existing vector sorting APIs remain unchanged.

[filesystem]: ../../../../docs/reference/filesystem.md
