/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#ifndef DEA_ENTROPY_SIMULATED_RANDOM_H
#define DEA_ENTROPY_SIMULATED_RANDOM_H

/* Native-call hooks supply the implementation; only Linux's API constants and
 * signed transfer width are needed to compile the unmodified adapter branch. */
#define GRND_NONBLOCK 0x0001
#define ssize_t ptrdiff_t
#endif
