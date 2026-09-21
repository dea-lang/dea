#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Windows startup-environment regression for native preparation identity."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from compiler_filesystem_support_test import resolve_c_compiler
from l1c_stage1_compile_only_test import stage1_compiler
from preparation_identity_test import identity_in_environment
from preparation_support_test import build_library, L1_ROOT


def main() -> int:
    """Verify Windows memo selection against the native startup environment."""
    if os.name != "nt":
        print("Windows native identity startup environment: SKIP")
        return 0
    with tempfile.TemporaryDirectory(prefix="l1-native-identity-windows-environment-") as directory:
        root = Path(directory).resolve()
        library = build_library(root)
        home, build = root / "compiler", root / "build"
        shutil.copytree(L1_ROOT / "compiler/shared", home / "shared")
        (home / "stage1_l0/src").mkdir(parents=True)
        (home / "stage1_l0/support").mkdir()
        (home / "stage1_l0/src/implementation.l0").write_text("implementation fixture")
        executable = root / "l1c"
        executable.write_text("executable fixture")
        for name in ("include", "interfaces"):
            shutil.copytree(stage1_compiler().parent.parent / name, build / name)
        config = dict(home=str(home), self=str(executable), build_dir=str(build), cache=str(root / "cache"),
                      compiler=resolve_c_compiler(), options=["-std=c99"])
        environment = dict(os.environ)
        for name in ("L1_STDLIB_CACHE", "L1_CFLAGS", "L1_RUNTIME_CC", "RUNTIME_CFLAGS", "AR"):
            environment.pop(name, None)
        with patch.dict(os.environ, environment, clear=True):
            pathext = os.environ.get("PATHEXT", "")
            base_environment = {"PATHEXT": pathext}
            changed_environment = {
                "PATHEXT": pathext + (os.pathsep if pathext else "") + ".DEAIDENTITY"
            }
            before = identity_in_environment(library, config, base_environment)
            warm = identity_in_environment(library, config, base_environment)
            assert warm[:3] == before[:3], "unchanged startup environment must preserve native identity"
            assert warm[3]["probes"] <= 4, "unchanged startup environment must reuse observation"
            changed = identity_in_environment(library, config, changed_environment)
            assert changed[:3] == before[:3], "irrelevant PATHEXT spelling must not change native identity"
            assert changed[3]["probes"] > 4, "new startup environment must reobserve"
    print("Windows native identity startup environment: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
