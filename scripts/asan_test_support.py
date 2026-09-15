# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Shared AddressSanitizer capability detection for Dea test harnesses."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Sequence


ASAN_COMPILE_TIMEOUT_SECONDS = 60
ASAN_BUILD_TIMEOUT_SECONDS = 180
ASAN_RUN_TIMEOUT_SECONDS = 20


class AsanUnavailableError(RuntimeError):
    """An explicitly requested ASan compiler is unavailable."""


class AsanTimeoutError(RuntimeError):
    """An ASan compile or execution command exceeded its deadline."""


@dataclass(frozen=True)
class AsanToolchain:
    """One compiler and the flags required for a working ASan runtime."""

    compiler: str
    compile_flags: tuple[str, ...]
    link_flags: tuple[str, ...]
    mode: str


_DEFAULT_TOOLCHAIN_FLAGS = (
    ("default", ("-fsanitize=address",), ("-fsanitize=address",)),
    (
        "non-PIE compatibility",
        ("-fsanitize=address", "-fno-pie"),
        ("-fsanitize=address", "-fno-pie", "-no-pie"),
    ),
)


def run_asan_command(
    command: Sequence[str | os.PathLike[str]],
    *,
    phase: str,
    timeout_seconds: int,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one ASan-related command with captured output and a deadline.

    Args:
        command: Command words to execute.
        phase: Human-readable operation name for timeout diagnostics.
        timeout_seconds: Maximum execution time in seconds.
        cwd: Optional working directory.
        env: Optional process environment.

    Returns:
        The completed subprocess result.

    Raises:
        AsanTimeoutError: The command did not complete before its deadline.
        OSError: The executable could not be launched.
    """

    words = [os.fspath(word) for word in command]
    try:
        return subprocess.run(
            words,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise AsanTimeoutError(
            f"{phase} timed out after {timeout_seconds}s: {shlex.join(words)}"
        ) from error


def _output_detail(completed: subprocess.CompletedProcess[str]) -> str:
    """Return concise output for one unsuccessful capability command."""

    return completed.stderr.strip() or completed.stdout.strip() or "no output"


def _compiler_candidates(
    explicit_compiler: str,
    configured_compilers: Sequence[str],
    fallback_compilers: Sequence[str],
) -> tuple[list[str], bool, str]:
    """Return candidates plus request strictness and selection source."""

    explicit = explicit_compiler.strip()
    if explicit:
        return [explicit], True, "explicit ASan request"

    configured = next((candidate.strip() for candidate in configured_compilers if candidate.strip()), "")
    if configured:
        return [configured], False, "configured C compiler"

    return [candidate for candidate in fallback_compilers if candidate], False, "local discovery"


def detect_asan_toolchain(
    *,
    explicit_compiler: str,
    configured_compilers: Sequence[str],
    fallback_compilers: Sequence[str],
    work_dir: Path,
    label: str,
    cwd: Path | None = None,
    compile_timeout_seconds: int = ASAN_COMPILE_TIMEOUT_SECONDS,
    run_timeout_seconds: int = ASAN_RUN_TIMEOUT_SECONDS,
) -> AsanToolchain | None:
    """Return a working same-compiler ASan configuration when available.

    An explicitly requested sanitizer compiler is mandatory. An ordinary
    configured compiler supplies an optional ASan capability and is never
    replaced by another compiler. Conventional compiler-name discovery is
    retained only when neither kind of compiler was configured.

    Args:
        explicit_compiler: Compiler requested through a level ASan variable.
        configured_compilers: Ordinary level compiler selections in priority order.
        fallback_compilers: Conventional compiler names for local discovery.
        work_dir: Directory for the empty support source and executable.
        label: Harness label used in diagnostics.
        cwd: Optional working directory for probe subprocesses.
        compile_timeout_seconds: Empty-probe compile deadline.
        run_timeout_seconds: Empty-probe execution deadline.

    Returns:
        A working ASan toolchain, or ``None`` for optional unavailability.

    Raises:
        AsanUnavailableError: An explicit ASan request cannot be satisfied.
    """

    candidates, required, source = _compiler_candidates(
        explicit_compiler, configured_compilers, fallback_compilers
    )
    support_source = work_dir / "asan-support.c"
    support_executable = work_dir / ("asan-support.exe" if os.name == "nt" else "asan-support")
    support_source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    diagnostics: list[str] = []
    seen_compilers: set[str] = set()

    for candidate in candidates:
        compiler = shutil.which(candidate)
        if compiler is None:
            diagnostics.append(f"{candidate}: compiler not found")
            continue
        compiler_key = str(Path(compiler).resolve())
        if compiler_key in seen_compilers:
            continue
        seen_compilers.add(compiler_key)

        for mode, compile_flags, link_flags in _DEFAULT_TOOLCHAIN_FLAGS:
            try:
                compiled = run_asan_command(
                    [compiler, *link_flags, str(support_source), "-o", str(support_executable)],
                    phase=f"{label} {mode} capability compile",
                    timeout_seconds=compile_timeout_seconds,
                    cwd=cwd,
                )
            except (AsanTimeoutError, OSError) as error:
                diagnostics.append(f"{compiler} ({mode}): {error}")
                continue
            if compiled.returncode != 0:
                diagnostics.append(
                    f"{compiler} ({mode}) compile exited {compiled.returncode}: "
                    f"{_output_detail(compiled)}"
                )
                continue

            support_env = os.environ.copy()
            support_env["ASAN_OPTIONS"] = "detect_leaks=0"
            try:
                executed = run_asan_command(
                    [str(support_executable)],
                    phase=f"{label} {mode} capability execution",
                    timeout_seconds=run_timeout_seconds,
                    cwd=cwd,
                    env=support_env,
                )
            except (AsanTimeoutError, OSError) as error:
                diagnostics.append(f"{compiler} ({mode}): {error}")
                continue
            if executed.returncode != 0:
                diagnostics.append(
                    f"{compiler} ({mode}) runtime exited {executed.returncode}: "
                    f"{_output_detail(executed)}"
                )
                continue

            if mode != "default":
                print(f"{label}: using {compiler} with {mode} flags")
            return AsanToolchain(compiler, compile_flags, link_flags, mode)

    detail = " | ".join(diagnostics) if diagnostics else "no compiler candidates"
    message = f"ASan unavailable from {source}: {detail}"
    if required:
        raise AsanUnavailableError(f"{label}: {message}")
    print(f"{label}: SKIP ASan: {message}")
    return None
