#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for private L1 Stage 1 build/run workspaces."""

from __future__ import annotations

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
DRIVER_FIXTURES = (
    L1_ROOT / "compiler" / "stage1_l0" / "tests" / "fixtures" / "driver"
)


class WorkspaceFailure(RuntimeError):
    """Raised when one workspace lifecycle assertion fails."""


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def stage1_compiler() -> Path:
    """Return the repo-local L1 Stage 1 compiler launcher."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def real_c_compiler() -> str:
    """Return one real host C compiler for the delegating fake."""

    for configured in (
        os.environ.get("L1_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    ):
        if configured:
            resolved = shutil.which(configured)
            if resolved is None:
                raise WorkspaceFailure(
                    f"configured C compiler was not found: {configured}"
                )
            return resolved

    for candidate in ("tcc", "gcc", "clang", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise WorkspaceFailure("workspace test requires a real C compiler")


def write_fake_compiler(root: Path) -> Path:
    """Write a host launcher for one instrumented delegating C compiler."""

    real_compiler = Path(real_c_compiler()).name.lower()
    family_prefix = "tcc" if real_compiler.startswith("tcc") else "gcc"
    script = root / (
        "fake_cc.py" if os.name == "nt" else f"{family_prefix}-workspace-fake"
    )
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            from pathlib import Path
            import subprocess
            import sys

            args = sys.argv[1:]
            c_path = next(
                (arg for arg in args if arg.lower().endswith(".c")),
                "",
            )
            output = ""
            for index, arg in enumerate(args):
                if arg == "-o" and index + 1 < len(args):
                    output = args[index + 1]
                elif arg.lower().startswith("/fe:"):
                    output = arg[4:]

            record = {
                "args": args,
                "c_path": c_path,
                "output": output,
            }
            log_path = Path(os.environ["L1_WORKSPACE_FAKE_LOG"])
            records = []
            if log_path.is_file():
                records = json.loads(log_path.read_text(encoding="utf-8"))
            records.append(record)
            log_path.write_text(
                json.dumps(records),
                encoding="utf-8",
            )

            mode = os.environ.get("L1_WORKSPACE_FAKE_MODE", "success")
            workspace = Path(c_path).parent if c_path else None
            if mode == "fail":
                print("instrumented compiler failure", file=sys.stderr)
                raise SystemExit(23)
            if mode == "no-output":
                raise SystemExit(0)

            compiler_env = os.environ.copy()
            configured_tmpdir = compiler_env.get("TMPDIR", "")
            if configured_tmpdir and not Path(configured_tmpdir).is_dir():
                compiler_env.pop("TMPDIR", None)

            completed = subprocess.run(
                [os.environ["L1_WORKSPACE_REAL_CC"], *args],
                env=compiler_env,
                check=False,
            )
            if completed.returncode == 0 and mode == "unexpected" and workspace is not None:
                (workspace / "unexpected.side").write_text(
                    "retained",
                    encoding="utf-8",
                )
            raise SystemExit(completed.returncode)
            """
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | 0o111)
    if os.name != "nt":
        return script

    launcher = root / f"{family_prefix}-workspace-fake.cmd"
    launcher.write_text(
        '@echo off\r\n'
        f'"{sys.executable}" "{script}" %*\r\n',
        encoding="utf-8",
    )
    return launcher


def compiler_env(
    temp_parent: Path,
    fake_compiler: Path,
    log_path: Path,
    mode: str,
) -> dict[str, str]:
    """Return one controlled compiler environment."""

    env = os.environ.copy()
    env["TMPDIR"] = str(temp_parent)
    env.pop("TEMP", None)
    env.pop("TMP", None)
    env["L1_WORKSPACE_FAKE_LOG"] = str(log_path)
    env["L1_WORKSPACE_FAKE_MODE"] = mode
    env["L1_WORKSPACE_REAL_CC"] = real_c_compiler()
    env["L1_WORKSPACE_FAKE_CC"] = str(fake_compiler)
    return env


def run_compiler(
    compiler: Path,
    cwd: Path,
    env: dict[str, str],
    fake_compiler: Path,
    mode: str,
    module_name: str,
    output: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one Stage 1 build or run command."""

    args = [
        str(compiler),
        mode,
        "--project-root",
        str(DRIVER_FIXTURES),
        "--c-compiler",
        str(fake_compiler),
    ]
    if output is not None:
        args.extend(["--output", str(output)])
    args.append(module_name)
    return subprocess.run(
        args,
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


def read_records(log_path: Path) -> list[dict[str, object]]:
    """Read all fake-compiler invocation records."""

    return json.loads(log_path.read_text(encoding="utf-8"))


def source_record(log_path: Path) -> dict[str, object]:
    """Return the first source-module compiler invocation record."""

    for record in read_records(log_path):
        c_path = str(record["c_path"])
        if c_path and Path(c_path).name != "__dea_wrapper.c":
            return record
    raise WorkspaceFailure("fake compiler recorded no source-module compile")


def workspace_from_log(log_path: Path) -> Path:
    """Return the absolute private workspace recorded for wrapper compilation."""

    for record in read_records(log_path):
        c_path = str(record["c_path"])
        if c_path and Path(c_path).name == "__dea_wrapper.c":
            scratch = Path(c_path).parent
            if scratch.name != ".link":
                raise WorkspaceFailure(
                    f"wrapper compiler scratch is not hidden .link: {scratch}"
                )
            return scratch.parent.resolve()
    raise WorkspaceFailure("fake compiler recorded no wrapper compile")


def workspaces(parent: Path) -> list[Path]:
    """Return retained build/run workspace directories under one parent."""

    return sorted(path.resolve() for path in parent.glob(".l1c-*-workspace-*"))


def require_no_workspaces(parent: Path, context: str) -> None:
    """Require one temporary parent to contain no compiler workspaces."""

    leftovers = workspaces(parent)
    if leftovers:
        raise WorkspaceFailure(
            f"{context} retained workspaces: "
            + ", ".join(str(path) for path in leftovers)
        )


def test_build_uses_canonical_workspace(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """Build scratch children stay under one canonical private workspace."""

    safe_parent = root / "canonical parent"
    selected_parent = root / "selected parent"
    safe_parent.mkdir(mode=0o700)
    try:
        selected_parent.symlink_to(safe_parent, target_is_directory=True)
    except OSError:
        selected_parent = safe_parent

    log_path = root / "canonical.json"
    output = root / ("canonical.exe" if os.name == "nt" else "canonical.out")
    env = compiler_env(selected_parent, fake_compiler, log_path, "success")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 0:
        raise WorkspaceFailure(
            "canonical workspace build failed:\n" + completed.stderr
        )
    if not output.is_file():
        raise WorkspaceFailure("canonical workspace build omitted output")

    record = source_record(log_path)
    c_path = Path(str(record["c_path"]))
    if c_path.name != "ok_leaf.c":
        raise WorkspaceFailure(f"unexpected generated C child: {c_path}")
    workspace = workspace_from_log(log_path)
    if workspace.parent != safe_parent.resolve():
        raise WorkspaceFailure(
            f"workspace did not use canonical parent: {workspace}"
        )
    if not workspace.name.startswith(".l1c-build-workspace-"):
        raise WorkspaceFailure(f"unexpected build workspace name: {workspace}")
    require_no_workspaces(safe_parent, "successful build")


def test_posix_literal_backslash_parent_contains_workspace(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """A POSIX parent ending in literal backslash contains the workspace."""

    if os.name == "nt":
        return

    temp_parent = root / "literal-backslash-parent\\"
    temp_parent.mkdir(mode=0o700)
    log_path = root / "literal-backslash.json"
    output = root / "literal-backslash.out"
    env = compiler_env(temp_parent, fake_compiler, log_path, "success")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 0:
        raise WorkspaceFailure(
            "literal-backslash parent build failed:\n" + completed.stderr
        )
    workspace = workspace_from_log(log_path)
    if workspace.parent != temp_parent.resolve():
        raise WorkspaceFailure(
            "workspace escaped literal-backslash parent: "
            f"{workspace}"
        )
    require_no_workspaces(temp_parent, "literal-backslash parent build")


def test_non_directory_candidate_falls_through(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """A non-directory TMPDIR falls through to the next existing candidate."""

    non_directory = root / "not-a-directory"
    non_directory.write_text("file", encoding="utf-8")
    fallback = root / "fallback parent"
    fallback.mkdir(mode=0o700)
    log_path = root / "fallback.json"
    output = root / ("fallback.exe" if os.name == "nt" else "fallback.out")
    env = compiler_env(non_directory, fake_compiler, log_path, "success")
    env["TEMP"] = str(fallback)
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 0:
        raise WorkspaceFailure(
            "temporary-parent fallback build failed:\n" + completed.stderr
        )
    workspace = workspace_from_log(log_path)
    if workspace.parent != fallback.resolve():
        raise WorkspaceFailure(
            f"non-directory TMPDIR did not fall through to TEMP: {workspace}"
        )
    require_no_workspaces(fallback, "fallback build")


def test_empty_candidate_falls_through(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """An explicitly empty TMPDIR retains absent-value fallback behavior."""

    fallback = root / "empty-value fallback"
    fallback.mkdir(mode=0o700)
    log_path = root / "empty-value.json"
    output = root / (
        "empty-value.exe" if os.name == "nt" else "empty-value.out"
    )
    env = compiler_env(fallback, fake_compiler, log_path, "success")
    env["TMPDIR"] = ""
    env["TEMP"] = str(fallback)
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 0:
        raise WorkspaceFailure(
            "empty temporary-parent fallback build failed:\n"
            + completed.stderr
        )
    workspace = workspace_from_log(log_path)
    if workspace.parent != fallback.resolve():
        raise WorkspaceFailure(
            f"empty TMPDIR did not fall through to TEMP: {workspace}"
        )
    require_no_workspaces(fallback, "empty-value fallback build")


def test_candidate_inspection_error_is_fatal(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """An inaccessible TMPDIR fails instead of falling through to TEMP."""

    if os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return

    denied_parent = root / "search-denied"
    selected_parent = denied_parent / "configured-parent"
    fallback = root / "must-not-use-fallback"
    denied_parent.mkdir(mode=0o700)
    selected_parent.mkdir(mode=0o700)
    fallback.mkdir(mode=0o700)
    denied_parent.chmod(0)
    try:
        try:
            selected_parent.stat()
        except PermissionError:
            pass
        else:
            # Some filesystems or sandbox policies do not enforce POSIX
            # search permissions. They cannot exercise this regression.
            return

        log_path = root / "inspection-error.json"
        output = root / "inspection-error.out"
        env = compiler_env(
            selected_parent, fake_compiler, log_path, "success")
        env["TEMP"] = str(fallback)
        completed = run_compiler(
            compiler,
            root,
            env,
            fake_compiler,
            "--build",
            "ok_main",
            output,
        )
        if completed.returncode != 1 or "[L1C-9513]" not in completed.stderr:
            raise WorkspaceFailure(
                "TMPDIR inspection error did not fail with L1C-9513:\n"
                + completed.stderr
            )
        if log_path.exists():
            raise WorkspaceFailure(
                "TMPDIR inspection error reached the host compiler"
            )
        if output.exists():
            raise WorkspaceFailure(
                "TMPDIR inspection error produced caller output"
            )
        require_no_workspaces(fallback, "inspection-error fallback")
    finally:
        denied_parent.chmod(0o700)


def test_compiler_failure_cleans_workspace(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """Host-compiler failure still removes every known workspace child."""

    temp_parent = root / "compiler failure parent"
    temp_parent.mkdir(mode=0o700)
    log_path = root / "compiler-failure.json"
    output = root / (
        "compiler-failure.exe" if os.name == "nt" else "compiler-failure.out"
    )
    env = compiler_env(temp_parent, fake_compiler, log_path, "fail")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode == 0 or "[L1C-0010]" not in completed.stderr:
        raise WorkspaceFailure(
            "instrumented compiler failure was not reported:\n"
            + completed.stderr
        )
    if "instrumented compiler failure" not in completed.stderr:
        raise WorkspaceFailure("host compiler stderr was not replayed")
    require_no_workspaces(temp_parent, "compiler failure")


def test_launch_failure_cleans_workspace(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """A missing temporary run executable still reaches bounded cleanup."""

    temp_parent = root / "launch failure parent"
    temp_parent.mkdir(mode=0o700)
    log_path = root / "launch-failure.json"
    env = compiler_env(temp_parent, fake_compiler, log_path, "no-output")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--run",
        "ok_main",
    )
    if completed.returncode == 0:
        raise WorkspaceFailure("missing run executable unexpectedly succeeded")
    require_no_workspaces(temp_parent, "launch failure")


def test_cleanup_failure_changes_build_success(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """Unexpected compiler contents retain the workspace and fail a build."""

    temp_parent = root / "retained build parent"
    temp_parent.mkdir(mode=0o700)
    log_path = root / "retained-build.json"
    output = root / (
        "retained-build.exe" if os.name == "nt" else "retained-build.out"
    )
    env = compiler_env(temp_parent, fake_compiler, log_path, "unexpected")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 1 or "[L1C-9514]" not in completed.stderr:
        raise WorkspaceFailure(
            "retained build workspace did not turn success into status 1:\n"
            + completed.stderr
        )
    if not output.is_file():
        raise WorkspaceFailure(
            "cleanup failure removed the successful caller output"
        )

    workspace = workspace_from_log(log_path)
    if workspaces(temp_parent) != [workspace]:
        raise WorkspaceFailure("cleanup failure did not retain exact workspace")
    if sorted(path.name for path in workspace.iterdir()) != [
        ".link",
        "unexpected.side",
    ]:
        raise WorkspaceFailure(
            "bounded cleanup did not remove only known children"
        )
    if sorted(path.name for path in (workspace / ".link").iterdir()) != [
        "unexpected.side"
    ]:
        raise WorkspaceFailure(
            "bounded cleanup removed unknown hidden-link contents"
        )
    shutil.rmtree(workspace)


def test_cleanup_failure_preserves_program_status(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """A nonzero program result remains authoritative over cleanup failure."""

    # Darwin tcc invokes its internal codesign helper without preserving a
    # space-bearing output token, so keep this status-precedence fixture path
    # simple while other cases cover shell-safe workspace paths.
    temp_parent = root / "retained_run_parent"
    temp_parent.mkdir(mode=0o700)
    log_path = root / "retained-run.json"
    env = compiler_env(temp_parent, fake_compiler, log_path, "unexpected")
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--run",
        "exit_seven",
    )
    if completed.returncode != 7 or "[L1C-9514]" not in completed.stderr:
        raise WorkspaceFailure(
            "cleanup failure did not preserve program status 7:\n"
            + completed.stderr
        )
    workspace = workspace_from_log(log_path)
    if workspaces(temp_parent) != [workspace]:
        raise WorkspaceFailure("run cleanup failure did not retain workspace")
    shutil.rmtree(workspace)


def test_posix_trust_uses_actual_host(
    compiler: Path,
    fake_compiler: Path,
    root: Path,
) -> None:
    """L1_PLATFORM cannot bypass POSIX temporary-parent trust validation."""

    if os.name == "nt":
        return
    unsafe_parent = root / "unsafe parent"
    unsafe_parent.mkdir(mode=0o700)
    unsafe_parent.chmod(0o777)
    log_path = root / "unsafe.json"
    output = root / "unsafe.out"
    env = compiler_env(unsafe_parent, fake_compiler, log_path, "success")
    env["L1_PLATFORM"] = "windows"
    completed = run_compiler(
        compiler,
        root,
        env,
        fake_compiler,
        "--build",
        "ok_main",
        output,
    )
    if completed.returncode != 1 or "[L1C-9513]" not in completed.stderr:
        raise WorkspaceFailure(
            "unsafe POSIX parent was not rejected with L1C-9513:\n"
            + completed.stderr
        )
    if log_path.exists():
        raise WorkspaceFailure("unsafe parent reached the host compiler")
    if output.exists():
        raise WorkspaceFailure("unsafe parent produced caller output")
    require_no_workspaces(unsafe_parent, "unsafe-parent rejection")


def main() -> int:
    """Run private workspace lifecycle integration coverage."""

    compiler = stage1_compiler()
    if not compiler.is_file():
        print(
            f"l1c_stage1_build_run_workspace_test: FAIL: "
            f"missing Stage 1 compiler: {compiler}"
        )
        return 1

    artifact_dir = Path(
        tempfile.mkdtemp(prefix="l1_stage1_build_run_workspace.")
    )
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    try:
        fake_compiler = write_fake_compiler(artifact_dir)
        checks = [
            test_build_uses_canonical_workspace,
            test_posix_literal_backslash_parent_contains_workspace,
            test_non_directory_candidate_falls_through,
            test_empty_candidate_falls_through,
            test_candidate_inspection_error_is_fatal,
            test_compiler_failure_cleans_workspace,
            test_launch_failure_cleans_workspace,
            test_cleanup_failure_changes_build_success,
            test_cleanup_failure_preserves_program_status,
            test_posix_trust_uses_actual_host,
        ]
        for check in checks:
            case_root = artifact_dir / check.__name__
            case_root.mkdir()
            check(compiler, fake_compiler, case_root)
        print("l1c_stage1_build_run_workspace_test: PASS")
        return 0
    except WorkspaceFailure as exc:
        keep_artifacts = True
        print(f"l1c_stage1_build_run_workspace_test: FAIL: {exc}")
        print(
            "l1c_stage1_build_run_workspace_test: "
            f"artifacts={artifact_dir}"
        )
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
