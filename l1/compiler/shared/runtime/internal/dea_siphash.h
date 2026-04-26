#ifndef SIPHASH_C99_SIPHASH_H
#define SIPHASH_C99_SIPHASH_H

/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

/**
 * @file dea_siphash.h
 * SipHash-1-3 and SipHash-2-4 (64-bit tag), portable C99.
 *
 * Header-only / single-header pattern:
 *  - In one translation unit: `#define SIPHASH_IMPLEMENTATION` before including this header.
 *  - Everywhere else: include this header without `SIPHASH_IMPLEMENTATION`.
 */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * SipHash-2-4 (64-bit tag).
 * 
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key, interpreted as little-endian (k0 = key[0..7], k1 = key[8..15]).
 * @return 64-bit hash value.
 */
uint64_t siphash24(const void *data, size_t len, const uint8_t key[16]);

/**
 * SipHash-1-3 (64-bit tag).
 * 
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key, interpreted as little-endian (k0 = key[0..7], k1 = key[8..15]).
 * @return 64-bit hash value.
 */
uint64_t siphash13(const void *data, size_t len, const uint8_t key[16]);

/**
 * Hash (tag8 || data) where tag8 is a raw 8-byte array using SipHash-2-4.
 * 
 * @param tag8 8-byte tag/prefix.
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key.
 * @return 64-bit hash value.
 */
uint64_t siphash24_tag8_bytes(const uint8_t tag8[8], const void *data, size_t len, const uint8_t key[16]);

/**
 * Hash (tag8 || data) where tag8 is a raw 8-byte array using SipHash-1-3.
 * 
 * @param tag8 8-byte tag/prefix.
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key.
 * @return 64-bit hash value.
 */
uint64_t siphash13_tag8_bytes(const uint8_t tag8[8], const void *data, size_t len, const uint8_t key[16]);

/**
 * Hash (tag8^flags || data) where tag8 is a raw 8-byte array and flags is one byte (XORed into tag8[0]).
 * Uses SipHash-2-4.
 * 
 * @param tag8 8-byte tag/prefix.
 * @param flags One byte flags XORed into tag8[0].
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key.
 * @return 64-bit hash value.
 */
uint64_t siphash24_tag8_bf(const uint8_t tag8[8], const uint8_t flags, const void *data, size_t len, const uint8_t key[16]);

/**
 * Hash (tag8^flags || data) where tag8 is a raw 8-byte array and flags is one byte (XORed into tag8[0]).
 * Uses SipHash-1-3.
 * 
 * @param tag8 8-byte tag/prefix.
 * @param flags One byte flags XORed into tag8[0].
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param key 16-byte key.
 * @return 64-bit hash value.
 */
uint64_t siphash13_tag8_bf(const uint8_t tag8[8], const uint8_t flags, const void *data, size_t len, const uint8_t key[16]);


#ifdef __cplusplus
}
#endif

#ifdef SIPHASH_IMPLEMENTATION

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Rotate left a 64-bit value.
 * 
 * @param x 64-bit value to rotate.
 * @param b Number of bits to rotate (MUST be nonzero to avoid undefined behavior).
 * @return Rotated value.
 */
static uint64_t sh_rotl64(uint64_t x, unsigned b) {
  return x << b | x >> (64u - b);
}

/**
 * Load 64-bit little-endian word from bytes (portable across host endianness and alignment).
 * 
 * @param p Pointer to bytes.
 * @return 64-bit word.
 */
static uint64_t sh_load64_le(const uint8_t *p) {
  return (uint64_t)p[0]       |
         (uint64_t)p[1] << 8  |
         (uint64_t)p[2] << 16 |
         (uint64_t)p[3] << 24 |
         (uint64_t)p[4] << 32 |
         (uint64_t)p[5] << 40 |
         (uint64_t)p[6] << 48 |
         (uint64_t)p[7] << 56;
}

/**
 * One SipRound: update the four state words (v0,v1,v2,v3) in place.
 */
#define SH_SIPROUND(v0, v1, v2, v3)   \
  do {                                \
    (v0) += (v1);                     \
    (v2) += (v3);                     \
    (v1) = sh_rotl64((v1), 13);       \
    (v3) = sh_rotl64((v3), 16);       \
    (v1) ^= (v0);                     \
    (v3) ^= (v2);                     \
    (v0) = sh_rotl64((v0), 32);       \
    (v2) += (v1);                     \
    (v0) += (v3);                     \
    (v1) = sh_rotl64((v1), 17);       \
    (v3) = sh_rotl64((v3), 21);       \
    (v1) ^= (v2);                     \
    (v3) ^= (v0);                     \
    (v2) = sh_rotl64((v2), 32);       \
  } while (0)

/**
 * Core SipHash implementation with configurable (c, d) rounds.
 * Used by siphash24 and siphash13.
 * 
 * @param data Pointer to the data to hash.
 * @param len Length of the data in bytes.
 * @param k0 First 64 bits of the key.
 * @param k1 Second 64 bits of the key.
 * @param c_rounds Number of compression rounds.
 * @param d_rounds Number of finalization rounds.
 * @return 64-bit hash value.
 */
static uint64_t sh_siphash_cd(const void *data, size_t len,
                           uint64_t k0, uint64_t k1,
                           int c_rounds, int d_rounds)
{
  const uint8_t *in = (const uint8_t *)data;
  const uint8_t *end = in + (len & ~(size_t)7);

  /* SipHash initialization vectors (from the SipHash specification). */
  uint64_t v0 = 0x736f6d6570736575ULL ^ k0;
  uint64_t v1 = 0x646f72616e646f6dULL ^ k1;
  uint64_t v2 = 0x6c7967656e657261ULL ^ k0;
  uint64_t v3 = 0x7465646279746573ULL ^ k1;

  for (; in != end; in += 8) {
    uint64_t m = sh_load64_le(in);
    v3 ^= m;
    for (int i = 0; i < c_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);
    v0 ^= m;
  }

  /* Final block: top byte is message length mod 256, lower bytes are remaining tail (per SipHash spec). */
  /* In other words, b = (len << 56) | tail */
  uint64_t b = ((uint64_t)len) << 56;
  switch (len & 7) {
  case 7: b |= (uint64_t)in[6] << 48; /* fallthrough */
  case 6: b |= (uint64_t)in[5] << 40; /* fallthrough */
  case 5: b |= (uint64_t)in[4] << 32; /* fallthrough */
  case 4: b |= (uint64_t)in[3] << 24; /* fallthrough */
  case 3: b |= (uint64_t)in[2] << 16; /* fallthrough */
  case 2: b |= (uint64_t)in[1] << 8;  /* fallthrough */
  case 1: b |= (uint64_t)in[0]; /* fallthrough */
  default: break;
  }

  v3 ^= b;
  for (int i = 0; i < c_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);
  v0 ^= b;

  /* Finalization marker (per SipHash spec). */
  v2 ^= 0xff;
  for (int i = 0; i < d_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);

  return (v0 ^ v1) ^ (v2 ^ v3);
}

/**
 * Load 128-bit key as (k0,k1) in little-endian order to be endian-independent.
 * 
 * @param key 16-byte key.
 * @param k0 Output for first 64 bits.
 * @param k1 Output for second 64 bits.
 */
static void sh_key_to_k01(const uint8_t key[16], uint64_t *k0, uint64_t *k1) {
  *k0 = sh_load64_le(&key[0]);
  *k1 = sh_load64_le(&key[8]);
}

/**
 * SipHash with c=2, d=4 rounds.
 */
uint64_t siphash24(const void *data, size_t len, const uint8_t key[16]) {
  uint64_t k0, k1;
  sh_key_to_k01(key, &k0, &k1);
  return sh_siphash_cd(data, len, k0, k1, 2, 4);
}

/**
 * SipHash with c=1, d=3 rounds.
 */
uint64_t siphash13(const void *data, size_t len, const uint8_t key[16]) {
  uint64_t k0, k1;
  sh_key_to_k01(key, &k0, &k1);
  return sh_siphash_cd(data, len, k0, k1, 1, 3);
}

/**
 * Core SipHash implementation with 8-byte tag prefix.
 * 
 * @param data Pointer to the data.
 * @param len Length of the data.
 * @param k0 First 64 bits of key.
 * @param k1 Second 64 bits of key.
 * @param tag8_le 8-byte tag in little-endian.
 * @param c_rounds Compression rounds.
 * @param d_rounds Finalization rounds.
 * @return 64-bit hash.
 */
static uint64_t sh_siphash_cd_tag8(const void *data, size_t len,
                                  uint64_t k0, uint64_t k1,
                                  uint64_t tag8_le,
                                  int c_rounds, int d_rounds) {
  const uint8_t *in = (const uint8_t *)data;
  const uint8_t *end = in + (len & ~(size_t)7);

  /* SipHash initialization vectors (from the SipHash specification). */
  uint64_t v0 = 0x736f6d6570736575ULL ^ k0;
  uint64_t v1 = 0x646f72616e646f6dULL ^ k1;
  uint64_t v2 = 0x6c7967656e657261ULL ^ k0;
  uint64_t v3 = 0x7465646279746573ULL ^ k1;

  /* First message block: the 8-byte tag/prefix. */
  {
    uint64_t m = tag8_le;
    v3 ^= m;
    for (int i = 0; i < c_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);
    v0 ^= m;
  }

  /* Process data blocks. */
  for (; in != end; in += 8) {
    uint64_t m = sh_load64_le(in);
    v3 ^= m;
    for (int i = 0; i < c_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);
    v0 ^= m;
  }

  /* Final block length includes the 8-byte tag. */
  uint64_t total_len = (uint64_t)len + 8u;
  uint64_t b = total_len << 56;

  switch (len & 7) {
    case 7: b |= (uint64_t)in[6] << 48; /* fallthrough */
    case 6: b |= (uint64_t)in[5] << 40; /* fallthrough */
    case 5: b |= (uint64_t)in[4] << 32; /* fallthrough */
    case 4: b |= (uint64_t)in[3] << 24; /* fallthrough */
    case 3: b |= (uint64_t)in[2] << 16; /* fallthrough */
    case 2: b |= (uint64_t)in[1] << 8;  /* fallthrough */
    case 1: b |= (uint64_t)in[0]; break;
    default: break;
  }

  v3 ^= b;
  for (int i = 0; i < c_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);
  v0 ^= b;

  v2 ^= 0xff;
  for (int i = 0; i < d_rounds; i++) SH_SIPROUND(v0, v1, v2, v3);

  return (v0 ^ v1) ^ (v2 ^ v3);
}

/**
 * SipHash-2-4 with 8-byte tag prefix.
 */
uint64_t siphash24_tag8_u64(uint64_t tag8_le, const void *data, size_t len, const uint8_t key[16]) {
  uint64_t k0, k1;
  sh_key_to_k01(key, &k0, &k1);
  return sh_siphash_cd_tag8(data, len, k0, k1, tag8_le, 2, 4);
}

/**
 * SipHash-1-3 with 8-byte tag prefix.
 */
uint64_t siphash13_tag8_u64(uint64_t tag8_le, const void *data, size_t len, const uint8_t key[16]) {
  uint64_t k0, k1;
  sh_key_to_k01(key, &k0, &k1);
  return sh_siphash_cd_tag8(data, len, k0, k1, tag8_le, 1, 3);
}

/**
 * SipHash-2-4 with 8-byte tag prefix as byte array.
 */
uint64_t siphash24_tag8_bytes(const uint8_t tag8[8], const void *data, size_t len, const uint8_t key[16]) {
  return siphash24_tag8_u64(sh_load64_le(tag8), data, len, key);
}

/**
 * SipHash-1-3 with 8-byte tag prefix as byte array.
 */
uint64_t siphash13_tag8_bytes(const uint8_t tag8[8], const void *data, size_t len, const uint8_t key[16]) {
  return siphash13_tag8_u64(sh_load64_le(tag8), data, len, key);
}

/**
 * SipHash-2-4 with 8-byte tag prefix as byte array and 1 byte flags XORed into tag8[0].
 */
uint64_t siphash24_tag8_bf(const uint8_t tag8[8], const uint8_t flags, const void *data, size_t len, const uint8_t key[16]) {
  return siphash24_tag8_u64(sh_load64_le(tag8)^flags, data, len, key);
}

/**
 * SipHash-1-3 with 8-byte tag prefix as byte array and 1 byte flags XORed into tag8[0].
 */
uint64_t siphash13_tag8_bf(const uint8_t tag8[8], const uint8_t flags, const void *data, size_t len, const uint8_t key[16]) {
  return siphash13_tag8_u64(sh_load64_le(tag8)^flags, data, len, key);
}

#ifdef __cplusplus
}
#endif

#endif /* SIPHASH_IMPLEMENTATION */

#endif /* SIPHASH_C99_SIPHASH_H */
