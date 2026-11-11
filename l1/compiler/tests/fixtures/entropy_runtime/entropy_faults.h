/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#ifndef DEA_ENTROPY_FAULTS_H
#define DEA_ENTROPY_FAULTS_H
#include "dea_rt.h"

/* Select one deterministic host scenario and reset all probe counters. */
void entropy_probe_config(dea_int mode);

/* Return the number of native entropy calls in the selected scenario. */
dea_int entropy_probe_calls(void);

/* Return the number of Windows loader calls in the selected scenario. */
dea_int entropy_probe_loads(void);

/* Return the number of Windows export lookups in the selected scenario. */
dea_int entropy_probe_lookups(void);

/* Return the expected native code for the selected failure scenario. */
dea_long entropy_probe_error(void);

/* Return the native error namespace of the selected scenario. */
dea_int entropy_probe_domain(void);

/* Return the number of temporary Windows module references released. */
dea_int entropy_probe_releases(void);

#if defined(_WIN32)
#include <windows.h>
#define DEA_ENTROPY_LOAD_LIBRARY entropy_probe_load
#define DEA_ENTROPY_GET_PROC entropy_probe_proc
#define DEA_ENTROPY_FREE_LIBRARY entropy_probe_free

/* Validate the secure DLL-search policy and simulate loader failure. */
HMODULE WINAPI entropy_probe_load(LPCWSTR name, HANDLE file, DWORD flags);

/* Resolve the injected BCrypt operation or simulate missing export failure. */
FARPROC WINAPI entropy_probe_proc(HMODULE module, LPCSTR name);

/* Release one simulated DLL reference while perturbing ambient last-error. */
BOOL WINAPI entropy_probe_free(HMODULE module);
#elif defined(__linux__) || defined(__FreeBSD__) || defined(__NetBSD__)
#include <sys/random.h>
#define DEA_ENTROPY_GETRANDOM entropy_probe_getrandom

/* Inject bounded native transfers, short results, and saved errno failures. */
ssize_t entropy_probe_getrandom(void *buf, size_t count, unsigned int flags);
#else
#define DEA_ENTROPY_GETENTROPY entropy_probe_getentropy

/* Inject bounded all-or-fail native entropy calls and saved errno failures. */
int entropy_probe_getentropy(void *buf, size_t count);
#endif
#endif
