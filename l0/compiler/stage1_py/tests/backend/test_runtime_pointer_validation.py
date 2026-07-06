#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""Runtime pointer access validation tests."""


def _run_l0(codegen_single, compile_and_run, tmp_path, src: str, stdin_text: str | None = None):
    c_code, diagnostics = codegen_single("main", src)
    assert c_code is not None, diagnostics
    return compile_and_run(c_code, tmp_path, stdin_text)


def _assert_runtime_failure(stderr: str, needle: str) -> None:
    assert "Software Failure:" in stderr
    assert needle in stderr


def _assert_accessed_at_line(stderr: str, expected_line: int) -> None:
    accessed_lines = [line for line in stderr.splitlines() if "accessed at:" in line]
    assert accessed_lines, stderr
    assert accessed_lines[-1].rstrip().endswith(f":{expected_line}"), stderr


def test_callee_drop_then_field_access_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;

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
    )

    assert not success
    _assert_runtime_failure(stderr, "use after drop/free")


def test_pointer_error_reports_source_line_with_cached_site(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """module main;

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
    )

    assert not success
    _assert_runtime_failure(stderr, "use after drop/free")
    _assert_accessed_at_line(stderr, 14)


def test_alias_double_drop_fails_before_field_cleanup(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct Box {
            text: string;
        }

        func main() -> int {
            let p: Box* = new Box("hello");
            let q: Box* = p;
            drop p;
            drop q;
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "double drop")


def test_null_drop_is_noop(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        struct Box {
            value: int;
        }

        func main() -> int {
            let p: Box*? = null;
            drop p;
            return 0;
        }
        """,
    )

    assert success, stderr


def test_raw_rt_alloc_is_tracked_for_pointer_access(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_alloc(sizeof(int)) as void*;
            let p: int* = raw as int*;
            *p = 7;
            let value: int = *p;
            rt_free(raw as void*?);
            return value - 7;
        }
        """,
    )

    assert success, stderr


def test_misaligned_raw_pointer_deref_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_calloc(1, sizeof(int) + 1) as void*;
            let p: int* = rt_array_element(raw, 1, 1) as int*;
            return *p;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "misaligned pointer access")


def test_rt_array_element_rejects_out_of_range_tracked_access(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_calloc(1, sizeof(int)) as void*;
            let p: int* = rt_array_element(raw, sizeof(int), 1) as int*;
            return *p;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "pointer index outside allocation")


def test_raw_rt_free_then_deref_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_alloc(sizeof(int)) as void*;
            let p: int* = raw as int*;
            *p = 11;
            rt_free(raw as void*?);
            return *p;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "use after drop/free")


def test_derived_pointer_after_parent_free_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_calloc(2, sizeof(int)) as void*;
            let elem: int* = rt_array_element(raw, sizeof(int), 1) as int*;
            *elem = 5;
            rt_free(raw as void*?);
            return *elem;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "stale derived pointer access")


def test_nested_byte_offset_derived_pointer_can_access_remaining_range(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_calloc(4, sizeof(int)) as void*;
            let parent: void* = rt_array_element(raw, sizeof(int) * 2, 1);
            let nested: int* = rt_array_element(parent, 1, sizeof(int)) as int*;
            *nested = 19;
            let value: int = *nested;
            rt_free(raw as void*?);
            return value - 19;
        }
        """,
    )

    assert success, stderr


def test_string_bytes_ptr_of_literal_is_dereferenceable(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let p: byte* = rt_string_bytes_ptr("Hi");
            let b: byte = *p;
            return (b as int) - 72;
        }
        """,
    )

    assert success, stderr


def test_string_bytes_ptr_of_heap_string_is_dereferenceable(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let a: string = "He";
            let b: string = a + "llo";
            let p: byte* = rt_string_bytes_ptr(b);
            let first: byte = *p;
            return (first as int) - 72;
        }
        """,
    )

    assert success, stderr


def test_string_bytes_ptr_of_realloc_grown_string_is_dereferenceable(
    codegen_single, compile_and_run, tmp_path
):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let line_opt: string? = rt_read_line();
            if (line_opt == null) {
                return 1;
            }
            let line: string = line_opt as string;
            let p: byte* = rt_string_bytes_ptr(line);
            let b: byte = *p;
            return (b as int) - 65;
        }
        """,
        stdin_text=("A" * 200) + "\n",
    )

    assert success, stderr


def test_string_bytes_ptr_of_literal_rejects_write(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let p: byte* = rt_string_bytes_ptr("Hi");
            *p = 'X';
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "read-only pointer write")


def test_string_bytes_ptr_of_heap_string_rejects_write(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let a: string = "He";
            let b: string = a + "llo";
            let p: byte* = rt_string_bytes_ptr(b);
            *p = 'X';
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "read-only pointer write")


def test_explicit_deref_field_write_rejects_read_only(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        struct Pair {
            a: byte;
            b: byte;
        }

        func main() -> int {
            let raw: void* = rt_string_bytes_ptr("Hi") as void*;
            let q: Pair* = raw as Pair*;
            (*q).b = 'X';
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "read-only pointer write")


def test_nested_field_write_rejects_read_only(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        struct Inner {
            a: byte;
            b: byte;
        }

        struct Outer {
            inner: Inner;
        }

        func main() -> int {
            let raw: void* = rt_string_bytes_ptr("Hi") as void*;
            let q: Outer* = raw as Outer*;
            q.inner.b = 'X';
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "read-only pointer write")


def test_explicit_deref_field_write_to_heap_struct_succeeds(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        struct Pair {
            a: byte;
            b: byte;
        }

        func main() -> int {
            let raw: void* = rt_calloc(1, sizeof(Pair)) as void*;
            let q: Pair* = raw as Pair*;
            (*q).b = 'X';
            let value: byte = (*q).b;
            rt_free(raw as void*?);
            return (value as int) - 88;
        }
        """,
    )

    assert success, stderr


def test_drop_of_string_bytes_ptr_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.rt;

        func main() -> int {
            let p: byte* = rt_string_bytes_ptr("Hi");
            drop p;
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "is not droppable")


def test_unchecked_codegen_compiles_and_runs_valid_program(analyze_single, compile_and_run, tmp_path):
    result = analyze_single(
        "main",
        """
        module main;
        import std.io;

        struct Box {
            value: int;
        }

        func main() -> int {
            let p: Box* = new Box(7);
            let v: int = p.value;
            drop p;
            printl_i(v);
            return 0;
        }
        """,
    )

    assert not result.has_errors(), result.diagnostics
    result.context.rt_unchecked = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    assert "#define L0_RT_UNCHECKED 1" in c_code

    success, stdout, stderr = compile_and_run(c_code, tmp_path)
    assert success, stderr
    assert stdout.strip() == "7"


def test_drop_of_derived_pointer_reports_runtime_error(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let raw: void* = rt_calloc(2, sizeof(int)) as void*;
            let elem: int* = rt_array_element(raw, sizeof(int), 1) as int*;
            drop elem;
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "pointer is not an allocation base")
