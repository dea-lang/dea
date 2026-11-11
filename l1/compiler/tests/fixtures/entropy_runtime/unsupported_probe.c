/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "dea_rt_entropy.c"
#include <assert.h>

/**
 * Verify unsupported hosts cannot silently substitute a fallback source.
 *
 * @return Zero after host-free empty success and unchanged positive failure.
 */
int main(void) {
    unsigned char bytes[3] = {0xa5, 0xa5, 0xa5};
    struct __deaM3sys2osS10RtIoResult result = rt_entropy_fill(NULL, 0);
    assert(result.state == DEA_IO_OK && result.count == 0);
    result = rt_entropy_fill(bytes + 1, 1);
    assert(result.state == DEA_IO_FAILED && result.count == 0);
    assert(result.error.kind == DEA_OS_ERROR_UNSUPPORTED);
    assert(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    assert(bytes[0] == 0xa5 && bytes[1] == 0xa5 && bytes[2] == 0xa5);
    puts("entropy native adapters: PASS");
    return 0;
}
