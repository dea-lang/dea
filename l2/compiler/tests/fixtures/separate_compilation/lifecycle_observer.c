/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include <stdint.h>

static int32_t next_step = 1;
static int32_t order_failed = 0;

/**
 * Record a lifecycle tag and remember any event-order mismatch.
 *
 * @param tag Lifecycle event tag to record.
 * @return The supplied tag, regardless of whether its order matched.
 */
int32_t lifecycle_record(int32_t tag) {
    if (tag != next_step) {
        order_failed = 1;
    }
    next_step += 1;
    return tag;
}

/**
 * Check that four lifecycle events occurred in the required order.
 * @return Zero for the complete correct sequence; one for an order or count mismatch.
 */
int32_t lifecycle_verify(void) {
    return order_failed == 0 && next_step == 5 ? 0 : 1;
}
