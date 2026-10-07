/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */
/** @file installation.h Shared native installed-prefix startup and inventory reader. */
#ifndef L1_INSTALLATION_H
#define L1_INSTALLATION_H
#include "preparation/json.h"
#include "preparation/sha256.h"
#include "preparation/platform.h"

#define INSTALL_MANIFEST "share/dea/l1/install-manifest.json"

/** Compare a required JSON string without dereferencing missing fields. */
static int install_text(const PcJson *j, const char *key, const char *expected) {
    const char *value = pj_field(j, key);
    return value && !strcmp(value, expected);
}
/** Validate portable version/host tokens independently of locale. */
static int install_token(const char *s, int target) {
    const char *p;
    if (!s || !*s) return 0;
    for (p = s; *p; ++p) {
        if ((*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') ||
            (!target && *p >= 'A' && *p <= 'Z')) continue;
        if (p == s || !strchr(target ? "_-" : "._+-", *p)) return 0;
    }
    return 1;
}
/** Validate a canonical portable inventory path, without filesystem traversal. */
static int install_path(const char *s) {
    const char *p, *start;
    if (!s || !*s) return 0;
    start = s;
    for (p = s; ; ++p) {
        unsigned char ch = (unsigned char)*p;
        if (!ch || ch == '/') {
            size_t n = (size_t)(p - start), i, stem;
            char lower[5] = {0};
            if (!n || start[n - 1] == '.' || start[n - 1] == ' ') return 0;
            for (stem = 0; stem < n && start[stem] != '.'; ++stem) {}
            if (stem <= 4) {
                for (i = 0; i < stem; ++i)
                    lower[i] = (char)tolower((unsigned char)start[i]);
                if (!strcmp(lower, "con") || !strcmp(lower, "prn") || !strcmp(lower, "aux") ||
                    !strcmp(lower, "nul") || (stem == 4 && lower[3] >= '1' && lower[3] <= '9' &&
                    (!strncmp(lower, "com", 3) || !strncmp(lower, "lpt", 3)))) return 0;
            }
            if (!ch) return 1;
            start = p + 1;
        } else if (ch < 32 || ch == 127 || strchr("\\:*?\"<>|", ch)) return 0;
    }
}
/** Resolve a relative alias lexically, rejecting escape from the prefix. */
static char *install_alias(const char *path, const char *target) {
    char *result, *slash;
    const char *p, *end;
    if (!target || !*target || *target == '/' || strchr(target, '\\')) return NULL;
    result = pc_alloc(strlen(path) + strlen(target) + 2);
    strcpy(result, path);
    slash = strrchr(result, '/');
    if (slash) *slash = 0; else *result = 0;
    for (p = target; ; p = end + 1) {
        char *part;
        end = strchr(p, '/');
        if (!end) end = p + strlen(p);
        part = pc_slice(p, (size_t)(end - p));
        if (!strcmp(part, "..")) {
            if (!*result) { free(part); free(result); return NULL; }
            slash = strrchr(result, '/');
            if (slash) *slash = 0; else *result = 0;
        } else if (install_path(part)) {
            if (*result) strcat(result, "/");
            strcat(result, part);
        } else { free(part); free(result); return NULL; }
        free(part);
        if (!*end) break;
    }
    if (!install_path(result)) { free(result); return NULL; }
    return result;
}
/** Check required complete-state structure; installers own payload hashing and preflight. */
static int install_inventory(const PcJson *record) {
    const PcJson *entries = pj_get(record, "entries"), *entry, *provenance = pj_get(record, "provenance");
    PcJson *paths = pj_new(PJ_OBJECT);
    int valid = 0, found = 0;
    if (!record || record->type != PJ_OBJECT || pj_count(record) != 10 ||
        !pj_is_number(pj_get(record, "schema_version"), 1) || !pj_is_number(pj_get(record, "stage"), 2) ||
        !install_text(record, "level", "l1") || !install_text(record, "state", "complete") ||
        !install_text(record, "maturity", "development") ||
        !install_token(pj_field(record, "package_version"), 0) ||
        !install_token(pj_field(record, "os"), 1) || !install_token(pj_field(record, "arch"), 1) ||
        !provenance || provenance->type != PJ_OBJECT || !pj_count(provenance) ||
        !entries || entries->type != PJ_ARRAY) goto done;
    for (entry = entries->child; entry; entry = entry->next) {
        const char *path = pj_field(entry, "path"), *kind = pj_field(entry, "kind");
        if (!install_path(path) || !kind || pj_get(paths, path)) goto done;
        if (!strcmp(kind, "file")) {
            const char *digest = pj_field(entry, "sha256");
            if (pj_count(entry) != 4 || !digest || strlen(digest) != 64 ||
                strspn(digest, "0123456789abcdef") != 64) goto done;
        } else if (!strcmp(kind, "manifest")) {
            if (pj_count(entry) != 3 || strcmp(path, INSTALL_MANIFEST) ||
                !pj_is_number(pj_get(entry, "mode"), 420)) goto done;
            found = 1;
        } else if (!strcmp(kind, "alias")) {
            char *destination;
            if (pj_count(entry) != 3) goto done;
            destination = install_alias(path, pj_field(entry, "target"));
            if (!destination) goto done;
            free(destination);
        } else goto done;
        if (strcmp(kind, "alias") && !pj_is_number(pj_get(entry, "mode"), 420) &&
            !pj_is_number(pj_get(entry, "mode"), 493)) goto done;
        pj_add(paths, path, pj_clone(entry));
    }
    for (entry = entries->child; entry; entry = entry->next) {
        const PcJson *current = entry;
        char *parent = pc_string(pj_field(entry, "path")), *slash;
        size_t hops = 0;
        while ((slash = strrchr(parent, '/')) != NULL) {
            *slash = 0;
            if (pj_get(paths, parent)) { free(parent); goto done; }
        }
        free(parent);
        while (install_text(current, "kind", "alias")) {
            char *destination = install_alias(pj_field(current, "path"), pj_field(current, "target"));
            current = destination ? pj_get(paths, destination) : NULL;
            free(destination);
            if (!current || install_text(current, "kind", "manifest") || ++hops > pj_count(entries)) goto done;
        }
    }
    valid = found;
done:
    pj_free(paths);
    return valid;
}
/** Validate installed state and select context before any compiler command. */
int32_t l1c_installation_startup(void) {
    char *executable = pc_self_executable(), *physical = NULL, *bin = NULL, *prefix = NULL;
    char *manifest = NULL, *contents = NULL, *parent = NULL;
    PcJson *record = NULL;
    size_t length = 0;
    int result = 1;
    const char *reason = "cannot resolve physical executable prefix";
    if (executable) physical = pc_path_call(executable, l1c_fs_canonical_existing_path);
    if (!physical) goto done;
    bin = pc_parent(physical);
#if defined(_WIN32)
    if (_stricmp(pc_base(bin), "bin")) goto done;
#else
    if (strcmp(pc_base(bin), "bin")) goto done;
#endif
    prefix = pc_parent(bin);
    manifest = pc_join(prefix, INSTALL_MANIFEST);
    reason = "missing, unreadable, or substituted installation metadata";
    parent = pc_parent(manifest);
    while (strcmp(parent, prefix)) {
        char *next;
        if (pc_kind(parent, 0) != 2) goto done;
        next = pc_parent(parent);
        if (!strcmp(next, parent)) { free(next); goto done; }
        free(parent); parent = next;
    }
    if (pc_kind(manifest, 0) != 1) goto done;
    contents = pc_read_file(manifest, 16 * 1024 * 1024, &length);
    if (!contents) goto done;
    record = pj_parse_mode(contents, length, 1);
    reason = "malformed, unsupported, or incomplete installation metadata";
    if (!install_inventory(record)) goto done;
    reason = "cannot select installed environment";
#if defined(_WIN32)
    if (_putenv_s("L1_HOME", prefix) || _putenv_s("L1_BUILD_DIR", "")) goto done;
#else
    if (setenv("L1_HOME", prefix, 1) || unsetenv("L1_BUILD_DIR")) goto done;
#endif
    result = 0;
done:
    if (result) fprintf(stderr, "error: [L1C-9515] %s at '%s'; repair or retry installation\n",
                        reason, manifest ? manifest : (physical ? physical : "<executable>"));
    pj_free(record);
    free(parent); free(contents); free(manifest); free(prefix); free(bin); free(physical); free(executable);
    return result;
}
#endif
