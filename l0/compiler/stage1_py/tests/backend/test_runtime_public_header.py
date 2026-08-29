# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Regression coverage for the public declaration-only L0 runtime header."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import _compiler_flag_family, _find_cc


# (return type, symbol, parameter types, portable in the L1 shared subset)
PUBLIC_RUNTIME_SIGNATURES = (
    ("dea_int", "rt_strlen", "dea_string", True),
    ("dea_byte", "rt_string_get", "dea_string, dea_int", True),
    ("dea_byte *", "rt_string_bytes_ptr", "dea_string", True),
    ("dea_bool", "rt_string_equals", "dea_string, dea_string", True),
    ("dea_int", "rt_string_compare", "dea_string, dea_string", True),
    ("dea_string", "rt_string_concat", "dea_string, dea_string", True),
    ("dea_string", "rt_string_slice", "dea_string, dea_int, dea_int", True),
    ("dea_string", "rt_string_from_byte", "dea_byte", True),
    ("dea_string", "rt_string_from_byte_array", "dea_byte *, dea_int", True),
    ("void", "rt_string_retain", "dea_string", True),
    ("void", "rt_string_release", "dea_string", True),
    ("dea_int", "rt_system", "dea_string", True),
    ("dea_opt_string", "rt_get_env_var", "dea_string", True),
    ("dea_int", "rt_get_argc", "void", True),
    ("dea_int", "rt_get_pid", "void", True),
    ("dea_string", "rt_get_argv", "dea_int", True),
    ("dea_bool", "rt_time_unix", "struct l0_sys_rt_RtTimeParts *", False),
    ("dea_bool", "rt_time_monotonic", "struct l0_sys_rt_RtTimeParts *", False),
    ("dea_bool", "rt_time_monotonic_supported", "void", True),
    ("dea_opt_int", "rt_time_local_offset_sec", "dea_int", True),
    ("dea_opt_bool", "rt_time_local_is_dst", "dea_int", True),
    ("dea_opt_string", "rt_read_file_all", "dea_string", True),
    ("dea_bool", "rt_write_file_all", "dea_string, dea_string", True),
    ("struct l0_sys_rt_RtFileInfo", "rt_file_info", "dea_string", False),
    ("dea_bool", "rt_delete_file", "dea_string", True),
    ("dea_int", "rt_stdin_read", "dea_byte *, dea_int", True),
    ("dea_int", "rt_stdout_write", "dea_byte *, dea_int", True),
    ("dea_int", "rt_stderr_write", "dea_byte *, dea_int", True),
    ("void", "rt_flush_stdout", "void", True),
    ("void", "rt_flush_stderr", "void", True),
    ("void", "rt_print", "dea_string", True),
    ("void", "rt_print_stderr", "dea_string", True),
    ("void", "rt_println", "void", True),
    ("void", "rt_println_stderr", "void", True),
    ("void", "rt_print_int", "dea_int", True),
    ("void", "rt_print_int_stderr", "dea_int", True),
    ("void", "rt_print_bool", "dea_bool", True),
    ("void", "rt_print_bool_stderr", "dea_bool", True),
    ("dea_opt_string", "rt_read_line", "void", True),
    ("dea_int", "rt_read_char", "void", True),
    ("void", "rt_abort", "dea_string", True),
    ("void", "rt_exit", "dea_int", True),
    ("void", "rt_srand", "dea_int", True),
    ("dea_int", "rt_rand", "dea_int", True),
    ("dea_int", "rt_errno", "void", True),
    ("void *", "rt_alloc", "dea_int", True),
    ("void *", "rt_realloc", "void *, dea_int", True),
    ("void", "rt_free", "void *", True),
    ("void *", "rt_calloc", "dea_int, dea_int", True),
    ("void *", "rt_memset", "void *, dea_int, dea_int", True),
    ("void *", "rt_memcpy", "void *, void *, dea_int", True),
    ("dea_int", "rt_memcmp", "void *, void *, dea_int", True),
    ("void *", "rt_array_element", "void *, dea_int, dea_int", True),
    ("void", "rt_register_foreign", "void *, dea_int, dea_bool", True),
    ("void", "rt_unregister_foreign", "void *", True),
    ("dea_int", "rt_hash_bool", "dea_bool", True),
    ("dea_int", "rt_hash_byte", "dea_byte", True),
    ("dea_int", "rt_hash_int", "dea_int", True),
    ("dea_int", "rt_hash_string", "dea_string", True),
    ("dea_int", "rt_hash_data", "void *, dea_int", True),
    ("dea_int", "rt_hash_opt_bool", "dea_opt_bool", True),
    ("dea_int", "rt_hash_opt_byte", "dea_opt_byte", True),
    ("dea_int", "rt_hash_opt_int", "dea_opt_int", True),
    ("dea_int", "rt_hash_opt_string", "dea_opt_string", True),
    ("dea_int", "rt_hash_ptr", "void *", True),
    ("dea_int", "rt_hash_opt_ptr", "void *", True),
)


def _typed_symbol_references(*, portable_only: bool) -> str:
    """Return C definitions that type-check and retain every selected symbol."""

    lines = []
    for return_type, name, parameters, portable in PUBLIC_RUNTIME_SIGNATURES:
        if portable_only and not portable:
            continue
        lines.append(
            f"{return_type} (*volatile dea_test_{name})({parameters}) = {name};"
        )
    return "\n".join(lines)


def _compile_c(
    source: Path,
    output: Path,
    include_dir: Path,
    *,
    link: bool,
) -> subprocess.CompletedProcess[str]:
    """Compile one C compatibility probe with the configured host compiler."""

    cc = _find_cc()
    family = _compiler_flag_family(cc)
    if family == "msvc":
        command = [cc, str(source), "/std:c11", "/WX", f"/I{include_dir}"]
        if link:
            command.append(f"/Fe:{output}")
        else:
            command.extend(["/c", f"/Fo{output}"])
    else:
        diagnostic_flag = "-Werror" if family == "tcc" else "-pedantic-errors"
        command = [
            cc,
            "-std=c99",
            diagnostic_flag,
            *([] if link else ["-c"]),
            "-I",
            str(include_dir),
            str(source),
            "-o",
            str(output),
        ]

    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize(
    "mode_flags",
    [
        pytest.param([], id="checked"),
        pytest.param(["--check-basic"], id="basic-checked"),
        pytest.param(["--unchecked"], id="unchecked"),
        pytest.param(["--trace-arc"], id="trace-arc"),
        pytest.param(["--trace-memory"], id="trace-memory"),
    ],
)
def test_additional_c_sources_link_public_runtime_header(
    temp_project: Path,
    mode_flags: list[str],
) -> None:
    """Two foreign C units may share declarations and call public runtime symbols."""

    (temp_project / "main.l0").write_text(
        """\
module main;

import std.io;

extern func exercise_memory(value: int) -> int;
extern func exercise_string() -> int;
extern func exercise_symbols() -> int;

func main() -> int {
    printl_i(exercise_memory(39) + exercise_string() + exercise_symbols() - 1);
    return 0;
}
""",
        encoding="utf-8",
    )
    (temp_project / "symbols.c").write_text(
        "#include \"dea_rt.h\"\n\n"
        + _typed_symbol_references(portable_only=False)
        + "\n\ndea_int exercise_symbols(void)\n"
        + "{\n    return dea_test_rt_strlen != NULL;\n}\n",
        encoding="utf-8",
    )
    (temp_project / "memory.c").write_text(
        """\
#include "dea_rt.h"

typedef char dea_int_matches_l0_int[
    sizeof(dea_int) == sizeof(l0_int) ? 1 : -1
];

dea_int exercise_memory(dea_int value)
{
    dea_byte *bytes = (dea_byte *)rt_calloc(4, (dea_int)sizeof(dea_byte));
    if (bytes == NULL) {
        return -1;
    }
    bytes[0] = 1;
    bytes = (dea_byte *)rt_realloc(bytes, 8);
    if (bytes == NULL) {
        return -1;
    }
    rt_memset(bytes + 1, 0, 7);
    rt_free(bytes);
    return value;
}
""",
        encoding="utf-8",
    )
    (temp_project / "string.c").write_text(
        """\
#include "dea_rt.h"

dea_int exercise_string(void)
{
    dea_string left = DEA_STRING_CONST("de", 2);
    l0_string right = L0_STRING_CONST("a", 1);
    dea_string joined = rt_string_concat(left, right);
    dea_int length = rt_strlen(joined);

    rt_string_retain(joined);
    rt_string_release(joined);
    rt_string_release(joined);
    return length;
}
""",
        encoding="utf-8",
    )

    l0_root = Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    env["L0_HOME"] = str(l0_root / "compiler")
    completed = subprocess.run(
        [
            sys.executable,
            str(l0_root / "compiler" / "stage1_py" / "l0c.py"),
            "--run",
            *mode_flags,
            "--project-root",
            str(temp_project),
            "--c-source",
            str(temp_project / "memory.c"),
            "--c-source",
            str(temp_project / "string.c"),
            "--c-source",
            str(temp_project / "symbols.c"),
            "main",
        ],
        cwd=temp_project,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "42\n"
    if mode_flags in (["--trace-arc"], ["--trace-memory"]):
        assert 'loc="<runtime>":0' in completed.stderr


def test_public_runtime_declarations_cover_l0_extern_functions(runtime_dir: Path) -> None:
    """Keep the public declarations synchronized with the L0 runtime modules."""

    stdlib_sys = runtime_dir.parent / "l0" / "stdlib" / "sys"
    extern_names: set[str] = set()
    for name in ("rt.l0", "memory.l0", "hash.l0"):
        source = (stdlib_sys / name).read_text(encoding="utf-8")
        extern_names.update(re.findall(r"\bextern\s+func\s+(rt_[a-z0-9_]+)\s*\(", source))

    header = (runtime_dir / "dea_rt.h").read_text(encoding="utf-8")
    declaration_names = set(
        re.findall(r"^[^#\n;{}]*\b(rt_[a-z0-9_]+)\s*\([^;{}]*\);$", header, re.MULTILINE)
    )

    expected_names = {name for _, name, _, _ in PUBLIC_RUNTIME_SIGNATURES}

    assert declaration_names == extern_names == expected_names


def test_l1_compatible_subset_compiles_and_has_matching_layout(
    temp_project: Path,
    runtime_dir: Path,
) -> None:
    """Compile shared C unchanged and compare ABI layouts against L1's header."""

    l0_root = Path(__file__).resolve().parents[4]
    l1_runtime_dir = l0_root.parent / "l1" / "compiler" / "shared" / "runtime" / "include"
    assert (l1_runtime_dir / "dea_rt.h").is_file()

    declarations = temp_project / "portable_symbols.c"
    declarations.write_text(
        "#include \"dea_rt.h\"\n\n"
        + _typed_symbol_references(portable_only=True)
        + "\n",
        encoding="utf-8",
    )
    for label, include_dir in (("l0", runtime_dir), ("l1", l1_runtime_dir)):
        compiled = _compile_c(
            declarations,
            temp_project / f"portable_symbols_{label}.o",
            include_dir,
            link=False,
        )
        assert compiled.returncode == 0, compiled.stderr

    layout_source = temp_project / "layout.c"
    layout_source.write_text(
        """\
#include <stddef.h>
#include <stdio.h>
#include "dea_rt.h"

int main(void)
{
    dea_string value = DEA_STRING_CONST("x", 1);
    dea_opt_string empty = DEA_OPT_STRING_EMPTY;
    printf(
        "%zu %zu %zu %zu %zu %zu %zu %zu %zu %zu %zu "
        "%zu %zu %zu %zu %zu %zu %u %d %u\\n",
        sizeof(dea_bool), sizeof(dea_tiny), sizeof(dea_short), sizeof(dea_int),
        sizeof(dea_long), sizeof(dea_byte), sizeof(dea_ushort), sizeof(dea_uint),
        sizeof(dea_ulong), sizeof(dea_float), sizeof(dea_double),
        sizeof(dea_string), offsetof(dea_string, data),
        sizeof(dea_opt_bool), sizeof(dea_opt_byte),
        sizeof(dea_opt_int), sizeof(dea_opt_string),
        (unsigned int)value.kind, (int)value.data.s_str.len,
        (unsigned int)empty.has_value
    );
    return 0;
}
""",
        encoding="utf-8",
    )
    layouts: dict[str, str] = {}
    for label, include_dir in (("l0", runtime_dir), ("l1", l1_runtime_dir)):
        executable = temp_project / (f"layout_{label}.exe" if os.name == "nt" else f"layout_{label}")
        compiled = _compile_c(layout_source, executable, include_dir, link=True)
        assert compiled.returncode == 0, compiled.stderr
        executed = subprocess.run(
            [str(executable)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        assert executed.returncode == 0, executed.stderr
        layouts[label] = executed.stdout

    assert layouts["l0"] == layouts["l1"]
