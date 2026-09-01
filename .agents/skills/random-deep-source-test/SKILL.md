---
name: random-deep-source-test
description: Perform randomized deep white-box correctness reviews of Dea production sources by selecting files with `scripts/shuffle_sources.py`, examining every function plus its direct callers and callees, scoring risks, and running temporary falsification probes. Use for randomized source correctness testing, deep per-function reviews, or bounded one-hop call-graph reviews in the Dea monorepo.
model: opus
effort: high
---

### Run randomized deep source reviews

Use requests such as `Use $random-deep-source-test for 3 L0 S1 sources.` Interpret omitted selection arguments as a
count of `1` with no level or stage scope.

## Select source files

1. Read root `CLAUDE.md` first. After selection, read `l0/AGENTS.md` then `l0/CLAUDE.md` for every L0 source or test
   route involved, and read `l1/AGENTS.md` then `l1/CLAUDE.md` for every L1 source or test route involved.
2. Resolve an interpreter from the shared virtual environment (`.venv/bin/python` or `.venv/Scripts/python.exe`), then
   fall back to `python3`. Do not assume bare `python` is available.
3. From the monorepo root, run:

```sh
<resolved-python> scripts/shuffle_sources.py COUNT [LEVEL [STAGE]]
```

4. Preserve the selector's root-relative POSIX output as the seed list. Do not reroll a selection or replace a seed
   based on its apparent complexity.
5. Apply `LEVEL` and `STAGE` only to seed selection. Search the full production corpus defined by
   `scripts/shuffle_sources.py` when resolving a seed's direct callers and callees. Treat tests as evidence and probe
   models, never as graph nodes to score.

## Build the bounded review set

1. Inventory every function body in each seed file and give each one a stable identity: language/module, qualified name,
   root-relative path, and definition line. Include Python functions, methods, and nested functions; Dea `func` and
   `unsafe func` bodies; C definitions; and C `static` or `inline` header bodies.

2. Record declarations without a body, including Dea `extern func` declarations and C prototypes, as external boundaries
   with score `N/A`. Do not count them as reviewed functions.

3. For each seed function, find direct production callers and direct production callees, then review their bodies once.
   Deduplicate a function reached by several seeds. Do not find callers or callees of a one-hop neighbor. A neighbor
   selected independently as a seed receives its own seed-level expansion.

4. Resolve identities before treating a textual name match as an edge. Keep same-spelling functions in different levels,
   modules, translation units, or lexical scopes separate.

5. Classify every candidate edge as `confirmed direct`, `candidate`, or `unresolved indirect/dynamic`:

   - Parse Python definitions and `ast.Call` expressions, then manually verify same-module names and obvious imports.
     Attribute calls, callbacks, monkeypatching, aliases, and dynamic imports can remain unresolved.
   - Resolve Dea named calls through imports and symbol context. Keep constructors and intrinsics separate from ordinary
     function edges. Record L1 function-pointer calls as unresolved unless their target is proven.
   - Use `rg` only to find C candidates. Manually distinguish definitions, declarations, macros, preprocessor branches,
     aliases, and function-pointer calls before confirming an edge.

Never claim that callers or callees are exhaustive when unresolved edges remain.

## Review and score functions

For every reviewed body, inspect its contract, inputs and boundary values, control flow, error paths, ownership and
resource cleanup, state changes, invariants, and interactions with each confirmed direct edge. Read the relevant
language or runtime documentation whenever it defines the behavior under review.

Assign a calibrated integer score from `0` through `100` and cite the evidence:

| Score | Meaning                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| 100   | No correctness concern found in this bounded review. This is not mathematical proof.     |
| 90-99 | Incomplete evidence, an untested boundary, or another small unresolved concern.          |
| 1-89  | A concrete concern, with lower values reserved for more direct or reproducible failures. |
| 0     | Visibly incorrect or contradicted by an existing or temporary test.                      |

Report unresolved graph evidence separately. It prevents an exhaustive call-graph claim, but does not by itself lower a
function score. Lower a score for incomplete graph evidence only when it leaves that function's contract or behavior
unverified, and state that causal link in the rationale.

After reviewing every seed and one-hop body, list all scores below `100` in ascending order. Include the function
identity, score, and concise reason.

Keep the review and scoring focused on correctness. During the same white-box inspection, record an evidence-backed
secondary observation only when it indicates a possible performance issue, vulnerability, serious readability or
maintainability issue, or another non-correctness risk that merits focused investigation. Do not expand the bounded call
graph or launch a separate audit solely to search for these issues. Do not lower a correctness score for a secondary
observation unless it also creates a correctness concern. If it does, report it in both relevant findings tables and
explain the correctness impact. Exclude routine style preferences, unsupported speculation, and minor nits.

## Write and run temporary probes

1. Write and run one or more focused falsification probes for every sub-100 function. One probe may cover multiple
   functions only when its assertions and report mapping identify each covered function. Existing focused tests may
   supplement the evidence, but never replace the required temporary probe.

2. Create probe source snippets, C harnesses, binaries, and output under a newly created system temporary directory.
   Allow canonical focused runners to create their normal ignored build/cache artifacts in the worktree. Keep a failed
   repro directory and report its path; remove successful temporary material when practical.

3. Reuse the narrowest existing route when possible:

   | Source area                                    | Preferred route                                                                                                                                             |
   | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | L0 Stage 1 Python or the Stage 2 trace checker | From `l0/`, run direct focused pytest with existing fixtures or a temporary probe.                                                                          |
   | L0 Stage 2 or shared L0                        | From `l0/`, run focused `make test-stage2 TESTS=...`; add `test-stage2-trace` for ownership or memory concerns.                                             |
   | L1 Stage 1, shared L1, or L1 runtime           | From `l1/`, run focused `make test-stage1 TESTS=...`; add `test-stage1-trace` for ownership or memory concerns, or use a temporary L1 program or C harness. |
   | Future L1 Stage 2 implementation               | Report an unsupported execution harness until that compiler and test workflow exist.                                                                        |

4. Use controlled inputs only. Do not probe arbitrary filesystem locations, network behavior, or process launching. Run
   focused workflows sequentially when they share bootstrap or build outputs.

5. Do not run `clean` or full `test-all` for this review. Do not auto-fix code, persist a test, commit, or push. Request
   separate authority before adding a durable regression test or changing production behavior.

6. Treat a passing probe as evidence that the tested case was not disproved, not proof of correctness. Treat a failure
   as a reproducible counterexample. If no safe or supported probe can run, report that limitation plainly instead of
   inventing a passing result.

## Deliver the review

Report all of the following:

- selector command, scope, and selected root-relative paths;
- every reviewed function's identity, role (`seed`, `caller`, and/or `callee`), score, and white-box evidence;
- confirmed, candidate, and unresolved direct-edge evidence for each seed;
- the ascending sub-100 suspect list;
- every temporary probe's covered functions, path, exact command, result, and failure-repro location when applicable;
- existing tests used as evidence; and
- unresolved edges, unsupported harnesses, and other limits on the conclusion.

As the final step, end the response with these two separate tables:

1. A correctness-defects table containing every confirmed or candidate correctness defect found anywhere in the review.
   Include status (`confirmed` or `candidate`), affected function and location, defect, evidence and impact, and
   possible remediation. Do not treat an evidence gap by itself as a defect. If no correctness defect was found, include
   a single `None found` row.
2. A further-investigation table containing every material secondary observation recorded during white-box inspection.
   Include category, affected function and location, observation and evidence, why it merits investigation, and a
   suggested next investigation. Keep this table separate from correctness defects. If no such observation was found,
   include a single `None found` row.

Possible remediation and investigation steps are report content only. Do not write bug-fix plans, issues, or any other
documents unless the user explicitly asks for them. Keep the worktree unchanged except for normal ignored build/cache
artifacts. A review request does not authorize a tracked test, a code change, a commit, or any remote action.
