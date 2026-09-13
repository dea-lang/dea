/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file preparation_support.c Compiler-private native preparation and command ownership. */
#if !defined(_WIN32)
#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 700
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#endif
#endif
#include "preparation/json.h"
#include "preparation/sha256.h"
#include "preparation/platform.h"
#include "preparation/storage.h"
#include "preparation/identity.h"
#include "preparation/build.h"

/** Remove a known Dea-owned scratch tree without following aliases or ignoring failures. */
static int pc_remove_owned_tree(const char *root) {
    int kind = pc_kind(root, 0), ok = 1;
    PcJson *names;
    const PcJson *name;
    if (kind == 0) return 1;
    if (kind != 2) return remove(root) == 0;
    names = pc_list(root);
    if (!names) return 0;
    for (name = names->child; name && ok; name = name->next) {
        char *path = pc_join(root, name->text);
        ok = pc_remove_owned_tree(path);
        free(path);
    }
    pj_free(names);
    return ok && l1c_fs_remove_empty_dir((const uint8_t *)root, (int32_t)strlen(root)) == 1;
}
/** Establish a profile only under per-key coordination or a command-owned private directory. */
static int pc_begin_profile(PcContext *c) {
    char *entry, *marker;
    PcJson *expected;
    const PcJson *item;
    int ok = 1;
    if ((!c->lock && !c->private_root) || !c->native)
        return pc_fail(c, 2152, "native preparation requires coordination or a command-private workspace", NULL);
    entry = c->private_root ? pc_string(c->private_root) : pc_entry_path(c->local, c->native_key);
    if (!pc_mkdirs(entry)) { pc_fail(c, 2150, "cannot create preparation profile", entry); free(entry); return 0; }
    marker = pc_join(entry, "manifest.json");
    if (pc_kind(marker, 0) != 0 && remove(marker) != 0)
        ok = pc_fail(c, 2150, "cannot invalidate selected profile", marker);
    free(marker);
    /* Quoted generated-C includes must not select stale scratch headers. A forced
       or incomplete-profile rebuild starts with clean compiler-owned scratch. */
    {
        static const char *const names[] = {"generated", "runtime-build", NULL};
        int i;
        for (i = 0; names[i] && ok; ++i) {
            char *scratch = pc_join(entry, names[i]);
            if (!pc_remove_owned_tree(scratch))
                ok = pc_fail(c, 2150, "cannot reset preparation scratch", scratch);
            free(scratch);
        }
    }
    expected = pc_expected_artifacts(c->native);
    if (!expected) ok = pc_fail(c, 2151, "cannot derive native artifact roles", entry);
    for (item = expected ? expected->child : NULL; item && ok; item = item->next) {
        char *path = pc_join(entry, item->key), *parent = pc_parent(path);
        if (!pc_mkdirs(parent)) ok = pc_fail(c, 2150, "cannot create artifact directory", parent);
        free(path); free(parent);
    }
    pj_free(expected);
    if (ok) { free(c->selected); c->selected = entry; c->begun = 1; }
    else free(entry);
    return ok;
}
/** Hash every expected output and write the sole completion record last. */
static int pc_complete_profile(PcContext *c) {
    PcJson *manifest, *expected, *inventory;
    const PcJson *item;
    char *marker, *pending;
    int ok = 1;
    if (!c->begun || !c->selected || (!c->lock && !c->private_root))
        return pc_fail(c, 2152, "completion requires active preparation", NULL);
    expected = pc_expected_artifacts(c->native);
    if (!expected) return pc_fail(c, 2151, "invalid native preparation identity", NULL);
    marker = pc_join(c->selected, "manifest.json");
    pending = pc_join(c->selected, ".manifest.pending");
    manifest = pj_new(PJ_OBJECT);
    pj_set_number(manifest, "schema", 1);
    pj_set_string(manifest, "kind", "native");
    pj_set_string(manifest, "key", c->native_key);
    pj_set_string(manifest, "D", c->dea_key);
    pj_add(manifest, "identity", pj_clone(c->native));
    pj_set_string(manifest, "compiler_description", c->description ? c->description : "");
    inventory = pj_new(PJ_ARRAY);
    pj_add(manifest, "artifacts", inventory);
    for (item = expected->child; item && ok; item = item->next) {
        char *path = pc_join(c->selected, item->key);
        char *canonical = pc_path_call(path, l1c_fs_canonical_existing_path);
        char digest[65];
        PcJson *metadata = NULL, *record;
        if (!canonical || !pc_within(canonical, c->selected) || !pc_hash_file(path, digest, &metadata))
            ok = pc_fail(c, 2153, "cannot validate prepared artifact", path);
        else {
            record = pj_new(PJ_OBJECT);
            pj_set_string(record, "path", item->key);
            pj_set_string(record, "role", item->text);
            pj_set_number(record, "size", pj_get(metadata, "size")->number);
            pj_set_string(record, "sha256", digest);
            pj_add(inventory, NULL, record);
        }
        pj_free(metadata); free(canonical); free(path);
    }
    if (ok) ok = pc_preparation_inputs_current(c);
    if (ok && pc_kind(pending, 0) != 0 && remove(pending) != 0)
        ok = pc_fail(c, 2150, "cannot establish pending completion manifest", pending);
    if (ok && !pc_write_json(pending, manifest)) ok = pc_fail(c, 2150, "cannot write completion manifest", pending);
    if (ok) ok = pc_validate_entry_manifest(c, c->selected, 1, ".manifest.pending") == 1;
    /* Atomic publication makes a killed/in-progress writer an incomplete miss,
       and ensures readers never mistake a partial record for completed corruption. */
    if (ok && rename(pending, marker) != 0) ok = pc_fail(c, 2150, "cannot publish completion manifest", marker);
    if (!ok) remove(pending);
    pj_free(expected); pj_free(manifest); free(marker); free(pending);
    c->begun = 0;
    return ok;
}

/** Create a lazy context; semantic-only consumers never resolve native identity or storage. */
void *l1c_prep_create(const uint8_t *data, int32_t length) {
    PcContext *c = pc_alloc(sizeof(*c));
    const PcJson *option;
    PcJson *options;
    c->old_files = pj_new(PJ_OBJECT); c->new_files = pj_new(PJ_OBJECT);
    c->config = data && length >= 0 ? pj_parse((const char *)data, (size_t)length) : NULL;
    if (!c->config || c->config->type != PJ_OBJECT) {
        pc_fail(c, 2150, "invalid internal preparation configuration", NULL); return c;
    }
    {
        static const char *const fields[] = {"home", "self", "compiler", "cache", "build_dir", "variant", "runtime_include", NULL};
        int i;
        for (i = 0; fields[i]; ++i) {
            PcJson *value = pj_get(c->config, fields[i]);
            if (value && value->type != PJ_STRING) { pc_fail(c, 2150, "preparation field requires a string", fields[i]); return c; }
        }
    }
    options = pj_get(c->config, "options");
    if (options && options->type != PJ_ARRAY) { pc_fail(c, 2150, "native options must be an ordered array", NULL); return c; }
    c->options = options ? pj_clone(options) : pj_new(PJ_ARRAY);
    for (option = c->options->child; option; option = option->next)
        if (!pj_str(option)) { pc_fail(c, 2150, "native options must contain strings", NULL); return c; }
    c->force = pj_is_number(pj_get(c->config, "force"), 1);
    pc_toolchain_paths(c);
    return c;
}
/** Release the command's allocations, OS lock and any fresh private native support. */
void l1c_prep_free(void *context) {
    PcContext *c = context;
    if (!c) return;
    pc_unlock(c->lock);
    if (c->private_root) pc_remove_owned_tree(c->private_root);
    pj_free(c->config); pj_free(c->options); pj_free(c->runtime_options); pj_free(c->dea); pj_free(c->native);
    pj_free(c->old_files); pj_free(c->new_files);
    free(c->local); free(c->home); free(c->compiler); free(c->self); free(c->semantic_root); free(c->include);
    free(c->dea_key); free(c->native_key); free(c->selected); free(c->error); free(c->description);
    free(c->family); free(c->archiver); free(c->private_root); free(c->ineligible); free(c->unusable); free(c);
}
int32_t l1c_prep_resolve(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_resolve_native(c) : 0;
}
/** Return a validated hit (1), ordinary miss (0), unusable completion (2), or error (-1). */
int32_t l1c_prep_find(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_find_profile(c) : -1;
}
int32_t l1c_prep_lock(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_acquire_profile(c) : 0;
}
void l1c_prep_unlock(void *context) {
    PcContext *c = context;
    if (c) { pc_unlock(c->lock); c->lock = NULL; c->begun = 0; }
}
/** Allocate fresh support for this consuming command, without publishing persistent state. */
int32_t l1c_prep_private(void *context) {
    PcContext *c = context;
    char *path;
    if (!c || c->private_root || c->lock) return 0;
    /* A consuming command may recover from an unavailable implicit destination,
       including a failed lock/output directory beneath an otherwise writable v1. */
    if (c->error && !c->explicit_root && (c->error_code == 2150 || c->error_code == 2152)) {
        if (pc_verbosity(c) >= 1) fprintf(stderr, "Fresh preparation after unavailable default cache: %s\n", c->error);
        pc_clear_error(c); c->writable = 0;
    }
    if (c->error) return 0;
    path = pc_probe_directory();
    if (!path) return pc_fail(c, 2150, "cannot allocate private native preparation workspace", NULL);
    c->private_root = pc_path_call(path, l1c_fs_canonical_existing_path);
    free(path);
    return c->private_root != NULL;
}
int32_t l1c_prep_begin(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_begin_profile(c) : 0;
}
int32_t l1c_prep_complete(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_complete_profile(c) : 0;
}
int32_t l1c_prep_error_code(void *context) {
    PcContext *c = context;
    return c ? c->error_code : 2150;
}
/** Copy context values into caller-owned spans; a null output queries the byte length. */
int32_t l1c_prep_get(void *context, const uint8_t *field, int32_t field_length, uint8_t *output, int32_t capacity) {
    PcContext *c = context;
    char *key, *owned = NULL;
    const char *value = NULL;
    size_t n;
    if (!c || !field || field_length < 0 || memchr(field, 0, (size_t)field_length)) return -1;
    key = pc_slice((const char *)field, (size_t)field_length);
    if (!strcmp(key, "error")) value = c->error;
    else if (!strcmp(key, "local")) value = c->local;
    else if (!strcmp(key, "home")) value = c->home;
    else if (!strcmp(key, "semantic_root")) value = c->semantic_root;
    else if (!strcmp(key, "include")) value = c->include;
    else if (!strcmp(key, "dea_key")) value = c->dea_key;
    else if (!strcmp(key, "native_key")) value = c->native_key;
    else if (!strcmp(key, "selected")) value = c->selected;
    else if (!strcmp(key, "compiler")) value = c->compiler;
    else if (!strcmp(key, "family")) value = c->family;
    else if (!strcmp(key, "description")) value = c->description;
    else if (!strcmp(key, "ineligible")) value = c->ineligible;
    else if (!strcmp(key, "unusable")) value = c->unusable;
    else if (!strcmp(key, "explicit_root")) value = c->explicit_root ? "1" : "0";
    else if (!strcmp(key, "writable")) value = c->writable ? "1" : "0";
    else if (!strcmp(key, "target") && c->native) value = pj_field(pj_get(c->native, "toolchain"), "target");
    else if (!strcmp(key, "modules") && c->modules) {
        PcBuffer names = {0};
        const PcJson *module;
        for (module = c->modules->child; module; module = module->next) { pc_text(&names, module->key); pc_char(&names, '\n'); }
        owned = pc_take(&names);
    } else if (!strcmp(key, "dea_identity") && c->dea) owned = pj_encode(c->dea);
    else if (!strcmp(key, "native_identity") && c->native) owned = pj_encode(c->native);
    else if (!strcmp(key, "native_inventory") && c->native) {
        PcJson *j = pc_expected_artifacts(c->native);
        if (j) { owned = pj_encode(j); pj_free(j); }
    } else if (!strcmp(key, "stats")) {
        PcJson *j = pj_new(PJ_OBJECT);
        pj_set_number(j, "identity_content_reads", c->identity_reads);
        pj_set_number(j, "artifact_content_reads", c->artifact_reads);
        pj_set_number(j, "metadata_checks", c->metadata_checks);
        pj_set_number(j, "probes", c->probes);
        pj_set_number(j, "native_resolutions", c->resolutions);
        pj_set_number(j, "build_commands", c->build_commands);
        pj_set_number(j, "module_compiles", c->module_compiles);
        pj_set_number(j, "option_file_parses", c->option_file_parses);
        pj_set_number(j, "option_root_expansions", c->option_root_expansions);
        owned = pj_encode(j); pj_free(j);
    }
    free(key);
    if (owned) value = owned;
    if (!value) value = "";
    n = strlen(value);
    if (n > INT32_MAX || (output && (capacity < 0 || (size_t)capacity < n))) { free(owned); return -1; }
    if (output && n) memcpy(output, value, n);
    free(owned);
    return (int32_t)n;
}
