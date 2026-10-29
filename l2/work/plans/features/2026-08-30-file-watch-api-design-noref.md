# Feature Plan

## Design a portable file-watch API

- Date: 2026-08-30
- Last reviewed: 2026-10-29
- Status: Draft
- Title: Define a portable file-watch event and lifetime contract
- Kind: Feature
- Priority: Low
- Stdlib Tier: 4
- Subsystem: Stdlib / runtime / filesystem watching
- Modules:
  - `l2/docs/specs/stdlib/file-watching.md`
  - `l2/compiler/shared/l2/stdlib/std/watch.l2`
  - `l2/compiler/shared/l2/stdlib/sys/watch.l2`
- Test modules:
  - `l2/compiler/tests/file_watch_runtime_test.l1`
- Related:
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l2/docs/roadmap.md`
- Repro: `rg -n "File-watch|File watch|watch" l2/docs l2/work`

## Summary

This work is deferred until stable-L1 catch-up and explicit activation of sustained L2 development. It does not gate L1
stabilization.

Resolve the Stdlib Tier 4 file-watch item already present in the roadmap before opening implementation work. The plan
compares supported host facilities and either defines a useful common event model or records why the capability should
remain platform-specific or deferred.

## Questions to Resolve

1. File versus directory watches and recursive watch behavior.
2. Event kinds for create, remove, modify, rename, metadata change, and unknown change.
3. Rename pairing and identity when a host reports only one side.
4. Event coalescing, duplicate events, queue overflow, and mandatory rescan signals.
5. Path representation and whether events are relative to a watched root.
6. Watch-handle ownership, close, cancellation, and interaction with blocking waits.
7. Whether the first surface is blocking-only or depends on a future event model.

## Approach

1. Inventory inotify, kqueue/FSEvents, ReadDirectoryChangesW, and any supported fallback constraints.
2. Derive the smallest semantics that can be tested consistently on all supported hosts.
3. Write the candidate contract in `l2/docs/specs/stdlib/file-watching.md`.
4. Prototype only enough runtime behavior to falsify the candidate semantics.
5. End with a decision to open bounded implementation plans, retain deferral, or expose only lower-level platform-
   specific bindings.

## Non-Goals

- implementing the complete watcher API in this design plan
- promising exactly-once events
- polling/event-loop design for sockets and processes
- file locking, memory mapping, or local IPC
- treating a watch stream as a replacement for filesystem rescan after overflow

## ADR Impact

- Decision: Define a portable file-watch event, overflow, rename, path, and lifetime model or reject a common safe
  surface.
  - Scope: L2
  - Disposition: Pending
  - ADR: None
  - Rationale: Supported host APIs expose materially different event and overflow semantics, and the roadmap item lacks
    an accepted portability contract.

## Verification Criteria

1. The design matrix covers every supported L2 host family.
2. The contract states which event distinctions are guaranteed and which are hints.
3. Overflow always produces an explicit rescan requirement.
4. Rename behavior remains correct when pairing is unavailable.
5. The conclusion names the exact follow-up plans or records a justified deferral.
