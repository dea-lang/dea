/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file inventory_mutation.c Falsify constructor results without a production test ABI.
 */
#include "../../../support/preparation_support.c"

/**
 * Replace one completed constructor result while retaining its real payloads and policy context.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @param data Borrowed readable input byte span.
 * @param length Number of input elements or bytes, as appropriate.
 * @return One after replacing the completed fixture inventory; zero for invalid state or malformed data.
 */
int32_t l1c_test_construction_inventory(void *context, const uint8_t *data, int32_t length) {
    PcContext *c = context;
    PcJson *inventory;
    if (!c || !c->construction || !c->construction->inventory || !data || length < 0) return 0;
    inventory = pj_parse((const char *)data, (size_t)length);
    if (!inventory) return 0;
    pj_free(c->construction->inventory);
    c->construction->inventory = inventory;
    return 1;
}
