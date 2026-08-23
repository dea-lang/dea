#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Runtime pointer validation regressions for L1 generated programs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
L1_ROOT = REPO_ROOT / "l1"


def resolve_tool(base: Path) -> Path:
    """Return a host-compatible launcher path for one tool base path."""

    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
        return base.with_suffix(".cmd")
    return base


def compiler_path() -> Path:
    """Return the repo-local L1 Stage 1 compiler launcher."""

    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    return resolve_tool(build_dir / "bin" / "l1c-stage1")


def is_gnu_compatible_compiler(path: str) -> bool:
    """Return whether one compiler basename accepts `-c ... -o ...`."""

    name = Path(path).name.lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return (
        "gcc" in name
        or ("clang" in name and "clang-cl" not in name)
        or name in {"cc", "tcc"}
    )


def foreign_c_compiler() -> str:
    """Return a GNU-compatible compiler for a caller-owned foreign object."""

    candidates = [
        os.environ.get("L1_RUNTIME_CC", "").strip(),
        os.environ.get("L1_CC", "").strip(),
        "clang",
        "gcc",
        "cc",
        os.environ.get("CC", "").strip(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved is not None and is_gnu_compatible_compiler(resolved):
            return resolved
    raise AssertionError("pointer validation test requires clang, gcc, or cc")


def run_source(
    module_name: str,
    source: str,
    extra_flags: list[str] | None = None,
    support_c: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Compile and run one temporary L1 source module."""

    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        (project_root / f"{module_name}.l1").write_text(source, encoding="utf-8")
        flags = list(extra_flags or [])
        if support_c is not None:
            support_path = project_root / "support.c"
            support_path.write_text(support_c, encoding="utf-8")
            support_object = project_root / "support.o"
            host_cc = foreign_c_compiler()
            compiled = subprocess.run(
                [
                    host_cc,
                    "-c",
                    str(support_path),
                    "-o",
                    str(support_object),
                ],
                cwd=L1_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if compiled.returncode != 0:
                sys.stderr.buffer.write(compiled.stdout)
                sys.stderr.buffer.write(compiled.stderr)
                raise AssertionError("foreign support C compilation failed")
            flags.extend(
                [
                    "--c-compiler",
                    host_cc,
                    "--foreign-object",
                    str(support_object),
                ]
            )
        return subprocess.run(
            [
                str(compiler_path()),
                "--project-root",
                str(project_root),
                "--run",
                *flags,
                module_name,
            ],
            cwd=L1_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


def require_failure(
    module_name: str,
    source: str,
    stderr_needle: str,
    *,
    extra_flags: list[str] | None = None,
    support_c: str | None = None,
) -> None:
    """Run one fixture and assert it fails with the expected runtime message."""

    completed = run_source(module_name, source, extra_flags=extra_flags, support_c=support_c)
    if completed.returncode == 0:
        sys.stderr.write(completed.stdout)
        raise AssertionError(f"{module_name} unexpectedly succeeded")
    if stderr_needle not in completed.stderr:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{module_name} stderr did not contain {stderr_needle!r}")


def require_run(
    module_name: str,
    source: str,
    extra_flags: list[str] | None = None,
    support_c: str | None = None,
) -> None:
    """Run one fixture and assert it succeeds."""

    completed = run_source(
        module_name, source, extra_flags=extra_flags, support_c=support_c
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{module_name} exited with {completed.returncode}")


def require_check_basic_failure(
    module_name: str,
    source: str,
    stderr_needle: str,
    *,
    support_c: str | None = None,
) -> None:
    """Run one fixture with --check-basic and assert the expected runtime failure."""

    completed = run_source(
        module_name,
        source,
        extra_flags=["--check-basic"],
        support_c=support_c,
    )
    if completed.returncode == 0:
        sys.stderr.write(completed.stdout)
        raise AssertionError(f"{module_name} unexpectedly succeeded")
    if stderr_needle not in completed.stderr:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise AssertionError(f"{module_name} stderr did not contain {stderr_needle!r}")


FOREIGN_INT_PROVIDER = """
#include <stdint.h>
static int32_t foreign_value_storage = 7;
int32_t *foreign_value(void) { return &foreign_value_storage; }
"""


def main() -> int:
    require_failure(
        "pointer_index_oob",
        """
        module pointer_index_oob;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int));
            let raw: void* = raw_opt as void*;
            let p: int* = raw as int*;
            return p[1];
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "pointer index outside allocation",
    )

    require_failure(
        "pointer_index_negative",
        """
        module pointer_index_negative;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int));
            let raw: void* = raw_opt as void*;
            let p: int* = raw as int*;
            return p[-1];
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "negative pointer index",
    )

    require_failure(
        "misaligned_pointer",
        """
        module misaligned_pointer;
        import sys.memory;

        unsafe func read_bad() -> int {
            let raw_opt: void*? = rt_calloc(1, sizeof(int) + 1);
            let raw: void* = raw_opt as void*;
            let p: int* = rt_array_element(raw, 1, 1) as int*;
            return *p;
        }

        func main() -> int {
            return read_bad();
        }
        """,
        "misaligned pointer access",
    )

    require_failure(
        "drop_raw_allocation",
        """
        module drop_raw_allocation;
        import sys.memory;

        unsafe func drop_bad() -> int {
            let raw: void* = rt_alloc(sizeof(int)) as void*;
            let p: int* = raw as int*;
            drop p;
            return 0;
        }

        func main() -> int {
            return drop_bad();
        }
        """,
        "pointer was not allocated by new",
    )

    require_failure(
        "trace_drop_raw_allocation",
        """
        module trace_drop_raw_allocation;
        import sys.memory;

        unsafe func drop_bad() -> int {
            let raw: void* = rt_alloc(sizeof(int)) as void*;
            let p: int* = raw as int*;
            drop p;
            return 0;
        }

        func main() -> int {
            return drop_bad();
        }
        """,
        "action=panic-not-found",
        extra_flags=["--trace-memory"],
    )

    require_failure(
        "free_new_allocation",
        """
        module free_new_allocation;
        import sys.memory;

        unsafe func free_bad() -> int {
            let p: int* = new int(7);
            rt_free(p as void*?);
            return 0;
        }

        func main() -> int {
            return free_bad();
        }
        """,
        "new allocation must be released with drop",
    )

    require_failure(
        "realloc_new_allocation",
        """
        module realloc_new_allocation;
        import sys.memory;

        unsafe func realloc_bad() -> int {
            let p: int* = new int(7);
            let q: void*? = rt_realloc(p as void*?, sizeof(int) * 2);
            if (q == null) {
                return 1;
            }
            return 0;
        }

        func main() -> int {
            return realloc_bad();
        }
        """,
        "new allocation cannot be reallocated",
    )

    require_failure(
        "drop_undersized_new",
        """
        module drop_undersized_new;

        struct Box {
            text: string;
        }

        unsafe func drop_bad() -> int {
            let small: byte* = new byte('X');
            let box: Box* = (small as void*) as Box*;
            drop box;
            return 0;
        }

        func main() -> int {
            return drop_bad();
        }
        """,
        "drop pointee exceeds allocation size",
    )

    require_run(
        "registered_foreign_write",
        """
        module registered_foreign_write;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_register_foreign(p as void*, sizeof(int), false);
            *p = 19;
            let value: int = *p;
            rt_unregister_foreign(p as void*);
            return value - 19;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "unregistered_foreign_read",
        """
        module unregistered_foreign_read;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            return *p;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "unregistered pointer access",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "registered_foreign_read_only",
        """
        module registered_foreign_read_only;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), true);
            *p = 19;
            return 0;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "read-only pointer write",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "conflicting_foreign_registration",
        """
        module conflicting_foreign_registration;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_register_foreign(p as void*, sizeof(int), true);
            return 0;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "conflicting tracked base",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "unchecked_foreign_extent",
        """
        module unchecked_foreign_extent;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, 0, false);
            return 0;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "invalid byte extent",
        extra_flags=["--unchecked"],
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "unregistered_foreign_lifetime",
        """
        module unregistered_foreign_lifetime;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            let before: int = *p;
            rt_unregister_foreign(p as void*);
            return *p - before;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "unregistered pointer access",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "free_registered_foreign",
        """
        module free_registered_foreign;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_free(p as void*?);
            return 0;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "foreign memory is not runtime-owned",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "drop_registered_foreign",
        """
        module drop_registered_foreign;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            drop p;
            return 0;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        "foreign memory is not runtime-owned",
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_failure(
        "stale_slice_backing",
        """
        module stale_slice_backing;

        func main() -> int {
            let heap: int[2]* = new int[2]([10, 20]);
            let s: int[] = *heap;
            drop heap;
            return s[0];
        }
        """,
        "use after drop/free",
    )

    require_check_basic_failure(
        "check_basic_base_uaf",
        """
        module check_basic_base_uaf;

        struct Box {
            value: int;
        }

        func consume(p: Box*) -> void {
            drop p;
        }

        func main() -> int {
            let p: Box* = new Box(7);
            consume(p);
            return p.value;
        }
        """,
        "use after drop/free",
    )

    require_check_basic_failure(
        "check_basic_double_drop",
        """
        module check_basic_double_drop;

        struct Box {
            value: int;
        }

        func main() -> int {
            let p: Box* = new Box(7);
            let q: Box* = p;
            drop p;
            drop q;
            return 0;
        }
        """,
        "double drop",
    )

    require_check_basic_failure(
        "check_basic_string_write",
        """
        module check_basic_string_write;
        import sys.rt;

        unsafe func write_bad() -> int {
            let p: byte* = rt_string_bytes_ptr("Hi");
            *p = 'X';
            return 0;
        }

        func main() -> int {
            return write_bad();
        }
        """,
        "read-only pointer write",
    )

    require_check_basic_failure(
        "check_basic_heap_string_write",
        """
        module check_basic_heap_string_write;
        import sys.rt;

        unsafe func write_bad() -> int {
            let a: string = "He";
            let b: string = a + "llo";
            let p: byte* = rt_string_bytes_ptr(b);
            *p = 'X';
            return 0;
        }

        func main() -> int {
            return write_bad();
        }
        """,
        "read-only pointer write",
    )

    require_run(
        "check_basic_registered_foreign",
        """
        module check_basic_registered_foreign;
        import sys.memory;

        unsafe extern func foreign_value() -> int*;

        unsafe func use_foreign() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            *p = 23;
            let value: int = *p;
            rt_unregister_foreign(p as void*);
            return value - 23;
        }

        func main() -> int {
            return use_foreign();
        }
        """,
        extra_flags=["--check-basic"],
        support_c=FOREIGN_INT_PROVIDER,
    )

    require_run(
        "check_basic_stale_derived",
        """
        module check_basic_stale_derived;
        import sys.memory;

        unsafe func read_after_free() -> int {
            let raw_opt: void*? = rt_calloc(2, sizeof(int));
            let raw: void* = raw_opt as void*;
            let elem: int* = rt_array_element(raw, sizeof(int), 1) as int*;
            *elem = 5;
            rt_free(raw as void*?);
            return *elem - 5;
        }

        func main() -> int {
            return read_after_free();
        }
        """,
        extra_flags=["--check-basic"],
    )

    require_check_basic_failure(
        "check_basic_derived_drop",
        """
        module check_basic_derived_drop;
        import sys.memory;

        unsafe func drop_bad() -> int {
            let raw_opt: void*? = rt_calloc(2, sizeof(int));
            let raw: void* = raw_opt as void*;
            let elem: int* = rt_array_element(raw, sizeof(int), 1) as int*;
            drop elem;
            return 0;
        }

        func main() -> int {
            return drop_bad();
        }
        """,
        "unregistered pointer",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
