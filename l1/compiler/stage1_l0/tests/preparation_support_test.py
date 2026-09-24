#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native preparation identity, storage, integrity, and coordination regressions."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import chdir
from unittest.mock import patch

if os.name == "nt":
    from _ctypes import FreeLibrary

from compiler_filesystem_support_test import resolve_c_compiler
from l1c_stage1_compile_only_test import stage1_compiler

L1_ROOT = Path(__file__).resolve().parents[3]
SUPPORT = L1_ROOT / "compiler/stage1_l0/support"


def compile_native(output: Path, sources: list[Path], flags: tuple[str, ...] = ()) -> None:
    """Compile a native fixture and retain compiler diagnostics on failure.

    Args:
        output: Destination executable or shared library.
        sources: Translation units to compile and link.
        flags: Additional compilation or shared-library options.

    Raises:
        AssertionError: If the compiler exits unsuccessfully.
        OSError: If the compiler cannot be started.
    """
    command = [resolve_c_compiler(), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
               *flags, *(str(source) for source in sources), "-o", str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"native fixture compilation failed ({result.returncode})\n"
        f"command: {command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")


def build_library(root: Path) -> Path:
    """Compile the service with strict warnings independently of the L0 driver."""
    library = root / ("preparation.dll" if os.name == "nt" else "preparation.so")
    flags = ("-shared",) if os.name == "nt" else ("-shared", "-fPIC")
    compile_native(library, [SUPPORT / "preparation_support.c", SUPPORT / "compiler_support.c"], flags)
    return library


def run_native_reader(executable: Path, fixtures: Path, name: str) -> None:
    """Run one compiled native reader against an owned fixture directory.

    Args:
        executable: Native reader executable to invoke.
        fixtures: Empty directory reserved for the reader's fixture files.
        name: Reader fixture name used in failure diagnostics.

    Raises:
        AssertionError: If the native reader exits unsuccessfully.
    """
    fixtures.mkdir()
    result = subprocess.run([str(executable), str(fixtures)], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{name} fixture failed ({result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")


def check_native_reader(root: Path, name: str) -> Path:
    """Run one private native reader fixture without exporting a test ABI.

    Args:
        root: Owned directory for the executable and input files.
        name: Reader fixture name, matching its C translation unit.
    """
    executable = root / (f"preparation-{name}.exe" if os.name == "nt" else f"preparation-{name}")
    compile_native(executable, [Path(__file__).with_name(f"preparation_{name}_test.c"),
                                SUPPORT / "compiler_support.c"])
    run_native_reader(executable, root / (name + "-files"), name)
    return executable


def check_observability(root: Path) -> None:
    """Validate production observations with a controlled native clock.

    Args:
        root: Owned directory for fixture compilation and input files.
    """
    executable = root / ("observability.exe" if os.name == "nt" else "observability")
    compile_native(executable, [Path(__file__).with_name("preparation_observability_test.c"),
                                SUPPORT / "compiler_support.c"])
    fixtures = root / "observation-files"
    fixtures.mkdir()
    result = subprocess.run([str(executable), str(fixtures)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    records = [json.loads(line.removeprefix("Preparation observation: ")) for line in result.stderr.splitlines()]
    hashes = [record for record in records if record["event"] == "hash"]
    assert [(item["bytes"], item["elapsed_us"], item["success"]) for item in hashes] == [(3, 1000, 1), (0, 1000, 0)]
    mismatches = [record for record in records if record["event"] == "metadata-mismatch"]
    assert len(mismatches) == 1 and mismatches[0]["field"] == "inode", mismatches
    assert mismatches[0]["path"] == 'quote"slash\\line\n'
    decisions = [record for record in records if record["event"] == "decision"]
    assert [item["reason"] for item in decisions] == ["memo-digest-invalid", "memo-digest-invalid"], decisions
    probes = [record for record in records if record["event"] == "probe"]
    assert probes[0]["status"] == 23 and probes[0]["timed_out"] == 0
    assert probes[1]["timed_out"] == 1


def check_digest_seeds(root: Path) -> None:
    """Exercise optional donor failures and their production debug observations.

    Args:
        root: Owned directory for fixture compilation and input files.
    """
    executable = root / ("digest-seeds.exe" if os.name == "nt" else "digest-seeds")
    compile_native(executable, [Path(__file__).with_name("preparation_digest_seed_test.c"),
                                SUPPORT / "compiler_support.c"])
    fixtures = root / "digest-seed-files"
    fixtures.mkdir()
    result = subprocess.run([str(executable), str(fixtures)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not result.stdout
    records = [json.loads(line.removeprefix("Preparation observation: ")) for line in result.stderr.splitlines()]
    decisions = [item for item in records if item["event"] == "decision"]
    reasons = [item["reason"] for item in decisions]
    # The three quiet iterations must not contribute debug records.
    assert reasons.count("validated-donor-record") == 2, reasons
    assert reasons.count("validated-current-record") == 1, reasons
    for scope in ("digest-seed-hint", "digest-seed-donor"):
        assert any(item["scope"] == scope and item["decision"] == "hit" for item in decisions)
        assert any(item["scope"] == scope and item["decision"] == "miss" for item in decisions)
    assert "write-unavailable" in reasons and "malformed-memo" in reasons
    assert any(item["scope"] == "input-digest" and item["decision"] == "fallback" and
               item["reason"] == "force" and Path(item["path"]) == fixtures / "input" for item in decisions)


class Service:
    """Small test adapter for the compiler-private, caller-owned byte-span ABI."""

    def __init__(self, library: Path, config: dict | bytes):
        self.lib = None
        self.context = None
        try:
            self.lib = ctypes.CDLL(str(library))
            self.lib.l1c_prep_create.argtypes = [ctypes.c_char_p, ctypes.c_int]
            self.lib.l1c_prep_create.restype = ctypes.c_void_p
            self.lib.l1c_prep_free.argtypes = [ctypes.c_void_p]
            self.lib.l1c_prep_free.restype = None
            self.lib.l1c_prep_get.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
            for name, count in (("resolve", 0), ("find", 0), ("lock", 0), ("unlock", 0), ("private", 0), ("begin", 0), ("complete", 0), ("copy_interfaces", 0), ("runtime", 0), ("error_code", 0)):
                getattr(self.lib, "l1c_prep_" + name).argtypes = [ctypes.c_void_p] + [ctypes.c_int] * count
            data = config if isinstance(config, bytes) else json.dumps(config).encode()
            self.context = self.lib.l1c_prep_create(data, len(data))
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        self._open_library()
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        """Release the context before this service's Windows DLL reference, once."""
        library, context = self.lib, self.context
        self.lib = None
        self.context = None
        if library is None:
            return
        try:
            if context is not None:
                library.l1c_prep_free(context)
        finally:
            if os.name == "nt":
                handle = library._handle
                # Cached ctypes functions borrow addresses in this DLL. Other
                # services own separate loader references to the same module.
                library.__dict__.clear()
                FreeLibrary(handle)

    def _open_library(self) -> ctypes.CDLL:
        """Reject use after close before accessing any native function address.

        Returns:
            The library owned by this open service.

        Raises:
            RuntimeError: If the service has been closed.
        """
        if self.lib is None:
            raise RuntimeError("preparation service is closed")
        return self.lib

    def call(self, operation: str, *args: int) -> int:
        """Call one service operation and return its status."""
        return getattr(self._open_library(), "l1c_prep_" + operation)(self.context, *args)

    def get(self, name: str) -> str:
        """Copy one exact service field without borrowing native storage."""
        library = self._open_library()
        field = name.encode()
        size = library.l1c_prep_get(self.context, field, len(field), None, 0)
        assert size >= 0
        output = ctypes.create_string_buffer(size + 1)
        assert library.l1c_prep_get(self.context, field, len(field), output, size) == size
        return output.value.decode()

    def require(self, operation: str, *args: int) -> None:
        """Require a successful operation and retain its actionable error on failure."""
        assert self.call(operation, *args) == 1, (operation, self.get("error"))

    def stats(self) -> dict:
        """Return counters used to assert warm-path behavior without timing gates."""
        return json.loads(self.get("stats"))


def check_service_lifetime(library: Path, root: Path) -> None:
    """Exercise overlap and exceptional cleanup, including Windows DLL deletion.

    Args:
        library: Compiled library to copy into independent lifetime fixtures.
        root: Owned directory for those disposable copies.
    """
    for case in ("overlap", "body-exception", "constructor-failure"):
        fixture = root / ("lifetime-" + case + library.suffix)
        shutil.copyfile(library, fixture)
        try:
            if case == "overlap":
                with Service(fixture, b"{") as first, Service(fixture, b"{") as second:
                    first.close()
                    first.close()
                    assert second.call("error_code") == 2150 and second.get("error")
                    for closed_operation in (lambda: first.call("error_code"), lambda: first.get("error")):
                        try:
                            closed_operation()
                        except RuntimeError as error:
                            assert str(error) == "preparation service is closed"
                        else:
                            raise AssertionError("closed service accepted a native operation")
            elif case == "body-exception":
                try:
                    with Service(fixture, b"{"):
                        raise LookupError("service body sentinel")
                except LookupError as error:
                    assert str(error) == "service body sentinel"
                else:
                    raise AssertionError("service suppressed the body exception")
            else:
                try:
                    unexpected = Service(fixture, {"unserializable": object()})
                except TypeError:
                    pass
                else:
                    unexpected.close()
                    raise AssertionError("service accepted a nonserializable configuration")
        finally:
            # Windows permits deletion only after every loader reference closes.
            fixture.unlink()


def populate(service: Service) -> Path:
    """Complete a real inventory with opaque native bytes and exact semantic copies."""
    service.require("resolve")
    service.require("lock")
    service.require("begin")
    service.require("copy_interfaces")
    root = Path(service.get("selected"))
    inventory = json.loads(service.get("native_inventory"))
    for relative, role in inventory.items():
        if role != "interface":
            (root / relative).write_bytes(("opaque fixture:" + relative).encode())
    service.require("complete")
    service.call("unlock")
    return root


def check_roots(library: Path, root: Path, config: dict) -> None:
    """Check lazy semantics, root precedence, defaults, ownership and unavailable defaults."""
    isolated = {**config, "cache": str(root / "lazy"), "compiler": "missing"}
    with Service(library, isolated) as semantic:
        assert semantic.call("error_code") == 0
        assert Path(semantic.get("semantic_root")) == root / "build/interfaces"
        assert semantic.stats()["identity_content_reads"] == semantic.stats()["probes"] == 0
        assert not Path(isolated["cache"]).exists()
    blocked = root / "blocked"
    blocked.write_text("caller-owned root sibling")
    with patch.dict(os.environ, {"L1_STDLIB_CACHE": str(blocked)}):
        with Service(library, config) as cli:
            cli.require("resolve")
            assert Path(cli.get("local")) == Path(config["cache"])
        no_cli = {k: v for k, v in config.items() if k != "cache"}
        with Service(library, no_cli) as environment:
            assert environment.call("resolve") == 0 and environment.call("error_code") == 2150
        with Service(library, {**no_cli, "cache": ""}) as empty:
            assert empty.call("resolve") == 0
    with chdir(root), Service(library, {**config, "cache": "relative cache"}) as relative:
        relative.require("resolve")
        assert Path(relative.get("local")) == root / "relative cache"
    no_cli = {k: v for k, v in config.items() if k != "cache"}
    with Service(library, no_cli) as default:
        default.require("resolve")
        assert Path(default.get("local")) == root / "build/cache"
    shutil.rmtree(root / "build/cache")
    (root / "build/cache").write_text("unavailable implicit destination")
    with Service(library, no_cli) as implicit:
        implicit.require("resolve")
        assert implicit.get("writable") == "0" and implicit.call("find") == 0
        implicit.require("private")
        implicit.require("begin")
        private_root = Path(implicit.get("selected"))
        assert private_root.is_dir() and root / "build/cache" not in private_root.parents
    assert not private_root.exists()
    installed = root / "installed"
    shutil.copytree(Path(config["home"]) / "shared", installed / "shared")
    shutil.copytree(root / "build/interfaces", installed / "interfaces")
    shutil.copytree(root / "build/include", installed / "include")
    installed_config = {**no_cli, "home": str(installed)}
    user = root / "user"
    cache_env = {"HOME": str(user), "USERPROFILE": str(user), "LOCALAPPDATA": str(user / "Local"),
                 "XDG_CACHE_HOME": str(user / "xdg")}
    with patch.dict(os.environ, cache_env):
        with Service(library, installed_config) as default:
            default.require("resolve")
            expected = (user / "Local/Dea/L1/Cache" if os.name == "nt" else
                        user / "Library/Caches/dea/l1" if sys.platform == "darwin" else user / "xdg/dea/l1")
            assert Path(default.get("local")) == expected
        for unsafe in (installed, installed / "cache"):
            with Service(library, {**installed_config, "cache": str(unsafe)}) as rejected:
                assert rejected.call("resolve") == 0 and "overlaps installed payload" in rejected.get("error")
        if os.name != "nt":
            alias = root / "installation-alias"
            alias.symlink_to(installed, target_is_directory=True)
            with Service(library, {**installed_config, "cache": str(alias / "future")}) as rejected:
                assert rejected.call("resolve") == 0 and "overlaps installed payload" in rejected.get("error")
    assert not (installed / "v1").exists()
    assert blocked.read_text() == "caller-owned root sibling"


def check_integrity(library: Path, root: Path, config: dict) -> None:
    """Use exact inventory authority and treat all completed corruption as unusable."""
    with Service(library, config) as service:
        entry = populate(service)
    # Recovery owns fresh scratch, including any stale quoted-header candidates.
    stale = entry / "generated/std/dea_rt.h"
    stale.parent.mkdir(parents=True)
    stale.write_text("#error stale generated header")
    outside = root / "caller-owned-scratch"
    outside.mkdir()
    (outside / "keep").write_text("preserved")
    if os.name != "nt":
        (entry / "runtime-build").symlink_to(outside, target_is_directory=True)
    with Service(library, config) as service:
        assert populate(service) == entry
    assert not stale.exists() and (outside / "keep").read_text() == "preserved"
    marker = entry / "manifest.json"
    original = marker.read_bytes()
    manifest = json.loads(original)
    count = len(manifest["artifacts"])
    with Service(library, config) as first:
        first.require("resolve")
        first.require("find")
        assert first.stats()["artifact_content_reads"] == count
    with Service(library, config) as warm:
        warm.require("resolve")
        warm.require("find")
        assert warm.stats()["artifact_content_reads"] == 0
        assert warm.stats()["metadata_checks"] == count
    obj = entry / "modules/std/io.o"
    obj_bytes = obj.read_bytes()
    os.utime(obj, None)
    with Service(library, config) as touched:
        touched.require("resolve")
        touched.require("find")
        assert touched.stats()["artifact_content_reads"] == 1
    for payload in (b"{", json.dumps({**manifest, "artifacts": manifest["artifacts"][:-1]}).encode(),
                    json.dumps({**manifest, "key": "0" * 64}).encode()):
        marker.write_bytes(payload)
        with Service(library, config) as invalid:
            invalid.require("resolve")
            assert invalid.call("find") == 2 and invalid.get("unusable")
            assert marker.read_bytes() == payload
        marker.write_bytes(original)
    marker.unlink()
    marker.mkdir()
    with Service(library, config) as nonregular:
        nonregular.require("resolve")
        assert nonregular.call("find") == 2
    marker.rmdir()
    if os.name != "nt":
        marker.symlink_to(root / "missing-marker-target")
        with Service(library, config) as dangling:
            dangling.require("resolve")
            assert dangling.call("find") == 2
        marker.unlink()
        os.mkfifo(marker)
        with Service(library, config) as fifo:
            fifo.require("resolve")
            assert fifo.call("find") == 2
        marker.unlink()
    with marker.open("wb") as oversized:
        oversized.truncate(16 * 1024 * 1024 + 1)
    with Service(library, config) as too_large:
        too_large.require("resolve")
        assert too_large.call("find") == 2
    marker.write_bytes(original)
    for relative in ("../escape", "/absolute", "modules/../../escape", "modules\\escape"):
        altered = json.loads(original)
        altered["artifacts"][0]["path"] = relative
        marker.write_text(json.dumps(altered))
        with Service(library, config) as invalid:
            invalid.require("resolve")
            assert invalid.call("find") == 2
    marker.write_bytes(original)
    for change in (b"", b"X" * len(obj_bytes)):
        obj.write_bytes(change)
        with Service(library, config) as invalid:
            invalid.require("resolve")
            assert invalid.call("find") == 2
    obj.write_bytes(obj_bytes)
    semantic = entry / "modules/std/io.l1m"
    semantic_bytes = semantic.read_bytes()
    semantic.write_bytes(b"altered semantic authority")
    altered = json.loads(original)
    record = next(item for item in altered["artifacts"] if item["path"] == "modules/std/io.l1m")
    record.update(size=semantic.stat().st_size, sha256=hashlib.sha256(semantic.read_bytes()).hexdigest())
    marker.write_text(json.dumps(altered))
    with Service(library, config) as mismatched:
        mismatched.require("resolve")
        assert mismatched.call("find") == 2, "a internally consistent differing semantic copy is unusable"
    semantic.write_bytes(semantic_bytes)
    marker.write_bytes(original)
    if os.name != "nt":
        external = root / "external-object"
        external.write_bytes(obj_bytes)
        obj.unlink()
        obj.symlink_to(external)
        with Service(library, config) as escaped:
            escaped.require("resolve")
            assert escaped.call("find") == 2
        obj.unlink()
        obj.write_bytes(obj_bytes)
    for memo in (Path(config["cache"]) / "v1/memo").rglob("*.json"):
        memo.write_text("{")
    with Service(library, config) as unmemoized:
        unmemoized.require("resolve")
        unmemoized.require("find")
        assert unmemoized.stats()["artifact_content_reads"] == count
        assert unmemoized.stats()["identity_content_reads"] > 0
    marker.unlink()
    (entry / ".manifest.pending").write_text("interrupted completion write")
    with Service(library, config) as interrupted:
        interrupted.require("resolve")
        assert interrupted.call("find") == 0
        assert populate(interrupted) == entry
        assert not (entry / ".manifest.pending").exists()
    with Service(library, {**config, "force": 1}) as forced:
        assert populate(forced) == entry
        assert forced.stats()["identity_content_reads"] > 0
    assert not (Path(config["cache"]) / "v1/interfaces").exists()


def can_create_file(directory: Path) -> bool:
    """Observe actual create permission, including privileged-user chmod bypass.

    Args:
        directory: Owned fixture directory to probe with an exclusive temporary file.

    Returns:
        Whether the current process can create a file in the directory.

    Raises:
        OSError: If probing fails for a reason other than denied permission.
    """
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".write-capability-"):
            return True
    except PermissionError:
        return False


def check_read_only_default(library: Path, root: Path, config: dict) -> None:
    """An implicit read-only root still permits a fully validated existing profile."""
    if os.name == "nt":
        return
    default = root / "build/cache"
    default.unlink()
    shutil.copytree(config["cache"], default)
    version = default / "v1"
    version.chmod(0o555)
    try:
        writable = can_create_file(version)
        implicit_config = {key: value for key, value in config.items() if key != "cache"}
        with Service(library, implicit_config) as readable:
            readable.require("resolve")
            assert readable.get("writable") == ("1" if writable else "0")
            readable.require("find")
        with Service(library, {**config, "cache": str(default)}) as explicit:
            if writable:
                explicit.require("resolve")
            else:
                assert explicit.call("resolve") == 0 and explicit.call("error_code") == 2150
    finally:
        version.chmod(0o755)

    # Writable v1 does not promise its native or coordination child is usable.
    for blocked_name in ("native", "locks"):
        blocked = version / blocked_name
        shutil.rmtree(blocked)
        blocked.write_text("obstructed managed child")
        with Service(library, implicit_config) as obstructed:
            obstructed.require("resolve")
            if blocked_name == "locks":
                assert obstructed.call("lock") == 0
            else:
                obstructed.require("lock")
                assert obstructed.call("begin") == 0
                obstructed.call("unlock")
            obstructed.require("private")
            obstructed.require("begin")
            private_root = Path(obstructed.get("selected"))
        assert not private_root.exists() and blocked.read_text() == "obstructed managed child"
        blocked.unlink()
        blocked.mkdir()


def test_lock_exit(library: Path, root: Path, config: dict) -> None:
    """Process exit releases coordination even though its lock file remains."""
    data = root / "lock-config.json"
    data.write_text(json.dumps(config))
    child = subprocess.Popen([sys.executable, __file__, "--lock-child", str(library), str(data)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        different_data = root / "different-key.json"
        different_data.write_text(json.dumps({**config, "options": ["-std=c99", "-DOTHER_NATIVE_KEY=1"]}))
        different = subprocess.run([sys.executable, __file__, "--lock-child", str(library), str(different_data)],
                                   input="exit\n", capture_output=True, text=True, timeout=60)
        assert different.returncode == 0 and different.stdout.strip() == "locked", different.stderr
        assert child.poll() is None, "different native keys must not share coordination"
        waiter = subprocess.Popen([sys.executable, __file__, "--lock-child", str(library), str(data)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(0.1)
            assert waiter.poll() is None
            child.kill()
            child.wait(timeout=10)
            assert waiter.stdout.readline().strip() == "locked"
            waiter.communicate("exit\n", timeout=10)
            assert waiter.returncode == 0
        finally:
            if waiter.poll() is None:
                waiter.kill()
                waiter.wait()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def main() -> int:
    """Run storage checks in isolated development and installation fixtures."""
    if len(sys.argv) > 1 and sys.argv[1] == "--lock-child":
        with Service(Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text())) as service:
            service.require("resolve")
            service.require("lock")
            print("locked", flush=True)
            sys.stdin.readline()
        return 0
    with tempfile.TemporaryDirectory(prefix="l1-preparation-test-") as temporary:
        root = Path(temporary).resolve()
        dependency_reader = check_native_reader(root, "dependencies")
        spaced_reader = root / "probe directory" / ("preparation dependencies" + dependency_reader.suffix)
        spaced_reader.parent.mkdir()
        shutil.copy2(dependency_reader, spaced_reader)
        run_native_reader(spaced_reader, root / "spaced-reader-files", "spaced-path")
        check_native_reader(root, "libraries")
        check_observability(root)
        check_digest_seeds(root)
        library = build_library(root)
        check_service_lifetime(library, root)
        home = root / "compiler"
        shutil.copytree(L1_ROOT / "compiler/shared", home / "shared")
        (home / "stage1_l0/src").mkdir(parents=True)
        (home / "stage1_l0/support").mkdir()
        (home / "stage1_l0/src/implementation.l0").write_text("implementation fixture")
        shutil.copytree(stage1_compiler().parent.parent / "interfaces", root / "build/interfaces")
        shutil.copytree(stage1_compiler().parent.parent / "include", root / "build/include")
        implementation = root / "l1c"
        implementation.write_text("compiler executable fixture")
        config = dict(home=str(home), self=str(implementation), build_dir=str(root / "build"),
                      cache=str(root / "cache"), compiler=resolve_c_compiler(), options=["-std=c99"])
        env = dict(os.environ)
        env.pop("L1_STDLIB_CACHE", None)
        with patch.dict(os.environ, env, clear=True):
            for invalid in (b'{"cache":[],"options":[]}', b'{"home":"a","home":"b"}', b'{"home":"\\ud800"}', b'{"home":"\xff"}'):
                with Service(library, invalid) as service:
                    assert service.call("error_code") == 2150
            check_roots(library, root, config)
            check_integrity(library, root, config)
            check_read_only_default(library, root, config)
            test_lock_exit(library, root, config)
    print("preparation storage, integrity and process coordination: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
