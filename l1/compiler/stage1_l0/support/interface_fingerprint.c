/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file interface_fingerprint.c
 * Fixed-key, allocation-free fingerprint bridge for the L0-built Stage 1.
 * The L0-generated translation unit supplies the SipHash implementation.
 * L1-built compilers obtain this bridge from the L1 runtime archive instead.
 */

#include "../../shared/runtime/internal/dea_interface_fingerprint.h"

void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    _dea_l1_interface_fingerprint_sip13_hex(data, len, out_hex);
}

/** Compiler-facing pointer adapter; input bytes remain read-only. */
void l1c_interface_fingerprint_sip13_hex_bytes(
    uint8_t *data,
    int32_t len,
    uint8_t *out_hex
) {
    l1c_interface_fingerprint_sip13_hex(data, len, out_hex);
}
