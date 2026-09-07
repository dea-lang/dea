#  SPDX-License-Identifier: MIT OR Apache-2.0
#  Copyright (c) 2026 gwz

import pytest

from l0_analysis import AnalysisResult
from l0_c_emitter import CEmitter
from l0_internal_error import InternalCompilerError
from l0_types import EnumType, StructType


def test_emit_enum_cleanup_ice_on_missing_enum_info():
    emitter = CEmitter()
    emitter.set_analysis(AnalysisResult())

    with pytest.raises(InternalCompilerError, match=r"\[ICE-1080\]"):
        emitter.cleanup.emit_enum_cleanup("p", EnumType("main", "Missing"))


def test_emit_struct_cleanup_ice_on_missing_struct_info():
    emitter = CEmitter()
    emitter.set_analysis(AnalysisResult())

    with pytest.raises(InternalCompilerError, match=r"\[ICE-1270\]"):
        emitter.cleanup.emit_struct_cleanup("p", StructType("main", "Missing"))
