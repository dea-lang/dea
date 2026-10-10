/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file libraries.h Cold discovery of dynamically loaded compiler implementation components. */
#ifndef L1_PREPARATION_LIBRARIES_H
#define L1_PREPARATION_LIBRARIES_H

#if defined(_WIN32)
#include "pe_imports.h"
#endif

#if defined(__APPLE__)
/** Expand the Mach-O loader placeholders whose base is explicit in the image. */
static char *pc_loader_path(const char *name, const char *binary, const char *executable) {
    const char *tail = NULL;
    char *base, *result;
    if (!strncmp(name, "@loader_path/", 13)) {
        tail = name + 13;
        base = pc_parent(binary);
    } else if (!strncmp(name, "@executable_path/", 17)) {
        tail = name + 17;
        base = pc_parent(executable);
    } else
        return pc_string(name);
    result = pc_join(base, tail);
    free(base);
    return result;
}
#endif

/** Inspect native images only; scripts are opaque adapters, not shared-library inventories. */
static int pc_image_kind(const char *path) {
    unsigned char magic[4];
    FILE *file = fopen(path, "rb");
    size_t n;
    if (!file)
        return 0;
    n = fread(magic, 1, sizeof(magic), file);
    fclose(file);
    if (n != 4)
        return 0;
#if defined(__APPLE__)
    return (magic[0] == 0xcf && magic[1] == 0xfa) || (magic[0] == 0xce && magic[1] == 0xfa) ||
           (magic[0] == 0xca && magic[1] == 0xfe) || (magic[0] == 0xfe && magic[1] == 0xed);
#elif defined(_WIN32)
    return magic[0] == 'M' && magic[1] == 'Z';
#else
    return !memcmp(magic, "\177ELF", 4);
#endif
}

#if !defined(__APPLE__) && !defined(_WIN32)
/** Record ELF loader search candidates without loading each library in a new context. */
static int pc_elf_searches(PcContext *c, const char *image, PcJson *dependencies,
                           const char *reader) {
    PcJson *words = pj_new(PJ_ARRAY);
    PcProbe probe;
    const char *line, *end;
    int ok = 1;
    char *parent = pc_parent(image);
    if (!reader) {
        pj_free(words);
        free(parent);
        return pc_fail(c, 2154, "readelf is required for ELF compiler discovery", image);
    }
    pj_add(words, NULL, pj_string(reader));
    pj_add(words, NULL, pj_string("-d"));
    pj_add(words, NULL, pj_string(image));
    probe = pc_context_probe(c, words, "ELF dynamic entries");
    if (!pc_probe_ok(c, &probe, "ELF loader search paths"))
        ok = 0;
    for (line = probe.out; *line && ok; line = *end ? end + 1 : end) {
        char *record, *start, *stop;
        end = strchr(line, '\n');
        if (!end)
            end = line + strlen(line);
        record = pc_slice(line, (size_t)(end - line));
        start = strchr(record, '[');
        stop = strrchr(record, ']');
        if ((strstr(record, "(RPATH)") || strstr(record, "(RUNPATH)")) && start && stop > start) {
            PcBuffer expanded = {0};
            ++start;
            *stop = 0;
            while (*start && ok) {
                if (!strncmp(start, "$ORIGIN", 7)) {
                    pc_text(&expanded, parent);
                    start += 7;
                } else if (!strncmp(start, "${ORIGIN}", 9)) {
                    pc_text(&expanded, parent);
                    start += 9;
                } else if (*start == '$')
                    ok = pc_fail(c, 2154, "unsupported ELF loader path token", start);
                else
                    pc_char(&expanded, *start++);
            }
            if (ok && expanded.s)
                pc_path_list_dependencies(dependencies, expanded.s);
            free(expanded.s);
        }
        free(record);
    }
    pc_probe_free(&probe);
    free(parent);
    return ok;
}
#endif

/** Bound library discovery, then remember its exact files and loader search inputs. */
static int pc_implementation_libraries(PcContext *c, PcJson *paths, PcJson *dependencies) {
    const PcJson *image;
#if !defined(_WIN32)
    char *inspector;
#endif
    PcJson *processed = pj_new(PJ_OBJECT);
#if defined(__APPLE__) || defined(_WIN32)
    PcJson *origins = pj_new(PJ_OBJECT);
#if defined(__APPLE__)
    PcJson *searches = pj_new(PJ_OBJECT);
#endif
#else
    PcJson *originals = pj_clone(paths);
    char *reader = pc_executable("readelf");
    pc_add_component(paths, "/etc/ld.so.cache");
    pc_add_component(paths, "/etc/ld.so.preload");
    pc_dependency(dependencies, "/etc/ld.so.cache");
    pc_dependency(dependencies, "/etc/ld.so.preload");
#endif
    int count = 0, ok = 1;
#if defined(__APPLE__)
    inspector = pc_executable("otool");
#elif !defined(_WIN32)
    inspector = pc_executable("ldd");
#endif
    for (image = paths->child; image && ok; image = image->next) {
#if defined(_WIN32)
        PcJson *imports;
        const PcJson *import;
#else
        PcJson *words;
        PcProbe probe;
        const char *line, *end;
#endif
#if defined(__APPLE__) || defined(_WIN32)
        const char *origin = pj_field(origins, image->key);
        if (!origin)
            origin = image->key;
#endif
#if defined(__APPLE__)
        PcJson *rpaths;
        int first_library = 1;
        rpaths = pj_get(searches, origin);
        if (!rpaths) {
            rpaths = pj_new(PJ_OBJECT);
            pj_add(searches, origin, rpaths);
        }
#endif
        char *canonical = pc_path_call(image->key, l1c_fs_canonical_existing_path);
        if (!canonical || pj_get(processed, canonical) || !pc_image_kind(image->key)) {
            free(canonical);
            continue;
        }
        pj_set_number(processed, canonical, 1);
        free(canonical);
        if (++count > 256
#if !defined(_WIN32)
            || !inspector
#endif
        ) {
            ok = pc_fail(c, 2154, "cannot inspect compiler implementation libraries", image->key);
            break;
        }
#if !defined(__APPLE__) && !defined(_WIN32)
        if (!pc_elf_searches(c, image->key, dependencies, reader)) {
            ok = 0;
            break;
        }
        /* ldd gives the complete closure in the executable's loader context.
           Re-running it on children would lose inherited RPATH semantics. */
        if (!pj_get(originals, image->key))
            continue;
#endif
#if defined(_WIN32)
        imports = pc_pe_imports(c, image->key);
        if (!imports) { ok = 0; break; }
        for (import = imports->child; import && ok; import = import->next) {
            const char *name = import->text;
            char *path = NULL;
#else
        words = pj_new(PJ_ARRAY);
        pj_add(words, NULL, pj_string(inspector));
#if defined(__APPLE__)
        pj_add(words, NULL, pj_string("-L"));
#endif
        pj_add(words, NULL, pj_string(image->key));
        probe = pc_context_probe(c, words, "compiler implementation libraries");
#if !defined(__APPLE__) && !defined(_WIN32)
        /* ldd reports static executables with a nonzero status. */
        if (probe.status != 0 && !probe.timed_out &&
            (strstr(probe.out, "statically linked") ||
             strstr(probe.err, "not a dynamic executable"))) {
            pc_probe_free(&probe);
            continue;
        }
#endif
        if (!pc_probe_ok(c, &probe, "compiler implementation libraries")) {
            pc_probe_free(&probe);
            ok = 0;
            break;
        }
        for (line = probe.out; *line && ok; line = *end ? end + 1 : end) {
            char *name, *path = NULL;
            end = strchr(line, '\n');
            if (!end)
                end = line + strlen(line);
            name = pc_slice(line, (size_t)(end - line));
            pc_trim(name);
#endif
#if defined(__APPLE__)
            {
                char *suffix = strstr(name, " (compatibility version ");
                if (!suffix) {
                    free(name);
                    continue;
                }
                *suffix = 0;
                /* otool includes LC_ID_DYLIB before a dylib's imported images. */
                if (first_library && pc_ends(image->key, ".dylib")) {
                    first_library = 0;
                    free(name);
                    continue;
                }
                first_library = 0;
                path = pc_loader_path(name, image->key, origin);
                if (!strncmp(path, "@rpath/", 7)) {
                    PcJson *rwords = pj_new(PJ_ARRAY);
                    PcProbe rprobe;
                    const char *rline;
                    free(path);
                    path = NULL;
                    pj_add(rwords, NULL, pj_string(inspector));
                    pj_add(rwords, NULL, pj_string("-l"));
                    pj_add(rwords, NULL, pj_string(image->key));
                    rprobe = pc_context_probe(c, rwords, "compiler library rpaths");
                    if (!pc_probe_ok(c, &rprobe, "compiler library rpaths"))
                        ok = 0;
                    rline = rprobe.out;
                    while (ok && !path && (rline = strstr(rline, "cmd LC_RPATH")) != NULL) {
                        const char *start = strstr(rline, "path "), *stop;
                        char *raw, *base, *candidate;
                        ++rline;
                        if (!start || !(stop = strstr(start, " (offset ")))
                            break;
                        raw = pc_slice(start + 5, (size_t)(stop - start - 5));
                        base = pc_loader_path(raw, image->key, origin);
                        if (!pj_get(rpaths, base))
                            pj_set_number(rpaths, base, 1);
                        candidate = pc_join(base, name + 7);
                        pc_directory_dependency(dependencies, base);
                        if (pc_kind(candidate, 1) == 1)
                            path = pc_string(candidate);
                        free(raw);
                        free(base);
                        free(candidate);
                    }
                    pc_probe_free(&rprobe);
                    if (ok && !path) {
                        const PcJson *search;
                        for (search = rpaths->child; search && !path; search = search->next) {
                            char *candidate = pc_join(search->key, name + 7);
                            if (pc_kind(candidate, 1) == 1)
                                path = pc_string(candidate);
                            free(candidate);
                        }
                    }
                    if (ok && !path)
                        ok =
                            pc_fail(c, 2154, "unsupported unresolved compiler library rpath", name);
                }
                /* Modern macOS keeps its OS libraries in the dyld shared cache.
                   The host OS build is a selection input for this boundary. */
                if (path && pc_kind(path, 1) != 1 &&
                    (pc_within(path, "/usr/lib") || pc_within(path, "/System/Library"))) {
                    free(path);
                    path = NULL;
                }
            }
#elif defined(_WIN32)
            {
                const char *dll = name;
                char system[MAX_PATH], *bin = pc_parent(origin), *candidate;
                candidate = pc_join(bin, dll);
                pc_directory_dependency(dependencies, bin);
                free(bin);
                if (pc_kind(candidate, 1) == 1)
                    path = pc_string(candidate);
                free(candidate);
                if (!path && GetSystemDirectoryA(system, sizeof(system))) {
                    candidate = pc_join(system, dll);
                    if (pc_kind(candidate, 1) == 1)
                        path = pc_string(candidate);
                    free(candidate);
                }
                if (!path)
                    path = pc_executable(dll);
                /* API-set names are virtual OS imports. */
                if (!path && _strnicmp(dll, "api-ms-", 7) && _strnicmp(dll, "ext-ms-", 7))
                    ok = pc_fail(c, 2154, "unresolved compiler implementation DLL", dll);
            }
#else
            {
                char *arrow = strstr(name, "=>"), *start = arrow ? arrow + 2 : name, *stop;
                while (*start == ' ' || *start == '\t')
                    ++start;
                if (strstr(start, "not found"))
                    ok = pc_fail(c, 2154, "missing compiler implementation library", name);
                if (*start == '/') {
                    stop = strstr(start, " (");
                    path = pc_slice(start, stop ? (size_t)(stop - start) : strlen(start));
                }
            }
#endif
            if (path && ok) {
                char *parent = pc_parent(path);
                pc_directory_dependency(dependencies, parent);
                if (pc_kind(path, 1) != 1)
                    ok = pc_fail(c, 2154, "missing compiler implementation library", path);
                else
                    pc_add_component(paths, path);
#if defined(__APPLE__) || defined(_WIN32)
                if (ok) {
                    char *absolute = pc_path_call(path, l1c_fs_absolute_path);
                    if (absolute && !pj_get(origins, absolute))
                        pj_set_string(origins, absolute, origin);
                    free(absolute);
                }
#endif
                free(parent);
            }
            free(path);
#if !defined(_WIN32)
            free(name);
#endif
        }
#if defined(_WIN32)
        pj_free(imports);
#else
        pc_probe_free(&probe);
#endif
    }
#if !defined(_WIN32)
    free(inspector);
#endif
    pj_free(processed);
#if defined(__APPLE__) || defined(_WIN32)
    pj_free(origins);
#if defined(__APPLE__)
    pj_free(searches);
#endif
#else
    pj_free(originals);
    free(reader);
#endif
    return ok;
}
#endif
