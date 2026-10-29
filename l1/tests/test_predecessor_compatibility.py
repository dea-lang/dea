# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""L1-owned checks for the explicitly supported predecessor compatibility surface."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from textwrap import dedent

import pytest

ROOT = Path(__file__).resolve().parents[2]
L0_INCLUDE = ROOT / "l0/compiler/shared/runtime"
L1_INCLUDE = ROOT / "l1/compiler/shared/runtime/include"

# This reviewed subset is explicit: discovering only matching declarations would hide drift.
COMMON_RUNTIME_SIGNATURES = (
    ("dea_int", "rt_strlen", "dea_string"),
    ("dea_byte", "rt_string_get", "dea_string, dea_int"),
    ("dea_byte *", "rt_string_bytes_ptr", "dea_string"),
    ("dea_bool", "rt_string_equals", "dea_string, dea_string"),
    ("dea_int", "rt_string_compare", "dea_string, dea_string"),
    ("dea_string", "rt_string_concat", "dea_string, dea_string"),
    ("dea_string", "rt_string_slice", "dea_string, dea_int, dea_int"),
    ("dea_string", "rt_string_from_byte", "dea_byte"),
    ("dea_string", "rt_string_from_byte_array", "dea_byte *, dea_int"),
    ("void", "rt_string_retain", "dea_string"),
    ("void", "rt_string_release", "dea_string"),
    ("dea_int", "rt_system", "dea_string"),
    ("dea_opt_string", "rt_get_env_var", "dea_string"),
    ("dea_int", "rt_get_argc", "void"),
    ("dea_int", "rt_get_pid", "void"),
    ("dea_string", "rt_get_argv", "dea_int"),
    ("dea_bool", "rt_time_monotonic_supported", "void"),
    ("dea_opt_string", "rt_read_file_all", "dea_string"),
    ("dea_bool", "rt_write_file_all", "dea_string, dea_string"),
    ("dea_bool", "rt_delete_file", "dea_string"),
    ("dea_int", "rt_stdin_read", "dea_byte *, dea_int"),
    ("dea_int", "rt_stdout_write", "dea_byte *, dea_int"),
    ("dea_int", "rt_stderr_write", "dea_byte *, dea_int"),
    ("void", "rt_flush_stdout", "void"),
    ("void", "rt_flush_stderr", "void"),
    ("void", "rt_print", "dea_string"),
    ("void", "rt_print_stderr", "dea_string"),
    ("void", "rt_println", "void"),
    ("void", "rt_println_stderr", "void"),
    ("void", "rt_print_int", "dea_int"),
    ("void", "rt_print_int_stderr", "dea_int"),
    ("void", "rt_print_bool", "dea_bool"),
    ("void", "rt_print_bool_stderr", "dea_bool"),
    ("dea_opt_string", "rt_read_line", "void"),
    ("dea_int", "rt_read_char", "void"),
    ("void", "rt_abort", "dea_string"),
    ("void", "rt_exit", "dea_int"),
    ("void", "rt_srand", "dea_int"),
    ("dea_int", "rt_rand", "dea_int"),
    ("dea_int", "rt_errno", "void"),
    ("void *", "rt_alloc", "dea_int"),
    ("void *", "rt_realloc", "void *, dea_int"),
    ("void", "rt_free", "void *"),
    ("void *", "rt_calloc", "dea_int, dea_int"),
    ("void *", "rt_memset", "void *, dea_int, dea_int"),
    ("void *", "rt_memcpy", "void *, void *, dea_int"),
    ("dea_int", "rt_memcmp", "void *, void *, dea_int"),
    ("void *", "rt_array_element", "void *, dea_int, dea_int"),
    ("void", "rt_register_foreign", "void *, dea_int, dea_bool"),
    ("void", "rt_unregister_foreign", "void *"),
    ("dea_int", "rt_hash_bool", "dea_bool"),
    ("dea_int", "rt_hash_byte", "dea_byte"),
    ("dea_int", "rt_hash_int", "dea_int"),
    ("dea_int", "rt_hash_string", "dea_string"),
    ("dea_int", "rt_hash_data", "void *, dea_int"),
    ("dea_int", "rt_hash_opt_bool", "dea_opt_bool"),
    ("dea_int", "rt_hash_opt_byte", "dea_opt_byte"),
    ("dea_int", "rt_hash_opt_int", "dea_opt_int"),
    ("dea_int", "rt_hash_opt_string", "dea_opt_string"),
    ("dea_int", "rt_hash_ptr", "void *"),
    ("dea_int", "rt_hash_opt_ptr", "void *"),
)

PRIVATE_STDLIB_RUNTIME_SIGNATURES = (
    ("dea_int", "_rt_byte_span_offset", "void *, dea_int, void *"),
    ("dea_bool", "_rt_byte_spans_overlap", "void *, dea_int, void *, dea_int"),
)


@pytest.fixture(scope="module")
def cc() -> str:
    """Resolve the selected L1 native compiler without consulting L0 overrides.

    Returns:
        Absolute path to the selected C compiler.

    Raises:
        RuntimeError: An explicit compiler or every default compiler is unavailable.
    """
    configured = os.environ.get("L1_RUNTIME_CC") or os.environ.get("L1_CC")
    candidates = [configured] if configured else ["clang", "gcc", "cc"]
    for candidate in candidates:
        if resolved := shutil.which(candidate):
            return str(Path(resolved).absolute())
    raise RuntimeError(f"L1 compatibility compiler unavailable: {configured or candidates}")


def _compile_c(cc: str, source: Path, output: Path, include_dir: Path, *, link: bool):
    """Compile one C signature or representation probe.

    Args:
        cc: Selected native compiler executable.
        source: Probe translation unit.
        output: Object or executable destination.
        include_dir: Runtime header directory for the selected level.
        link: Whether to link an executable instead of compiling an object.

    Returns:
        Completed process with captured diagnostics.
    """
    name = Path(cc).name.lower().removesuffix(".exe")
    if name in {"cl", "clang-cl"}:
        command = [cc, str(source), "/std:c11", "/WX", f"/I{include_dir}"]
        command += [f"/Fe:{output}"] if link else ["/c", f"/Fo{output}"]
    else:
        command = [cc, "-std=c99", "-Werror" if name == "tcc" else "-pedantic-errors"]
        command += [] if link else ["-c"]
        command += ["-I", str(include_dir), str(source), "-o", str(output)]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60, check=False)


def _check_signatures(cc, tmp_path, include_dir, signatures):
    """Compile explicit signatures against one level's actual public header.

    Args:
        cc: Selected C compiler.
        tmp_path: Temporary probe directory.
        include_dir: Selected runtime header directory.
        signatures: Reviewed return type, function name, and parameter tuples.
    """
    source = tmp_path / "signatures.c"
    source.write_text('#include "dea_rt.h"\n' + "\n".join(
        f"{result} (*volatile dea_test_{name})({parameters}) = {name};"
        for result, name, parameters in signatures
    ) + "\n", encoding="utf-8")
    compiled = _compile_c(cc, source, tmp_path / "signatures.o", include_dir, link=False)
    assert compiled.returncode == 0, compiled.stderr


@pytest.mark.parametrize("include_dir", [L0_INCLUDE, L1_INCLUDE], ids=["l0", "l1"])
def test_common_runtime_signatures(cc, tmp_path, include_dir):
    """Keep every explicitly portable function type-compatible across levels."""
    _check_signatures(cc, tmp_path, include_dir, COMMON_RUNTIME_SIGNATURES)


@pytest.mark.parametrize("include_dir,seconds", [(L0_INCLUDE, "dea_int"), (L1_INCLUDE, "dea_long")],
                         ids=["l0-int-seconds", "l1-long-seconds"])
def test_level_specific_time_signatures(cc, tmp_path, include_dir, seconds):
    """Preserve the intentional time-parameter width difference."""
    _check_signatures(cc, tmp_path, include_dir, [
        ("dea_opt_int", "rt_time_local_offset_sec", seconds),
        ("dea_opt_bool", "rt_time_local_is_dst", seconds),
    ])


@pytest.mark.parametrize("include_dir", [L0_INCLUDE, L1_INCLUDE], ids=["l0", "l1"])
def test_private_stdlib_runtime_helpers(cc, tmp_path, include_dir):
    """Check inherited helper signatures without making them portable public API."""
    _check_signatures(cc, tmp_path, include_dir, PRIVATE_STDLIB_RUNTIME_SIGNATURES)


def test_common_runtime_layout(cc, tmp_path):
    """Compare actual common-type layouts and storage-free value macros."""
    layout_source = tmp_path / "layout.c"
    layout_source.write_text(
        """\
#include <stddef.h>
#include <stdio.h>
#include "dea_rt.h"

int main(void)
{
    dea_string value = DEA_STRING_CONST("x", 1);
    dea_opt_string empty = DEA_OPT_STRING_EMPTY;
    printf(
        "%zu %zu %zu %zu %zu %zu %zu %zu %zu %zu %zu "
        "%zu %zu %zu %zu %zu %zu %u %d %u\\n",
        sizeof(dea_bool), sizeof(dea_tiny), sizeof(dea_short), sizeof(dea_int),
        sizeof(dea_long), sizeof(dea_byte), sizeof(dea_ushort), sizeof(dea_uint),
        sizeof(dea_ulong), sizeof(dea_float), sizeof(dea_double),
        sizeof(dea_string), offsetof(dea_string, data),
        sizeof(dea_opt_bool), sizeof(dea_opt_byte),
        sizeof(dea_opt_int), sizeof(dea_opt_string),
        (unsigned int)value.kind, (int)value.data.s_str.len,
        (unsigned int)empty.has_value
    );
    return 0;
}
""",
        encoding="utf-8",
    )
    layouts: dict[str, str] = {}
    for label, include_dir in (("l0", L0_INCLUDE), ("l1", L1_INCLUDE)):
        executable = tmp_path / (f"layout_{label}.exe" if os.name == "nt" else f"layout_{label}")
        compiled = _compile_c(cc, layout_source, executable, include_dir, link=True)
        assert compiled.returncode == 0, compiled.stderr
        executed = subprocess.run(
            [str(executable)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        assert executed.returncode == 0, executed.stderr
        layouts[label] = executed.stdout

    assert layouts["l0"] == layouts["l1"]


def _l0_checker_path() -> Path:
    """Return the predecessor trace checker used as the compatibility baseline."""
    return ROOT / "l0/compiler/stage2_l0/scripts/check_trace_log.py"


def _l1_checker_path() -> Path:
    """Return the L1 trace checker being validated."""
    return ROOT / "l1/compiler/scripts/check_trace_log.py"


@pytest.mark.parametrize(
    "log_text",
    [
        """
        unrelated diagnostic
        [l0][mem] payload-without-op ptr=0x1
        [l0][mem] op=new_alloc bytes=16 ptr=0x1 action=ok loc="main.l0":4
        [l0][mem] op=drop ptr=0x1 action=free loc="main.l0":5
        """,
        """
        [l0][mem] op=drop ptr=0x2 action=free
        [l0][arc] op=release kind=heap ptr=0x3 rc_before=x rc_after=y action=free
        """,
        """
        [l0][mem] op=new_alloc bytes=8 ptr=0x4 action=ok
        [l0][mem] op=drop ptr=0x4 action=free
        [l0][mem] op=new_alloc bytes=32 ptr=0x4 action=ok
        [l0][mem] op=drop ptr=0x4 action=free
        [l0][mem] op=alloc_string len=2 ptr=0x5 loc="reuse.l0":7
        [l0][mem] op=free_string ptr=0x5 action=free loc="reuse.l0":8
        """,
    ],
)
def test_l0_and_l1_trace_checkers_report_identical_results(tmp_path, log_text):
    """Preserve the supported predecessor trace format in the L1 checker."""
    log_path = tmp_path / "shared-trace.stderr.log"
    log_path.write_text(dedent(log_text), encoding="utf-8")
    args = [str(log_path), "--triage", "--max-details", "3"]

    l0_proc = subprocess.run(
        [sys.executable, str(_l0_checker_path()), *args],
        capture_output=True,
        text=True,
    )
    l1_proc = subprocess.run(
        [sys.executable, str(_l1_checker_path()), *args],
        capture_output=True,
        text=True,
    )

    assert l0_proc.returncode == l1_proc.returncode
    assert l0_proc.stdout == l1_proc.stdout
    assert l0_proc.stderr == l1_proc.stderr
