/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/*
 * L1 compiler support linked beside the L0-generated Stage 1 translation
 * unit. The generated unit owns the SipHash implementation; this unit only
 * supplies the fixed-key, allocation-free interface-fingerprint ABI.
 */

#include "../../shared/runtime/internal/dea_interface_fingerprint.h"

void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    _dea_l1_interface_fingerprint_sip13_hex(data, len, out_hex);
}
