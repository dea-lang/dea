/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file benchmark.c Experiment-local SHA-256 and stable-reader measurement harness. */
#ifndef _WIN32
#define _XOPEN_SOURCE 700
#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#endif
#endif
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "../../../../../compiler/stage1_l0/support/preparation_support.c"

typedef struct {
    const char *name;
    size_t fixed;
} ChunkMode;

static const ChunkMode chunk_modes[] = {
    {"65536", 65536},
    {"64", 64},
    {"irregular", 0},
};

/** Exit with a diagnostic when an experiment invariant fails. */
static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "sha256 benchmark: %s\n", message);
        exit(1);
    }
}

/** Return a monotonic wall-clock timestamp in seconds. */
static double wall_seconds(void) {
    struct timespec value;
    require(clock_gettime(CLOCK_MONOTONIC, &value) == 0, "cannot read monotonic clock");
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

/** Return process CPU time in seconds. */
static double cpu_seconds(void) {
    struct timespec value;
    require(clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0, "cannot read process CPU clock");
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

/** Load one regular file before timing the in-memory operation. */
static unsigned char *load_file(const char *path, size_t *length) {
    struct stat info;
    FILE *file;
    unsigned char *allocation;
    require(stat(path, &info) == 0 && info.st_size >= 0, "cannot stat input");
    require((uint64_t)info.st_size <= (uint64_t)SIZE_MAX - 1, "input is too large");
    *length = (size_t)info.st_size;
    allocation = malloc(*length + 2);
    require(allocation != NULL, "cannot allocate input");
    file = fopen(path, "rb");
    require(file != NULL, "cannot open input");
    require(fread(allocation + 1, 1, *length, file) == *length, "cannot preload input");
    require(fclose(file) == 0, "cannot close input");
    allocation[0] = 0xa5;
    allocation[*length + 1] = 0x5a;
    return allocation;
}

/** Feed bytes using one fixed or cyclic irregular division. */
static void hash_stream(PcSha *sha, const unsigned char *data, size_t length, const ChunkMode *mode) {
    static const size_t irregular[] = {4093, 65521, 127, 8191};
    size_t offset = 0, index = 0;
    while (offset < length) {
        size_t amount = mode->fixed ? mode->fixed : irregular[index++ % 4];
        if (amount > length - offset)
            amount = length - offset;
        pc_sha_update(sha, data + offset, amount);
        offset += amount;
    }
}

/** Emit deterministic boundary and streaming-vector digests. */
static void emit_vectors(void) {
    static const size_t sizes[] = {0, 55, 56, 63, 64, 65, 129};
    static const size_t divisions[] = {1, 7, 31, 64, 65};
    unsigned char allocation[132];
    size_t case_index, i;
    for (i = 0; i < sizeof(allocation); ++i)
        allocation[i] = (unsigned char)((i * 131u + 17u) & 255u);
    for (case_index = 0; case_index < sizeof(sizes) / sizeof(sizes[0]); ++case_index) {
        PcSha sha;
        char digest[65];
        size_t length = sizes[case_index], offset = 0, division = 0;
        pc_sha_init(&sha);
        while (offset < length) {
            size_t amount = divisions[division++ % (sizeof(divisions) / sizeof(divisions[0]))];
            if (amount > length - offset)
                amount = length - offset;
            pc_sha_update(&sha, allocation + 1 + offset, amount);
            offset += amount;
        }
        pc_sha_finish(&sha, digest);
        printf("{\"kind\":\"vector\",\"bytes\":%zu,\"offset\":1,\"digest\":\"%s\"}\n",
               length, digest);
    }
}

/** Emit one common timing record. */
static void emit_measurement(const char *operation, const char *path, const char *mode, int iteration,
                             size_t bytes, double wall, double cpu, const char *digest,
                             uint64_t checksum, double production_ms) {
    printf("{\"kind\":\"measurement\",\"operation\":\"%s\",\"path\":\"%s\","
           "\"mode\":\"%s\",\"access\":\"%s\",\"iteration\":%d,\"bytes\":%zu,"
           "\"wall_ms\":%.6f,\"cpu_ms\":%.6f,\"digest\":%s,\"checksum\":%" PRIu64
           ",\"production_ms\":%.6f}\n",
           operation, path, mode, iteration ? "repeated" : "first", iteration, bytes, wall * 1000.0,
           cpu * 1000.0, digest ? digest : "null", checksum, production_ms);
}

/** Measure SHA-256 after loading the complete file outside the timed span. */
static void measure_memory(const char *path, const ChunkMode *mode, int repetitions) {
    size_t length;
    unsigned char *allocation = load_file(path, &length);
    int iteration;
    for (iteration = 0; iteration < repetitions; ++iteration) {
        PcSha sha;
        char digest[65], quoted[68];
        double wall_start = wall_seconds(), cpu_start = cpu_seconds();
        pc_sha_init(&sha);
        hash_stream(&sha, allocation + 1, length, mode);
        pc_sha_finish(&sha, digest);
        snprintf(quoted, sizeof(quoted), "\"%s\"", digest);
        emit_measurement("memory-sha256", path, mode->name, iteration, length,
                         wall_seconds() - wall_start, cpu_seconds() - cpu_start, quoted, 0, 0.0);
    }
    require(allocation[0] == 0xa5 && allocation[length + 1] == 0x5a, "unaligned buffer guard changed");
    free(allocation);
}

/** Measure sequential fread while consuming every byte in a checked FNV-1a checksum. */
static void measure_read(const char *path, int repetitions) {
    unsigned char buffer[65536];
    int iteration;
    for (iteration = 0; iteration < repetitions; ++iteration) {
        FILE *file = fopen(path, "rb");
        uint64_t checksum = UINT64_C(1469598103934665603);
        size_t n, total = 0, i;
        double wall_start, cpu_start;
        require(file != NULL, "cannot open read-only input");
        wall_start = wall_seconds();
        cpu_start = cpu_seconds();
        while ((n = fread(buffer, 1, sizeof(buffer), file)) > 0) {
            for (i = 0; i < n; ++i) {
                checksum ^= buffer[i];
                checksum *= UINT64_C(1099511628211);
            }
            total += n;
        }
        require(!ferror(file), "read-only operation failed");
        require(fclose(file) == 0, "cannot close read-only input");
        emit_measurement("fread-checksum", path, "65536", iteration, total,
                         wall_seconds() - wall_start, cpu_seconds() - cpu_start, NULL, checksum, 0.0);
    }
}

/** Measure the complete production stable-file hash. */
static void measure_stable(const char *path, int repetitions) {
    int iteration;
    for (iteration = 0; iteration < repetitions; ++iteration) {
        PcJson *metadata = NULL;
        char digest[65], quoted[68];
        int64_t bytes = 0;
        double production_ms = 0.0, wall_start = wall_seconds(), cpu_start = cpu_seconds();
        require(pc_hash_file_measured(path, digest, &metadata, &bytes, &production_ms),
                "stable hash failed");
        snprintf(quoted, sizeof(quoted), "\"%s\"", digest);
        emit_measurement("stable-hash", path, "65536", iteration, (size_t)bytes,
                         wall_seconds() - wall_start, cpu_seconds() - cpu_start, quoted, 0,
                         production_ms);
        pj_free(metadata);
    }
}

/** Parse a positive repetition count. */
static int repetitions_from(const char *text) {
    char *end = NULL;
    long value;
    errno = 0;
    value = strtol(text, &end, 10);
    require(!errno && end && !*end && value > 0 && value <= 20, "invalid repetitions");
    return (int)value;
}

int main(int argc, char **argv) {
    size_t i;
    if (argc == 2 && !strcmp(argv[1], "vectors")) {
        emit_vectors();
        return 0;
    }
    require(argc == 4 || argc == 5, "usage: benchmark vectors | OP PATH [MODE] REPETITIONS");
    if (!strcmp(argv[1], "memory")) {
        require(argc == 5, "memory requires a chunk mode");
        for (i = 0; i < sizeof(chunk_modes) / sizeof(chunk_modes[0]); ++i)
            if (!strcmp(argv[3], chunk_modes[i].name)) {
                measure_memory(argv[2], &chunk_modes[i], repetitions_from(argv[4]));
                return 0;
            }
        require(0, "unknown chunk mode");
    } else if (!strcmp(argv[1], "read")) {
        require(argc == 4, "read takes no chunk mode");
        measure_read(argv[2], repetitions_from(argv[3]));
    } else if (!strcmp(argv[1], "stable")) {
        require(argc == 4, "stable takes no chunk mode");
        measure_stable(argv[2], repetitions_from(argv[3]));
    } else {
        require(0, "unknown operation");
    }
    return 0;
}
