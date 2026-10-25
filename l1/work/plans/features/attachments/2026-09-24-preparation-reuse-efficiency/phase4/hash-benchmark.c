/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file hash-benchmark.c Experiment-local backend and stable-reader measurement harness.
 */
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

#ifdef HASH_HEADER
#include HASH_HEADER
#endif
#ifdef HASH_PLATFORM
#define L1_PREPARATION_SHA256_H
#ifdef __APPLE__
#include <CommonCrypto/CommonDigest.h>
typedef CC_SHA256_CTX PcSha;
#else

/**
 * OpenSSL's public opaque EVP interface; experiment links its existing shared library.
 */
typedef struct evp_md_ctx_st EVP_MD_CTX;
typedef struct evp_md_st EVP_MD;
typedef struct engine_st ENGINE;

/* Allocate an OpenSSL digest context. */
extern EVP_MD_CTX *EVP_MD_CTX_new(void);

/* Release an OpenSSL digest context. */
extern void EVP_MD_CTX_free(EVP_MD_CTX *ctx);

/* Select the OpenSSL SHA-256 digest implementation. */
extern const EVP_MD *EVP_sha256(void);

/* Initialize an OpenSSL digest context. */
extern int EVP_DigestInit_ex(EVP_MD_CTX *ctx, const EVP_MD *type, ENGINE *engine);

/* Append bytes to an OpenSSL digest context. */
extern int EVP_DigestUpdate(EVP_MD_CTX *ctx, const void *data, size_t count);

/* Finalize an OpenSSL digest into caller-owned output. */
extern int EVP_DigestFinal_ex(EVP_MD_CTX *ctx, unsigned char *digest, unsigned int *length);
typedef struct { EVP_MD_CTX *context; } PcSha;
#endif

/**
 * Initialize the experiment's platform digest context.
 *
 * @param s Caller-owned streaming SHA-256 state to update.
 */
static void pc_sha_init(PcSha *s) {
#ifdef __APPLE__
    if (!CC_SHA256_Init(s)) abort();
#else
    s->context = EVP_MD_CTX_new();
    if (!s->context || !EVP_DigestInit_ex(s->context, EVP_sha256(), NULL)) abort();
#endif
}

/**
 * Feed a complete chunk without changing the production stable reader.
 *
 * @param s Caller-owned streaming SHA-256 state to update.
 * @param data Borrowed readable input byte span.
 * @param n Number of bytes to process.
 */
static void pc_sha_update(PcSha *s, const void *data, size_t n) {
#ifdef __APPLE__
    if (n > UINT32_MAX || !CC_SHA256_Update(s, data, (CC_LONG)n)) abort();
#else
    if (!EVP_DigestUpdate(s->context, data, n)) abort();
#endif
}

/**
 * Render platform digest bytes using the same lowercase hexadecimal encoding.
 *
 * @param s Caller-owned streaming SHA-256 state to update.
 * @param hex Caller-owned 65-byte buffer for a NUL-terminated lowercase SHA-256 digest.
 */
static void pc_sha_finish(PcSha *s, char hex[65]) {
    static const char digits[] = "0123456789abcdef";
    unsigned char digest[32];
    size_t i;
#ifdef __APPLE__
    if (!CC_SHA256_Final(digest, s)) abort();
#else
    unsigned int length;
    if (!EVP_DigestFinal_ex(s->context, digest, &length) || length != 32) abort();
    EVP_MD_CTX_free(s->context);
#endif
    for (i = 0; i < sizeof(digest); ++i) {
        hex[2 * i] = digits[digest[i] >> 4];
        hex[2 * i + 1] = digits[digest[i] & 15];
    }
    hex[64] = 0;
}

/**
 * Hash one span through the experiment's platform implementation.
 *
 * @param data Borrowed readable input byte span.
 * @param n Number of bytes to process.
 * @param hex Caller-owned 65-byte buffer for a NUL-terminated lowercase SHA-256 digest.
 */
static void pc_sha_bytes(const void *data, size_t n, char hex[65]) {
    PcSha sha;
    pc_sha_init(&sha);
    pc_sha_update(&sha, data, n);
    pc_sha_finish(&sha, hex);
}
#endif
#ifdef HASH_READER_CHECKS
static int reader_mode;
static unsigned reader_calls;
static const char *reader_path;

/**
 * Inject clean short reads, an I/O failure, or an in-read content change.
 *
 * @param data Caller-owned writable destination span for the requested items.
 * @param size Requested item size in bytes.
 * @param count Number of elements in the supplied collection.
 * @param file Open file stream whose position is managed by this operation.
 * @return Number of complete items actually read under the selected injected behavior.
 */
static size_t checked_fread(void *data, size_t size, size_t count, FILE *file) {
    size_t n;
    if (reader_mode == 1 && reader_calls) return 0;
    if ((reader_mode == 1 || reader_mode == 3) && count > 7) count = 7;
    n = fread(data, size, count, file);
    if (reader_mode == 2 && !reader_calls) {
        FILE *changed = fopen(reader_path, "ab");
        if (!changed || fputc('x', changed) == EOF || fclose(changed)) abort();
    }
    ++reader_calls;
    return n;
}

/**
 * Preserve a deterministic error after the injected partial read.
 *
 * @param file Open file stream whose position is managed by this operation.
 * @return Nonzero when a real or injected read failure is active.
 */
static int checked_ferror(FILE *file) {
    return (reader_mode == 1 && reader_calls) || ferror(file);
}
#define fread checked_fread
#define ferror checked_ferror
#endif
#ifndef PREPARATION_SUPPORT
#define PREPARATION_SUPPORT "../../../../../../compiler/support/preparation_support.c"
#endif
#include PREPARATION_SUPPORT
#undef fread
#undef ferror

typedef struct {
    const char *name;
    size_t fixed;
} ChunkMode;

static const ChunkMode chunk_modes[] = {
    {"65536", 65536},
    {"64", 64},
    {"irregular", 0},
};

/**
 * Exit with a diagnostic when an experiment invariant fails.
 *
 * @param condition Predicate required to hold for the fixture.
 * @param message Borrowed diagnostic text.
 */
static void require(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "sha256 benchmark: %s\n", message);
        exit(1);
    }
}

/**
 * Return a monotonic wall-clock timestamp in seconds.
 * @return Monotonic clock value in seconds.
 */
static double wall_seconds(void) {
    struct timespec value;
    require(clock_gettime(CLOCK_MONOTONIC, &value) == 0, "cannot read monotonic clock");
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

/**
 * Return process CPU time in seconds.
 * @return Process CPU time in seconds.
 */
static double cpu_seconds(void) {
    struct timespec value;
    require(clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0, "cannot read process CPU clock");
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

/**
 * Load one regular file before timing the in-memory operation.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param length Number of input elements or bytes, as appropriate.
 * @return Owned file bytes, or NULL if file loading fails.
 */
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

/**
 * Feed bytes using one fixed or cyclic irregular division.
 *
 * @param sha Caller-owned streaming SHA-256 state to update.
 * @param data Borrowed readable input byte span.
 * @param length Number of input elements or bytes, as appropriate.
 * @param mode Requested access or processing mode.
 */
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

/**
 * Emit standard short known-answer vectors.
 */
static void emit_standard_vectors(void) {
    static const char *vectors[] = {
        "", "abc", "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    };
    size_t i;
    for (i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        char digest[65];
        pc_sha_bytes(vectors[i], strlen(vectors[i]), digest);
        printf("{\"kind\":\"standard-vector\",\"index\":%zu,\"digest\":\"%s\"}\n", i, digest);
    }
}

/**
 * Emit deterministic boundary and streaming-vector digests.
 */
static void emit_vectors(void) {
    static const size_t sizes[] = {0, 3, 55, 56, 63, 64, 65, 129, 1000000};
    static const size_t divisions[] = {1, 7, 31, 64, 65};
    unsigned char *allocation = malloc(1000002);
    require(allocation != NULL, "cannot allocate vector input");
    size_t case_index, i;
    for (i = 0; i < 1000002; ++i)
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
    free(allocation);
}

/**
 * Emit one common timing record.
 *
 * @param operation Borrowed name of the measured or failed native operation.
 * @param path Borrowed NUL-terminated filesystem path.
 * @param mode Requested access or processing mode.
 * @param iteration Repetition index reported with this measurement.
 * @param bytes Requested byte count.
 * @param wall Measured elapsed wall time.
 * @param cpu Measured process CPU time.
 * @param digest Caller-owned 65-byte buffer for a NUL-terminated SHA-256 digest.
 * @param checksum Hash checksum retained to make measured work observable.
 * @param production_ms Measured production-path elapsed time in milliseconds.
 */
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

/**
 * Measure SHA-256 after loading the complete file outside the timed span.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param mode Requested access or processing mode.
 * @param repetitions Number of measurement repetitions.
 */
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

/**
 * Measure sequential fread while consuming every byte in a checked FNV-1a checksum.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param repetitions Number of measurement repetitions.
 */
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

/**
 * Measure the complete production stable-file hash.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param repetitions Number of measurement repetitions.
 */
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

#ifdef HASH_READER_CHECKS

/**
 * Verify stable-reader success and conservative rejection independently of backend speed.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 */
static void check_reader(const char *path) {
    unsigned char data[129];
    char expected[65], digest[65];
    int mode;
    size_t i;
    for (i = 0; i < sizeof(data); ++i) data[i] = (unsigned char)(i * 131u + 17u);
    pc_sha_bytes(data, sizeof(data), expected);
    reader_path = path;
    for (mode = 0; mode < 4; ++mode) {
        PcJson *metadata = NULL;
        FILE *file = fopen(path, "wb");
        int64_t bytes = -1;
        int result;
        require(file != NULL && fwrite(data, 1, sizeof(data), file) == sizeof(data), "write reader fixture");
        require(fclose(file) == 0, "close reader fixture");
        reader_mode = mode;
        reader_calls = 0;
        memset(digest, 'z', 64);
        digest[64] = 0;
        result = pc_hash_file_measured(path, digest, &metadata, &bytes, NULL);
        if (mode == 0 || mode == 3) {
            require(result && metadata && bytes == 129 && !strcmp(digest, expected), "stable or clean short read");
        } else {
            require(!result && !metadata && bytes > 0 && digest[0] == 'z', "failed or changed read rejected");
        }
        pj_free(metadata);
    }
    reader_mode = 0;
    require(remove(path) == 0, "remove reader fixture");
    require(!pc_hash_file_measured(path, digest, NULL, NULL, NULL), "missing read rejected");
    puts("{\"kind\":\"reader-checks\",\"stable\":true,\"short_read\":true,\"failed_read\":true,\"changed_read\":true,\"missing\":true}");
}

#endif

/**
 * Parse a positive repetition count.
 *
 * @param text Borrowed text to parse or caller-owned buffer receiving constructed text.
 * @return Validated positive repetition count, or the fixture failure sentinel for invalid input.
 */
static int repetitions_from(const char *text) {
    char *end = NULL;
    long value;
    errno = 0;
    value = strtol(text, &end, 10);
    require(!errno && end && !*end && value > 0 && value <= 20, "invalid repetitions");
    return (int)value;
}

/**
 * Measure supported SHA-256 and stable-read candidates against the production path.
 *
 * @param argc Number of process argument words.
 * @param argv Borrowed NUL-terminated process argument vector.
 * @return Zero when all requested checks succeed; nonzero on a fixture failure.
 */
int main(int argc, char **argv) {
    size_t i;
    if (argc == 2 && !strcmp(argv[1], "vectors")) {
        emit_standard_vectors();
        emit_vectors();
        return 0;
    }
#ifdef HASH_READER_CHECKS
    if (argc == 3 && !strcmp(argv[1], "reader-checks")) {
        check_reader(argv[2]);
        return 0;
    }
#endif
    require(argc == 4 || argc == 5, "usage: benchmark vectors | reader-checks PATH | OP PATH [MODE] REPETITIONS");
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
