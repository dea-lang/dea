/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file preparation_digest_seed_test.c Disposable donor evidence and fallback regressions. */
#include "../support/preparation_support.c"

static const char *seed_key = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static const char *donor_key = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
static const char *current_key = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";

/** Fail a named invariant independently of assertion flags. */
static void check(int ok, const char *name) {
    if (!ok) { fprintf(stderr, "digest seed fixture: %s\n", name); exit(1); }
}

/** Create an invocation with only the storage and digest state under test. */
static PcContext *context(const char *root, int verbosity) {
    PcContext *c = pc_alloc(sizeof(*c));
    c->config = pj_new(PJ_OBJECT);
    pj_set_number(c->config, "verbosity", verbosity);
    c->local = pc_string(root);
    c->writable = 1;
    c->digest_seed_key = pc_string(seed_key);
    c->old_files = pj_new(PJ_OBJECT);
    c->new_files = pj_new(PJ_OBJECT);
    return c;
}

/** Require the selected digest and whether file hashing was necessary. */
static void digest(PcContext *c, const char *path, const char *expected, int reads) {
    char *actual = pc_input_digest(c, path, "toolchain-input");
    check(actual && !strcmp(actual, expected), "correct file content digest");
    check(c->identity_reads == reads && !c->error, "optional evidence never fails preparation");
    free(actual);
}

/** Write a hint through the production versioned JSON representation. */
static void hint(const char *path, const char *key, int schema) {
    PcJson *j = pj_new(PJ_OBJECT);
    pj_set_number(j, "schema", schema);
    pj_set_string(j, "kind", "input-digest-seed");
    pj_set_string(j, "memo_key", key);
    check(pc_write_json(path, j), "hint write");
    pj_free(j);
}

int main(int argc, char **argv) {
    PcContext *c;
    PcJson *donor, *discovery, *changed, *record;
    char *path, *hint_path, *donor_path, *current_path, *actual;
    const char *rejection;
    char expected[65], modified[65];
    int i, verbosity;
    check(argc == 2, "fixture root");
    path = pc_join(argv[1], "input");
    check(pc_write_file(path, "abc", 3), "input write");
    pc_sha_bytes("abc", 3, expected);
    pc_sha_bytes("changed", 7, modified);
    c = context(argv[1], 0);
    digest(c, path, expected, 1);
    discovery = pj_new(PJ_OBJECT); /* Deliberately unusable discovery: only files may be donated. */
    pc_save_input_memo(c, donor_key, discovery);
    hint_path = pc_memo_path(c, "digest-seeds", seed_key, 0);
    donor_path = pc_memo_path(c, "toolchains", donor_key, 0);
    current_path = pc_memo_path(c, "toolchains", current_key, 0);
    donor = pc_read_json_status(donor_path, NULL);
    check(donor != NULL, "saved donor");
    l1c_prep_free(c);

    /* Equal metadata is insufficient when the filesystem cannot supply reliable evidence. */
    changed = pj_clone(donor);
    record = pj_get(pj_get(changed, "files"), path);
    pj_get(pj_get(record, "metadata"), "reliable")->number = 0;
    rejection = pc_digest_rejection(record, pj_get(record, "metadata"));
    check(rejection && !strcmp(rejection, "metadata-unreliable"),
          "equal unreliable metadata cannot authorize digest reuse");
    pj_free(changed);

    for (verbosity = 0; verbosity <= 3; ++verbosity) {
        c = context(argv[1], verbosity);
        digest(c, path, expected, 0);
        check(c->digest_seed_loaded && c->digest_donor, "one donor loaded");
        /* Removing the donor after loading does not affect the copied record. */
        check(remove(donor_path) == 0, "donor removed");
        pc_save_input_memo(c, current_key, discovery);
        l1c_prep_free(c);
        c = context(argv[1], verbosity);
        pc_load_input_memo(c, current_key, "toolchain-input-memo");
        digest(c, path, expected, 0);
        check(!c->digest_seed_loaded, "current memo avoids hint lookup");
        l1c_prep_free(c);
        check(pc_write_json(donor_path, donor), "restore donor");
        hint(hint_path, donor_key, 1);
    }
    /* Rejected hints must not even load a donor, and a late hint is not retried. */
    for (i = 0; i < 5; ++i) {
        if (i == 0) check(remove(hint_path) == 0, "hint removed");
        if (i == 1) check(pc_write_file(hint_path, "{", 1), "broken hint");
        if (i == 2) hint(hint_path, donor_key, 99);
        if (i == 3) hint(hint_path, "../../outside", 1);
        if (i == 4) {
            check(remove(hint_path) == 0 && pc_mkdirs(hint_path), "nonregular hint");
        }
        c = context(argv[1], 3);
        digest(c, path, expected, 1);
        check(!c->digest_donor, "bad hint ignored");
        if (i == 4) check(pc_remove_owned_tree(hint_path), "remove hint directory");
        hint(hint_path, donor_key, 1);
        check(!pc_digest_seed_files(c), "no repeated lookup after a miss");
        l1c_prep_free(c);
    }
    for (i = 0; i < 7; ++i) {
        changed = pj_clone(donor);
        record = pj_get(pj_get(changed, "files"), path);
        if (i == 0) check(remove(donor_path) == 0, "deleted donor");
        if (i == 1) check(pc_write_file(donor_path, "{", 1), "broken donor");
        if (i == 2) pj_get(changed, "schema")->number = 99;
        if (i == 3) pj_get(changed, "files")->type = PJ_ARRAY;
        if (i == 4) { free(pj_get(record, "sha256")->text); pj_get(record, "sha256")->text = pc_string("bad"); }
        if (i == 5) ++pj_get(pj_get(record, "metadata"), "inode")->number;
        if (i == 6) pj_get(pj_get(record, "metadata"), "reliable")->number = 0;
        if (i >= 2) check(pc_write_json(donor_path, changed), "invalid donor write");
        c = context(argv[1], 3);
        digest(c, path, expected, 1);
        l1c_prep_free(c); pj_free(changed);
        check(pc_write_json(donor_path, donor), "restore valid donor");
    }
    c = context(argv[1], 3);
    c->force = 1;
    digest(c, path, expected, 1);
    check(!c->digest_seed_loaded, "force skips hint");
    l1c_prep_free(c);
    c = context(argv[1], 3);
    pc_decline(c, "fixture ineligible");
    digest(c, path, expected, 1);
    check(!c->digest_seed_loaded, "ineligible skips hint");
    l1c_prep_free(c);

    /* A stale current record may fall back to a valid donor. */
    c = context(argv[1], 3);
    record = pj_clone(pj_get(pj_get(donor, "files"), path));
    ++pj_get(pj_get(record, "metadata"), "inode")->number;
    pj_add(c->old_files, path, record);
    digest(c, path, expected, 0);
    l1c_prep_free(c);
    check(remove(path) == 0 && pc_write_file(path, "changed", 7), "replace selected file");
    c = context(argv[1], 3);
    digest(c, path, modified, 1);
    /* Hint publication failure is ignored after successful memo publication. */
    check(remove(hint_path) == 0 && pc_mkdirs(hint_path), "block hint publication");
    pc_save_input_memo(c, current_key, discovery);
    check(!c->error, "failed hint write ignored");
    check(pc_remove_owned_tree(hint_path), "unblock hint");
    hint(hint_path, donor_key, 1);
    check(remove(current_path) == 0 && pc_mkdirs(current_path), "block memo publication");
    pc_save_input_memo(c, current_key, discovery);
    changed = pc_read_json_status(hint_path, NULL);
    check(!strcmp(pj_field(changed, "memo_key"), donor_key), "failed memo save leaves hint unchanged");
    pj_free(changed);
    check(remove(path) == 0, "remove actual input");
    actual = pc_input_digest(c, path, "toolchain-input");
    check(!actual && c->error_code == 2151, "actual input failure retains diagnostic");
    l1c_prep_free(c);
    pj_free(donor); pj_free(discovery);
    free(path); free(hint_path); free(donor_path); free(current_path);
    return 0;
}
