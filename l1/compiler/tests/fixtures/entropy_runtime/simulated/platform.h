/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/* Load every host header used by the adapter fixtures before changing selectors.
 * The runtime header guard keeps the production TU on these real host types. */
#include "dea_rt.h"
#include <assert.h>
#include <wchar.h>

#undef _WIN32
#undef __APPLE__
#undef __linux__
#undef __FreeBSD__
#undef __NetBSD__
#undef __OpenBSD__
#if defined(DEA_ENTROPY_SIMULATE_WINDOWS)
#define _WIN32 1
#elif defined(DEA_ENTROPY_SIMULATE_GETRANDOM)
#define __linux__ 1
#elif defined(DEA_ENTROPY_SIMULATE_UNSUPPORTED)

/* Leave every supported entropy backend unselected. */
#else
#error "Select an entropy adapter simulation"
#endif
