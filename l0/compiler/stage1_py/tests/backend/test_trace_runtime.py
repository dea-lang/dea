#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import os

import pytest


POLICY_PROBE = r"""
#define L0_TRACE_MEMORY 1
#define SIPHASH_IMPLEMENTATION 1
#include "l0_runtime.h"

int main(int argc, char **argv) {
    _rt_init_args(argc, argv);
    printf("%d\n", _rt_trace_flush_each_event);
    return 0;
}
"""


@pytest.mark.parametrize(
    ("policy", "expected_event_flush"),
    [(None, 1), ("event", 1), ("invalid", 1), ("block", 0)],
)
def test_trace_runtime_selects_startup_flush_policy(
    tmp_path,
    compile_and_run,
    policy,
    expected_event_flush,
):
    success, stdout, stderr = compile_and_run(
        POLICY_PROBE,
        tmp_path,
        env={"DEA_TRACE_FLUSH": policy},
    )

    assert success, stderr
    assert stdout == f"{expected_event_flush}\n"


def test_trace_runtime_preinit_event_forces_durable_fallback(tmp_path, compile_and_run):
    c_code = r"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {
        _RT_TRACE_MEM("op=preinit ptr=%p", (void*)0x1);
        _rt_init_args(argc, argv);
        printf("%d\n", _rt_trace_flush_each_event);
        return 0;
    }
    """

    success, stdout, stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert success, stderr
    assert stdout == "1\n"
    assert stderr.startswith("[l0][mem] op=preinit ptr=")


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell command to verify child stderr ordering")
def test_trace_runtime_flushes_before_child_stderr(tmp_path, compile_and_run):
    c_code = r"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {
        char cmd_bytes[] = "printf 'child-stderr\\n' >&2";
        l0_string cmd = L0_STRING_CONST(cmd_bytes, (l0_int)(sizeof(cmd_bytes) - 1));
        _rt_init_args(argc, argv);
        _RT_TRACE_MEM("op=alloc_string len=%d ptr=%p", 1, (void*)0x1);
        return (int)rt_system(cmd);
    }
    """

    success, _stdout, stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert success, stderr
    lines = stderr.splitlines()
    assert len(lines) >= 2, stderr
    assert lines[0].startswith("[l0][mem] op=alloc_string len=1 ptr="), stderr
    assert lines[1] == "child-stderr", stderr


@pytest.mark.skipif(os.name == "nt", reason="uses a POSIX shell command to verify explicit flush ordering")
def test_trace_runtime_explicit_stderr_flush_preserves_order(tmp_path, compile_and_run):
    c_code = r"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {
        _rt_init_args(argc, argv);
        _RT_TRACE_MEM("op=before-flush ptr=%p", (void*)0x1);
        rt_flush_stderr();
        return system("printf 'after-flush\\n' >&2");
    }
    """

    success, _stdout, stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert success, stderr
    assert stderr.splitlines()[0].startswith("[l0][mem] op=before-flush ptr=")
    assert stderr.splitlines()[1] == "after-flush"


def test_trace_runtime_panic_flushes_buffered_trace(tmp_path, compile_and_run):
    c_code = r"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {
        _rt_init_args(argc, argv);
        _RT_TRACE_MEM("op=before-panic ptr=%p", (void*)0x1);
        _rt_panic("trace panic probe");
    }
    """

    success, _stdout, stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert not success
    assert stderr.splitlines()[0].startswith("[l0][mem] op=before-panic ptr=")
    assert stderr.splitlines()[1] == "Software Failure: trace panic probe"


@pytest.mark.parametrize("exit_statement", ["return 0;", "rt_exit(0);"])
def test_trace_runtime_process_exit_flushes_buffered_trace(
    tmp_path,
    compile_and_run,
    exit_statement,
):
    c_code = f"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {{
        _rt_init_args(argc, argv);
        _RT_TRACE_MEM("op=before-exit ptr=%p", (void*)0x1);
        {exit_statement}
    }}
    """

    success, _stdout, stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert success, stderr
    assert stderr.startswith("[l0][mem] op=before-exit ptr=")


def test_trace_runtime_block_policy_preserves_synthetic_event_bytes(tmp_path, compile_and_run):
    c_code = r"""
    #define L0_TRACE_MEMORY 1
    #define SIPHASH_IMPLEMENTATION 1
    #include "l0_runtime.h"

    int main(int argc, char **argv) {
        int i;
        _rt_init_args(argc, argv);
        for (i = 0; i < 4096; ++i) {
            _RT_TRACE_MEM("op=probe index=%d ptr=%p", i, (void*)(uintptr_t)(i + 1));
        }
        return 0;
    }
    """

    event_success, _stdout, event_stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "event"},
    )
    block_success, _stdout, block_stderr = compile_and_run(
        c_code,
        tmp_path,
        env={"DEA_TRACE_FLUSH": "block"},
    )

    assert event_success and block_success
    assert event_stderr == block_stderr
    assert len(block_stderr.splitlines()) == 4096
