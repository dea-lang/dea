#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""ABI and edge-case coverage for the L1 `sys.hash` runtime boundary."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler" / "shared" / "runtime"
HASH_MODULE = L1_ROOT / "compiler" / "shared" / "l1" / "stdlib" / "sys" / "hash.l1"
HASH_RUNTIME_SOURCE = RUNTIME_ROOT / "src" / "dea_rt_hash.c"
RUNTIME_SOURCES = [
    "dea_rt_panic.c",
    "dea_rt_sys.c",
    "dea_rt_math.c",
    "dea_rt_rand.c",
    "dea_rt_string.c",
    "dea_rt_alloc.c",
    "dea_rt_io.c",
    "dea_rt_hash.c",
    "dea_rt_time.c",
]
EXPECTED_DECLARATIONS = {
    "rt_hash_bool": ("value: bool", "int"),
    "rt_hash_byte": ("value: byte", "int"),
    "rt_hash_int": ("value: int", "int"),
    "rt_hash_string": ("value: string", "int"),
    "rt_hash_data": ("data: void*, size: int", "int"),
    "rt_hash_opt_bool": ("opt: bool?", "int"),
    "rt_hash_opt_byte": ("opt: byte?", "int"),
    "rt_hash_opt_int": ("opt: int?", "int"),
    "rt_hash_opt_string": ("opt: string?", "int"),
    "rt_hash_ptr": ("ptr: void*", "int"),
    "rt_hash_opt_ptr": ("opt: void*?", "int"),
}


def runtime_c_compilers() -> list[str]:
    """Return distinct GNU-compatible compiler candidates."""

    candidates = [
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
        "tcc",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = shutil.which(candidate)
        if path is None:
            continue
        name = Path(path).name.lower().removesuffix(".exe")
        if (
            "gcc" not in name
            and "clang" not in name
            and name not in {"cc", "tcc"}
        ):
            continue
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key)
            resolved.append(path)
    return resolved


def require_dea_signature_inventory() -> None:
    """Require the extern-only module to expose exactly the reviewed ABI."""

    source = HASH_MODULE.read_text(encoding="utf-8")
    matches = re.findall(
        r"\bextern\s+func\s+(rt_hash_[a-z_]+)\s*\(([^)]*)\)\s*->\s*([^;]+);",
        source,
    )
    actual = {
        name: (" ".join(parameters.split()), " ".join(result.split()))
        for name, parameters, result in matches
    }
    assert actual == EXPECTED_DECLARATIONS, (
        "sys.hash declaration inventory mismatch:\n"
        f"expected={EXPECTED_DECLARATIONS}\nactual={actual}"
    )


def require_optional_string_domain_routing() -> None:
    """Lock present and absent optional strings to their intended subdomains."""

    source = HASH_RUNTIME_SOURCE.read_text(encoding="utf-8")
    expected = re.compile(
        r"dea_int\s+rt_hash_opt_string\s*\(dea_opt_string\s+opt\)\s*\{"
        r"\s*if\s*\(opt\.has_value\)\s*\{"
        r"\s*return\s+_rt_hash_string\(opt\.value,\s*_DEA_TAG_OPT\);"
        r"\s*\}"
        r"\s*return\s+_rt_hash_string\(DEA_STRING_EMPTY,"
        r"\s*_DEA_TAG_OPT\s*\|\s*_DEA_TAG_ABSENT\);"
        r"\s*\}",
        re.MULTILINE,
    )
    assert expected.search(source), "optional-string hash domain routing changed"


def compile_probe(work_dir: Path) -> tuple[Path, str] | None:
    """Compile a typed C ABI and behavior probe against the runtime sources."""

    source = work_dir / "hash_runtime_probe.c"
    executable = work_dir / (
        "hash_runtime_probe.exe" if os.name == "nt" else "hash_runtime_probe"
    )
    source.write_text(
        r"""
#include "dea_rt.h"

#include <string.h>

dea_int (*volatile hash_bool_symbol)(dea_bool) = rt_hash_bool;
dea_int (*volatile hash_byte_symbol)(dea_byte) = rt_hash_byte;
dea_int (*volatile hash_int_symbol)(dea_int) = rt_hash_int;
dea_int (*volatile hash_string_symbol)(dea_string) = rt_hash_string;
dea_int (*volatile hash_data_symbol)(void *, dea_int) = rt_hash_data;
dea_int (*volatile hash_opt_bool_symbol)(dea_opt_bool) = rt_hash_opt_bool;
dea_int (*volatile hash_opt_byte_symbol)(dea_opt_byte) = rt_hash_opt_byte;
dea_int (*volatile hash_opt_int_symbol)(dea_opt_int) = rt_hash_opt_int;
dea_int (*volatile hash_opt_string_symbol)(dea_opt_string) = rt_hash_opt_string;
dea_int (*volatile hash_ptr_symbol)(void *) = rt_hash_ptr;
dea_int (*volatile hash_opt_ptr_symbol)(void *) = rt_hash_opt_ptr;

static int check_optional_canonicalization(void)
{
    dea_opt_bool bool_a;
    dea_opt_bool bool_b;
    dea_opt_byte byte_a;
    dea_opt_byte byte_b;
    dea_opt_int int_a;
    dea_opt_int int_b;

    memset(&bool_a, 0xA5, sizeof(bool_a));
    memset(&bool_b, 0x5A, sizeof(bool_b));
    bool_a.has_value = 0;
    bool_b.has_value = 0;
    if (rt_hash_opt_bool(bool_a) != rt_hash_opt_bool(bool_b)) return 1;

    memset(&byte_a, 0xA5, sizeof(byte_a));
    memset(&byte_b, 0x5A, sizeof(byte_b));
    byte_a.has_value = 0;
    byte_b.has_value = 0;
    if (rt_hash_opt_byte(byte_a) != rt_hash_opt_byte(byte_b)) return 2;

    memset(&int_a, 0xA5, sizeof(int_a));
    memset(&int_b, 0x5A, sizeof(int_b));
    int_a.has_value = 0;
    int_b.has_value = 0;
    if (rt_hash_opt_int(int_a) != rt_hash_opt_int(int_b)) return 3;

    memset(&int_a, 0xA5, sizeof(int_a));
    memset(&int_b, 0x5A, sizeof(int_b));
    int_a.has_value = 1;
    int_b.has_value = 1;
    int_a.value = 42;
    int_b.value = 42;
    if (rt_hash_opt_int(int_a) != rt_hash_opt_int(int_b)) return 4;
    return 0;
}

static int check_success(void)
{
    dea_byte first = 1;
    dea_byte second = 2;
    dea_string string_value = DEA_STRING_CONST("abc", 3);
    dea_opt_bool none_bool = { 0 };
    dea_opt_byte none_byte = { 0 };
    dea_opt_int none_int = { 0 };
    dea_opt_string none_string = DEA_OPT_STRING_NULL;
    dea_opt_string empty_string = DEA_OPT_STRING_EMPTY;
    void *ptr = rt_alloc(1);
    int canonical = check_optional_canonicalization();

    if (canonical != 0) return 10 + canonical;
    if (rt_hash_bool(1) != rt_hash_bool(1)) return 20;
    if (rt_hash_byte(42) != rt_hash_byte(42)) return 21;
    if (rt_hash_int(123) != rt_hash_int(123)) return 22;
    if (rt_hash_string(string_value) != rt_hash_string(string_value)) return 23;
    if (rt_hash_data(&first, 0) != rt_hash_data(&second, 0)) return 24;
    if (rt_hash_opt_bool(none_bool) != rt_hash_opt_bool(none_bool)) return 25;
    if (rt_hash_opt_byte(none_byte) != rt_hash_opt_byte(none_byte)) return 26;
    if (rt_hash_opt_int(none_int) != rt_hash_opt_int(none_int)) return 27;
    if (rt_hash_opt_string(none_string) != rt_hash_opt_string(none_string)) return 28;
    if (rt_hash_opt_string(empty_string) != rt_hash_opt_string(empty_string)) return 29;
    if (rt_hash_opt_string(none_string) == rt_hash_opt_string(empty_string)) return 30;
    if (rt_hash_ptr(ptr) != rt_hash_ptr(ptr)) return 31;
    if (rt_hash_opt_ptr(ptr) != rt_hash_opt_ptr(ptr)) return 32;
    rt_free(ptr);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) return 90;
    if (strcmp(argv[1], "success") == 0) return check_success();
    if (strcmp(argv[1], "null-data-zero") == 0) {
        (void)rt_hash_data(NULL, 0);
        return 91;
    }
    if (strcmp(argv[1], "negative-size") == 0) {
        dea_byte value = 0;
        (void)rt_hash_data(&value, -1);
        return 92;
    }
    if (strcmp(argv[1], "null-pointer") == 0) {
        (void)rt_hash_ptr(NULL);
        return 93;
    }
    if (strcmp(argv[1], "empty-optional-pointer") == 0) {
        (void)rt_hash_opt_ptr(NULL);
        return 94;
    }
    return 95;
}
""",
        encoding="utf-8",
    )

    failures: list[str] = []
    for compiler in runtime_c_compilers():
        compiler_name = Path(compiler).name.lower().removesuffix(".exe")
        diagnostic_flag = "-Werror" if compiler_name == "tcc" else "-pedantic-errors"
        command = [
            compiler,
            "-std=c99",
            diagnostic_flag,
            f"-I{RUNTIME_ROOT / 'include'}",
            f"-I{RUNTIME_ROOT / 'internal'}",
            str(source),
            *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
            "-lm",
            "-o",
            str(executable),
        ]
        completed = subprocess.run(command, cwd=L1_ROOT, capture_output=True, text=True, check=False)
        if completed.returncode == 0:
            return executable, compiler
        failures.append(f"{compiler}: {completed.stderr.strip()}")

    if failures:
        raise AssertionError("hash runtime probe did not compile: " + " | ".join(failures))
    print("hash_runtime_test: SKIP: no GNU-compatible C compiler found")
    return None


def run_probe(executable: Path, mode: str) -> subprocess.CompletedProcess[str]:
    """Run one hash probe mode."""

    return subprocess.run(
        [str(executable), mode],
        cwd=L1_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def require_panic(executable: Path, mode: str, message: str) -> None:
    """Require one mode to abort with the exact runtime panic message."""

    completed = run_probe(executable, mode)
    stderr_lines = completed.stderr.strip().splitlines()
    if completed.returncode == 0 or not stderr_lines or stderr_lines[-1] != message:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"hash probe mode {mode!r} did not report {message!r}")


def main() -> int:
    """Verify declarations, C ABI, deterministic edges, and failure contracts."""

    require_dea_signature_inventory()
    require_optional_string_domain_routing()
    with tempfile.TemporaryDirectory() as tmp:
        compiled = compile_probe(Path(tmp))
        if compiled is None:
            return 0
        executable, _compiler = compiled
        success = run_probe(executable, "success")
        if success.returncode != 0:
            sys.stderr.write(success.stdout)
            sys.stderr.write(success.stderr)
            raise AssertionError(f"hash success probe exited with {success.returncode}")
        require_panic(
            executable,
            "null-data-zero",
            "Software Failure: rt_hash_data: null data pointer",
        )
        require_panic(
            executable,
            "negative-size",
            "Software Failure: rt_hash_data: negative size",
        )
        require_panic(
            executable,
            "null-pointer",
            "Software Failure: rt_hash_ptr: null pointer",
        )
        require_panic(
            executable,
            "empty-optional-pointer",
            "Software Failure: rt_hash_opt_ptr: unwrap of empty optional",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
