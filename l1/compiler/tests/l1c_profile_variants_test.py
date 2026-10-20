#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Check explicit runtime variants and frozen native option directory semantics."""

from __future__ import annotations

from functools import partial
import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile

from l1c_managed_preparation_test import invoke, preparation_c_compiler, toolchain_fixture
from l1c_profile_test import no_preparation, snapshot


def main() -> int:
    """Create each runtime variant and consume its locked options from a different cwd.

    Returns:
        Zero after configuration, invocation and refusal checks pass.
    """
    cc = preparation_c_compiler()
    assert cc
    env = dict(os.environ)
    for name in ("L1_CC", "L1_CFLAGS", "L1_SYSTEM", "L1_RUNTIME_INCLUDE", "L1_RUNTIME_LIB", "L1_STDLIB_CACHE"):
        env.pop(name, None)
    # Relative option words remain whitespace-delimited, while freezing their
    # absolute paths must preserve spaces through every native invocation.
    with tempfile.TemporaryDirectory(prefix="l1 profile variants ") as directory:
        root = Path(directory).resolve()
        compiler = toolchain_fixture(root, env)
        create = partial(invoke, root, env, compiler=compiler)
        (root / "app.l1").write_text(
            'module app; import std.io; func main() { printl_s("variant-ok"); }\n', encoding="utf-8")
        native_include = root / "native-include"
        native_include.mkdir()
        (native_include / "profile_config.h").write_text(
            '#ifndef APP_PROFILE_ONLY\n#error "generated-C options were lost"\n#endif\n', encoding="utf-8")
        flags = "-O0 -DAPP_PROFILE_ONLY=1 -I native-include -include native-include/profile_config.h"
        consumer_root = root / "different-cwd"
        consumer_root.mkdir()
        original_env = dict(env)
        response = root / "macro.rsp"
        response.write_text("PROFILE_RESPONSE_DEFINE=1\n", encoding="utf-8")
        rejected_cache = root / "rejected-cache"
        env["L1_STDLIB_CACHE"] = str(rejected_cache)
        for value in ("@unsupported-response", "--config=unsupported-config", "-D @macro.rsp"):
            destination = root / "rejected"
            rejected = create("--create-profile", "--c-compiler", cc,
                              "--c-options=" + value, "-o", str(destination), expected=1)
            assert "L1C-2180" in rejected.stderr, rejected.stderr
            assert not destination.exists() and not list(root.glob(".l1-profile-*"))
            assert not rejected_cache.exists()
            assert response.read_text(encoding="utf-8") == "PROFILE_RESPONSE_DEFINE=1\n"
        variants = (("default", ()), ("check_basic", ("--check-basic",)),
                    ("unchecked", ("--unchecked",)), ("traced", ("--trace-arc", "--trace-memory")))
        for variant, settings in variants:
            env.clear()
            env.update(original_env)
            profile = root / ("profile-" + variant)
            created = create("--create-profile", "--c-compiler", cc, "--c-options=" + flags,
                             *settings, "-o", str(profile))
            assert not created.stdout, created.stdout
            manifest = json.loads((profile / "profile.json").read_text(encoding="utf-8"))
            configuration = manifest["configuration"]
            assert configuration["variant"] == variant, configuration
            assert "-DAPP_PROFILE_ONLY=1" in configuration["options"]
            assert "-DAPP_PROFILE_ONLY=1" not in configuration["runtime_options"]
            assert "-include" not in configuration["runtime_options"]
            include_index = configuration["options"].index("-I")
            recorded_include = Path(configuration["options"][include_index + 1])
            assert recorded_include.is_absolute() and recorded_include.samefile(native_include)
            header_index = configuration["options"].index("-include")
            assert Path(configuration["options"][header_index + 1]).samefile(native_include / "profile_config.h")
            moved = consumer_root / ("moved-" + variant)
            profile.rename(moved)
            before = snapshot(moved)
            env.update(L1_CC="missing-profile-compiler", L1_CFLAGS="-ffast-math",
                       L1_SYSTEM=str(root / "missing-system"), L1_RUNTIME_INCLUDE=str(root / "missing-headers"),
                       L1_RUNTIME_LIB=str(root / "missing-runtime"), L1_STDLIB_CACHE=str(root / "must-not-create-cache"))
            ran = invoke(consumer_root, env, "--run", "app", "--project-root", str(root),
                         "--profile", str(moved), "-vvv", compiler=compiler)
            assert ran.stdout == "variant-ok\n", ran.stdout
            no_preparation(ran)
            assert before == snapshot(moved), "variant consumption changed profile payloads"
            assert not (root / "must-not-create-cache").exists()
        tcc = shutil.which("tcc")
        if tcc is not None:
            env.clear()
            env.update(original_env)
            profile = root / "tinycc-profile"
            create("--create-profile", "--c-compiler", tcc, "-o", str(profile))
            manifest = json.loads((profile / "profile.json").read_text(encoding="utf-8"))
            assert manifest["configuration"]["family"] == "tcc"
            assert len(manifest["runtime"]) == 9 and all(path.endswith(".o") for path in manifest["runtime"])
            ran = create("--run", "app", "--profile", str(profile), "-vvv")
            assert ran.stdout == "variant-ok\n", ran.stdout
            no_preparation(ran)
        # A shebang compiler is invocable but deliberately cannot certify managed persistent reuse.
        # Shell wrappers are POSIX fixtures; Windows exercises the native compiler variant matrix above.
        if os.name != "nt":
            env.clear()
            env.update(original_env)
            wrapper_dir = root / "compiler-wrapper"
            wrapper_dir.mkdir()
            wrapper = wrapper_dir / "native-driver"
            wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(cc) + ' "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
            cache = root / "wrapper-managed-cache"
            refused = create("--prepare-stdlib", "--c-compiler", str(wrapper),
                             "--stdlib-cache", str(cache), expected=1)
            assert "L1C-2154" in refused.stderr and "wrapper" in refused.stderr, refused.stderr
            profile = root / "wrapper-profile"
            create("--create-profile", "--c-compiler", str(wrapper), "-o", str(profile))
            ran = create("--run", "app", "--profile", str(profile), "--rpath", str(native_include), "-vvv")
            assert ran.stdout == "variant-ok\n", ran.stdout
            no_preparation(ran)
    print("explicit L1 profile variants: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
