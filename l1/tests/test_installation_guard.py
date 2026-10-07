# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
"""Native installed-prefix startup fixtures without a compiler bootstrap."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_stage2_l1c import host_compiler
from productization_inventory import MANIFEST_PATH, InventoryError, install_payload, validate_inventory


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    root = tmp_path_factory.mktemp("installation native")
    source = root / "probe.c"
    source.write_text('''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
extern int32_t l1c_installation_startup(void);
int main(void) {
    int rc = l1c_installation_startup();
    if (rc) return rc;
    printf("%s\\n%s\\n%s\\n", getenv("L1_HOME"),
        getenv("L1_BUILD_DIR") ? getenv("L1_BUILD_DIR") : "unset",
        getenv("L1_STDLIB_CACHE") ? getenv("L1_STDLIB_CACHE") : "unset");
    return 0;
}
''')
    executable = root / ("probe.exe" if os.name == "nt" else "probe")
    support = ROOT / "compiler/stage1_l0/support"
    subprocess.run([host_compiler(dict(os.environ)), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
                    str(source), str(support / "compiler_support.c"), str(support / "preparation_support.c"),
                    "-o", str(executable)], check=True)
    return executable


@pytest.fixture
def installed(tmp_path, native):
    payload = tmp_path / "payload"
    (payload / "bin").mkdir(parents=True)
    shutil.copy2(native, payload / "bin" / native.name)
    prefix = tmp_path / "prefix with spaces"
    metadata = {"package_version": "dev", "maturity": "development", "os": "linux", "arch": "x86_64",
                "provenance": {"build": "fixture", "extra": [1.5, 1e-20, 2 ** 80, "caf\u00e9 \U0001f680"]}}
    record = install_payload(payload, prefix, metadata)
    return prefix, record, native.name


def invoke(prefix, name):
    return subprocess.run([str(prefix / "bin" / name)], cwd=prefix.parent,
                          env={**os.environ, "PATH": "", "L1_HOME": "stale/source", "L1_BUILD_DIR": "stale/build",
                               "L1_STDLIB_CACHE": "explicit-cache"}, capture_output=True, text=True)


def write(prefix, record):
    (prefix / MANIFEST_PATH).write_text(json.dumps(record), encoding="utf-8")


def test_valid_inventory_relocation_and_context(installed):
    prefix, record, name = installed
    moved = prefix.with_name("relocated prefix with spaces")
    prefix.rename(moved)
    result = invoke(moved, name)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(moved), "unset", "explicit-cache"]
    # Startup validates state, not payload hashes or unrelated prefix files.
    (moved / "unrelated").write_text("unowned")
    record["entries"][0]["sha256"] = "0" * 64
    write(moved, record)
    assert invoke(moved, name).returncode == 0


@pytest.mark.parametrize("change", ["missing", "garbage", "duplicate-key", "duplicate-path", "incomplete", "version",
                                    "float-version", "bool-stage", "extra", "empty-provenance", "unsafe-path", "mode",
                                    "digest", "alias-escape", "alias-cycle", "alias-dangling", "parent", "manifest",
                                    "invalid-utf8", "nul", "fifo", "metadata-link", "parent-link"])
def test_invalid_inventory_fails_closed(installed, tmp_path, change):
    prefix, record, name = installed
    path = prefix / MANIFEST_PATH
    if change == "missing":
        path.unlink()
    elif change in {"garbage", "duplicate-key", "invalid-utf8", "nul"}:
        data = {"garbage": b'{', "duplicate-key": b'{"state":"complete",' + path.read_bytes()[1:],
                "invalid-utf8": path.read_bytes().replace(b'fixture', b'\xff'),
                "nul": path.read_bytes() + b'\0'}[change]
        path.write_bytes(data)
    elif change in {"fifo", "metadata-link", "parent-link"}:
        if os.name == "nt":
            pytest.skip("POSIX file substitution fixture")
        if change == "fifo":
            path.unlink()
            os.mkfifo(path)
        elif change == "metadata-link":
            target = tmp_path / "metadata"
            path.rename(target)
            path.symlink_to(target)
        else:
            target = tmp_path / "metadata parent"
            path.parent.rename(target)
            path.parent.symlink_to(target, target_is_directory=True)
    else:
        file = record["entries"][0]
        if change == "duplicate-path": record["entries"].append(copy.deepcopy(file))
        elif change == "incomplete": record["state"] = "incomplete"
        elif change == "version": record["schema_version"] = 2
        elif change == "float-version": record["schema_version"] = 1.0
        elif change == "bool-stage": record["stage"] = True
        elif change == "extra": record["unexpected"] = "value"
        elif change == "empty-provenance": record["provenance"] = {}
        elif change == "unsafe-path": file["path"] = "../escape"
        elif change == "mode": file["mode"] = 777
        elif change == "digest": file["sha256"] = "bad"
        elif change == "parent": record["entries"].append({**file, "path": file["path"] + "/child"})
        elif change == "manifest": record["entries"].pop()
        elif change.startswith("alias-"):
            target = {"alias-escape": "../../outside", "alias-cycle": "alias", "alias-dangling": "absent"}[change]
            record["entries"].append({"path": "bin/alias", "kind": "alias", "target": target})
        write(prefix, record)
    result = invoke(prefix, name)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "[L1C-9515]" in result.stderr
    # Native diagnostics can join Windows prefixes with forward-slash suffixes.
    assert str(path).replace(os.sep, "/") in result.stderr.replace(os.sep, "/")
    assert "repair or retry installation" in result.stderr


def test_valid_relative_alias(installed):
    prefix, record, name = installed
    record["entries"].append({"path": "bin/alias", "kind": "alias", "target": "../bin/" + name})
    write(prefix, record)
    assert invoke(prefix, name).returncode == 0


def test_unreadable_metadata(installed):
    if os.name == "nt" or os.geteuid() == 0:
        pytest.skip("requires POSIX mode enforcement for a non-root process")
    prefix, _, name = installed
    path = prefix / MANIFEST_PATH
    path.chmod(0)
    try:
        result = invoke(prefix, name)
        assert result.returncode == 1 and "[L1C-9515]" in result.stderr
    finally:
        path.chmod(0o644)


@pytest.mark.parametrize("value", ["bad\0string", "\ud800", {1: "non-string key"}, float("nan")])
def test_installer_rejects_native_unreadable_provenance(installed, value):
    _, record, _ = installed
    record["provenance"]["extra"] = value
    with pytest.raises(InventoryError):
        validate_inventory(record)


def test_installer_rejects_native_nesting_limit(installed):
    _, record, _ = installed
    value = []
    for _ in range(65):
        value = [value]
    record["provenance"]["extra"] = value
    with pytest.raises(InventoryError, match="nesting"):
        validate_inventory(record)


def test_inherited_prefix_cannot_replace_physical_location(installed, native):
    prefix, _, _ = installed
    result = subprocess.run([str(native)], env={**os.environ, "L1_HOME": str(prefix)},
                            capture_output=True, text=True)
    assert result.returncode == 1 and "[L1C-9515]" in result.stderr


def test_external_executable_alias_uses_physical_prefix(installed, tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX executable alias fixture")
    prefix, _, name = installed
    alias = tmp_path / "external executable alias"
    alias.symlink_to(prefix / "bin" / name)
    result = subprocess.run([str(alias)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == str(prefix)
