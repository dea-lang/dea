#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Strict triple-bootstrap regression for the Stage 2 compiler artifact."""

from __future__ import annotations

import difflib
import hashlib
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_DIR = SCRIPT_DIR.parent / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from test_runner_common import require_repo_stage2_test_env

REPO_ROOT = SCRIPT_DIR.parent.parent.parent
BUILD_TESTS_DIR = REPO_ROOT / "build" / "tests"


class TripleBootstrapFailure(RuntimeError):
    """Raised when one triple-bootstrap assertion fails."""


def fail(message: str, artifact_dir: Path) -> None:
    """Abort the test and keep artifacts."""

    raise TripleBootstrapFailure(f"{message}\nartifacts={artifact_dir}")


def read_text(path: Path) -> str:
    """Read UTF-8 text with replacement for invalid bytes."""

    return path.read_text(encoding="utf-8", errors="replace")


def read_bytes(path: Path) -> bytes:
    """Read one binary file."""

    return path.read_bytes()


def shell_join(command: list[str]) -> str:
    """Render one command for failure messages."""

    return " ".join(shlex.quote(part) for part in command)


def stage2_wrapper_command(wrapper_path: Path) -> list[str]:
    """Return the command used to invoke one generated Stage 2 wrapper."""

    if os.name == "nt":
        cmd_path = wrapper_path.with_suffix(".cmd")
        if cmd_path.is_file():
            return [str(cmd_path)]
    return [str(wrapper_path)]


def stage2_bootstrap_build_command() -> list[str]:
    """Return the command used to build the repo-local bootstrap Stage 2 artifact."""

    return [sys.executable, str(REPO_ROOT / "scripts" / "build_stage2_l0c.py")]


def first_lines(text: str, limit: int) -> str:
    """Return at most `limit` lines from `text`."""

    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit]) + "\n..."


def format_duration(seconds: float) -> str:
    """Render one wall-clock duration for human-readable progress output."""

    return f"{seconds:.2f}s"


def notice(message: str) -> None:
    """Print one progress line with the test prefix."""

    print(f"l0c_triple_bootstrap_test: {message}", flush=True)


def run_logged(
        name: str,
        command: list[str],
        *,
        env: dict[str, str],
        artifact_dir: Path,
        cwd: Path = REPO_ROOT,
        expected_returncode: int = 0,
) -> tuple[Path, float]:
    """Run one subprocess, capture combined output, and return wall time."""

    log_path = artifact_dir / f"{name}.log"
    start = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.monotonic() - start
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != expected_returncode:
        fail(
            "\n".join(
                [
                    f"{name} failed (rc={completed.returncode})",
                    f"command={shell_join(command)}",
                    f"log={log_path}",
                    first_lines(completed.stdout, 80),
                ]
            ).rstrip(),
            artifact_dir,
        )
    return log_path, elapsed


def resolve_host_c_compiler(env: dict[str, str]) -> str:
    """Resolve the exact host C compiler command used for all self-builds."""

    from_env = env.get("L0_CC", "").strip()
    if from_env:
        return from_env

    for candidate in ("tcc", "gcc", "clang", "cc"):
        if shutil.which(candidate):
            return candidate

    from_cc = env.get("CC", "").strip()
    if from_cc:
        return from_cc

    raise TripleBootstrapFailure("no host C compiler found; set L0_CC or CC")


def deterministic_c_flags(compiler_text: str) -> list[str]:
    """Return deterministic C compiler and linker flags required for native comparison.

    Covers both codegen-level reproducibility (``-frandom-seed``) and
    linker-level non-determinism (UUIDs, ad hoc signatures, build-ids, PE timestamps).
    """

    if uses_tcc(compiler_text):
        return []

    # -frandom-seed makes GCC/Clang internal symbol generation deterministic
    # regardless of ASLR or invocation environment.
    flags: list[str] = ["-frandom-seed=l0c-stage2"]

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

    words = existing.split()
    for flag in extra_flags:
        if flag not in words:
            words.append(flag)
    return " ".join(words)


def compiler_command_words(command_text: str) -> list[str]:
    """Split one compiler command string into argv words."""

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
    cflags = cflags_text.split()
    outputs: list[Path] = []
    with probe_log.open("w", encoding="utf-8") as log_file:
        for output in (probe_a, probe_b):
            command = [*compiler, *cflags, str(probe_source), "-o", str(output)]
            log_file.write(f"$ {shell_join(command)}\n")
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


def short_unified_diff(left: Path, right: Path, artifact_dir: Path) -> str:
    """Write and return a short unified diff for retained-C mismatches."""

    diff_lines = list(
        difflib.unified_diff(
            read_text(left).splitlines(),
            read_text(right).splitlines(),
            fromfile=str(left),
            tofile=str(right),
            n=3,
            lineterm="",
        )
    )
    diff_path = artifact_dir / "retained_c.diff"
    diff_text = "\n".join(diff_lines)
    diff_path.write_text(diff_text, encoding="utf-8")
    if not diff_lines:
        return f"diff={diff_path} (files differ but no text diff was produced)"
    if len(diff_lines) > 80:
        return f"diff={diff_path}\n" + "\n".join(diff_lines[:80]) + "\n..."
    return f"diff={diff_path}\n" + diff_text


def assert_same_bytes(label: str, left: Path, right: Path, artifact_dir: Path, *, include_diff: bool) -> None:
    """Compare two artifacts byte-for-byte and fail with a compact summary."""

    if read_bytes(left) == read_bytes(right):
        return

    lines = [
        f"{label} mismatch",
        artifact_summary(left),
        artifact_summary(right),
    ]
    if include_diff:
        lines.append(short_unified_diff(left, right, artifact_dir))
    fail("\n".join(lines), artifact_dir)


def assert_fallback_version(name: str, compiler_path: Path, *, env: dict[str, str], artifact_dir: Path) -> None:
    """Assert that one raw self-hosted compiler stays on the static fallback `--version` path."""

    version_log, _ = run_logged(
        name,
        [str(compiler_path), "--version"],
        env=env,
        artifact_dir=artifact_dir,
    )
    version_text = read_text(version_log).strip()
    expected = "Dea language / L0 compiler"
    if version_text != expected:
        fail(
            "\n".join(
                [
                    f"expected fallback --version output for {compiler_path}",
                    f"log={version_log}",
                    f"got={version_text!r}",
                ]
            ),
            artifact_dir,
        )


def main() -> int:
    """Program entrypoint."""

    BUILD_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path(tempfile.mkdtemp(prefix="l0_stage2_triple_bootstrap.", dir=BUILD_TESTS_DIR))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    total_start = time.monotonic()

    try:
        _, _, _, repo_env = require_repo_stage2_test_env("l0c_triple_bootstrap_test.py")
        compiler_text = resolve_host_c_compiler(repo_env)
        merged_cflags = merge_cflags(repo_env.get("L0_CFLAGS", ""), deterministic_c_flags(compiler_text))
        notice(f"using host C compiler: {compiler_text}")
        notice(f"using host C flags: {merged_cflags or '(none)'}")
        assert_stable_native_toolchain(compiler_text, merged_cflags, artifact_dir)

        build_env = repo_env.copy()
        build_env["L0_CC"] = compiler_text
        build_env["L0_CFLAGS"] = merged_cflags
        self_build_env = build_env.copy()
        self_build_env["L0_HOME"] = str(REPO_ROOT / "compiler")

        first_dea_build = artifact_dir / "stage1-dea-build"
        first_dea_build_rel = os.path.relpath(first_dea_build, REPO_ROOT)
        stage2_wrapper = first_dea_build / "bin" / "l0c-stage2"
        stage2_native = first_dea_build / "bin" / "l0c-stage2.native"
        stage2_c = first_dea_build / "bin" / "l0c-stage2.c"

        first_build_env = build_env.copy()
        first_build_env["DEA_BUILD_DIR"] = first_dea_build_rel
        first_build_env["KEEP_C"] = "1"
        notice("building compiler 1/3: trusted Stage 1 -> first Stage 2 compiler")
        _, first_build_elapsed = run_logged(
            "first_build",
            stage2_bootstrap_build_command(),
            env=first_build_env,
            artifact_dir=artifact_dir,
        )
        notice(
            f"built compiler 1/3 in {format_duration(first_build_elapsed)}: {stage2_native}"
        )

        if not stage2_wrapper.is_file() or not stage2_native.is_file() or not stage2_c.is_file():
            fail("first build did not produce the expected Stage 2 artifact layout", artifact_dir)

        second_native = artifact_dir / "l0c-stage2-second.native"
        second_c = second_native.with_suffix(".c")
        notice("building compiler 2/3: first Stage 2 compiler -> second self-hosted Stage 2 compiler")
        _, second_build_elapsed = run_logged(
            "second_build",
            [
                *stage2_wrapper_command(stage2_wrapper),
                "--build",
                "--keep-c",
                "-P",
                "compiler/stage2_l0/src",
                "-o",
                str(second_native),
                "l0c",
            ],
            env=self_build_env,
            artifact_dir=artifact_dir,
        )
        notice(
            f"built compiler 2/3 in {format_duration(second_build_elapsed)}: {second_native}"
        )

        if not second_native.is_file() or not second_c.is_file():
            fail("second self-build did not retain both native and C artifacts", artifact_dir)
        assert_fallback_version(
            "second_version",
            second_native,
            env=self_build_env,
            artifact_dir=artifact_dir,
        )

        third_native = artifact_dir / "l0c-stage2-third.native"
        third_c = third_native.with_suffix(".c")
        notice("building compiler 3/3: second self-hosted Stage 2 compiler -> third self-hosted Stage 2 compiler")
        _, third_build_elapsed = run_logged(
            "third_build",
            [
                str(second_native),
                "--build",
                "--keep-c",
                "-P",
                "compiler/stage2_l0/src",
                "-o",
                str(third_native),
                "l0c",
            ],
            env=self_build_env,
            artifact_dir=artifact_dir,
        )
        notice(
            f"built compiler 3/3 in {format_duration(third_build_elapsed)}: {third_native}"
        )

        if not third_native.is_file() or not third_c.is_file():
            fail("third self-build did not retain both native and C artifacts", artifact_dir)
        assert_fallback_version(
            "third_version",
            third_native,
            env=self_build_env,
            artifact_dir=artifact_dir,
        )

        notice("comparing second and third self-built retained C artifacts")
        assert_same_bytes("retained C (compiler 2 vs compiler 3)", second_c, third_c, artifact_dir, include_diff=True)
        if uses_tcc(compiler_text):
            notice("skipping native binary comparison for tcc (no stable binary guarantee)")
        elif sys.platform == "win32":
            notice("skipping native binary comparison on Windows (PE binaries are not reliably deterministic)")
        else:
            native_left = normalized_native_artifact(second_native, artifact_dir)
            native_right = normalized_native_artifact(third_native, artifact_dir)
            notice("comparing stripped second and third self-built native compiler binaries")
            assert_same_bytes(
                "native binary (compiler 2 vs compiler 3)",
                native_left,
                native_right,
                artifact_dir,
                include_diff=False,
            )

        notice("running final smoke check through the third self-built compiler")
        smoke_log, smoke_elapsed = run_logged(
            "third_self_smoke",
            [str(third_native), "--run", "-P", "examples", "hello"],
            env=self_build_env,
            artifact_dir=artifact_dir,
        )
        if "Hello, world! This is Dea/L0." not in read_text(smoke_log):
            fail(f"third self-built compiler smoke check output mismatch: log={smoke_log}", artifact_dir)
        notice(f"final smoke passed in {format_duration(smoke_elapsed)}")

        total_elapsed = time.monotonic() - total_start
        notice(f"PASS (total wall time: {format_duration(total_elapsed)})")
        if keep_artifacts:
            notice(f"artifacts={artifact_dir}")
        return 0
    except RuntimeError as exc:
        keep_artifacts = True
        print(f"l0c_triple_bootstrap_test: FAIL: {exc}")
        return 2
    except TripleBootstrapFailure as exc:
        keep_artifacts = True
        lines = str(exc).splitlines()
        if lines:
            print(f"l0c_triple_bootstrap_test: FAIL: {lines[0]}")
        for line in lines[1:]:
            print(f"l0c_triple_bootstrap_test: {line}")
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
