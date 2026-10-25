/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file storage.h Single-root native profiles and disposable validation memos.
 */
#ifndef L1_PREPARATION_STORAGE_H
#define L1_PREPARATION_STORAGE_H

/**
 * Construction borrows a caller-owned destination and owns its immutable inputs/result.
 */
typedef struct {
    PcJson *inputs, *expected, *inventory;
    char *root;
    int active;
} PcConstruction;

typedef struct {
    PcJson *config, *options, *runtime_options, *dea, *native, *modules, *interfaces;
    PcJson *old_files, *new_files, *digest_donor, *legacy_configuration;
    char *digest_seed_key;
    int digest_seed_loaded;
    char *local, *home, *compiler, *self, *semantic_root, *include;
    char *dea_key, *native_key, *selected, *error, *description, *family, *archiver;
    char *private_root, *ineligible, *unusable;
    char *clang_config_directory, *clang_config_path;
    int clang_isolation;
    int error_code, force, native_resolved, begun, explicit_root, writable, installed, runtime_config_observed;
    int64_t identity_reads, artifact_reads, probes, metadata_checks, resolutions;
    int64_t build_commands, module_compiles;
    int64_t option_file_parses, option_root_expansions;
    PcLock *lock;
    PcConstruction *construction;
    PcJson *profile, *profile_headers;
    char *profile_destination, *profile_stage;
    int profile_manifest_written;
} PcContext;

/* Read the configured preparation diagnostic verbosity. */
static int pc_verbosity(PcContext *c);

/**
 * Avoid observation clock calls outside debug verbosity.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Monotonic start in milliseconds at debug verbosity; zero when observations are disabled.
 */
static double pc_observation_start(PcContext *c) {
    return c && pc_verbosity(c) >= 3 ? pc_milliseconds() : 0;
}

/**
 * Emit one machine-readable debug observation without retaining persistent state.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param record Owned observation record consumed and freed even when debug output is disabled.
 */
static void pc_observe(PcContext *c, PcJson *record) {
    if (pc_verbosity(c) >= 3) {
        char *encoded;
        pj_set_number(record, "schema", 1);
        encoded = pj_encode(record);
        fprintf(stderr, "Preparation observation: %s\n", encoded);
        free(encoded);
    }
    pj_free(record);
}

/**
 * Create an owned preparation observation record with an event name.
 *
 * @param event Borrowed observation event label.
 * @return Owned JSON record consumed by pc_observe or released with pj_free.
 */
static PcJson *pc_observation(const char *event) {
    PcJson *record = pj_new(PJ_OBJECT);
    pj_set_string(record, "event", event);
    return record;
}

/**
 * Emit one inclusive debug timing span when observation verbosity is enabled.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param name Borrowed NUL-terminated name.
 * @param started Monotonic observation start in milliseconds.
 * @param success Nonzero when the observed operation succeeded.
 */
static void pc_observe_span(PcContext *c, const char *name, double started, int success) {
    if (pc_verbosity(c) < 3) return;
    PcJson *record = pc_observation("span");
    pj_set_string(record, "name", name);
    pj_set_number(record, "inclusive", 1);
    pj_set_number(record, "elapsed_us", (int64_t)((pc_milliseconds() - started) * 1000.0));
    pj_set_number(record, "success", success ? 1 : 0);
    pc_observe(c, record);
}

/**
 * Emit one debug reuse decision and its optional path when enabled.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param scope Borrowed observation scope label.
 * @param decision Borrowed reuse decision label.
 * @param reason Borrowed diagnostic or observation reason.
 * @param path Borrowed NUL-terminated filesystem path.
 */
static void pc_observe_decision(PcContext *c, const char *scope, const char *decision,
                                const char *reason, const char *path) {
    if (pc_verbosity(c) < 3) return;
    PcJson *record = pc_observation("decision");
    pj_set_string(record, "scope", scope);
    pj_set_string(record, "decision", decision);
    pj_set_string(record, "reason", reason);
    if (path) pj_set_string(record, "path", path);
    pc_observe(c, record);
}

/**
 * Classify recorded native metadata for diagnostic observations.
 *
 * @param metadata Metadata evidence read or updated by this operation.
 * @return Borrowed constant string naming file, directory, or unknown metadata.
 */
static const char *pc_metadata_kind(const PcJson *metadata) {
    const PcJson *mode = pj_get(metadata, "mode");
    if (!mode || mode->type != PJ_NUMBER) return "unknown";
#if defined(_WIN32)
    return (mode->number & FILE_ATTRIBUTE_DIRECTORY) ? "directory" : "file";
#else
    return S_ISDIR((mode_t)mode->number) ? "directory" : "file";
#endif
}

/**
 * Append a copied JSON value or explicit null to a diagnostic record.
 *
 * @param record JSON observation or metadata record updated by the operation.
 * @param key Borrowed NUL-terminated object or identity key.
 * @param value Borrowed value to clone, or NULL to append explicit JSON null.
 */
static void pc_add_optional_value(PcJson *record, const char *key, const PcJson *value) {
    pj_add(record, key, value ? pj_clone(value) : pj_new(PJ_NULL));
}

/**
 * Allocate the complete difference map only after finding an unequal field.
 *
 * @param differences Optional owned difference map allocated on the first mismatch.
 * @param field Borrowed field name or bounded field-name bytes.
 * @param previous Borrowed previous metadata value.
 * @param current Borrowed current metadata value.
 */
static void pc_add_metadata_difference(PcJson **differences, const char *field,
                                       const PcJson *previous, const PcJson *current) {
    PcJson *values;
    if (pj_equal(previous, current)) return;
    if (!*differences) *differences = pj_new(PJ_OBJECT);
    values = pj_new(PJ_OBJECT);
    if (previous) pj_add(values, "previous", pj_clone(previous));
    if (current) pj_add(values, "current", pj_clone(current));
    pj_add(*differences, field, values);
}

/**
 * Report every field difference while retaining the first-field compatibility view.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param scope Borrowed observation scope label.
 * @param path Borrowed NUL-terminated filesystem path.
 * @param previous Borrowed previous metadata value.
 * @param current Borrowed current metadata value.
 */
static void pc_observe_metadata_mismatch(PcContext *c, const char *scope, const char *path,
                                         const PcJson *previous, const PcJson *current) {
    static const char *const fields[] = {"device", "inode", "size", "mode", "mtime", "mtime_ns",
                                         "ctime", "ctime_ns", "reliable", NULL};
    const PcJson *item;
    PcJson *differences = NULL;
    const char *field = "entry";
    int i;
    if (pc_verbosity(c) < 3) return;
    if (previous && previous->type == PJ_OBJECT && current && current->type == PJ_OBJECT) {
        for (i = 0; fields[i]; ++i) {
            if (!pj_equal(pj_get(previous, fields[i]), pj_get(current, fields[i]))) {
                field = fields[i];
                break;
            }
        }
        for (item = previous->child; item; item = item->next)
            pc_add_metadata_difference(&differences, item->key, item, pj_get(current, item->key));
        for (item = current->child; item; item = item->next)
            if (!pj_get(previous, item->key))
                pc_add_metadata_difference(&differences, item->key, NULL, item);
    }
    {
        PcJson *record = pc_observation("metadata-mismatch");
        pj_set_string(record, "scope", scope);
        pj_set_string(record, "path", path);
        pj_set_string(record, "kind", pc_metadata_kind(current ? current : previous));
        pj_set_string(record, "field", field);
        if (!strcmp(field, "entry")) {
            pc_add_optional_value(record, "previous", previous);
            pc_add_optional_value(record, "current", current);
        } else {
            pc_add_optional_value(record, "previous", previous ? pj_get(previous, field) : NULL);
            pc_add_optional_value(record, "current", current ? pj_get(current, field) : NULL);
        }
        if (differences) pj_add(record, "differences", differences);
        pc_observe(c, record);
    }
}

/**
 * Hash a stable file and optionally emit debug cost observations.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param path Borrowed NUL-terminated filesystem path.
 * @param digest Caller-owned 65-byte buffer for a NUL-terminated SHA-256 digest.
 * @param metadata Optional output receiving owned stable descriptor metadata on success.
 * @param category Borrowed observation category label.
 * @param reason Borrowed diagnostic or observation reason.
 * @return Nonzero on a stable complete read; zero on file or metadata failure.
 */
static int pc_hash_observed(PcContext *c, const char *path, char digest[65], PcJson **metadata,
                            const char *category, const char *reason) {
    if (pc_verbosity(c) < 3)
        return pc_hash_file_measured(path, digest, metadata, NULL, NULL);
    int64_t bytes = 0;
    double elapsed = 0;
    int ok = pc_hash_file_measured(path, digest, metadata, &bytes, &elapsed);
    PcJson *record = pc_observation("hash");
    pj_set_string(record, "category", category);
    pj_set_string(record, "path", path);
    pj_set_string(record, "reason", reason);
    pj_set_number(record, "bytes", bytes);
    pj_set_number(record, "elapsed_us", (int64_t)(elapsed * 1000.0));
    pj_set_number(record, "success", ok ? 1 : 0);
    pc_observe(c, record);
    return ok;
}

/**
 * Retain the first actionable error; cleanup must not hide its cause.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param code Diagnostic code to retain.
 * @param reason Borrowed diagnostic or observation reason.
 * @param path Borrowed NUL-terminated filesystem path.
 * @return Always zero, allowing the retained diagnostic to be returned as failure.
 */
static int pc_fail(PcContext *c, int code, const char *reason, const char *path) {
    PcBuffer b = {0};
    if (c->error) return 0;
    pc_text(&b, reason);
    if (path && *path) { pc_text(&b, ": "); pc_text(&b, path); }
    c->error = pc_take(&b);
    c->error_code = code;
    return 0;
}

/**
 * Release the saved preparation diagnostic and reset its error code.
 *
 * @param c Mutable preparation context owned by the consuming command.
 */
static void pc_clear_error(PcContext *c) {
    free(c->error); c->error = NULL; c->error_code = 0;
}

/**
 * Read a borrowed environment value with an empty-string fallback.
 *
 * @param key Borrowed NUL-terminated object or identity key.
 * @return Borrowed environment text, or a constant empty string when unset.
 */
static const char *pc_env(const char *key) {
    const char *s = getenv(key);
    return s ? s : "";
}

/**
 * Read the configured preparation diagnostic verbosity.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Configured integer verbosity, or zero when absent or not an integer.
 */
static int pc_verbosity(PcContext *c) {
    const PcJson *v = pj_get(c->config, "verbosity");
    return v && v->type == PJ_NUMBER ? (int)v->number : 0;
}

/**
 * Read a borrowed string configuration field with an empty fallback.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param key Borrowed NUL-terminated object or identity key.
 * @return Borrowed string value, or a constant empty string when absent or not a string.
 */
static const char *pc_config(PcContext *c, const char *key) {
    const char *s = pj_field(c->config, key);
    return s ? s : "";
}

/**
 * Construct the platform-specific default installed preparation cache path.
 * @return Owned cache path, or NULL when required environment roots are unavailable.
 */
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

/**
 * Resolve toolchain-owned paths without hashing inputs or touching native storage.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero after resolving toolchain-owned paths; zero after recording invalid toolchain selection.
 */
static int pc_toolchain_paths(PcContext *c) {
    const char *build = pc_config(c, "build_dir");
    char *repo_marker, *derived = NULL, *base;
    c->home = pc_path_call(pc_config(c, "home"), l1c_fs_absolute_path);
    if (!c->home) return pc_fail(c, 2151, "cannot locate L1 toolchain inputs; rebuild bootstrap or repair installation", NULL);
    repo_marker = pc_join(c->home, "src");
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

/**
 * Test only the Dea-owned subtree, never treating its caller-selected parent as disposable.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero when an exclusive write probe in the owned subtree succeeds.
 */
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

/**
 * Resolve one root and enforce installed-payload ownership before any managed write.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero after selecting a safe cache policy; zero after recording overlap or explicit-root
 * failure.
 */
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

/**
 * Construct an optional memo path, creating its directory only when requested.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param kind Requested record or artifact kind.
 * @param key Borrowed NUL-terminated object or identity key.
 * @param create Nonzero to create the required memo directory.
 * @return Owned path, or NULL when memo storage is unavailable or directory creation fails.
 */
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

/**
 * Check the memo schema and exact record kind.
 *
 * @param memo Borrowed optional memo record.
 * @param kind Requested record or artifact kind.
 * @return Nonzero only for a compatible memo of the requested kind.
 */
static int pc_memo_valid(const PcJson *memo, const char *kind) {
    return memo && pj_is_number(pj_get(memo, "schema"), 1) && pj_field(memo, "kind") &&
        !strcmp(pj_field(memo, "kind"), kind);
}

/**
 * Create an owned versioned memo envelope of the requested kind.
 *
 * @param kind Requested record or artifact kind.
 * @return Owned JSON object released with pj_free.
 */
static PcJson *pc_memo_create(const char *kind) {
    PcJson *m = pj_new(PJ_OBJECT);
    pj_set_number(m, "schema", 1); pj_set_string(m, "kind", kind);
    return m;
}

/**
 * Read at most one optional donor; its discovery is never consulted.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Borrowed candidate file evidence owned by the context, or NULL when no usable donor memo is
 * available.
 */
static const PcJson *pc_digest_seed_files(PcContext *c) {
    char *path;
    PcJson *hint;
    const char *key;
    int status;
    if (!c->digest_seed_key || c->force || c->ineligible || c->private_root) return NULL;
    if (c->digest_seed_loaded) return pj_get(c->digest_donor, "files");
    c->digest_seed_loaded = 1;
    path = pc_memo_path(c, "digest-seeds", c->digest_seed_key, 0);
    hint = pc_read_json_status(path, &status);
    key = pj_field(hint, "memo_key");
    if (!pc_memo_valid(hint, "input-digest-seed") || !pc_hex_digest(key)) {
        pc_observe_decision(c, "digest-seed-hint", "miss",
                            status == PC_JSON_ABSENT ? "no-matching-memo" :
                            status == PC_JSON_UNREADABLE ? "unreadable-memo" : "malformed-memo", path);
        free(path); pj_free(hint); return NULL;
    }
    pc_observe_decision(c, "digest-seed-hint", "hit", "candidate-memo", path);
    free(path);
    path = pc_memo_path(c, "toolchains", key, 0);
    c->digest_donor = pc_read_json_status(path, &status);
    pj_free(hint);
    if (!pc_memo_valid(c->digest_donor, "identity") || !pj_get(c->digest_donor, "files") ||
        pj_get(c->digest_donor, "files")->type != PJ_OBJECT) {
        pc_observe_decision(c, "digest-seed-donor", "miss",
                            status == PC_JSON_ABSENT ? "no-matching-memo" :
                            status == PC_JSON_UNREADABLE ? "unreadable-memo" : "malformed-memo", path);
        pj_free(c->digest_donor); c->digest_donor = NULL;
    } else
        pc_observe_decision(c, "digest-seed-donor", "hit", "candidate-files", path);
    free(path);
    return pj_get(c->digest_donor, "files");
}

/**
 * An optional record is usable only against current reliable file metadata.
 *
 * @param old Borrowed previous metadata or memo evidence.
 * @param now Borrowed current metadata evidence.
 * @return Borrowed rejection reason, or NULL when reliable current metadata authorizes reuse.
 */
static const char *pc_digest_rejection(const PcJson *old, const PcJson *now) {
    if (!old) return "memo-entry-absent";
    if (!pc_hex_digest(pj_field(old, "sha256"))) return "memo-digest-invalid";
    if (!pj_is_number(pj_get(now, "reliable"), 1)) return "metadata-unreliable";
    if (!pj_equal(now, pj_get(old, "metadata"))) return "metadata-changed";
    return NULL;
}

/**
 * Metadata is local evidence only; missing or invalid records always rehash.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param path Borrowed NUL-terminated filesystem path.
 * @param category Borrowed observation category label.
 * @return Owned lowercase SHA-256 string, or NULL after recording an input failure.
 */
static char *pc_input_digest(PcContext *c, const char *path, const char *category) {
    PcJson *now = pc_meta(path), *old = pj_get(c->old_files, path), *record;
    const char *reason;
    char hex[65];
    char *result;
    if (!now)
        return pc_fail(c, 2151, "cannot stat preparation input", path), NULL;
    reason = c->force ? "force" : pc_digest_rejection(old, now);
    if (reason && !c->force && c->digest_seed_key && !c->ineligible && !c->private_root) {
        PcJson *donor = pj_get(pc_digest_seed_files(c), path);
        const char *rejection = pc_digest_rejection(donor, now);
        pc_observe_decision(c, "input-digest", rejection ? "miss" : "hit",
                            rejection ? rejection : "validated-donor-record", path);
        if (!rejection) { old = donor; reason = NULL; }
    } else if (!reason)
        pc_observe_decision(c, "input-digest", "hit", "validated-current-record", path);
    if (!reason)
        result = pc_string(pj_field(old, "sha256"));
    else {
        pc_observe_decision(c, "input-digest", "fallback", reason, path);
        if (pc_verbosity(c) >= 3 && old && !pj_equal(now, pj_get(old, "metadata")))
            pc_observe_metadata_mismatch(c, category, path, pj_get(old, "metadata"), now);
        pj_free(now);
        now = NULL;
        ++c->identity_reads;
        if (!pc_hash_observed(c, path, hex, &now, category, reason))
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

/**
 * Construct the relative artifact path for a validated dotted module name.
 *
 * @param name Borrowed NUL-terminated name.
 * @param suffix Borrowed exact suffix bytes.
 * @param top Borrowed artifact root component.
 * @return Owned artifact path released with free.
 */
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

/**
 * Validate a dotted compiler module name for artifact construction.
 *
 * @param name Borrowed NUL-terminated name.
 * @return Nonzero for a supported nonempty module spelling.
 */
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

/**
 * Validate a relative artifact path against traversal and absolute spellings.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @return Nonzero only for a permitted nonempty relative path.
 */
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

/**
 * Choose the runtime archive filename for the selected runtime variant.
 *
 * @param variant Borrowed runtime configuration variant name.
 * @return Borrowed constant archive filename, or NULL for an unknown variant.
 */
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

/**
 * Payload roles depend only on the semantic set and normalized native configuration.
 *
 * @param modules Module inventory read or populated by this operation.
 * @param family Borrowed native compiler family name.
 * @param variant Borrowed runtime configuration variant name.
 * @return Owned payload-role inventory, or NULL for invalid module or runtime configuration.
 */
static PcJson *pc_payload_artifacts(const PcJson *modules, const char *family, const char *variant) {
    const PcJson *m;
    const char *archive;
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

/**
 * Managed validation derives the same roles from its existing identity format.
 *
 * @param identity Borrowed exact native identity record.
 * @return Owned expected payload-role inventory, or NULL for invalid native identity data.
 */
static PcJson *pc_expected_artifacts(const PcJson *identity) {
    return pc_payload_artifacts(pj_get(pj_get(identity, "dea_inputs"), "modules"),
        pj_field(pj_get(identity, "toolchain"), "family"),
        pj_field(pj_get(identity, "runtime"), "variant"));
}

/**
 * Validate common record fields against the role authorized by the policy adapter.
 *
 * @param item Borrowed payload inventory record.
 * @param expected_role Borrowed required payload role name.
 * @param seen Borrowed inventory of already observed payload paths.
 * @return Nonzero for a valid authorized record; zero for an invalid or duplicate payload.
 */
static int pc_payload_record(const PcJson *item, const char *expected_role, const PcJson *seen) {
    const char *path = pj_field(item, "path"), *role = pj_field(item, "role"),
               *digest = pj_field(item, "sha256");
    const PcJson *size = pj_get(item, "size");
    return pc_relative(path) && role && expected_role && !strcmp(role, expected_role) &&
        pc_hex_digest(digest) && size && size->type == PJ_NUMBER && size->number >= 0 && !pj_get(seen, path);
}

/**
 * Check containment and file kind without reading bytes or imposing public alias policy on managed
 * entries.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param root Borrowed root path.
 * @param no_alias Nonzero to reject filesystem aliases.
 * @return Nonzero for a contained regular payload; zero for invalid kind or forbidden aliasing.
 */
static int pc_payload_regular(const char *path, const char *root, int no_alias) {
    char *canonical = pc_path_call(path, l1c_fs_canonical_existing_path);
    int ok = canonical && pc_within(canonical, root) &&
        (!no_alias || pc_path_equal(canonical, path)) && pc_kind(path, !no_alias) == 1;
    free(canonical);
    return ok;
}

/**
 * Verify selected content; callers own hash scheduling, counters, memo authority and diagnostics.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param path Borrowed NUL-terminated filesystem path.
 * @param digest Caller-owned 65-byte buffer for a NUL-terminated SHA-256 digest.
 * @param size Borrowed JSON integer containing the expected payload byte length.
 * @param metadata Metadata evidence read or updated by this operation.
 * @param phase Borrowed construction phase label.
 * @param reason Borrowed diagnostic or observation reason.
 * @return Nonzero for matching payload bytes; zero when hashing or digest comparison fails.
 */
static int pc_payload_digest(PcContext *c, const char *path, const char *digest, const PcJson *size,
                             PcJson **metadata, const char *phase, const char *reason) {
    char actual[65];
    return pc_hash_observed(c, path, actual, metadata, phase, reason) &&
        (!size || pj_is_number(pj_get(*metadata, "size"), size->number)) && !strcmp(actual, digest);
}

/**
 * Construct the managed native profile directory for an identity key.
 *
 * @param root Borrowed root path.
 * @param key Borrowed NUL-terminated object or identity key.
 * @return Owned entry path released with free.
 */
static char *pc_entry_path(const char *root, const char *key) {
    char *directory = pc_join(root, "v1/native"), *entry = pc_join(directory, key);
    free(directory); return entry;
}

/**
 * Validate one completion record. Return 1 for a hit, 0 for unavailable, -1
 * for supported completed corruption. Only successful checks populate memos.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param entry Borrowed profile entry directory.
 * @param full Nonzero to verify payload contents in addition to manifest structure.
 * @param manifest_name Borrowed completion-manifest filename.
 * @return One for valid completion, zero for absence or incomplete state, or -1 for invalid completed
 * state.
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
    int outcome = -1, manifest_io_error = 0, memo_status = PC_JSON_ABSENT;
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
        memo = pc_read_json_status(memo_path, &memo_status);
    if (!pc_memo_valid(memo, "artifact-validation") || !pj_field(memo, "entry") ||
        !pc_path_equal(pj_field(memo, "entry"), resolved) || !pj_field(memo, "manifest") ||
        strcmp(pj_field(memo, "manifest"), manifest_digest)) {
        pj_free(memo);
        memo = NULL;
    }
    pc_observe_decision(c, "artifact-validation-memo", memo ? "hit" : "miss",
                        full ? "full-validation" : memo_status == PC_JSON_ABSENT ? "no-matching-memo" :
                        memo_status == PC_JSON_UNREADABLE ? "unreadable-memo" :
                        memo_status == PC_JSON_MALFORMED ? "malformed-memo" :
                        memo ? "validated-memo" : "memo-identity-mismatch", memo_path);
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
        char *path;
        PcJson *metadata, *old;
        int hit;
        const char *role;
        role = relative ? pj_field(expected, relative) : NULL;
        if (!pc_payload_record(item, role, seen))
            goto malformed;
        if (!strcmp(role, "interface")) {
            const char *semantic_digest = pj_field(c->interfaces, relative);
            if (!semantic_digest || strcmp(semantic_digest, digest))
                goto malformed;
        }
        pj_set_number(seen, relative, 1);
        path = pc_join(entry, relative);
        if (!pc_payload_regular(path, resolved, 0)) {
            pc_fail(c, 2153, "missing, escaped, or nonregular managed artifact", path);
            free(path);
            goto finish;
        }
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
            const char *reason = full ? "full-validation" : !old ? "memo-entry-absent" :
                !pc_hex_digest(pj_field(old, "sha256")) ? "memo-digest-invalid" :
                strcmp(pj_field(old, "sha256"), digest) ? "memo-digest-mismatch" :
                !pj_is_number(pj_get(metadata, "reliable"), 1) ? "metadata-unreliable" : "metadata-changed";
            if (pc_verbosity(c) >= 3 && old && !pj_equal(metadata, pj_get(old, "metadata")))
                pc_observe_metadata_mismatch(c, "artifact", path, pj_get(old, "metadata"), metadata);
            pj_free(metadata);
            metadata = NULL;
            ++c->artifact_reads;
            if (!pc_payload_digest(c, path, digest, NULL, &metadata,
                                   full ? "publication" : "artifact-validation", reason)) {
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

/**
 * Readers recognize only the final completion name, never a writer's pending bytes.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @param entry Borrowed profile entry directory.
 * @param full Nonzero to verify payload contents in addition to manifest structure.
 * @return One for valid completion, zero for absence or incomplete state, or -1 for invalid completed
 * state.
 */
static int pc_validate_entry(PcContext *c, const char *entry, int full) {
    return pc_validate_entry_manifest(c, entry, full, "manifest.json");
}

/**
 * A detected completed failure is retained as recovery context, never consumed or repaired here.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return One for a validated hit, zero for a miss, two for unusable completion, or -1 for error.
 */
static int pc_find_profile(PcContext *c) {
    char *entry;
    int result;
    if (!c->native_key) return pc_fail(c, 2151, "native identity is unresolved", NULL), -1;
    if (c->ineligible || !c->local) {
        pc_observe_decision(c, "native-profile", "miss", c->ineligible ? "ineligible" : "no-cache-root", NULL);
        return 0;
    }
    entry = pc_entry_path(c->local, c->native_key);
    result = pc_validate_entry(c, entry, c->force);
    if (result == 1) {
        pc_observe_decision(c, "native-profile", "hit", "validated-profile", entry);
        free(c->selected); c->selected = entry; return 1;
    }
    if (result < 0) {
        pc_observe_decision(c, "native-profile", "unusable", "invalid-completed-profile", entry);
        free(entry);
        free(c->unusable);
        c->unusable = pc_string(c->error ? c->error : "invalid completed native profile");
        pc_clear_error(c);
        return 2;
    }
    pc_observe_decision(c, "native-profile", "miss", "profile-absent", entry);
    free(entry);
    return 0;
}

/**
 * Serialize absent/incomplete preparations by native key; OS ownership follows process lifetime.
 *
 * @param c Mutable preparation context owned by the consuming command.
 * @return Nonzero after acquiring the exclusive profile lock; zero after recording a coordination failure.
 */
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
