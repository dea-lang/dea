/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include <stdint.h>

/**
 * Return the foreign C fixture answer for separate linking.
 * @return The fixed fixture answer.
 */
int32_t foreign_answer(void) {
    return 37;
}
