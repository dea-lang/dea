---
name: squash-recent-commits
description: Squash the most recent N Git commits into one cohesive local commit while consolidating transient bug-fix documents and preserving durable findings in surviving documentation. Use when the user asks to squash, fold, or combine a recent linear commit suffix; default N to 2 when the user does not specify it.
---

# Squash Recent Commits

Replace a recent linear suffix with one commit whose tree expresses the final intent. Treat documentation consolidation
as part of that final tree, not as a reason to discard useful knowledge.

## Required context

1. Read root `AGENTS.md`.
2. Read the level-local `AGENTS.md` guide for every affected `l0/` or `l1/` subtree.
3. Read `.agents/skills/finalize-dea-work/SKILL.md` and follow its current history-rewrite validation, staged-check,
   pre-commit, and commit-message rules.
4. Prefer repository instructions over this workflow when they are stricter.

## Inputs and authorization

- Use the user-supplied `N`; use `2` when it is omitted.
- Require `N` to be a decimal integer of at least 2. Treat `N = 1` as a no-op and ask for correction rather than
  manufacturing a replacement commit.
- Interpret invocation as authorization to rewrite exactly the selected local suffix and create its replacement commit.
  Do not widen the range.
- Do not stash, discard, or absorb pre-existing worktree changes.
- Do not fetch, push, force-push, create or push tags, change an upstream, or perform any other remote write. A local
  squash never authorizes publication.

## 1. Establish a safe range

1. Require a clean index and worktree with `git status --short`. Stop and report any pre-existing changes; do not hide
   them with a stash.
2. Require a named branch. Stop on detached `HEAD`.
3. Resolve the base as the first parent immediately before the selected suffix, equivalent to `HEAD~N`. Verify that it
   exists before changing history.
4. Record the branch name, base commit, original `HEAD`, and original `HEAD` tree. Keep the original `HEAD` available in
   the handoff as the reflog recovery point; do not create a backup tag.
5. Inspect the selected commits in chronological order, including each subject, body, changed paths, and full diff.
6. Detect merge commits in the range. Stop unless the user explicitly authorizes flattening their topology into one
   ordinary commit.
7. Check the configured upstream and locally known remote-tracking refs. If any selected commit is already reachable
   from one of them, disclose that the rewrite affects published history and continue only after the user explicitly
   confirms that consequence. Do not fetch merely to perform this check.

## 2. Define the cohesive final state

Summarize the selected range's single primary intent before editing. Review the combined diff from the base to the
original `HEAD`, then reconcile later fixes with earlier implementation so the replacement commit reads as one finished
change rather than a timeline of mistakes.

Find possible intermediate bug-fix documents from the paths added or changed by the selected commits. Delete a document
only when all of these conditions hold:

- it exists solely to describe an intermediate bug, failed attempt, or superseded state
- the final behavior in the selected range makes that state obsolete
- it is not required by repository lifecycle, ADR, audit, release, or index policy
- all live references to it can be removed or redirected correctly
- every durable fact it contains is already documented elsewhere or is migrated before deletion

Retain the document when its status is ambiguous. Do not sweep unrelated documentation outside the selected work.

For each deletion candidate, extract durable information before removing it. Preserve facts such as:

- root causes, invariants, and architectural constraints
- reusable debugging, tracing, reproduction, or validation techniques
- subtle failure modes, ownership rules, and recovery procedures
- regression-test rationale and conditions that distinguish the real bug from misleading symptoms
- lasting design decisions and their consequences

Do not preserve obsolete instructions, raw investigation chronology, false starts without teaching value, or
intermediate behavior as though it were current. Prefer the existing normative reference, troubleshooting guide,
surviving final plan, or ADR that owns the topic. Avoid duplicating material already recorded. Follow repository
metadata and index rules, repair inbound links, and never add commit IDs to repository documentation.

Reconcile every surviving plan or initiative's ADR Impact records against the recorded base, because intermediate commit
relationships disappear:

- When the target ADR exists in the base, retain or select `Amend ADR` or `Covered by ADR` as warranted and ensure the
  replacement change updates the ADR with the required plan link.
- When the target ADR is absent from the base but added by the selected suffix, the replacement commit introduces it.
  Use `New ADR` with the exact numbered path and ensure the ADR, index row, and Related Plans link are all staged. Apply
  this independently to each surviving closed document that contributed a decision to the same new ADR.
- Update nearby timeline-dependent wording so it describes creating or amending the final ADR set rather than acting on
  an ADR in an intermediate commit.
- Do not change a disposition merely to satisfy the checker. Confirm that the target ADR records the stated decision; if
  it does not, choose the substantively correct disposition or stop when that choice is ambiguous.

## 3. Build the replacement commit

1. After the scope and documentation migration plan are settled, soft-reset `HEAD` to the recorded base. Use a soft
   reset so the selected commits' combined changes remain staged.
2. Apply the planned documentation edits and deletions to the working tree.
3. Stage only those deliberate documentation changes and any explicit new destination documents. The selected commits'
   original combined changes should already be staged by the soft reset.
4. Review `git status --short`, the staged name-status summary, and the complete staged diff against the base. Verify
   that no unrelated path entered the commit and that the diff represents the final cohesive state.
5. Search for stale references to every removed or renamed document and repair them.
6. Record the staged tree with `git write-tree` immediately before committing.

## 4. Validate and commit

Apply the history-rewrite rules in `.agents/skills/finalize-dea-work/SKILL.md`:

- compare the proposed tree with the recorded original tree
- reuse applicable successful validation for an unchanged code tree
- run documentation checks for documentation-only consolidation
- run broader validation only when the proposed code, build, dependency, or generated-source tree differs
- always run the staged whitespace check and required pre-commit hooks

Run `python3 scripts/check_adr_impact.py --staged` before the remaining final checks. Treat a failure as an in-scope
documentation-consolidation correction, rather than a terminal validation failure, only when all of these conditions
hold:

- the failure says an `Amend ADR` or `Covered by ADR` target must exist in the base or is absent from the base
- the target ADR is absent from the recorded base and added in the staged replacement tree
- the affected surviving document and target ADR are both within the selected suffix's combined change
- the target ADR substantively records the document's decision and links the document from Related Plans

When these conditions hold unambiguously, change the record to `New ADR`, reconcile nearby chronology-dependent wording,
stage only those documentation edits, review the diff, and rerun the staged ADR check without seeking separate approval.
Do not use this exception for missing ADR content, index entries, links, unrelated documents, targets that existed in
the base, or any other validation failure.

If validation or hooks modify files, stage only the expected edits, review the staged diff again, rerun the affected
checks, and record a new expected tree.

Write one commit message for the resulting repository change. Describe the final implementation, fix, refactor, or
documentation outcome; do not use "squash commits" as the summary and do not concatenate the old messages. Follow the
repository's required message format and commit through a temporary message file when it is multiline.

## 5. Verify and report

After committing, verify all of the following:

- exactly one commit exists between the recorded base and new `HEAD`
- the new commit's sole parent is the recorded base
- the new commit tree equals the tree recorded immediately before commit
- the index and worktree are clean
- removed documents have no stale live references
- no remote operation occurred

Report the effective `N`, the new commit summary, validation run or reused, and the documentation decisions. For each
removed document, name the surviving destination of any migrated facts; explicitly say when no qualifying intermediate
document existed. Include the original `HEAD` as the local reflog recovery point and report any resulting ahead/behind
relationship without pushing.

Except for the narrowly defined squash-induced ADR topology correction in section 4, if any rewrite, edit, validation,
or commit step fails, stop with the index and worktree intact. Report the recorded base and original `HEAD`; do not
attempt a hard reset or other destructive recovery without explicit authorization.
