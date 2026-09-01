# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""AddressSanitizer observability for checked-runtime quarantine payloads."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def _asan_compilers() -> list[str]:
    """Return distinct GNU-compatible compiler candidates for ASan probes."""

    candidates = [
        os.environ.get("L0_ASAN_CC", "").strip(),
        os.environ.get("L0_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = shutil.which(candidate)
        if path is None:
            continue
        name = Path(path).name.lower().removesuffix(".exe")
        if "gcc" not in name and "clang" not in name and name != "cc":
            continue
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key)
            resolved.append(path)
    return resolved


def _compile_asan_probe(
    c_code: str,
    runtime_dir: Path,
    work_dir: Path,
    quarantine_count: int,
) -> tuple[Path, str] | None:
    """Compile one generated probe with the first ASan-capable compiler."""

    executable_suffix = ".exe" if os.name == "nt" else ""
    source = work_dir / f"quarantine-{quarantine_count}.c"
    executable = work_dir / f"quarantine-{quarantine_count}{executable_suffix}"
    support_source = work_dir / "asan-support.c"
    support_executable = work_dir / f"asan-support{executable_suffix}"
    source.write_text(c_code, encoding="utf-8")
    support_source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    unsupported: list[str] = []
    failures: list[str] = []

    for compiler in _asan_compilers():
        support = subprocess.run(
            [compiler, "-fsanitize=address", str(support_source), "-o", str(support_executable)],
            capture_output=True,
            text=True,
            check=False,
        )
        if support.returncode != 0:
            unsupported.append(f"{compiler}: {support.stderr.strip()}")
            continue
        support_env = os.environ.copy()
        support_env["ASAN_OPTIONS"] = "detect_leaks=0"
        try:
            support_run = subprocess.run(
                [str(support_executable)],
                capture_output=True,
                text=True,
                env=support_env,
                check=False,
            )
        except OSError as error:
            unsupported.append(f"{compiler}: ASan runtime did not launch: {error}")
            continue
        if support_run.returncode != 0:
            detail = support_run.stderr.strip() or support_run.stdout.strip()
            unsupported.append(
                f"{compiler}: ASan runtime exited {support_run.returncode}: {detail}"
            )
            continue
        command = [
            compiler,
            "-std=c99",
            "-O0",
            "-g",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            f"-D_RT_QUARANTINE_MAX_COUNT={quarantine_count}",
            "-I",
            str(runtime_dir),
            str(source),
            "-o",
            str(executable),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            return executable, compiler
        failures.append(f"{compiler}: {completed.stderr.strip()}")

    if failures:
        pytest.fail("ASan quarantine probe did not compile: " + " | ".join(failures))
    if unsupported:
        pytest.skip("no ASan-capable C compiler: " + " | ".join(unsupported))
    pytest.skip("no GNU-compatible C compiler is available for the ASan probe")


@pytest.mark.parametrize(
    ("quarantine_count", "expected_error"),
    [(4096, "use-after-poison"), (0, "heap-use-after-free")],
)
def test_checked_quarantine_preserves_asan_lifetime_observability(
    codegen_single,
    runtime_dir: Path,
    tmp_path: Path,
    quarantine_count: int,
    expected_error: str,
) -> None:
    """Retained and immediately evicted payloads remain inaccessible to ASan."""

    c_code, diagnostics = codegen_single(
        "quarantine_asan",
        """
        module quarantine_asan;

        import sys.memory;

        extern func asan_stale_read(ptr: void*) -> int;

        func main() -> int {
            let raw: void* = rt_alloc(8) as void*;
            rt_memset(raw, 90, 8);
            rt_free(raw);
            return asan_stale_read(raw);
        }
        """,
    )
    assert c_code is not None, diagnostics
    c_code += "\nl0_int asan_stale_read(void *ptr) {\n"
    c_code += "    return (l0_int)(*(volatile l0_byte *)ptr);\n"
    c_code += "}\n"

    compiled = _compile_asan_probe(c_code, runtime_dir, tmp_path, quarantine_count)
    assert compiled is not None
    executable, _compiler = compiled
    run_env = os.environ.copy()
    run_env["ASAN_OPTIONS"] = "abort_on_error=1:detect_leaks=0:halt_on_error=1"
    completed = subprocess.run(
        [str(executable)],
        capture_output=True,
        text=True,
        env=run_env,
        check=False,
    )

    assert completed.returncode != 0
    assert expected_error in completed.stderr
