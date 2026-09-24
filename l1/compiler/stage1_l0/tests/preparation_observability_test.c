/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file preparation_observability_test.c Controlled accounting and memo rejection observations. */
#ifndef _WIN32
#define _XOPEN_SOURCE 700
#define _POSIX_C_SOURCE 200809L
#ifdef __APPLE__
#define _DARWIN_C_SOURCE 1
#endif
#endif
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif
#include "../support/preparation/json.h"

static int clock_calls, observation_allocations;
/** Count direct JSON allocations by observation builders. */
static PcJson *counted_json_new(int type) {
    ++observation_allocations;
    return pj_new(type);
}
#define pj_new counted_json_new
#ifdef _WIN32
static ULONGLONG controlled_ticks(void) { return (ULONGLONG)++clock_calls; }
#define GetTickCount64 controlled_ticks
#else
static int controlled_clock(clockid_t id, struct timespec *value) {
    (void)id;
    value->tv_sec = ++clock_calls / 1000;
    value->tv_nsec = (clock_calls % 1000) * 1000000;
    return 0;
}
#define clock_gettime controlled_clock
#endif
#include "../support/preparation_support.c"

/** Fail a named invariant independently of assertion compilation flags. */
static void check(int ok, const char *name) {
    if (!ok) { fprintf(stderr, "observability fixture: %s\n", name); exit(1); }
}

/** Create only the minimum sealed observation memo accepted by production validation. */
static PcJson *discovery_memo(const char *path, int with_digest) {
    PcJson *memo = pc_memo_create("identity"), *discovery = pj_new(PJ_OBJECT);
    PcJson *tc = pj_new(PJ_OBJECT), *paths = pj_new(PJ_OBJECT), *files = pj_new(PJ_OBJECT);
    PcJson *file = pj_new(PJ_OBJECT);
    char hex[65], *seal;
    pc_sha_bytes("target", 6, hex);
    pj_set_number(discovery, "schema", 1);
    pj_set_string(discovery, "version", "fixture");
    pj_add(discovery, "dependencies", pj_new(PJ_OBJECT));
    pj_set_string(paths, path, "input");
    pj_add(discovery, "paths", paths);
    pj_set_string(tc, "family", "tcc");
    pj_set_string(tc, "invocation", "fixture");
    pj_set_string(tc, "target", "fixture");
    pj_set_string(tc, "target_macros", hex);
    pj_set_string(tc, "runtime_target_macros", hex);
    pj_add(discovery, "toolchain", tc);
    pj_add(memo, "discovery", discovery);
    seal = pc_json_digest(discovery);
    pj_set_string(memo, "discovery_digest", seal);
    free(seal);
    pj_add(file, "metadata", pc_meta(path));
    if (with_digest) pj_set_string(file, "sha256", "invalid-digest");
    pj_add(files, path, file);
    pj_add(memo, "files", files);
    return memo;
}

int main(int argc, char **argv) {
    PcContext c = {0};
    PcJson *metadata = NULL, *previous, *memo, *words;
    PcProbe probe;
    char digest[65], quiet_digest[65], *path, *absent, *oversized;
    FILE *file;
    int status, verbosity;
    if (argc == 2 && !strcmp(argv[1], "--fail")) return 23;
    if (argc == 2 && !strcmp(argv[1], "--wait")) {
#ifdef _WIN32
        Sleep(10000);
#else
        sleep(10);
#endif
        return 0;
    }
    check(argc == 2, "fixture directory");
    path = pc_join(argv[1], "input");
    absent = pc_join(argv[1], "absent");
    oversized = pc_join(argv[1], "oversized");
    check(pc_write_file(path, "abc", 3), "input write");
    c.config = pj_new(PJ_OBJECT);
    pj_set_number(c.config, "verbosity", 0);
    for (verbosity = 0; verbosity < 3; ++verbosity) {
        pj_get(c.config, "verbosity")->number = verbosity;
        clock_calls = observation_allocations = 0;
        pc_observe_decision(&c, "test", "miss", "test", NULL);
        pc_observe_metadata_mismatch(&c, "test", path, NULL, NULL);
        pc_observe_span(&c, "quiet", pc_observation_start(&c), 1);
        check(!clock_calls && !observation_allocations, "quiet observation allocation/clock");
        check(pc_hash_observed(&c, path, quiet_digest, NULL, "dea-input", "test"), "quiet hash");
        check(!clock_calls, "quiet hash clock");
    }
    pj_get(c.config, "verbosity")->number = 3;
    clock_calls = 0;
    check(pc_hash_observed(&c, path, digest, &metadata, "dea-input", "test"), "debug hash");
    check(clock_calls == 2 && !strcmp(digest, quiet_digest), "hash accounting and digest identity");
    check(!pc_hash_observed(&c, absent, digest, NULL, "dea-input", "test"), "failed hash");
    previous = pj_clone(metadata);
    ++pj_get(previous, "inode")->number;
    pj_get(previous, "size")->number = 99;
    pc_observe_metadata_mismatch(&c, "test", "quote\"slash\\line\n", previous, metadata);
    pj_free(previous); pj_free(metadata);
    memo = discovery_memo(path, 1);
    check(!pc_discovery_current(&c, memo), "invalid digest rejected");
    pj_free(memo);
    memo = discovery_memo(path, 0);
    check(!pc_discovery_current(&c, memo), "missing digest rejected");
    pj_free(memo);
    check(!pc_read_json_status(absent, &status) && status == PC_JSON_ABSENT, "absent memo");
    check(!pc_read_json_status(argv[1], &status) && status == PC_JSON_MALFORMED, "nonregular memo");
    check(pc_write_file(path, "{bad", 4), "malformed memo write");
    check(!pc_read_json_status(path, &status) && status == PC_JSON_MALFORMED, "malformed memo");
    file = fopen(oversized, "wb");
    check(file != NULL && !fseek(file, 16 * 1024 * 1024, SEEK_SET) && fputc('x', file) != EOF,
          "oversized memo write");
    check(!fclose(file), "oversized memo close");
    check(!pc_read_json_status(oversized, &status) && status == PC_JSON_MALFORMED, "oversized memo");
    words = pj_new(PJ_ARRAY);
    pj_add(words, NULL, pj_string(argv[0])); pj_add(words, NULL, pj_string("--fail"));
    probe = pc_context_probe(&c, words, "failed fixture probe");
    check(probe.status == 23 && !probe.timed_out, "failed probe status");
    pc_probe_free(&probe);
    pj_set_number(c.config, "probe_timeout_ms", 1);
    words = pj_new(PJ_ARRAY);
    pj_add(words, NULL, pj_string(argv[0])); pj_add(words, NULL, pj_string("--wait"));
    probe = pc_context_probe(&c, words, "timed out fixture probe");
    check(probe.timed_out, "probe timeout");
    pc_probe_free(&probe);
    pj_free(c.config); free(path); free(absent); free(oversized);
    return 0;
}
