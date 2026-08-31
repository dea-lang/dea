# Feature Plan

## Add blocking IP networking

- Date: 2026-08-30
- Status: Draft
- Title: Add blocking IPv4 and IPv6 TCP, UDP, and DNS APIs
- Kind: Feature
- Severity: Medium
- Priority: 3
- Stage: L1
- Parent Initiative: `l1/work/initiatives/0007-blocking-networking.md`
- Subsystem: Stdlib / runtime / networking
- Modules:
  - `l1/compiler/shared/l1/stdlib/std/net.l1`
  - `l1/compiler/shared/l1/stdlib/std/os.l1`
  - `l1/compiler/shared/l1/stdlib/std/stream.l1`
  - `l1/compiler/shared/l1/stdlib/sys/net.l1`
  - `l1/compiler/shared/runtime/include/dea_rt.h`
  - `l1/compiler/shared/runtime/src/dea_rt_net.c`
  - `l1/compiler/shared/runtime/dea_rt.symbols`
  - `l1/compiler/shared/runtime/dea_rt_traced.symbols`
  - `l1/docs/reference/standard-library.md`
  - `l1/docs/reference/design-decisions.md`
- Test modules:
  - `l1/compiler/stage1_l0/tests/net_runtime_test.l0`
  - `l1/compiler/stage1_l0/tests/analysis_trace_test.l0`
- Related:
  - `l1/work/initiatives/0007-blocking-networking.md`
  - `l1/work/initiatives/0005-filesystem-and-stream-io.md`
  - `l1/work/plans/features/2026-08-30-time-width-sleep-and-deadlines-noref.md`
- Repro: `make -C l1 test-stage1 TESTS="net_runtime_test analysis_trace_test"`

## Summary

Add the first portable networking surface as blocking APIs over typed IPv4/IPv6 addresses, TCP streams/listeners, UDP
sockets, and DNS resolution. This plan deliberately avoids selecting an asynchronous or event-loop model.

## Public Surface

- Types: `IpAddress`, `SocketAddress`, `TcpStream`, `TcpListener`, and `UdpSocket`.
- Addressing: parse, format, port access, and family inspection.
- DNS: `resolve` with multiple ordered candidate addresses.
- TCP: `tcp_connect`, `tcp_listen`, `accept`, `recv`, `send`, `send_all`, `shutdown`, and `close`.
- UDP: `udp_bind`, `recv_from`, `send_to`, and `close`.
- Options: `set_read_timeout`, `set_write_timeout`, `set_no_delay`, and `set_reuse_address`.

## Required Semantics

1. IPv4 and IPv6 are first-class and DNS does not assume one family.
2. Graceful TCP peer close is distinct from failure.
3. Partial sends and receives are successful results with `int` counts.
4. Timeout is explicit and distinct from other OS errors.
5. `SIGPIPE` cannot terminate the process after peer close.
6. Socket handles are non-inherited by child processes by default.
7. Close and shutdown have distinct documented behavior.
8. Address resolution preserves native diagnostic information through `OsError`.

## Implementation Phases

1. Add portable address records, parsing/formatting, and runtime representation.
2. Add synchronous DNS resolution with bounded result materialization.
3. Add TCP connect/listen/accept and partial transfer operations.
4. Add UDP bind/send-to/receive-from.
5. Add timeouts and the minimum common socket options.
6. Add stream adapters after endpoint ownership is proven.
7. Add loopback-only deterministic tests, failure injection, trace coverage, and stable docs.

## Non-Goals

- polling, readiness, completion queues, or asynchronous syntax
- Unix-domain sockets, named pipes, shared memory, or other local IPC
- TLS, HTTP, WebSocket, or certificate validation
- multicast, raw sockets, packet capture, or advanced routing in v1
- exposing native descriptors or platform socket structures

## ADR Impact

- Decision: Define blocking typed IPv4/IPv6 TCP, UDP, and DNS APIs with explicit timeout, graceful-close, partial-
  transfer, shutdown, and handle-inheritance behavior.
  - Scope: L1
  - Disposition: New ADR
  - ADR: `l1/docs/decisions/`
  - Rationale: The initial networking contract must be useful and portable without making a premature promise about
    incompatible host asynchronous models.

## Verification Criteria

1. Loopback TCP tests cover connect, accept, bidirectional partial transfer, graceful close, reset, and timeout.
2. UDP tests cover IPv4/IPv6 address round trips and datagram boundaries.
3. Resolver tests preserve multiple candidates and report invalid names separately from unsupported families.
4. Closed-peer writes cannot terminate the test process.
5. Child processes do not inherit unselected sockets.
6. Normal and traced symbol manifests contain the same networking surface.
