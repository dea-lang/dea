#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Runtime coverage for L1 I/O helpers and filesystem boundaries."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def runtime_c_compiler() -> str:
    """Return the GNU-compatible compiler used for runtime boundary probes."""
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
        if resolved is None:
            continue
        name = Path(resolved).name.lower().removesuffix(".exe")
        if "gcc" in name or ("clang" in name and "clang-cl" not in name) or name in {"cc", "tcc"}:
            return resolved
    raise AssertionError("io runtime test requires a C compiler")


def require_filesystem_close_failure_contract() -> None:
    """Compile a runtime with injected close outcomes and verify both payload paths."""
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        probe_path = json.dumps((work_dir / "close-failure-probe.txt").as_posix())
        harness = work_dir / "filesystem_close_probe.c"
        executable = work_dir / ("filesystem_close_probe.exe" if os.name == "nt" else "filesystem_close_probe")
        harness.write_text(
            f"""
#include "dea_rt.h"

static int close_should_fail = 0;
static int close_calls = 0;
static int stat_calls = 0;
static int remove_calls = 0;

int injected_close(FILE *stream) {{
    int actual = fclose(stream);
    close_calls += 1;
    if (actual != 0) return actual;
    return close_should_fail ? EOF : 0;
}}

#if defined(_WIN32)
int injected_stat(const char *path, struct _stat64 *buffer) {{
#else
int injected_stat(const char *path, struct stat *buffer) {{
#endif
    (void)path;
    (void)buffer;
    stat_calls += 1;
    return -1;
}}

int injected_remove(const char *path) {{
    (void)path;
    remove_calls += 1;
    return -1;
}}

int main(void) {{
    char path_bytes[] = {probe_path};
    char payload_bytes[] = "x";
    dea_string path = DEA_STRING_CONST(path_bytes, (dea_int)(sizeof(path_bytes) - 1));
    dea_string payload = DEA_STRING_CONST(payload_bytes, 1);
    dea_string empty = DEA_STRING_EMPTY;

    struct __deaM3sys2rtS10RtFileInfo info = rt_file_info(empty);
    if (info.exists || info.size.has_value) return 2;
    if (rt_delete_file(empty)) return 3;
    if (stat_calls != 0 || remove_calls != 0) return 9;

    close_should_fail = 0;
    if (!rt_write_file_all(path, empty)) return 4;
    close_should_fail = 1;
    if (rt_write_file_all(path, empty)) return 5;
    close_should_fail = 0;
    if (!rt_write_file_all(path, payload)) return 6;
    close_should_fail = 1;
    if (rt_write_file_all(path, payload)) return 7;
    if (close_calls != 4) return 8;

    remove(path_bytes);
    return 0;
}}
""",
            encoding="utf-8",
        )
        compiler = runtime_c_compiler()
        command = [
            compiler,
            "-std=c99",
            "-DDEA_RUNTIME_FCLOSE=injected_close",
            "-DDEA_RUNTIME_FILE_INFO_STAT=injected_stat",
            "-DDEA_RUNTIME_REMOVE=injected_remove",
            f"-I{RUNTIME_ROOT / 'include'}",
            f"-I{RUNTIME_ROOT / 'internal'}",
            str(harness),
            *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
            "-lm",
            "-o",
            str(executable),
        ]
        compiled = subprocess.run(command, cwd=L1_ROOT, capture_output=True, text=True, check=False)
        if compiled.returncode != 0:
            raise AssertionError(f"filesystem close probe compilation failed:\n{compiled.stderr}")
        completed = subprocess.run([str(executable)], cwd=L1_ROOT, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise AssertionError(
                f"filesystem close probe exited with {completed.returncode}:\n{completed.stderr}"
            )


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def compiler_path() -> Path:
    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def run_mode(mode: str, stdin_text: str = "", extra_flags: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(compiler_path()),
            "--project-root",
            "compiler/stage1_l0/tests/fixtures/io_runtime",
            *(extra_flags or []),
            "--run",
            "io_numeric_main",
            "--",
            mode,
        ],
        cwd=L1_ROOT,
        input=stdin_text,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require_run(
    mode: str,
    stdin_text: str,
    stdout: str,
    stderr: str = "",
    extra_flags: list[str] | None = None,
) -> None:
    completed = run_mode(mode, stdin_text, extra_flags)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{mode} exited with {completed.returncode}")
    assert completed.stdout == stdout, f"{mode} stdout mismatch: {completed.stdout!r}"
    assert completed.stderr == stderr, f"{mode} stderr mismatch: {completed.stderr!r}"


def require_failure(mode: str, stdin_text: str, stderr_needle: str) -> None:
    completed = run_mode(mode, stdin_text)
    if completed.returncode == 0:
        raise AssertionError(f"{mode} unexpectedly succeeded")
    assert stderr_needle in completed.stderr, f"{mode} stderr mismatch: {completed.stderr!r}"


def main() -> int:
    require_filesystem_close_failure_contract()
    require_run("delim", ",alpha beta;gamma", "\nalpha\nbeta\ngamma\n")
    require_run(
        "reads",
        "  -42 4294967295\n-9223372036854775808 18446744073709551615 bad",
        "-42\n4294967295\n-9223372036854775808\n18446744073709551615\ninvalid\n",
    )
    require_run("prints", "", "1 -2 3 1.5 0.25\n", "4 -5 6 2.5 0.125\n")
    require_run(
        "text",
        "",
        (
            "4294967295\n"
            "ffffffff\n"
            "-9223372036854775808\n"
            "-8000000000000000\n"
            "18446744073709551615\n"
            "ffffffffffffffff\n"
            "4294967295\n"
            "-9223372036854775808\n"
            "18446744073709551615\n"
            "invalids\n"
        ),
    )
    require_run("bytes", ("A" * 200) + "\n", "bytes-ok\n")
    # A valid program must behave identically with the unchecked runtime archive.
    require_run("bytes", ("A" * 200) + "\n", "bytes-ok\n", extra_flags=["--unchecked"])
    require_failure("bytes-write-static", "", "read-only pointer write")
    require_failure("bytes-write-field", "", "read-only pointer write")
    require_failure("bytes-write-heap", ("A" * 200) + "\n", "read-only pointer write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
