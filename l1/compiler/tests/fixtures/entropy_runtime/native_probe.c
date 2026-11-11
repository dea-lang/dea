/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "entropy_faults.h"
#include <assert.h>
#include "dea_rt_entropy.c"

#if defined(DEA_ENTROPY_SIMULATE_WINDOWS)
DWORD entropy_simulated_last_error;
#endif

/**
 * Verify the initialized prefix and unchanged bytes outside that prefix.
 *
 * @param buf Test storage initialized to the sentinel byte.
 * @param size Full storage size including range guards.
 * @param count Successfully completed prefix after the leading guard.
 */
static void check_bytes(const unsigned char *buf, int size, int count) {
    assert(buf[0] == 0xa5);
    for (int i = 0; i < count; i++) assert(buf[i + 1] == (unsigned char)(i % 251));
    for (int i = count + 1; i < size; i++) assert(buf[i] == 0xa5);
}

/**
 * Exercise native entropy adapters against deterministic host-call failures.
 *
 * @return Zero after chunking, exact progress, error capture, and loader checks.
 */
int main(void) {
    unsigned char buffer[702];
    struct __deaM3sys2osS10RtIoResult result;
    entropy_probe_config(1);
    result = rt_entropy_fill((void *)(uintptr_t)1, 0);
    assert(result.state == DEA_IO_OK && result.count == 0 && entropy_probe_calls() == 0);
    result = rt_entropy_fill(NULL, 1);
    assert(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    result = rt_entropy_fill(NULL, -1);
    assert(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    assert(entropy_probe_calls() == 0 && entropy_probe_releases() == 0);
    assert(entropy_probe_loads() == 0 && entropy_probe_lookups() == 0);
    const int sizes[] = {1, 255, 256, 257, 700};
    for (unsigned int i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
        memset(buffer, 0xa5, sizeof(buffer));
        entropy_probe_config(0);
        result = rt_entropy_fill(buffer + 1, sizes[i]);
        assert(result.state == DEA_IO_OK && result.count == sizes[i]);
        assert(entropy_probe_calls() == (sizes[i] + 255) / 256);
        check_bytes(buffer, (int)sizeof(buffer), sizes[i]);
    }
    for (int mode = 1; mode <= 3; mode++) {
        memset(buffer, 0xa5, sizeof(buffer));
        entropy_probe_config(mode);
        result = rt_entropy_fill(buffer + 1, 700);
        assert(result.state == DEA_IO_FAILED && result.count == (mode == 2 ? 256 : 0));
        assert(entropy_probe_calls() == (mode == 2 ? 2 : 1));
        assert(result.error.domain == entropy_probe_domain());
        assert(result.error.native_code == entropy_probe_error());
        assert(result.error.kind == (mode == 3 ?
#if defined(_WIN32)
            DEA_OS_ERROR_INVALID_INPUT
#else
            DEA_OS_ERROR_INTERRUPTED
#endif
            : DEA_OS_ERROR_PERMISSION_DENIED));
        check_bytes(buffer, (int)sizeof(buffer), result.count);
#if defined(_WIN32)
        assert(entropy_probe_releases() == 1);
#endif
    }
#if defined(_WIN32)
    for (int mode = 12; mode <= 13; mode++) {
        memset(buffer, 0xa5, sizeof(buffer));
        entropy_probe_config(mode);
        result = rt_entropy_fill(buffer + 1, 700);
        assert(result.state == DEA_IO_FAILED && result.count == 0 && entropy_probe_calls() == 1);
        assert(result.error.domain == DEA_OS_DOMAIN_NTSTATUS && result.error.native_code == entropy_probe_error());
        assert(result.error.kind == (mode == 12 ? DEA_OS_ERROR_PERMISSION_DENIED : DEA_OS_ERROR_OTHER));
        assert(entropy_probe_releases() == 1);
        assert(entropy_probe_loads() == 1 && entropy_probe_lookups() == 1);
        check_bytes(buffer, (int)sizeof(buffer), 0);
    }
    for (int mode = 7; mode <= 8; mode++) {
        memset(buffer, 0xa5, sizeof(buffer));
        entropy_probe_config(mode);
        result = rt_entropy_fill(buffer + 1, 700);
        assert(result.state == DEA_IO_FAILED && result.count == 0);
        assert(result.error.domain == DEA_OS_DOMAIN_WIN32);
        assert(result.error.native_code == entropy_probe_error());
        assert(entropy_probe_calls() == 0 && entropy_probe_releases() == (mode == 8 ? 1 : 0));
        assert(entropy_probe_loads() == 1 && entropy_probe_lookups() == (mode == 8 ? 1 : 0));
        check_bytes(buffer, (int)sizeof(buffer), 0);
    }
#elif defined(__linux__) || defined(__FreeBSD__) || defined(__NetBSD__)
    memset(buffer, 0xa5, sizeof(buffer));
    entropy_probe_config(4);
    result = rt_entropy_fill(buffer + 1, 700);
    assert(result.state == DEA_IO_OK && result.count == 700 && entropy_probe_calls() == 4);
    check_bytes(buffer, (int)sizeof(buffer), 700);
    memset(buffer, 0xa5, sizeof(buffer));
    entropy_probe_config(11);
    result = rt_entropy_fill(buffer + 1, 700);
    assert(result.state == DEA_IO_FAILED && result.count == 7 && entropy_probe_calls() == 2);
    assert(result.error.kind == DEA_OS_ERROR_PERMISSION_DENIED);
    assert(result.error.domain == DEA_OS_DOMAIN_ERRNO && result.error.native_code == entropy_probe_error());
    check_bytes(buffer, (int)sizeof(buffer), 7);
    for (int mode = 5; mode <= 6; mode++) {
        memset(buffer, 0xa5, sizeof(buffer));
        entropy_probe_config(mode);
        result = rt_entropy_fill(buffer + 1, 700);
        assert(result.state == DEA_IO_FAILED && result.count == 0 && entropy_probe_calls() == 1);
        assert(result.error.kind == DEA_OS_ERROR_IO_ERROR && result.error.domain == DEA_OS_DOMAIN_RUNTIME);
        check_bytes(buffer, (int)sizeof(buffer), 0);
    }
    for (int mode = 9; mode <= 10; mode++) {
        entropy_probe_config(mode);
        result = rt_entropy_fill(buffer + 1, 700);
        assert(result.state == DEA_IO_FAILED && result.count == 0 && entropy_probe_calls() == 1);
        assert(result.error.kind == (mode == 9 ? DEA_OS_ERROR_WOULD_BLOCK : DEA_OS_ERROR_UNSUPPORTED));
        assert(result.error.domain == DEA_OS_DOMAIN_ERRNO && result.error.native_code == entropy_probe_error());
    }
#endif
    struct __deaM3sys2osS9RtOsError status_error = {
        DEA_OS_ERROR_OTHER, DEA_OS_DOMAIN_NTSTATUS, UINT32_C(0xc1234567)};
    dea_string message = rt_os_error_message(status_error);
    assert(strstr(_rt_string_bytes(message), "NtStatus error 3240314215") != NULL);
    _rt_free_string(message);
    puts("entropy native adapters: PASS");
    return 0;
}
