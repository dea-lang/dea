/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "dea_rt.h"
#include "probe_names.h"
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static dea_int left_calls;
static dea_int right_calls;
static dea_int value_calls;

/**
 * Count one left-operand evaluation independently of the other operands.
 *
 * @param value Runtime operand to preserve.
 * @return The supplied value.
 */
dea_int integer_boundary_left(dea_int value) {
    left_calls += 1;
    return value;
}

/**
 * Count one right-operand evaluation independently of the other operands.
 *
 * @param value Runtime operand to preserve.
 * @return The supplied value.
 */
dea_int integer_boundary_right(dea_int value) {
    right_calls += 1;
    return value;
}

/**
 * Count one unary-operand evaluation.
 *
 * @param value Runtime operand to preserve.
 * @return The supplied value.
 */
dea_int integer_boundary_value(dea_int value) {
    value_calls += 1;
    return value;
}

/**
 * Parse one signed argument without overflowing arithmetic in the caller.
 *
 * @param text Decimal argument known by the test matrix to fit its target type.
 * @return Its signed 64-bit value; exits with a harness error for invalid text.
 */
static dea_long signed_argument(const char *text) {
    char *end = NULL;
    errno = 0;
    long long value = strtoll(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fprintf(stderr, "invalid signed harness argument: %s\n", text);
        exit(2);
    }
    return (dea_long)value;
}

/**
 * Parse one unsigned argument without overflowing arithmetic in the caller.
 *
 * @param text Non-negative decimal argument within its target type's range.
 * @return Its unsigned 64-bit value; exits with a harness error for invalid text.
 */
static dea_ulong unsigned_argument(const char *text) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || *text == '-') {
        fprintf(stderr, "invalid unsigned harness argument: %s\n", text);
        exit(2);
    }
    return (dea_ulong)value;
}

/**
 * Check independent operand counters after successful generated operations.
 *
 * @return Zero when every operand is evaluated once, or a harness failure.
 */
static int check_single_evaluation(void) {
    if (left_once(3, 2) != 12 || left_calls != 1 || right_calls != 1) return 1;
    left_calls = right_calls = 0;
    if (right_once(-9, 2) != -3 || left_calls != 1 || right_calls != 1) return 1;
    if (neg_once(5) != -5 || value_calls != 1) return 1;
    puts("ok");
    return 0;
}

/**
 * Preserve floating-point negation and both signed-zero transitions.
 *
 * @return Zero when floating unary behavior is unchanged, or a harness failure.
 */
static int check_floating_negation(void) {
    if (neg_float(3.5f) != -3.5f || neg_double(-2.25) != 2.25) return 1;
    if (!signbit(neg_float(0.0f)) || signbit(neg_float(-0.0f))) return 1;
    if (!signbit(neg_double(0.0)) || signbit(neg_double(-0.0))) return 1;
    puts("ok");
    return 0;
}

#define SIGNED_UNARY(name, type) \
    if (strcmp(argv[1], #name) == 0) { \
        printf("%" PRId64 "\n", (int64_t)name((type)signed_argument(argv[2]))); return 0; \
    }
#define UNSIGNED_UNARY(name, type) \
    if (strcmp(argv[1], #name) == 0) { \
        printf("%" PRIu64 "\n", (uint64_t)name((type)unsigned_argument(argv[2]))); return 0; \
    }
#define SIGNED_SHIFT(name, type) \
    if (strcmp(argv[1], #name) == 0) { \
        printf("%" PRId64 "\n", (int64_t)name((type)signed_argument(argv[2]), \
            (type)signed_argument(argv[3]))); return 0; \
    }
#define UNSIGNED_SHIFT(name, type) \
    if (strcmp(argv[1], #name) == 0) { \
        printf("%" PRIu64 "\n", (uint64_t)name((type)unsigned_argument(argv[2]), \
            (type)unsigned_argument(argv[3]))); return 0; \
    }

/**
 * Dispatch a single runtime case from separately compiled generated Dea code.
 *
 * The caller only parses representable values and prints results. Expected
 * arithmetic is computed by Python, so failing boundary operations never run
 * in the C test oracle.
 *
 * @param argc Argument count.
 * @param argv Operation name and decimal runtime operands.
 * @return Zero after printing a result, or a harness error; Dea failures abort.
 */
int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "once") == 0) return check_single_evaluation();
    if (argc == 2 && strcmp(argv[1], "float") == 0) return check_floating_negation();
    if (argc != 4) return 2;
    SIGNED_UNARY(neg_tiny, dea_tiny)
    SIGNED_UNARY(neg_short, dea_short)
    SIGNED_UNARY(neg_int, dea_int)
    SIGNED_UNARY(neg_long, dea_long)
    UNSIGNED_UNARY(neg_byte, dea_byte)
    UNSIGNED_UNARY(neg_ushort, dea_ushort)
    UNSIGNED_UNARY(neg_uint, dea_uint)
    UNSIGNED_UNARY(neg_ulong, dea_ulong)
    SIGNED_SHIFT(left_int, dea_int)
    SIGNED_SHIFT(right_int, dea_int)
    SIGNED_SHIFT(left_long, dea_long)
    SIGNED_SHIFT(right_long, dea_long)
    UNSIGNED_SHIFT(left_uint, dea_uint)
    UNSIGNED_SHIFT(right_uint, dea_uint)
    UNSIGNED_SHIFT(left_ulong, dea_ulong)
    UNSIGNED_SHIFT(right_ulong, dea_ulong)
    if (strcmp(argv[1], "left_mixed_uint_int") == 0) {
        printf("%" PRId64 "\n", (int64_t)left_mixed_uint_int(
            (dea_uint)unsigned_argument(argv[2]), (dea_int)signed_argument(argv[3])));
    } else if (strcmp(argv[1], "right_mixed_uint_int") == 0) {
        printf("%" PRId64 "\n", (int64_t)right_mixed_uint_int(
            (dea_uint)unsigned_argument(argv[2]), (dea_int)signed_argument(argv[3])));
    } else if (strcmp(argv[1], "left_narrow") == 0) {
        printf("%" PRId64 "\n", (int64_t)left_narrow(
            (dea_tiny)signed_argument(argv[2]), (dea_short)signed_argument(argv[3])));
    } else if (strcmp(argv[1], "left_narrow_unsigned") == 0) {
        printf("%" PRId64 "\n", (int64_t)left_narrow_unsigned(
            (dea_byte)unsigned_argument(argv[2]), (dea_ushort)unsigned_argument(argv[3])));
    } else if (strcmp(argv[1], "left_mixed_ulong_byte") == 0) {
        printf("%" PRIu64 "\n", (uint64_t)left_mixed_ulong_byte(
            (dea_ulong)unsigned_argument(argv[2]), (dea_byte)unsigned_argument(argv[3])));
    } else {
        fprintf(stderr, "unknown harness operation: %s\n", argv[1]);
        return 2;
    }
    return 0;
}
