/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for pseudo-random number generation.
 * ========================================================================= */

/**
 * Seed the random number generator.
 * Uses current time if seed is 0.
 *
 * L0 signature: `extern func rt_srand(seed: int) -> void;`
 *
 * @param seed Seed value.
 */
void rt_srand(dea_int seed) {
    if (seed == 0) {
        srand((unsigned int)time(NULL));
    } else {
        srand((unsigned int)seed);
    }
}

/**
 * Generate a random integer in the range [0, max).
 * Returns 0 if max <= 0.
 *
 * Dea signature: `extern func rt_rand(max: int) -> int;`
 *
 * @param max Upper bound (exclusive).
 * @return Random value.
 */
dea_int rt_rand(dea_int max) {
    if (max <= 0) {
        return 0;
    }
    return (dea_int)(rand() % max);
}
