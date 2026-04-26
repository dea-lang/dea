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

## Per-Level Guidance

For L0-specific guidance, read `l0/CLAUDE.md`.

For L1-specific guidance, read `l1/CLAUDE.md`.

For human-facing monorepo structure and root workflow guidance, read `MONOREPO.md`.

For Dea-wide plans, proposals, and shared refactors, use `work/` at the repository root.

## Root Makefile

The monorepo root `Makefile` is intentionally minimal. Use it only for monorepo maintenance:

- `make help`
- `make venv`
- `make clean`
- `make clean-all`

Do not treat the root `Makefile` as a dispatcher for level-local build, test, or docs targets. For those, enter the
level directory first.

## Shared Environment

- The monorepo uses one shared repo-local virtual environment at `/.venv`.
- Level-local `make venv` targets populate or reuse that shared environment.
- Root `make venv` delegates to each registered level.

## Documentation And Work Tracking

- Level-owned docs stay inside that level subtree (for example `l0/docs/**`).
- Level-owned lifecycle artifacts stay inside that level subtree under `work/` (for example `l0/work/**`).
- Root `docs/**` is for Dea-wide and monorepo-wide stable material only.
- Root `work/**` is for Dea-wide and monorepo-wide lifecycle artifacts only.
- In Markdown links to repository files, use repository-root paths as the visible link text (for example
  `docs/specs/compiler/diagnostic-code-catalog.md`), not relative-path text such as `../../..`.
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

## Git Conventions

- Multiline commits: sentence-case summary with period, then factual body as bullets with `- ` prefix, sentence-case,
  ending with a period.
- Always leave one blank line between the summary line and the first body bullet.
- Each bullet is a single line; do not wrap bullets across multiple lines.
- Before committing, run pre-commit from the relevant level directory against the root config:
  `uv run --group dev pre-commit run --hook-stage pre-commit -c ../.pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR --relative)`.
- For multiline commit messages, write the message to a temporary file and use `git commit -F <file>`.
- Avoid assigning to `zsh` special parameters such as `status` in shell helpers.
- No tag-phrases such as "for clarity" or "for consistency".
- Use backticks for language/code identifiers in commit messages.
- No `Co-Authored-By` lines.

## Quality Standards

- When operating in autopilot or agentic mode, do not send an extra follow-up request after the task is already complete
  (for example asking whether the user wants a summary). End after delivering the result unless the user explicitly asks
  for more.
- Python uses Google Style docstrings with `Args`, `Returns`, and `Raises` sections.
- C and Dea source files use Doxygen/Javadoc-style block comments.
- Keep code names and comments in English.
- Update relevant tests in the same change.
- Update relevant documentation in the same change.
