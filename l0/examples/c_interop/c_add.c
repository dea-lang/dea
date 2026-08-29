/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "dea_rt.h"

/**
 * Add two L0 integers across the C FFI boundary.
 *
 * @param left Left operand.
 * @param right Right operand.
 * @return The sum of the operands.
 */
dea_int add_in_c(dea_int left, dea_int right)
{
    return left + right;
}
