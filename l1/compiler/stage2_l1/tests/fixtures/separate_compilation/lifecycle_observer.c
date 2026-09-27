/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include <stdint.h>

static int32_t next_step = 1;
static int32_t order_failed = 0;

int32_t lifecycle_record(int32_t tag) {
    if (tag != next_step) {
        order_failed = 1;
    }
    next_step += 1;
    return tag;
}

int32_t lifecycle_verify(void) {
    return order_failed == 0 && next_step == 5 ? 0 : 1;
}
