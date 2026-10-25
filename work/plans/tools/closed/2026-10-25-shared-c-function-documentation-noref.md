# Tool Plan

## Canonical C function contracts and complete reference inputs

- Date: 2026-10-25
- Status: Completed
- Title: Canonical C function contracts and complete reference inputs
- Kind: Tooling
- Priority: Medium
- Scope: Shared
- Targets:
  - L0 runtime, support, fixtures, and both reference stages
  - L1 runtime, support, fixtures, and canonical reference
  - L2 runtime, support, fixtures, and reference inventory
  - Shared tooling and editor bindings
- Origin: Repository-wide C documentation audit
- Porting rule: Use identical documentation rules while preserving each implementation's contracts and source inventory.
- Target status:
  - L0 runtime, support, fixtures, and both reference stages: Implemented
  - L1 runtime, support, fixtures, and canonical reference: Implemented
  - L2 runtime, support, fixtures, and reference inventory: Implemented
  - Shared tooling and editor bindings: Implemented
- Subsystem: C contracts, source inventories, Doxygen extraction, and undocumented-function reports
- Modules:
  - `scripts/check_c_docs.py`
  - `scripts/c_declarators.py`
  - `scripts/docgen_c_contracts.py`
  - `scripts/docgen_doxygen.py`
  - `scripts/docgen_function_inventory.py`
  - `l0/compiler/docgen/`
  - `l1/compiler/docgen/`
  - `l2/scripts/gen_c_docs.py`
  - `l0/compiler/shared/runtime/`
  - `l1/compiler/shared/runtime/`
  - `l2/compiler/shared/runtime/`
- Test modules:
  - `scripts/tests/test_c_docs.py`
  - `scripts/tests/test_docgen_function_inventory.py`
  - `scripts/tests/test_docgen_inputs.py`
  - `l0/compiler/stage1_py/tests/cli/`
  - `l1/tests/`
  - `l2/tests/test_docgen_native.py`

## Summary

Put the complete multiline Doxygen contract immediately before each C function definition. Use Javadoc autobrief without
explicit brief commands. Header prototypes use an ordinary one-line comment reproducing the canonical first sentence
exactly. Header-defined functions retain full contracts. Add blank source lines before block comments, preserve
nonfunction documentation in its natural location, and exclude only identified vendored and generated files from bulk
changes. Consolidate existing details and document missing behavior without changing executable code.

## ADR Impact

- Decision: Isolate Doxygen extraction by language binding and native implementation role before combining references.
  - Scope: Repository/tooling
  - Disposition: New ADR
  - ADR: `docs/decisions/0024-c-contracts-and-isolated-reference-extraction.md`
  - Rationale: Doxygen associates unrelated declarations across language bindings and alternative native providers. The
    extraction boundary must preserve independent contracts while retaining source locations and prototype/body
    identity.

## Approach

1. Inventory all tracked C/header files, with explicit vendored/generated exclusions and per-target audit counts.
2. Consolidate contracts at definitions; retain header-only documentation and exact prototype briefs.
3. Validate multiline contracts, comment spacing, and declaration/definition brief matching without name-only merging.
4. Include production implementation files and private implementation headers in each applicable reference pipeline.
   Isolate language bindings and alternative native providers during extraction so unrelated contracts cannot merge.
5. Add real-Doxygen extraction and source-location regressions, including unrelated same-named functions.
6. Regenerate complete references and audit genuine undocumented findings and source-inventory limitations.

## Verification criteria

- Comment-only C changes preserve executable token streams, including preprocessor directives and string literals.
- Maintained source inventory passes the C documentation checker; exclusions identify their provenance.
- Real Doxygen preserves parameters, returns, ownership, failures, and declaration/body source locations.
- Matching C declarations share documentation; distinct signatures, static functions, and language bindings stay
  distinct.
- Affected documentation suites, full reference generation, whitespace, ADR Impact, and pre-commit checks pass.
- Implementation and validation complete locally. Remote operations are outside this plan.

## Source audit

| Area            | Maintained files | Source definitions | Header definitions | Header prototypes |
| --------------- | ---------------: | -----------------: | -----------------: | ----------------: |
| L0              |                7 |                 37 |                193 |                88 |
| L1              |               55 |                448 |                368 |               214 |
| L2              |               33 |                337 |                273 |               186 |
| Editor bindings |                3 |                  2 |                  0 |                 2 |
| Total           |               98 |                824 |                834 |               490 |

The 171 tracked C/header files contain 73 explicit exclusions: 61 vendored files under `tools/`, eight generated backend
goldens, three upstream Tree-sitter support headers, and its generated parser. Owned fixtures, examples, benchmarks, and
historical C probes are included in the maintained audit. Every physical function definition has an adjacent full
contract; conditional alternatives remain separate physical definitions. All Doxygen blocks are multiline. Header-only
libraries remain in headers. Javadoc autobrief supplies each first-sentence brief. The 230 explicit brief commands in
six maintained L0 files were removed without changing prose, line counts, or executable tokens; Dea sources already use
implicit briefs. The source checker rejects explicit brief commands.

The final C token audit includes operators, literals, preprocessor directives, macro adjacency, and line splicing. Every
tracked C/header file preserves its executable token stream; excluded files also preserve their complete bytes. Targeted
semantic review corrected stale allocation, string, cleanup, profile, JSON, native-path, and observation ownership
descriptions. In particular, Windows trusted temporary parents resolve an opened handle's final path rather than using
lexical normalization.

## Reference inventory and report audit

- L0 Stage 1 includes its Python compiler, shared Dea stdlib, and full runtime/header-only implementations. Stage 2
  includes its Dea compiler, shared stdlib/runtime, native filesystem support, and selected trace support tooling.
- L1 includes its canonical compiler, stdlib bindings, runtime units, private filesystem/preparation headers, and
  alternative fingerprint bridge. `preparation/profile.h` is now selected.
- L2 has a bootstrap-independent complete native C reference. It has no compiler-language or stdlib-binding autodocs
  pipeline; native results do not claim coverage of those sources.
- Production references intentionally omit tests, examples, benchmarks, generated files, and vendored code. Their
  selected preprocessing profiles do not enumerate all mutually exclusive platform, sanitizer, checking, or trace
  alternatives; the whole-source audit covers those physical definitions separately.
- The L1 binding audit identifies 36 compiler helpers and 37 Dea extern bindings that require contracts on their own
  declarations; documented native implementations cannot cover distinct Dea bindings. All 73 contracts are completed and
  the canonical report has zero findings, as recorded in
  [l1/work/plans/tools/closed/2026-10-25-compiler-function-contracts-noref.md](../../../../l1/work/plans/tools/closed/2026-10-25-compiler-function-contracts-noref.md).
- Independent XML audits verify native declaration/body locations and retained contracts. Real rendering exposed a
  parameter-name alias case: Doxygen records declaration `s` and definition `a`, but m.css drops an unmatched copied
  parameter label. Generated XML labels now use that explicit per-member relationship, preserving signatures, locations,
  descriptions, and C source tokens. Already-correct LaTeX captions and tables retain definition names.

## Verification

The change is documentation and documentation-tooling work. C executable tokens, compiler behavior, runtime flags, and
trace execution are unchanged; compiler and trace aggregates are outside this validation scope.

- `python3 scripts/check_c_docs.py`: 98 maintained files, 73 explicit exclusions, zero errors. Independent lexical
  comparison confirms identical executable tokens for all 171 tracked C/header files and byte-identical exclusions.
- L0 `make test-docgen`: 227 tests passed; the remaining namespace-alias fixture was corrected to use its canonical
  rendered anchor and its focused regression passed. L1 `make test-docgen`: 167 passed. L2 `make test-docgen`: 56
  passed; its unchanged native inputs retain that result, and both newly added L0/L1 rendering cases pass in those
  levels.
- L0 `make docs-artifacts DOC_STAGE=all DEA_DIST_VERSION=dev`: strict complete references and verified bundles for Stage
  1 (839 PDF pages) and Stage 2 (993 PDF pages). L1 `make docs-artifacts DEA_DIST_VERSION=dev`: strict complete
  reference and verified bundle (1,839 PDF pages).
- L2 `python scripts/gen_c_docs.py --strict --pdf` (the `make docs-pdf` target): strict native HTML/XML/LaTeX reference
  and complete 601-page PDF. The final XML parameter helper makes zero changes to its database; unchanged source and TeX
  inputs permit reuse of this completed result.
- Real-Doxygen regressions cover header/source contracts, parameters, returns, ownership, failures, declaration/body
  locations, header-only definitions, unrelated names and signatures, binding isolation, and parameter-name aliases.
  Independent native XML audits check 548 L0 Stage 1 anchors, 586 Stage 2 locations/signatures, and 1,656 L1 anchors.
- Final autobrief coverage: `scripts/tests/test_c_docs.py` passes 45 tests and
  `scripts/tests/test_docgen_function_inventory.py` passes 17 tests. Real Doxygen produces identical brief/detail XML
  for all 230 converted comments. Regressions preserve same-paragraph details, parameter/return contracts, and source
  locations while checking exact implicit first-sentence briefs.
- Fresh strict L0 autobrief extraction uses
  `python -m compiler.docgen.l0_docgen --stage all --strict --output-dir /private/tmp/dea-l0-autobrief-current` and
  preserves all native output bytes (20 XML/26 TeX files for Stage 1; 24 XML/30 TeX for Stage 2) and both reports.
  Unchanged non-C outputs and completed PDFs are reused; unrelated translated include ordering and graph metadata are
  nondeterministic across processes. C shadow copies match current sources, and refreshed L0 bundles verify with
  identical HTML/PDF payload hashes and current source identities. L1/L2 generation inputs are unchanged.
- Simulated Windows configuration checks cover drive, UNC, mixed separators, and spaces. Native Windows execution was
  unavailable; successful POSIX generation does not substitute for it.
- Final HTML audits cover 378 L0 Stage 1 pages, 328 Stage 2 pages, 588 L1 pages, and 75 L2 native pages, with zero
  broken local files or fragments. Verified bundles contain 383, 333, and 592 payload files for the first three
  references. Final HTML-only corrections preserve every XML, TeX source, asset, and PDF byte in 707, 491, and 849
  recorded files; current generator fingerprints and extracted bundle digests verify successfully. Reused successful
  tests and PDF builds retain unchanged relevant inputs; no external source modifications intervened.

## Contract-preservation constraints and compatibility evidence

- Fallthrough annotations affect strict C compilation even when executable tokens are unchanged. Keep the tagged SipHash
  marker immediately before the case 2-to-case 1 transition in both L1 and L2. All three level implementations compile
  with `-std=c99 -Wall -Wextra -Werror -pedantic` under GCC 14.2.0 on Linux x86_64 and produce identical 1-3, 2-4,
  tagged 1-3, and tagged 2-4 hashes for input lengths 0 through 64.
- Extract Windows lexical helpers using function-declaration boundaries rather than documentation text. The focused
  `make test-compiler TESTS='filesystem_native_test interface_fingerprint_runtime_test preparation_profile_test'`
  selection passes with `L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc`. Drive, UNC, mixed separators, spaces, case, and unequal
  paths are lexical simulations on Linux; native Windows validation remains separate. The optional Clang fixture is
  skipped when Clang is unavailable. The focused L0 documentation selection passes 203 cases with 34 external-tool
  skips; warning and public-header checks pass nine cases. Native probes need filesystem ownership checks compatible
  with their execution environment; a sandbox UID mapping that reports owned ancestors as UID 65534 invalidates those
  setup assumptions.
- Doxygen 1.9.8 can omit callback declaration/body relationships when nested parameter names and typedef spellings
  differ. Matching normalized signatures cannot authorize association without explicit XML/source identity. Real
  extraction tests require stable plain-parameter links and validate every supplied relationship; 24 independent XML
  cases cover callback aliases, nested types, documentation on either occurrence, and absent or unrelated links.
- Parse LaTeX caption parameter identifiers independently of padding and comma placement while retaining signature,
  ownership, failure, and parameter-description checks. Older captions include separators inside name fields.
- `scripts/tests/test_docgen_function_inventory.py` passes all 49 cases with Doxygen/Python combinations 1.9.8/3.14.7,
  1.18.0/3.14.7, and 1.18.0/3.15.1. With Doxygen 1.9.8 and Python 3.15.1, the L0 documentation selection plus shared
  inventory, C-contract, and input-fingerprint checks passes 269 cases. These macOS reproductions establish version
  compatibility independently of Windows path semantics; they do not substitute for native Windows execution.

## Outcome

All maintained C functions follow the canonical convention, and full references retain their contracts and original
declaration/definition locations. The L1 compiler binding audit completes the selected inventory; L2 reference limits
remain explicit rather than suppressed. The changes are complete locally; remote publication is outside this plan.
