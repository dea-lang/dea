#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Native C and L1 regression for compound dereference operands."""

import sys

from l1c_compile_only_test import L1_ROOT, resolve_host_c_compiler, stage1_compiler
from support.driver_inputs import native_driver_args

sys.path.insert(0, str(L1_ROOT / "compiler/scripts"))
sys.path.insert(0, str(L1_ROOT.parent))
from scripts.tests.fixtures.deref_lvalue.probe import check_deref_lvalue
from test_runner_common import bootstrap_command, compiler_support_args


def main() -> None:
    """Run both branch writes and an ordinary checked pointer access."""
    cc = resolve_host_c_compiler()
    compiler = stage1_compiler()
    check_deref_lvalue(
        "c_emitter.expr",
        [*bootstrap_command(), "--run", "--project-root", str(L1_ROOT / "compiler/src"),
         *compiler_support_args(preparation=False)],
        cc, [compiler, "--run", "--c-compiler", cc, *native_driver_args(compiler, cc)], ".l1",
    )


if __name__ == "__main__":
    main()
