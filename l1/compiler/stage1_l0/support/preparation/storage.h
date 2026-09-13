/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file storage.h Single-root native profiles and disposable validation memos. */
#ifndef L1_PREPARATION_STORAGE_H
#define L1_PREPARATION_STORAGE_H

typedef struct {
    PcJson *config, *options, *runtime_options, *dea, *native, *modules, *interfaces;
    PcJson *old_files, *new_files;
    char *local, *home, *compiler, *self, *semantic_root, *include;
    char *dea_key, *native_key, *selected, *error, *description, *family, *archiver;
    char *private_root, *ineligible, *unusable;
    int error_code, force, native_resolved, begun, explicit_root, writable, installed, runtime_config_observed;
    int64_t identity_reads, artifact_reads, probes, metadata_checks, resolutions;
    int64_t build_commands, module_compiles;
    int64_t option_file_parses, option_root_expansions;
    PcLock *lock;
} PcContext;

/** Retain the first actionable error; cleanup must not hide its cause. */
static int pc_fail(PcContext *c, int code, const char *reason, const char *path) {
    PcBuffer b = {0};
    if (c->error) return 0;
    pc_text(&b, reason);
    if (path && *path) { pc_text(&b, ": "); pc_text(&b, path); }
    c->error = pc_take(&b);
    c->error_code = code;
    return 0;
}
static void pc_clear_error(PcContext *c) {
    free(c->error); c->error = NULL; c->error_code = 0;
}
static const char *pc_env(const char *key) {
    const char *s = getenv(key);
    return s ? s : "";
}
static int pc_verbosity(PcContext *c) {
    const PcJson *v = pj_get(c->config, "verbosity");
    return v && v->type == PJ_NUMBER ? (int)v->number : 0;
}
static const char *pc_config(PcContext *c, const char *key) {
    const char *s = pj_field(c->config, key);
    return s ? s : "";
}
static char *pc_user_default(void) {
#if defined(_WIN32)
    if (*pc_env("LOCALAPPDATA")) return pc_join(pc_env("LOCALAPPDATA"), "Dea/L1/Cache");
    return *pc_env("USERPROFILE") ? pc_join(pc_env("USERPROFILE"), "AppData/Local/Dea/L1/Cache") : NULL;
#elif defined(__APPLE__)
    return *pc_env("HOME") ? pc_join(pc_env("HOME"), "Library/Caches/dea/l1") : NULL;
#else
    if (*pc_env("XDG_CACHE_HOME")) return pc_join(pc_env("XDG_CACHE_HOME"), "dea/l1");
    return *pc_env("HOME") ? pc_join(pc_env("HOME"), ".cache/dea/l1") : NULL;
#endif
}
/** Resolve toolchain-owned paths without hashing inputs or touching native storage. */
static int pc_toolchain_paths(PcContext *c) {
    const char *build = pc_config(c, "build_dir");
    char *repo_marker, *derived = NULL, *base;
    c->home = pc_path_call(pc_config(c, "home"), l1c_fs_absolute_path);
    if (!c->home) return pc_fail(c, 2151, "cannot locate L1 toolchain inputs; rebuild bootstrap or repair installation", NULL);
    repo_marker = pc_join(c->home, "stage1_l0/src");
    c->installed = pc_kind(repo_marker, 1) != 2;
    free(repo_marker);
    if (!c->installed && !*build) {
        char *parent = pc_parent(c->home);
        derived = pc_join(parent, "build/dea");
        free(parent);
        build = derived;
    }
    base = pc_path_call(c->installed ? c->home : build, l1c_fs_absolute_path);
    if (!base) { pc_fail(c, 2151, "cannot resolve toolchain build directory", build); free(derived); return 0; }
    c->semantic_root = pc_join(base, "interfaces");
    if (*pc_config(c, "runtime_include"))
        c->include = pc_path_call(pc_config(c, "runtime_include"), l1c_fs_absolute_path);
    else
        c->include = pc_join(base, "include");
    free(base); free(derived);
    return 1;
}
/** Test only the Dea-owned subtree, never treating its caller-selected parent as disposable. */
static int pc_root_writable(PcContext *c) {
    char *version = c->local ? pc_join(c->local, "v1") : NULL;
    int ok = version && pc_mkdirs(version);
    if (ok) {
        char name[96];
        char *probe;
        int fd;
#if defined(_WIN32)
        unsigned long process = (unsigned long)GetCurrentProcessId();
#else
        unsigned long process = (unsigned long)getpid();
#endif
        snprintf(name, sizeof(name), ".write-%lu-%p", process, (void *)c);
        probe = pc_join(version, name);
#if defined(_WIN32)
        fd = _open(probe, _O_CREAT | _O_EXCL | _O_WRONLY | _O_BINARY, _S_IREAD | _S_IWRITE);
        ok = fd >= 0;
        if (ok) { _close(fd); remove(probe); }
#else
        fd = open(probe, O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC, 0600);
        ok = fd >= 0;
        if (ok) { close(fd); remove(probe); }
#endif
        free(probe);
    }
    free(version);
    return ok;
}
/** Resolve one root and enforce installed-payload ownership before any managed write. */
static int pc_roots(PcContext *c) {
    const char *value = pc_config(c, "cache");
    char *fallback = NULL, *absolute, *version, *canonical, *payload;
    if (!pj_get(c->config, "cache")) value = pc_env("L1_STDLIB_CACHE");
    c->explicit_root = pj_get(c->config, "cache") != NULL || getenv("L1_STDLIB_CACHE") != NULL;
    if (!c->explicit_root) {
        if (c->installed) fallback = pc_user_default();
        else {
            char *build = pc_parent(c->semantic_root);
            fallback = pc_join(build, "cache"); free(build);
        }
        value = fallback;
    }
    absolute = value && *value ? pc_path_call(value, l1c_fs_absolute_path) : NULL;
    c->local = absolute ? pc_canonical_future(absolute) : NULL;
    if (!c->local) c->local = absolute ? pc_string(absolute) : NULL;
    free(absolute); free(fallback);
    version = c->local ? pc_join(c->local, "v1") : NULL;
    canonical = version ? pc_canonical_future(version) : NULL;
    payload = c->installed ? pc_canonical_future(c->home) : NULL;
    if (c->installed && (!payload || (canonical &&
            (pc_within(canonical, payload) || pc_within(payload, canonical))))) {
        free(version); free(canonical); free(payload);
        return pc_fail(c, 2150, "managed v1 subtree overlaps installed payload; select a cache outside the installation", c->local);
    }
    free(payload); free(version);
    c->writable = canonical && pc_root_writable(c);
    free(canonical);
    if (c->explicit_root && !c->writable)
        return pc_fail(c, 2150, "explicit stdlib cache is unusable; choose a writable --stdlib-cache or L1_STDLIB_CACHE directory", c->local);
    return 1;
}
static char *pc_memo_path(PcContext *c, const char *kind, const char *key, int create) {
    char *base, *directory, *filename, *path;
    PcBuffer b = {0};
    if (!c->local || (create && !c->writable) || c->private_root) return NULL;
    base = pc_join(c->local, "v1/memo");
    directory = pc_join(base, kind);
    free(base);
    if (create && !pc_mkdirs(directory)) { free(directory); return NULL; }
    pc_text(&b, key); pc_text(&b, ".json"); filename = pc_take(&b);
    path = pc_join(directory, filename);
    free(directory); free(filename);
    return path;
}
static int pc_memo_valid(const PcJson *memo, const char *kind) {
    return memo && pj_is_number(pj_get(memo, "schema"), 1) && pj_field(memo, "kind") &&
        !strcmp(pj_field(memo, "kind"), kind);
}
static PcJson *pc_memo_create(const char *kind) {
    PcJson *m = pj_new(PJ_OBJECT);
    pj_set_number(m, "schema", 1); pj_set_string(m, "kind", kind);
    return m;
}
/** Metadata is local evidence only; missing or invalid records always rehash. */
static char *pc_input_digest(PcContext *c, const char *path) {
    PcJson *now = pc_meta(path), *old = pj_get(c->old_files, path), *record;
    const char *digest = pj_field(old, "sha256");
    char hex[65];
    char *result;
    if (!now)
        return pc_fail(c, 2151, "cannot stat preparation input", path), NULL;
    if (!c->force && pc_hex_digest(digest) && pj_is_number(pj_get(now, "reliable"), 1) &&
        pj_equal(now, pj_get(old, "metadata")))
        result = pc_string(digest);
    else {
        pj_free(now);
        now = NULL;
        ++c->identity_reads;
        if (!pc_hash_file(path, hex, &now))
            return pc_fail(c, 2151, "cannot obtain stable preparation input digest", path), NULL;
        result = pc_string(hex);
    }
    if (!pj_get(c->new_files, path)) {
        record = pj_new(PJ_OBJECT);
        pj_set_string(record, "sha256", result);
        pj_add(record, "metadata", now);
        pj_add(c->new_files, path, record);
    } else
        pj_free(now);
    return result;
}
static char *pc_module_artifact(const char *name, const char *suffix, const char *top) {
    PcBuffer b = {0};
    const char *p;
    pc_text(&b, top);
    pc_char(&b, '/');
    for (p = name; *p; ++p)
        pc_char(&b, *p == '.' ? '/' : *p);
    pc_text(&b, suffix);
    return pc_take(&b);
}
static int pc_module_name(const char *name) {
    const unsigned char *p = (const unsigned char *)name;
    int first = 1;
    if (!p || !*p)
        return 0;
    for (; *p; ++p) {
        if (*p == '.') {
            if (first)
                return 0;
            first = 1;
            continue;
        }
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') || *p == '_' ||
              (!first && *p >= '0' && *p <= '9')))
            return 0;
        first = 0;
    }
    return !first;
}
static int pc_relative(const char *path) {
    const char *p, *start;
    if (!path || !*path || *path == '/' || strchr(path, '\\') || strchr(path, ':'))
        return 0;
    for (start = p = path;; ++p) {
        if (!*p || *p == '/') {
            size_t n = (size_t)(p - start);
            if (!n || (n == 1 && *start == '.') || (n == 2 && start[0] == '.' && start[1] == '.'))
                return 0;
            if (!*p)
                break;
            start = p + 1;
        } else if ((unsigned char)*p < 32)
            return 0;
    }
    return 1;
}
static const char *pc_runtime_archive(const char *variant) {
    if (!strcmp(variant, "traced"))
        return "lib/libdea_rt_traced.a";
    if (!strcmp(variant, "unchecked"))
        return "lib/libdea_rt_unchecked.a";
    if (!strcmp(variant, "check_basic"))
        return "lib/libdea_rt_check_basic.a";
    if (!strcmp(variant, "default"))
        return "lib/libdea_rt.a";
    return NULL;
}
static const char *const pc_runtime_sources[] = {
    "dea_rt_panic", "dea_rt_sys", "dea_rt_math", "dea_rt_rand", "dea_rt_string",
    "dea_rt_alloc", "dea_rt_io",  "dea_rt_hash", "dea_rt_time", NULL};

/** Expected roles come from the selected compiler's complete input inventory. */
static PcJson *pc_expected_artifacts(const PcJson *identity) {
    const PcJson *modules = pj_get(pj_get(identity, "dea_inputs"), "modules"), *m;
    const char *family = pj_field(pj_get(identity, "toolchain"), "family");
    const char *variant = pj_field(pj_get(identity, "runtime"), "variant"), *archive;
    PcJson *expected = pj_new(PJ_OBJECT);
    int i;
    if (!modules || modules->type != PJ_OBJECT || !pj_count(modules) || !family || !variant ||
        !(archive = pc_runtime_archive(variant))) goto invalid;
    for (m = modules->child; m; m = m->next) {
        char *path;
        if (!pc_module_name(m->key)) goto invalid;
        path = pc_module_artifact(m->key, ".l1m", "modules");
        pj_set_string(expected, path, "interface"); free(path);
        path = pc_module_artifact(m->key, ".o", "modules");
        pj_set_string(expected, path, "object"); free(path);
    }
    if (!strcmp(family, "tcc")) {
        for (i = !strcmp(variant, "traced") ? -1 : 0; i < 9; ++i) {
            PcBuffer b = {0};
            pc_text(&b, "lib/tcc/"); pc_text(&b, variant); pc_char(&b, '/');
            pc_text(&b, i == -1 ? "dea_rt_trace" : pc_runtime_sources[i]); pc_text(&b, ".o");
            pj_set_string(expected, b.s, "runtime"); free(b.s);
        }
    } else if (!strcmp(family, "gcc") || !strcmp(family, "clang"))
        pj_set_string(expected, archive, "runtime");
    else goto invalid;
    return expected;
invalid:
    pj_free(expected); return NULL;
}
static char *pc_entry_path(const char *root, const char *key) {
    char *directory = pc_join(root, "v1/native"), *entry = pc_join(directory, key);
    free(directory); return entry;
}
/**
 * Validate one completion record. Return 1 for a hit, 0 for unavailable, -1
 * for supported completed corruption. Only successful checks populate memos.
 */
static int pc_validate_entry_manifest(PcContext *c, const char *entry,
                                      int full, const char *manifest_name) {
    char *manifest_path = pc_join(entry, manifest_name), *raw = NULL, *identity_key = NULL,
         *resolved = NULL, *memo_key = NULL, *memo_path = NULL;
    size_t raw_size;
    PcJson *manifest = NULL, *expected = NULL, *memo = NULL, *validated = NULL, *files = NULL,
           *seen = NULL;
    const PcJson *identity, *inventory, *item;
    char manifest_digest[65];
    int outcome = -1, manifest_io_error = 0;
    raw = pc_read_file_checked(manifest_path, 16 * 1024 * 1024, &raw_size, &manifest_io_error);
    if (!raw) {
        if (manifest_io_error || pc_kind(manifest_path, 0) != 0) {
            pc_fail(c, 2153, "cannot read existing completion manifest", manifest_path);
            goto finish;
        }
        outcome = 0;
        goto finish;
    }
    manifest = pj_parse(raw, raw_size);
    if (!manifest || !pj_is_number(pj_get(manifest, "schema"), 1)) {
        goto malformed;
    }
    pc_sha_bytes(raw, raw_size, manifest_digest);
    identity = pj_get(manifest, "identity");
    inventory = pj_get(manifest, "artifacts");
    if (!identity || identity->type != PJ_OBJECT || !inventory || inventory->type != PJ_ARRAY ||
        !pj_field(manifest, "kind") ||
        strcmp(pj_field(manifest, "kind"), "native") ||
        !pj_field(manifest, "key") || strcmp(pj_field(manifest, "key"), c->native_key))
        goto malformed;
    identity_key = pc_json_digest(identity);
    if (strcmp(identity_key, c->native_key) || !pj_equal(c->native, identity))
        goto malformed;
    expected = pc_expected_artifacts(c->native);
    if (!expected || pj_count(expected) != pj_count(inventory))
        goto malformed;
    if (!pj_field(manifest, "D") || strcmp(pj_field(manifest, "D"), c->dea_key))
        goto malformed;
    resolved = pc_path_call(entry, l1c_fs_canonical_existing_path);
    if (!resolved) {
        pc_fail(c, 2153, "cannot resolve completed profile", entry);
        goto finish;
    }
    {
        char *canonical = pc_path_call(manifest_path, l1c_fs_canonical_existing_path);
        int safe = canonical && pc_within(canonical, resolved) && pc_kind(manifest_path, 1) == 1;
        free(canonical);
        if (!safe) {
            pc_fail(c, 2153, "escaped or nonregular completion manifest", manifest_path);
            goto finish;
        }
    }
    {
        PcJson *selection = pj_new(PJ_OBJECT);
        pj_set_string(selection, "entry", resolved);
        pj_set_string(selection, "manifest", manifest_digest);
        pj_set_number(selection, "validation_schema", 1);
        memo_key = pc_json_digest(selection);
        pj_free(selection);
    }
    memo_path = pc_memo_path(c, "artifacts", memo_key, 0);
    if (memo_path && !full)
        memo = pc_read_json(memo_path);
    if (!pc_memo_valid(memo, "artifact-validation") || !pj_field(memo, "entry") ||
        !pc_path_equal(pj_field(memo, "entry"), resolved) || !pj_field(memo, "manifest") ||
        strcmp(pj_field(memo, "manifest"), manifest_digest)) {
        pj_free(memo);
        memo = NULL;
    }
    if (pc_verbosity(c) >= 3)
        fprintf(stderr, "Preparation validation: %s (%s)\n", entry,
                memo ? "manifest reread; per-artifact metadata with changed-file hashing"
                     : "full inventory hashing");
    validated = pc_memo_create("artifact-validation");
    pj_set_string(validated, "entry", resolved);
    pj_set_string(validated, "manifest", manifest_digest);
    files = pj_new(PJ_OBJECT);
    pj_add(validated, "files", files);
    seen = pj_new(PJ_OBJECT);
    for (item = inventory->child; item; item = item->next) {
        const char *relative = pj_field(item, "path"), *digest = pj_field(item, "sha256");
        const PcJson *size = pj_get(item, "size");
        char *path, *canonical;
        PcJson *metadata, *old;
        int hit;
        const char *role;
        char actual[65];
        if (!pc_relative(relative) || !pc_hex_digest(digest) || !size || size->type != PJ_NUMBER ||
            size->number < 0 || pj_get(seen, relative) || !pj_get(expected, relative))
            goto malformed;
        role = pj_field(expected, relative);
        if (!pj_field(item, "role") || strcmp(pj_field(item, "role"), role))
            goto malformed;
        if (!strcmp(role, "interface")) {
            const char *semantic_digest = pj_field(c->interfaces, relative);
            if (!semantic_digest || strcmp(semantic_digest, digest))
                goto malformed;
        }
        pj_set_number(seen, relative, 1);
        path = pc_join(entry, relative);
        canonical = pc_path_call(path, l1c_fs_canonical_existing_path);
        if (!canonical || !pc_within(canonical, resolved) || pc_kind(path, 1) != 1) {
            pc_fail(c, 2153, "missing, escaped, or nonregular managed artifact", path);
            free(path);
            free(canonical);
            goto finish;
        }
        free(canonical);
        metadata = pc_meta(path);
        ++c->metadata_checks;
        if (!metadata || !pj_is_number(pj_get(metadata, "size"), size->number)) {
            pc_fail(c, 2153, "managed artifact size or metadata mismatch", path);
            pj_free(metadata);
            free(path);
            goto finish;
        }
        old = pj_get(pj_get(memo, "files"), relative);
        hit = !full && pj_is_number(pj_get(metadata, "reliable"), 1) && pj_field(old, "sha256") &&
              !strcmp(pj_field(old, "sha256"), digest) &&
              pj_equal(metadata, pj_get(old, "metadata"));
        if (!hit) {
            pj_free(metadata);
            metadata = NULL;
            ++c->artifact_reads;
            if (!pc_hash_file(path, actual, &metadata) ||
                strcmp(actual, digest)) {
                pc_fail(c, 2153, "managed artifact digest mismatch or unstable read", path);
                pj_free(metadata);
                free(path);
                goto finish;
            }
        }
        {
            PcJson *record = pj_new(PJ_OBJECT);
            pj_set_string(record, "sha256", digest);
            pj_add(record, "metadata", metadata);
            pj_add(files, relative, record);
        }
        free(path);
    }
    outcome = 1;
    if (!c->private_root && !full) {
        free(memo_path);
        memo_path = pc_memo_path(c, "artifacts", memo_key, 1);
        if (memo_path)
            pc_write_json(memo_path, validated);
    }
    goto finish;
malformed:
    pc_fail(c, 2153, "inconsistent completed preparation identity or artifact inventory",
            manifest_path);
finish:
    free(manifest_path);
    free(raw);
    free(identity_key);
    free(resolved);
    free(memo_key);
    free(memo_path);
    pj_free(manifest);
    pj_free(expected);
    pj_free(memo);
    pj_free(validated);
    pj_free(seen);
    return outcome;
}

/** Readers recognize only the final completion name, never a writer's pending bytes. */
static int pc_validate_entry(PcContext *c, const char *entry, int full) {
    return pc_validate_entry_manifest(c, entry, full, "manifest.json");
}

/** A detected completed failure is retained as recovery context, never consumed or repaired here. */
static int pc_find_profile(PcContext *c) {
    char *entry;
    int result;
    if (!c->native_key) return pc_fail(c, 2151, "native identity is unresolved", NULL), -1;
    if (c->ineligible || !c->local) return 0;
    entry = pc_entry_path(c->local, c->native_key);
    result = pc_validate_entry(c, entry, c->force);
    if (result == 1) { free(c->selected); c->selected = entry; return 1; }
    free(entry);
    if (result < 0) {
        free(c->unusable);
        c->unusable = pc_string(c->error ? c->error : "invalid completed native profile");
        pc_clear_error(c);
        return 2;
    }
    return 0;
}
/** Serialize absent/incomplete preparations by native key; OS ownership follows process lifetime. */
static int pc_acquire_profile(PcContext *c) {
    char *directory, *lockpath;
    PcBuffer name = {0};
    if (c->lock || !c->writable || !c->native_key || c->ineligible)
        return pc_fail(c, 2152, "persistent preparation requires an eligible identity and writable cache", c->local);
    directory = pc_join(c->local, "v1/locks");
    if (!pc_mkdirs(directory)) {
        pc_fail(c, 2152, "cannot create preparation coordination directory", directory);
        free(directory); return 0;
    }
    pc_text(&name, "native-"); pc_text(&name, c->native_key); pc_text(&name, ".lock");
    lockpath = pc_join(directory, name.s);
    free(name.s); free(directory);
    c->lock = pc_lock_file(lockpath);
    if (!c->lock) pc_fail(c, 2152, "cannot acquire preparation coordination", lockpath);
    free(lockpath);
    return c->lock != NULL;
}
#endif
