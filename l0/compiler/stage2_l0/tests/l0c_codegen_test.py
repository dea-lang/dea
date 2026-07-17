#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Compare Stage 2 generated C against backend golden fixtures."""

from __future__ import annotations

import difflib
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from tool_test_common import (
    BUILD_TESTS_ROOT,
    REPO_ROOT,
    ToolTestFailure,
    build_stage2,
    detect_c_compiler,
    make_temp_dir,
    native_path,
    normalize_text_file,
    read_text,
    repo_relative,
    run,
    stage2_launcher_path,
)

FIXTURE_ROOT = REPO_ROOT / "compiler" / "stage2_l0" / "tests" / "fixtures" / "backend_golden"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_stage2_backend_goldens.py"


def fail(message: str, artifact_dir: Path, bootstrap_dir: Path | None) -> int:
    """Print one failure and return the shell-style exit code."""

    print(f"l0c_codegen_test: FAIL: {message}")
    print(f"l0c_codegen_test: artifacts={artifact_dir}")
    if bootstrap_dir is not None:
        print(f"l0c_codegen_test: bootstrap={bootstrap_dir}")
    return 1


def compiler_words(compiler: str) -> list[str]:
    """Split one compiler command string into argv words."""

    words = shlex.split(compiler)
    if not words:
        raise ToolTestFailure("resolved C compiler command is empty")
    return words


def compile_generated_c(compiler: str, src: Path, exe: Path) -> None:
    """Compile one generated C source file for runtime parity checks."""

    name = Path(compiler_words(compiler)[0]).name.lower()
    command = [*compiler_words(compiler), str(src), "-o", str(exe), "-I", str(REPO_ROOT / "compiler" / "shared" / "runtime")]
    if name.startswith("tcc"):
        command.extend(["-std=c99", "-Wall", "-pedantic"])
    elif name.startswith("gcc") or name.startswith("clang") or name == "cc":
        command.extend(["-std=c99", "-Wall", "-Wextra", "-Wno-unused", "-pedantic-errors"])
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise ToolTestFailure(
            f"C compilation failed with rc={completed.returncode}: {' '.join(command)}\n{completed.stdout}"
        )


def selected_case_names(args: list[str]) -> set[str] | None:
    """Return optional fixture filters supplied to the script directly."""

    if not args:
        return None
    return set(args)


def main() -> int:
    """Program entrypoint."""

    artifact_dir = make_temp_dir("l0_stage2_codegen_tests.", BUILD_TESTS_ROOT)
    bootstrap_dir: Path | None = None
    keep_artifacts = False
    try:
        run([sys.executable, REFRESH_SCRIPT, "--check", *sys.argv[1:]])
        bootstrap_dir = make_temp_dir("l0_stage2_codegen.", BUILD_TESTS_ROOT)
        build_stage2(repo_relative(bootstrap_dir))
        l0c = stage2_launcher_path(bootstrap_dir / "bin" / "l0c-stage2")

        compiler = ""
        if any(FIXTURE_ROOT.glob("*/*.expected.out")):
            resolved = detect_c_compiler()
            if resolved is None:
                raise ToolTestFailure("no C compiler found for runtime parity checks")
            compiler = resolved

        wanted = selected_case_names(sys.argv[1:])
        failed = False
        for entry_file in sorted(FIXTURE_ROOT.glob("*/entry_module.txt")):
            case_dir = entry_file.parent
            case_name = case_dir.name
            if wanted is not None and case_name not in wanted:
                continue

            entry_module = read_text(entry_file).strip()
            generated = artifact_dir / f"{case_name}.generated.c"
            normalized_generated = artifact_dir / f"{case_name}.generated.normalized.c"
            normalized_expected = artifact_dir / f"{case_name}.expected.normalized.c"
            expected = case_dir / f"{case_name}.golden.c"

            gen_result = run(
                [l0c, "--gen", "--no-line-directives", "--project-root", native_path(case_dir), entry_module],
                expected_returncode=None,
            )
            generated.write_text(gen_result.stdout, encoding="utf-8")
            if gen_result.returncode != 0:
                print(f"{case_name}: GEN_FAIL")
                (artifact_dir / f"{case_name}.gen.log").write_text(
                    gen_result.stdout + gen_result.stderr,
                    encoding="utf-8",
                )
                failed = True
                continue

            normalize_text_file(expected, normalized_expected)
            normalize_text_file(generated, normalized_generated)
            expected_text = read_text(normalized_expected)
            generated_text = read_text(normalized_generated)
            if expected_text != generated_text:
                diff = "".join(
                    difflib.unified_diff(
                        expected_text.splitlines(keepends=True),
                        generated_text.splitlines(keepends=True),
                        fromfile=str(normalized_expected),
                        tofile=str(normalized_generated),
                    )
                )
                (artifact_dir / f"{case_name}.diff").write_text(diff, encoding="utf-8")
                print(f"{case_name}: DIFF_FAIL")
                print(diff)
                failed = True
                continue

            expected_out = case_dir / f"{case_name}.expected.out"
            if expected_out.is_file():
                exe = artifact_dir / f"{case_name}.out"
                actual_out = artifact_dir / f"{case_name}.stdout"
                compile_generated_c(compiler, generated, exe)
                completed = subprocess.run(
                    [str(exe)],
                    cwd=REPO_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                actual_out.write_text(completed.stdout, encoding="utf-8")
                if completed.returncode != 0:
                    print(f"{case_name}: RUNTIME_FAIL")
                    failed = True
                    continue
                if read_text(expected_out) != read_text(actual_out):
                    diff = "".join(
                        difflib.unified_diff(
                            read_text(expected_out).splitlines(keepends=True),
                            read_text(actual_out).splitlines(keepends=True),
                            fromfile=str(expected_out),
                            tofile=str(actual_out),
                        )
                    )
                    (artifact_dir / f"{case_name}.stdout.diff").write_text(diff, encoding="utf-8")
                    print(f"{case_name}: RUNTIME_DIFF_FAIL")
                    print(diff)
                    failed = True
                    continue

            print(f"{case_name}: OK")

        if failed:
            keep_artifacts = True
            raise ToolTestFailure("one or more codegen cases failed")
    except ToolTestFailure as exc:
        return fail(str(exc), artifact_dir, bootstrap_dir)
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)
            if bootstrap_dir is not None:
                shutil.rmtree(bootstrap_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
