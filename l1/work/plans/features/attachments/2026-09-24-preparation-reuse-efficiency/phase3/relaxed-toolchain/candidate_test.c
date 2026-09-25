/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file candidate_test.c Isolated Linux experiment boundaries and accepted stale-digest limitation. */
#include "../support/preparation_support.c"

/** Require a named experimental invariant. */
static void check(int ok, const char *name) {
    if (!ok) { fprintf(stderr, "candidate fixture: %s\n", name); exit(1); }
}
/** Construct a digest record from complete metadata. */
static PcJson *record(const PcJson *metadata, const char *digest) {
    PcJson *r = pj_new(PJ_OBJECT);
    pj_set_string(r, "sha256", digest);
    pj_add(r, "metadata", pj_clone(metadata));
    return r;
}
/** Exercise the actual input-digest path with a selected category. */
static void input(const char *path, const PcJson *old, const char *category,
                  int force, int reads, const char *digest) {
    PcContext *c = pc_alloc(sizeof(*c));
    char *actual;
    PcJson *now;
    c->config = pj_new(PJ_OBJECT);
    c->old_files = pj_new(PJ_OBJECT);
    c->new_files = pj_new(PJ_OBJECT);
    c->force = force;
    if (old) pj_add(c->old_files, path, pj_clone(old));
    actual = pc_input_digest(c, path, category);
    check(actual && !strcmp(actual, digest), "expected digest");
    check(c->identity_reads == reads, "expected number of stable reads");
    now = pc_meta(path);
    check(pj_equal(pj_get(pj_get(c->new_files, path), "metadata"), now),
          "save current complete metadata on hit or hash");
    pj_free(now); free(actual); l1c_prep_free(c);
}
/** Build valid discovery evidence, then prove dependency and selected-file checks stay strict. */
static void discovery(const char *path, const PcJson *metadata, const char *digest) {
    const char *text = "{\"schema\":1,\"version\":\"fixture\",\"dependencies\":{},\"paths\":{},"
                       "\"toolchain\":{\"family\":\"tcc\",\"invocation\":\"tcc\",\"target\":\"fixture\"}}";
    PcJson *d = pj_parse(text, strlen(text)), *memo = pj_new(PJ_OBJECT), *files = pj_new(PJ_OBJECT);
    PcJson *stamp = pj_clone(metadata);
    PcContext *c = pc_alloc(sizeof(*c));
    char *seal;
    c->config = pj_new(PJ_OBJECT);
    pj_set_number(pj_get(d, "paths"), path, 1);
    pj_set_string(pj_get(d, "toolchain"), "target_macros", digest);
    pj_set_string(pj_get(d, "toolchain"), "runtime_target_macros", digest);
    pj_add(pj_get(d, "dependencies"), path, stamp);
    pj_add(files, path, record(metadata, digest));
    pj_add(memo, "files", files); pj_add(memo, "discovery", d);
    seal = pc_json_digest(d); pj_set_string(memo, "discovery_digest", seal); free(seal);
    check(pc_discovery_current(c, memo), "valid discovery hit");
    ++pj_get(stamp, "inode")->number;
    seal = pc_json_digest(d); free(pj_get(memo, "discovery_digest")->text);
    pj_get(memo, "discovery_digest")->text = seal;
    check(!pc_discovery_current(c, memo), "dependency inode still rejects discovery");
    --pj_get(stamp, "inode")->number;
    seal = pc_json_digest(d); free(pj_get(memo, "discovery_digest")->text);
    pj_get(memo, "discovery_digest")->text = seal;
    check(pc_discovery_current(c, memo), "restored dependency validates");
    ++pj_get(pj_get(pj_get(files, path), "metadata"), "inode")->number;
    check(!pc_discovery_current(c, memo), "selected-file inode still rejects discovery");
    pj_free(memo); l1c_prep_free(c);
}
int main(int argc, char **argv) {
    const char *ignored[] = {"device", "inode", "ctime", "ctime_ns"};
    const char *retained[] = {"size", "mode", "mtime", "mtime_ns", "reliable"};
    char *path, original[65], changed[65], stable[65];
    PcJson *now, *old, *copy, *minimal, *other;
    struct stat before;
    struct timespec times[2], delay = {0, 10000000};
    size_t i;
    check(argc == 2, "fixture root");
    path = pc_join(argv[1], "selected-input");
    check(pc_write_file(path, "abc", 3), "write original");
    pc_sha_bytes("abc", 3, original); pc_sha_bytes("xyz", 3, changed);
    now = pc_meta(path); old = record(now, original);
    for (i = 0; i < sizeof(ignored) / sizeof(*ignored); ++i) {
        copy = pj_clone(old);
        ++pj_get(pj_get(copy, "metadata"), ignored[i])->number;
        check(!pc_experimental_digest_rejection(copy, now, 1), "ignored field permits eligible reuse");
        check(pc_experimental_digest_rejection(copy, now, 0) != NULL, "other categories strict");
        input(path, copy, "toolchain-input", 0, 0, original);
        input(path, copy, "dea-input", 0, 1, original);
        input(path, copy, "toolchain-input", 1, 1, original);
        pj_free(copy);
    }
    for (i = 0; i < sizeof(retained) / sizeof(*retained); ++i) {
        copy = pj_clone(old);
        ++pj_get(pj_get(copy, "metadata"), retained[i])->number;
        check(pc_experimental_digest_rejection(copy, now, 1) != NULL, "retained field rejects");
        input(path, copy, "toolchain-input", 0, 1, original);
        pj_free(copy);
    }
    for (i = 0; i < sizeof(ignored) / sizeof(*ignored); ++i) {
        copy = pj_clone(old);
        pj_get(pj_get(copy, "metadata"), ignored[i])->type = PJ_NULL;
        check(pc_experimental_digest_rejection(copy, now, 1) != NULL, "malformed ignored field rejects");
        input(path, copy, "toolchain-input", 0, 1, original);
        pj_free(copy);
    }
    minimal = pj_new(PJ_OBJECT); other = pj_new(PJ_OBJECT);
    check(pc_experimental_metadata_equal(minimal, other), "mutually absent timestamp fields equal");
    pj_set_number(minimal, "mtime_ns", 8289578); pj_set_number(other, "mtime_ns", 0);
    check(!pc_experimental_metadata_equal(minimal, other), "nonzero to zero is a mismatch");
    pj_add(minimal, "future", pj_new(PJ_NULL));
    check(!pc_experimental_metadata_equal(minimal, other), "absent versus explicit null differs");
    pj_get(other, "mtime_ns")->number = 8289578;
    check(!pc_experimental_metadata_equal(minimal, other), "union checks additional previous fields");
    check(!pc_experimental_metadata_equal(other, minimal), "union checks additional current fields");
    check(!pc_experimental_metadata_equal(NULL, now), "missing record rejects");
    pj_free(minimal); pj_free(other);
    copy = record(now, "invalid"); input(path, copy, "toolchain-input", 0, 1, original); pj_free(copy);
    copy = pj_new(PJ_OBJECT); pj_set_string(copy, "sha256", original);
    input(path, copy, "toolchain-input", 0, 1, original); pj_free(copy);
    copy = pj_clone(now); pj_get(copy, "reliable")->number = 0;
    check(pc_experimental_digest_rejection(old, copy, 1) != NULL, "unreliable current rejects");
    pj_free(copy);
    discovery(path, now, original);
    check(stat(path, &before) == 0, "stat before adversarial write");
    times[0] = before.st_atim; times[1] = before.st_mtim;
    nanosleep(&delay, NULL);
    check(pc_write_file(path, "xyz", 3), "same-size content mutation");
    check(utimensat(AT_FDCWD, path, times, 0) == 0, "restore full modification time");
    input(path, old, "toolchain-input", 0, 0, original);
    input(path, old, "dea-input", 0, 1, changed);
    check(pc_hash_file_measured(path, stable, NULL, NULL, NULL) && !strcmp(stable, changed),
          "stable read still hashes actual changed bytes");
    input(path, old, "toolchain-input", 1, 1, changed);
    check(remove(path) == 0, "remove selected input");
    check(pc_meta(path) == NULL, "missing metadata remains unavailable");
    pj_free(now); pj_free(old); free(path);
    puts("candidate predicate, discovery boundaries, refresh, force and preserved-mtime limitation: PASS");
    return 0;
}
