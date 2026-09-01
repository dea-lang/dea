# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Exact generated-call contracts for runtime-facing C emitter helpers."""

from l0_c_emitter import CEmitter


def test_runtime_call_helpers_preserve_extent_alignment_and_ownership_arguments():
    """Runtime call text carries the complete checked-access and drop ABI."""

    emitter = CEmitter()
    direct = emitter.emit_checked_ptr_access(
        "ptr",
        "l0_int*",
        "sizeof(l0_int)",
        "_RT_ALIGNOF(l0_int)",
        "_RT_ACCESS_READ",
    )
    indexed = emitter.emit_checked_ptr_index_access(
        "base",
        "index",
        "l0_byte*",
        "sizeof(l0_byte)",
        "_RT_ALIGNOF(l0_byte)",
        "_RT_ACCESS_WRITE",
    )
    drop_begin = emitter.emit_drop_begin_expr(
        "owned",
        "struct l0_demo_Box*",
        "sizeof(struct l0_demo_Box)",
        "_RT_ALIGNOF(struct l0_demo_Box)",
    )
    emitter.emit_drop_finish_call("checked_owned")
    emitter.emit_alloc_obj(
        "struct l0_demo_Box*", "struct l0_demo_Box", "allocated"
    )

    assert direct == (
        "((l0_int*)_rt_check_ptr_site(&l0_site_1, (void*)(ptr), "
        "(l0_int)(sizeof(l0_int)), (l0_int)(_RT_ALIGNOF(l0_int)), "
        "_RT_ACCESS_READ, __FILE__, __LINE__))"
    )
    assert indexed == (
        "((l0_byte*)_rt_check_index_ptr_site(&l0_site_2, (void*)(base), "
        "(l0_int)(index), (l0_int)(sizeof(l0_byte)), "
        "(l0_int)(_RT_ALIGNOF(l0_byte)), _RT_ACCESS_WRITE, __FILE__, __LINE__))"
    )
    assert drop_begin == (
        "((struct l0_demo_Box*)_rt_drop_begin_impl((void*)(owned), "
        "(l0_int)(sizeof(struct l0_demo_Box)), "
        "(l0_int)(_RT_ALIGNOF(struct l0_demo_Box)), __FILE__, __LINE__))"
    )
    assert emitter.get_output() == (
        "static _rt_ptr_site l0_site_1;\n"
        "static _rt_ptr_site l0_site_2;\n"
        "_rt_drop_finish_impl((void*)(checked_owned), __FILE__, __LINE__);\n"
        "struct l0_demo_Box* allocated = "
        "(struct l0_demo_Box*)_rt_alloc_obj((l0_int)sizeof(struct l0_demo_Box));\n"
    )
