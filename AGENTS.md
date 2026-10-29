# AGENTS.md

Guidance for AI agents working in this monorepo.

## Repository Structure

This is a monorepo for the Dea programming language and its levels. Each level is a self-contained subtree.

| Directory  | Description                                                         |
| ---------- | ------------------------------------------------------------------- |
| `l0/`      | L0 language, compiler, stdlib, docs, and tests                      |
| `l1/`      | L1 canonical compiler implemented in L0, stdlib, runtime, and tests |
| `l2/`      | L2 canonical compiler implemented in L1, stdlib, runtime, and tests |
| `editors/` | Shared editor grammars, modes, tags, docs, and tests                |
| `scripts/` | Shared monorepo automation and helper modules                       |
| `tools/`   | Vendored third-party dependencies                                   |
| `docs/`    | Dea-wide and monorepo-wide stable docs                              |
| `work/`    | Dea-wide and monorepo-wide plans/proposals                          |

The official public repository for Dea is [dea-lang/dea](https://github.com/dea-lang/dea). Use this canonical URL in
every other technical file or document that links to Dea's public repository.

## Per-Level Guidance

For L0-specific guidance, read `l0/AGENTS.md`.

For L1-specific guidance, read `l1/AGENTS.md`.

For L2-specific guidance, read `l2/AGENTS.md`.

For human-facing monorepo structure and root workflow guidance, read `MONOREPO.md`.

For Dea-wide plans, proposals, and shared refactors, use `work/` at the repository root.

## Root Makefile

The monorepo root `Makefile` is intentionally minimal. Use it only for monorepo maintenance:

- `make help`
- `make venv`
- `make test`
- `make test-extended`
- `make clean`
- `make clean-all`

Do not treat the root `Makefile` as a dispatcher for focused level-local build, test, or docs targets. Root `make test`
runs repository checks and each registered level's normal validation; root `make test-extended` runs repository checks
and each level's extended gate. Their contents vary by level: L0 `test-extended` includes its Stage 2 trace sweep, while
L1/L2 `test-extended` cover their canonical compiler normal suites without CI-only cases. Use level-local `test-ci` for
exhaustive compiler validation, including applicable environment, trace, and child fixtures. L1 artifact acceptance
remains a separate gate; L2 additionally provides opt-in `test-isolation`. L2 requires explicit `L2_BOOTSTRAP_L1C`,
including when root aggregate tests enter L2. Installed L1 is the default; `L2_BOOTSTRAP_MODE=development` permits
explicit development-toolchain reuse as described in `l2/AGENTS.md`. For targeted level work, enter that level's
directory first.

## Validation Ownership

- A level's suite validates that level without reading successor source or artifacts. L0 checks must not depend on L1 or
  L2 files. A successor owns comparisons against an explicitly supported predecessor contract.
- Runtime compatibility covers reviewed common signatures and representations, not automatic equality of all APIs or
  private implementation details. Keep intentional level differences explicit and tested.
- Shared repository tests live under `scripts/tests/` and run through root aggregate targets or Unified CI's repository
  checks. Do not add shared cross-level tests to predecessor aggregates merely because their helpers were introduced
  there.
- CI selects the changed level and affected consumers of predecessor compiler, runtime, or build inputs. Successor-only
  changes do not select predecessor compiler suites. L2 selection still requires its configured enablement.
- Recover unavailable event comparison bases before routing rewritten pushes. Use the pull-request merge base for PR
  changes. If comparison evidence cannot be recovered, report the reason and retain conservative validation.

## Shared Environment

- The monorepo is a single `uv` workspace rooted at the repository root, with `l0/`, `l1/`, and `l2/` as workspace
  members (see `pyproject.toml`).
- One shared virtual environment lives at `./.venv`. One lockfile lives at `./uv.lock`.
- The root `Makefile` owns `make venv`. It prefers `uv sync --all-groups` and falls back to `python -m venv` plus
  `pip install` of the dev/docs dependency-group specifiers when `uv` is not on `PATH`. `uv` is therefore an optional
  accelerator, not a hard dependency.
- Level-local `make venv` targets delegate upward to the root and are no-ops once the shared `./.venv` is in sync.
- On Windows, the shared `.venv` uses native CPython (`Scripts/python.exe`). Make forwards its selected `PYTHON` to
  `uv sync --python`; use native `HOST_PYTHON` (or explicit `PYTHON`) when bootstrapping from MSYS2. An old MSYS2
  `.venv` must be recreated, not reused. POSIX selection is unchanged.
- Windows L0 CI also runs the complete Stage 1 suite under a separate temporary UCRT64 Python environment outside the
  checkout. Provision dependencies once from `uv export --frozen --all-groups --no-emit-workspace` using that
  environment's pip; invoke `make -C l0 test-stage1-msys2` with explicit `DEA_MSYS2_TEST_PYTHON`. Never use this
  interpreter for shared tooling or ask uv to manage it with `--python`.
- Dev/docs dependency groups (`pre-commit`, `pytest`, `pytest-xdist`, `mdformat*`, `jinja2`, `PyYAML`, `pygments`) are
  declared once in the root `pyproject.toml`.

## Documentation And Work Tracking

- In every repository document, including plans, initiatives, ADRs, and agent/skill guidance, never refer to the person
  directing the work as "the user". Use "the project maintainer" for an individual, or "the project team" / "the Dea
  team" for collective work, only when attribution is needed. Otherwise state the requirement or finding directly.
  Reserve user terminology for actual Dea users; never conflate them with the project maintainer or team. For example:
  "The project team measured the performance under Linux."
- Keep plans and other lifecycle documents concise records of scope, methods, findings, decisions, conclusions, and
  verification evidence. Update the relevant sections as work progresses and consolidate superseded notes. Do not append
  conversational back-and-forth, a step-by-step development history, repeated progress reports, or a diary of
  implementation attempts. Preserve an unsuccessful approach only when its evidence or conclusion informs the design or
  prevents repeating a known failure, and summarize that lesson directly. Planned steps, reproducible procedures,
  current status, and remaining work are still appropriate.
- Level-owned docs stay inside that level subtree (for example `l0/docs/**`).
- Level-owned lifecycle artifacts stay inside that level subtree under `work/` (for example `l0/work/**`).
- Root `docs/**` is for Dea-wide and monorepo-wide stable material only.
- Root `work/**` is for Dea-wide and monorepo-wide lifecycle artifacts only.
- In Markdown links to repository files, use repository-root paths as the visible link text (for example
  `docs/specs/compiler/diagnostic-code-catalog.md`), not relative-path text such as `../../..`.
- Do not mention commit IDs, short SHAs, or full SHAs in work plans, documentation, ADRs, or other lifecycle artifacts.
  Refer to named plans, dates, features, bug IDs, or descriptive change names instead.
- Do not identify specific CI or workflow runs in work plans, documentation, ADRs, or other lifecycle artifacts. Omit
  run IDs, run numbers, and run-specific URLs, including job and artifact links. Record workflow or check names,
  relevant platforms, reproducible commands, and outcomes instead.
- Shared compiler CLI modes, options, exit-code meanings, and level-extension rules live in
  `docs/specs/compiler/cli-contract.md`.
- Shared compiler diagnostic-code registry, levels, and meanings live in
  `docs/specs/compiler/diagnostic-code-catalog.md`.
- For shared diagnostic-code documentation, treat L0 Python Stage 1 as the current oracle for registered code
  inventory/meaning unless a broader Dea-wide policy supersedes it.
- When planning work that may introduce or reassign compiler diagnostic codes, inspect
  `docs/specs/compiler/diagnostic-code-catalog.md` and carry explicit diagnostic-code planning in the draft.
- For a genuinely new diagnostic area/category, provisionally reserve one unused block of 20 codes per impacted
  family/category; when only a few new diagnostics are needed in an established area, prefer nearby unused codes first.
- Treat any diagnostic-code reservation written in a plan as provisional and re-check it against the live catalog at
  implementation time before assigning final numbers.
- Non-trivial shared work should be tracked under `work/plans/`.
- Active plans stay at `work/plans/<kind>/`. Closed plans move into `work/plans/<kind>/closed/`.
- Shared parity or seeded-port work defaults to one root-owned shared plan with explicit target implementations and
  per-target status. Do not open a follow-up level-local plan for a mechanical downstream port unless the downstream
  scope materially diverges.
- Plans spawned by an initiative carry a `Parent Initiative:` field in their metadata block pointing at the initiative
  file using the repo-root path. Standalone plans omit this field. Keep `Open plans:` / `Closed plans:` in the
  initiative in sync whenever a plan is opened or closed.
- ADR-style decision records live in `docs/decisions/` (Dea-wide), `l0/docs/decisions/` (L0-specific), and
  `l1/docs/decisions/` (L1-specific), and `l2/docs/decisions/` (L2-specific). Each ADR links the decision to the closed
  plans that shaped it and the current docs where it is normatively recorded. ADR numbers are never reused; superseded
  ADRs stay in place with updated status.

### ADR Impact In Plans And Initiatives

Every active plan and initiative must contain exactly one `## ADR Impact` section. Use one record per atomic
architectural question; repeat the record when the document addresses independent questions:

```markdown
## ADR Impact

- Decision: Short architectural question or durable choice.
  - Scope: Shared
  - Disposition: New ADR
  - ADR: `docs/decisions/`
  - Rationale: Why this disposition and destination are appropriate.
```

Every record requires `Decision`, `Scope`, `Disposition`, `ADR`, and `Rationale`.

- `Scope` is `Dea-wide`, `Shared`, `Repository/tooling`, `L0`, `L1`, or a future `L<N>`. Use `N/A` only with
  `ADR not warranted`.
- `Dea-wide`, `Shared`, and `Repository/tooling` decisions belong in `docs/decisions/`. Level decisions belong in the
  matching `lN/docs/decisions/` directory. Root shared work may carry a targeted level decision. Level-local work may
  reference a root scope or its own level, but never a sibling level. The exact ADR path must match the declared scope.
- `Pending` is allowed only while a document is active. It uses `ADR: None` and records what remains unresolved.
- `New ADR` points to the destination directory while active and to the exact numbered ADR file when closed.
- `Amend ADR` and `Covered by ADR` point to an exact existing, indexed ADR file.
- `ADR not warranted` uses `ADR: None` and a substantive rationale. When a document contains no ADR-worthy decision, use
  this as its sole ADR Impact record.

Do not close a plan or initiative while any ADR Impact record is `Pending`. In the same change that closes it:

- `New ADR` requires the exact numbered ADR, its index row, and a resolvable ADR link back to the closed document.
- `Amend ADR` requires the named ADR to be updated and linked to the closed document.
- `Covered by ADR` requires the named ADR's `Related Plans` section to be updated with a resolvable link to the closed
  document.

Untouched closed documents created before this policy are grandfathered. Any added, renamed, or modified closed plan or
initiative must carry a valid final ADR Impact section. Run `python3 scripts/check_adr_impact.py --all-active` while
planning and `python3 scripts/check_adr_impact.py --staged` before committing; pre-commit and CI enforce the same rules.

### ADR Maintenance

**When to create a new ADR:** in the same change that closes a plan or initiative that introduced or confirmed a lasting
design decision with architectural significance. The ADR number is the next unused number in the relevant `decisions/`
directory.

**Lifecycle steps:**

1. Create `NNNN-slug.md` with metadata bullets (`- Decision date:`, `- Last edited:`, `- Status:`), all required
   sections (Context, Decision, Rationale, Consequences, Related Plans, Current Docs), a resolvable link to each closed
   source document, and resolve all links before committing.
2. Add a row to the corresponding `decisions/INDEX.md`.
3. If the new ADR supersedes an existing one: update the old ADR's `Status:` to
   `Superseded by [ADR-NNNN](NNNN-slug.md) (YYYY-MM-DD)` and add a `- Supersedes: [ADR-XXXX](XXXX-slug.md)` bullet to
   the new ADR's metadata block.

**INDEX.md policy:** each `decisions/INDEX.md` is the only file that tracks which ADRs exist in its scope; it must be
kept in sync manually whenever an ADR is added or superseded. A superseded ADR stays in the index with its updated
status; the next new ADR takes the next sequential number.

**Em-dash and n-dash policy:** use ASCII punctuation only. Choose the form that fits the local context: colon (`:`) to
introduce an explanation or list, parentheses for a parenthetical aside, semicolon (`;`) for a contrast, comma (`,`) for
a simple annotation. Do not use `--` (double-hyphen) unless none of the above fit naturally.

## Remote And Publication Authorization

Treat local implementation, remote writes, and publication as separate authorization boundaries:

| Action                                                                         | Required authorization                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Analysis, tests, builds, and explicitly requested local edits                  | Allowed within the stated task scope. "Organize" and "review" are read-only; "draft" authorizes only the named draft artifact.                                                                                                                                                                         |
| Local commits                                                                  | Allowed when the project maintainer requests implementation or finalization and the commit follows repository conventions. A local commit never authorizes a push.                                                                                                                                     |
| Push to the current private upstream                                           | Requires an explicit push request and verification that the checked-out branch's configured upstream is the exact requested destination.                                                                                                                                                               |
| Public, cross-repository, workflow-dispatching, or deployment-triggering write | Requires fresh project maintainer confirmation immediately before execution. Show the exact command or action, remote and branch or artifact, pending commit range where applicable, and all known downstream effects.                                                                                 |
| Public branch push                                                             | Also requires repository instructions to designate that public target and the checked-out branch to track that exact public remote and branch. Do not bypass this requirement with `HEAD:<branch>`, `--set-upstream`, `pushRemote`, an ad hoc refspec, or an upstream change made as part of the push. |
| Release tag creation                                                           | Requires a separate, explicit project maintainer request naming the exact tag and target commit. A request to implement a plan that mentions the tag does not satisfy this gate.                                                                                                                       |
| Release tag push                                                               | Always requires a separate, fresh project maintainer confirmation immediately before the push, even if tag creation or release preparation was already requested. Show the tag, target commit, exact remote URL, and all release, asset, Pages, deployment, and cross-repository effects.              |
| Blog or announcement publication                                               | Keep copy as a local draft until the project maintainer reviews its exact final contents. Any content change invalidates that review. Promotion or deployment requires a fresh project maintainer confirmation that the exact copy is clear to publish.                                                |

- A plan describes possible future work; it does not grant authority to create a release tag or cross a manual
  remote-write or publication gate, even when the project maintainer asks to implement the whole plan.
- "Reviewed" means reviewed by the project maintainer in the exact form to be published. Agent review, tests, and CI do
  not satisfy this requirement.
- Sandbox escalation, tool approval, stored credentials, and technical capability are not project maintainer
  authorization.
- Treat a private-source push that automatically updates a public site as a deployment-triggering write.
- Authorization for one remote write does not authorize follow-up pushes, CI fixes, workflow reruns, dispatches, or
  publication actions. Obtain the authorization required for each new action.

## Git Conventions

- Multiline commits: sentence-case summary with period, then factual body as bullets with `- ` prefix, sentence-case,
  ending with a period.
- Always leave one blank line between the summary line and the first body bullet.
- Each bullet is a single line; do not wrap bullets across multiple lines.
- Before committing, run pre-commit from the monorepo root against the root config:
  `uv run --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR)`.
- For multiline commit messages, write the message to a temporary file and use `git commit -F <file>`.
- Avoid assigning to `zsh` special parameters such as `status` in shell helpers.
- No tag-phrases such as "for clarity" or "for consistency".
- Use backticks for language/code identifiers in commit messages.
- Do not mention commit IDs, short SHAs, full SHAs, or specific CI or workflow runs in commit messages. Omit run IDs,
  run numbers, and run-specific URLs, including job and artifact links. Refer to the relevant plan, issue, feature, or
  behavior and summarize validation by check name and outcome instead.
- No `Co-Authored-By` lines.

### Example-only validation

- Treat a change as example-only only when the complete intended diff is confined to example programs and example-local
  supporting files. Changes to shared compiler, runtime, build, test, or tooling behavior follow the normal validation
  rules.
- For an example-only change, do not run aggregate `test`, `test-extended`, `test-ci`, trace, or other extensive suites.
  From each affected level directory, run `make check-examples`, then manually run every added or modified example
  through its intended execution workflow and inspect its output and behavior.
- Still run the required staged whitespace and pre-commit checks before committing.

### Level naming in summaries

- Determine level scope from the primary intent of the change, not solely from the locations of the touched files.
- When a commit's primary work applies to exactly one language level, include that level (`L0`, `L1`, or a future level)
  naturally within the summary sentence.
- Prefer `Implement L1 per-module backend lifecycle output.` Do not use the level as a scope-label prefix or suffix,
  such as `L1: Implement per-module backend lifecycle output.` or `[L1] Implement per-module backend lifecycle output.`
- Omit level names when the work is cross-level, applies to all levels, or is level-neutral, including shared
  documentation and vendored dependency updates.
- Treat primarily single-level work as level-scoped when it also updates supporting shared files, such as the shared
  diagnostic-code catalog.
- An example-only summary must name each affected level naturally, as in `Add a new L0 Forth parsing example.`

### Summary verb selection

- The commit summary must describe the repository change introduced by the commit, not the lifecycle state of the work
  session or plan file.
- Choose a precise imperative verb that describes the primary change. The vocabulary is open; the verbs and examples
  below are guidance, not an exhaustive list or mandatory assignments by change category.
- `Fix`, `Implement`, `Refactor`, and `Document` are useful defaults when a more specific verb would not make the
  summary clearer. `Refactor` describes restructuring without changing semantics. Docs-only changes need not begin with
  `Document`, and bug fixes may use a more specific verb such as `Restore` when it accurately describes the repair.
- `Add` applies to any new capability or artifact, including examples, tests, tooling, and documentation.
- Keep claims supported by the change: use `Optimize` for demonstrated efficiency improvements and `Enforce` when checks
  actually enforce the stated requirement.
- Use `Complete ...` only for follow-up completion work where the implementation already exists in prior commits and
  this commit finishes remaining integration, docs, tests, or plan cleanup.
- Use `Close ...` only when the primary repository change is closing, archiving, or updating an already-existing plan or
  lifecycle artifact. Do not use `Close ...` for a commit whose primary change is a code fix or feature implementation.
- Mention plan closure in a body bullet, not in the summary, unless the plan lifecycle change is the primary change.

Suggested verbs by intent:

| Verbs                                       | Appropriate change                                                                            |
| ------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `Add`, `Introduce`, `Extend`                | Introduce something or expand an existing capability.                                         |
| `Support`, `Enable`, `Allow`                | Make a platform, workflow, or language construct usable.                                      |
| `Remove`, `Retire`, `Deprecate`             | Delete something, end its use, or begin phasing it out.                                       |
| `Restore`, `Preserve`                       | Recover lost behavior or maintain a required property.                                        |
| `Harden`, `Tighten`                         | Strengthen safety boundaries, validation, or constraints.                                     |
| `Optimize`, `Reduce`                        | Improve efficiency or lower a specific cost.                                                  |
| `Port`, `Backport`, `Migrate`               | Move an implementation between languages, levels, or conventions.                             |
| `Rename`, `Split`, `Consolidate`, `Replace` | Describe a concrete structural change.                                                        |
| `Integrate`, `Configure`                    | Connect existing components or change their setup.                                            |
| `Test`, `Cover`                             | Add tests or coverage as the primary change.                                                  |
| `Clarify`, `Define`, `Record`               | Resolve ambiguous wording, specify a contract, or preserve a decision.                        |
| `Refresh`, `Revise`, `Align`                | Bring existing documentation or planning into agreement with current requirements.            |
| `Enforce`                                   | Introduce checks that require a policy to be followed.                                        |
| `Update`, `Upgrade`, `Bump`                 | Change existing content or dependency versions; prefer the more specific verb where possible. |

Example summaries:

- `` Remove the deprecated L1 `case` default. ``
- `Integrate L0 documentation validation into Unified CI.`
- `Extend L1 trace validation to child fixtures.`
- `Introduce explicit validation tiers and reduce local test cost.`
- `Prohibit specific CI run references in repository documentation.`
- `Record Dea architectural decisions and enforce ADR impact requirements.`

## Quality Standards

- When operating in autopilot or agentic mode, do not send an extra follow-up request after the task is already complete
  (for example asking whether the project maintainer wants a summary). End after delivering the result unless the
  project maintainer explicitly asks for more.
- Python uses Google Style docstrings with `Args`, `Returns`, and `Raises` sections.
- Dea declaration documentation uses multiline Doxygen/Javadoc-style block comments. Put the opening `/**` on its own
  line, prefix content lines with ` *`, and include `@param` and `@return` sections where applicable. C and Dea
  contracts use Javadoc autobrief: the first sentence is the brief; omit explicit `@brief` and `\brief` commands.
- Every repository-owned C function definition has its complete multiline Doxygen contract immediately before the
  definition. This includes private, static, inline, and header-only definitions. Corresponding header prototypes have
  only an ordinary single-line `/* ... */` comment reproducing the canonical brief sentence exactly, without `@brief`.
  Consolidate parameters, returns, ownership, failures, and other guarantees in the definition's full contract. Keep
  header-only libraries header-only, including `dea_siphash.h`.
- Leave a blank source line before every ordinary or Doxygen block comment, except at the beginning of a file. Keep
  type, field, enum, macro, and file documentation in its natural location. Exclude identified vendored third-party and
  generated files from bulk comment rewrites; do not remove their existing documentation.
- Run `python3 scripts/check_c_docs.py` after changing C contracts. Documentation inventories must include relevant
  implementation `.c` files and implementation headers. Match documentation across prototype/definition occurrences by
  function identity, never by name alone; preserve different static functions, signatures, and language bindings.
- Keep code names and comments in English.
- Update relevant tests in the same change.
- Update relevant documentation in the same change.

### Portable Path Comparisons

- Apply these rules across all levels when writing or reviewing path handling and tests, especially diagnostics,
  subprocess output, launchers, installation, and documentation tooling. Review new path assertions for Windows
  portability before committing; a passing POSIX run does not exercise Windows path semantics.
- Choose the comparison from the contract. Native filesystem paths may use `\`, `/`, or mixed separators on Windows. Do
  not compare `str(expected_path)` literally with diagnostic or subprocess text unless exact spelling is the behavior
  under test. For same-host native path text where only separators are irrelevant, normalize both sides with
  `.replace(os.sep, "/")`; this preserves literal backslashes in POSIX filenames. Prefer extracting the path field
  before comparing when the output format permits it, and retain independent assertions for diagnostic codes, exit
  status, and other required text.
- Host `Path` and `os.path` follow the running platform. For synthetic Windows paths tested on POSIX, use
  `PureWindowsPath` or `ntpath` with explicitly chosen semantics; do not assume host `normpath` handles Windows
  separators. Lexical equality does not establish filesystem identity. Use `samefile` only when both paths exist and
  physical identity is the intended contract.
- Do not normalize away behavior under test. Keep exact assertions for specified canonical output, manifest paths, URLs,
  escaping, and security checks. Do not indiscriminately lowercase paths, resolve symlinks, collapse `..`, or rewrite an
  entire structured payload merely to make an assertion pass. Case and alias equivalence depend on the relevant
  filesystem and contract.
- For changed path comparisons, exercise representative POSIX and Windows spellings, including mixed separators and
  spaces, plus a genuinely different path that must still fail. Include drive, UNC, case, or alias cases when the
  affected behavior handles them. Prefer existing focused tests; use a small portable probe where the Windows branch
  would otherwise be untested locally. Report simulated checks separately from native Windows validation and keep
  unavailable native coverage explicit.
- When Windows CI fails on a path assertion, inspect the expected and actual paths and the preceding behavior checks
  before attributing it to a compiler or runtime bug. Correct a faulty test comparison without weakening unrelated
  checks or changing production output whose spelling already satisfies its contract.
