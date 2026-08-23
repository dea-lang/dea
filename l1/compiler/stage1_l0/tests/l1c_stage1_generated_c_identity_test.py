#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end generated-C identity coverage across every producing CLI mode."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
FIXTURE_ROOT = (
    L1_ROOT
    / "compiler"
    / "stage1_l0"
    / "tests"
    / "fixtures"
    / "separate_compilation"
)
SOURCE_ONLY_ENTRY = "identity.main"
MIXED_ENTRY = "linkset.main"
MIXED_PROVIDER_MODULES = ("linkset.leaf", "linkset.provider")
CODEGEN_SETTINGS = (
    ("default", ()),
    ("no-line-directives", ("--no-line-directives",)),
    ("trace-arc", ("--trace-arc",)),
    ("trace-memory", ("--trace-memory",)),
    ("unchecked", ("--unchecked",)),
    ("check-basic", ("--check-basic",)),
)


class GeneratedCIdentityFailure(RuntimeError):
    """Raised when one generated-C identity assertion fails."""


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible compiler launcher path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def stage1_compiler() -> Path:
    """Return the repo-local L1 Stage 1 compiler."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def real_c_compiler() -> str:
    """Return a non-TinyCC compiler suitable for reusable native objects."""

    for configured in (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    ):
        if configured:
            resolved = shutil.which(configured)
            if resolved is None:
                raise GeneratedCIdentityFailure(
                    f"configured C compiler was not found: {configured}"
                )
            return resolved
    for candidate in ("clang", "gcc", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise GeneratedCIdentityFailure("identity test requires clang, gcc, or cc")


def run(
    args: list[str | Path],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one captured command."""

    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def require_status(
    completed: subprocess.CompletedProcess[str],
    expected: int,
    context: str,
) -> None:
    """Require one exact command status with captured failure context."""

    if completed.returncode != expected:
        raise GeneratedCIdentityFailure(
            f"{context} returned {completed.returncode}, expected {expected}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def write_recording_compiler(root: Path, real_cc: str) -> Path:
    """Write a compiler proxy that records every C input before compilation."""

    bin_dir = root / "recording-compiler"
    bin_dir.mkdir()
    script = bin_dir / ("gcc.py" if os.name == "nt" else "gcc")
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import hashlib
            import json
            import os
            from pathlib import Path
            import subprocess
            import sys

            args = sys.argv[1:]
            log_path = os.environ.get("L1_C_INPUT_LOG", "")
            records = []
            for arg in args:
                if not arg.lower().endswith(".c"):
                    continue
                path = Path(arg)
                if not path.is_file():
                    continue
                data = path.read_bytes()
                records.append({{
                    "path": str(path.resolve()),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                }})
            if log_path and records:
                with Path(log_path).open("a", encoding="utf-8") as stream:
                    for record in records:
                        stream.write(json.dumps(record, sort_keys=True) + "\\n")
            raise SystemExit(subprocess.run([{real_cc!r}, *args], check=False).returncode)
            """
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | 0o111)
    if os.name != "nt":
        return script
    launcher = bin_dir / "gcc.cmd"
    launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n')
    return launcher


def invocation_env(base: dict[str, str], log_path: Path) -> dict[str, str]:
    """Return an invocation environment selecting one fresh recorder log."""

    env = base.copy()
    env["L1_C_INPUT_LOG"] = str(log_path)
    return env


def require_exact_compiler_input(
    log_path: Path,
    relative_path: str,
    expected: bytes,
    context: str,
) -> None:
    """Require the recorder to have seen the exact expected C byte sequence."""

    expected_hash = hashlib.sha256(expected).hexdigest()
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    normalized_suffix = "/" + relative_path.replace("\\", "/")
    matches = [
        record
        for record in records
        if record["path"].replace("\\", "/").endswith(normalized_suffix)
    ]
    if not any(
        record["sha256"] == expected_hash and record["size"] == len(expected)
        for record in matches
    ):
        raise GeneratedCIdentityFailure(
            f"{context} did not pass exact retained bytes for {relative_path} "
            "to the host compiler"
        )


def compiler_args(
    compiler: Path,
    mode: str,
    source_root: Path,
    recorder: Path,
    settings: tuple[str, ...],
    *,
    interface_root: Path | None = None,
) -> list[str | Path]:
    """Return the common prefix for one generated-C-producing invocation."""

    args: list[str | Path] = [
        compiler,
        mode,
        "--project-root",
        source_root,
        "--c-compiler",
        recorder,
        *settings,
    ]
    if interface_root is not None:
        args.extend(("--interface-path", interface_root))
    return args


def generate_module(
    compiler: Path,
    env: dict[str, str],
    source_root: Path,
    output: Path,
    module: str,
    settings: tuple[str, ...],
    *,
    interface_root: Path | None = None,
) -> bytes:
    """Generate one module C file without invoking host tools."""

    args: list[str | Path] = [
        compiler,
        "--gen",
        "--project-root",
        source_root,
        *settings,
    ]
    if interface_root is not None:
        args.extend(("--interface-path", interface_root))
    args.extend(("--output", output, module))
    completed = run(args, cwd=REPO_ROOT, env=env)
    require_status(completed, 0, f"generated-C {module}")
    return output.read_bytes()


def compile_module(
    compiler: Path,
    recorder: Path,
    base_env: dict[str, str],
    source_root: Path,
    artifact_root: Path,
    module: str,
    settings: tuple[str, ...],
    label: str,
    *,
    interface_root: Path | None = None,
) -> tuple[Path, bytes]:
    """Compile one module and return its object path and exact retained C."""

    object_path = artifact_root.joinpath(*module.split(".")).with_suffix(".o")
    log_path = artifact_root / f"{label}.compiler-inputs.jsonl"
    args = compiler_args(
        compiler,
        "--compile",
        source_root,
        recorder,
        settings,
        interface_root=interface_root,
    )
    args.extend(("--keep-c", "--output", object_path, module))
    completed = run(args, cwd=REPO_ROOT, env=invocation_env(base_env, log_path))
    require_status(completed, 0, f"compile-only {module} ({label})")
    c_path = object_path.with_suffix(".c")
    c_bytes = c_path.read_bytes()
    require_exact_compiler_input(
        log_path,
        "/".join(module.split(".")) + ".c",
        c_bytes,
        f"compile-only {module} ({label})",
    )
    return object_path, c_bytes


def build_or_run(
    compiler: Path,
    recorder: Path,
    base_env: dict[str, str],
    mode: str,
    source_root: Path,
    work_root: Path,
    settings: tuple[str, ...],
    label: str,
    entry_module: str,
    *,
    interface_root: Path | None = None,
) -> dict[str, bytes]:
    """Execute build/run keep-C and return the complete retained C tree."""

    work_root.mkdir(parents=True)
    log_path = work_root / f"{label}.compiler-inputs.jsonl"
    args = compiler_args(
        compiler,
        mode,
        source_root,
        recorder,
        settings,
        interface_root=interface_root,
    )
    args.append("--keep-c")
    if mode == "--build":
        executable = work_root / ("program.exe" if os.name == "nt" else "program.out")
        args.extend(("--output", executable))
        retained_root = Path(str(executable) + ".dea-c")
        expected_status = 0
    else:
        retained_root = work_root / f"{entry_module}.dea-c"
        expected_status = 7
    args.append(entry_module)
    completed = run(
        args,
        cwd=work_root,
        env=invocation_env(base_env, log_path),
    )
    require_status(completed, expected_status, f"{mode} ({label})")
    retained = {
        path.relative_to(retained_root).as_posix(): path.read_bytes()
        for path in retained_root.rglob("*.c")
    }
    if "__dea_wrapper.c" not in retained:
        raise GeneratedCIdentityFailure(f"{mode} ({label}) retained no wrapper")
    for relative_path, data in retained.items():
        require_exact_compiler_input(
            log_path, relative_path, data, f"{mode} ({label})"
        )
    return retained


def require_module_identity(
    outputs: dict[str, bytes],
    context: str,
) -> None:
    """Require every named mode to contain one identical module byte sequence."""

    distinct = {value for value in outputs.values()}
    if len(distinct) != 1:
        raise GeneratedCIdentityFailure(
            f"generated C differs across modes for {context}: "
            + ", ".join(outputs)
        )


def run_setting(
    compiler: Path,
    recorder: Path,
    base_env: dict[str, str],
    root: Path,
    label: str,
    settings: tuple[str, ...],
) -> None:
    """Verify source-only and mixed-graph identity for one codegen setting."""

    setting_root = root / label
    source_root = setting_root / "source-only-sources"
    source_path = source_root / "identity" / "main.l1"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "module identity.main;\n\nfunc main() -> int {\n    return 7;\n}\n",
        encoding="utf-8",
    )

    source_gen = generate_module(
        compiler,
        base_env,
        source_root,
        setting_root / "source-gen.c",
        SOURCE_ONLY_ENTRY,
        settings,
    )
    _, source_compile = compile_module(
        compiler,
        recorder,
        base_env,
        source_root,
        setting_root / "source-artifacts",
        SOURCE_ONLY_ENTRY,
        settings,
        "source-main",
    )
    source_build = build_or_run(
        compiler,
        recorder,
        base_env,
        "--build",
        source_root,
        setting_root / "source-build",
        settings,
        "source-build",
        SOURCE_ONLY_ENTRY,
    )
    source_run = build_or_run(
        compiler,
        recorder,
        base_env,
        "--run",
        source_root,
        setting_root / "source-run",
        settings,
        "source-run",
        SOURCE_ONLY_ENTRY,
    )
    require_module_identity(
        {
            "--gen": source_gen,
            "--compile --keep-c": source_compile,
            "--build --keep-c": source_build["identity/main.c"],
            "--run --keep-c": source_run["identity/main.c"],
        },
        f"source-only graph ({label})",
    )
    if source_build["__dea_wrapper.c"] != source_run["__dea_wrapper.c"]:
        raise GeneratedCIdentityFailure(
            f"build/run wrapper bytes differ for source-only graph ({label})"
        )

    provider_artifacts = setting_root / "provider-artifacts"
    for module in MIXED_PROVIDER_MODULES:
        interface_root = provider_artifacts if module != "linkset.leaf" else None
        compile_module(
            compiler,
            recorder,
            base_env,
            FIXTURE_ROOT,
            provider_artifacts,
            module,
            settings,
            f"provider-{module}",
            interface_root=interface_root,
        )

    mixed_sources = setting_root / "mixed-sources"
    (mixed_sources / "linkset").mkdir(parents=True)
    shutil.copyfile(
        FIXTURE_ROOT / "linkset" / "main.l1",
        mixed_sources / "linkset" / "main.l1",
    )
    provider_c_paths = [
        provider_artifacts.joinpath(*module.split(".")).with_suffix(".c")
        for module in MIXED_PROVIDER_MODULES
    ]
    for path in provider_c_paths:
        path.unlink()

    mixed_gen = generate_module(
        compiler,
        base_env,
        mixed_sources,
        setting_root / "mixed-gen.c",
        MIXED_ENTRY,
        settings,
        interface_root=provider_artifacts,
    )
    _, mixed_compile = compile_module(
        compiler,
        recorder,
        base_env,
        mixed_sources,
        setting_root / "mixed-artifacts",
        MIXED_ENTRY,
        settings,
        "mixed-main",
        interface_root=provider_artifacts,
    )
    mixed_build = build_or_run(
        compiler,
        recorder,
        base_env,
        "--build",
        mixed_sources,
        setting_root / "mixed-build",
        settings,
        "mixed-build",
        MIXED_ENTRY,
        interface_root=provider_artifacts,
    )
    mixed_run = build_or_run(
        compiler,
        recorder,
        base_env,
        "--run",
        mixed_sources,
        setting_root / "mixed-run",
        settings,
        "mixed-run",
        MIXED_ENTRY,
        interface_root=provider_artifacts,
    )
    expected_mixed_tree = {"__dea_wrapper.c", "linkset/main.c"}
    if set(mixed_build) != expected_mixed_tree or set(mixed_run) != expected_mixed_tree:
        raise GeneratedCIdentityFailure(
            f"mixed graph regenerated provider C for {label}"
        )
    if any(path.exists() for path in provider_c_paths):
        raise GeneratedCIdentityFailure(
            f"mixed graph recreated an absent provider C file for {label}"
        )
    require_module_identity(
        {
            "--gen": mixed_gen,
            "--compile --keep-c": mixed_compile,
            "--build --keep-c": mixed_build["linkset/main.c"],
            "--run --keep-c": mixed_run["linkset/main.c"],
        },
        f"mixed source/interface graph ({label})",
    )
    if mixed_build["__dea_wrapper.c"] != mixed_run["__dea_wrapper.c"]:
        raise GeneratedCIdentityFailure(
            f"build/run wrapper bytes differ for mixed graph ({label})"
        )


def main() -> int:
    """Run the generated-C identity matrix."""

    compiler = stage1_compiler()
    real_cc = real_c_compiler()
    with tempfile.TemporaryDirectory(prefix="l1_generated_c_identity.") as raw_temp:
        root = Path(raw_temp)
        recorder = write_recording_compiler(root, real_cc)
        temp_parent = root / "temp"
        temp_parent.mkdir(mode=0o700)
        base_env = os.environ.copy()
        base_env["TMPDIR"] = str(temp_parent)
        base_env.pop("TEMP", None)
        base_env.pop("TMP", None)
        for label, settings in CODEGEN_SETTINGS:
            run_setting(
                compiler, recorder, base_env, root, label, settings
            )
        leftovers = sorted(temp_parent.glob(".l1c-*-workspace-*"))
        if leftovers:
            raise GeneratedCIdentityFailure(
                "identity matrix retained workspace(s): "
                + ", ".join(str(path) for path in leftovers)
            )

    print("l1c_stage1_generated_c_identity_test: all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
