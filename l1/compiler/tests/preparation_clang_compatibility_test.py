#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Clang configuration isolation, fresh legacy selection, and scratch ownership."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from compiler_filesystem_support_test import resolve_c_compiler
from l1c_compile_only_test import stage1_compiler
from preparation_identity_test import (
    component_digest, has_component, identity, identity_in_environment, check_runtime_compilation,
)
from preparation_support_test import L1_ROOT, Service, build_library, compile_native


def check_legacy_selection(library: Path, root: Path, config: dict) -> None:
    """Use the selected legacy driver as the oracle for configuration precedence.

    Args:
        library: Compiled preparation service.
        root: Owned directory for configuration, aliases, and scratch fixtures.
        config: Preparation configuration selecting a real legacy Clang compiler.
    """
    compiler = config["compiler"]
    system, user = root / "system configs", root / "user configs"
    system.mkdir()
    user.mkdir()
    target = subprocess.check_output([compiler, "-dumpmachine"], text=True).strip()
    alias = root / (target + "-clang")
    alias.symlink_to(compiler)
    options = ["--config-system-dir=" + str(system), "--config-user-dir=" + str(user)]
    selected = {**config, "compiler": str(alias), "options": options}
    plain = identity(library, selected)
    assert plain[2]["runtime"]["configuration_isolation"] == "clang-explicit-empty-config-v1"
    assert identity(library, selected)[:2] == plain[:2]
    name = alias.name + ".cfg"
    lower, higher = system / name, user / name
    lower.write_text("-DDEA_LEGACY_APPLICATION=1 -fPIC\n")
    created = identity(library, selected)
    assert created[0] == plain[0] and created[1] != plain[1]
    assert has_component(created[2], lower)
    assert "-fPIC" in created[2]["runtime"]["options"]
    assert "-DDEA_LEGACY_APPLICATION=1" not in created[2]["runtime"]["options"]
    lower.write_text("-DDEA_LEGACY_APPLICATION=2 -fPIC\n")
    changed = identity(library, selected)
    assert changed[1] != created[1], "application-only config edits must invalidate native identity"
    assert changed[2]["runtime"]["options"] == created[2]["runtime"]["options"]
    assert changed[2]["toolchain"]["runtime_target_macros"] == created[2]["toolchain"]["runtime_target_macros"]
    higher.write_text("-DDEA_LEGACY_APPLICATION=3 -fno-pic\n")
    shadowed = identity(library, selected)
    assert shadowed[1] != changed[1] and has_component(shadowed[2], higher)
    assert not has_component(shadowed[2], lower)
    assert "-fno-pic" in shadowed[2]["runtime"]["options"]
    actual = subprocess.run([str(alias), *options, "-###", "-x", "c", "-c", os.devnull],
                            capture_output=True, text=True, check=True)
    selected_paths = [Path(line.removeprefix("Configuration file: ").strip())
                      for line in actual.stderr.splitlines() if line.startswith("Configuration file: ")]
    assert higher in selected_paths and "DEA_LEGACY_APPLICATION=3" in actual.stderr
    higher.unlink()
    assert identity(library, selected)[:2] == changed[:2]
    lower.unlink()
    assert identity(library, selected)[:2] == plain[:2]
    lower.write_text("-DDEA_LEGACY_APPLICATION=1 -fPIC\n")
    assert identity(library, selected)[:2] == created[:2]
    # Reversing search roots changes selection even when compiler spelling stays fixed.
    higher.write_text("-DDEA_LEGACY_APPLICATION=4 -fno-pic\n")
    reversed_options = ["--config-system-dir=" + str(user), "--config-user-dir=" + str(system)]
    reversed_selection = identity(library, {**selected, "options": reversed_options})
    assert has_component(reversed_selection[2], lower) and not has_component(reversed_selection[2], higher)
    # Explicit configuration supersedes implicit application flags and records transitive inputs.
    nested = root / "nested options.rsp"
    nested.write_text("-DDEA_LEGACY_NESTED=1 -fPIC -fshort-enums\n")
    explicit = root / "explicit configuration.cfg"
    explicit.write_text("@" + shlex.quote(str(nested)) + "\n")
    explicit_options = [*options, "--config", str(explicit)]
    configured = {**selected, "options": explicit_options}
    first = identity(library, configured)
    assert has_component(first[2], explicit) and has_component(first[2], nested)
    assert not has_component(first[2], lower) and not has_component(first[2], higher)
    assert {"-fPIC", "-fshort-enums"}.issubset(first[2]["runtime"]["options"])
    warm = identity(library, configured)
    assert warm[:2] == first[:2] and warm[3]["identity_content_reads"] == 2
    assert warm[3]["probes"] <= 6 and warm[3]["build_commands"] == 0
    nested.write_text("-DDEA_LEGACY_NESTED=2 -fPIC -fshort-enums\n")
    edited = identity(library, configured)
    assert edited[0] == first[0] and edited[1] != first[1]
    assert component_digest(edited[2], nested) != component_digest(first[2], nested)
    assert identity(library, {**configured, "force": 1})[:2] == edited[:2]
    nested.unlink()
    with Service(library, configured) as missing:
        assert missing.call("resolve") == 0 and missing.call("error_code") == 2154
    nested.write_text("-DDEA_LEGACY_NESTED=1 -fPIC -fshort-enums\n")
    assert identity(library, configured)[:2] == first[:2]
    # Different process-local physical files cannot contribute to N or retained memo inputs.
    for name in ("scratch one", "scratch two"):
        scratch = root / name
        scratch.mkdir()
        isolated = identity_in_environment(library, configured, {"TMPDIR": str(scratch)})
        assert isolated[:2] == first[:2] and not list(scratch.iterdir())
        assert str(scratch) not in json.dumps(isolated[2])
        for memo in Path(config["cache"]).glob("v1/memo/toolchains/*.json"):
            assert str(scratch) not in memo.read_text()
    for variant in ("default", "traced", "unchecked", "check_basic"):
        check_runtime_compilation(library, configured, variant, "clang")
    # Runtime-only baseline defines distinguish leaked application preprocessing
    # from the generated-C dependency probes used to authorize the source snapshot.
    poison = root / "application-only header.h"
    poison.write_text("#ifdef _RT_QUARANTINE_MAX_BYTES\n#error application config leaked into runtime\n#endif\n")
    higher.write_text("-include " + shlex.quote(str(poison)) + " -fPIC\n")
    check_construction_snapshot(library, root / "implicit snapshot", selected)
    explicit.write_text("--this-option-is-invalid-for-clang\n")
    with Service(library, configured) as malformed:
        assert malformed.call("resolve") == 0 and malformed.call("error_code") == 2154
        assert "--this-option-is-invalid-for-clang" in malformed.get("error")


def check_construction_snapshot(library: Path, root: Path, config: dict) -> None:
    """Recreate legacy isolation from a snapshot after its original context is destroyed.

    Args:
        library: Compiled preparation service.
        root: Owned directory for the direct payload and isolated scratch roots.
        config: Managed preparation configuration that selects legacy isolation.
    """
    root.mkdir()
    scratch = root / "construction scratch with spaces"
    scratch.mkdir()
    destination = root / "direct caller-owned payload"
    destination.mkdir()
    sentinel = destination / "caller-owned"
    sentinel.write_text("retain")
    with patch.dict(os.environ, {"TMPDIR": str(scratch)}):
        with Service(library, config) as managed:
            managed.require("resolve")
            managed.require("private")
            managed.require("begin")
            snapshot_text = managed.get("construction_inputs")
            snapshot = json.loads(snapshot_text)
            assert snapshot["runtime_configuration_isolation"] == "clang-explicit-empty-config-v1"
            original = list(scratch.glob("*/empty.cfg"))
            assert len(original) == 1
            assert str(scratch) not in snapshot_text and "--config" not in snapshot["runtime_options"]
        assert not original[0].exists() and not list(scratch.glob("l1-preparation-*"))
        with Service(library, snapshot, destination) as direct:
            assert direct.call("error_code") == 0, direct.get("error")
            owned = list(scratch.glob("*/empty.cfg"))
            assert len(owned) == 1 and owned != original
            assert direct.stats()["probes"] == direct.stats()["native_resolutions"] == 0
            direct.require("copy_interfaces")
            for module in snapshot["modules"]:
                (destination / "modules" / (module.replace(".", "/") + ".o")).write_bytes(b"opaque module fixture")
            direct.require("runtime")
            direct.require("construction_complete")
            assert direct.stats()["probes"] == direct.stats()["native_resolutions"] == 0
            assert direct.stats()["build_commands"] == 10 and direct.stats()["module_compiles"] == 0
            assert json.loads(direct.get("construction_inputs")) == snapshot
        assert not list(scratch.glob("l1-preparation-*"))
    assert sentinel.read_text() == "retain" and not (destination / "manifest.json").exists()
    assert (destination / "lib/libdea_rt.a").stat().st_size > 0


def build_capability_driver(root: Path, compiler: str) -> tuple[Path, Path, Path]:
    """Compile a native fixture that exposes independent capability failure classes.

    Args:
        root: Owned fixture directory.
        compiler: Real Clang to run after controlled probe interception.

    Returns:
        Native driver, mode file, and invocation log paths.
    """
    source, driver = root / "capability-driver.c", root / "capability-clang"
    mode, log = root / "capability-mode", root / "capability-argv"
    source.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
/** Forward real work while exposing deterministic unsupported, error, and timeout probes. */
int main(int argc, char **argv) {
    FILE *input = fopen(MODE_PATH, "r"), *output = fopen(LOG_PATH, "a");
    int mode = 0, modern = 0, explicit_config = 0, isolation = 0, selection = 0, compilation = 0, archive = 0;
    if (input) { if (fscanf(input, "%d", &mode) != 1) mode = 0; fclose(input); }
    for (int i = 1; i < argc; ++i) {
        if (output) fprintf(output, "%s\n", argv[i]);
        if (!strcmp(argv[i], "--no-default-config")) modern = 1;
        if (!strcmp(argv[i], "--config")) {
            explicit_config = 1;
            if (i + 1 < argc && strstr(argv[i + 1], "/empty.cfg")) isolation = 1;
        }
        if (!strcmp(argv[i], "-###")) selection = 1;
        if (strstr(argv[i], "dea_rt_") && strstr(argv[i], ".c")) compilation = 1;
        if (!strcmp(argv[i], "-print-prog-name=ar")) archive = 1;
    }
    if (output) { fputs("END\n", output); fclose(output); }
    if (modern) {
        if (mode == 2) { fputs("controlled unrelated capability error\n", stderr); return 1; }
        if (mode == 3) sleep(2);
        if (mode == 11) { fputs("clang: error: unsupported option '--no-default-config-extra'\n", stderr); return 1; }
        if (mode == 12) { fputs("clang: error: unknown argument '--no-default-confog'; did you mean '--no-default-config'?\n", stderr); return 1; }
        fputs("clang: error: unsupported option '--no-default-config'\n", stderr); return mode == 10 ? 2 : 1;
    }
    if (mode == 4 && explicit_config) {
        fputs("controlled explicit configuration failure\n", stderr); return 1;
    }
    if (mode == 8 && explicit_config) { fputs("clang: error: unsupported option '--config'\n", stderr); return 1; }
    if (mode == 9 && explicit_config) { fputs("clang: error: unsupported option '--config-user-dir'\n", stderr); return 1; }
    if (mode == 5 && selection && !isolation) return 1;
    if (mode == 6 && compilation) { fputs("controlled runtime compilation failure\n", stderr); return 1; }
    if (mode == 7 && archive) { puts("/missing-controlled-runtime-archiver"); return 0; }
    argv[0] = COMPILER_PATH;
    execv(argv[0], argv);
    return 127;
}
'''.replace("MODE_PATH", json.dumps(str(mode))).replace("LOG_PATH", json.dumps(str(log)))
        .replace("COMPILER_PATH", json.dumps(compiler)))
    compile_native(driver, [source])
    mode.write_text("0")
    return driver, mode, log


def check_capability_ownership(library: Path, root: Path, config: dict) -> None:
    """Exercise legacy scratch lifetime and failure discrimination with a native fixture.

    Args:
        library: Compiled preparation service.
        root: Owned directory for native driver and context-local temporary files.
        config: Preparation configuration selecting a real Clang compiler.
    """
    if os.name == "nt":
        return  # The injected native driver uses execv; real argv paths remain covered on Windows.
    driver, mode, log = build_capability_driver(root, config["compiler"])
    selected = {**config, "compiler": str(driver)}
    scratch = root / "owned scratch with spaces"
    scratch.mkdir()
    with patch.dict(os.environ, {"TMPDIR": str(scratch)}):
        with Service(library, selected) as first:
            first.require("resolve")
            assert not first.get("ineligible"), first.get("ineligible")
            first_key = first.get("native_key")
            owned = list(scratch.glob("*/empty.cfg"))
            assert len(owned) == 1 and owned[0].is_file() and owned[0].read_bytes() == b""
            assert str(scratch) not in first.get("native_identity")
            before = first.stats()["probes"]
            first.require("resolve")
            assert first.stats()["probes"] == before, "capability is resolved once per context"
            with Service(library, selected) as second:
                second.require("resolve")
                assert second.get("native_key") == first_key
                assert len(list(scratch.glob("*/empty.cfg"))) == 2
            assert list(scratch.glob("*/empty.cfg")) == owned
        # Apple Clang can retain its unrelated xcrun_db in TMPDIR.
        assert not list(scratch.glob("l1-preparation-*")), list(scratch.iterdir())
        for value, diagnostic in ((2, "controlled unrelated"), (3, "timed out"),
                                  (4, "controlled explicit"), (7, "runtime archiver"),
                                  (8, "cannot isolate runtime configuration"), (9, "--config-user-dir"),
                                  (10, "--no-default-config"), (11, "--no-default-config-extra"),
                                  (12, "--no-default-confog")):
            mode.write_text(str(value))
            log.write_text("")
            with Service(library, {**selected, "probe_timeout_ms": 500, "force": int(value == 7)}) as failed:
                resolved = failed.call("resolve")
                assert resolved == 0 and failed.call("error_code") == 2154, (
                    value, resolved, failed.call("error_code"), failed.get("error"))
                assert diagnostic in failed.get("error"), failed.get("error")
                if value == 9:
                    assert "cannot isolate runtime configuration" not in failed.get("error")
                assert not list(scratch.glob("l1-preparation-*")), "failed resolution releases isolation scratch"
            assert not list(scratch.glob("l1-preparation-*")), list(scratch.iterdir())
            if value in (2, 3, 10, 11, 12):
                assert "--config\n" not in log.read_text(), "unrelated failures must not select legacy fallback"
        mode.write_text("5")
        with Service(library, selected) as unobservable:
            assert unobservable.call("resolve") == 0 and unobservable.call("error_code") == 2154
            assert "cannot establish safe legacy Clang runtime configuration" in unobservable.get("error")
        known_config = root / "known private config.cfg"
        known_config.write_text("-fPIC -DDEA_APPLICATION_ONLY=1\n")
        private = {**selected, "options": ["--config", str(known_config)]}
        identity(library, private, eligible=False)
        identity(library, {**private, "force": 1}, eligible=False)
        check_runtime_compilation(library, private, "default", "clang")
        assert not list(scratch.glob("l1-preparation-*")), list(scratch.iterdir())
        mode.write_text("0")
        check_construction_snapshot(library, root / "capability snapshot", selected)
        with Service(library, selected) as failed_build:
            failed_build.require("resolve")
            failed_build.require("private")
            failed_build.require("begin")
            mode.write_text("6")
            compiled = failed_build.call("runtime")
            assert compiled == 0 and failed_build.call("error_code") == 2156, (
                compiled, failed_build.call("error_code"), failed_build.get("error"))
            assert "native preparation command failed" in failed_build.get("error")
        assert not list(scratch.glob("l1-preparation-*")), list(scratch.iterdir())


def main() -> int:
    """Require safe native Clang isolation and exercise real legacy selection when present."""
    compiler = resolve_c_compiler()
    version = subprocess.check_output([compiler, "--version"], text=True)
    if "clang" not in version:
        compiler = shutil.which("clang")
        if compiler is None:
            print("Clang compatibility: SKIP: no Clang available")
            return 0
    compiler = str(Path(compiler).absolute())
    with tempfile.TemporaryDirectory(prefix="l1-clang-compatibility-") as directory:
        root = Path(directory).resolve()
        library = build_library(root)
        home, build = root / "compiler", root / "build"
        shutil.copytree(L1_ROOT / "compiler/shared", home / "shared")
        (home / "src").mkdir()
        (home / "support").mkdir()
        (home / "src/implementation.l0").write_text("implementation fixture")
        executable = root / "l1c"
        executable.write_text("executable fixture")
        for name in ("include", "interfaces"):
            shutil.copytree(stage1_compiler().parent.parent / name, build / name)
        config = dict(home=str(home), self=str(executable), build_dir=str(build), cache=str(root / "cache"),
                      compiler=compiler, options=["-std=c99"])
        env = dict(os.environ)
        for name in ("L1_STDLIB_CACHE", "L1_CFLAGS", "L1_RUNTIME_CC", "RUNTIME_CFLAGS", "AR"):
            env.pop(name, None)
        with patch.dict(os.environ, env, clear=True):
            probe = subprocess.run([compiler, "--no-default-config", "-print-prog-name=ar"],
                                   capture_output=True, text=True)
            if probe.returncode:
                assert "--no-default-config" in probe.stderr
                check_legacy_selection(library, root, config)
            else:
                observed = identity(library, config)
                assert observed[2]["runtime"]["configuration_isolation"] == "clang-no-default-config-v1"
            check_capability_ownership(library, root, config)
    print("Clang configuration isolation, selection invalidation and scratch ownership: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
