/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file permission_probe.c
 * Inaccessible objects must fail rather than compare unequal.
 */
#include "dea_rt.h"
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "permission line %d: %s\n", __LINE__, #x); return 1; } } while (0)

/**
 * Borrow a host path for one operation.
 *
 * @param s NUL-terminated fixture path bytes borrowed for the operation.
 * @return A non-owning Dea string valid while s remains alive.
 */
static dea_string text(const char *s) { return (dea_string)DEA_STRING_CONST((char *)s, (dea_int)strlen(s)); }

/**
 * Exercise inaccessible followed identities in both operand positions.
 *
 * @param argc Number of command-line arguments, including the executable name.
 * @param argv Argument vector containing the Python-owned fixture paths.
 * @return Zero if every probe passes, otherwise one.
 */
int main(int argc, char **argv) {
    REQUIRE(argc == 3);
    struct __deaM3sys2fsS8RtFsBool result = rt_fs_same_file(text(argv[1]), text(argv[2]));
    REQUIRE(!result.ok && result.error.kind == DEA_OS_ERROR_PERMISSION_DENIED);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_ERRNO && result.error.native_code == EACCES);
    result = rt_fs_same_file(text(argv[2]), text(argv[1]));
    REQUIRE(!result.ok && result.error.kind == DEA_OS_ERROR_PERMISSION_DENIED);
    REQUIRE(!rt_fs_metadata(text(argv[2]), 1).ok);
    REQUIRE(!rt_dir_open(text(argv[2])).ok);
    return 0;
}
