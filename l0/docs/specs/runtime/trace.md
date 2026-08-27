# L0 Trace Specification

Version: 2026-08-27

This document specifies the shared trace instrumentation contract for generated C code and runtime behavior in both
Stage 1 and Stage 2.

## 1. Purpose

Trace instrumentation exists to verify ownership and memory code paths at runtime, especially subtle ARC behavior
(`retain`/`release`) and allocation/deallocation flows.

Tracing is opt-in and intended for debugging, validation, and regression analysis.

## 2. User Interface (Shared CLI)

`l0c` exposes trace flags on codegen-producing modes (`--gen`, `--build`, `--run`):

- `-Va` / `--trace-arc`: enable ARC operation tracing.
- `-Vm` / `--trace-memory`: enable memory operation tracing.

Flags are independent and composable.

Examples:

```bash
l0c --gen -Va app.main
l0c --build -Vm app.main
l0c --run -Va -Vm app.main
```

## 3. Generated C Contract

When enabled, generated C emitted by either stage writes preprocessor defines immediately before including
`l0_runtime.h`:

- `#define L0_TRACE_ARC 1`
- `#define L0_TRACE_MEMORY 1`

These defines gate runtime trace code with `#ifdef` so trace logic is fully excluded when flags are off.

Manual C defines passed via `-Co` (for example `-Co "-DL0_TRACE_ARC"`) remain compatible.

## 4. Runtime Output Contract

- Trace output stream: `stderr`.
- Prefixes:
  - ARC: `[l0][arc]`
  - Memory: `[l0][mem]`
- Trace format is line-oriented text, one event per line.

No stdout behavior is changed by tracing.

### 4.1 Trace flush policy

Trace-enabled runtimes select one process-wide stderr flush policy during `_rt_init_args()`, before user module
initialization:

- The default and `DEA_TRACE_FLUSH=event` flush after every complete trace event. This is the durable interactive mode
  and is appropriate for native-crash archaeology.
- `DEA_TRACE_FLUSH=block` installs a fixed 64 KiB stderr buffer and flushes at process boundaries. This is the bulk
  capture mode used by the repository trace runners.
- Missing, empty, or unrecognized values use event flushing. A trace macro invoked before `_rt_init_args()` also keeps
  event flushing for the rest of the process because C stream buffering cannot safely change after I/O begins.

Block mode preserves complete-event formatting and flushes pending trace bytes before `rt_system()` launches a child,
before panic or abort diagnostics, when `rt_flush_stderr()` is called, and through normal C process termination or
`rt_exit()`. This keeps synchronous parent/child stderr ordering while avoiding one operating-system flush per trace
event.

The Stage 2 and L1 Stage 1 trace runners choose block mode unless `DEA_TRACE_FLUSH` is already set. To rerun a bulk
trace capture with event durability, set `DEA_TRACE_FLUSH=event` explicitly.

## 5. Trace Families

### 5.1 ARC (`L0_TRACE_ARC`)

ARC traces include retain/release operations and branch outcomes.

Current ARC instrumentation points:

- `rt_string_retain`
- `rt_string_release` path (`_rt_free_string`)

Typical fields include:

- operation (`op=retain` or `op=release`)
- string kind (`static`/`heap`)
- pointer identity
- reference count transition (`rc_before`/`rc_after`) where applicable
- action (`retain`, `keep`, `free`, `noop-*`, or `panic-*`)
- source location (`loc="file":line`) where available

### 5.2 Memory (`L0_TRACE_MEMORY`)

Memory traces include allocation/free/reallocation/new/drop paths.

Current memory instrumentation points:

- `rt_alloc`
- `rt_realloc`
- `rt_free`
- `rt_calloc`
- `_rt_alloc_string`
- `_rt_realloc_string`
- `_rt_free_string`
- `_rt_alloc_obj`
- generated drop begin/finish helpers

Typical fields include:

- operation name
- size/count arguments
- pointer identities (old/new for realloc)
- action (`ok`, `fail`, `free`, `noop-*`, `panic-*`)
- source location (`loc="file":line`) where available

A rejected generated drop emits exactly one `op=drop ... action=panic-not-found` event before the runtime panic. This
compatibility event covers unregistered, non-base, stale, wrong-provenance, undersized, and misaligned drop failures;
successful drops emit `action=free` before quarantine eviction can release the pointer record.

## 6. Compatibility and Defaults

- Tracing is disabled by default.
- Enabling tracing does not change language semantics; it only emits additional `stderr` logs.
- Existing programs compile and run unchanged without trace flags.
- Successful bulk trace capture streams stdout and stderr directly into artifact files, waits for EOF from inherited
  writers, and analyzes the trace line by line. Runner memory does not scale with the raw trace byte count.

## 7. Non-goals (Current Stage)

- Structured trace output formats (JSON/binary).
- Configurable runtime filtering levels/categories.

## 8. Candidate Future Flags

Potential future `trace-*` families:

- `trace-panic`
- `trace-io`
- `trace-hash`
- `trace-newdrop` (if split from general memory tracing)
