#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for L1 multi-CU build/run orchestration."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
SEPARATE_FIXTURES = (
    L1_ROOT
    / "compiler"
    / "stage1_l0"
    / "tests"
    / "fixtures"
    / "separate_compilation"
)
DRIVER_FIXTURES = (
    L1_ROOT / "compiler" / "stage1_l0" / "tests" / "fixtures" / "driver"
)


class MultiCuFailure(RuntimeError):
    """Raised when one orchestration assertion fails."""


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
    """Return a non-TinyCC compiler suitable for reusable foreign objects."""

    for configured in (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    ):
        if configured:
            resolved = shutil.which(configured)
            if resolved is None:
                raise MultiCuFailure(f"configured C compiler was not found: {configured}")
            return resolved
    for candidate in ("clang", "gcc", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise MultiCuFailure("multi-CU test requires clang, gcc, or cc")


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
        raise MultiCuFailure(
            f"{context} returned {completed.returncode}, expected {expected}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def compiler_command(
    compiler: Path,
    cc: str,
    mode: str,
    root: Path,
    module: str,
    *extra: str | Path,
) -> list[str | Path]:
    """Return one build/run compiler command."""

    return [
        compiler,
        mode,
        "--project-root",
        root,
        "--c-compiler",
        cc,
        *extra,
        module,
    ]


def compile_module(
    compiler: Path,
    cc: str,
    env: dict[str, str],
    source_root: Path,
    artifact_root: Path,
    module: str,
    *,
    interface_root: Path | None = None,
    keep_c: bool = False,
) -> Path:
    """Compile one module to its canonical artifact-root object."""

    object_path = artifact_root.joinpath(*module.split(".")).with_suffix(".o")
    args: list[str | Path] = [
        compiler,
        "--compile",
        "--project-root",
        source_root,
        "--c-compiler",
        cc,
        "--output",
        object_path,
    ]
    if interface_root is not None:
        args.extend(["--interface-path", interface_root])
    if keep_c:
        args.append("--keep-c")
    args.append(module)
    completed = run(args, cwd=REPO_ROOT, env=env)
    require_status(completed, 0, f"compile-only {module}")
    return object_path


def compile_foreign(cc: str, source: Path, output: Path, env: dict[str, str]) -> None:
    """Compile one caller-asserted foreign object."""

    output.parent.mkdir(parents=True, exist_ok=True)
    completed = run([cc, "-c", source, "-o", output], cwd=REPO_ROOT, env=env)
    require_status(completed, 0, f"foreign compile {source.name}")


def write_module(root: Path, module: str, body: str) -> None:
    """Write one temporary canonical L1 source module."""

    path = root.joinpath(*module.split(".")).with_suffix(".l1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def require_no_workspaces(temp_parent: Path, context: str) -> None:
    """Require complete invocation-workspace cleanup."""

    leftovers = sorted(temp_parent.glob(".l1c-*-workspace-*"))
    if leftovers:
        raise MultiCuFailure(
            f"{context} retained workspace(s): "
            + ", ".join(str(path) for path in leftovers)
        )


def write_launch_failure_compiler(root: Path, real_cc: str) -> Path:
    """Write a compiler that emits a regular non-executable final output."""

    bin_dir = root / "launch-failure-bin"
    bin_dir.mkdir()
    script = bin_dir / ("gcc.py" if os.name == "nt" else "gcc")
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            import os
            from pathlib import Path
            import subprocess
            import sys

            args = sys.argv[1:]
            if "-c" in args or any(arg.lower() == "/c" for arg in args):
                raise SystemExit(subprocess.run([{real_cc!r}, *args], check=False).returncode)
            output = ""
            for index, arg in enumerate(args):
                if arg == "-o" and index + 1 < len(args):
                    output = args[index + 1]
                elif arg.lower().startswith("/fe:"):
                    output = arg[4:]
            if not output:
                raise SystemExit(91)
            path = Path(output)
            path.write_bytes(b"not executable")
            if os.name != "nt":
                path.chmod(0o600)
            raise SystemExit(0)
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


def write_source_mutating_compiler(
    root: Path,
    real_cc: str,
    consumer_source: Path,
) -> Path:
    """Write a compiler proxy that invalidates a downstream source mid-fan-out."""

    bin_dir = root / "source-mutating-bin"
    bin_dir.mkdir()
    script = bin_dir / ("gcc.py" if os.name == "nt" else "gcc")
    invalid_consumer = textwrap.dedent(
        """
        module boundary.consumer;
        import boundary.provider;
        func value() -> int { return missing_symbol(); }
        """
    )
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            from pathlib import Path
            import subprocess
            import sys

            args = sys.argv[1:]
            completed = subprocess.run([{real_cc!r}, *args], check=False)
            compiling = "-c" in args or any(arg.lower() == "/c" for arg in args)
            if completed.returncode == 0 and compiling:
                inputs = [Path(arg) for arg in args if arg.endswith(".c")]
                if any(path.name == "provider.c" for path in inputs):
                    Path({str(consumer_source)!r}).write_text(
                        {invalid_consumer!r}, encoding="utf-8"
                    )
            raise SystemExit(completed.returncode)
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


def write_invocation_marker_compiler(root: Path, marker: Path) -> Path:
    """Write a compiler proxy that records any unexpected invocation."""

    bin_dir = root / "preflight-marker-bin"
    bin_dir.mkdir()
    script = bin_dir / ("gcc.py" if os.name == "nt" else "gcc")
    script.write_text(
        textwrap.dedent(
            f"""\
            #!{sys.executable}
            from pathlib import Path

            Path({str(marker)!r}).write_text("invoked\\n", encoding="ascii")
            raise SystemExit(97)
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


def main() -> int:
    """Run the multi-CU build/run regression matrix."""

    compiler = stage1_compiler()
    cc = real_c_compiler()
    with tempfile.TemporaryDirectory(prefix="l1_multi_cu_test.") as raw_temp:
        root = Path(raw_temp)
        temp_parent = root / "temp"
        temp_parent.mkdir(mode=0o700)
        env = os.environ.copy()
        env["TMPDIR"] = str(temp_parent)
        env.pop("TEMP", None)
        env.pop("TMP", None)

        if os.name == "nt":
            invocation_marker = root / "unsafe-link-arg-invoked-compiler"
            marker_cc = write_invocation_marker_compiler(root, invocation_marker)
            unsafe_output = root / "unsafe-link-arg.exe"
            unsafe_link_arg = run(
                compiler_command(
                    compiler,
                    str(marker_cc),
                    "--build",
                    SEPARATE_FIXTURES,
                    "linkset.main",
                    "--link-arg=%TEMP%",
                    "--output",
                    unsafe_output,
                ),
                cwd=root,
                env=env,
            )
            require_status(
                unsafe_link_arg,
                1,
                "unsafe Windows build/run link argument preflight",
            )
            if "[L1C-2106]" not in unsafe_link_arg.stderr:
                raise MultiCuFailure(
                    "unsafe Windows build/run link argument lacks L1C-2106"
                )
            if invocation_marker.exists():
                raise MultiCuFailure(
                    "unsafe Windows build/run link argument invoked the host compiler"
                )
            if unsafe_output.exists():
                raise MultiCuFailure(
                    "unsafe Windows build/run link argument published an executable"
                )
            require_no_workspaces(
                temp_parent,
                "unsafe Windows build/run link argument preflight",
            )

        source_executable = root / ("source.exe" if os.name == "nt" else "source.out")
        source_build = run(
            compiler_command(
                compiler,
                cc,
                "--build",
                SEPARATE_FIXTURES,
                "linkset.main",
                "--keep-c",
                "--output",
                source_executable,
            ),
            cwd=root,
            env=env,
        )
        require_status(source_build, 0, "source-backed multi-CU build")
        require_status(run([source_executable], cwd=root, env=env), 7, "built source graph")

        retained_root = Path(str(source_executable) + ".dea-c")
        expected_retained = {
            "__dea_wrapper.c",
            "linkset/leaf.c",
            "linkset/provider.c",
            "linkset/main.c",
        }
        actual_retained = {
            path.relative_to(retained_root).as_posix()
            for path in retained_root.rglob("*")
            if path.is_file()
        }
        if actual_retained != expected_retained:
            raise MultiCuFailure(
                f"retained C tree mismatch: {sorted(actual_retained)}"
            )
        if any(path.suffix in {".o", ".l1m"} for path in retained_root.rglob("*")):
            raise MultiCuFailure("retained C tree contains non-C build artifacts")

        boundary_root = root / "boundary"
        write_module(
            boundary_root,
            "boundary.provider",
            """
            module boundary.provider;
            func value() -> int { return 8; }
            """,
        )
        consumer_source = boundary_root / "boundary" / "consumer.l1"
        write_module(
            boundary_root,
            "boundary.consumer",
            """
            module boundary.consumer;
            import boundary.provider;
            func value() -> int { return boundary.provider.value(); }
            """,
        )
        write_module(
            boundary_root,
            "boundary.main",
            """
            module boundary.main;
            import boundary.consumer;
            func main() -> int { return boundary.consumer.value(); }
            """,
        )
        mutating_cc = write_source_mutating_compiler(
            root, cc, consumer_source
        )
        stale_analysis_output = root / (
            "stale-analysis.exe" if os.name == "nt" else "stale-analysis.out"
        )
        stale_analysis = run(
            compiler_command(
                compiler,
                str(mutating_cc),
                "--build",
                boundary_root,
                "boundary.main",
                "--output",
                stale_analysis_output,
            ),
            cwd=root,
            env=env,
        )
        require_status(
            stale_analysis,
            1,
            "downstream source reanalysis after provider staging",
        )
        if stale_analysis_output.exists():
            raise MultiCuFailure(
                "stale whole-graph analysis produced an executable"
            )
        require_no_workspaces(
            temp_parent, "downstream source reanalysis failure"
        )

        artifact_root = root / "artifacts"
        leaf_object = compile_module(
            compiler,
            cc,
            env,
            SEPARATE_FIXTURES,
            artifact_root,
            "linkset.leaf",
            keep_c=True,
        )
        provider_object = compile_module(
            compiler,
            cc,
            env,
            SEPARATE_FIXTURES,
            artifact_root,
            "linkset.provider",
            interface_root=artifact_root,
            keep_c=True,
        )
        main_object = compile_module(
            compiler,
            cc,
            env,
            SEPARATE_FIXTURES,
            artifact_root,
            "linkset.main",
            interface_root=artifact_root,
            keep_c=True,
        )
        for module, object_path in (
            ("linkset.leaf", leaf_object),
            ("linkset.provider", provider_object),
            ("linkset.main", main_object),
        ):
            generated = root / f"{module}.gen.c"
            completed = run(
                [
                    compiler,
                    "--gen",
                    "--project-root",
                    SEPARATE_FIXTURES,
                    "--output",
                    generated,
                    module,
                ],
                cwd=REPO_ROOT,
                env=env,
            )
            require_status(completed, 0, f"generated C for {module}")
            retained = retained_root.joinpath(*module.split(".")).with_suffix(".c")
            compiled_c = object_path.with_suffix(".c")
            if retained.read_bytes() != generated.read_bytes():
                raise MultiCuFailure(f"build and --gen C bytes differ for {module}")
            if retained.read_bytes() != compiled_c.read_bytes():
                raise MultiCuFailure(
                    f"build and compile-only --keep-c bytes differ for {module}"
                )

        main_only = root / "main-only"
        (main_only / "linkset").mkdir(parents=True)
        shutil.copyfile(
            SEPARATE_FIXTURES / "linkset" / "main.l1",
            main_only / "linkset" / "main.l1",
        )
        for c_path in artifact_root.rglob("*.c"):
            c_path.unlink()
        stable_paths = sorted(
            [*artifact_root.rglob("*.o"), *artifact_root.rglob("*.l1m")]
        )
        stable_bytes = {path: path.read_bytes() for path in stable_paths}
        mixed = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                main_only,
                "linkset.main",
                "--interface-path",
                artifact_root,
            ),
            cwd=root,
            env=env,
        )
        require_status(mixed, 7, "mixed source/interface run")
        if any(path.read_bytes() != stable_bytes[path] for path in stable_paths):
            raise MultiCuFailure("mixed build/run changed a caller-owned artifact pair")

        leaf_object.unlink()
        missing_pair = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                main_only,
                "linkset.main",
                "--interface-path",
                artifact_root,
            ),
            cwd=root,
            env=env,
        )
        require_status(missing_pair, 1, "missing authoritative sibling object")
        if "[L1C-2097]" not in missing_pair.stderr:
            raise MultiCuFailure("missing sibling object did not use native-input diagnostics")

        entry_root = root / "entry"
        write_module(
            entry_root,
            "entry.other",
            """
            module entry.other;
            func main() -> int { return 23; }
            """,
        )
        write_module(
            entry_root,
            "entry.target",
            """
            module entry.target;
            import entry.other;
            func main() -> int { return 11; }
            """,
        )
        write_module(
            entry_root,
            "entry.no_entry",
            """
            module entry.no_entry;
            import entry.other;
            func value() -> int { return 5; }
            """,
        )
        selected = run(
            compiler_command(
                compiler, cc, "--run", entry_root, "entry.target"
            ),
            cwd=root,
            env=env,
        )
        require_status(selected, 11, "explicit source-target entry selection")
        if "multiple entry" in selected.stderr:
            raise MultiCuFailure("build/run reused ambiguous standalone entry inference")
        missing_entry = run(
            compiler_command(
                compiler, cc, "--run", entry_root, "entry.no_entry"
            ),
            cwd=root,
            env=env,
        )
        require_status(missing_entry, 1, "selected target without entry bridge")
        if "does not carry 'entry;'" not in missing_entry.stderr:
            raise MultiCuFailure("non-entry target was replaced by an imported entry")

        wrapper_name_root = root / "wrapper-name"
        write_module(
            wrapper_name_root,
            "__dea_wrapper",
            """
            module __dea_wrapper;
            func main() -> int { return 41; }
            """,
        )
        wrapper_named_run = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                wrapper_name_root,
                "__dea_wrapper",
            ),
            cwd=root,
            env=env,
        )
        require_status(
            wrapper_named_run,
            41,
            "module name disjoint from private wrapper scratch",
        )
        wrapper_named_keep = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                wrapper_name_root,
                "__dea_wrapper",
                "--keep-c",
            ),
            cwd=root,
            env=env,
        )
        require_status(
            wrapper_named_keep,
            1,
            "retained wrapper/module path collision",
        )
        if "[L1C-2132]" not in wrapper_named_keep.stderr:
            raise MultiCuFailure(
                "retained wrapper/module collision lacks its diagnostic"
            )
        if (root / "__dea_wrapper.dea-c").exists():
            raise MultiCuFailure(
                "retained wrapper/module collision created an output tree"
            )

        wrapper_case_root = root / "wrapper-name-case"
        write_module(
            wrapper_case_root,
            "__DEA_WRAPPER",
            """
            module __DEA_WRAPPER;
            func main() -> int { return 42; }
            """,
        )
        wrapper_case_run = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                wrapper_case_root,
                "__DEA_WRAPPER",
            ),
            cwd=root,
            env=env,
        )
        require_status(
            wrapper_case_run,
            42,
            "case-variant module name disjoint from private wrapper scratch",
        )
        wrapper_case_keep = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                wrapper_case_root,
                "__DEA_WRAPPER",
                "--keep-c",
            ),
            cwd=root,
            env=env,
        )
        require_status(
            wrapper_case_keep,
            1,
            "case-variant retained wrapper/module path collision",
        )
        if "[L1C-2132]" not in wrapper_case_keep.stderr:
            raise MultiCuFailure(
                "case-variant retained wrapper collision lacks its diagnostic"
            )
        if (root / "__DEA_WRAPPER.dea-c").exists():
            raise MultiCuFailure(
                "case-variant retained wrapper collision created an output tree"
            )

        foreign_answer = root / "foreign-answer.o"
        compile_foreign(
            cc,
            SEPARATE_FIXTURES / "foreign_answer.c",
            foreign_answer,
            env,
        )
        foreign_run = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                SEPARATE_FIXTURES,
                "linkset.foreign_entry",
                "--foreign-object",
                foreign_answer,
            ),
            cwd=root,
            env=env,
        )
        require_status(foreign_run, 37, "foreign-object run")
        foreign_executable = root / (
            "foreign.exe" if os.name == "nt" else "foreign.out"
        )
        foreign_build = run(
            compiler_command(
                compiler,
                cc,
                "--build",
                SEPARATE_FIXTURES,
                "linkset.foreign_entry",
                "--foreign-object",
                foreign_answer,
                "--output",
                foreign_executable,
            ),
            cwd=root,
            env=env,
        )
        require_status(foreign_build, 0, "foreign-object build")
        require_status(
            run([foreign_executable], cwd=root, env=env),
            37,
            "foreign-object built executable",
        )

        lifecycle_observer = root / "lifecycle-observer.o"
        compile_foreign(
            cc,
            SEPARATE_FIXTURES / "lifecycle_observer.c",
            lifecycle_observer,
            env,
        )
        lifecycle = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                SEPARATE_FIXTURES,
                "lifecycle.main",
                "--foreign-object",
                lifecycle_observer,
            ),
            cwd=root,
            env=env,
        )
        require_status(lifecycle, 0, "dependency-ordered lifecycle run")

        argv_run = run(
            [
                compiler,
                "--run",
                "--project-root",
                DRIVER_FIXTURES,
                "--c-compiler",
                cc,
                "argv_dump",
                "--",
                "two words",
                'quote"slash\\',
            ],
            cwd=root,
            env=env,
        )
        require_status(argv_run, 0, "exact run argv forwarding")
        if argv_run.stdout.splitlines() != ["3", "two words", 'quote"slash\\']:
            raise MultiCuFailure(f"run argv mismatch: {argv_run.stdout!r}")

        status_root = root / "status"
        write_module(
            status_root,
            "status.main",
            """
            module status.main;
            func main() -> int { return 127; }
            """,
        )
        status_run = run(
            compiler_command(
                compiler, cc, "--run", status_root, "status.main"
            ),
            cwd=root,
            env=env,
        )
        require_status(status_run, 127, "status 127 forwarding")

        launch_failure_cc = write_launch_failure_compiler(root, cc)
        launch_failure = run(
            compiler_command(
                compiler,
                str(launch_failure_cc),
                "--run",
                status_root,
                "status.main",
            ),
            cwd=root,
            env=env,
        )
        require_status(launch_failure, 1, "run executable launch failure")
        if "[L1C-2133]" not in launch_failure.stderr:
            raise MultiCuFailure("launch failure was not distinguished from status 127")

        run_keep = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                SEPARATE_FIXTURES,
                "linkset.main",
                "--keep-c",
            ),
            cwd=root,
            env=env,
        )
        require_status(run_keep, 7, "run-mode retained C")
        run_retained = root / "linkset.main.dea-c"
        if not (run_retained / "__dea_wrapper.c").is_file():
            raise MultiCuFailure("run-mode retained wrapper is missing")
        run_files = {
            path.relative_to(run_retained).as_posix()
            for path in run_retained.rglob("*")
            if path.is_file()
        }
        if run_files != expected_retained:
            raise MultiCuFailure(
                f"run-mode retained C tree mismatch: {sorted(run_files)}"
            )
        for relative in sorted(expected_retained):
            if (run_retained / relative).read_bytes() != (
                retained_root / relative
            ).read_bytes():
                raise MultiCuFailure(
                    f"build/run retained C bytes differ for {relative}"
                )
        repeated_keep = run(
            compiler_command(
                compiler,
                cc,
                "--run",
                SEPARATE_FIXTURES,
                "linkset.main",
                "--keep-c",
            ),
            cwd=root,
            env=env,
        )
        require_status(repeated_keep, 1, "existing retained-C tree rejection")
        if "[L1C-2132]" not in repeated_keep.stderr:
            raise MultiCuFailure("existing retained-C tree lacks its diagnostic")

        require_no_workspaces(temp_parent, "multi-CU matrix")

    print("l1c_stage1_build_run_multi_cu_test: all tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
