#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for the compiled L1 runtime trace flush policy."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_SOURCES = [
    "dea_rt_panic.c",
    "dea_rt_sys.c",
    "dea_rt_math.c",
    "dea_rt_rand.c",
    "dea_rt_string.c",
    "dea_rt_alloc.c",
    "dea_rt_io.c",
    "dea_rt_hash.c",
    "dea_rt_time.c",
]

HARNESS_SOURCE = r"""
#include "dea_rt.h"
#include "dea_rt_trace.c"

static int run_probe(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "policy";

    if (strcmp(mode, "preinit") == 0) {
        _RT_TRACE_MEM("op=preinit ptr=%p", (void*)0x1);
        _rt_init_args(argc, argv);
        printf("%d\n", _rt_trace_flush_each_event);
        return 0;
    }

    _rt_init_args(argc, argv);
    if (strcmp(mode, "policy") == 0) {
        printf("%d\n", _rt_trace_flush_each_event);
        return 0;
    }
    if (strcmp(mode, "system") == 0 || strcmp(mode, "flush") == 0) {
#if defined(_WIN32)
        char cmd_bytes[] = "echo child-stderr 1>&2";
#else
        char cmd_bytes[] = "printf 'child-stderr\\n' >&2";
#endif
        dea_string cmd = DEA_STRING_CONST(cmd_bytes, (dea_int)(sizeof(cmd_bytes) - 1));
        _RT_TRACE_MEM("op=before-child ptr=%p", (void*)0x1);
        if (strcmp(mode, "flush") == 0) {
            rt_flush_stderr();
            return system(cmd_bytes);
        }
        return (int)rt_system(cmd);
    }
    if (strcmp(mode, "panic") == 0) {
        _RT_TRACE_MEM("op=before-panic ptr=%p", (void*)0x1);
        _rt_panic("trace panic probe");
    }
    if (strcmp(mode, "exit") == 0) {
        _RT_TRACE_MEM("op=before-exit ptr=%p", (void*)0x1);
        rt_exit(0);
    }
    if (strcmp(mode, "events") == 0) {
        int i;
        for (i = 0; i < 4096; ++i) {
            _RT_TRACE_MEM("op=probe index=%d ptr=%p", i, (void*)(uintptr_t)(i + 1));
        }
        return 0;
    }

    _RT_TRACE_MEM("op=before-return ptr=%p", (void*)0x1);
    return 0;
}

int main(int argc, char **argv) {
    return run_probe(argc, argv);
}
"""


def runtime_c_compiler() -> str:
    """Return a GNU-compatible compiler for the runtime probe."""

    for candidate in (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
    ):
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise AssertionError("runtime trace policy test requires a C compiler")


def build_probe(work_dir: Path) -> Path:
    """Build and return the compiled trace policy probe."""

    source_path = work_dir / "runtime_trace_policy_probe.c"
    executable = work_dir / ("runtime_trace_policy_probe.exe" if os.name == "nt" else "runtime_trace_policy_probe")
    source_path.write_text(HARNESS_SOURCE, encoding="utf-8")
    command = [
        runtime_c_compiler(),
        "-std=c99",
        "-DDEA_TRACE_ARC",
        "-DDEA_TRACE_MEMORY",
        f"-I{RUNTIME_ROOT / 'include'}",
        f"-I{RUNTIME_ROOT / 'internal'}",
        f"-I{RUNTIME_ROOT / 'src'}",
        str(source_path),
        *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm",
        "-o",
        str(executable),
    ]
    completed = subprocess.run(command, cwd=L1_ROOT, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(f"runtime trace policy probe compilation failed:\n{completed.stderr}")
    return executable


def run_probe(executable: Path, mode: str, policy: str | None) -> subprocess.CompletedProcess[str]:
    """Run one probe mode with the requested trace policy."""

    env = os.environ.copy()
    if policy is None:
        env.pop("DEA_TRACE_FLUSH", None)
    else:
        env["DEA_TRACE_FLUSH"] = policy
    return subprocess.run(
        [str(executable), mode],
        cwd=L1_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="l1_runtime_trace_policy.") as tmp:
        executable = build_probe(Path(tmp))

        for policy, expected in ((None, "1\n"), ("event", "1\n"), ("invalid", "1\n"), ("block", "0\n")):
            completed = run_probe(executable, "policy", policy)
            assert completed.returncode == 0, completed.stderr
            assert completed.stdout == expected

        preinit = run_probe(executable, "preinit", "block")
        assert preinit.returncode == 0, preinit.stderr
        assert preinit.stdout == "1\n"
        assert preinit.stderr.startswith("[l0][mem] op=preinit ptr=")

        for mode in ("system", "flush"):
            ordered = run_probe(executable, mode, "block")
            assert ordered.returncode == 0, ordered.stderr
            lines = ordered.stderr.splitlines()
            assert lines[0].startswith("[l0][mem] op=before-child ptr=")
            assert lines[1].strip() == "child-stderr"

        panic = run_probe(executable, "panic", "block")
        assert panic.returncode != 0
        panic_lines = panic.stderr.splitlines()
        assert panic_lines[0].startswith("[l0][mem] op=before-panic ptr=")
        assert panic_lines[1] == "Software Failure: trace panic probe"

        for mode in ("return", "exit"):
            exited = run_probe(executable, mode, "block")
            assert exited.returncode == 0, exited.stderr
            assert exited.stderr.startswith(f"[l0][mem] op=before-{mode} ptr=")

        event_started = time.perf_counter()
        event_output = run_probe(executable, "events", "event")
        event_seconds = time.perf_counter() - event_started
        block_started = time.perf_counter()
        block_output = run_probe(executable, "events", "block")
        block_seconds = time.perf_counter() - block_started
        assert event_output.returncode == 0 and block_output.returncode == 0
        assert event_output.stderr == block_output.stderr
        assert len(block_output.stderr.splitlines()) == 4096

    speedup = event_seconds / block_seconds if block_seconds > 0 else float("inf")
    print(
        "runtime_trace_policy_test: PASS: "
        f"events=4096 event_s={event_seconds:.6f} block_s={block_seconds:.6f} speedup={speedup:.2f}x"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
