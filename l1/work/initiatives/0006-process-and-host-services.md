# L1 Initiative 0006 - Process and Host Services

- Version: 2026-10-29
- Status: Active
- Kind: Initiative
- Open plans:
  - `l1/work/plans/features/2026-08-30-secure-os-entropy-noref.md`
  - `l1/work/plans/features/2026-08-30-secure-temporary-files-and-directories-noref.md`
  - `l1/work/plans/features/2026-08-30-process-spawning-and-anonymous-pipes-noref.md`
- Closed plans:
  - `l1/work/plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md`

## Summary

This initiative adds the host services needed by compiler drivers and build tools: secure OS entropy, race-free
temporary objects, shell-free process spawning with anonymous pipes, and time primitives for sleep, deadlines, and
timeouts. Public `std.*` modules remain typed and portable; `sys.*` modules and the C runtime contain POSIX and Win32
differences.

This initiative executes under the [L1 roadmap] and consumes the shared error and endpoint contracts from
[Initiative 0005].

## Stdlib-first delivery and compiler follow-up

Define complete public L1 host-service contracts and use existing compiler-private C helpers/tests as reference material
for implementation and platform edge cases. Private argument carriers, temporary-parent policy, fixed probe limits, and
coarse errors do not become the stdlib contract. Relevant child plans inventory those references before implementation.

L2 can later consume L1 stdlib through separately scoped migration work and remove superseded private helpers. Preserve
canonical L1's L0 bootstrap boundary. Compiler migration/removal and shared-private-code extraction are not completion
requirements for this initiative or its stdlib plans.

## Current baseline

- `std.system::system` runs one shell command string but does not model a child process or argument vector.
- L1 has no pipe endpoints, wait status, child standard-stream redirection, or termination API.
- `std.rand` is a pseudorandom generator and is not a secure entropy source.
- There is no race-free temporary-file or temporary-directory API.
- `std.time` uses `long` seconds and normalized `int` nanoseconds. Checked calendar conversion, monotonic sleep,
  deadlines, structured errors, and explicit interruption/resumption are implemented.

## Decisions and invariants

1. `std.process` is shell-free by default and passes arguments as an argument vector.
2. `std.pipe` owns anonymous byte-pipe endpoints separately; broken-pipe behavior is reported as an error and must not
   terminate the process through `SIGPIPE`.
3. `SpawnOptions` controls arguments, environment replacement or overrides, working directory, and standard streams.
4. Native handles are non-inherited by default; only explicitly selected child endpoints cross the spawn boundary.
5. `std.entropy` is distinct from repeatable `std.rand` and is backed by the operating system.
6. Temporary objects are created exclusively and race-free; name-then-check construction is forbidden.
7. General wall, monotonic, and duration second fields use `long`; normalized nanoseconds remain `int`.
8. Deadline helpers use monotonic time, and timeout results remain distinguishable from operation failures.

## Phases and stdlib tiers

### Phase 0 - Secure entropy (Stdlib Tier 2)

Add `fill` and `random_bytes` backed by supported OS entropy facilities, with no deterministic fallback.

Spawned plan: [secure OS entropy].

### Phase 1 - Temporary objects (Stdlib Tier 2)

Add exclusive temporary files and directories plus cleanup helpers over the filesystem and entropy foundations. Specify
explicit/default parent selection, owned private directories, and observable primary/cleanup failures.

Spawned plan: [secure temporary objects].

### Phase 2 - Process spawning and pipes (Stdlib Tier 2)

Add anonymous pipe endpoints, child spawning, wait and try-wait, exit status, termination, and explicit standard-stream
routing. Add executable lookup and current-executable discovery. Concurrent in-memory capture is deferred to L2;
acceptance captures output to temporary files.

Spawned plan: [process spawning and anonymous pipes].

### Phase 3 - Sleep, deadlines, and timeouts (Stdlib Tier 3)

Completed: general time seconds use `long`; `sleep`, `sleep_until`, `deadline_after`, and `remaining` use monotonic
deadlines with checked arithmetic, structured failures, and caller-controlled interruption/resumption. Native macOS
Intel and Linux `test-ci` gates passed, including generated L1 traces; native Windows/macOS ARM validation remains
unverified locally.

Spawned plan: [time width, sleep, and deadlines].

## Dependencies

- OS errors, byte buffers, and file handles come from [Initiative 0005].
- Temporary-object work depends on the filesystem mutation and secure-entropy plans.

## Non-goals

- shell parsing in the primary process API
- pseudo-terminal support, job control, or daemonization
- named local IPC, shared memory, or an event loop
- cryptographic algorithms beyond obtaining host entropy
- calendaring or timezone-database management
- process-wide signal-handler APIs

## ADR Impact

- Decision: Define shell-free process spawning, separately owned anonymous pipe endpoints, explicit standard-stream
  routing, executable discovery, and non-inherited native handles by default.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Process construction and endpoint inheritance are durable portability, security, and ownership contracts.
- Decision: Separate secure operating-system entropy from deterministic pseudorandom generation.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: Security-sensitive consumers must fail explicitly when host entropy is unavailable and must never receive
    a deterministic fallback silently.
- Decision: Use `long` seconds for general time values and monotonic time for deadlines.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0050-wide-time-and-monotonic-deadlines.md`
  - Rationale: Wide seconds and monotonic deadline semantics are implemented and recorded in the accepted time ADR.
- Decision: Expose sleep interruption with the original deadline and leave restart policy to callers.
  - Scope: L1
  - Disposition: Covered by ADR
  - ADR: `l1/docs/decisions/0051-explicit-sleep-interruption-and-restart.md`
  - Rationale: The completed sleep contract preserves deadline budgets, captured errors, and explicit retry policy.

## References

[initiative 0005]: 0005-filesystem-and-stream-io.md
[l1 roadmap]: ../../docs/roadmap.md
[process spawning and anonymous pipes]: ../plans/features/2026-08-30-process-spawning-and-anonymous-pipes-noref.md
[secure os entropy]: ../plans/features/2026-08-30-secure-os-entropy-noref.md
[secure temporary objects]: ../plans/features/2026-08-30-secure-temporary-files-and-directories-noref.md
[time width, sleep, and deadlines]: ../plans/features/closed/2026-08-30-time-width-sleep-and-deadlines-noref.md
