#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""End-to-end coverage for transactional L1 Stage 1 compile-only mode."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
import shlex
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
CURRENT_SENTINEL_MARKER = "current-sentinel"
RELATIVE_SENTINEL_MARKER = "relative-sentinel"


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
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the Stage 1 compiler with captured UTF-8 text output.

    Args:
        compiler: Stage 1 launcher path.
        cwd: Working directory for default artifact placement.
        *args: Compiler arguments excluding the executable name.
        env: Optional process environment override.

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
        env=env,
        check=False,
    )


def resolve_host_c_compiler() -> str:
    """Return the compiler selected by the Stage 1 host-tool precedence."""

    configured = os.environ.get("L1_CC", "").strip()
    if configured:
        resolved = shutil.which(configured)
        return resolved if resolved is not None else configured
    for candidate in ("tcc", "gcc", "clang", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    configured_cc = os.environ.get("CC", "").strip()
    if configured_cc:
        resolved_cc = shutil.which(configured_cc)
        return resolved_cc if resolved_cc is not None else configured_cc
    raise CompileOnlyFailure("compile-only test requires a host C compiler")


def resolve_deterministic_host_c_compiler() -> str | None:
    """Return an available recognized compiler for path-neutrality coverage."""

    for candidate in ("clang", "gcc", "cc"):
        resolved = shutil.which(candidate)
        if resolved is None:
            continue
        if classify_debug_compiler(resolved) is not None:
            return resolved
    return None


def compiler_driver_name_matches(compiler: str, driver: str) -> bool:
    """Return whether a compiler basename denotes one conventional driver."""

    name = Path(compiler).name.lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    for thread_model in ("-posix", "-win32"):
        if name.endswith(thread_model):
            name = name[: -len(thread_model)]
            break
    stem, separator, suffix = name.rpartition("-")
    if separator and suffix and all(
        component and all("0" <= character <= "9" for character in component)
        for component in suffix.split(".")
    ):
        name = stem
    return name == driver or name.endswith("-" + driver)


def classify_debug_compiler(compiler: str) -> str | None:
    """Return the recognizable GCC/Clang identity of one compiler path."""

    for path in (Path(compiler), Path(compiler).resolve()):
        if compiler_driver_name_matches(str(path), "clang"):
            return "clang"
        if compiler_driver_name_matches(str(path), "gcc"):
            return "gcc"
    return None


def compiler_version_banner(compiler: str) -> tuple[int, str]:
    """Return one compiler's version-probe status and lower-case output."""

    completed = subprocess.run(
        [compiler, "--version"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode, completed.stdout.lower()


def resolve_gnu_gcc() -> str | None:
    """Return an available genuine GNU GCC driver for focused coverage."""

    candidates = [
        os.environ.get("L1_TEST_GNU_GCC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        os.environ.get("CC", "").strip(),
        "gcc",
        *(f"gcc-{version}" for version in range(30, 4, -1)),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        if classify_debug_compiler(resolved) != "gcc":
            continue
        returncode, banner = compiler_version_banner(resolved)
        if (
            returncode == 0
            and "clang" not in banner
            and ("gcc" in banner or "free software foundation" in banner)
        ):
            return resolved
    return None


def resolve_clang_driver_aliases() -> tuple[str, ...]:
    """Return Darwin's standard `gcc`/`cc` hard links to system Clang."""

    system_clang = Path("/usr/bin/clang")
    if sys.platform != "darwin" or not system_clang.is_file():
        return ()
    aliases: list[str] = []
    for candidate in (Path("/usr/bin/gcc"), Path("/usr/bin/cc")):
        if not candidate.is_file():
            continue
        try:
            is_system_clang = candidate.samefile(system_clang)
        except OSError:
            is_system_clang = False
        if is_system_clang:
            aliases.append(str(candidate))
    return tuple(aliases)


def build_host_tool_sentinel(
    root: Path,
    object_marker: str = "sentinel-object",
) -> Path:
    """Build a compiler sentinel that records argv and writes a fake object."""

    if re.fullmatch(r"[a-z-]+", object_marker) is None:
        raise CompileOnlyFailure(f"invalid host-tool sentinel marker: {object_marker}")

    source = root / "host-tool-sentinel.c"
    executable = root / (
        "host-tool-sentinel.exe" if os.name == "nt" else "host-tool-sentinel"
    )
    source_text = r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *log_path = getenv("L1_SENTINEL_LOG");
    const char *output = NULL;
    FILE *log;
    FILE *object;
    static const char marker[] = "__L1_SENTINEL_MARKER__";
    int i;
    if (log_path == NULL) return 90;
    log = fopen(log_path, "ab");
    if (log == NULL) return 91;
    for (i = 1; i < argc; ++i) {
        if (fprintf(log, "%s\n", argv[i]) < 0) return 92;
        if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) output = argv[i + 1];
        if (strncmp(argv[i], "/Fo:", 4) == 0) output = argv[i] + 4;
    }
    if (fclose(log) != 0 || output == NULL) return 93;
    object = fopen(output, "wb");
    if (object == NULL) return 94;
    if (fwrite(marker, 1, sizeof(marker) - 1, object) != sizeof(marker) - 1)
        return 95;
    return fclose(object) == 0 ? 0 : 96;
}
'''.replace("__L1_SENTINEL_MARKER__", object_marker)
    source.write_text(
        source_text,
        encoding="utf-8",
    )
    completed = subprocess.run(
        [resolve_host_c_compiler(), str(source), "-o", str(executable)],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "failed to build host-tool sentinel:\n" + completed.stdout
        )
    return executable


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


def test_generated_c_is_pure_and_exact(
    compiler: Path,
    root: Path,
    sentinel: Path,
) -> None:
    """Generated-C writes one exact file without invoking a host tool."""

    output = root / "pure generation" / "chosen-output.data"
    output.parent.mkdir()
    sentinel_log = root / "pure-generation-host-tool.log"
    env = os.environ.copy()
    env["L1_CC"] = str(sentinel)
    env["L1_SENTINEL_LOG"] = str(sentinel_log)
    completed = run_compiler(
        compiler,
        root,
        "--gen",
        "--no-line-directives",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(output),
        "no_main",
        env=env,
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure("pure generated-C failed:\n" + completed.stderr)
    if sentinel_log.exists():
        raise CompileOnlyFailure("--gen unexpectedly invoked the host compiler")
    if not output.is_file():
        raise CompileOnlyFailure("--gen did not write the exact requested output")
    for companion in (output.with_suffix(".o"), output.with_suffix(".l1m")):
        if companion.exists():
            raise CompileOnlyFailure(f"--gen created a companion artifact: {companion}")

    text = output.read_text(encoding="utf-8")
    if "I4init(void)" not in text or "I4fini(void)" not in text:
        raise CompileOnlyFailure("utility generated-C lacks module lifecycle symbols")
    if "I5entry(void)" in text or "int main(int argc, char **argv)" in text:
        raise CompileOnlyFailure("utility generated-C contains an entry/process wrapper")


def test_generated_c_matches_compile_retention(
    compiler: Path,
    root: Path,
) -> None:
    """`--gen` and `-c --keep-c` publish identical module C bytes."""

    gen_path = root / "generated identity" / "selected.c"
    object_path = root / "compile identity" / "selected.o"
    gen_path.parent.mkdir()
    completed_gen = run_compiler(
        compiler,
        root,
        "--gen",
        "--no-line-directives",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(gen_path),
        "no_main",
    )
    if completed_gen.returncode != 0:
        raise CompileOnlyFailure(
            "generated-C identity producer failed:\n" + completed_gen.stderr
        )
    completed_compile = run_compiler(
        compiler,
        root,
        "-c",
        "--keep-c",
        "--no-line-directives",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(object_path),
        "no_main",
    )
    if completed_compile.returncode != 0:
        raise CompileOnlyFailure(
            "compile-retention identity producer failed:\n"
            + completed_compile.stderr
        )
    kept_c, _, _ = require_kept_c_set(object_path, "no_main")
    if gen_path.read_bytes() != kept_c:
        raise CompileOnlyFailure("--gen and -c --keep-c C bytes differ")
    assert_no_transactions(root)


def test_host_compiler_sees_module_relative_paths(
    compiler: Path,
    root: Path,
    sentinel: Path,
) -> None:
    """A host-tool sentinel sees no transaction or destination path inputs."""

    object_path = root / "sentinel destination" / "caller-name.o"
    sentinel_log = root / "compile-host-tool.log"
    env = os.environ.copy()
    env["L1_CC"] = str(sentinel)
    env["L1_SENTINEL_LOG"] = str(sentinel_log)
    env["L1_CFLAGS"] = ""
    completed = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(INTERFACE_FIXTURES),
        "-o",
        str(object_path),
        "pkg.sub",
        env=env,
    )
    if completed.returncode != 0:
        raise CompileOnlyFailure(
            "sentinel-backed compile failed:\n" + completed.stderr
        )
    require_reusable_set(object_path, "pkg.sub")
    arguments = sentinel_log.read_text(encoding="utf-8").splitlines()
    if "pkg/sub.c" not in arguments or "pkg/sub.o" not in arguments:
        raise CompileOnlyFailure(
            f"host compiler did not receive canonical module paths: {arguments!r}"
        )
    leaked = [
        argument
        for argument in arguments
        if ".l1c-compile-" in argument or str(object_path.parent) in argument
    ]
    if leaked:
        raise CompileOnlyFailure(
            f"host compiler arguments leaked private/destination prefixes: {leaked!r}"
        )
    assert_no_transactions(root)


def test_bare_compiler_path_resolution(
    compiler: Path,
    root: Path,
    current_directory_sentinel: Path,
) -> None:
    """Bare compilers retain invocation-time relative and empty PATH lookup."""

    relative_toolchain = root / "relative-toolchain"
    relative_toolchain.mkdir()
    build_host_tool_sentinel(
        relative_toolchain,
        RELATIVE_SENTINEL_MARKER,
    )
    bare_name = (
        current_directory_sentinel.stem
        if os.name == "nt"
        else current_directory_sentinel.name
    )
    if os.name == "nt":
        # A suffix-free regular file must not beat PATHEXT-selected `.exe`.
        (root / bare_name).write_bytes(b"extensionless-decoy")
    inherited_path = os.environ.get("PATH", "")
    relative_path = (
        os.path.relpath(relative_toolchain, root) + os.pathsep + inherited_path
    )
    cases: list[tuple[str, str, str, bool]] = []
    if os.name == "nt":
        cases.extend(
            (
                (
                    "relative default cwd",
                    CURRENT_SENTINEL_MARKER,
                    relative_path,
                    False,
                ),
                (
                    "relative suppressed cwd",
                    RELATIVE_SENTINEL_MARKER,
                    relative_path,
                    True,
                ),
                (
                    "explicit empty path",
                    CURRENT_SENTINEL_MARKER,
                    os.pathsep + inherited_path,
                    True,
                ),
            )
        )
    else:
        cases.extend(
            (
                (
                    "relative",
                    RELATIVE_SENTINEL_MARKER,
                    relative_path,
                    False,
                ),
                (
                    "empty",
                    CURRENT_SENTINEL_MARKER,
                    os.pathsep + inherited_path,
                    False,
                ),
            )
        )
    for label, expected_marker, configured_path, suppress_cwd in cases:
        object_path = root / f"bare compiler {label}" / "selected.o"
        sentinel_log = root / f"bare-compiler-{label}.log"
        env = os.environ.copy()
        env["L1_CC"] = bare_name
        env["L1_CFLAGS"] = ""
        env["L1_SENTINEL_LOG"] = str(sentinel_log)
        env["PATH"] = configured_path
        if os.name == "nt":
            env["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
        if suppress_cwd:
            env["NoDefaultCurrentDirectoryInExePath"] = "1"
        else:
            env.pop("NoDefaultCurrentDirectoryInExePath", None)
        completed = run_compiler(
            compiler,
            root,
            "-c",
            "-Rp",
            str(DRIVER_FIXTURES),
            "-o",
            str(object_path),
            "no_main",
            env=env,
        )
        if completed.returncode != 0:
            raise CompileOnlyFailure(
                f"bare compiler {label} PATH lookup failed:\n{completed.stderr}"
            )
        object_bytes, _ = require_reusable_set(object_path, "no_main")
        if object_bytes != expected_marker.encode("ascii"):
            raise CompileOnlyFailure(
                f"bare compiler {label} selected the wrong executable: "
                f"{object_bytes!r}"
            )
        if not sentinel_log.is_file():
            raise CompileOnlyFailure(
                f"bare compiler {label} PATH lookup selected the wrong tool"
            )
        assert_no_transactions(root)

    if os.name == "nt":
        empty_pathext_output = root / "bare compiler empty PATHEXT" / "selected.o"
        empty_pathext_env = os.environ.copy()
        empty_pathext_env["L1_CC"] = bare_name
        empty_pathext_env["L1_CFLAGS"] = ""
        empty_pathext_env["PATH"] = relative_path
        empty_pathext_env["PATHEXT"] = ""
        empty_pathext_env["NoDefaultCurrentDirectoryInExePath"] = "1"
        completed_empty_pathext = run_compiler(
            compiler,
            root,
            "-c",
            "-Rp",
            str(DRIVER_FIXTURES),
            "-o",
            str(empty_pathext_output),
            "no_main",
            env=empty_pathext_env,
        )
        if (
            completed_empty_pathext.returncode == 0
            or "[L1C-0010]" not in completed_empty_pathext.stderr
        ):
            raise CompileOnlyFailure(
                "empty PATHEXT did not suppress suffix-free compiler lookup:\n"
                + completed_empty_pathext.stderr
            )
        if any(path.exists() for path in companions(empty_pathext_output)):
            raise CompileOnlyFailure("empty PATHEXT published an artifact")
        assert_no_transactions(root)

    missing_name = "l1-missing-bare-compiler-probe"
    missing_output = root / "bare compiler missing.o"
    missing_env = os.environ.copy()
    missing_env["L1_CC"] = missing_name
    missing_env["L1_CFLAGS"] = ""
    completed_missing = run_compiler(
        compiler,
        root,
        "-c",
        "-Rp",
        str(DRIVER_FIXTURES),
        "-o",
        str(missing_output),
        "no_main",
        env=missing_env,
    )
    if (
        completed_missing.returncode == 0
        or "[L1C-0010]" not in completed_missing.stderr
    ):
        raise CompileOnlyFailure(
            "unresolved bare compiler did not fail deterministically:\n"
            + completed_missing.stderr
        )
    if any(path.exists() for path in companions(missing_output)):
        raise CompileOnlyFailure("unresolved bare compiler published an artifact")
    assert_no_transactions(root)


def test_driver_controlled_object_path_neutrality(
    compiler: Path,
    root: Path,
) -> None:
    """A known local toolchain does not retain driver-controlled paths."""

    if os.name == "nt":
        return
    selected_compiler = resolve_deterministic_host_c_compiler()
    if selected_compiler is None:
        return
    configurations = (
        ("plain", "", False, False),
        ("debug", "-g", False, False),
        ("debug g3", "-g3", False, False),
        ("debug ggdb", "-ggdb", False, False),
        ("debug relative output", "-g", True, False),
        ("debug equals path", "-g", False, True),
    )
    for label, cflags, use_relative_output, use_equals_path in configurations:
        separator = "=" if use_equals_path else " "
        first = root / f"object identity {label}{separator}one" / "first.o"
        second = root / f"object identity {label}{separator}two" / "second.o"
        env = os.environ.copy()
        env["L1_CFLAGS"] = cflags
        for output in (first, second):
            completed = run_compiler(
                compiler,
                root,
                "-c",
                "--no-line-directives",
                "-Cc",
                selected_compiler,
                "-Rp",
                str(DRIVER_FIXTURES),
                "-o",
                str(output.relative_to(root) if use_relative_output else output),
                "no_main",
                env=env,
            )
            if completed.returncode != 0:
                raise CompileOnlyFailure(
                    f"{label} object-identity compile failed:\n"
                    + completed.stderr
                )
        first_bytes, _ = require_reusable_set(first, "no_main")
        second_bytes, _ = require_reusable_set(second, "no_main")
        if first_bytes != second_bytes:
            raise CompileOnlyFailure(
                f"local regression baseline retained driver-controlled {label} paths"
            )
        if cflags and b".l1c-compile-" in first_bytes:
            raise CompileOnlyFailure(
                "debug object exposed the private compile transaction path"
            )
    assert_no_transactions(root)


def test_gnu_gcc_debug_path_neutrality(
    compiler: Path,
    root: Path,
) -> None:
    """GNU GCC debug objects omit driver-owned paths, including on Darwin."""

    if os.name == "nt":
        return
    gnu_gcc = resolve_gnu_gcc()
    if gnu_gcc is None:
        return
    for debug_option in ("-g", "-g3", "-ggdb"):
        label = debug_option.removeprefix("-")
        outputs = (
            root / f"GNU GCC {label}=one" / "selected.o",
            root / f"GNU GCC {label}=two" / "selected.o",
        )
        env = os.environ.copy()
        env["L1_CFLAGS"] = debug_option
        for output in outputs:
            completed = run_compiler(
                compiler,
                root,
                "-c",
                "--no-line-directives",
                "-Cc",
                gnu_gcc,
                "-Rp",
                str(DRIVER_FIXTURES),
                "-o",
                str(output),
                "no_main",
                env=env,
            )
            if completed.returncode != 0:
                raise CompileOnlyFailure(
                    f"GNU GCC {debug_option} path-neutrality compile failed:\n"
                    + completed.stderr
                )
        first_bytes, _ = require_reusable_set(outputs[0], "no_main")
        second_bytes, _ = require_reusable_set(outputs[1], "no_main")
        if first_bytes != second_bytes:
            raise CompileOnlyFailure(
                f"GNU GCC {debug_option} retained a driver-controlled path"
            )
        if any(b".l1c-compile-" in data for data in (first_bytes, second_bytes)):
            raise CompileOnlyFailure(
                f"GNU GCC {debug_option} exposed the private transaction path"
            )
    assert_no_transactions(root)


def test_clang_backed_gcc_cc_aliases(
    compiler: Path,
    root: Path,
) -> None:
    """Clang reached through system `gcc`/`cc` aliases gets Clang remapping."""

    for alias_index, clang_alias in enumerate(resolve_clang_driver_aliases()):
        alias_name = Path(clang_alias).name
        outputs = (
            root / f"Clang alias {alias_index} {alias_name}=one" / "selected.o",
            root / f"Clang alias {alias_index} {alias_name}=two" / "selected.o",
        )
        env = os.environ.copy()
        env["L1_CFLAGS"] = "-g3"
        for output in outputs:
            completed = run_compiler(
                compiler,
                root,
                "-c",
                "--no-line-directives",
                "-Cc",
                clang_alias,
                "-Rp",
                str(DRIVER_FIXTURES),
                "-o",
                str(output),
                "no_main",
                env=env,
            )
            if completed.returncode != 0:
                raise CompileOnlyFailure(
                    f"Clang-backed {alias_name} compile failed:\n"
                    + completed.stderr
                )
        first_bytes, _ = require_reusable_set(outputs[0], "no_main")
        second_bytes, _ = require_reusable_set(outputs[1], "no_main")
        if first_bytes != second_bytes:
            raise CompileOnlyFailure(
                f"Clang-backed {alias_name} retained a driver-controlled path"
            )
        if any(b".l1c-compile-" in data for data in (first_bytes, second_bytes)):
            raise CompileOnlyFailure(
                f"Clang-backed {alias_name} exposed the private transaction path"
            )
    assert_no_transactions(root)


def test_debug_path_remap_for_compiler_alias(
    compiler: Path,
    root: Path,
) -> None:
    """Canonical compiler identity controls debug remapping for an alias."""

    if os.name == "nt":
        return
    selected_compiler = resolve_deterministic_host_c_compiler()
    if selected_compiler is None:
        return
    debug_family = classify_debug_compiler(selected_compiler)
    if debug_family is None:
        return

    toolchain = root / "aliased-debug-toolchain"
    toolchain.mkdir()
    canonical_wrapper = toolchain / f"x86_64-test-{debug_family}-99.exe"
    canonical_wrapper.write_text(
        "#!/bin/sh\nexec "
        + shlex.quote(selected_compiler)
        + ' "$@"\n',
        encoding="utf-8",
    )
    canonical_wrapper.chmod(0o700)
    alias = toolchain / ("gcc" if debug_family == "clang" else "clang")
    alias.symlink_to(canonical_wrapper.name)

    env = os.environ.copy()
    env["L1_CC"] = alias.name
    env["L1_CFLAGS"] = "-g3"
    env["PATH"] = os.path.relpath(toolchain, root) + os.pathsep + env.get(
        "PATH", ""
    )
    outputs = (
        root / "aliased debug=one" / "selected.o",
        root / "aliased debug=two" / "selected.o",
    )
    for output in outputs:
        completed = run_compiler(
            compiler,
            root,
            "-c",
            "--no-line-directives",
            "-Rp",
            str(DRIVER_FIXTURES),
            "-o",
            str(output),
            "no_main",
            env=env,
        )
        if completed.returncode != 0:
            raise CompileOnlyFailure(
                "aliased debug compiler failed:\n" + completed.stderr
            )
    first_bytes, _ = require_reusable_set(outputs[0], "no_main")
    second_bytes, _ = require_reusable_set(outputs[1], "no_main")
    if first_bytes != second_bytes:
        raise CompileOnlyFailure(
            "compiler alias retained a driver-controlled transaction path"
        )
    if b".l1c-compile-" in first_bytes:
        raise CompileOnlyFailure(
            "aliased debug compiler exposed the private transaction path"
        )
    assert_no_transactions(root)


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
        sentinel = build_host_tool_sentinel(root, CURRENT_SENTINEL_MARKER)
        test_generated_c_is_pure_and_exact(compiler, root, sentinel)
        test_generated_c_matches_compile_retention(compiler, root)
        test_host_compiler_sees_module_relative_paths(compiler, root, sentinel)
        test_bare_compiler_path_resolution(compiler, root, sentinel)
        test_driver_controlled_object_path_neutrality(compiler, root)
        test_gnu_gcc_debug_path_neutrality(compiler, root)
        test_clang_backed_gcc_cc_aliases(compiler, root)
        test_debug_path_remap_for_compiler_alias(compiler, root)
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
