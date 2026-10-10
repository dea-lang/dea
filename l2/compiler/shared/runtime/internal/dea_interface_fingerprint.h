#ifndef DEA_INTERFACE_FINGERPRINT_H
#define DEA_INTERFACE_FINGERPRINT_H

/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_interface_fingerprint.h
 * Internal fixed-key SipHash-1-3 adapter for L1 interface fingerprints.
 */

#include <stddef.h>
#include <stdint.h>

#include "dea_siphash.h"

/** Fixed v1 interface-fingerprint key: the 16 UTF-8 bytes of `DeaL1-fp-v1-key!`. */
static const uint8_t _dea_l1_interface_fingerprint_key[16] = {
    'D', 'e', 'a', 'L', '1', '-', 'f', 'p',
    '-', 'v', '1', '-', 'k', 'e', 'y', '!'
};

/**
 * Hash bytes for the v1 interface-fingerprint domain and write lowercase hex.
 *
 * `out_hex` receives exactly 16 bytes and is not NUL-terminated. The caller
 * guarantees that `len` is non-negative and that `data` is readable for
 * `len` bytes.
 */
static void _dea_l1_interface_fingerprint_sip13_hex(
    const uint8_t *data,
    int32_t len,
    uint8_t out_hex[16]
) {
    static const uint8_t hex_digits[16] = {
        '0', '1', '2', '3', '4', '5', '6', '7',
        '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'
    };
    uint64_t hash = siphash13(data, (size_t)len, _dea_l1_interface_fingerprint_key);
    int32_t index;

    for (index = 0; index < 16; index++) {
        uint32_t shift = (uint32_t)(60 - (index * 4));
        out_hex[index] = hex_digits[(hash >> shift) & UINT64_C(0x0f)];
    }
}

#endif /* DEA_INTERFACE_FINGERPRINT_H */
