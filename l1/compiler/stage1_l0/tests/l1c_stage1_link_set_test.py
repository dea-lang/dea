#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for the L1 Stage 1 standalone link-set mode."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from l1c_stage1_compile_only_test import (
    require_reusable_set,
    run_compiler,
    stage1_compiler,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
FIXTURES = (
    L1_ROOT
    / "compiler"
    / "stage1_l0"
    / "tests"
    / "fixtures"
    / "separate_compilation"
)
STALE_V1_FIXTURES = FIXTURES / "stale" / "v1"
STALE_V2_FIXTURES = FIXTURES / "stale" / "v2"
TRACE_CHECKER = (
    L1_ROOT / "compiler" / "stage1_l0" / "scripts" / "check_trace_log.py"
)
RUNTIME_HEADER = L1_ROOT / "compiler" / "shared" / "runtime" / "include" / "dea_rt.h"
ARC_LOCATION_RE = re.compile(r'\bloc="([^"]+)":(\d+)\s*$')


class LinkSetFailure(RuntimeError):
    """Raised when one standalone link-set assertion fails."""


def resolve_c_compiler() -> str:
    """Return one GCC-style compiler suitable for the end-to-end link lane.

    Returns:
        Resolved compiler path.

    Raises:
        LinkSetFailure: If a configured compiler is unavailable or unsupported,
            or no supported host C compiler is available.
    """

    configured_values = (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    )
    for configured in configured_values:
        if not configured:
            continue
        resolved = shutil.which(configured)
        if resolved is None and Path(configured).is_file():
            resolved = str(Path(configured).resolve())
        if resolved is None:
            raise LinkSetFailure(
                f"configured C compiler was not found: {configured}"
            )
        if Path(resolved).name.lower() in {
            "cl",
            "cl.exe",
            "clang-cl",
            "clang-cl.exe",
        }:
            raise LinkSetFailure(
                "standalone link-set test requires a GCC-style C compiler, "
                f"not {configured}"
            )
        return resolved

    candidates = ("gcc", "clang", "cc") if os.name == "nt" else ("clang", "gcc", "cc")
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise LinkSetFailure("standalone link-set test requires a GCC-style C compiler")


def module_object(artifact_root: Path, module_name: str) -> Path:
    """Return the canonical object path for one dotted module.

    Args:
        artifact_root: Root of the generated artifact tree.
        module_name: Canonical dotted module name.

    Returns:
        Canonical `.o` path below `artifact_root`.
    """

    return artifact_root.joinpath(*module_name.split(".")).with_suffix(".o")


def sibling_interface(object_path: Path) -> Path:
    """Return the exact terminal-`.o` sibling interface path."""

    if object_path.name == ".o" or not object_path.name.endswith(".o"):
        raise LinkSetFailure(
            f"cannot derive sibling interface for noncanonical object: {object_path}"
        )
    return object_path.with_name(object_path.name[:-2] + ".l1m")


def copy_dea_pair(source_object: Path, destination_object: Path) -> Path:
    """Copy one caller-trusted object/interface pair to a new basename."""

    destination_object.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_object, destination_object)
    shutil.copy2(
        sibling_interface(source_object),
        sibling_interface(destination_object),
    )
    return destination_object


def compile_module(
    compiler: Path,
    c_compiler: str,
    source_root: Path,
    artifact_root: Path,
    module_name: str,
    *,
    trace_arc: bool = False,
) -> Path:
    """Compile one fixture module and return its opaque paired object.

    Args:
        compiler: Repo-local L1 Stage 1 compiler.
        c_compiler: Host C compiler path.
        source_root: Project root containing the fixture module.
        artifact_root: Canonical output and interface-search root.
        module_name: Canonical dotted module name.
        trace_arc: Generate caller-location-preserving ARC operations.

    Returns:
        Published object path.

    Raises:
        LinkSetFailure: If compile-only fails or does not publish its reusable
            object/interface pair.
    """

    artifact_root.mkdir(parents=True, exist_ok=True)
    object_path = module_object(artifact_root, module_name)
    args = [
        "--compile",
        "--project-root",
        str(source_root),
        "--interface-path",
        str(artifact_root),
        "--c-compiler",
        c_compiler,
        "--output",
        str(object_path),
        module_name,
    ]
    if trace_arc:
        args.insert(1, "--trace-arc")
    completed = run_compiler(compiler, artifact_root, *args)
    if completed.returncode != 0:
        raise LinkSetFailure(
            f"compile-only failed for {module_name}:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        require_reusable_set(object_path, module_name)
    except RuntimeError as exc:
        raise LinkSetFailure(str(exc)) from exc
    return object_path


def compile_module_with_default_host(
    compiler: Path,
    source_root: Path,
    artifact_root: Path,
    module_name: str,
) -> Path:
    """Compile one fixture module with the driver's default host compiler."""

    artifact_root.mkdir(parents=True, exist_ok=True)
    object_path = module_object(artifact_root, module_name)
    completed = run_compiler(
        compiler,
        artifact_root,
        "--compile",
        "--project-root",
        str(source_root),
        "--interface-path",
        str(artifact_root),
        "--output",
        str(object_path),
        module_name,
    )
    if completed.returncode != 0:
        raise LinkSetFailure(
            f"default-host compile-only failed for {module_name}:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        require_reusable_set(object_path, module_name)
    except RuntimeError as exc:
        raise LinkSetFailure(str(exc)) from exc
    return object_path


def compile_foreign_object(
    c_compiler: str,
    source_path: Path,
    object_path: Path,
) -> Path:
    """Compile one caller-asserted C relocatable object.

    Args:
        c_compiler: Host C compiler path.
        source_path: C fixture source.
        object_path: Destination object path.

    Returns:
        `object_path`.

    Raises:
        LinkSetFailure: If the host compiler fails.
    """

    object_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            c_compiler,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ],
        cwd=L1_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise LinkSetFailure(
            f"foreign fixture compilation failed for {source_path}:\n"
            f"{completed.stdout}"
        )
    if not object_path.is_file() or not object_path.read_bytes():
        raise LinkSetFailure(
            f"foreign fixture did not produce an object: {object_path}"
        )
    return object_path


def compile_foreign_assembly(
    c_compiler: str,
    source_path: Path,
    object_path: Path,
) -> Path:
    """Compile one host-native assembly fixture into a relocatable object.

    Args:
        c_compiler: Host C compiler driver path.
        source_path: Assembly fixture source.
        object_path: Destination object path.

    Returns:
        `object_path`.

    Raises:
        LinkSetFailure: If the host compiler fails.
    """

    object_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            c_compiler,
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ],
        cwd=L1_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise LinkSetFailure(
            f"foreign assembly compilation failed for {source_path}:\n"
            f"{completed.stdout}"
        )
    if not object_path.is_file() or not object_path.read_bytes():
        raise LinkSetFailure(
            f"foreign assembly did not produce an object: {object_path}"
        )
    return object_path


def run_link(
    compiler: Path,
    c_compiler: str,
    cwd: Path,
    dea_objects: list[Path],
    output: Path,
    *,
    foreign_objects: list[Path] | None = None,
    entry: str | None = None,
    foreign_equals: bool = False,
    c_options: str | None = None,
    runtime_include: Path | None = None,
    trace_arc: bool = False,
    short_aliases: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one public standalone link invocation.

    Args:
        compiler: Repo-local L1 Stage 1 compiler.
        c_compiler: Host C compiler path.
        cwd: Link invocation directory.
        dea_objects: Positional verified Dea objects.
        output: Final executable path.
        foreign_objects: Explicit caller-asserted native objects.
        entry: Optional canonical entry module.
        foreign_equals: Use the `--foreign-object=PATH` spelling for the first
            foreign object.
        c_options: Optional wrapper-compilation options.
        runtime_include: Optional directory containing a test-owned `dea_rt.h`.
        trace_arc: Select the traced runtime and preserve ARC source locations.
        short_aliases: Use the public short spellings for link-specific options.

    Returns:
        Completed compiler process.
    """

    args = ["-k" if short_aliases else "--link", *(str(path) for path in dea_objects)]
    if trace_arc:
        args.append("-Va" if short_aliases else "--trace-arc")
    for index, path in enumerate(foreign_objects or []):
        if foreign_equals and index == 0:
            option = "-Cf" if short_aliases else "--foreign-object"
            args.append(f"{option}={path}")
        else:
            args.extend(["-Cf" if short_aliases else "--foreign-object", str(path)])
    if entry is not None:
        args.extend(["-e" if short_aliases else "--entry", entry])
    if c_options is not None:
        args.extend(["--c-options", c_options])
    if runtime_include is not None:
        args.extend(["--runtime-include", str(runtime_include)])
    args.extend(["--c-compiler", c_compiler, "--output", str(output)])
    return run_compiler(compiler, cwd, *args)


def run_link_with_default_host(
    compiler: Path,
    cwd: Path,
    dea_objects: list[Path],
    output: Path,
) -> subprocess.CompletedProcess[str]:
    """Run standalone linking with the driver's default host compiler."""

    return run_compiler(
        compiler,
        cwd,
        "--link",
        *(str(path) for path in dea_objects),
        "--output",
        str(output),
    )


def combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    """Return normalized combined text from one compiler invocation."""

    return f"{completed.stdout}\n{completed.stderr}".lower()


def require_link_success(
    completed: subprocess.CompletedProcess[str],
    output: Path,
    context: str,
) -> None:
    """Require one standalone link invocation to publish an executable.

    Args:
        completed: Completed compiler process.
        output: Expected executable path.
        context: Human-readable test context.

    Raises:
        LinkSetFailure: If linking failed or no executable was produced.
    """

    if completed.returncode != 0:
        raise LinkSetFailure(
            f"{context} failed:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    if not output.is_file():
        raise LinkSetFailure(f"{context} did not publish an executable: {output}")


def require_link_failure(
    completed: subprocess.CompletedProcess[str],
    context: str,
    *fragments: str,
) -> None:
    """Require one link invocation to fail with identifying text fragments.

    Args:
        completed: Completed compiler process.
        context: Human-readable test context.
        *fragments: Case-insensitive text required in combined output.

    Raises:
        LinkSetFailure: If linking succeeds or expected text is absent.
    """

    if completed.returncode == 0:
        raise LinkSetFailure(f"{context} unexpectedly succeeded")
    text = combined_output(completed)
    for fragment in fragments:
        if fragment.lower() not in text:
            raise LinkSetFailure(
                f"{context} did not report {fragment!r}:\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )


def require_program_status(executable: Path, expected: int, context: str) -> None:
    """Run one linked executable and require its expected status.

    Args:
        executable: Program to run.
        expected: Expected process status.
        context: Human-readable test context.

    Raises:
        LinkSetFailure: If the program returns another status.
    """

    completed = subprocess.run(
        [str(executable)],
        cwd=executable.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != expected:
        raise LinkSetFailure(
            f"{context} returned {completed.returncode}, expected {expected}:\n"
            f"stdout={completed.stdout!r}\n"
            f"stderr={completed.stderr!r}"
        )


def require_clean_trace(trace_path: Path, context: str) -> None:
    """Require one runtime trace to pass the repository trace checker.

    Args:
        trace_path: Captured executable stderr.
        context: Human-readable test context.

    Raises:
        LinkSetFailure: If trace validation fails or reports leaks.
    """

    completed = subprocess.run(
        [sys.executable, str(TRACE_CHECKER), "--triage", str(trace_path)],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    required = ("errors=0", "leaked_object_ptrs=0", "leaked_string_ptrs=0")
    if completed.returncode != 0 or any(
        fragment not in completed.stdout for fragment in required
    ):
        raise LinkSetFailure(
            f"{context} failed trace validation:\n{completed.stdout}"
        )


def lifecycle_free_source_order(stderr: str) -> list[str]:
    """Return lifecycle fixture sources for terminal heap-string releases."""

    expected_names = {"leaf.l1", "provider.l1", "side_effect.l1", "main.l1"}
    sources: list[str] = []
    for line in stderr.splitlines():
        if (
            not line.startswith("[l0][arc] ")
            or "op=release" not in line
            or "kind=heap" not in line
            or "action=free" not in line
        ):
            continue
        match = ARC_LOCATION_RE.search(line)
        if match is None:
            continue
        source_name = Path(match.group(1)).name
        if source_name in expected_names:
            sources.append(source_name)
    return sources


def executable_path(root: Path, name: str) -> Path:
    """Return one host-appropriate executable path below `root`."""

    suffix = ".exe" if os.name == "nt" else ""
    return root / f"{name}{suffix}"


def create_windows_junction(
    link_path: Path,
    target_path: Path,
    context: str,
) -> None:
    """Create one Windows directory junction for an integration fixture.

    Args:
        link_path: Junction path to create.
        target_path: Existing directory that the junction targets.
        context: Human-readable fixture description.

    Raises:
        LinkSetFailure: If `mklink` cannot create the junction.
    """

    # Keep `/c` command words separate so Python quotes each path for
    # `cmd.exe` instead of backslash-escaping quotes in one combined payload.
    created = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(link_path),
            str(target_path),
        ],
        cwd=link_path.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        raise LinkSetFailure(
            f"cannot create {context}:\n"
            f"link={link_path}\n"
            f"target={target_path}\n"
            f"status={created.returncode}\n"
            f"{created.stdout}"
        )


def assert_no_link_transactions(root: Path) -> None:
    """Require that no standalone-link transaction remains below `root`.

    Args:
        root: Per-run output tree.

    Raises:
        LinkSetFailure: If a hidden transaction directory remains.
    """

    leftovers = sorted(root.rglob(".l1c-link-*"))
    if leftovers:
        raise LinkSetFailure(
            "leftover link transaction directories: "
            + ", ".join(str(path) for path in leftovers)
        )


def capture_input_bytes(paths: list[Path]) -> dict[Path, bytes]:
    """Return exact bytes for caller-owned link inputs."""

    return {path: path.read_bytes() for path in paths}


def capture_link_input_bytes(
    dea_objects: list[Path],
    foreign_objects: list[Path] | None = None,
) -> dict[Path, bytes]:
    """Capture every authoritative interface and opaque caller input."""

    paths: list[Path] = []
    for object_path in dea_objects:
        paths.extend((object_path, sibling_interface(object_path)))
    paths.extend(foreign_objects or [])
    return capture_input_bytes(paths)


def assert_inputs_unchanged(captured: dict[Path, bytes]) -> None:
    """Require caller-owned link inputs to remain byte-identical."""

    for path, expected in captured.items():
        if not path.is_file() or path.read_bytes() != expected:
            raise LinkSetFailure(f"standalone linking changed caller input: {path}")


def create_final_link_probe(
    c_compiler: str,
    probe_root: Path,
    marker_path: Path,
    sentinel: str,
    *,
    partial_output: bytes | None = None,
) -> Path:
    """Create a compiler proxy that delegates wrapper compilation only.

    The proxy records final-link arguments as JSON, optionally writes a partial
    direct output, emits `sentinel`, and deliberately fails the final command.
    """

    probe_root.mkdir(parents=True, exist_ok=True)
    helper = probe_root / "compiler_probe.py"
    helper.write_text(
        "from pathlib import Path\n"
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "real_compiler = sys.argv[1]\n"
        "marker_path = Path(sys.argv[2])\n"
        "sentinel = sys.argv[3]\n"
        "partial_hex = sys.argv[4]\n"
        "args = sys.argv[5:]\n"
        "if '-c' in args:\n"
        "    completed = subprocess.run([real_compiler, *args], check=False)\n"
        "    raise SystemExit(completed.returncode)\n"
        "marker_path.write_text(json.dumps(args), encoding='utf-8')\n"
        "if partial_hex:\n"
        "    output_index = len(args) - 1 - args[::-1].index('-o')\n"
        "    Path(args[output_index + 1]).write_bytes(bytes.fromhex(partial_hex))\n"
        "sys.stderr.write(sentinel + '\\n')\n"
        "raise SystemExit(97)\n",
        encoding="utf-8",
    )

    real_compiler = str(Path(c_compiler).resolve())
    partial_hex = "" if partial_output is None else partial_output.hex()
    if os.name == "nt":
        proxy = probe_root / (Path(c_compiler).stem + ".cmd")
        proxy.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "{helper}" "{real_compiler}" '
            f'"{marker_path}" "{sentinel}" "{partial_hex}" %*\r\n'
            "exit /b %ERRORLEVEL%\r\n",
            encoding="utf-8",
        )
        return proxy

    proxy = probe_root / Path(c_compiler).name
    proxy.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(sys.executable)} {shlex.quote(str(helper))} "
        f"{shlex.quote(real_compiler)} {shlex.quote(str(marker_path))} "
        f"{shlex.quote(sentinel)} {shlex.quote(partial_hex)} \"$@\"\n",
        encoding="utf-8",
    )
    proxy.chmod(0o755)
    return proxy


def recorded_final_args(marker_path: Path, context: str) -> list[str]:
    """Load one compiler probe's final-link argument vector."""

    if not marker_path.is_file():
        raise LinkSetFailure(f"{context} did not reach the final host command")
    value = json.loads(marker_path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise LinkSetFailure(f"{context} recorded malformed final arguments: {value!r}")
    return value


def normalized_host_path(raw: str | Path) -> str:
    """Normalize one recorded host path for cross-platform comparison."""

    return os.path.normcase(os.path.normpath(str(raw)))


def expected_default_runtime_inputs(
    compiler: Path,
    c_compiler: str,
) -> list[Path]:
    """Return the expected default runtime-native input order."""

    compiler_name = Path(c_compiler).stem.lower()
    if "tcc" in compiler_name:
        object_dir = compiler.parent.parent / "runtime" / "tcc" / "default"
        object_names = (
            "dea_rt_panic.o",
            "dea_rt_sys.o",
            "dea_rt_math.o",
            "dea_rt_rand.o",
            "dea_rt_string.o",
            "dea_rt_alloc.o",
            "dea_rt_io.o",
            "dea_rt_hash.o",
            "dea_rt_time.o",
        )
        object_paths = [object_dir / name for name in object_names]
        if all(path.is_file() for path in object_paths):
            return object_paths
    return [compiler.parent.parent / "lib" / "libdea_rt.a"]


def build_primary_objects(
    compiler: Path,
    c_compiler: str,
    artifact_root: Path,
) -> dict[str, Path]:
    """Compile the main standalone-link fixture set."""

    modules = (
        "linkset.leaf",
        "linkset.provider",
        "linkset.main",
        "linkset.other_entry",
        "linkset.no_entry",
        "linkset.foreign_entry",
    )
    return {
        module_name: compile_module(
            compiler,
            c_compiler,
            FIXTURES,
            artifact_root,
            module_name,
        )
        for module_name in modules
    }


def test_missing_sibling_interface(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A positional Dea object cannot link without its sibling interface."""

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    missing_interface = sibling_interface(objects["linkset.main"])
    interface_bytes = missing_interface.read_bytes()
    missing_interface.unlink()
    output = executable_path(root, "missing sibling interface")
    try:
        completed = run_link(compiler, c_compiler, root, inputs, output)
        require_link_failure(
            completed,
            "missing sibling interface",
            "drv-0074",
            str(missing_interface),
        )
        if output.exists():
            raise LinkSetFailure(
                "missing-sibling failure published an executable"
            )
    finally:
        missing_interface.write_bytes(interface_bytes)
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_lifecycle_order_and_arc_cleanup(
    compiler: Path,
    c_compiler: str,
    root: Path,
) -> None:
    """Lifecycle initializers and ARC finalizers execute in graph order."""

    artifact_root = root / "lifecycle objects"
    lifecycle_objects = {
        module_name: compile_module(
            compiler,
            c_compiler,
            FIXTURES,
            artifact_root,
            module_name,
            trace_arc=True,
        )
        for module_name in (
            "lifecycle.leaf",
            "lifecycle.provider",
            "lifecycle.side_effect",
            "lifecycle.main",
        )
    }
    observer = compile_foreign_object(
        c_compiler,
        FIXTURES / "lifecycle_observer.c",
        artifact_root / "lifecycle observer.o",
    )
    inputs = [
        lifecycle_objects["lifecycle.main"],
        lifecycle_objects["lifecycle.side_effect"],
        lifecycle_objects["lifecycle.leaf"],
        lifecycle_objects["lifecycle.provider"],
        observer,
    ]
    before = capture_link_input_bytes(inputs[:-1], [observer])
    output = executable_path(root, "lifecycle graph")
    linked = run_link(
        compiler,
        c_compiler,
        root,
        inputs[:-1],
        output,
        foreign_objects=[observer],
        trace_arc=True,
    )
    require_link_success(linked, output, "traced lifecycle graph link")

    executed = subprocess.run(
        [str(output)],
        cwd=output.parent,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if executed.returncode != 0:
        raise LinkSetFailure(
            "traced lifecycle graph executable returned "
            f"{executed.returncode}, expected 0:\n"
            f"stdout:\n{executed.stdout}\n"
            f"stderr:\n{executed.stderr}"
        )

    free_order = lifecycle_free_source_order(executed.stderr)
    expected_free_order = [
        "main.l1",
        "side_effect.l1",
        "provider.l1",
        "leaf.l1",
    ]
    if free_order != expected_free_order:
        raise LinkSetFailure(
            "lifecycle finalization source order mismatch: "
            f"expected {expected_free_order!r}, got {free_order!r}\n"
            f"stderr:\n{executed.stderr}"
        )

    trace_path = root / "lifecycle trace.stderr"
    trace_path.write_text(executed.stderr, encoding="utf-8")
    require_clean_trace(trace_path, "traced lifecycle graph")
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_link_transaction_mode(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A POSIX standalone-link transaction is created with mode 0700."""

    if os.name == "nt":
        return

    probe_root = root / "transaction mode probe"
    probe_root.mkdir()
    mode_marker = probe_root / "observed mode.txt"
    mode_helper = probe_root / "record_mode.py"
    mode_helper.write_text(
        "from pathlib import Path\n"
        "import stat\n"
        "import sys\n"
        "\n"
        "wrapper_path = Path(sys.argv[1])\n"
        "marker_path = Path(sys.argv[2])\n"
        "mode = stat.S_IMODE(wrapper_path.parent.stat().st_mode)\n"
        'marker_path.write_text(f"{mode:04o}\\n", encoding="ascii")\n',
        encoding="utf-8",
    )

    compiler_probe = probe_root / Path(c_compiler).name
    compiler_probe.write_text(
        "#!/bin/sh\n"
        "for dea_arg do\n"
        '    if [ "${dea_arg##*/}" = "wrapper.c" ]; then\n'
        f"        {shlex.quote(sys.executable)} "
        f"{shlex.quote(str(mode_helper))} "
        f'"$dea_arg" {shlex.quote(str(mode_marker))} || exit $?\n'
        "    fi\n"
        "done\n"
        f"exec {shlex.quote(str(Path(c_compiler).resolve()))} \"$@\"\n",
        encoding="utf-8",
    )
    compiler_probe.chmod(0o755)

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(root, "transaction mode")
    previous_umask = os.umask(0)
    try:
        completed = run_link(
            compiler,
            str(compiler_probe),
            root,
            inputs,
            output,
        )
    finally:
        os.umask(previous_umask)

    require_link_success(completed, output, "POSIX transaction-mode link")
    require_program_status(output, 7, "POSIX transaction-mode executable")
    if not mode_marker.is_file():
        raise LinkSetFailure("compiler probe did not observe wrapper transaction")
    observed_mode = int(mode_marker.read_text(encoding="ascii").strip(), 8)
    if observed_mode != 0o700:
        raise LinkSetFailure(
            "standalone-link transaction mode was "
            f"{observed_mode:04o}, expected 0700"
        )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_trusted_output_parent_alias(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A trusted symlink alias may name the existing output parent."""

    if os.name == "nt":
        return

    physical_parent = root / "physical output parent"
    physical_parent.mkdir()
    alias_parent = root / "trusted output parent alias"
    try:
        alias_parent.symlink_to(physical_parent, target_is_directory=True)
    except OSError as exc:
        raise LinkSetFailure(
            f"cannot create trusted output-parent alias fixture: {exc}"
        ) from exc

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(alias_parent, "through trusted alias")
    completed = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        output,
    )
    require_link_success(completed, output, "trusted output-parent alias link")
    require_program_status(output, 7, "trusted output-parent alias executable")
    physical_output = executable_path(physical_parent, "through trusted alias")
    if not physical_output.is_file():
        raise LinkSetFailure(
            "trusted output-parent alias did not publish in the physical parent"
        )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_opaque_inputs_use_original_final_paths(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
    foreign_main: Path,
) -> None:
    """Opaque positional and foreign bytes reach the final host command."""

    probe_root = root / "opaque original-path probe"
    opaque_main = probe_root / "renamed malformed main.o"
    opaque_main.parent.mkdir(parents=True)
    opaque_main.write_bytes(b"regular bytes that are not a native object\n")
    shutil.copy2(
        sibling_interface(objects["linkset.main"]),
        sibling_interface(opaque_main),
    )

    if sys.platform == "darwin":
        control_source = FIXTURES / "foreign_linker_option_darwin.s"
    elif os.name == "nt":
        control_source = FIXTURES / "foreign_directive_windows.s"
    elif sys.platform.startswith("linux"):
        control_source = FIXTURES / "foreign_dependent_libraries_elf.s"
    else:
        control_source = None
    control_object = probe_root / "opaque linker-control foreign.o"
    if control_source is None:
        control_object.write_bytes(b"caller-asserted opaque foreign bytes\n")
    else:
        compile_foreign_assembly(c_compiler, control_source, control_object)

    marker = probe_root / "final args.json"
    sentinel = "DEA_OPAQUE_FINAL_SENTINEL"
    partial_output = b"partial direct host output\n"
    compiler_probe = create_final_link_probe(
        c_compiler,
        probe_root / "compiler proxy",
        marker,
        sentinel,
        partial_output=partial_output,
    )

    dea_inputs = [
        opaque_main,
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    foreign_inputs = [foreign_main, control_object]
    before = capture_link_input_bytes(dea_inputs, foreign_inputs)
    output = executable_path(root, "opaque direct output")
    completed = run_compiler(
        compiler,
        root,
        "--link",
        str(opaque_main),
        "--foreign-object",
        str(foreign_main),
        str(objects["linkset.provider"]),
        "-Cf",
        str(control_object),
        str(objects["linkset.leaf"]),
        "--c-compiler",
        str(compiler_probe),
        "--output",
        str(output),
    )
    require_link_failure(
        completed,
        "opaque original-path final link",
        "l1c-2109",
        sentinel,
    )
    failure_text = combined_output(completed)
    for retired_code in ("l1c-2097", "l1c-2098", "l1c-2110"):
        if retired_code in failure_text:
            raise LinkSetFailure(
                "opaque input failed through retired preflight diagnostic "
                f"{retired_code}:\n{completed.stderr}"
            )

    final_args = recorded_final_args(marker, "opaque original-path probe")
    expected_callers = [
        opaque_main,
        foreign_main,
        objects["linkset.provider"],
        control_object,
        objects["linkset.leaf"],
    ]
    if not final_args or Path(final_args[0]).name != "wrapper.o":
        raise LinkSetFailure(
            f"final host command was not wrapper-first: {final_args!r}"
        )
    actual_callers = final_args[1 : 1 + len(expected_callers)]
    if [normalized_host_path(path) for path in actual_callers] != [
        normalized_host_path(path) for path in expected_callers
    ]:
        raise LinkSetFailure(
            "final caller input order/path mismatch:\n"
            f"expected={expected_callers!r}\nactual={actual_callers!r}"
        )
    if any(Path(path).name.startswith("input-") for path in final_args):
        raise LinkSetFailure(
            "final host command contains a retired transaction-owned input copy: "
            f"{final_args!r}"
        )

    tail = final_args[1 + len(expected_callers) :]
    runtime_inputs = expected_default_runtime_inputs(compiler, c_compiler)
    expected_tail = [
        *(str(path) for path in runtime_inputs),
        "-lm",
        "-o",
        str(output),
    ]
    if [normalized_host_path(path) for path in tail] != [
        normalized_host_path(path) for path in expected_tail
    ]:
        raise LinkSetFailure(
            "runtime/math/output final argument order mismatch:\n"
            f"expected={expected_tail!r}\nactual={tail!r}"
        )
    if not output.is_file() or output.read_bytes() != partial_output:
        raise LinkSetFailure(
            "failed final host command did not retain its direct partial output"
        )

    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_default_host_runtime_inputs(
    compiler: Path,
    root: Path,
) -> None:
    """The default compiler links against its compatible runtime inputs."""

    artifact_root = root / "default_host_objects"
    objects = {
        module_name: compile_module_with_default_host(
            compiler,
            FIXTURES,
            artifact_root,
            module_name,
        )
        for module_name in (
            "linkset.leaf",
            "linkset.provider",
            "linkset.main",
        )
    }
    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(root, "default_host")
    completed = run_link_with_default_host(compiler, root, inputs, output)
    require_link_success(completed, output, "default-host standalone link")
    require_program_status(output, 7, "default-host standalone executable")
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_sibling_interface_validation(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Nonregular, non-UTF-8, malformed, and corrupt siblings fail early."""

    case_root = root / "invalid sibling interfaces"
    source_object = objects["linkset.no_entry"]

    nonregular_object = case_root / "nonregular" / "module.o"
    nonregular_object.parent.mkdir(parents=True)
    shutil.copy2(source_object, nonregular_object)
    sibling_interface(nonregular_object).mkdir()

    utf8_object = case_root / "invalid utf8" / "module.o"
    utf8_object.parent.mkdir(parents=True)
    shutil.copy2(source_object, utf8_object)
    sibling_interface(utf8_object).write_bytes(b"\xff\xfe\x00")

    malformed_object = case_root / "malformed" / "module.o"
    malformed_object.parent.mkdir(parents=True)
    shutil.copy2(source_object, malformed_object)
    sibling_interface(malformed_object).write_text(
        "module interface\n",
        encoding="utf-8",
    )

    corrupt_object = copy_dea_pair(
        source_object,
        case_root / "bad fingerprint" / "module.o",
    )
    corrupt_interface = sibling_interface(corrupt_object)
    corrupt_text = corrupt_interface.read_text(encoding="utf-8")
    fingerprint_match = re.search(
        r'fingerprint "sip13:([0-9a-f]{16})";',
        corrupt_text,
    )
    if fingerprint_match is None:
        raise LinkSetFailure(
            f"cannot locate test interface fingerprint: {corrupt_interface}"
        )
    digest = fingerprint_match.group(1)
    replacement = ("0" if digest[0] != "0" else "1") + digest[1:]
    corrupt_interface.write_text(
        corrupt_text[: fingerprint_match.start(1)]
        + replacement
        + corrupt_text[fingerprint_match.end(1) :],
        encoding="utf-8",
    )

    cases = (
        (nonregular_object, "nonregular sibling", "drv-0075"),
        (utf8_object, "invalid UTF-8 sibling", "drv-0076"),
        (malformed_object, "malformed sibling", "par-0562"),
        (corrupt_object, "bad-fingerprint sibling", "sig-0282"),
    )
    for index, (object_path, context, diagnostic) in enumerate(cases):
        output = executable_path(case_root, f"invalid sibling {index}")
        completed = run_link(
            compiler,
            c_compiler,
            root,
            [object_path],
            output,
        )
        require_link_failure(completed, context, diagnostic)
        if output.exists():
            raise LinkSetFailure(f"{context} published an executable")
        assert_no_link_transactions(root)


def test_positional_suffix_and_arbitrary_basename(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Path-only sibling derivation accepts arbitrary valid basenames."""

    case_root = root / "positional suffix contract"
    renamed_main = copy_dea_pair(
        objects["linkset.main"],
        case_root / "arbitrary caller basename.o",
    )
    inputs = [
        renamed_main,
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(case_root, "arbitrary basename executable")
    completed = run_link(compiler, c_compiler, root, inputs, output)
    require_link_success(completed, output, "arbitrary-basename pair link")
    require_program_status(output, 7, "arbitrary-basename pair executable")
    assert_inputs_unchanged(before)

    invalid_suffix = case_root / "invalid suffix.obj"
    shutil.copy2(objects["linkset.main"], invalid_suffix)
    invalid_output = executable_path(case_root, "invalid suffix output")
    invalid = run_link(
        compiler,
        c_compiler,
        root,
        [invalid_suffix],
        invalid_output,
    )
    require_link_failure(
        invalid,
        "non-.o positional suffix",
        "l1c-2097",
        "terminal '.o' suffix",
    )

    empty_stem = case_root / ".o"
    shutil.copy2(objects["linkset.main"], empty_stem)
    empty_output = executable_path(case_root, "empty stem output")
    empty = run_link(
        compiler,
        c_compiler,
        root,
        [empty_stem],
        empty_output,
    )
    require_link_failure(
        empty,
        "empty-stem positional suffix",
        "l1c-2097",
        "nonempty basename stem",
    )
    assert_no_link_transactions(root)


def test_entry_selection(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Multiple entry candidates fail unless one canonical module is selected."""

    inputs = [
        objects["linkset.other_entry"],
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    ambiguous_output = executable_path(root, "ambiguous entry")
    ambiguous = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        ambiguous_output,
    )
    require_link_failure(
        ambiguous,
        "multiple inferred entries",
        "l1c-2104",
        "linkset.main",
        "linkset.other_entry",
    )
    if ambiguous_output.exists():
        raise LinkSetFailure("multiple-entry failure published an executable")

    selected_output = executable_path(root, "selected entry")
    selected = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        selected_output,
        entry="linkset.main",
        short_aliases=True,
    )
    require_link_success(selected, selected_output, "explicit entry selection")
    require_program_status(selected_output, 7, "explicitly selected executable")
    assert_no_link_transactions(root)


def test_explicit_foreign_object(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
    foreign_answer: Path,
) -> None:
    """A caller-asserted provider satisfies an unmangled extern explicitly."""

    output = executable_path(root, "foreign provider")
    inputs = [objects["linkset.foreign_entry"], foreign_answer]
    before = capture_link_input_bytes(
        [objects["linkset.foreign_entry"]],
        [foreign_answer],
    )
    completed = run_link(
        compiler,
        c_compiler,
        root,
        [objects["linkset.foreign_entry"]],
        output,
        foreign_objects=[foreign_answer],
        foreign_equals=True,
        short_aliases=True,
    )
    require_link_success(completed, output, "explicit foreign provider link")
    require_program_status(output, 37, "foreign-provider executable")
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_typed_operand_failures(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
    foreign_answer: Path,
    option_shaped_foreign: Path,
) -> None:
    """Typed native operands retain their distinct CLI roles."""

    positional_output = executable_path(root, "implicit foreign")
    positional = run_link(
        compiler,
        c_compiler,
        root,
        [foreign_answer],
        positional_output,
    )
    require_link_failure(
        positional,
        "foreign object used as a positional Dea object",
        "drv-0074",
        str(sibling_interface(foreign_answer)),
    )
    if positional_output.exists():
        raise LinkSetFailure("missing-sibling positional failure published output")

    smuggled_output = executable_path(root, "smuggled foreign")
    smuggled = run_link(
        compiler,
        c_compiler,
        root,
        [objects["linkset.foreign_entry"]],
        smuggled_output,
        c_options=str(foreign_answer),
    )
    require_link_failure(
        smuggled,
        "foreign object smuggled through C options",
        "l1c-210",
    )
    if smuggled_output.exists():
        raise LinkSetFailure("C-options input bypass published output")

    option_path_output = executable_path(root, "option-shaped foreign")
    option_path = run_link(
        compiler,
        c_compiler,
        option_shaped_foreign.parent,
        [objects["linkset.foreign_entry"]],
        option_path_output,
        foreign_objects=[Path(option_shaped_foreign.name)],
    )
    require_link_failure(
        option_path,
        "option-shaped foreign object path",
        "l1c-2109",
    )
    if option_path_output.exists():
        raise LinkSetFailure("option-shaped input path was reinterpreted")

    no_dea_output = executable_path(root, "no dea objects")
    no_dea = run_link(
        compiler,
        c_compiler,
        root,
        [],
        no_dea_output,
        foreign_objects=[foreign_answer],
    )
    require_link_failure(
        no_dea,
        "foreign-only link set",
        "l1c-2095",
        "dea",
        "object",
    )
    if no_dea_output.exists():
        raise LinkSetFailure("foreign-only failure published output")
    assert_no_link_transactions(root)


def test_wrapper_embedded_linker_control_reaches_final_host(
    compiler: Path,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A wrapper linker control is left to the final host command."""

    if sys.platform != "darwin":
        return

    clang = shutil.which("clang")
    if clang is None:
        raise LinkSetFailure(
            "wrapper linker-control regression requires Apple clang"
        )

    probe_root = root / "wrapper linker control probe"
    probe_root.mkdir()
    final_link_marker = probe_root / "final args.json"
    sentinel = "DEA_WRAPPER_CONTROL_FINAL_SENTINEL"
    compiler_probe = create_final_link_probe(
        clang,
        probe_root / "compiler proxy",
        final_link_marker,
        sentinel,
    )

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(root, "wrapper embedded linker control")
    completed = run_link(
        compiler,
        str(compiler_probe),
        root,
        inputs,
        output,
        c_options="-Xclang --dependent-lib=Security",
    )
    require_link_failure(
        completed,
        "wrapper-embedded Mach-O linker control",
        "l1c-2109",
        sentinel,
    )
    if "l1c-2110" in combined_output(completed):
        raise LinkSetFailure(
            "wrapper linker control triggered the retired preflight diagnostic"
        )
    recorded_final_args(
        final_link_marker,
        "wrapper linker-control final-host probe",
    )
    if output.exists():
        raise LinkSetFailure(
            "deliberately failed wrapper-control final link published output"
        )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_windows_command_value_rejection(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Quote-bearing Windows C options fail before transaction allocation."""

    if os.name != "nt":
        return

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    sentinel = root / "windows-command-injection-sentinel.txt"
    malicious_option = (
        '-DDEA_LINK_TEST=x"&echo.injected>'
        f"{sentinel.name}&rem"
    )
    output = executable_path(root, "unsafe windows command value")
    completed = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        output,
        c_options=malicious_option,
    )
    require_link_failure(
        completed,
        "unsafe Windows command value",
        "l1c-2106",
    )
    if sentinel.exists():
        raise LinkSetFailure(
            "unsafe Windows command value executed an injected command"
        )
    if output.exists():
        raise LinkSetFailure(
            "unsafe Windows command value published an executable"
        )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_windows_spaced_compiler_path(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A compiler executable reached through a spaced path links successfully."""

    if os.name != "nt":
        return

    compiler_target = Path(c_compiler).resolve().parent
    compiler_alias = root / "host compiler path with spaces"
    create_windows_junction(
        compiler_alias,
        compiler_target,
        "spaced compiler-path junction fixture",
    )

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    output = executable_path(root, "spaced compiler executable")
    spaced_compiler = compiler_alias / Path(c_compiler).name
    try:
        completed = run_link(
            compiler,
            str(spaced_compiler),
            root,
            inputs,
            output,
        )
        require_link_success(
            completed,
            output,
            "spaced Windows compiler-path link",
        )
        require_program_status(
            output,
            7,
            "spaced Windows compiler-path executable",
        )
    finally:
        if os.path.lexists(compiler_alias):
            try:
                compiler_alias.rmdir()
            except OSError as exc:
                raise LinkSetFailure(
                    f"cannot remove spaced compiler-path junction: {exc}"
                ) from exc

    if os.path.lexists(compiler_alias):
        raise LinkSetFailure(
            "spaced compiler-path junction remained after cleanup"
        )
    if not Path(c_compiler).is_file():
        raise LinkSetFailure(
            "spaced compiler-path cleanup changed the real compiler"
        )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_graph_and_entry_failures(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Missing, duplicate, and entry-free Dea link sets fail before linking."""

    missing_output = executable_path(root, "missing provider")
    missing = run_link(
        compiler,
        c_compiler,
        root,
        [objects["linkset.main"], objects["linkset.leaf"]],
        missing_output,
    )
    require_link_failure(
        missing,
        "missing provider",
        "l1c-2101",
        "linkset.provider",
    )
    if missing_output.exists():
        raise LinkSetFailure("missing-provider failure published output")

    duplicate_output = executable_path(root, "duplicate module")
    duplicate = run_link(
        compiler,
        c_compiler,
        root,
        [
            objects["linkset.main"],
            objects["linkset.provider"],
            objects["linkset.leaf"],
            objects["linkset.leaf"],
        ],
        duplicate_output,
    )
    require_link_failure(
        duplicate,
        "duplicate module identity",
        "l1c-2100",
        "linkset.leaf",
    )
    if duplicate_output.exists():
        raise LinkSetFailure("duplicate-module failure published output")

    no_entry_output = executable_path(root, "no entry")
    no_entry = run_link(
        compiler,
        c_compiler,
        root,
        [objects["linkset.no_entry"]],
        no_entry_output,
    )
    require_link_failure(
        no_entry,
        "entry-free link set",
        "l1c-2104",
        "no entry module",
    )
    if no_entry_output.exists():
        raise LinkSetFailure("entry-free failure published output")

    missing_output_option = run_compiler(
        compiler,
        root,
        "--link",
        str(objects["linkset.main"]),
        str(objects["linkset.provider"]),
        str(objects["linkset.leaf"]),
    )
    require_link_failure(
        missing_output_option,
        "missing standalone output",
        "l1c-2096",
        "output",
    )
    assert_no_link_transactions(root)


def test_output_input_alias_rejection(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """An output cannot alias a native input or consumed interface."""

    case_root = root / "output input aliases"
    copied_main = copy_dea_pair(
        objects["linkset.main"],
        case_root / "copied main.o",
    )
    inputs = [
        copied_main,
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    exact = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        copied_main,
    )
    require_link_failure(
        exact,
        "output equal to caller input",
        "l1c-2105",
        "aliases caller native input",
    )
    assert_inputs_unchanged(before)

    hard_link_output = case_root / "hard-linked native output.o"
    try:
        os.link(copied_main, hard_link_output)
    except OSError as exc:
        raise LinkSetFailure(
            f"cannot create output/input hard-link fixture: {exc}"
        ) from exc
    hard_link = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        hard_link_output,
    )
    require_link_failure(
        hard_link,
        "output hard-linked to caller input",
        "l1c-2105",
        "aliases caller native input",
    )
    assert_inputs_unchanged(before)

    consumed_interface = sibling_interface(copied_main)
    exact_interface = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        consumed_interface,
    )
    require_link_failure(
        exact_interface,
        "output equal to consumed sibling interface",
        "l1c-2105",
        "aliases consumed sibling interface",
    )
    assert_inputs_unchanged(before)

    hard_link_interface_output = case_root / "hard-linked interface output"
    try:
        os.link(consumed_interface, hard_link_interface_output)
    except OSError as exc:
        raise LinkSetFailure(
            f"cannot create output/interface hard-link fixture: {exc}"
        ) from exc
    hard_link_interface = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        hard_link_interface_output,
    )
    require_link_failure(
        hard_link_interface,
        "output hard-linked to consumed sibling interface",
        "l1c-2105",
        "aliases consumed sibling interface",
    )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_runtime_header_alias_rejection(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """Output identity checks protect a test-owned resolved runtime header."""

    case_root = root / "runtime header aliases"
    include_dir = case_root / "include"
    include_dir.mkdir(parents=True)
    runtime_header = include_dir / "dea_rt.h"
    shutil.copy2(RUNTIME_HEADER, runtime_header)

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    before[runtime_header] = runtime_header.read_bytes()

    exact = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        runtime_header,
        runtime_include=include_dir,
    )
    require_link_failure(
        exact,
        "output equal to resolved runtime header",
        "l1c-2105",
        "aliases resolved runtime header",
    )
    assert_inputs_unchanged(before)

    hard_link_output = case_root / "hard-linked runtime header output"
    try:
        os.link(runtime_header, hard_link_output)
    except OSError as exc:
        raise LinkSetFailure(
            f"cannot create output/runtime-header hard-link fixture: {exc}"
        ) from exc
    hard_link = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        hard_link_output,
        runtime_include=include_dir,
    )
    require_link_failure(
        hard_link,
        "output hard-linked to resolved runtime header",
        "l1c-2105",
        "aliases resolved runtime header",
    )
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_output_symlink_rejection(
    compiler: Path,
    c_compiler: str,
    root: Path,
    objects: dict[str, Path],
) -> None:
    """A final-output symlink or junction is rejected without target changes."""

    if os.name == "nt":
        inputs = [
            objects["linkset.main"],
            objects["linkset.provider"],
            objects["linkset.leaf"],
        ]
        before = capture_link_input_bytes(inputs)
        target = root / "output junction target"
        target.mkdir()
        target_marker = target / "caller-owned.txt"
        target_bytes = b"caller-owned junction target\n"
        target_marker.write_bytes(target_bytes)
        output = executable_path(root, "junction final output")
        create_windows_junction(
            output,
            target,
            "final-output NTFS junction fixture",
        )
        try:
            try:
                original_tag = os.lstat(output).st_reparse_tag
            except (AttributeError, OSError) as exc:
                raise LinkSetFailure(
                    "cannot inspect final-output NTFS junction fixture: "
                    f"{exc}"
                ) from exc

            completed = run_link(
                compiler,
                c_compiler,
                root,
                inputs,
                output,
            )
            require_link_failure(
                completed,
                "junction final output",
                "l1c-2105",
                "absent or a regular file",
            )
            try:
                final_tag = os.lstat(output).st_reparse_tag
            except (AttributeError, OSError) as exc:
                raise LinkSetFailure(
                    "standalone linking removed the final-output junction: "
                    f"{exc}"
                ) from exc
            if final_tag != original_tag or not os.path.samefile(
                output, target
            ):
                raise LinkSetFailure(
                    "standalone linking changed the final-output junction"
                )
            if target_marker.read_bytes() != target_bytes:
                raise LinkSetFailure(
                    "standalone linking changed the output junction target"
                )
            assert_inputs_unchanged(before)
            assert_no_link_transactions(root)
        finally:
            if os.path.lexists(output):
                try:
                    output.rmdir()
                except OSError as exc:
                    raise LinkSetFailure(
                        "cannot remove verified final-output junction "
                        f"fixture: {exc}"
                    ) from exc
        if os.path.lexists(output):
            raise LinkSetFailure(
                "final-output junction remained after fixture cleanup"
            )
        if target_marker.read_bytes() != target_bytes:
            raise LinkSetFailure(
                "junction fixture cleanup changed the target"
            )
        return

    inputs = [
        objects["linkset.main"],
        objects["linkset.provider"],
        objects["linkset.leaf"],
    ]
    before = capture_link_input_bytes(inputs)
    target = root / "output symlink target"
    target_bytes = b"caller-owned output target\n"
    target.write_bytes(target_bytes)
    output = executable_path(root, "symlinked final output")
    try:
        output.symlink_to(target)
    except OSError as exc:
        raise LinkSetFailure(
            f"cannot create final-output symlink fixture: {exc}"
        ) from exc
    original_link = os.readlink(output)

    completed = run_link(
        compiler,
        c_compiler,
        root,
        inputs,
        output,
    )
    require_link_failure(
        completed,
        "symlinked final output",
        "l1c-2105",
        "absent or a regular file",
    )
    if not output.is_symlink() or os.readlink(output) != original_link:
        raise LinkSetFailure("standalone linking changed final-output symlink")
    if target.read_bytes() != target_bytes:
        raise LinkSetFailure("standalone linking changed output symlink target")
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def test_stale_provider_fingerprint(
    compiler: Path,
    c_compiler: str,
    root: Path,
    consumer: Path,
    matching_provider: Path,
    stale_interface_provider: Path,
) -> None:
    """A mismatched sibling interface, not object bytes, fails pre-link."""

    mixed_provider = root / "stale sibling" / "mixed provider.o"
    mixed_provider.parent.mkdir(parents=True)
    shutil.copy2(matching_provider, mixed_provider)
    shutil.copy2(
        sibling_interface(stale_interface_provider),
        sibling_interface(mixed_provider),
    )
    inputs = [consumer, mixed_provider]
    before = capture_link_input_bytes(inputs)
    output = executable_path(root, "stale provider")
    completed = run_link(compiler, c_compiler, root, inputs, output)
    require_link_failure(
        completed,
        "stale provider fingerprint",
        "l1c-2102",
        "linkset.stale.provider",
        "fingerprint",
    )
    if output.exists():
        raise LinkSetFailure("stale-provider failure published output")
    assert_inputs_unchanged(before)
    assert_no_link_transactions(root)


def main() -> int:
    """Run the standalone link-set integration matrix."""

    compiler = stage1_compiler()
    if not compiler.is_file():
        print(
            f"l1c_stage1_link_set_test: FAIL: missing compiler: {compiler}",
            file=sys.stderr,
        )
        return 1

    root = Path(tempfile.mkdtemp(prefix="l1c_stage1_link_set_"))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    try:
        c_compiler = resolve_c_compiler()
        workspace = root / "workspace with spaces"
        workspace.mkdir()
        artifact_root = workspace / "dea objects"
        stale_v1_root = workspace / "stale v1 objects"
        stale_v2_root = workspace / "stale v2 objects"
        foreign_root = workspace / "foreign objects"

        objects = build_primary_objects(
            compiler,
            c_compiler,
            artifact_root,
        )
        stale_v1_provider = compile_module(
            compiler,
            c_compiler,
            STALE_V1_FIXTURES,
            stale_v1_root,
            "linkset.stale.provider",
        )
        stale_consumer = compile_module(
            compiler,
            c_compiler,
            STALE_V1_FIXTURES,
            stale_v1_root,
            "linkset.stale.main",
        )
        stale_v2_provider = compile_module(
            compiler,
            c_compiler,
            STALE_V2_FIXTURES,
            stale_v2_root,
            "linkset.stale.provider",
        )
        foreign_answer = compile_foreign_object(
            c_compiler,
            FIXTURES / "foreign_answer.c",
            foreign_root / "foreign_actual.o",
        )
        foreign_main = compile_foreign_object(
            c_compiler,
            FIXTURES / "foreign_main.c",
            foreign_root / "foreign main.o",
        )
        option_shaped_foreign = compile_foreign_object(
            c_compiler,
            FIXTURES / "foreign_benign.c",
            foreign_root / "-Wl,foreign_actual.o",
        )

        test_missing_sibling_interface(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_lifecycle_order_and_arc_cleanup(
            compiler,
            c_compiler,
            workspace,
        )
        test_link_transaction_mode(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_trusted_output_parent_alias(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_opaque_inputs_use_original_final_paths(
            compiler,
            c_compiler,
            workspace,
            objects,
            foreign_main,
        )
        test_default_host_runtime_inputs(compiler, root)
        test_sibling_interface_validation(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_positional_suffix_and_arbitrary_basename(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_entry_selection(compiler, c_compiler, workspace, objects)
        test_explicit_foreign_object(
            compiler,
            c_compiler,
            workspace,
            objects,
            foreign_answer,
        )
        test_typed_operand_failures(
            compiler,
            c_compiler,
            workspace,
            objects,
            foreign_answer,
            option_shaped_foreign,
        )
        test_wrapper_embedded_linker_control_reaches_final_host(
            compiler,
            workspace,
            objects,
        )
        test_windows_command_value_rejection(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_windows_spaced_compiler_path(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_graph_and_entry_failures(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_output_input_alias_rejection(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_runtime_header_alias_rejection(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_output_symlink_rejection(
            compiler,
            c_compiler,
            workspace,
            objects,
        )
        test_stale_provider_fingerprint(
            compiler,
            c_compiler,
            workspace,
            stale_consumer,
            stale_v1_provider,
            stale_v2_provider,
        )

        if not stale_v1_provider.is_file():
            raise LinkSetFailure(
                "stale-provider setup unexpectedly removed the original object"
            )
    except LinkSetFailure as exc:
        keep_artifacts = True
        print(f"l1c_stage1_link_set_test: FAIL: {exc}", file=sys.stderr)
        print(f"l1c_stage1_link_set_test: artifacts={root}", file=sys.stderr)
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(root, ignore_errors=True)

    print("l1c_stage1_link_set_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
