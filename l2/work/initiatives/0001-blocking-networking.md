# L2 Initiative 0001 - Blocking Networking

- Version: 2026-10-29
- Status: Active
- Kind: Initiative
- Open plans:
  - `l2/work/plans/features/2026-08-30-blocking-ip-networking-noref.md`
- Closed plans: (none)

## Summary

This work is deferred until stable-L1 catch-up and explicit activation of sustained L2 development. It does not gate L1
stabilization.

This initiative promotes networking from deferred direction to a Stdlib Tier 3 roadmap capability. The first portable
surface is deliberately blocking: address resolution, IPv4 and IPv6 addressing, TCP clients and listeners, and UDP
sockets. It does not promise a portable asynchronous model before Dea has selected one.

Typed public APIs live in `std.net`, low-level host bindings in `sys.net`, and POSIX or Win32 differences behind the C
runtime. The initiative executes under the [l2/docs/roadmap.md][l2 roadmap].

## Decisions and invariants

1. Distinct `IpAddress`, `SocketAddress`, `TcpStream`, `TcpListener`, and `UdpSocket` types prevent invalid endpoint
   combinations.
2. DNS resolution returns a portable result with all usable IPv4 and IPv6 candidates.
3. TCP graceful close is distinct from failure; sends and receives may complete partially.
4. Read and write timeouts are explicit operation results.
5. `SIGPIPE` must never terminate an L2 process after a peer close.
6. Socket handles are non-inherited by child processes unless explicitly selected.
7. Socket streams can be adapted into `std.stream` after the endpoint ownership contract is satisfied.

## Phase and stdlib tier

### Phase 1 - Blocking IP networking (Stdlib Tier 3)

Add address parsing and formatting, DNS resolution, TCP connect/listen/accept/send/receive/shutdown, UDP
bind/send-to/receive-from, and common timeout and socket-option controls.

Spawned plan: [l2/work/plans/features/2026-08-30-blocking-ip-networking-noref.md][blocking ip networking].

## Dependencies

- Stable-L1 catch-up supplies OS errors, dynamic bytes, concrete endpoints, and time contracts from L1 Initiatives 0005
  and 0006.
- L2 streams supply adapters after their endpoint ownership gate.
- L1 non-inheritance policy remains the baseline for process and socket handles.

## Non-goals

- asynchronous I/O, polling, or a portable event loop
- Unix-domain sockets, Windows named pipes, or shared-memory IPC
- TLS, HTTP, WebSocket, or DNS protocol implementations
- certificate stores or security policy above the socket layer
- exposing native socket descriptors through `std.net`

## ADR Impact

- Decision: Establish blocking IPv4/IPv6 TCP, UDP, and DNS as the initial portable networking model, with typed
  endpoints and direct operation results.
  - Scope: L2
  - Disposition: New ADR
  - ADR: `l2/docs/decisions/`
  - Rationale: A blocking surface provides useful portable systems capability without prematurely equating readiness-
    based POSIX APIs with completion-based Windows APIs.

## References

[blocking ip networking]: ../plans/features/2026-08-30-blocking-ip-networking-noref.md
[l2 roadmap]: ../../docs/roadmap.md
