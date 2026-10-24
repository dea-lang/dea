#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Portable regressions for the actual runtime's pure Windows/POSIX path helpers."""

from pathlib import Path
import os
import tempfile

from os_runtime_test import RUNTIME_ROOT, require_success, runtime_c_compiler


def main() -> int:
    """Compile both spelling branches independently of the host filesystem APIs.

    Returns:
        Zero after both native-character helper probes pass.

    Raises:
        AssertionError: A spelling, root guard, or strict compilation check fails.
    """
    cc = runtime_c_compiler()
    source = Path(__file__).parent / "fixtures/filesystem_runtime/path_probe.c"
    with tempfile.TemporaryDirectory(prefix="l1-fs-path-") as raw:
        work = Path(raw)
        for mode, flags in (("posix", []), ("windows", ["-DDEA_FS_PATH_TEST_WINDOWS"])):
            executable = work / (mode + (".exe" if os.name == "nt" else ""))
            require_success([
                cc, "-std=c99", "-Wall", "-Wextra", "-Werror", *flags,
                f"-I{RUNTIME_ROOT / 'internal'}", str(source.resolve()), "-o", str(executable),
            ])
            require_success([str(executable)])
    print("filesystem_path_support_test: PASS (simulated Windows and POSIX spelling semantics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
