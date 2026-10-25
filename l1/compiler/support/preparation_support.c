/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file preparation_support.c Compiler-private native preparation and command ownership.
 */
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
#include "preparation/construction.h"
#include "preparation/build.h"
#include "installation.h"

/**
 * Establish a profile only under per-key coordination or a command-owned private directory.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero after starting the selected owned profile; zero after recording a preparation failure.
 */
static int pc_begin_profile(PcContext *c) {
    char *entry, *marker;
    PcJson *inputs;
    int ok = 1;
    if ((!c->lock && !c->private_root) || !c->native)
        return pc_fail(c, 2152, "native preparation requires coordination or a command-private workspace", NULL);
    entry = c->private_root ? pc_string(c->private_root) : pc_entry_path(c->local, c->native_key);
    if (!pc_mkdirs(entry)) { pc_fail(c, 2150, "cannot create preparation profile", entry); free(entry); return 0; }
    marker = pc_join(entry, "manifest.json");
    if (pc_kind(marker, 0) != 0 && remove(marker) != 0)
        ok = pc_fail(c, 2150, "cannot invalidate selected profile", marker);
    free(marker);
    inputs = pc_construction_inputs(c, pj_field(pj_get(c->native, "runtime"), "variant"));
    if (ok) ok = pc_begin_construction(c, inputs, entry);
    pj_free(inputs);
    if (ok) { free(c->selected); c->selected = entry; c->begun = 1; }
    else free(entry);
    return ok;
}

/**
 * Publish an already validated payload using the unchanged managed completion contract.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero after validated atomic publication; zero after retaining the first completion failure.
 */
static int pc_complete_profile(PcContext *c) {
    PcJson *manifest;
    char *marker, *pending;
    int ok = 1;
    if (!c->begun || !c->selected || (!c->lock && !c->private_root))
        return pc_fail(c, 2152, "completion requires active preparation", NULL);
    if (!c->construction || (!c->construction->inventory && !pc_finish_construction(c))) return 0;
    marker = pc_join(c->selected, "manifest.json");
    pending = pc_join(c->selected, ".manifest.pending");
    manifest = pj_new(PJ_OBJECT);
    pj_set_number(manifest, "schema", 1);
    pj_set_string(manifest, "kind", "native");
    pj_set_string(manifest, "key", c->native_key);
    pj_set_string(manifest, "D", c->dea_key);
    pj_add(manifest, "identity", pj_clone(c->native));
    pj_set_string(manifest, "compiler_description", c->description ? c->description : "");
    pj_add(manifest, "artifacts", pj_clone(c->construction->inventory));
    if (ok) ok = pc_preparation_inputs_current(c);
    if (ok && pc_kind(pending, 0) != 0 && remove(pending) != 0)
        ok = pc_fail(c, 2150, "cannot establish pending completion manifest", pending);
    if (ok && !pc_write_json(pending, manifest)) ok = pc_fail(c, 2150, "cannot write completion manifest", pending);
    if (ok) ok = pc_validate_entry_manifest(c, c->selected, 1, ".manifest.pending") == 1;

    /* Atomic publication makes a killed/in-progress writer an incomplete miss,
       and ensures readers never mistake a partial record for completed corruption. */
    if (ok && rename(pending, marker) != 0) ok = pc_fail(c, 2150, "cannot publish completion manifest", marker);
    if (!ok) remove(pending);
    pj_free(manifest); free(marker); free(pending);
    c->begun = 0;
    return ok;
}

/**
 * Create a lazy context; semantic-only consumers never resolve native identity or storage.
 *
 * @param data Borrowed readable input byte span.
 * @param length Number of input elements or bytes, as appropriate.
 * @return Owned lazy preparation context released with l1c_prep_free, including after configuration
 * failure.
 */
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
#include "preparation/profile.h"

/**
 * Release the command's allocations, OS lock and any fresh private native support.
 *
 * @param context Owned preparation context to destroy; NULL is a no-op.
 */
void l1c_prep_free(void *context) {
    PcContext *c = context;
    if (!c) return;
    pc_unlock(c->lock);
    pc_profile_cleanup(c);
    pc_construction_free(c->construction);
    if (c->private_root) pc_remove_owned_tree(c->private_root);
    pc_clang_isolation_free(c);
    pj_free(c->config); pj_free(c->options); pj_free(c->runtime_options); pj_free(c->dea); pj_free(c->native);
    pj_free(c->old_files); pj_free(c->new_files); pj_free(c->digest_donor); pj_free(c->legacy_configuration);
    pj_free(c->profile); pj_free(c->profile_headers);
    free(c->profile_stage); free(c->profile_destination);
    free(c->digest_seed_key);
    free(c->local); free(c->home); free(c->compiler); free(c->self); free(c->semantic_root); free(c->include);
    free(c->dea_key); free(c->native_key); free(c->selected); free(c->error); free(c->description);
    free(c->family); free(c->archiver); free(c->private_root); free(c->ineligible); free(c->unusable); free(c);
}

/**
 * Resolve native preparation identity and retain any context diagnostic.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One on success; zero for an invalid context or resolution failure.
 */
int32_t l1c_prep_resolve(void *context) {
    PcContext *c = context;
    double started = pc_observation_start(c);
    int result = c && !c->error ? pc_resolve_native(c) : 0;
    if (c && c->force)
        pc_observe_decision(c, "native-profile", "miss", "force", NULL);
    if (c) pc_observe_span(c, "native-identity-resolution", started, result);
    return result;
}

/**
 * Return a validated hit (1), ordinary miss (0), unusable completion (2), or error (-1).
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One for a validated hit, zero for an ordinary miss, two for unusable completion, or -1 for
 * error.
 */
int32_t l1c_prep_find(void *context) {
    PcContext *c = context;
    double started = pc_observation_start(c);
    int result = c && !c->error ? pc_find_profile(c) : -1;
    if (c) pc_observe_span(c, "profile-validation", started, result >= 0);
    return result;
}

/**
 * Acquire per-profile coordination for a resolved preparation context.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One on success; zero for invalid state or a recorded lock failure.
 */
int32_t l1c_prep_lock(void *context) {
    PcContext *c = context;
    double started = pc_observation_start(c);
    int result = c && !c->error ? pc_acquire_profile(c) : 0;
    if (c) pc_observe_span(c, "profile-lock-wait", started, result);
    return result;
}

/**
 * Release per-profile coordination and invalidate active construction state.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 */
void l1c_prep_unlock(void *context) {
    PcContext *c = context;
    if (c) {
        pc_unlock(c->lock); c->lock = NULL; c->begun = 0;
        if (c->construction) c->construction->active = 0;
    }
}

/**
 * Allocate fresh support for this consuming command, without publishing persistent state.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One after establishing private support, or zero for invalid state or a recorded allocation
 * failure.
 */
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

/**
 * Begin native construction under the selected profile ownership.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One on success; zero for invalid state or a recorded construction failure.
 */
int32_t l1c_prep_begin(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_begin_profile(c) : 0;
}

/**
 * Validate and publish the completed native profile under coordination.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One on success; zero for invalid state or a recorded publication failure.
 */
int32_t l1c_prep_complete(void *context) {
    PcContext *c = context;
    double started = pc_observation_start(c);
    int result = c && !c->error ? pc_complete_profile(c) : 0;
    if (c) pc_observe_span(c, "native-publication", started, result);
    return result;
}

/**
 * Internal direct constructor entry: inputs are normalized and destination is already owned.
 * No toolchain defaults, cache roots, reuse identities, locks or publication are resolved here.
 * The returned context owns its descriptions, never the caller's directory, even on failure.
 *
 * @param data Borrowed readable input byte span.
 * @param length Number of input elements or bytes, as appropriate.
 * @param destination Borrowed native byte span with an explicit length; no terminator is required.
 * @param destination_length Number of readable destination path bytes.
 * @return Owned context released with l1c_prep_free, including after a recorded construction failure.
 */
void *l1c_prep_construction_create(const uint8_t *data, int32_t length,
                                  const uint8_t *destination, int32_t destination_length) {
    PcContext *c = pc_alloc(sizeof(*c));
    char *root = NULL;
    c->config = pj_new(PJ_OBJECT);
    c->old_files = pj_new(PJ_OBJECT); c->new_files = pj_new(PJ_OBJECT);
    if (data && length >= 0 && destination && destination_length >= 0 &&
        !memchr(destination, 0, (size_t)destination_length)) {
        PcJson *inputs = pj_parse((const char *)data, (size_t)length);
        root = pc_slice((const char *)destination, (size_t)destination_length);
        pc_begin_construction(c, inputs, root);
        pj_free(inputs);
    } else pc_fail(c, 2151, "invalid construction inputs or destination", NULL);
    free(root);
    return c;
}

/**
 * Finish payload validation without writing a managed manifest or publication memo.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return One after complete payload validation; zero for invalid state or a recorded validation failure.
 */
int32_t l1c_prep_construction_complete(void *context) {
    PcContext *c = context;
    return c && !c->error ? pc_finish_construction(c) : 0;
}

/**
 * Read the saved preparation diagnostic code.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @return Saved code, zero if no failure is saved, or 2150 for a null context.
 */
int32_t l1c_prep_error_code(void *context) {
    PcContext *c = context;
    return c ? c->error_code : 2150;
}

/**
 * Copy context values into caller-owned spans; a null output queries the byte length.
 *
 * @param context Borrowed preparation context created by the matching constructor.
 * @param field Borrowed field name or bounded field-name bytes.
 * @param field_length Number of field-name bytes.
 * @param output Caller-owned writable output span, or NULL for a length query.
 * @param capacity Writable output capacity in bytes.
 * @return Byte length without a NUL terminator, including zero for empty, unknown, or unavailable fields;
 * -1 for invalid input, an unrepresentable length, or insufficient nonnull output capacity.
 */
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
    } else if (!strncmp(key, "profile_", 8)) value = pc_profile_get(c, key, &owned);
    else if (!strcmp(key, "dea_identity") && c->dea) owned = pj_encode(c->dea);
    else if (!strcmp(key, "native_identity") && c->native) owned = pj_encode(c->native);
    else if (!strcmp(key, "native_inventory") && c->native) {
        PcJson *j = pc_expected_artifacts(c->native);
        if (j) { owned = pj_encode(j); pj_free(j); }
    } else if (!strncmp(key, "construction_", 13) && c->construction) {
        PcConstruction *p = c->construction;
        const char *field = key + 13;
        if (!strcmp(field, "root")) value = p->root;
        else if (!strcmp(field, "inputs")) owned = pj_encode(p->inputs);
        else if (!strcmp(field, "inventory") && p->inventory) owned = pj_encode(p->inventory);
        else if (!strcmp(field, "option_count")) {
            PcBuffer count = {0};
            char number[32];
            snprintf(number, sizeof(number), "%lu", (unsigned long)pj_count(pj_get(p->inputs, "options")));
            pc_text(&count, number); owned = pc_take(&count);
        } else if (!strncmp(field, "option_", 7)) {
            const PcJson *option = pj_get(p->inputs, "options");
            int index = atoi(field + 7);
            option = option ? option->child : NULL;
            while (option && index-- > 0) option = option->next;
            value = pj_str(option);
        } else if (!strncmp(field, "codegen_", 8)) {
            value = pj_is_number(pj_get(pj_get(p->inputs, "codegen"), field + 8), 1) ? "1" : "0";
        } else value = pj_field(p->inputs, field);
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
