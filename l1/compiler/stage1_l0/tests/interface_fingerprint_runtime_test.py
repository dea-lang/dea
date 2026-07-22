#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Known-answer coverage for the L1 interface-fingerprint C bridge."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_INCLUDE = RUNTIME_ROOT / "include"
RUNTIME_INTERNAL = RUNTIME_ROOT / "internal"
STAGE1_SUPPORT = L1_ROOT / "compiler" / "stage1_l0" / "support" / "interface_fingerprint.c"
EXPECTED_HEX = "0c3810c9b2f8823a"


def build_dir() -> Path:
    """Return the configured repo-local L1 build directory."""

    raw = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    return raw if raw.is_absolute() else (L1_ROOT / raw).resolve()


def resolve_c_compiler() -> str:
    """Return one available C compiler without changing compiler families."""

    for configured in (
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        os.environ.get("CC", "").strip(),
    ):
        if configured:
            resolved = shutil.which(configured)
            if resolved is None:
                raise AssertionError(f"configured C compiler was not found: {configured}")
            return resolved

    for candidate in ("clang", "gcc", "cc"):
        resolved = shutil.which(candidate)
        if resolved is not None:
            return resolved
    raise AssertionError("interface-fingerprint runtime test requires a C compiler")


def compile_and_run(
    compiler: str,
    output_path: Path,
    sources: list[Path],
    *,
    archive: Path | None = None,
) -> None:
    """Compile and run one bridge known-answer harness."""

    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        f"-I{RUNTIME_INCLUDE}",
        f"-I{RUNTIME_INTERNAL}",
        *(str(source) for source in sources),
    ]
    if archive is not None:
        command.append(str(archive))
    command.extend(["-o", str(output_path)])

    completed = subprocess.run(
        command,
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"C compilation exited with {completed.returncode}:\n{completed.stdout}"
        )

    run = subprocess.run(
        [str(output_path)],
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if run.returncode != 0:
        raise AssertionError(
            f"known-answer harness exited with {run.returncode}:\n{run.stdout}"
        )


def main() -> int:
    """Compare the direct implementation, Stage 1 shim, and every archive mode."""

    compiler = resolve_c_compiler()
    with tempfile.TemporaryDirectory(prefix="l1_interface_fingerprint_runtime_test.") as raw_temp:
        temp_dir = Path(raw_temp)

        direct_harness = temp_dir / "direct_harness.c"
        direct_harness.write_text(
            f'''#define SIPHASH_IMPLEMENTATION
#include <stdint.h>
#include <string.h>
#include "dea_interface_fingerprint.h"

void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
);

int main(void) {{
    static const uint8_t input[] = {{ 'i', 'n', 'p', 'u', 't' }};
    static const uint8_t expected[] = "{EXPECTED_HEX}";
    uint64_t direct_hash;
    uint8_t direct[16];
    uint8_t bridged[16];

    direct_hash = siphash13(input, 5, _dea_l1_interface_fingerprint_key);
    _dea_l1_interface_fingerprint_sip13_hex(input, 5, direct);
    l1c_interface_fingerprint_sip13_hex(input, 5, bridged);
    if (direct_hash != UINT64_C(0x{EXPECTED_HEX})) return 1;
    if (memcmp(direct, expected, 16) != 0) return 2;
    if (memcmp(bridged, expected, 16) != 0) return 3;
    if (memcmp(direct, bridged, 16) != 0) return 4;
    return 0;
}}
''',
            encoding="utf-8",
        )
        compile_and_run(
            compiler,
            temp_dir / "direct_bridge",
            [direct_harness, STAGE1_SUPPORT],
        )

        archive_harness = temp_dir / "archive_harness.c"
        archive_harness.write_text(
            f'''#include <stdint.h>
#include <string.h>
#include "dea_rt.h"

int main(void) {{
    static const uint8_t input[] = {{ 'i', 'n', 'p', 'u', 't' }};
    static const uint8_t expected[] = "{EXPECTED_HEX}";
    uint8_t actual[16];

    l1c_interface_fingerprint_sip13_hex(input, 5, actual);
    return memcmp(actual, expected, 16) == 0 ? 0 : 1;
}}
''',
            encoding="utf-8",
        )

        for archive_name in (
            "libdea_rt.a",
            "libdea_rt_traced.a",
            "libdea_rt_check_basic.a",
            "libdea_rt_unchecked.a",
        ):
            archive = build_dir() / "lib" / archive_name
            if not archive.is_file():
                raise AssertionError(f"missing runtime archive: {archive}")
            compile_and_run(
                compiler,
                temp_dir / archive_name.removesuffix(".a"),
                [archive_harness],
                archive=archive,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
