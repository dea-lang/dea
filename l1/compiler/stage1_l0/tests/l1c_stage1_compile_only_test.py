#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for transactional L1 Stage 1 compile-only mode."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
FIXTURES = L1_ROOT / "compiler" / "stage1_l0" / "tests" / "fixtures"
DRIVER_FIXTURES = FIXTURES / "driver"
INTERFACE_FIXTURES = FIXTURES / "interface"
GRAPH_INTERFACES = FIXTURES / "module_graph" / "interfaces_first"
FINGERPRINT_RE = re.compile(
    r'^fingerprint "sip13:[0-9a-f]{16}";$', re.MULTILINE
)


class CompileOnlyFailure(RuntimeError):
    """Raised when one compile-only integration assertion fails."""


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path.

    Args:
        base: Extensionless tool path.

    Returns:
        Existing host launcher, or the expected launcher path when missing.
    """

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def stage1_compiler() -> Path:
    """Return the repo-local L1 Stage 1 compiler path."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def run_compiler(
    compiler: Path,
    cwd: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    """Run the Stage 1 compiler with captured UTF-8 text output.

    Args:
        compiler: Stage 1 launcher path.
        cwd: Working directory for default artifact placement.
        *args: Compiler arguments excluding the executable name.

    Returns:
        Completed compiler process with decoded output.
    """

    return subprocess.run(
        [str(compiler), *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def companions(object_path: Path) -> tuple[Path, Path, Path]:
    """Return C, object, and interface companions for one object path.

    Args:
        object_path: Canonical `.o` output path.

    Returns:
        Sibling C, object, and interface paths.
    """

    stem = object_path.with_suffix("")
    return stem.with_suffix(".c"), object_path, stem.with_suffix(".l1m")


def require_reusable_set(object_path: Path, module_name: str) -> tuple[bytes, bytes]:
    """Assert and return one reusable object/interface artifact set.

    Args:
        object_path: Expected object artifact.
        module_name: Expected canonical interface identity.

    Returns:
        Exact object and interface bytes.

    Raises:
        CompileOnlyFailure: If the set is missing, empty, or inconsistent.
    """

    _, actual_object, interface_path = companions(object_path)
    for path in (actual_object, interface_path):
        if not path.is_file():
            raise CompileOnlyFailure(f"missing compile-only artifact: {path}")

    object_bytes = actual_object.read_bytes()
    interface_bytes = interface_path.read_bytes()
    if not object_bytes or not interface_bytes:
        raise CompileOnlyFailure(f"empty compile-only artifact set for {object_path}")

    interface_text = interface_bytes.decode("utf-8")
    if f"module interface {module_name};" not in interface_text:
        raise CompileOnlyFailure(
            f"interface identity mismatch for {module_name}: {interface_text}"
        )
    if FINGERPRINT_RE.search(interface_text) is None:
        raise CompileOnlyFailure(
            f"missing canonical interface fingerprint for {module_name}"
        )
    return object_bytes, interface_bytes


def require_kept_c_set(
    object_path: Path,
    module_name: str,
) -> tuple[bytes, bytes, bytes]:
    """Assert and return a retained C plus reusable artifact set.

    Args:
        object_path: Expected object artifact.
        module_name: Expected canonical interface identity.

    Returns:
        Exact C, object, and interface bytes.

    Raises:
        CompileOnlyFailure: If retained C is missing or empty, or the reusable
            set is invalid.
    """

    c_path, _, _ = companions(object_path)
    if not c_path.is_file():
        raise CompileOnlyFailure(f"missing retained C artifact: {c_path}")
    c_bytes = c_path.read_bytes()
    if not c_bytes:
        raise CompileOnlyFailure(f"empty retained C artifact: {c_path}")
    object_bytes, interface_bytes = require_reusable_set(object_path, module_name)
    return c_bytes, object_bytes, interface_bytes


def global_object_symbols(object_path: Path) -> set[str]:
    """Return global symbols using the repository's cross-platform `nm` lane."""

    nm = shutil.which("nm")
    if nm is None:
        raise CompileOnlyFailure(
            "compile-only object-symbol coverage requires host tool 'nm'"
        )
    completed = subprocess.run(
        [nm, "-g", str(object_path)],
        cwd=L1_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            f"nm failed for compile-only object {object_path}:\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )

    symbols: set[str] = set()
    for line in completed.stdout.splitlines():
        fields = line.split()
        if fields and not line.rstrip().endswith(":"):
            symbols.add(fields[-1])
    return symbols


def assert_no_transactions(root: Path) -> None:
    """Assert no compile transaction directory remains below a test root.

    Args:
        root: Test output tree to inspect.

    Raises:
        CompileOnlyFailure: If a hidden transaction directory remains.
    """

    leftovers = sorted(root.rglob(".l1c-compile-*"))
    if leftovers:
        raise CompileOnlyFailure(
            "leftover compile transaction directories: "
            + ", ".join(str(path) for path in leftovers)
        )


def require_output_path_error(
    completed: subprocess.CompletedProcess[str],
    context: str,
) -> None:
    """Assert one compile-only output path fails only at the compile layer.

    Args:
        completed: Completed compiler process.
        context: Human-readable failing-path description.

    Raises:
        CompileOnlyFailure: If the result lacks `L1C-2033`, succeeds, or leaks
            generic artifact diagnostic `DRV-0072`.
    """

    if completed.returncode == 0 or "[L1C-2033]" not in completed.stderr:
        raise CompileOnlyFailure(
            f"{context} was not rejected with L1C-2033:\n{completed.stderr}"
        )
    if "[DRV-0072]" in completed.stderr:
        raise CompileOnlyFailure(
            f"{context} leaked generic artifact validation:\n{completed.stderr}"
        )
    if "[L1C-9511]" in completed.stderr:
        raise CompileOnlyFailure(
            f"{context} reached transaction creation:\n{completed.stderr}"
        )


def symlinks_available(root: Path) -> bool:
    """Return whether this test process can create directory symlinks.

    Args:
        root: Per-run temporary root.

    Returns:
        `True` when a disposable directory symlink can be created.
    """

    target = root / "symlink capability target"
    alias = root / "symlink capability alias"
    target.mkdir()
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError:
        target.rmdir()
        return False
    alias.unlink()
    target.rmdir()
    return True


def test_default_nested_artifacts(compiler: Path, root: Path) -> None:
    """Default output maps a dotted module beneath the invocation directory.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    output_root = root / "default output"
    output_root.mkdir()
    completed = run_compiler(
        compiler,
        output_root,
        "--compile",
        "--project-root",
        str(INTERFACE_FIXTURES),
        "pkg.sub",
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "default nested compile failed:\n" + completed.stderr
        )
    object_path = output_root / "pkg" / "sub.o"
    require_reusable_set(object_path, "pkg.sub")
    c_path, _, _ = companions(object_path)
    if c_path.exists():
        raise CompileOnlyFailure(f"default compile unexpectedly retained C: {c_path}")
    assert_no_transactions(output_root)


def test_interface_only_graph(compiler: Path, root: Path) -> None:
    """Imported modules resolve from interfaces and do not enter generated C.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    object_path = root / "interface output" / "graph-entry.o"
    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-I",
        str(GRAPH_INTERFACES),
        "--keep-c",
        "-o",
        str(object_path),
        "graph_entry",
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "interface-backed compile failed:\n" + completed.stderr
        )
    c_bytes, _, _ = require_kept_c_set(object_path, "graph_entry")
    c_text = c_bytes.decode("utf-8")
    if "/* Module: graph_entry */" not in c_text:
        raise CompileOnlyFailure("entry module definitions are missing from generated C")
    for provider in ("graph.provider", "graph.required", "graph.linked"):
        if f"/* Module: {provider} */" in c_text:
            raise CompileOnlyFailure(
                f"interface provider definitions leaked into generated C: {provider}"
            )
    assert_no_transactions(root)


def test_retired_metadata_symbols_absent(compiler: Path, root: Path) -> None:
    """Published objects retain lifecycle symbols but no metadata arrays."""

    object_path = root / "retired metadata symbols" / "no-main.o"
    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "no_main",
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "metadata-symbol negative fixture failed to compile:\n"
            + completed.stderr
        )
    require_reusable_set(object_path, "no_main")

    symbols = global_object_symbols(object_path)
    for required_suffix in ("I4init", "I4fini"):
        if not any(symbol.endswith(required_suffix) for symbol in symbols):
            raise CompileOnlyFailure(
                "object-symbol probe did not find required lifecycle symbol "
                f"{required_suffix}: {sorted(symbols)!r}"
            )
    retired = sorted(
        symbol
        for symbol in symbols
        if symbol.endswith("I8metadata") or symbol.endswith("I7imports")
    )
    if retired:
        raise CompileOnlyFailure(
            f"compile-only object retains retired metadata symbols: {retired!r}"
        )
    assert_no_transactions(root)


def test_failed_analysis_preserves_set(compiler: Path, root: Path) -> None:
    """Missing interfaces fail without changing a pre-existing artifact set.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    object_path = root / "analysis-failure.o"
    c_path, _, interface_path = companions(object_path)
    old = (b"old-c", b"old-object", b"old-interface")
    c_path.write_bytes(old[0])
    object_path.write_bytes(old[1])
    interface_path.write_bytes(old[2])

    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "graph_entry",
    )
    if completed.returncode == 0 or "[DRV-0074]" not in completed.stderr:
        raise CompileOnlyFailure(
            "missing interface did not fail through interface-only resolution:\n"
            + completed.stderr
        )
    actual = (c_path.read_bytes(), object_path.read_bytes(), interface_path.read_bytes())
    if actual != old:
        raise CompileOnlyFailure("analysis failure changed the previous artifact set")
    assert_no_transactions(root)


def test_failed_analysis_does_not_create_output_parent(
    compiler: Path,
    root: Path,
) -> None:
    """Analysis failure does not create a previously absent output tree.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    output_root = root / "absent analysis output"
    object_path = output_root / "nested" / "graph-entry.o"
    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "graph_entry",
    )
    if completed.returncode == 0 or "[DRV-0074]" not in completed.stderr:
        raise CompileOnlyFailure(
            "missing interface did not fail before output creation:\n"
            + completed.stderr
        )
    if output_root.exists():
        raise CompileOnlyFailure(
            f"analysis failure created the output tree: {output_root}"
        )
    assert_no_transactions(root)


def test_failed_compiler_preserves_set(compiler: Path, root: Path) -> None:
    """Host compiler failure leaves the prior complete set byte-for-byte.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    object_path = root / "compiler-failure.o"
    c_path, _, interface_path = companions(object_path)
    old = (b"old-c-2", b"old-object-2", b"old-interface-2")
    c_path.write_bytes(old[0])
    object_path.write_bytes(old[1])
    interface_path.write_bytes(old[2])
    missing_compiler = root / "compiler-that-does-not-exist"

    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-Cc",
        str(missing_compiler),
        "-o",
        str(object_path),
        "no_main",
    )
    if completed.returncode == 0 or "[L1C-0010]" not in completed.stderr:
        raise CompileOnlyFailure(
            "missing host compiler did not report C compilation failure:\n"
            + completed.stderr
        )
    actual = (c_path.read_bytes(), object_path.read_bytes(), interface_path.read_bytes())
    if actual != old:
        raise CompileOnlyFailure("host compiler failure changed the previous set")
    assert_no_transactions(root)


def test_existing_regular_c_is_preserved(compiler: Path, root: Path) -> None:
    """Default compile leaves an existing regular C companion untouched.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    object_path = root / "partial" / "module.o"
    c_path, _, interface_path = companions(object_path)
    c_path.parent.mkdir()
    old_c = b"caller-owned-c"
    c_path.write_bytes(old_c)

    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "no_main",
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "compile beside existing C failed:\n" + completed.stderr
        )
    require_reusable_set(object_path, "no_main")
    if c_path.read_bytes() != old_c:
        raise CompileOnlyFailure("default compile changed the existing C companion")
    if not interface_path.is_file():
        raise CompileOnlyFailure("default compile did not publish the interface")
    assert_no_transactions(root)


def test_existing_nonregular_c_is_preserved(compiler: Path, root: Path) -> None:
    """Default compile neither rejects nor changes a non-regular C companion.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    object_path = root / "nonregular-c" / "module.o"
    c_path, _, _ = companions(object_path)
    c_path.mkdir(parents=True)
    sentinel = c_path / "sentinel"
    sentinel.write_bytes(b"caller-owned-directory")

    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "no_main",
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "compile beside non-regular C failed:\n" + completed.stderr
        )
    require_reusable_set(object_path, "no_main")
    if not c_path.is_dir() or sentinel.read_bytes() != b"caller-owned-directory":
        raise CompileOnlyFailure("default compile changed the non-regular C companion")
    assert_no_transactions(root)


def test_invalid_destinations(compiler: Path, root: Path) -> None:
    """Directories and non-directory parents are rejected with L1C-2033.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    directory_object = root / "directory.o"
    directory_object.mkdir()
    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(directory_object),
        "no_main",
    )
    if completed.returncode == 0 or "[L1C-2033]" not in completed.stderr:
        raise CompileOnlyFailure(
            "directory object destination was not rejected:\n" + completed.stderr
        )

    parent_file = root / "not-a-parent"
    parent_file.write_bytes(b"parent")
    completed2 = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(parent_file / "module.o"),
        "no_main",
    )
    if completed2.returncode == 0 or "[L1C-2033]" not in completed2.stderr:
        raise CompileOnlyFailure(
            "non-directory output parent was not rejected:\n" + completed2.stderr
        )
    assert_no_transactions(root)


def test_trailing_separator_outputs(compiler: Path, root: Path) -> None:
    """Compile-only rejects empty and separator-terminated outputs directly.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    base_args = (
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
    )
    for output, context in (
        ("", "empty output"),
        (str(root / "slash-terminated.o") + "/", "slash-terminated output"),
        (str(root / "backslash-terminated.o") + "\\", "backslash-terminated output"),
    ):
        completed = run_compiler(
            compiler,
            root,
            *base_args,
            output,
            "no_main",
        )
        require_output_path_error(completed, context)
    assert_no_transactions(root)


def test_directory_alias_parents(compiler: Path, root: Path) -> None:
    """Trusted directory aliases work directly, in chains, and below gaps.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    physical_parent = root / "physical output"
    physical_parent.mkdir()
    alias_parent = root / "output alias"
    alias_parent.symlink_to(physical_parent, target_is_directory=True)

    direct_object = alias_parent / "direct.o"
    direct = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(direct_object),
        "no_main",
    )
    if direct.returncode != 0:
        raise CompileOnlyFailure(
            "compile through direct directory alias failed:\n" + direct.stderr
        )
    require_reusable_set(direct_object, "no_main")

    chained_alias = root / "chained output alias"
    chained_alias.symlink_to(alias_parent, target_is_directory=True)
    chained_object = chained_alias / "chained.o"
    chained = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(chained_object),
        "no_main",
    )
    if chained.returncode != 0:
        raise CompileOnlyFailure(
            "compile through chained directory aliases failed:\n" + chained.stderr
        )
    require_reusable_set(chained_object, "no_main")

    nested_object = alias_parent / "missing" / "nested" / "module.o"
    nested = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(nested_object),
        "no_main",
    )
    if nested.returncode != 0:
        raise CompileOnlyFailure(
            "compile below directory alias failed to create nested parents:\n"
            + nested.stderr
        )
    require_reusable_set(nested_object, "no_main")
    if not (physical_parent / "missing" / "nested").is_dir():
        raise CompileOnlyFailure(
            "compile below directory alias did not create physical nested parents"
        )
    if not alias_parent.is_symlink() or not chained_alias.is_symlink():
        raise CompileOnlyFailure("compile changed a trusted directory alias")
    assert_no_transactions(physical_parent)


def test_invalid_symlink_destinations(compiler: Path, root: Path) -> None:
    """Dangling, non-directory, and final artifact symlinks are rejected.

    Args:
        compiler: Stage 1 launcher path.
        root: Per-run temporary root.
    """

    dangling_parent = root / "dangling parent"
    dangling_parent.symlink_to(root / "missing directory", target_is_directory=True)
    dangling = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(dangling_parent / "module.o"),
        "no_main",
    )
    require_output_path_error(dangling, "dangling output-parent alias")
    if (
        not dangling_parent.is_symlink()
        or (root / "missing directory").exists()
    ):
        raise CompileOnlyFailure(
            "rejected dangling output-parent alias was changed or materialized"
        )

    parent_file = root / "parent target file"
    parent_file.write_bytes(b"parent")
    file_alias = root / "file parent alias"
    file_alias.symlink_to(parent_file)
    non_directory = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(file_alias / "module.o"),
        "no_main",
    )
    require_output_path_error(non_directory, "non-directory output-parent alias")
    if (
        not file_alias.is_symlink()
        or parent_file.read_bytes() != b"parent"
    ):
        raise CompileOnlyFailure(
            "rejected non-directory output-parent alias was changed"
        )

    for suffix, keep_c in ((".o", False), (".l1m", False), (".c", True)):
        case_root = root / ("final symlink " + suffix[1:])
        case_root.mkdir()
        object_path = case_root / "module.o"
        c_path, _, interface_path = companions(object_path)
        selected_path = {
            ".c": c_path,
            ".o": object_path,
            ".l1m": interface_path,
        }[suffix]
        target = case_root / ("symlink target " + suffix[1:])
        target.write_bytes(b"caller-owned-target")
        selected_path.symlink_to(target)
        args = [
            "-c",
            "-Rp",
            str(DRIVER_FIXTURES),
            "-o",
            str(object_path),
        ]
        if keep_c:
            args.append("--keep-c")
        args.append("no_main")
        completed = run_compiler(compiler, root, *args)
        require_output_path_error(completed, f"final {suffix} artifact symlink")
        if not selected_path.is_symlink() or target.read_bytes() != b"caller-owned-target":
            raise CompileOnlyFailure(
                f"rejected final {suffix} artifact symlink was changed"
            )
    assert_no_transactions(root)


def main() -> int:
    """Run the end-to-end compile-only matrix."""

    compiler = stage1_compiler()
    if not compiler.is_file():
        print(
            f"l1c_stage1_compile_only_test: FAIL: missing compiler: {compiler}",
            file=sys.stderr,
        )
        return 1

    root = Path(tempfile.mkdtemp(prefix="l1c_stage1_compile_only_"))
    keep_artifacts = os.environ.get("KEEP_ARTIFACTS", "0") == "1"
    try:
        test_default_nested_artifacts(compiler, root)
        test_interface_only_graph(compiler, root)
        test_retired_metadata_symbols_absent(compiler, root)
        test_failed_analysis_preserves_set(compiler, root)
        test_failed_analysis_does_not_create_output_parent(compiler, root)
        test_failed_compiler_preserves_set(compiler, root)
        test_existing_regular_c_is_preserved(compiler, root)
        test_existing_nonregular_c_is_preserved(compiler, root)
        test_invalid_destinations(compiler, root)
        test_trailing_separator_outputs(compiler, root)
        if symlinks_available(root):
            test_directory_alias_parents(compiler, root)
            test_invalid_symlink_destinations(compiler, root)
    except CompileOnlyFailure as exc:
        keep_artifacts = True
        print(f"l1c_stage1_compile_only_test: FAIL: {exc}", file=sys.stderr)
        print(f"l1c_stage1_compile_only_test: artifacts={root}", file=sys.stderr)
        return 1
    finally:
        if not keep_artifacts:
            shutil.rmtree(root, ignore_errors=True)

    print("l1c_stage1_compile_only_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
