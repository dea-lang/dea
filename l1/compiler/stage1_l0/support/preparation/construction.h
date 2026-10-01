/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file construction.h Payload construction in a caller-owned staging directory. */
#ifndef L1_PREPARATION_CONSTRUCTION_H
#define L1_PREPARATION_CONSTRUCTION_H

/** Remove registered scratch without following aliases or ignoring failures. */
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

/** Release only the description; the policy caller retains the destination and recovery evidence. */
static void pc_construction_free(PcConstruction *p) {
    if (!p) return;
    pj_free(p->inputs); pj_free(p->expected); pj_free(p->inventory);
    free(p->root); free(p);
}

/** Read a required, frozen construction string without consulting command or cache defaults. */
static const char *pc_construction_field(const PcConstruction *p, const char *name) {
    return pj_field(p->inputs, name);
}

/** Refuse an aliased parent before creating any output directories outside the owned root. */
static int pc_construction_directory(PcContext *c, const PcConstruction *p, const char *path) {
    char *canonical = pc_canonical_future(path);
    int safe = canonical && pc_within(canonical, p->root);
    free(canonical);
    if (!safe) return pc_fail(c, 2150, "artifact directory escapes owned staging root", path);
    if (!pc_mkdirs(path)) return pc_fail(c, 2150, "cannot create artifact directory", path);
    return 1;
}

/** Validate explicit inputs before authorizing writes to the supplied owned directory. */
static int pc_begin_construction(PcContext *c, const PcJson *inputs, const char *destination) {
    static const char *const strings[] = {
        "compiler", "family", "variant", "home", "semantic_root", "include", NULL};
    static const char *const arrays[] = {"options", "runtime_options", NULL};
    PcConstruction *p = pc_alloc(sizeof(*p));
    const PcJson *item, *interfaces, *modules, *codegen;
    int i, ok = 1;
    pc_construction_free(c->construction);
    c->construction = p;
    if (!inputs || inputs->type != PJ_OBJECT)
        return pc_fail(c, 2151, "invalid construction inputs", NULL);
    p->inputs = pj_clone(inputs);
    for (i = 0; strings[i]; ++i) {
        const char *value = pc_construction_field(p, strings[i]);
        if (!value || !*value) return pc_fail(c, 2151, "missing construction input", strings[i]);
    }
    for (i = 0; arrays[i]; ++i) {
        const PcJson *words = pj_get(inputs, arrays[i]);
        if (!words || words->type != PJ_ARRAY)
            return pc_fail(c, 2151, "construction options require an ordered array", arrays[i]);
        for (item = words->child; item; item = item->next)
            if (!pj_str(item)) return pc_fail(c, 2151, "construction options require strings", arrays[i]);
    }
    codegen = pj_get(inputs, "codegen");
    if (!codegen || codegen->type != PJ_OBJECT)
        return pc_fail(c, 2151, "construction requires frontend settings", NULL);
    for (item = codegen->child; item; item = item->next)
        if (!pj_is_number(item, 0) && !pj_is_number(item, 1))
            return pc_fail(c, 2151, "construction frontend settings require boolean numbers", item->key);
    if (strcmp(pc_construction_field(p, "family"), "tcc") &&
        (!pj_field(inputs, "archiver") || !*pj_field(inputs, "archiver")))
        return pc_fail(c, 2154, "construction requires a resolved runtime archiver", NULL);
    modules = pj_get(inputs, "modules");
    interfaces = pj_get(inputs, "interfaces");
    p->expected = pc_payload_artifacts(modules, pc_construction_field(p, "family"),
                                      pc_construction_field(p, "variant"));
    if (!p->expected || !interfaces || interfaces->type != PJ_OBJECT ||
        pj_count(interfaces) != pj_count(modules))
        return pc_fail(c, 2151, "invalid construction semantic inventory", NULL);
    for (item = p->expected->child; item; item = item->next)
        if (!strcmp(item->text, "interface") && !pc_hex_digest(pj_field(interfaces, item->key)))
            return pc_fail(c, 2151, "construction requires verified semantic inputs", item->key);
    p->root = destination ? pc_path_call(destination, l1c_fs_canonical_existing_path) : NULL;
    if (!p->root || pc_kind(p->root, 0) != 2)
        return pc_fail(c, 2150, "construction requires an owned staging directory", destination);
    /* These are the only registered scratch trees. Keep generated C as optional
       debugging evidence, including on failure; the owner decides when to remove it. */
    {
        static const char *const scratch[] = {"generated", "runtime-build", NULL};
        for (i = 0; scratch[i] && ok; ++i) {
            char *path = pc_join(p->root, scratch[i]);
            if (!pc_remove_owned_tree(path)) ok = pc_fail(c, 2150, "cannot reset preparation scratch", path);
            free(path);
        }
    }
    for (item = p->expected->child; item && ok; item = item->next) {
        char *path = pc_join(p->root, item->key), *parent = pc_parent(path);
        ok = pc_construction_directory(c, p, parent);
        free(path); free(parent);
    }
    p->active = ok;
    return ok;
}

/** Produce an owned payload inventory without serializing or publishing managed metadata. */
static int pc_finish_construction(PcContext *c) {
    PcConstruction *p = c->construction;
    PcJson *inventory;
    const PcJson *item;
    int ok = 1;
    if (!p || !p->active) return pc_fail(c, 2152, "payload completion requires active construction", NULL);
    inventory = pj_new(PJ_ARRAY);
    for (item = p->expected->child; item && ok; item = item->next) {
        char *path = pc_join(p->root, item->key);
        char *canonical = pc_path_call(path, l1c_fs_canonical_existing_path);
        char digest[65];
        PcJson *metadata = NULL, *record;
        if (!canonical || !pc_within(canonical, p->root) || pc_kind(path, 1) != 1 ||
            !pc_hash_observed(c, path, digest, &metadata, "publication", "completion-inventory"))
            ok = pc_fail(c, 2153, "cannot validate prepared artifact", path);
        else if (!strcmp(item->text, "interface") &&
                 strcmp(digest, pj_field(pj_get(p->inputs, "interfaces"), item->key)))
            ok = pc_fail(c, 2153, "prepared interface differs from selected semantic input", path);
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
    p->active = 0;
    if (ok) p->inventory = inventory;
    else pj_free(inventory);
    return ok;
}

/** Build exact argv from the immutable invocation inputs, with distinct runtime options. */
static PcJson *pc_construction_words(const PcConstruction *p, int runtime) {
    PcJson *words = pj_new(PJ_ARRAY);
    const PcJson *option;
    pj_add(words, NULL, pj_string(pc_construction_field(p, "compiler")));
    for (option = pj_get(p->inputs, runtime ? "runtime_options" : "options")->child;
         option; option = option->next)
        pj_add(words, NULL, pj_clone(option));
    return words;
}
#endif
