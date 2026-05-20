---
name: finalize-dea-work
description: Finalize Dea repo work by checking plans/docs/tests, staging only intended files, running level-appropriate validation and pre-commit, and committing with the required Dea L0/L1 message format.
model: sonnet
effort: medium
---

### Finalize and commit Dea work

Use this skill when the user asks to finalize, close plans, commit changes, prepare a commit, or package completed Dea
work.

## Required context

1. Read root `CLAUDE.md` first.
2. If touched paths are under `l0/`, read `l0/CLAUDE.md`.
3. If touched paths are under `l1/`, read `l1/CLAUDE.md`.
4. Check `git status --short` before staging. Never stage unrelated user files.

## Finalization workflow

1. Review the diff and classify the work:

- one cohesive change: one commit
- separable implementation/docs/tooling pieces: two or three commits
- unrelated work: leave it unstaged and tell the user

2. Finish lifecycle artifacts before committing:

- active plans that are complete move to `work/plans/<kind>/closed/` or `lN/work/plans/<kind>/closed/`
- update `Status: Completed`, completion notes, and final repro/validation commands
- future follow-up work stays as a draft plan in the correct kind, for example `tools` for test-runner/tooling work

2a. Check for ADR-worthy decisions:

If the plan introduced or confirmed a design decision with lasting architectural significance, check whether a matching
ADR exists in `docs/decisions/`, `l0/docs/decisions/`, or `l1/docs/decisions/`. If not, flag the gap in the handoff and
note that a new ADR may be warranted. If a new ADR is needed, create it (with metadata, all required sections, and
resolved links) and update the corresponding `decisions/INDEX.md` in the same commit.

3. Refresh docs affected by shipped behavior:

- update relevant `Version: YYYY-MM-DD` metadata when editing reference/status docs
- do not document draft-only future behavior as shipped

4. Run relevant validation before the commit:

- For code changes: run repo-root `make clean test-all` before any commit (executes in all `lN` directories).
- For docs-only changes: run `git diff --check`; run docs tooling when the edited docs have a generator/check target

5. Stage explicitly. Use `git add -u <scope>` plus explicit new files. Re-check `git status --short`.
6. Run staged whitespace check:

```bash
git diff --cached --check
```

7. Run pre-commit from the relevant level directory against the root config after staging:

```bash
uv run --group dev pre-commit run --hook-stage pre-commit -c ../.pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR --relative)
```

If a hook reformats files, stage the hook edits, rerun `git diff --cached --check`, and rerun pre-commit before
committing.

## Commit message rules

Use a temporary message file and `git commit -F <file>` for multiline commits.

Format:

```text
Implement wide integer math follow-up.

- Extend `std.math` with `uint`, `long`, and `ulong` helper families.
- Tighten nullable integer cast and contextual literal lowering.
- Close the completed feature plan under `l1/work/plans/features/closed/`.
```

Rules:

- Summary is sentence case and ends with a period.
- A scope prefix such as `L0:` or `L1:` may be used when it improves readability, but it is not required.
- Leave exactly one blank line between summary and bullets.
- Body bullets start with `- `, are factual, sentence case, and end with a period.
- Keep each bullet on one physical line.
- Use backticks for language, command, type, module, and path identifiers.
- Do not use tag phrases such as "for clarity" or "for consistency".
- Do not add `Co-Authored-By` lines.

Summary verb selection:

- Choose the summary verb from the primary repository change, not from the plan lifecycle action.
- Use `Fix ...` when the commit introduces a bug fix.
- Use `Implement ...` when the commit introduces a feature or implementation.
- Use `Refactor ...` when the commit primarily restructures existing behavior without changing semantics.
- Use `Document ...` when the commit is docs-only.
- Use `Complete ...` only when prior commits already introduced the main implementation and this commit finishes
  residual work.
- Use `Close ...` only when closing, archiving, or updating an already-existing plan or lifecycle artifact is the
  primary change.
- If a plan is created and closed in the same commit as the code change, describe the code change in the summary and
  record the plan action in a body bullet.

## Commit execution

1. Create the message file, for example:

```bash
tmp_msg=$(mktemp)
cat > "$tmp_msg" <<'EOF'
Implement wide integer math follow-up.

- Extend `std.math` with `uint`, `long`, and `ulong` helper families.
- Tighten nullable integer cast and contextual literal lowering.
- Close the completed feature plan under `l1/work/plans/features/closed/`.
EOF
git commit -F "$tmp_msg"
rm -f "$tmp_msg"
```

2. If commit hooks modify files, stage the modifications and retry with the same message file content.
3. After committing, run:

```bash
git status --short
git log -1 --oneline
```

4. Final response must include:

- commit hash and summary
- validation commands run
- any unstaged/untracked files intentionally left alone
