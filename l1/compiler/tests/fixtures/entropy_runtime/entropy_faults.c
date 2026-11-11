/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "entropy_faults.h"
#include <assert.h>
#include <wchar.h>

static dea_int probe_mode;
static dea_int probe_calls;
static dea_int probe_bytes;
static dea_int probe_releases;
static dea_int probe_loads;
static dea_int probe_lookups;

/**
 * Select one deterministic host scenario and reset all probe counters.
 *
 * @param mode Zero succeeds; one fails immediately; two fails after one chunk;
 * three interrupts POSIX or rejects Windows parameters; four through six
 * inject short, zero, and oversized getrandom results; seven and eight fail
 * Windows loading and export lookup respectively; nine and ten return
 * unavailable entropy and an unsupported syscall on getrandom hosts; eleven
 * succeeds with a short prefix before failing the next getrandom call. Twelve
 * fails Windows cleanup after a provider error; thirteen returns an unknown NTSTATUS.
 */
void entropy_probe_config(dea_int mode) {
    probe_mode = mode;
    probe_calls = 0;
    probe_bytes = 0;
    probe_releases = 0;
    probe_loads = 0;
    probe_lookups = 0;
}

/**
 * Return the number of native entropy calls in the selected scenario.
 *
 * @return Number of attempts, including failed calls.
 */
dea_int entropy_probe_calls(void) {
    return probe_calls;
}

/**
 * Return the number of Windows loader calls in the selected scenario.
 *
 * @return Load attempt count, always zero on POSIX hosts.
 */
dea_int entropy_probe_loads(void) {
    return probe_loads;
}

/**
 * Return the number of Windows export lookups in the selected scenario.
 *
 * @return Export lookup count, always zero on POSIX hosts.
 */
dea_int entropy_probe_lookups(void) {
    return probe_lookups;
}

/**
 * Return the expected native code for the selected failure scenario.
 *
 * @return Unsigned NTSTATUS/Win32 code or positive errno code.
 */
dea_long entropy_probe_error(void) {
#if defined(_WIN32)
    if (probe_mode == 7) return ERROR_MOD_NOT_FOUND;
    if (probe_mode == 8) return ERROR_PROC_NOT_FOUND;
    if (probe_mode == 13) return UINT32_C(0xc1234567);
    return probe_mode == 3 ? UINT32_C(0xc000000d) : UINT32_C(0xc0000022);
#else
    if (probe_mode == 9) return EAGAIN;
    if (probe_mode == 10) return ENOSYS;
    return probe_mode == 3 ? EINTR : EACCES;
#endif
}

/**
 * Return the native error namespace of the selected scenario.
 *
 * @return Stable runtime namespace tag.
 */
dea_int entropy_probe_domain(void) {
#if defined(_WIN32)
    return probe_mode == 7 || probe_mode == 8 ? DEA_OS_DOMAIN_WIN32 : DEA_OS_DOMAIN_NTSTATUS;
#else
    return DEA_OS_DOMAIN_ERRNO;
#endif
}

/**
 * Return the number of temporary Windows module references released.
 *
 * @return Release count; always zero on POSIX hosts.
 */
dea_int entropy_probe_releases(void) {
    return probe_releases;
}

/**
 * Fill a bounded host request or deliberately dirty it before reporting failure.
 *
 * @param buf Host destination with at least count writable bytes.
 * @param count Positive request size bounded by the production chunk limit.
 * @return Nonzero on a configured failure, zero after deterministic success.
 */
static int probe_fill(void *buf, size_t count) {
    assert(buf != NULL && count > 0 && count <= 256);
    probe_calls++;
    if (probe_mode == 1 || probe_mode == 3 || probe_mode == 9 || probe_mode == 10 ||
        probe_mode == 12 || probe_mode == 13 ||
        ((probe_mode == 2 || probe_mode == 11) && probe_calls == 2)) {
        memset(buf, 0xee, count);
        return 1;
    }
    for (size_t i = 0; i < count; i++)
        ((unsigned char *)buf)[i] = (unsigned char)((probe_bytes + (dea_int)i) % 251);
    probe_bytes += (dea_int)count;
    return 0;
}

#if defined(_WIN32)

/**
 * Implement the injected system-preferred BCrypt RNG call.
 *
 * @param algorithm Required null system-preferred provider selector.
 * @param buf Writable temporary chunk owned by the entropy adapter.
 * @param count Requested bytes, at most 256.
 * @param flags Required BCRYPT_USE_SYSTEM_PREFERRED_RNG flag.
 * @return Success or the configured NTSTATUS with a deliberately unrelated last-error.
 */
static LONG WINAPI probe_generate(void *algorithm, unsigned char *buf, ULONG count, ULONG flags) {
    assert(algorithm == NULL && flags == 0x00000002);
    if (probe_fill(buf, count)) {
        SetLastError(ERROR_FILE_NOT_FOUND);
        return (LONG)(uint32_t)entropy_probe_error();
    }
    return 0;
}

/**
 * Validate the secure DLL-search policy and simulate loader failure.
 *
 * @param name Required bcrypt.dll name.
 * @param file Required null reserved argument.
 * @param flags Required System32-only lookup flag.
 * @return Simulated owned module reference, or null with a saved Win32 error.
 */
HMODULE WINAPI entropy_probe_load(LPCWSTR name, HANDLE file, DWORD flags) {
    assert(wcscmp(name, L"bcrypt.dll") == 0 && file == NULL && flags == 0x00000800);
    probe_loads++;
    if (probe_mode == 7) {
        SetLastError(ERROR_MOD_NOT_FOUND);
        return NULL;
    }
    return (HMODULE)(uintptr_t)1;
}

/**
 * Resolve the injected BCrypt operation or simulate missing export failure.
 *
 * @param module Simulated live module reference.
 * @param name Required BCryptGenRandom export name.
 * @return Injected function pointer, or null with a saved Win32 error.
 */
FARPROC WINAPI entropy_probe_proc(HMODULE module, LPCSTR name) {
    assert(module == (HMODULE)(uintptr_t)1 && strcmp(name, "BCryptGenRandom") == 0);
    probe_lookups++;
    if (probe_mode == 8) {
        SetLastError(ERROR_PROC_NOT_FOUND);
        return NULL;
    }
    return (FARPROC)(void (*)(void))probe_generate;
}

/**
 * Release one simulated DLL reference while perturbing ambient last-error.
 *
 * @param module Simulated reference that must be released exactly once.
 * @return False for the selected cleanup failure, otherwise true after recording release.
 */
BOOL WINAPI entropy_probe_free(HMODULE module) {
    assert(module == (HMODULE)(uintptr_t)1 && probe_releases == 0);
    probe_releases++;
    SetLastError(ERROR_INVALID_HANDLE);
    return probe_mode == 12 ? 0 : TRUE;
}
#elif defined(__linux__) || defined(__FreeBSD__) || defined(__NetBSD__)

/**
 * Inject bounded native transfers, short results, and saved errno failures.
 *
 * @param buf Writable temporary chunk owned by the entropy adapter.
 * @param count Positive bounded request length.
 * @param flags Required GRND_NONBLOCK flag without insecure/random options.
 * @return Native transfer count, anomalous count, or minus one with saved errno.
 */
ssize_t entropy_probe_getrandom(void *buf, size_t count, unsigned int flags) {
    assert(flags == GRND_NONBLOCK);
    if ((probe_mode == 4 || probe_mode == 11) && probe_calls == 0) count = 7;
    if (probe_fill(buf, count)) {
        errno = (int)entropy_probe_error();
        return -1;
    }
    if (probe_mode == 5) return 0;
    if (probe_mode == 6) return (ssize_t)count + 1;
    return (ssize_t)count;
}
#else

/**
 * Inject bounded all-or-fail native entropy calls and saved errno failures.
 *
 * @param buf Writable temporary chunk owned by the entropy adapter.
 * @param count Positive bounded request length.
 * @return Zero on full success, or minus one with the configured errno.
 */
int entropy_probe_getentropy(void *buf, size_t count) {
    if (probe_fill(buf, count)) {
        errno = (int)entropy_probe_error();
        return -1;
    }
    return 0;
}
#endif
