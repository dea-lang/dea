# CLAUDE.md

Guidance for Claude Code and AI agents working in this monorepo.

## Repository Structure

This is a monorepo for the Dea language family. Each language level is a self-contained subtree.

| Directory  | Description                                           |
| ---------- | ----------------------------------------------------- |
| `l0/`      | L0 language, compiler, stdlib, docs, and tests        |
| `l1/`      | L1 bootstrap scaffold, compiler seed, and local tests |
| `scripts/` | Shared monorepo automation and helper modules         |
| `tools/`   | Vendored third-party dependencies                     |
| `docs/`    | Dea-wide and monorepo-wide stable docs                |
| `work/`    | Dea-wide and monorepo-wide plans/proposals            |

The official public repository for Dea is [googlielmo/dea-lang](https://github.com/googlielmo/dea-lang). Use this
canonical URL in every other technical file or document that links to Dea's public repository.

## Per-Level Guidance

For L0-specific guidance, read `l0/CLAUDE.md`.

For L1-specific guidance, read `l1/CLAUDE.md`.

For human-facing monorepo structure and root workflow guidance, read `MONOREPO.md`.

For Dea-wide plans, proposals, and shared refactors, use `work/` at the repository root.

## Root Makefile

The monorepo root `Makefile` is intentionally minimal. Use it only for monorepo maintenance:

- `make help`
- `make venv`
- `make test`
- `make test-all`
- `make clean`
- `make clean-all`

Do not treat the root `Makefile` as a dispatcher for focused level-local build, test, or docs targets. Root `make test`
runs each registered level's normal validation without its dedicated broad trace sweep; root `make test-all` adds those
trace sweeps for full registered-level validation. For targeted level work, enter the level directory first.

## Shared Environment

- The monorepo is a single `uv` workspace rooted at the repository root, with `l0/` and `l1/` as workspace members (see
  `pyproject.toml`).
- One shared virtual environment lives at `./.venv`. One lockfile lives at `./uv.lock`.
- The root `Makefile` owns `make venv`. It prefers `uv sync --all-groups` and falls back to `python -m venv` plus
  `pip install` of the dev/docs dependency-group specifiers when `uv` is not on `PATH`. `uv` is therefore an optional
  accelerator, not a hard dependency.
- Level-local `make venv` targets delegate upward to the root and are no-ops once the shared `./.venv` is in sync.
- Dev/docs dependency groups (`pre-commit`, `pytest`, `pytest-xdist`, `mdformat*`, `jinja2`, `PyYAML`, `pygments`) are
  declared once in the root `pyproject.toml`.

## Documentation And Work Tracking

- Level-owned docs stay inside that level subtree (for example `l0/docs/**`).
- Level-owned lifecycle artifacts stay inside that level subtree under `work/` (for example `l0/work/**`).
- Root `docs/**` is for Dea-wide and monorepo-wide stable material only.
- Root `work/**` is for Dea-wide and monorepo-wide lifecycle artifacts only.
- In Markdown links to repository files, use repository-root paths as the visible link text (for example
  `docs/specs/compiler/diagnostic-code-catalog.md`), not relative-path text such as `../../..`.
- Do not mention commit IDs, short SHAs, or full SHAs in work plans, documentation, ADRs, or other lifecycle artifacts.
  Refer to named plans, dates, features, bug IDs, or descriptive change names instead.
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
  `l1/docs/decisions/` (L1-specific). Each ADR links the decision to the closed plans that shaped it and the current
  docs where it is normatively recorded. ADR numbers are never reused; superseded ADRs stay in place with updated
  status.

### ADR Maintenance

**When to create a new ADR:** after closing a plan that introduced or confirmed a lasting design decision with
architectural significance. The ADR number is the next unused number in the relevant `decisions/` directory.

**Lifecycle steps:**

1. Create `NNNN-slug.md` with metadata bullets (`- Decision date:`, `- Last edited:`, `- Status:`), all required
   sections (Context, Decision, Rationale, Consequences, Related Plans, Current Docs), and resolve all links before
   committing.
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
| Local commits                                                                  | Allowed when the user requests implementation or finalization and the commit follows repository conventions. A local commit never authorizes a push.                                                                                                                                                   |
| Push to the current private upstream                                           | Requires an explicit push request and verification that the checked-out branch's configured upstream is the exact requested destination.                                                                                                                                                               |
| Public, cross-repository, workflow-dispatching, or deployment-triggering write | Requires fresh user confirmation immediately before execution. Show the exact command or action, remote and branch or artifact, pending commit range where applicable, and all known downstream effects.                                                                                               |
| Public branch push                                                             | Also requires repository instructions to designate that public target and the checked-out branch to track that exact public remote and branch. Do not bypass this requirement with `HEAD:<branch>`, `--set-upstream`, `pushRemote`, an ad hoc refspec, or an upstream change made as part of the push. |
| Release tag creation                                                           | Requires a separate, explicit user request naming the exact tag and target commit. A request to implement a plan that mentions the tag does not satisfy this gate.                                                                                                                                     |
| Release tag push                                                               | Always requires a separate, fresh user confirmation immediately before the push, even if tag creation or release preparation was already requested. Show the tag, target commit, exact remote URL, and all release, asset, Pages, deployment, and cross-repository effects.                            |
| Blog or announcement publication                                               | Keep copy as a local draft until the user reviews its exact final contents. Any content change invalidates that review. Promotion or deployment requires a fresh user confirmation that the exact copy is clear to publish.                                                                            |

- A plan describes possible future work; it does not grant authority to create a release tag or cross a manual
  remote-write or publication gate, even when the user asks to implement the whole plan.
- "Reviewed" means reviewed by the user in the exact form to be published. Agent review, tests, and CI do not satisfy
  this requirement.
- Sandbox escalation, tool approval, stored credentials, and technical capability are not user authorization.
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
- Do not mention commit IDs, short SHAs, or full SHAs in commit messages. Refer to the relevant plan, issue, feature, or
  behavior instead.
- No `Co-Authored-By` lines.

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

### Summary verb selection

- The commit summary must describe the repository change introduced by the commit, not the lifecycle state of the work
  session or plan file.
- Use `Fix ...` for a commit that introduces a bug fix, even when the same commit also creates and closes the
  corresponding bug-fix plan.
- Use `Implement ...` for a commit that introduces a new feature or completed implementation, even when the same commit
  also closes the corresponding feature plan.
- Use `Refactor ...` when the commit primarily restructures existing behavior without changing semantics.
- Use `Document ...` when the commit is docs-only.
- Use `Complete ...` only for follow-up completion work where the implementation already exists in prior commits and
  this commit finishes remaining integration, docs, tests, or plan cleanup.
- Use `Close ...` only when the primary repository change is closing, archiving, or updating an already-existing plan or
  lifecycle artifact. Do not use `Close ...` for a commit whose primary change is a code fix or feature implementation.
- Mention plan closure in a body bullet, not in the summary, unless the plan lifecycle change is the primary change.

## Quality Standards

- When operating in autopilot or agentic mode, do not send an extra follow-up request after the task is already complete
  (for example asking whether the user wants a summary). End after delivering the result unless the user explicitly asks
  for more.
- Python uses Google Style docstrings with `Args`, `Returns`, and `Raises` sections.
- C and Dea source files use Doxygen/Javadoc-style block comments.
- Keep code names and comments in English.
- Update relevant tests in the same change.
- Update relevant documentation in the same change.
