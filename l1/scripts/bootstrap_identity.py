# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Native identity policy ported from the L0 strict triple-bootstrap regression.

Keep the platform exceptions, stripping, UUID and signature rules aligned with
l0/compiler/stage2_l0/tests/l0c_triple_bootstrap_test.py.
"""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


class TripleBootstrapFailure(RuntimeError):
    """Raised when native identity cannot be established."""


def fail(message: str, artifact_dir: Path) -> None:
    """Fail with the retained evidence location."""
    raise TripleBootstrapFailure(f"{message}\nartifacts={artifact_dir}")


def read_bytes(path: Path) -> bytes:
    """Read a native artifact without transforming its bytes."""
    return path.read_bytes()


def notice(message: str) -> None:
    """Report native identity decisions."""
    print(f"l1-triple-bootstrap: {message}", flush=True)


def deterministic_c_flags(compiler_text: str) -> list[str]:
    """Return deterministic C compiler and linker flags required for native comparison.

    Covers both codegen-level reproducibility (``-frandom-seed``) and
    linker-level non-determinism (UUIDs, ad hoc signatures, build-ids, PE timestamps).
    """

    if uses_tcc(compiler_text):
        return []

    # -frandom-seed makes GCC/Clang internal symbol generation deterministic
    # regardless of ASLR or invocation environment.
    flags: list[str] = ["-frandom-seed=l1c-stage2"]

    if sys.platform == "darwin":
        if platform.machine() != "arm64":
            flags.extend(["-Wl,-no_uuid", "-Wl,-no_adhoc_codesign"])
    elif sys.platform.startswith("linux"):
        flags.append("-Wl,--build-id=none")
    elif sys.platform == "win32":
        # --no-insert-timestamp prevents ld from writing the current time into the
        # COFF PE header TimeDateStamp field, which strip -s does not remove.
        flags.extend(["-Wl,--build-id=none", "-Wl,--no-insert-timestamp"])
    else:
        raise TripleBootstrapFailure(f"unsupported host platform for native identity check: {sys.platform}")

    return flags


def merge_cflags(existing: str, extra_flags: list[str]) -> str:
    """Preserve user flags while appending deterministic C/linker flags once."""

    words = shlex.split(existing)
    additions = []
    for flag in extra_flags:
        if flag not in words:
            words.append(flag)
            additions.append(flag)
    return " ".join(part for part in (existing, shlex.join(additions)) if part)


def compiler_command_words(command_text: str) -> list[str]:
    """Split one compiler command string into argv words."""

    # The Stage 2 builder supplies a resolved executable, including native Windows
    # paths and paths with spaces. Preserve it before interpreting shell syntax.
    if Path(command_text).is_file():
        return [command_text]
    words = shlex.split(command_text)
    if not words:
        raise TripleBootstrapFailure("resolved host C compiler command is empty")
    return words


def recognized_compiler_family(command_text: str) -> str | None:
    """Return one recognized compiler family from the resolved command, if any."""

    for word in compiler_command_words(command_text):
        name = Path(word).name
        lower_name = name.lower()
        if lower_name.endswith(".exe"):
            lower_name = lower_name[:-4]

        if lower_name == "tcc":
            return "tcc"
        if re.fullmatch(r"gcc-[0-9]+", lower_name):
            return "gcc"
        if lower_name == "gcc":
            return "gcc"
        if re.fullmatch(r"clang-[0-9]+", lower_name):
            return "clang"
        if lower_name == "clang":
            return "clang"
    return None


def uses_tcc(command_text: str) -> bool:
    """Return whether the resolved compiler command ultimately invokes `tcc`."""

    return recognized_compiler_family(command_text) == "tcc"


def assert_stable_native_toolchain(compiler_text: str, cflags_text: str, artifact_dir: Path) -> None:
    """Fail early when the selected compiler still emits unstable binaries."""

    family = recognized_compiler_family(compiler_text)
    if family == "tcc":
        notice("skipping native stability probe for known tcc compiler (no stable binary guarantee)")
        return
    if family in {"gcc", "clang"}:
        notice(f"skipping native stability probe for known {family} compiler")
        return

    probe_source = artifact_dir / "native_stability_probe.c"
    probe_a = artifact_dir / "native_stability_probe_a"
    probe_b = artifact_dir / "native_stability_probe_b"
    probe_log = artifact_dir / "native_stability_probe.log"
    probe_source.write_text(
        "int main(void) {\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    compiler = compiler_command_words(compiler_text)
    cflags = shlex.split(cflags_text)
    outputs: list[Path] = []
    with probe_log.open("w", encoding="utf-8") as log_file:
        for output in (probe_a, probe_b):
            command = [*compiler, *cflags, str(probe_source), "-o", str(output)]
            log_file.write(f"$ {shlex.join(command)}\n")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            log_file.write(completed.stdout)
            if completed.returncode != 0:
                fail(
                    "\n".join(
                        [
                            "deterministic native toolchain probe failed",
                            f"compiler={compiler_text}",
                            f"cflags={cflags_text}",
                            f"log={probe_log}",
                        ]
                    ),
                    artifact_dir,
                )
            outputs.append(output)

    if read_bytes(outputs[0]) != read_bytes(outputs[1]):
        fail(
            "\n".join(
                [
                    "host toolchain does not produce stable binaries even with deterministic linker flags",
                    f"compiler={compiler_text}",
                    f"cflags={cflags_text}",
                    f"log={probe_log}",
                ]
            ),
            artifact_dir,
        )


def sha256_hex(path: Path) -> str:
    """Return the SHA-256 digest for one file."""

    return hashlib.sha256(read_bytes(path)).hexdigest()


def artifact_summary(path: Path) -> str:
    """Return a compact summary for one artifact."""

    return f"{path} size={path.stat().st_size} sha256={sha256_hex(path)[:16]}"


def resolve_strip_command() -> list[str] | None:
    """Return one available strip command for native artifact normalization."""

    for candidate in ("strip", "llvm-strip"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    return None


def _run_strip(strip_command: list[str], path: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """Run strip to produce a normalized copy of one native artifact.

    On macOS, ``strip`` does not support ``-o``; we copy-then-strip-in-place.
    GNU/MinGW ``strip`` supports ``-o`` for direct output.
    """

    if sys.platform == "darwin":
        shutil.copy2(path, output)
        return subprocess.run(
            [*strip_command, "-x", str(output)],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    return subprocess.run(
        [*strip_command, "-s", "-o", str(output), str(path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _remove_darwin_code_signature(path: Path) -> None:
    """Remove one Darwin code signature when present."""

    codesign = shutil.which("codesign")
    if codesign is None:
        return

    completed = subprocess.run(
        [codesign, "--remove-signature", str(path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise TripleBootstrapFailure(
            "\n".join(
                [
                    "failed to remove Darwin code signature from normalized artifact",
                    f"path={path}",
                    completed.stdout.rstrip(),
                ]
            ).rstrip()
        )


def neutralize_darwin_uuid(path: Path) -> None:
    """Zero the ``LC_UUID`` payload in one thin Mach-O comparison copy."""

    data = bytearray(read_bytes(path))
    magic_layouts = {
        b"\xce\xfa\xed\xfe": ("<", 28),
        b"\xcf\xfa\xed\xfe": ("<", 32),
        b"\xfe\xed\xfa\xce": (">", 28),
        b"\xfe\xed\xfa\xcf": (">", 32),
    }
    layout = magic_layouts.get(bytes(data[:4]))
    if layout is None:
        raise TripleBootstrapFailure(f"normalized Darwin artifact is not a thin Mach-O binary: {path}")

    byte_order, header_size = layout
    if len(data) < header_size:
        raise TripleBootstrapFailure(f"truncated Mach-O header in normalized Darwin artifact: {path}")

    command_count = struct.unpack_from(f"{byte_order}I", data, 16)[0]
    command_bytes = struct.unpack_from(f"{byte_order}I", data, 20)[0]
    command_offset = header_size
    command_end = command_offset + command_bytes
    if command_end > len(data):
        raise TripleBootstrapFailure(f"truncated Mach-O load-command table in normalized Darwin artifact: {path}")

    uuid_count = 0
    for _ in range(command_count):
        if command_offset + 8 > command_end:
            raise TripleBootstrapFailure(f"truncated Mach-O load command in normalized Darwin artifact: {path}")
        command, command_size = struct.unpack_from(f"{byte_order}II", data, command_offset)
        if command_size < 8 or command_offset + command_size > command_end:
            raise TripleBootstrapFailure(f"invalid Mach-O load command size in normalized Darwin artifact: {path}")
        if command == 0x1B:  # LC_UUID
            if command_size != 24:
                raise TripleBootstrapFailure(f"invalid Mach-O LC_UUID size in normalized Darwin artifact: {path}")
            uuid_count += 1
            if uuid_count > 1:
                raise TripleBootstrapFailure(f"duplicate Mach-O LC_UUID command in normalized Darwin artifact: {path}")
            data[command_offset + 8:command_offset + 24] = b"\0" * 16
        command_offset += command_size

    if command_offset != command_end:
        raise TripleBootstrapFailure(f"inconsistent Mach-O load-command table in normalized Darwin artifact: {path}")

    path.write_bytes(data)


def normalized_native_artifact(path: Path, artifact_dir: Path) -> Path:
    """Return one normalized native artifact path for byte-identity comparison.

    Strips debug symbols and local symbols on all platforms to remove
    non-deterministic metadata (DWARF paths, code signatures, section timestamps).
    """

    strip_command = resolve_strip_command()
    normalized = artifact_dir / f"{path.name}.stripped"

    if sys.platform == "darwin":
        if strip_command is None:
            raise TripleBootstrapFailure("no strip tool found for native identity comparison")
        shutil.copy2(path, normalized)
        completed = subprocess.run(
            [*strip_command, "-x", str(normalized)],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise TripleBootstrapFailure(
                "\n".join(
                    [
                        f"failed to normalize native artifact with {' '.join(strip_command)}",
                        f"path={path}",
                        completed.stdout.rstrip(),
                    ]
                ).rstrip()
            )
        _remove_darwin_code_signature(normalized)
        neutralize_darwin_uuid(normalized)
        return normalized

    if sys.platform == "win32":
        # MinGW-w64 strip removes debug sections; --no-insert-timestamp handles the COFF header timestamp.
        if strip_command is None:
            return path
        completed = _run_strip(strip_command, path, normalized)
        if completed.returncode != 0:
            # If strip fails on Windows, fall back to raw comparison.
            return path
        return normalized

    # Linux: strip is required for deterministic comparison.
    if strip_command is None:
        raise TripleBootstrapFailure("no strip tool found for native identity comparison")

    completed = _run_strip(strip_command, path, normalized)
    if completed.returncode != 0:
        raise TripleBootstrapFailure(
            "\n".join(
                [
                    f"failed to normalize native artifact with {' '.join(strip_command)}",
                    f"path={path}",
                    completed.stdout.rstrip(),
                ]
            ).rstrip()
        )
    return normalized
