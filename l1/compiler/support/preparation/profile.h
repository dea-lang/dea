/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file profile.h Versioned caller-owned profiles, independent of managed discovery. */
#ifndef L1_PREPARATION_PROFILE_H
#define L1_PREPARATION_PROFILE_H

/* Bump the compilation contract for incompatible .l1m, generated-C, public-header,
   runtime, or module-lifecycle protocol changes. Producer identity is not a substitute. */
#define PC_PROFILE_SCHEMA 1
#define PC_PROFILE_CONTRACT 1
#define PC_PROFILE_MAX_WORDS 4096
#define PC_PROFILE_MAX_MODULES 4096
#define PC_PROFILE_MAX_PAYLOADS 16384
#define PC_PROFILE_MAX_MANIFEST (16 * 1024 * 1024)

/** Require an exact object vocabulary; the JSON reader already rejects duplicate keys. */
static int pc_profile_fields(const PcJson *object, const char *const *names) {
    const PcJson *field;
    if (!object || object->type != PJ_OBJECT) return 0;
    for (field = object->child; field; field = field->next) {
        int i;
        for (i = 0; names[i] && strcmp(field->key, names[i]); ++i) {}
        if (!names[i]) return 0;
    }
    return 1;
}

/** Recognize native absolute paths without testing external files or resolving aliases. */
static int pc_profile_absolute(const char *path) {
    if (!path || !*path) return 0;
#if defined(_WIN32)
    return (isalpha((unsigned char)path[0]) && path[1] == ':' && pc_separator(path[2])) ||
        (pc_separator(path[0]) && pc_separator(path[1]));
#else
    return path[0] == '/';
#endif
}

/** Bound argv and freeze supported path operands; opaque indirection is deliberately refused. */
static PcJson *pc_profile_options(PcContext *c, const PcJson *options, int frozen) {
    static const char *const path_flags[] = {
        "--config-system-dir", "--config-user-dir", "--gcc-toolchain", "-resource-dir",
        "--sysroot", "-isysroot", "-idirafter", "-iquote", "-isystem", "-imacros",
        "-include", "-I", "-L", "-B", "-F", "-iframework", NULL};
    const PcJson *word;
    PcJson *result = pj_new(PJ_ARRAY);
    if (!options || options->type != PJ_ARRAY || pj_count(options) > PC_PROFILE_MAX_WORDS) goto invalid;
    /* Drivers expand response words before interpreting option operands. Check
       every original argv word, including values later consumed by paired flags. */
    for (word = options->child; word; word = word->next) {
        const char *s = pj_str(word);
        if (!s || !*s || *s == '@' || strlen(s) > 32768) goto invalid;
    }
    for (word = options->child; word; word = word->next) {
        const char *s = pj_str(word), *operand = NULL, *flag = NULL;
        char *absolute;
        int i;
        if (!strncmp(s, "--config", 8) || !strncmp(s, "-specs", 6) ||
            !strncmp(s, "--specs", 7) || !strncmp(s, "-fplugin", 8) ||
            !strncmp(s, "-fpass-plugin", 13) || !strncmp(s, "-fprofile", 9) ||
            !strncmp(s, "-fauto-profile", 14) || !strcmp(s, "-wrapper") ||
            !strncmp(s, "-X", 2) || !strncmp(s, "-Wl,", 4) ||
            !strncmp(s, "-Wa,", 4) || !strncmp(s, "-Wp,", 4) ||
            !strcmp(s, "-mllvm") || !strncmp(s, "-ivfsoverlay", 12) ||
            !strncmp(s, "-o", 2) || !strncmp(s, "-M", 2) || !strncmp(s, "-save-temps", 11) ||
            !strncmp(s, "-dump", 5) || !strncmp(s, "-working-directory", 18) ||
            !strncmp(s, "-auxbase", 8) || !strncmp(s, "-aux-info", 9) ||
            !strcmp(s, "-c") || !strcmp(s, "-E") || !strcmp(s, "-S")) goto invalid;
        for (i = 0; path_flags[i]; ++i) {
            size_t length = strlen(path_flags[i]);
            if (!strcmp(s, path_flags[i])) {
                flag = path_flags[i]; word = word->next;
                operand = pj_str(word);
                break;
            }
            if (!strncmp(s, path_flags[i], length) && s[length]) {
                if (path_flags[i][1] == '-' && s[length] == '=') operand = s + length + 1;
                else if (length == 2 && path_flags[i][1] != '-') operand = s + length;
                else goto invalid;
                if (operand) { flag = path_flags[i]; break; }
            }
        }
        if (flag) {
            if (!operand || !*operand || *operand == '=' || !strncmp(operand, "$SYSROOT", 8) ||
                !strcmp(operand, "-") || strlen(operand) > 32768 ||
                (frozen && !pc_profile_absolute(operand))) goto invalid;
            absolute = frozen ? pc_string(operand) : pc_path_call(operand, l1c_fs_absolute_path);
            if (!absolute) goto invalid;
            if (!strcmp(flag, "--gcc-toolchain")) {
                PcBuffer joined = {0};
                pc_text(&joined, flag); pc_char(&joined, '='); pc_text(&joined, absolute);
                pj_add(result, NULL, pj_string(joined.s)); free(joined.s);
            } else {
                pj_add(result, NULL, pj_string(flag));
                pj_add(result, NULL, pj_string(absolute));
            }
            free(absolute);
            continue;
        }
        if (!strcmp(s, "-target") || !strcmp(s, "--target") || !strcmp(s, "-arch") ||
            !strcmp(s, "-D") || !strcmp(s, "-U")) {
            pj_add(result, NULL, pj_string(s)); word = word->next;
            s = pj_str(word);
            if (!s || !*s || strlen(s) > 32768) goto invalid;
            pj_add(result, NULL, pj_string(s));
            continue;
        }
        /* Definitions are data. Other unclassified path spellings cannot acquire
           invocation-directory semantics after the profile has moved. */
        if (!strncmp(s, "-i", 2) || *s != '-' || (strncmp(s, "-D", 2) && strncmp(s, "-U", 2) &&
            (strchr(s, '/') || strchr(s, '\\')))) goto invalid;
        if (strchr(s, '=') && strncmp(s, "-D", 2) && strncmp(s, "-U", 2)) {
            static const char *const value_flags[] = {
                "-std=", "--std=", "--target=", "-march=", "-mcpu=", "-mtune=", "-mabi=",
                "-mfpu=", "-mfloat-abi=", "-ffp-contract=", "-fexcess-precision=", "-fvisibility=", NULL};
            int known = 0;
            for (i = 0; value_flags[i]; ++i)
                if (!strncmp(s, value_flags[i], strlen(value_flags[i]))) { known = 1; break; }
            if (!known) goto invalid;
        }
        pj_add(result, NULL, pj_string(s));
    }
    if (pj_count(result) > PC_PROFILE_MAX_WORDS) goto invalid;
    for (word = result->child; word; word = word->next)
        if (strlen(word->text) > 32768) goto invalid;
    return result;
invalid:
    pj_free(result);
    pc_fail(c, frozen ? 2182 : 2180,
            "unsupported profile native option, relative path, or response/configuration indirection", NULL);
    return NULL;
}

/** Require the complete five-setting frontend configuration, without ambient defaults. */
static int pc_profile_codegen(const PcJson *codegen) {
    static const char *const fields[] = {
        "no_line_directives", "trace_arc", "trace_memory", "unchecked", "check_basic", NULL};
    int i;
    if (!pc_profile_fields(codegen, fields) || pj_count(codegen) != 5) return 0;
    for (i = 0; fields[i]; ++i)
        if (!pj_is_number(pj_get(codegen, fields[i]), 0) &&
            !pj_is_number(pj_get(codegen, fields[i]), 1)) return 0;
    {
        int unchecked = pj_is_number(pj_get(codegen, "unchecked"), 1),
            basic = pj_is_number(pj_get(codegen, "check_basic"), 1),
            trace = pj_is_number(pj_get(codegen, "trace_arc"), 1) || pj_is_number(pj_get(codegen, "trace_memory"), 1);
        return !((unchecked && basic) || ((unchecked || basic) && trace));
    }
}

/** Runtime support and generated checks must describe one configuration. */
static int pc_profile_variant(const PcJson *codegen, const char *variant) {
    const char *expected = pj_is_number(pj_get(codegen, "trace_arc"), 1) ||
        pj_is_number(pj_get(codegen, "trace_memory"), 1) ? "traced" :
        pj_is_number(pj_get(codegen, "unchecked"), 1) ? "unchecked" :
        pj_is_number(pj_get(codegen, "check_basic"), 1) ? "check_basic" : "default";
    return variant && !strcmp(expected, variant);
}

/** Record stable compiler-owned inputs without resolving a managed identity or memo. */
static int pc_profile_track(PcContext *c, const char *path) {
    PcJson *record = pj_new(PJ_OBJECT), *metadata = pc_meta(path);
    if (!metadata) { pj_free(record); return pc_fail(c, 2151, "cannot inspect profile construction input", path); }
    pj_add(record, "metadata", metadata);
    if (!pj_get(c->new_files, path)) pj_add(c->new_files, path, record);
    else pj_free(record);
    return 1;
}

/** Keep runtime sources and their local headers stable throughout construction. */
static int pc_profile_track_tree(PcContext *c, const char *root, int depth) {
    PcJson *names;
    const PcJson *name;
    int ok = depth <= 16 && pc_profile_track(c, root);
    names = ok ? pc_list(root) : NULL;
    ok = ok && names;
    if (!ok) { pj_free(names); return pc_fail(c, 2151, "cannot inspect profile runtime inputs", root); }
    for (name = names->child; name && ok; name = name->next) {
        char *path = pc_join(root, name->text);
        int kind = pc_kind(path, 0);
        if (kind == 2) ok = pc_profile_track_tree(c, path, depth + 1);
        else if (kind == 1) ok = pc_profile_track(c, path);
        else ok = pc_fail(c, 2151, "profile runtime inputs require ordinary files and directories", path);
        free(path);
    }
    pj_free(names);
    return ok;
}

/** Collect bundled module names only; no managed identity, roots, or memos are involved. */
static int pc_profile_modules(PcContext *c, const char *root, const char *relative, int depth) {
    char *directory = pc_join(root, relative);
    PcJson *names;
    const PcJson *name;
    int ok = depth <= 16 && pc_profile_track(c, directory);
    names = ok ? pc_list(directory) : NULL;
    ok = ok && names;
    free(directory);
    if (!ok) { pj_free(names); return pc_fail(c, 2151, "cannot enumerate bundled profile modules", root); }
    for (name = names->child; name && ok; name = name->next) {
        char *rel = *relative ? pc_join(relative, name->text) : pc_string(name->text);
        char *path = pc_join(root, rel);
        int kind = pc_kind(path, 0);
        if (kind == 2) ok = pc_profile_modules(c, root, rel, depth + 1);
        else if (kind == 1 && pc_ends(rel, ".l1")) {
            char *module = pc_slice(rel, strlen(rel) - 3), *p, *interface_path, *source;
            char digest[65];
            for (p = module; *p; ++p) if (*p == '/' || *p == '\\') *p = '.';
            interface_path = pc_module_artifact(module, ".l1m", "modules");
            source = pc_join(c->semantic_root, interface_path + strlen("modules/"));
            if (!pc_module_name(module) || (strncmp(module, "std.", 4) && strncmp(module, "sys.", 4)) ||
                pj_get(c->modules, module) || pj_count(c->modules) >= PC_PROFILE_MAX_MODULES)
                ok = pc_fail(c, 2151, "invalid bundled profile module", rel);
            else if (!pc_hash_observed(c, source, digest, NULL, "profile", "semantic-interface"))
                ok = pc_fail(c, 2158, "required bundled semantic interface is unavailable; rebuild or repair installation", source);
            else if (pc_profile_track(c, path) && pc_profile_track(c, source)) {
                pj_set_string(c->modules, module, interface_path); pj_set_string(c->interfaces, interface_path, digest);
            } else ok = 0;
            free(module); free(interface_path); free(source);
        } else if (kind != 1) ok = pc_fail(c, 2151, "profile inputs require ordinary files and directories", path);
        free(rel); free(path);
    }
    pj_free(names);
    return ok;
}

/** Refuse output overlap with all protected trees/files before creating its parent. */
static int pc_profile_destination(PcContext *c, const char *destination) {
    const char *protected_paths[7];
    char *absolute = pc_path_call(destination, l1c_fs_absolute_path);
    char *canonical = pc_canonical_future(destination);
    int i, ok = absolute && canonical && pc_kind(absolute, 0) == 0;
    protected_paths[0] = c->home; protected_paths[1] = c->semantic_root;
    protected_paths[2] = c->include; protected_paths[3] = c->self;
    protected_paths[4] = c->compiler; protected_paths[5] = c->archiver; protected_paths[6] = NULL;
    for (i = 0; i < 6 && ok; ++i) {
        char *input = protected_paths[i] ? pc_canonical_future(protected_paths[i]) : NULL;
        if (input && (pc_within(canonical, input) || pc_within(input, canonical))) ok = 0;
        free(input);
    }
    if (!ok) pc_fail(c, 2181, "profile output must be a new directory outside protected inputs", destination);
    else c->profile_destination = canonical;
    free(absolute);
    if (!ok) free(canonical);
    return ok;
}

/** Keep native search/input trees outside the creator-owned output, including resolved aliases. */
static int pc_profile_option_overlap(PcContext *c, const PcJson *options) {
    const PcJson *word;
    for (word = options ? options->child : NULL; word; word = word->next) {
        const char *path = word->text;
        char *canonical;
        if (!strncmp(path, "--gcc-toolchain=", 16)) path += 16;
        if (!pc_profile_absolute(path)) continue;
        canonical = pc_canonical_future(path);
        if (canonical && (pc_within(c->profile_destination, canonical) ||
                          pc_within(canonical, c->profile_destination))) {
            pc_fail(c, 2181, "profile destination overlaps a selected external native input", path);
            free(canonical); return 0;
        }
        free(canonical);
    }
    return 1;
}

/** Allocate one exclusive registered sibling; the parent is trusted and writers are serialized externally. */
static int pc_profile_stage(PcContext *c) {
    char *parent = pc_parent(c->profile_destination), *stage = NULL;
    unsigned i;
    int ok = pc_mkdirs(parent);
    for (i = 0; ok && i < 100 && !stage; ++i) {
        PcBuffer name = {0};
        char suffix[96], *candidate;
        snprintf(suffix, sizeof(suffix), ".l1-profile-%p-%u", (void *)c, i);
        pc_text(&name, suffix); candidate = pc_join(parent, name.s); free(name.s);
#if defined(_WIN32)
        if (_mkdir(candidate) == 0) stage = candidate;
#else
        if (mkdir(candidate, 0700) == 0) stage = candidate;
#endif
        else { free(candidate); if (errno != EEXIST) ok = 0; }
    }
    free(parent);
    if (!stage) return pc_fail(c, 2181, "cannot allocate profile sibling staging directory", c->profile_destination);
    c->profile_stage = stage;
    return 1;
}

/** Copy every ordinary public-header input, retaining no links to mutable installation files. */
static int pc_profile_headers(PcContext *c, const char *source_root, const char *relative,
                               PcJson *inventory, int depth) {
    char *source = pc_join(source_root, relative);
    PcJson *names;
    const PcJson *name;
    int ok = depth <= 16 && pc_profile_track(c, source);
    names = ok ? pc_list(source) : NULL;
    ok = ok && names;
    free(source);
    if (!ok) { pj_free(names); return pc_fail(c, 2183, "cannot enumerate complete public header set", source_root); }
    for (name = names->child; name && ok; name = name->next) {
        char *rel = *relative ? pc_join(relative, name->text) : pc_string(name->text);
        char *from = pc_join(source_root, rel), *payload = pc_join("include", rel);
        char *to = pc_join(c->profile_stage, payload);
        int kind = pc_kind(from, 0);
        if (!pc_relative(payload)) ok = pc_fail(c, 2183, "unsupported public header path", from);
        else if (kind == 2) ok = pc_profile_headers(c, source_root, rel, inventory, depth + 1);
        else if (kind == 1) {
            size_t size;
            char *data = pc_profile_track(c, from) ? pc_read_file(from, PC_PROFILE_MAX_MANIFEST, &size) : NULL;
            char *parent = pc_parent(to), digest[65];
            PcJson *record = pj_new(PJ_OBJECT);
            ok = data && pc_mkdirs(parent) && pc_write_file(to, data, size);
            if (ok) {
                pc_sha_bytes(data, size, digest);
                pj_set_string(record, "path", payload); pj_set_string(record, "role", "header");
                pj_set_number(record, "size", (int64_t)size); pj_set_string(record, "sha256", digest);
                pj_add(inventory, NULL, record);
            } else { pj_free(record); pc_fail(c, 2183, "cannot copy public header", from); }
            free(data); free(parent);
        } else ok = pc_fail(c, 2183, "public header inputs require ordinary files and directories", from);
        free(rel); free(from); free(payload); free(to);
    }
    pj_free(names);
    return ok;
}

/** Describe only expected constructor outputs and registered explicit-profile copies. */
static PcJson *pc_profile_owned(PcContext *c) {
    PcJson *allowed = pj_new(PJ_OBJECT);
    const PcJson *item;
    int i;
    if (c->construction) {
        for (item = c->construction->expected ? c->construction->expected->child : NULL;
             item; item = item->next) pj_set_number(allowed, item->key, 1);
        for (item = pj_get(c->construction->inputs, "modules") ? pj_get(c->construction->inputs, "modules")->child : NULL;
             item; item = item->next) {
            char *path = pc_module_artifact(item->key, ".c", "generated");
            pj_set_number(allowed, path, 1); free(path);
        }
        for (i = -1; i < 9; ++i) {
            PcBuffer name = {0};
            pc_text(&name, "runtime-build/"); pc_text(&name, i < 0 ? "dea_rt_trace" : pc_runtime_sources[i]);
            pc_text(&name, ".o"); pj_set_number(allowed, name.s, 1); free(name.s);
        }
    }
    for (item = c->profile_headers ? c->profile_headers->child : NULL; item; item = item->next)
        pj_set_number(allowed, pj_field(item, "path"), 1);
    if (c->profile_manifest_written) pj_set_number(allowed, "profile.json", 1);
    return allowed;
}

/** Inspect the complete owned tree before deleting anything, retaining unexpected evidence intact. */
static int pc_profile_known_tree(const char *root, const char *relative, const PcJson *allowed, int depth) {
    char *path = *relative ? pc_join(root, relative) : pc_string(root);
    int kind = pc_kind(path, 0), ok = 1;
    const PcJson *item;
    if (kind == 1) ok = pj_get(allowed, relative) != NULL;
    else if (kind == 2 && depth <= 20) {
        PcJson *names;
        if (*relative) {
            size_t length = strlen(relative);
            ok = 0;
            for (item = allowed->child; item; item = item->next)
                if (!strncmp(item->key, relative, length) && item->key[length] == '/') { ok = 1; break; }
        }
        names = ok ? pc_list(path) : NULL;
        if (!names) ok = 0;
        for (item = names ? names->child : NULL; item && ok; item = item->next) {
            char *child = *relative ? pc_join(relative, item->text) : pc_string(item->text);
            ok = pc_profile_known_tree(root, child, allowed, depth + 1); free(child);
        }
        pj_free(names);
    } else ok = kind == 0;
    free(path);
    return ok;
}

/** Remove only registered owned contents after recoverable failure; never traverse unexpected aliases. */
static void pc_profile_cleanup(PcContext *c) {
    PcJson *allowed;
    int ok;
    if (!c->profile_stage) return;
    allowed = pc_profile_owned(c);
    ok = pc_profile_known_tree(c->profile_stage, "", allowed, 0) && pc_remove_owned_tree(c->profile_stage);
    pj_free(allowed);
    if (!ok) fprintf(stderr, "Profile staging retained after unexpected contents or cleanup failure: %s\n", c->profile_stage);
}

/** Undeclared files, including headers that can shadow native includes, have no consumption authority. */
static int pc_profile_public_tree(PcContext *c, const char *root, const PcJson *manifest) {
    PcJson *allowed = pj_new(PJ_OBJECT);
    const PcJson *item, *payloads = pj_get(manifest, "payloads");
    int ok;
    pj_set_number(allowed, "profile.json", 1);
    for (item = payloads ? payloads->child : NULL; item; item = item->next)
        pj_set_number(allowed, pj_field(item, "path"), 1);
    ok = pc_profile_known_tree(root, "", allowed, 0);
    pj_free(allowed);
    return ok ? 1 : pc_fail(c, 2183, "profile contains undeclared files, directories, or aliases", root);
}

/** Validate all declared payload paths and selected bytes without consulting installation/toolchain identity. */
static int pc_profile_payloads(PcContext *c, const char *root, const PcJson *manifest, int native) {
    static const char *const record_fields[] = {"path", "role", "size", "sha256", NULL};
    const PcJson *configuration = pj_get(manifest, "configuration");
    const PcJson *payloads = pj_get(manifest, "payloads"), *item, *module;
    PcJson *expected = pc_payload_artifacts(pj_get(manifest, "modules"), pj_field(configuration, "family"),
                                           pj_field(configuration, "variant"));
    PcJson *seen = pj_new(PJ_OBJECT), *runtime = pj_new(PJ_ARRAY);
    int ok = expected && payloads && payloads->type == PJ_ARRAY && pj_count(payloads) <= PC_PROFILE_MAX_PAYLOADS;
    for (item = ok ? payloads->child : NULL; item && ok; item = item->next) {
        const char *path = pj_field(item, "path"), *role = pj_field(item, "role"), *digest = pj_field(item, "sha256");
        const PcJson *size = pj_get(item, "size");
        const char *wanted = path ? pj_field(expected, path) : NULL;
        char *absolute = NULL, *canonical = NULL;
        if (!pc_profile_fields(item, record_fields) || pj_count(item) != 4 || !pc_relative(path) ||
            !role || !pc_hex_digest(digest) || !size || size->type != PJ_NUMBER || size->number < 0 ||
            pj_get(seen, path) || ((!wanted || strcmp(wanted, role)) &&
                (strcmp(role, "header") || strncmp(path, "include/", 8)))) { ok = 0; break; }
        pj_set_string(seen, path, role);
        if (!strcmp(role, "runtime")) pj_add(runtime, NULL, pj_string(path));
        absolute = pc_join(root, path);
        canonical = pc_path_call(absolute, l1c_fs_canonical_existing_path);
        if (!canonical || !pc_within(canonical, root) || !pc_path_equal(canonical, absolute) ||
            pc_kind(absolute, 0) != 1) ok = 0;
        if (ok && (native || !strcmp(role, "header") || !strcmp(role, "interface"))) {
            char actual[65]; PcJson *metadata = NULL;
            ++c->artifact_reads;
            ok = pc_hash_observed(c, absolute, actual, &metadata, "profile-payload", "selected-profile") &&
                 pj_is_number(pj_get(metadata, "size"), size->number) && !strcmp(digest, actual);
            pj_free(metadata);
        }
        free(absolute); free(canonical);
    }
    for (item = expected ? expected->child : NULL; item && ok; item = item->next)
        if (!pj_get(seen, item->key)) ok = 0;
    for (module = pj_get(manifest, "modules") ? pj_get(manifest, "modules")->child : NULL;
         module && ok; module = module->next) {
        char *path = pc_module_artifact(module->key, ".l1m", "modules");
        if (!pj_str(module) || strcmp(path, module->text) ||
            (strncmp(module->key, "std.", 4) && strncmp(module->key, "sys.", 4))) ok = 0;
        free(path);
    }
    if (!pj_get(seen, "include/dea_rt.h") || !pj_get(seen, "include/l1_real.h") ||
        !pj_equal(runtime, pj_get(manifest, "runtime"))) ok = 0;
    pj_free(expected); pj_free(seen); pj_free(runtime);
    return ok ? 1 : pc_fail(c, 2183, "invalid, incomplete, escaped, or damaged profile payload inventory", root);
}

/** Read the bounded exact public schema before following any payload reference. */
static PcJson *pc_profile_read(PcContext *c, const char *root) {
    static const char *const top_fields[] = {
        "schema", "kind", "contract", "producer", "configuration", "include", "modules", "runtime", "payloads", NULL};
    static const char *const configuration_fields[] = {"compiler", "family", "options", "runtime_options",
        "runtime_configuration_isolation", "variant", "codegen", NULL};
    static const char *const producer_fields[] = {"name", "language", "compiler_description", NULL};
    char *path = pc_join(root, "profile.json"), *data;
    size_t size;
    PcJson *manifest, *options = NULL, *runtime_options = NULL;
    const PcJson *configuration, *producer, *modules;
    const char *family, *isolation;
    int ok;
    data = pc_kind(path, 0) == 1 ? pc_read_file(path, PC_PROFILE_MAX_MANIFEST, &size) : NULL;
    manifest = data ? pj_parse(data, size) : NULL;
    free(data); free(path);
    configuration = pj_get(manifest, "configuration"); producer = pj_get(manifest, "producer");
    modules = pj_get(manifest, "modules");
    family = pj_field(configuration, "family"); isolation = pj_field(configuration, "runtime_configuration_isolation");
    ok = pc_profile_fields(manifest, top_fields) && pj_count(manifest) == 9 &&
         pj_is_number(pj_get(manifest, "schema"), PC_PROFILE_SCHEMA) &&
         pj_field(manifest, "kind") && !strcmp(pj_field(manifest, "kind"), "l1-explicit-profile") &&
         pc_profile_fields(configuration, configuration_fields) && pj_count(configuration) == 7 &&
         pc_profile_fields(producer, producer_fields) && pj_field(producer, "name") &&
         !strcmp(pj_field(producer, "name"), "l1c") && pj_field(producer, "language") &&
         !strcmp(pj_field(producer, "language"), "L1") &&
         (!pj_get(producer, "compiler_description") || pj_field(producer, "compiler_description")) &&
         pc_profile_absolute(pj_field(configuration, "compiler")) && family &&
         (!strcmp(family, "gcc") || !strcmp(family, "clang") || !strcmp(family, "tcc")) &&
         pj_field(configuration, "variant") && pc_runtime_archive(pj_field(configuration, "variant")) &&
         isolation && (!strcmp(isolation, "none") || (!strcmp(family, "clang") &&
             (!strcmp(isolation, "clang-no-default-config-v1") || !strcmp(isolation, "clang-explicit-empty-config-v1")))) &&
         pc_profile_codegen(pj_get(configuration, "codegen")) &&
         pc_profile_variant(pj_get(configuration, "codegen"), pj_field(configuration, "variant")) &&
         pj_field(manifest, "include") && !strcmp(pj_field(manifest, "include"), "include") &&
         modules && modules->type == PJ_OBJECT && pj_count(modules) > 0 && pj_count(modules) <= PC_PROFILE_MAX_MODULES &&
         pj_get(manifest, "runtime") && pj_get(manifest, "runtime")->type == PJ_ARRAY;
    if (!ok) pc_fail(c, 2182, "unreadable, incomplete, or unsupported explicit profile manifest", root);
    else if (!pj_is_number(pj_get(manifest, "contract"), PC_PROFILE_CONTRACT))
        pc_fail(c, 2184, "unsupported Dea compilation contract version", root);
    else {
        options = pc_profile_options(c, pj_get(configuration, "options"), 1);
        runtime_options = pc_profile_options(c, pj_get(configuration, "runtime_options"), 1);
        if (options && runtime_options &&
            (!pj_equal(options, pj_get(configuration, "options")) ||
             !pj_equal(runtime_options, pj_get(configuration, "runtime_options"))))
            pc_fail(c, 2182, "profile options are not in normalized form", root);
    }
    pj_free(options); pj_free(runtime_options);
    if (c->error || !pc_profile_payloads(c, root, manifest, 0) ||
        !pc_profile_public_tree(c, root, manifest)) { pj_free(manifest); return NULL; }
    return manifest;
}

/** Start a fresh explicit profile through the shared constructor, with no cache interaction. */
void *l1c_profile_create(const uint8_t *data, int32_t length,
                         const uint8_t *destination, int32_t destination_length) {
    PcContext *c = l1c_prep_create(data, length);
    PcJson *inputs = NULL, *options = NULL;
    PcOptionInputs option_inputs = {0};
    char *target = NULL, *source_root = NULL;
    const char *variant;
    if (c->error) return c;
    if (!destination || destination_length <= 0 || memchr(destination, 0, (size_t)destination_length)) {
        pc_fail(c, 2181, "explicit profile requires a nonempty new output directory", NULL); return c;
    }
    target = pc_slice((const char *)destination, (size_t)destination_length);
    options = pc_profile_options(c, c->options, 0);
    if (!options) goto finish;
    pj_free(c->options); c->options = options; options = NULL;
    if (!pc_profile_codegen(pj_get(c->config, "codegen"))) {
        pc_fail(c, 2180, "profile requires a complete frontend configuration", NULL); goto finish;
    }
    c->compiler = pc_executable(pc_config(c, "compiler"));
    if (!c->compiler) { pc_fail(c, 2154, "cannot resolve selected C compiler", pc_config(c, "compiler")); goto finish; }
    c->self = *pc_config(c, "self") ? pc_path_call(pc_config(c, "self"), l1c_fs_absolute_path) : NULL;
    variant = *pc_config(c, "variant") ? pc_config(c, "variant") : "default";
    if (!pc_runtime_archive(variant) || !pc_profile_variant(pj_get(c->config, "codegen"), variant)) {
        pc_fail(c, 2180, "invalid or conflicting profile runtime variant", variant); goto finish;
    }
    /* Family, capability isolation, runtime target extraction and archive-tool selection
       are execution prerequisites. No managed observation, memo, key or reuse admission runs. */
    if (!pc_profile_destination(c, target) || !pc_compilation_family(c) ||
        !pc_runtime_configuration(c, variant, &option_inputs)) goto finish;
    {
        const PcOptionFile *file;
        for (file = option_inputs.files; file; file = file->next)
            if (file->configuration) {
                pc_fail(c, 2180, "selected implicit compiler configuration files are unsupported in explicit profiles", file->path);
                goto finish;
            }
    }
    if (!pc_compilation_toolchain(c)) goto finish;
    {
        char *archiver = c->archiver ? pc_canonical_future(c->archiver) : NULL;
        int overlap = archiver && (pc_within(c->profile_destination, archiver) || pc_within(archiver, c->profile_destination));
        free(archiver);
        if (overlap) { pc_fail(c, 2181, "profile destination overlaps selected archive tool", target); goto finish; }
    }
    options = pc_profile_options(c, c->runtime_options, 0);
    if (!options) goto finish;
    pj_free(c->runtime_options); c->runtime_options = options; options = NULL;
    if (!pc_profile_option_overlap(c, c->options) || !pc_profile_option_overlap(c, c->runtime_options)) goto finish;
    c->dea = pj_new(PJ_OBJECT); c->modules = pj_new(PJ_OBJECT); c->interfaces = pj_new(PJ_OBJECT);
    pj_add(c->dea, "modules", c->modules); pj_add(c->dea, "interfaces", c->interfaces);
    source_root = pc_join(c->home, "shared/l1/stdlib");
    if (!pc_profile_modules(c, source_root, "", 0) || !pj_count(c->modules) || !pc_profile_stage(c)) goto finish;
    {
        char *runtime_root = pc_join(c->home, "shared/runtime");
        int stable = pc_profile_track_tree(c, runtime_root, 0);
        free(runtime_root);
        if (!stable) goto finish;
    }
    c->profile_headers = pj_new(PJ_ARRAY);
    if (!pc_profile_headers(c, c->include, "", c->profile_headers, 0)) goto finish;
    free(c->include); c->include = pc_join(c->profile_stage, "include");
    inputs = pj_new(PJ_OBJECT);
    pj_set_string(inputs, "compiler", c->compiler); pj_set_string(inputs, "family", c->family);
    if (c->archiver) pj_set_string(inputs, "archiver", c->archiver);
    pj_set_string(inputs, "home", c->home); pj_set_string(inputs, "semantic_root", c->semantic_root);
    pj_set_string(inputs, "include", c->include); pj_set_string(inputs, "variant", variant);
    pj_set_string(inputs, "runtime_configuration_isolation", pc_runtime_isolation(c));
    pj_add(inputs, "options", pj_clone(c->options)); pj_add(inputs, "runtime_options", pj_clone(c->runtime_options));
    pj_add(inputs, "modules", pj_clone(c->modules)); pj_add(inputs, "interfaces", pj_clone(c->interfaces));
    pj_add(inputs, "codegen", pj_clone(pj_get(c->config, "codegen")));
    pc_begin_construction(c, inputs, c->profile_stage);
finish:
    pj_free(options); pj_free(inputs); pc_option_inputs_free(&option_inputs);
    free(target); free(source_root);
    return c;
}

/** Publish completion last to an absent destination; retain failed staging as recovery evidence. */
int32_t l1c_profile_publish(void *context) {
    PcContext *c = context;
    PcJson *manifest, *configuration, *producer, *runtime;
    const PcJson *item;
    char *path;
    int ok;
    if (!c || c->error || !c->profile_stage || !c->construction) return 0;
    if (!c->construction->inventory && !pc_finish_construction(c)) return 0;
    manifest = pj_new(PJ_OBJECT); configuration = pj_new(PJ_OBJECT); producer = pj_new(PJ_OBJECT);
    runtime = pj_new(PJ_ARRAY);
    pj_set_number(manifest, "schema", PC_PROFILE_SCHEMA); pj_set_number(manifest, "contract", PC_PROFILE_CONTRACT);
    pj_set_string(manifest, "kind", "l1-explicit-profile");
    pj_set_string(producer, "name", "l1c"); pj_set_string(producer, "language", "L1");
    if (c->description && *c->description) pj_set_string(producer, "compiler_description", c->description);
    pj_add(manifest, "producer", producer);
    pj_set_string(configuration, "compiler", c->compiler); pj_set_string(configuration, "family", c->family);
    pj_add(configuration, "options", pj_clone(c->options));
    pj_add(configuration, "runtime_options", pj_clone(c->runtime_options));
    pj_set_string(configuration, "variant", pc_construction_field(c->construction, "variant"));
    pj_set_string(configuration, "runtime_configuration_isolation", pc_runtime_isolation(c));
    pj_add(configuration, "codegen", pj_clone(pj_get(c->config, "codegen")));
    pj_add(manifest, "configuration", configuration);
    pj_set_string(manifest, "include", "include"); pj_add(manifest, "modules", pj_clone(c->modules));
    pj_add(manifest, "runtime", runtime);
    pj_add(manifest, "payloads", pj_clone(c->construction->inventory));
    for (item = c->construction->inventory->child; item; item = item->next)
        if (!strcmp(pj_field(item, "role"), "runtime")) pj_add(runtime, NULL, pj_string(pj_field(item, "path")));
    for (item = c->profile_headers ? c->profile_headers->child : NULL; item; item = item->next)
        pj_add(pj_get(manifest, "payloads"), NULL, pj_clone(item));
    ok = pc_preparation_inputs_current(c) && pc_profile_payloads(c, c->profile_stage, manifest, 1);
    path = pc_join(c->profile_stage, "profile.json");
    if (ok) {
        char *encoded = pj_encode(manifest);
        size_t length = strlen(encoded);
        if (length > PC_PROFILE_MAX_MANIFEST)
            ok = pc_fail(c, 2182, "profile completion manifest exceeds the supported size bound", path);
        else {
            c->profile_manifest_written = 1;
            if (!pc_write_file(path, encoded, length)) ok = pc_fail(c, 2185, "cannot write profile completion manifest", path);
        }
        free(encoded);
    }
    free(path);
    /* Registered constructor scratch is optional evidence only and is absent from the public artifact. */
    if (ok) {
        PcJson *allowed = pc_profile_owned(c);
        ok = pc_profile_known_tree(c->profile_stage, "", allowed, 0);
        pj_free(allowed);
        path = pc_join(c->profile_stage, "generated"); if (ok) ok = pc_remove_owned_tree(path); free(path);
        if (ok) { path = pc_join(c->profile_stage, "runtime-build"); ok = pc_remove_owned_tree(path); free(path); }
        if (!ok) pc_fail(c, 2185, "cannot remove profile construction scratch; staging retained", c->profile_stage);
    }
    if (ok && (pc_kind(c->profile_destination, 0) != 0 || rename(c->profile_stage, c->profile_destination) != 0))
        ok = pc_fail(c, 2185, "cannot publish profile to absent destination; staging retained", c->profile_stage);
    if (ok) {
        free(c->selected); c->selected = pc_string(c->profile_destination);
        free(c->include); c->include = pc_join(c->selected, "include");
        free(c->semantic_root); c->semantic_root = pc_join(c->selected, "modules");
        free(c->profile_stage); c->profile_stage = NULL;
        pj_free(c->profile); c->profile = manifest; manifest = NULL;
    }
    pj_free(manifest);
    return ok;
}

/** Load exactly one public artifact read-only, with no defaults, compiler probe, or managed context. */
void *l1c_profile_load(const uint8_t *path, int32_t length) {
    PcContext *c = pc_alloc(sizeof(*c));
    char *requested = NULL;
    const PcJson *configuration;
    c->config = pj_new(PJ_OBJECT); c->old_files = pj_new(PJ_OBJECT); c->new_files = pj_new(PJ_OBJECT);
    if (path && length > 0 && !memchr(path, 0, (size_t)length)) {
        requested = pc_slice((const char *)path, (size_t)length);
        c->selected = pc_path_call(requested, l1c_fs_canonical_existing_path);
    }
    if (!c->selected || pc_kind(c->selected, 0) != 2) {
        pc_fail(c, 2182, "explicit profile root is unavailable", requested); free(requested); return c;
    }
    free(requested);
    c->profile = pc_profile_read(c, c->selected);
    if (!c->profile) return c;
    configuration = pj_get(c->profile, "configuration");
    c->compiler = pc_string(pj_field(configuration, "compiler"));
    c->family = pc_string(pj_field(configuration, "family"));
    c->include = pc_join(c->selected, "include"); c->semantic_root = pc_join(c->selected, "modules");
    c->modules = pj_get(c->profile, "modules");
    c->options = pj_clone(pj_get(configuration, "options"));
    c->runtime_options = pj_clone(pj_get(configuration, "runtime_options"));
    return c;
}

/** Recheck bytes required by the consuming mode before native invocation, without writing a memo. */
int32_t l1c_profile_verify(void *context, int32_t native_payloads) {
    PcContext *c = context;
    return c && !c->error && c->profile &&
        pc_profile_payloads(c, c->selected, c->profile, native_payloads != 0) &&
        pc_profile_public_tree(c, c->selected, c->profile);
}

/** Preserve profile ownership even when caller-selected outputs alias unused payload locations. */
int32_t l1c_profile_output(void *context, const uint8_t *path, int32_t length) {
    PcContext *c = context;
    char *requested = NULL, *canonical = NULL;
    int ok;
    if (!c || c->error || !c->profile) return 0;
    if (path && length > 0 && !memchr(path, 0, (size_t)length)) {
        requested = pc_slice((const char *)path, (size_t)length);
        canonical = pc_canonical_future(requested);
    }
    ok = canonical && !pc_within(canonical, c->selected) && !pc_within(c->selected, canonical);
    if (!ok) pc_fail(c, 2184, "consumer output overlaps the read-only selected profile", requested);
    free(requested); free(canonical);
    return ok;
}

/** Reject scratch allocation under a selected profile while permitting ordinary ancestor temp roots. */
int32_t l1c_profile_temp_parent(void *context, const uint8_t *path, int32_t length) {
    PcContext *c = context;
    char *requested = NULL, *canonical = NULL;
    int ok;
    if (!c || c->error || !c->profile) return 0;
    if (path && length > 0 && !memchr(path, 0, (size_t)length)) {
        requested = pc_slice((const char *)path, (size_t)length);
        canonical = pc_path_call(requested, l1c_fs_canonical_existing_path);
    }
    ok = canonical && !pc_within(canonical, c->selected);
    if (!ok) pc_fail(c, 2184, "consumer temporary parent overlaps the read-only selected profile", requested);
    free(requested); free(canonical);
    return ok;
}

/** Compare only explicitly supplied settings using lexical normalization, never alternate compiler probes. */
int32_t l1c_profile_match(void *context, const uint8_t *data, int32_t length) {
    PcContext *c = context;
    PcJson *supplied, *normalized = NULL;
    const PcJson *configuration, *value, *field;
    int ok = 1;
    if (!c || c->error || !c->profile) return 0;
    supplied = data && length >= 0 ? pj_parse((const char *)data, (size_t)length) : NULL;
    configuration = pj_get(c->profile, "configuration");
    if (!supplied || supplied->type != PJ_OBJECT) ok = 0;
    value = pj_get(supplied, "compiler");
    if (value) {
        const char *compiler = pj_str(value);
        if (!compiler || !*compiler) ok = 0;
        else if (!strchr(compiler, '/') && !strchr(compiler, '\\')) ok = !strcmp(compiler, pc_base(c->compiler));
        else {
            char *absolute = pc_path_call(compiler, l1c_fs_absolute_path);
            ok = absolute && pc_path_equal(absolute, c->compiler); free(absolute);
        }
    }
    value = pj_get(supplied, "options");
    if (ok && value) { normalized = pc_profile_options(c, value, 0); ok = normalized && pj_equal(normalized, c->options); }
    value = pj_get(supplied, "variant");
    if (ok && value) ok = pj_equal(value, pj_get(configuration, "variant"));
    value = pj_get(supplied, "codegen");
    if (ok && value) {
        if (value->type != PJ_OBJECT) ok = 0;
        for (field = value->child; field && ok; field = field->next)
            ok = pj_equal(field, pj_get(pj_get(configuration, "codegen"), field->key));
    }
    pj_free(normalized); pj_free(supplied);
    return ok ? 1 : pc_fail(c, 2184, "explicit settings conflict with selected profile configuration", NULL);
}

/** Project public configuration for the L0 frontend without exposing private JSON layouts to it. */
static const char *pc_profile_get(PcContext *c, const char *field, char **owned) {
    const PcJson *configuration = pj_get(c->profile, "configuration"), *array, *value;
    const char *key = field + strlen("profile_");
    char count[32];
    int index;
    if (!strcmp(key, "stage")) return c->profile_stage;
    if (!strcmp(key, "destination")) return c->profile_destination;
    if (!configuration) return NULL;
    if (!strcmp(key, "options") || !strcmp(key, "codegen") || !strcmp(key, "runtime_options")) {
        *owned = pj_encode(pj_get(configuration, key)); return *owned;
    }
    if (!strcmp(key, "variant")) return pj_field(configuration, "variant");
    if (!strncmp(key, "codegen_", 8))
        return pj_is_number(pj_get(pj_get(configuration, "codegen"), key + 8), 1) ? "1" : "0";
    if (!strncmp(key, "option_", 7) || !strncmp(key, "runtime_", 8)) {
        int runtime = !strncmp(key, "runtime_", 8);
        const char *suffix = key + (runtime ? 8 : 7);
        array = runtime ? pj_get(c->profile, "runtime") : pj_get(configuration, "options");
        if (!strcmp(suffix, "count")) {
            snprintf(count, sizeof(count), "%lu", (unsigned long)pj_count(array));
            *owned = pc_string(count); return *owned;
        }
        index = atoi(suffix); value = array ? array->child : NULL;
        while (value && index-- > 0) value = value->next;
        if (runtime && pj_str(value)) { *owned = pc_join(c->selected, value->text); return *owned; }
        return pj_str(value);
    }
    return NULL;
}
#endif
