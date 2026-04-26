/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#define SIPHASH_IMPLEMENTATION

#include "../include/dea_rt.h"
#include "dea_siphash.h"

/* =========================================================================
 * Runtime support for hashing (using SipHash-1-3)
 * ========================================================================= */

/**
 * Final mixing function for 32-bit hashes (MurmurHash3 fmix32).
 *
 * @param x Current hash.
 * @return Mixed hash.
 */
uint32_t _rt_fmix32(uint32_t x) {
    x ^= x >> 16;
    x *= 0x85ebca6bu;
    x ^= x >> 13;
    x *= 0xc2b2ae35u;
    x ^= x >> 16;
    return x;
}

/**
 * Fold a 64-bit hash into a 32-bit hash with final mixing.
 *
 * @param h 64-bit hash.
 * @return 32-bit hash.
 */
uint32_t _rt_fold_u64_to_u32_fmix(uint64_t h) {
    uint32_t x = (uint32_t)(h ^ (h >> 32));
    return _rt_fmix32(x);
}

typedef uint8_t _rt_siphash_key_t[16];
typedef uint8_t _rt_siphash_tag8_t[8];

/* Type tags for L0 runtime type identification */
static const _rt_siphash_tag8_t _dea_sh_tag_bool   = { 0, 'b', 'o', 'o', 'l' };
static const _rt_siphash_tag8_t _dea_sh_tag_byte   = { 0, 'i', 'n', 't', 8 };
static const _rt_siphash_tag8_t _dea_sh_tag_int    = { 0, 'i', 'n', 't', 32 };
static const _rt_siphash_tag8_t _dea_sh_tag_string = { 0, 's', 't', 'r', 'i', 'n', 'g' };
static const _rt_siphash_tag8_t _dea_sh_tag_data   = { 0, 'd', 'a', 't', 'a' };

/* Flag bits for hash functions */
#define _DEA_TAG_OPT 0x80    /* option */
#define _DEA_TAG_PTR 0x40    /* pointer */
#define _DEA_TAG_ENUM 0x20   /* enum */
#define _DEA_TAG_STRUCT 0x10 /* struct */

/**
 * Default (debug) SipHash key for L0 runtime.
 * In production, it will be randomized at runtime to prevent hash-flooding attacks.
 */
static _rt_siphash_key_t _rt_sh_key = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F
};

/**
 * Internal helper to hash data with a given 8-byte tag and flags.
 *
 * @param tag8 8-byte tag.
 * @param flags Flags.
 * @param data Pointer to data.
 * @param len Data length.
 * @param key SipHash key.
 * @return 32-bit hash.
 */
static dea_int _rt_hash_tag8(const _rt_siphash_tag8_t tag8,
                            const uint8_t flags,
                            const void *data, size_t len,
                            const _rt_siphash_key_t key)
{
    uint64_t hash = siphash13_tag8_bf(tag8, flags, data, len, key); /* compute SipHash-1-3 */
    return _rt_fold_u64_to_u32_fmix(hash);
}

/* Hash functions for basic types */

/**
 * Hash a boolean value with the runtime bool tag.
 *
 * @param value Boolean value to hash.
 * @param flags Type-shaping flags mixed into the hash domain.
 * @return 32-bit hash.
 */
dea_int _rt_hash_bool(dea_bool value, const uint8_t flags) {
    return _rt_hash_tag8(_dea_sh_tag_bool, flags, &value, sizeof(dea_bool), _rt_sh_key);
}

/**
 * Hash a byte value with the runtime byte tag.
 *
 * @param value Byte value to hash.
 * @param flags Type-shaping flags mixed into the hash domain.
 * @return 32-bit hash.
 */
dea_int _rt_hash_byte(dea_byte value, const uint8_t flags) {
    return _rt_hash_tag8(_dea_sh_tag_byte, flags, &value, sizeof(dea_byte), _rt_sh_key);
}

/**
 * Hash an integer value with the runtime int tag.
 *
 * @param value Integer value to hash.
 * @param flags Type-shaping flags mixed into the hash domain.
 * @return 32-bit hash.
 */
dea_int _rt_hash_int(dea_int value, const uint8_t flags) {
    return _rt_hash_tag8(_dea_sh_tag_int, flags, &value, sizeof(dea_int), _rt_sh_key);
}

/**
 * Hash a string's byte contents with the runtime string tag.
 *
 * @param str String value to hash.
 * @param flags Type-shaping flags mixed into the hash domain.
 * @return 32-bit hash.
 */
dea_int _rt_hash_string(dea_string str, const uint8_t flags) {
    const char *str_data = _rt_string_bytes(str);
    dea_int str_len = rt_strlen(str);
    return _rt_hash_tag8(_dea_sh_tag_string, flags, str_data, (size_t)str_len, _rt_sh_key);
}

/**
 * Hash an arbitrary byte sequence with the runtime data tag.
 *
 * @param data Pointer to the byte sequence.
 * @param size Size of `data` in bytes.
 * @param flags Type-shaping flags mixed into the hash domain.
 * @return 32-bit hash.
 */
dea_int _rt_hash_data(void *data, dea_int size, const uint8_t flags) {
    return _rt_hash_tag8(_dea_sh_tag_data, flags, data, (size_t)size, _rt_sh_key);
}

/* =========================================================================
 * User-exposed hash functions
 * ========================================================================= */

/**
 * Hash a boolean value.
 *
 * @param value Boolean value.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_bool(value: bool) -> int;`
 */
dea_int rt_hash_bool(dea_bool value) {
    return _rt_hash_bool(value, 0);
}

/**
 * Hash a byte value.
 *
 * @param value Byte value.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_byte(value: byte) -> int;`
 */
dea_int rt_hash_byte(dea_byte value) {
    return _rt_hash_byte(value, 0);
}

/**
 * Hash an integer value.
 *
 * @param value Integer value.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_int(value: int) -> int;`
 */
dea_int rt_hash_int(dea_int value) {
    return _rt_hash_int(value, 0);
}

/**
 * Hash a string value.
 *
 * @param value L0 string.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_string(value: string) -> int;`
 */
dea_int rt_hash_string(dea_string value) {
    return _rt_hash_string(value, 0);
}

/**
 * Hash raw data.
 * Panics if data is null or size is negative.
 *
 * @param data Pointer to data.
 * @param size Data size.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_data(data: void*, size: int) -> int;`
 */
dea_int rt_hash_data(void *data, dea_int size) {
    if (size < 0) {
        _rt_panic("rt_hash_data: negative size");
    }
    if (data == NULL) {
        _rt_panic("rt_hash_data: null data pointer");
    }
    return _rt_hash_data(data, size, 0);
}

/**
 * Hash an optional boolean value.
 *
 * @param opt Optional bool.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_opt_bool(opt: bool?) -> int;`
 */
dea_int rt_hash_opt_bool(dea_opt_bool opt) {
    uint8_t flags = _DEA_TAG_OPT;
    return _rt_hash_data(&opt, sizeof(dea_opt_bool), flags);
}

/**
 * Hash an optional byte value.
 *
 * @param opt Optional byte.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_opt_byte(opt: byte?) -> int;`
 */
dea_int rt_hash_opt_byte(dea_opt_byte opt) {
    uint8_t flags = _DEA_TAG_OPT;
    return _rt_hash_data(&opt, sizeof(dea_opt_byte), flags);
}

/**
 * Hash an optional integer value.
 *
 * @param opt Optional int.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_opt_int(opt: int?) -> int;`
 */
dea_int rt_hash_opt_int(dea_opt_int opt) {
    uint8_t flags = _DEA_TAG_OPT;
    return _rt_hash_data(&opt, sizeof(dea_opt_int), flags);
}

/**
 * Hash an optional string value.
 * If opt is empty, hashes as an empty string with the optional flag.
 *
 * @param opt Optional string.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_opt_string(opt: string?) -> int;`
 */
dea_int rt_hash_opt_string(dea_opt_string opt) {
    uint8_t flags = _DEA_TAG_OPT;
    if (opt.has_value) {
        return _rt_hash_string(opt.value, flags);
    } else {
        return _rt_hash_string(DEA_STRING_EMPTY, flags);
    }
}

/**
 * Hash a pointer value.
 * Note: this hashes the pointer value (address), not the data it points to.
 * Panics if ptr is null.
 *
 * @param ptr Pointer.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_ptr(ptr: void*) -> int;`
 */
dea_int rt_hash_ptr(void *ptr) {
    if (ptr == NULL) {
        _rt_panic("rt_hash_ptr: null pointer");
    }
    uint8_t flags = _DEA_TAG_PTR;
    return _rt_hash_data(&ptr, sizeof(void*), flags);
}

/**
 * Hash an optional pointer value.
 * Note: this hashes the pointer value (address), not the data it points to.
 * Panics if opt is empty (null pointer).
 *
 * @param opt Pointer.
 * @return 32-bit hash.
 *
 * L0 signature: `extern func rt_hash_opt_ptr(opt: void*?) -> int;`
 */
dea_int rt_hash_opt_ptr(void *opt) {
    if (opt == NULL) {
        _rt_panic("rt_hash_opt_ptr: unwrap of empty optional");
    }
    uint8_t flags = _DEA_TAG_OPT | _DEA_TAG_PTR;
    return _rt_hash_data(&opt, sizeof(void*), flags);
}
