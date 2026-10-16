#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

"""Verify the compiler-private monotonic clock ABI under strict C99."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from compiler_filesystem_support_test import compile_harness, resolve_c_compiler


def main() -> int:
    """Check real monotonic readings and unchanged output on invalid calls.

    Returns:
        Zero after all direct ABI assertions pass.

    Raises:
        AssertionError: If strict-C99 harness compilation fails.
        subprocess.CalledProcessError: If a native clock assertion fails.
    """
    source_text = r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>

int32_t l1c_timing_monotonic(uint8_t *output, int32_t capacity);

int main(void) {
    int32_t previous[2], current[2];
    uint8_t short_output[8], original[8];
    int i;
    memset(short_output, 0xa5, sizeof(short_output));
    memcpy(original, short_output, sizeof(original));
    if (l1c_timing_monotonic(NULL, 8) != 0 ||
        l1c_timing_monotonic(short_output, -1) != 0 ||
        l1c_timing_monotonic(short_output, 7) != 0 ||
        memcmp(short_output, original, sizeof(original)) != 0) return 1;
    if (l1c_timing_monotonic((uint8_t *)previous, sizeof(previous)) != 1) return 2;
    for (i = 0; i < 1000; ++i) {
        if (l1c_timing_monotonic((uint8_t *)current, sizeof(current)) != 1 ||
            current[0] < 0 || current[1] < 0 || current[1] >= 1000000000 ||
            current[0] < previous[0] ||
            (current[0] == previous[0] && current[1] < previous[1])) return 3;
        memcpy(previous, current, sizeof(previous));
    }
    puts("compiler timing ABI: monotonic fields and invalid-buffer preservation passed");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="l1-compiler-timing-") as directory:
        root = Path(directory)
        source = root / "clock.c"
        source.write_text(source_text)
        output = root / ("clock.exe" if os.name == "nt" else "clock")
        compile_harness(resolve_c_compiler(), source, output)
        subprocess.run([str(output)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
