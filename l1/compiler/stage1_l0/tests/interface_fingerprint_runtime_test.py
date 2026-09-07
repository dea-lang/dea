#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Known-answer coverage for the L1 interface-fingerprint C bridge."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
RUNTIME_INTERNAL = RUNTIME_ROOT / "internal"
STAGE1_SUPPORT = L1_ROOT / "compiler" / "stage1_l0" / "support" / "interface_fingerprint.c"
COMMON_SUPPORT = L1_ROOT / "compiler" / "stage1_l0" / "support" / "compiler_support.c"
FINGERPRINT_SOURCE = L1_ROOT / "compiler" / "stage1_l0" / "src" / "interface_fingerprint.l0"
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
    """Compile and run one bridge known-answer harness.

    Args:
        compiler: C compiler to use.
        output_path: Destination executable.
        sources: C sources and precompiled objects to link.
        archive: Optional runtime archive.

    Raises:
        AssertionError: Compilation or the known-answer harness fails.
    """

    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        f"-I{build_dir() / 'include'}",
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


def compile_public_header(
    compiler: str,
    source_path: Path,
    output_path: Path,
) -> None:
    """Compile a translation unit strictly against the delivered public header."""

    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        f"-I{build_dir() / 'include'}",
        "-c",
        str(source_path),
        "-o",
        str(output_path),
    ]
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
            f"public-header compilation exited with {completed.returncode}:\n"
            f"{completed.stdout}"
        )


def compile_generated_bridge(compiler: str, temp_dir: Path) -> tuple[str, Path]:
    """Compile the production extern through L1 and the delivered runtime header.

    Args:
        compiler: Strict C99 compiler to use.
        temp_dir: Temporary fixture and object directory.

    Returns:
        The production bridge name and the compiled L1-generated object.

    Raises:
        AssertionError: The production declaration is missing or compilation fails.
    """

    declarations = list(re.finditer(
        r"^extern func (l1c_interface_fingerprint_\w+)\([^\n]+\) -> void;$",
        FINGERPRINT_SOURCE.read_text(encoding="utf-8"),
        re.MULTILINE,
    ))
    if len(declarations) != 1:
        raise AssertionError("expected one production fingerprint extern declaration")
    declaration = declarations[0]
    bridge_name = declaration.group(1)
    source = temp_dir / "fingerprint_probe.l1"
    source.write_text(
        f"module fingerprint_probe;\n{declaration.group(0)}\n"
        "func probe(data: byte*, len: int, out_hex: byte*) {\n"
        f"    {bridge_name}(data, len, out_hex);\n}}\n",
        encoding="utf-8",
    )
    stage1 = build_dir() / "bin" / "l1c-stage1"
    if os.name == "nt":
        stage1 = stage1.with_suffix(".cmd")
    generated = temp_dir / "fingerprint_probe.c"
    completed = subprocess.run(
        [str(stage1), "--gen", "-Rp", str(temp_dir), "-o", str(generated),
         "fingerprint_probe"],
        cwd=L1_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"L1 bridge generation failed:\n{completed.stdout}")
    if f"({bridge_name})(" not in generated.read_text(encoding="utf-8"):
        raise AssertionError("generated C omitted the production extern declaration")
    obj = temp_dir / "fingerprint_probe.o"
    compile_public_header(compiler, generated, obj)
    return bridge_name, obj


def bridge_vectors(bridge_name: str) -> str:
    """Return known-answer and buffer-integrity checks shared by both link paths.

    Args:
        bridge_name: Compiler-facing bridge taken from the production source.

    Returns:
        A C helper checking empty, ordinary, and binary inputs through both ABIs.
    """

    return f'''
static int check_vectors(void) {{
    static const uint8_t inputs[3][9] = {{
        {{0}}, {{'i', 'n', 'p', 'u', 't'}},
        {{0, 1, 0x7f, 0x80, 0xff, 0, 42, 10, 0xfe}}
    }};
    static const int32_t lengths[3] = {{0, 5, 9}};
    static const char expected[3][17] = {{
        "c0c0dc8802134acd", "{EXPECTED_HEX}", "5866d8ef3b2566aa"
    }};
    uint8_t mutable_input[9];
    uint8_t const_output[18];
    uint8_t compiler_output[18];
    int i;
    for (i = 0; i < 3; ++i) {{
        memcpy(mutable_input, inputs[i], sizeof(mutable_input));
        memset(const_output, '!', sizeof(const_output));
        memset(compiler_output, '!', sizeof(compiler_output));
        l1c_interface_fingerprint_sip13_hex(inputs[i], lengths[i], const_output + 1);
        {bridge_name}(mutable_input, lengths[i], compiler_output + 1);
        if (memcmp(const_output + 1, expected[i], 16) != 0) return 20 + i;
        if (memcmp(compiler_output + 1, expected[i], 16) != 0) return 30 + i;
        if (memcmp(mutable_input, inputs[i], sizeof(mutable_input)) != 0) return 40 + i;
        if (const_output[0] != '!' || const_output[17] != '!') return 50 + i;
        if (compiler_output[0] != '!' || compiler_output[17] != '!') return 60 + i;
    }}
    return 0;
}}
'''


def main() -> int:
    """Compare the direct implementation, Stage 1 shim, and every archive mode."""

    compiler = resolve_c_compiler()
    with tempfile.TemporaryDirectory(prefix="l1_interface_fingerprint_runtime_test.") as raw_temp:
        temp_dir = Path(raw_temp)

        public_header_harness = temp_dir / "public_header_harness.c"
        public_header_harness.write_text(
            '#include "dea_rt.h"\n',
            encoding="utf-8",
        )
        compile_public_header(
            compiler,
            public_header_harness,
            temp_dir / "public_header_harness.o",
        )
        bridge_name, generated_object = compile_generated_bridge(compiler, temp_dir)

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
void {bridge_name}(uint8_t *data, int32_t len, uint8_t *out_hex);

{bridge_vectors(bridge_name)}

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
    return check_vectors();
}}
''',
            encoding="utf-8",
        )
        compile_and_run(
            compiler,
            temp_dir / "direct_bridge",
            [direct_harness, STAGE1_SUPPORT, COMMON_SUPPORT, generated_object],
        )

        archive_harness = temp_dir / "archive_harness.c"
        archive_harness.write_text(
            f'''#include <stdint.h>
#include <string.h>
#include "dea_rt.h"

{bridge_vectors(bridge_name)}

int main(void) {{
    static const uint8_t input[] = {{ 'i', 'n', 'p', 'u', 't' }};
    static const uint8_t expected[] = "{EXPECTED_HEX}";
    uint8_t actual[16];
    dea_string empty_string = DEA_STRING_EMPTY;
    dea_opt_string null_string = DEA_OPT_STRING_NULL;
    dea_opt_string empty_optional_string = DEA_OPT_STRING_EMPTY;

    l1c_interface_fingerprint_sip13_hex(input, 5, actual);
    if (memcmp(actual, expected, 16) != 0) return 1;
    if (empty_string.kind != DEA_STRING_K_STATIC) return 2;
    if (empty_string.data.s_str.len != 0) return 3;
    if (empty_string.data.s_str.bytes != NULL) return 4;
    if (null_string.has_value != 0) return 5;
    if (null_string.value.kind != DEA_STRING_K_STATIC) return 6;
    if (null_string.value.data.s_str.len != 0) return 7;
    if (null_string.value.data.s_str.bytes != NULL) return 8;
    if (empty_optional_string.has_value != 1) return 9;
    if (empty_optional_string.value.kind != DEA_STRING_K_STATIC) return 10;
    if (empty_optional_string.value.data.s_str.len != 0) return 11;
    if (empty_optional_string.value.data.s_str.bytes != NULL) return 12;
    return check_vectors();
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
                [archive_harness, generated_object],
                archive=archive,
            )
            compile_and_run(
                compiler,
                temp_dir / (archive_name.removesuffix(".a") + "_with_support"),
                [archive_harness, generated_object, COMMON_SUPPORT],
                archive=archive,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
