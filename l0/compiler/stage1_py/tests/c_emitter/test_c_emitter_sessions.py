# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Behavior across syntax collaborators and independent emission sessions."""

from l0_analysis import AnalysisResult
from l0_c_emitter import CEmitter
from l0_types import BuiltinType, NullableType


def test_pointer_sites_share_temporary_sequence_and_output_with_statements():
    """Mixed syntax emission uses one sequence without affecting another session."""
    first = CEmitter()
    second = CEmitter()

    assert first.names.fresh_tmp("value") == "l0_value_1"
    first.values.emit_checked_ptr_access_for_base("ptr", "l0_int")
    first.statements.emit_checked_pointer_assignment("ptr", "l0_int", "7")
    first.cleanup.emit_string_release("owned")

    assert "static _rt_ptr_site l0_site_2;" in first.get_output()
    assert "static _rt_ptr_site l0_site_3;" in first.get_output()
    assert "= 7;" in first.get_output()
    assert "rt_string_release(owned);" in first.get_output()
    assert second.names.fresh_tmp("value") == "l0_value_1"
    assert second.get_output() == "\n"


def test_optional_wrapper_collection_is_independent_between_sessions():
    """Collecting another unit cannot erase or leak this unit's wrapper state."""
    first = CEmitter()
    second = CEmitter()
    first_analysis = AnalysisResult()
    first_analysis.expr_types[1] = NullableType(BuiltinType("int"))
    second_analysis = AnalysisResult()
    second_analysis.expr_types[1] = NullableType(BuiltinType("bool"))
    first.set_analysis(first_analysis)
    second.set_analysis(second_analysis)

    first.types.prepare_optional_wrappers()
    second.types.prepare_optional_wrappers()
    first.types.emit_optional_wrappers(early=True)
    first.types.emit_optional_wrappers(early=True)
    second.types.emit_optional_wrappers(early=True)

    assert first.get_output().count("} l0_opt_int;") == 1
    assert "l0_opt_bool" not in first.get_output()
    assert second.get_output().count("} l0_opt_bool;") == 1
    assert "l0_opt_int" not in second.get_output()
