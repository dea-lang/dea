#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Exercise production entropy branches with narrow simulated host API declarations."""

from __future__ import annotations

import os
from pathlib import Path

from os_runtime_test import L1_ROOT, RUNTIME_ROOT, require_success


FIXTURES = L1_ROOT / "compiler/tests/fixtures/entropy_runtime"


def require_simulated_adapters(work: Path, cc: str, archive: Path) -> None:
    """Compile actual Linux, Windows, and unsupported-host adapter branches.

    Real host headers load before selecting a simulated branch. Only the probe
    and fault translation units receive the platform selectors; the remaining
    runtime comes from an ordinary host archive, including real error mapping.
    These checks do not establish native platform or SDK compatibility.

    Args:
        work: Temporary directory for generated object files and executables.
        cc: Explicit selected host C compiler.
        archive: Host runtime archive used for normal error/string support.

    Raises:
        AssertionError: Compilation fails or a production-branch invariant fails.
    """
    for platform, selector in (
        ("linux", "DEA_ENTROPY_SIMULATE_GETRANDOM"),
        ("windows", "DEA_ENTROPY_SIMULATE_WINDOWS"),
        ("unsupported", "DEA_ENTROPY_SIMULATE_UNSUPPORTED"),
    ):
        objects = []
        sources = ("unsupported_probe",) if platform == "unsupported" else ("native_probe", "entropy_faults")
        for name in sources:
            obj = work / f"entropy-simulated-{platform}-{name}.o"
            require_success([
                cc, "-std=c99", "-Wall", "-Wextra", "-Werror", f"-D{selector}=1",
                f"-I{FIXTURES / 'simulated' / platform}",
                f"-I{RUNTIME_ROOT / 'include'}", f"-I{RUNTIME_ROOT / 'src'}",
                "-include", str(FIXTURES / "simulated/platform.h"),
                "-c", str(FIXTURES / f"{name}.c"), "-o", str(obj),
            ], timeout=120)
            objects.append(str(obj))
        executable = work / (f"entropy-simulated-{platform}" + (".exe" if os.name == "nt" else ""))
        require_success([cc, *objects, str(archive), "-lm", "-o", str(executable)], timeout=120)
        completed = require_success([str(executable)], timeout=60)
        assert completed.stdout == "entropy native adapters: PASS\n", completed.stdout
        print(f"Simulated {platform} entropy adapter: PASS", flush=True)
