#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Regression coverage for vendored m.css Doxygen compatibility."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest


def _load_mcss_doxygen():
    """Load the vendored m.css Doxygen renderer as a module."""

    documentation_dir = Path(__file__).resolve().parents[5] / "tools" / "m.css" / "documentation"
    spec = spec_from_file_location("dea_vendored_mcss_doxygen", documentation_dir / "doxygen.py")
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(documentation_dir))
    try:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


MCSS_DOXYGEN = _load_mcss_doxygen()


@pytest.mark.parametrize(
    ("name", "parent_name", "expected"),
    [
        ("api::Record::Field", "api::Record", "Field"),
        ("l0_string::[union].data", "l0_string", "[union].data"),
        ("l0_string::[struct].data.s_str", "l0_string::[union].data", "s_str"),
    ],
)
def test_compound_leaf_name_supports_established_and_doxygen_1_18_names(
    name: str,
    parent_name: str,
    expected: str,
) -> None:
    assert MCSS_DOXYGEN._compound_leaf_name(name, parent_name) == expected


def test_compound_leaf_name_rejects_unrelated_anonymous_field_paths() -> None:
    with pytest.raises(AssertionError, match="does not descend"):
        MCSS_DOXYGEN._compound_leaf_name(
            "l0_string::[struct].other.s_str",
            "l0_string::[union].data",
        )
