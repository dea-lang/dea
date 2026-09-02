#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

"""Runtime pointer access validation tests."""


def _run_l0(codegen_single, compile_and_run, tmp_path, src: str, stdin_text: str | None = None):
    c_code, diagnostics = codegen_single("main", src)
    assert c_code is not None, diagnostics
    return compile_and_run(c_code, tmp_path, stdin_text)


def _run_l0_with_c_suffix(codegen_single, compile_and_run, tmp_path, src: str, c_suffix: str):
    c_code, diagnostics = codegen_single("main", src)
    assert c_code is not None, diagnostics
    return compile_and_run(c_code + "\n" + c_suffix, tmp_path)


def _run_l0_check_basic(
    analyze_single, compile_and_run, tmp_path, src: str, c_suffix: str = ""
):
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.rt_check_basic = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    assert "#define L0_RT_CHECK_BASIC 1" in c_code
    return compile_and_run(c_code + "\n" + c_suffix, tmp_path)


def _run_l0_unchecked(
    analyze_single, compile_and_run, tmp_path, src: str, c_suffix: str = ""
):
    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    result.context.rt_unchecked = True

    from l0_backend import Backend

    c_code = Backend(result).generate()
    assert "#define L0_RT_UNCHECKED 1" in c_code
    return compile_and_run(c_code + "\n" + c_suffix, tmp_path)


def _run_l0_runtime_mode(
    analyze_single,
    compile_and_run,
    tmp_path,
    src: str,
    mode: str,
):
    """Compile and run one source under a selected runtime mode."""

    result = analyze_single("main", src)
    assert not result.has_errors(), result.diagnostics
    if mode == "check-basic":
        result.context.rt_check_basic = True
    elif mode == "unchecked":
        result.context.rt_unchecked = True
    elif mode == "traced":
        result.context.trace_memory = True
    elif mode != "checked":
        raise AssertionError(f"unknown runtime mode: {mode}")

    from l0_backend import Backend

    tmp_path.mkdir(parents=True, exist_ok=True)
    return compile_and_run(Backend(result).generate(), tmp_path)


def _assert_runtime_failure(stderr: str, needle: str) -> None:
    assert "Software Failure:" in stderr
    assert needle in stderr


def _assert_accessed_at_line(stderr: str, expected_line: int) -> None:
    accessed_lines = [line for line in stderr.splitlines() if "accessed at:" in line]
    assert accessed_lines, stderr
    assert accessed_lines[-1].rstrip().endswith(f":{expected_line}"), stderr


def test_byte_span_offset_contract_matches_all_runtime_modes(
    analyze_single, compile_and_run, tmp_path
):
    source = """
        module main;
        import sys.memory;

        func main() -> int {
            let base: void* = rt_alloc(9) as void*;
            let other: void* = rt_alloc(1) as void*;
            let interior = rt_array_element(base, 1, 3);
            let exact_end = rt_array_element(base, 1, 8);

            if (_rt_byte_span_offset(base, 8, base) != 0) {
                return 1;
            }
            if (_rt_byte_span_offset(base, 8, interior) != 3) {
                return 2;
            }
            if (_rt_byte_span_offset(base, 8, exact_end) != -1) {
                return 3;
            }
            if (_rt_byte_span_offset(base, 8, other) != -1) {
                return 4;
            }
            if (_rt_byte_span_offset(null, 8, base) != -1) {
                return 5;
            }
            if (_rt_byte_span_offset(base, 8, null) != -1) {
                return 6;
            }
            if (_rt_byte_span_offset(base, 0, base) != -1) {
                return 7;
            }
            if (_rt_byte_span_offset(base, -1, base) != -1) {
                return 8;
            }
            if (!_rt_byte_spans_overlap(base, 8, base, 1)) {
                return 9;
            }
            if (!_rt_byte_spans_overlap(base, 8, interior, 2)) {
                return 10;
            }
            if (!_rt_byte_spans_overlap(interior, 2, base, 4)) {
                return 11;
            }
            if (_rt_byte_spans_overlap(interior, 2, base, 3)) {
                return 12;
            }
            if (_rt_byte_spans_overlap(base, 3, interior, 2)) {
                return 13;
            }
            if (_rt_byte_spans_overlap(base, 8, other, 1)) {
                return 14;
            }
            if (_rt_byte_spans_overlap(null, 8, base, 1)) {
                return 15;
            }
            if (_rt_byte_spans_overlap(base, 8, null, 1)) {
                return 16;
            }
            if (_rt_byte_spans_overlap(base, 0, base, 1)) {
                return 17;
            }
            if (_rt_byte_spans_overlap(base, 8, base, -1)) {
                return 18;
            }

            rt_free(other);
            rt_free(base);
            return 0;
        }
    """
    for mode in ("checked", "check-basic", "traced", "unchecked"):
        success, _stdout, stderr = _run_l0_runtime_mode(
            analyze_single,
            compile_and_run,
            tmp_path / mode,
            source,
            mode,
        )
        assert success, f"{mode}: {stderr}"


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


def test_drop_rejects_raw_rt_alloc(codegen_single, compile_and_run, tmp_path):
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
            drop p;
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "pointer was not allocated by new")


def test_rt_free_rejects_new_allocation(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let p: int* = new int(7);
            rt_free(p as void*?);
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "new allocation must be released with drop")


def test_rt_realloc_rejects_new_allocation(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        func main() -> int {
            let p: int* = new int(7);
            let q: void*? = rt_realloc(p as void*?, sizeof(int) * 2);
            if (q == null) {
                return 1;
            }
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "new allocation cannot be reallocated")


def test_drop_rejects_undersized_new_before_field_cleanup(codegen_single, compile_and_run, tmp_path):
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
            let small: byte* = new byte('X');
            let box: Box* = (small as void*) as Box*;
            drop box;
            return 0;
        }
        """,
    )

    assert not success
    _assert_runtime_failure(stderr, "drop pointee exceeds allocation size")


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


_FOREIGN_INT_PROVIDER = """
static l0_int _foreign_value = 7;
l0_int *foreign_value(void) { return &_foreign_value; }
"""


def test_registered_writable_foreign_pointer_is_accessible(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_register_foreign(p as void*, sizeof(int), false);
            *p = 19;
            let value: int = *p;
            rt_unregister_foreign(p as void*);
            return value - 19;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert success, stderr


def test_unregistered_foreign_pointer_is_rejected(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            return *p;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "unregistered pointer access")


def test_registered_read_only_foreign_pointer_rejects_write(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), true);
            *p = 19;
            return 0;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "read-only pointer write")


def test_conflicting_foreign_registration_is_rejected(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_register_foreign(p as void*, sizeof(int), true);
            return 0;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "conflicting tracked base")


def test_unchecked_foreign_registration_still_validates_extent(
    analyze_single, compile_and_run, tmp_path
):
    success, _stdout, stderr = _run_l0_unchecked(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, 0, false);
            return 0;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "invalid byte extent")


def test_unregistered_foreign_pointer_becomes_inaccessible(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            let before: int = *p;
            rt_unregister_foreign(p as void*);
            return *p - before;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "unregistered pointer access")


def test_rt_free_rejects_registered_foreign_pointer(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            rt_free(p as void*?);
            return 0;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "foreign memory is not runtime-owned")


def test_drop_rejects_registered_foreign_pointer(codegen_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_with_c_suffix(
        codegen_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            drop p;
            return 0;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert not success
    _assert_runtime_failure(stderr, "foreign memory is not runtime-owned")


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


def test_check_basic_base_uaf_reports_runtime_error(analyze_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
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


def test_check_basic_double_drop_reports_runtime_error(analyze_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;

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
    )

    assert not success
    _assert_runtime_failure(stderr, "double drop")


def test_check_basic_string_bytes_exact_base_rejects_write(analyze_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
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


def test_check_basic_heap_string_bytes_exact_base_rejects_write(
    analyze_single, compile_and_run, tmp_path
):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
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


def test_check_basic_registered_foreign_pointer_is_accessible(
    analyze_single, compile_and_run, tmp_path
):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
        compile_and_run,
        tmp_path,
        """
        module main;
        import sys.memory;

        extern func foreign_value() -> int*;

        func main() -> int {
            let p: int* = foreign_value();
            rt_register_foreign(p as void*, sizeof(int), false);
            *p = 23;
            let value: int = *p;
            rt_unregister_foreign(p as void*);
            return value - 23;
        }
        """,
        _FOREIGN_INT_PROVIDER,
    )

    assert success, stderr


def test_check_basic_stale_derived_access_passes(analyze_single, compile_and_run, tmp_path):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
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
            return *elem - 5;
        }
        """,
    )

    assert success, stderr


def test_check_basic_drop_of_derived_pointer_reports_unregistered(
    analyze_single, compile_and_run, tmp_path
):
    success, _stdout, stderr = _run_l0_check_basic(
        analyze_single,
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
    _assert_runtime_failure(stderr, "unregistered pointer")
