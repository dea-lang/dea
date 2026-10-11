#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Build canonical L2 using an explicitly selected compatible L1 toolchain."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

MONOREPO_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(MONOREPO_SCRIPTS))
from dea_tooling.bootstrap import wrapper_command, resolve_l1_toolchain, l1_bootstrap_environment
from dea_tooling.launchers import (render_repo_native_wrapper, render_repo_native_cmd_wrapper,
                                  render_repo_env_script, render_repo_env_cmd_script)

REPO_ROOT = Path(__file__).resolve().parents[1]
SUPPORT_ROOT = REPO_ROOT / "compiler/support"
SUPPORT_SOURCES = tuple(SUPPORT_ROOT / name for name in ("compiler_support.c", "preparation_support.c"))

@dataclass(frozen=True)
class L2BuildLayout:
    """Owned development artifact locations."""
    repo_root: Path
    build_dir: Path
    bin_dir: Path
    build_relative_from_repo: str
    repo_relative_from_bin: str


def normalize_l2_build_dir(text: str) -> L2BuildLayout:
    """Resolve an output directory strictly within this level's tree.

    Args:
        text: Explicit absolute or level-relative build directory.
    Returns:
        Validated development layout.
    Raises:
        ValueError: The location is empty or outside the level.
    """
    if not text.strip():
        raise ValueError("L2_BUILD_DIR must not be empty")
    raw = Path(text)
    path = (raw if raw.is_absolute() else REPO_ROOT / raw).resolve()
    if path == REPO_ROOT or not path.is_relative_to(REPO_ROOT):
        raise ValueError("L2_BUILD_DIR must resolve to a subdirectory inside the L2 repository")
    return L2BuildLayout(REPO_ROOT, path, path / "bin", os.path.relpath(path, REPO_ROOT),
                         os.path.relpath(REPO_ROOT, path / "bin"))


def resolve_bootstrap() -> Path:
    """Validate the explicit L1 bootstrap in its selected construction mode.

    Returns:
        Absolute compiler path.
    Raises:
        RuntimeError: The input is missing, incomplete, or incompatible with the mode.
    """
    return resolve_l1_toolchain(os.environ.get("L2_BOOTSTRAP_L1C", ""),
                                mode=os.environ.get("L2_BOOTSTRAP_MODE", "installed").strip(),
                                env=bootstrap_environment(dict(os.environ)))


def bootstrap_environment(source: dict[str, str]) -> dict[str, str]:
    """Keep selected L1 input discovery independent of active development shells.

    Args:
        source: Calling environment.
    Returns:
        Independent environment with upstream source and target-cache overrides removed.
    """
    # Upstream native preparation is an implementation build dependency. Keep
    # its writable cache in L2-owned artifacts, never in a sibling source tree.
    layout = normalize_l2_build_dir(source.get("L2_BUILD_DIR", "build/dea"))
    return l1_bootstrap_environment(source, layout.build_dir / "bootstrap-cache")


def host_compiler(env: dict[str, str]) -> str:
    """Resolve the C compiler used to build the L1 implementation and private support."""
    configured = env.get("L1_CC")
    for candidate in ([configured] if configured else ["tcc", "gcc", "clang", "cc"]):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError(f"native compiler not found: {configured or 'tcc/gcc/clang/cc'}")


def _has_c_define(flags: str, name: str) -> bool:
    """Return whether a raw flag sequence defines the exact macro."""
    words = shlex.split(flags)
    return any(word == f"-D{name}" or word.startswith(f"-D{name}=") or
               (word == "-D" and i + 1 < len(words) and
                (words[i + 1] == name or words[i + 1].startswith(name + "=")))
               for i, word in enumerate(words))


def compiler_build_env(source: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Apply compiler-only runtime settings through the selected L1 compiler.

    Args:
        source: Calling environment with L2 compiler-construction choices.
    Returns:
        Upstream build environment and explicit runtime-mode arguments.
    """
    env = bootstrap_environment(source)
    env["L1_CC"] = host_compiler(env)
    flags = env.get("L1_CFLAGS", "")
    mode = []
    if _has_c_define(flags, "DEA_RT_UNCHECKED"):
        mode = ["--unchecked"]
    elif _has_c_define(flags, "DEA_RT_CHECK_BASIC"):
        mode = ["--check-basic"]
    elif env.get("L2_COMPILER_RT_UNCHECKED", "").strip():
        mode = ["--unchecked"]
    elif env.get("L2_COMPILER_RT_CHECK_BASIC", "1").strip():
        mode = ["--check-basic"]
    for suffix, default in (("MAX_BYTES", ""), ("MAX_COUNT", "256")):
        value = env.get(f"L2_COMPILER_RT_QUARANTINE_{suffix}", default).strip()
        define = f"_RT_QUARANTINE_{suffix}"
        if value and not _has_c_define(flags, define):
            flags = f"{flags} -D{define}={value}".strip()
    env["L1_CFLAGS"] = flags
    return env, mode


def build_support_objects(directory: Path, env: dict[str, str], *, preparation: bool = True) -> list[str]:
    """Compile owned compiler support with the implementation's host C compiler.

    Args:
        directory: Private output location.
        env: Upstream compiler environment.
        preparation: Include native preparation support when imported by the consumer.
    Returns:
        Structured foreign-object arguments for L1 compilation.
    """
    directory.mkdir(parents=True, exist_ok=True)
    args = []
    flags = [flag for flag in shlex.split(env.get("L1_CFLAGS", "")) if not flag.startswith("-Wl,")]
    for source in SUPPORT_SOURCES:
        if not preparation and source.name == "preparation_support.c":
            continue
        obj = directory / (source.stem + ".o")
        subprocess.run([host_compiler(env), "-std=c99", *flags, "-c", str(source), "-o", str(obj)],
                       env=env, check=True)
        args.extend(["--foreign-object", str(obj)])
    return args


def write_executable(path: Path, text: str) -> None:
    """Write an owned executable launcher."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def write_launchers(layout: L2BuildLayout) -> None:
    """Write canonical native launchers and stackable activation scripts."""
    text = render_repo_native_wrapper(repo_relative_from_bin=layout.repo_relative_from_bin,
                                     home_var_name="L2_HOME", native_name="l2c.native")
    text = text.replace('export L2_HOME="${repo_root}/compiler"\n',
                        'export L2_HOME="${repo_root}/compiler"\n' +
                        f'export L2_BUILD_DIR="${{repo_root}}/{layout.build_relative_from_repo}"\n')
    write_executable(layout.bin_dir / "l2c", text)
    text = render_repo_env_script(repo_relative_from_bin=layout.repo_relative_from_bin,
                                 build_relative_from_repo=layout.build_relative_from_repo,
                                 env_script_name="l2-env.sh", env_script_label="l2-env",
                                 home_var_name="L2_HOME", compiler_env_var="L2_CC")
    text = text.replace('export L2_HOME="${REPO_ROOT}/compiler"\n',
                        'export L2_HOME="${REPO_ROOT}/compiler"\n' +
                        f'export L2_BUILD_DIR="${{REPO_ROOT}}/{layout.build_relative_from_repo}"\n')
    write_executable(layout.bin_dir / "l2-env.sh", text)
    if os.name == "nt":
        relative = layout.build_relative_from_repo.replace("/", "\\")
        text = render_repo_native_cmd_wrapper(repo_relative_from_bin=layout.repo_relative_from_bin,
                                             home_var_name="L2_HOME", native_name="l2c.native")
        text = text.replace('set "L2_HOME=%REPO_ROOT%\\compiler"\n',
                            f'set "L2_HOME=%REPO_ROOT%\\compiler"\nset "L2_BUILD_DIR=%REPO_ROOT%\\{relative}"\n')
        write_executable(layout.bin_dir / "l2c.cmd", text)
        text = render_repo_env_cmd_script(repo_relative_from_bin=layout.repo_relative_from_bin,
                                         env_script_label="l2-env", home_var_name="L2_HOME")
        text = text.replace('set "L2_HOME=%REPO_ROOT%\\compiler"\n',
                            f'set "L2_HOME=%REPO_ROOT%\\compiler"\nset "L2_BUILD_DIR=%REPO_ROOT%\\{relative}"\n')
        write_executable(layout.bin_dir / "l2-env.cmd", text)


def provide_public_headers(layout: L2BuildLayout) -> None:
    """Copy owned target-runtime headers without borrowing upstream runtime inputs."""
    destination = layout.build_dir / "include"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("dea_rt.h", "l1_real.h"):
        shutil.copy2(REPO_ROOT / "compiler/shared/runtime/include" / name, destination / name)


def build_semantic_interfaces(layout: L2BuildLayout, native: Path) -> None:
    """Generate and verify owned L2 semantics with the newly constructed L2 compiler."""
    source = REPO_ROOT / "compiler/shared/l2/stdlib"
    modules = sorted(p.relative_to(source).with_suffix("").as_posix().replace("/", ".") for p in source.rglob("*.l2"))
    if not modules or any(not m.startswith(("std.", "sys.")) for m in modules):
        raise RuntimeError("invalid canonical L2 bundled module inventory")
    env = {k: v for k, v in os.environ.items() if not k.startswith("L2_")}
    env.update(L2_HOME=str(REPO_ROOT / "compiler"), L2_BUILD_DIR=str(layout.build_dir))
    with tempfile.TemporaryDirectory(prefix="semantic-bootstrap-", dir=layout.build_dir) as temporary:
        work = Path(temporary)
        interfaces = work / "interfaces"
        interfaces.mkdir()
        for module in modules:
            output = interfaces / (module.replace(".", "/") + ".l2m")
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([str(native), "--emit-interface", "--no-managed-stdlib", "--sys-root", str(source),
                            "--project-root", str(work), module, "-o", str(output)], env=env, check=True)
        (work / "_dea_semantic_bootstrap.l2").write_text("module _dea_semantic_bootstrap;\n" +
            "".join(f"import {module};\n" for module in modules), encoding="utf-8")
        subprocess.run([str(native), "--gen", "--no-managed-stdlib", "--sys-root", str(source),
                        "--project-root", str(work), "-I", str(interfaces), "_dea_semantic_bootstrap", "-o", str(work / "verify.c")],
                       env=env, check=True)
        destination = layout.build_dir / "interfaces"
        if destination.exists():
            shutil.rmtree(destination)
        interfaces.rename(destination)
    print(f"build-l2c: verified {len(modules)} bundled interfaces under {destination}")


def build_compiler(compiler: Path, output: Path, env: dict[str, str], *, keep_c: bool = False) -> None:
    """Build the L1 implementation through its explicit upstream toolchain."""
    output.parent.mkdir(parents=True, exist_ok=True)
    build_env, mode = compiler_build_env(env)
    with tempfile.TemporaryDirectory(prefix="l2-support-", dir=output.parent) as directory:
        support = build_support_objects(Path(directory), build_env)
        command = [*wrapper_command(compiler), "--build", *mode, *support, "--project-root",
                   str(REPO_ROOT / "compiler/src"), "-o", str(output), "l2c"]
        if keep_c:
            command.append("--keep-c")
        subprocess.run(command, cwd=REPO_ROOT, env=build_env, check=True)
    output.chmod(output.stat().st_mode | 0o111)


def main() -> int:
    """Construct and verify the single canonical L2 compiler."""
    try:
        layout = normalize_l2_build_dir(os.environ.get("L2_BUILD_DIR", "build/dea"))
        compiler = resolve_bootstrap()
        provide_public_headers(layout)
        native = layout.bin_dir / "l2c.native"
        build_compiler(compiler, native, dict(os.environ), keep_c=os.environ.get("KEEP_C") == "1")
        build_semantic_interfaces(layout, native)
        write_launchers(layout)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"build-l2c: {exc}", file=sys.stderr)
        return 1
    print(f"build-l2c: wrote {native}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
