/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include <stdint.h>

/**
 * Multiply two L0 integers across the C FFI boundary.
 *
 * @param left Left operand.
 * @param right Right operand.
 * @return The product of the operands.
 */
int32_t multiply_in_c(int32_t left, int32_t right)
{
    return left * right;
}
