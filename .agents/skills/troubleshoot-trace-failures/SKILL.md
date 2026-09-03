---
name: troubleshoot-trace-failures
description: Diagnose Dea ARC and memory trace failures, fix ownership bugs, and validate against the subtree ownership rules.
---

### Troubleshoot tracing errors and leaks

Use this skill when Dea trace output reports leaks, retain/release imbalances, object lifetime bugs, or other ARC/memory
trace failures in `l0/` or `l1/`.

## Scope

This skill is for ownership-sensitive debugging and fixes in:

- `l0/compiler/stage2_l0/**`
- `l1/compiler/stage1_l0/**`
- shared runtime and stdlib paths used by those compilers
- trace runner scripts and trace-focused regression tests

Typical triggers:

- `run_trace_tests.py` reports `leaked_object_ptrs` or `leaked_string_ptrs`
- `check_trace_log.py --triage` reports imbalance errors
- a minimal traced repro leaks even though the normal test passes
- an early return, cleanup path, or raw-memory container helper looks ownership-unsafe

## Repo-specific workflow

1. Read `AGENTS.md` first. Then read the subtree guide:
   - `l0/AGENTS.md` for L0 Stage 2 work
   - `l1/AGENTS.md` for L1 Stage 1 work
2. Read the ownership reference that governs the target subtree:
   - `l0/docs/reference/ownership.md` for L0 work
   - `l1/docs/reference/ownership.md` for L1 work
3. Treat the ownership reference as normative. If wording diverges from implementation, treat the mismatch as a bug and
   use the current subtree's implementation plus the documented ownership contract to drive the fix.
4. Reproduce the failure with the narrowest useful traced command first:

```bash
# L0
cd l0
make test-stage2-trace TESTS="lexer_test"
../.venv/bin/python compiler/stage2_l0/scripts/run_test_trace.py lexer_test
../.venv/bin/python compiler/stage2_l0/scripts/check_trace_log.py /path/to/stderr.log --triage

# L1
cd l1
make test-stage1-trace TESTS="lexer_test"
../.venv/bin/python compiler/stage1_l0/scripts/run_test_trace.py lexer_test
../.venv/bin/python compiler/stage1_l0/scripts/check_trace_log.py /path/to/stderr.log --triage
```

5. If the suite case is noisy, reduce it to a minimal `.l0` reproducer that exercises the exact ownership path.
6. Map the leak or trace error to one of the common ownership failure modes:
   - early return skips cleanup of temporary vectors or builders
   - ownership moves but the old slot still gets released
   - raw-memory removal/zeroing happens before releasing owned strings
   - container helpers violate their documented ownership contract
   - success paths transfer ownership but do not null or otherwise disarm the local owner
7. Fix the root cause, not just the current repro. Prefer existing ownership patterns from the subtree and the ownership
   docs over ad hoc retain/release patches.
8. Add or update a regression test that hits the exact traced failure mode. If the normal suite does not exercise the
   leak path, add a small focused test module so the trace suite covers it directly.
9. Re-run the narrow traced repro, then the relevant subtree trace target, then the related normal tests.

## Ownership rules to enforce

- Ordinary `string` assignment is compiler-balanced. Do not add manual retain/release around normal assignment paths.
- Raw-memory and container internals must release owned strings before zeroing or removing storage.
- Byte-copy moves transfer ownership with the bytes; do not release the moved-from slot again.
- Temporary allocations must have deterministic cleanup on all error paths.
- For temporary owners that may transfer successfully, prefer the documented ownership pattern:

```dea
let result: T? = null;
with (let tmp = create()) {
    ...
    result = tmp;
    return result;
}
cleanup {
    if (result == null) {
        free(tmp);
    }
}
```

- For simple temporary cleanup with no ownership transfer, the baseline pattern is:

```dea
with (let x = create() => free(x))
```

## L0-specific notes

- Use `l0/docs/reference/ownership.md` as the main oracle.
- Final validation should normally include:

```bash
cd l0
make test-stage2
make test-stage2-trace
```

- If the bug is in shared runtime or stdlib ownership, check whether both Stage 1 and Stage 2 behavior remain aligned.

## L1-specific notes

- Use `l1/docs/reference/ownership.md` first; when L1 behavior is intended to mirror L0 ownership semantics, treat L0's
  documented rule as the upstream contract and L1 drift as a bug.
- Final validation should normally include:

```bash
cd l1
make test-stage1
make test-stage1-trace
```

- L1 trace discovery is `.l0`-only. Python parity tests belong in the normal test runner, not the trace runner.

## Investigation checklist

- failing command reproduced
- trace log triaged with `check_trace_log.py --triage`
- ownership rule identified from the correct subtree reference
- root cause narrowed to a concrete allocation/transfer/cleanup path
- regression test added or updated for the failing path
- relevant normal tests and trace tests rerun

## Deliverable checklist

- failure and ownership rule explained briefly
- fix uses repo ownership patterns instead of speculative retain/release
- traced repro passes with zero leaks
- subtree trace target passes
- related normal tests pass
