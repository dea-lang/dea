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

## Authorization boundary

This skill ends at a local commit and handoff. A request to implement, finalize, prepare, or commit work authorizes the
local finalization steps below, but never authorizes a remote operation.

While using this skill:

- do not create or push tags
- do not push commits to any remote
- do not create, publish, edit, or delete a release
- do not dispatch workflows or trigger documentation, Pages, package, or site deployments
- do not write to another repository

Plans that mention those operations do not grant authority to perform them, even when the user asks to implement the
whole plan. Sandbox, tool, or escalation approval grants capability only and is not user authorization. Stop after the
local commit, report the current upstream and pending commit range, and leave every remote action for a separately
authorized follow-up.

## Finalization workflow

1. Review the diff and classify the work:

- one cohesive change: one commit
- separable implementation/docs/tooling pieces: two or three commits
- unrelated work: leave it unstaged and tell the user

2. Finish lifecycle artifacts before committing:

- active plans that are complete move to `work/plans/<kind>/closed/` or `lN/work/plans/<kind>/closed/`
- update `Status: Completed`, completion notes, and final repro/validation commands
- future follow-up work stays as a draft plan in the correct kind, for example `tools` for test-runner/tooling work
- if completion depends on a push, tag, release, deployment, cross-repository write, or other gated external result,
  keep the plan active; do not close it based on unauthorized external state

2a. Check for ADR-worthy decisions:

If the plan introduced or confirmed a design decision with lasting architectural significance, check whether a matching
ADR exists in `docs/decisions/`, `l0/docs/decisions/`, or `l1/docs/decisions/`. If not, flag the gap in the handoff and
note that a new ADR may be warranted. If a new ADR is needed, create it (with metadata, all required sections, and
resolved links) and update the corresponding `decisions/INDEX.md` in the same commit.

3. Refresh docs affected by shipped behavior:

- update relevant `Version: YYYY-MM-DD` metadata when editing reference/status docs
- do not document draft-only future behavior as shipped

4. Validate the exact work being committed. Before choosing or running a command from the scope matrix below, apply the
   mandatory reuse gate.

### Mandatory reuse of just-completed validation

Reuse is a requirement, not an optional optimization. When an applicable full or level test suite completed successfully
earlier in the same task and its result remains available in the task tool history, including immediately before a user
says "ok commit", record and reuse that result if the validated inputs have not changed. **Do not run the suite again.**

Treat validation as reusable when all of these are true:

- The completed command covered the current code/build/test scope. A passing `test-all` satisfies `test`; a passing
  `test` does not by itself satisfy `test-all`.
- No code, tests, build configuration, dependencies, generated source, or compiler/toolchain selection covered by the
  result changed after the run. Any branch or `HEAD` change preserved the exact validated tree.
- No user, external process, or other agent modified an input covered by the result after the run.
- The result was complete and successful, and the current `git status --short`, diff, and task tool history provide
  enough evidence that it still applies.

A new user message such as "ok commit", activation of this skill, a short passage of time, diff/status inspection, or
staging unchanged content does not invalidate validation. Plan closure, documentation edits, and Markdown-only hook
formatting after the suite also do not invalidate code-test results; run the applicable docs checks plus the mandatory
staged whitespace and pre-commit checks instead.

When there is no clean-build or artifact-validity reason to rerun normal validation, unchanged inputs already passed
`test`, and the final classification requires `test-all`, reuse the normal-suite result and run only the missing
dedicated trace target for each affected level: `make -C l0 test-stage2-trace` and/or `make -C l1 test-stage1-trace`.
"Affected level" means every level selected by the scope matrix, including all registered levels for root/cross-cutting
validation. The unchanged passing `test` plus the applicable passing trace target(s) jointly satisfy full validation; do
not invoke `test-all` merely to repeat the normal work.

Do not upgrade a just-passed applicable `test` or `test-all` run to its `clean` form solely because the scope matrix
names the clean command. The `clean` prefix is how to obtain fresh validation when validation is needed, not a reason to
discard a passing result for unchanged inputs. Rerun from clean only when the work concerns clean-build behavior,
dependency or artifact invalidation, or there is concrete reason to distrust the prior artifacts.

If an input covered by the prior suite changed, the suite did not cover the current scope, an external modification
affected a covered input, or the evidence is uncertain, run the smallest applicable validation not already satisfied by
a reused result. Always run the staged whitespace check and pre-commit. If pre-commit changes code, tests, build
configuration, dependencies, or generated source, rerun the affected validation; Markdown-only rewrites require only
restaging and rerunning the staged checks.

In the final handoff, name every reused validation command and result and state why it remained valid, including the
absence of intervening relevant or external modifications.

### Validation tier classification

Choose the validation tier from the complete intended commit diff before applying the level scope matrix. Scope and tier
are independent decisions; reclassify if staging or pre-commit changes that diff:

- `test` is the normal validation aggregate. It preserves the ordinary compiler, example, environment, workflow, and
  distribution checks owned by the affected level while omitting only the dedicated broad `run_trace_tests.py` sweep.
  Focused trace regressions already embedded in a normal suite remain included.
- `test-all` is the full aggregate: `test` plus the affected level's dedicated ARC/memory trace sweep.

Require `test-all` when any functional change can affect trace health or the trace gate itself, including:

- runtime implementation or configuration, allocation tracking, quarantine behavior, pointer provenance/bounds/alignment
  validation, runtime variants, or compiler/runtime flags that select those behaviors
- ownership or lifetime behavior such as `new`, `drop`, raw allocation/free/reallocation, ARC retain/release, managed
  assignment/copy/move/return/argument passing, nullable unwrap, owned container storage, generated cleanup, or
  allocation-bearing control flow in self-hosted compiler code
- backend or C-emitter behavior that can alter generated allocation, ownership, lifetime, cleanup, or trace
  instrumentation
- trace flags or defines, trace event formats, runner/checker logic, discovery/exclusion/parallelism, artifact handling,
  trace environment, or Make/CI wiring of dedicated trace targets
- adding, changing, removing, or renaming a trace-eligible top-level `.l0` test under `l0/compiler/stage2_l0/tests/` or
  `l1/compiler/stage1_l0/tests/`, or a fixture/dependency whose execution can affect that trace result; when the changed
  case is intentionally excluded from the default sweep, also run its documented focused trace command because
  `test-all` will not execute it

`test` is sufficient only when every functional change is confidently trace-independent. Examples include:

- diagnostics, source spans, help/version/output wording, AST/debug printing, and comparable presentation-only edits
- lexer, parser, name-resolution, or type-analysis changes that do not alter ownership classification, accepted-program
  memory semantics, emitted cleanup, or the self-hosted compiler's own owning-value/control-flow behavior
- pure scalar behavior with no allocation, managed values, pointer validation, cleanup, or trace-instrumentation impact
- new or changed non-trace Python tests and ordinary test harnesses that do not affect trace discovery or execution
- CI routing, packaging, release, documentation tooling, or Make changes that do not alter trace invocation, inputs,
  environment, compiler/runtime flags, or artifacts

These categories select the aggregate tier only. Continue to run every focused validation required by the affected
subsystem. Do not require full validation solely because a path is compiler-, test-, CI-, or tooling-related. If the
diff mixes trace-independent and trace-sensitive work, or the classification is uncertain, use `test-all`.

### Validation scope matrix

Use this matrix for each required validation not already satisfied by a reused result. Scope the remaining runs to the
level(s) actually touched (determine touched paths from the same `git status --short`/diff review used in step 1 and the
Required-context section):

For history-only rewrites such as squash, reword, or reorder operations:

- Start from a clean worktree and record the pre-rewrite commit and tree.

- Compare the proposed tree with the pre-rewrite tree rather than classifying the combined diff against the reset base.

- When the proposed tree is identical and relevant tests or CI for that exact tree are known passing, reuse those
  results instead of rerunning the code suites. Record the reused validation in the final handoff.

- When the proposed tree differs only in documentation, follow the docs-only rule below.

- When any code, build configuration, dependency, or generated source differs, follow the normal level-specific or
  cross-cutting validation rule below.

- Still run the staged whitespace check and pre-commit. For a soft-reset squash, use
  `git diff --cached --quiet "$pre_rewrite_commit"` to prove staged tree identity, then verify the replacement commit's
  tree matches the recorded pre-rewrite tree.

- For trace-independent non-documentation functional changes confined to `l0/`: run `make -C l0 clean test`.

- For trace-sensitive non-documentation functional changes confined to `l0/`: run `make -C l0 clean test-all`.

- For trace-independent non-documentation functional changes confined to `l1/`: run `make -C l1 clean test`.

- For trace-sensitive non-documentation functional changes confined to `l1/`: run `make -C l1 clean test-all`.

- For trace-independent cross-cutting non-documentation functional changes (touching more than one level, or touching
  shared/root paths such as `scripts/`, `tools/`, root `pyproject.toml`, `uv.lock`, root config, or the root
  `Makefile`): run the repo-root `make clean test` (executes in all `lN` directories).

- For trace-sensitive cross-cutting non-documentation functional changes: run the repo-root `make clean test-all`
  (executes in all `lN` directories).

- Support-script exception: Do not classify a change as cross-cutting solely because it adds a new auxiliary utility
  under root `scripts/`, plus its focused test and test-target wiring, when it does not change compiler behavior or
  build behavior. Run the utility's focused regression and any affected lightweight workflow target instead; do not run
  root `make clean test-all` only because of that root-level script path. This exception does not apply when the change
  affects compiler source or runtime behavior, compiler source generation, build scripts or flags, artifact layout,
  bootstrap or launcher behavior, or existing test behavior beyond adding the utility's own coverage.

- For docs-only changes: run `git diff --check`; run docs tooling when the edited docs have a generator/check target

5. Stage explicitly. Use `git add -u <scope>` plus explicit new files. Re-check `git status --short`, the staged diff,
   and the validation tier; if staging changes the intended commit, reclassify it before continuing.
6. Run staged whitespace check:

```bash
git diff --cached --check
```

7. Run pre-commit against the root config after staging. The root `pyproject.toml` owns the `dev` dependency group, so
   run from the monorepo root by default:

```bash
uv run --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git diff --cached --name-only --diff-filter=ACMR)
```

If you are already in an immediate level directory such as `l0/` or `l1/`, keep `uv` pointed at the root project and
pass root-relative staged paths:

```bash
uv run --directory .. --group dev pre-commit run --hook-stage pre-commit -c .pre-commit-config.yaml --files $(git -C .. diff --cached --name-only --diff-filter=ACMR)
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
- selected validation tier, or docs-only classification, and the trace-risk rationale for that classification
- validation commands run; for every reused result, its command, result, and unchanged-input evidence, plus tree
  identity for a history-only rewrite
- any unstaged/untracked files intentionally left alone
- current branch upstream and the unpushed commit range
- gated remote or publication actions intentionally left pending
