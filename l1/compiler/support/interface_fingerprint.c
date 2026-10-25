/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file interface_fingerprint.c
 * Fixed-key, allocation-free fingerprint bridge for the L0-built L1.
 * The L0-generated translation unit supplies the SipHash implementation.
 * L1-built compilers obtain this bridge from the L1 runtime archive instead.
 */

#include "../shared/runtime/internal/dea_interface_fingerprint.h"

/**
 * Compute the canonical L1 interface fingerprint digest as lowercase hex.
 *
 * @param data Canonical interface bytes.
 * @param len Byte length of `data`; must be non-negative.
 * @param out_hex Exact 16-byte output buffer; no NUL terminator is written.
 */
void l1c_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    _dea_l1_interface_fingerprint_sip13_hex(data, len, out_hex);
}

/**
 * Compiler-facing pointer adapter; input bytes remain read-only.
 *
 * Compiler-private L0/L1 pointer adapter; does not modify input bytes.
 * Pointer parameters match generated extern declarations, including under GCC array-parameter warnings.
 *
 * @param data Read-only canonical interface bytes passed through the pointer ABI. Canonical interface
 * bytes.
 * @param len Non-negative byte length of data. Number of canonical bytes.
 * @param out_hex Exact 16-byte output buffer; no NUL terminator is written. Caller-owned storage for
 * exactly 16 output bytes; no NUL terminator is written.
 */
void l1c_interface_fingerprint_sip13_hex_bytes(
    uint8_t *data,
    int32_t len,
    uint8_t *out_hex
) {
    l1c_interface_fingerprint_sip13_hex(data, len, out_hex);
}
