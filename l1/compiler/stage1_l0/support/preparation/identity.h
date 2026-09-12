/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file identity.h Exact Dea/native identities and machine-local discovery memos. */
#ifndef L1_PREPARATION_IDENTITY_H
#define L1_PREPARATION_IDENTITY_H

static int pc_ends(const char *s, const char *suffix) {
    size_t a = strlen(s), b = strlen(suffix);
    return a >= b && !memcmp(s + a - b, suffix, b);
}
static void pc_trim(char *s) {
    size_t n = strlen(s), first = 0;
    while (n && strchr(" \t\r\n", s[n - 1]))
        s[--n] = 0;
    while (s[first] && strchr(" \t\r\n", s[first]))
        ++first;
    if (first)
        memmove(s, s + first, n - first + 1);
}
static void pc_load_input_memo(PcContext *c, const char *key) {
    char *path = pc_memo_path(c, "toolchains", key, 0);
    PcJson *memo = path ? pc_read_json(path) : NULL;
    free(path);
    pj_free(c->old_files);
    c->old_files = pj_new(PJ_OBJECT);
    if (!c->force && pc_memo_valid(memo, "identity") && pj_get(memo, "files") &&
        pj_get(memo, "files")->type == PJ_OBJECT) {
        pj_free(c->old_files);
        c->old_files = pj_clone(pj_get(memo, "files"));
    }
    pj_free(memo);
}
static void pc_save_input_memo(PcContext *c, const char *key, const PcJson *discovery) {
    char *path = pc_memo_path(c, "toolchains", key, 1);
    PcJson *memo;
    if (!path)
        return;
    memo = pc_memo_create("identity");
    pj_add(memo, "files", pj_clone(c->new_files));
    if (discovery) {
        char *digest = pc_json_digest(discovery);
        pj_add(memo, "discovery", pj_clone(discovery));
        pj_set_string(memo, "discovery_digest", digest);
        free(digest);
    }
    pc_write_json(path, memo);
    pj_free(memo);
    free(path);
}
/** Walk the small compiler-owned input tree; never walk a toolchain SDK. */
static int pc_source_tree(PcContext *c, const char *root, const char *relative, PcJson *sources,
                          PcJson *modules, int depth) {
    char *directory = pc_join(root, relative);
    PcJson *names = pc_list(directory);
    const PcJson *name;
    int ok = 1;
    free(directory);
    if (!names)
        return pc_fail(c, 2151, "cannot enumerate bundled preparation sources", relative);
    if (depth > 16) {
        pj_free(names);
        return pc_fail(c, 2151, "bundled source nesting exceeds supported depth", relative);
    }
    for (name = names->child; name && ok; name = name->next) {
        char *rel = pc_join(relative, name->text), *path = pc_join(root, rel);
        int kind = pc_kind(path, 0);
        if (kind == 2)
            ok = pc_source_tree(c, root, rel, sources, modules, depth + 1);
        else if (kind == 1 &&
                 (pc_ends(path, ".l1") || pc_ends(path, ".l0") || pc_ends(path, ".c") || pc_ends(path, ".h"))) {
            char *digest = pc_input_digest(c, path);
            if (!digest)
                ok = 0;
            else {
                pj_set_string(sources, rel, digest);
                if (modules && pc_ends(path, ".l1")) {
                    const char *prefix = "shared/l1/stdlib/";
                    size_t i;
                    char *module;
                    if (strncmp(rel, prefix, strlen(prefix)))
                        ok = pc_fail(c, 2151, "bundled module escaped its source root", rel);
                    else {
                        module = pc_slice(rel + strlen(prefix), strlen(rel) - strlen(prefix) - 3);
                        for (i = 0; module[i]; ++i)
                            if (module[i] == '/')
                                module[i] = '.';
                        if (!pc_module_name(module) ||
                            (strncmp(module, "std.", 4) && strncmp(module, "sys.", 4)))
                            ok = pc_fail(c, 2151, "invalid bundled module path", rel);
                        else
                            pj_set_string(modules, module, digest);
                        free(module);
                    }
                }
                free(digest);
            }
        } else if (kind != 1)
            ok =
                pc_fail(c, 2151,
                        "bundled preparation sources must be ordinary files and directories", path);
        free(rel);
        free(path);
    }
    pj_free(names);
    return ok;
}
static int pc_resolve_dea(PcContext *c) {
    PcJson *selection, *sources;
    char *memo_key, *digest;
    if (c->dea)
        return 1;
    c->self = *pc_config(c, "self")
                  ? pc_path_call(pc_config(c, "self"), l1c_fs_canonical_existing_path)
                  : pc_self_executable();
    if (!c->home || !c->self)
        return pc_fail(c, 2151, "cannot locate bundled sources or Dea compiler implementation",
                       pc_config(c, "home"));
    selection = pj_new(PJ_OBJECT);
    pj_set_string(selection, "kind", "dea-inputs");
    pj_set_string(selection, "home", c->home);
    pj_set_string(selection, "compiler", c->self);
    memo_key = pc_json_digest(selection);
    pj_free(selection);
    pc_load_input_memo(c, memo_key);
    digest = pc_input_digest(c, c->self);
    if (!digest) {
        free(memo_key);
        return 0;
    }
    c->dea = pj_new(PJ_OBJECT);
    pj_set_number(c->dea, "schema", 1);
    pj_set_string(c->dea, "compiler", digest);
    free(digest);
    sources = pj_new(PJ_OBJECT);
    c->modules = pj_new(PJ_OBJECT);
    pj_add(c->dea, "sources", sources);
    pj_add(c->dea, "modules", c->modules);
    if (!pc_source_tree(c, c->home, "shared/l1/stdlib", sources, c->modules, 0) ||
        !pc_source_tree(c, c->home, "shared/runtime", sources, NULL, 0)) {
        free(memo_key);
        return 0;
    }
    if (!pj_count(c->modules)) {
        free(memo_key);
        return pc_fail(c, 2151, "bundled stdlib has no preparation modules", c->home);
    }
    c->interfaces = pj_new(PJ_OBJECT);
    pj_add(c->dea, "interfaces", c->interfaces);
    {
        const PcJson *module;
        for (module = c->modules->child; module; module = module->next) {
            char *relative = pc_module_artifact(module->key, ".l1m", "modules");
            char *path = pc_join(c->semantic_root, relative + strlen("modules/"));
            char *interface_digest = pc_input_digest(c, path);
            if (!interface_digest) {
                pc_clear_error(c);
                pc_fail(c, 2158, "required bundled semantic interface is unavailable; rerun make build-stage1 or repair installation", path);
                free(relative); free(path); free(memo_key); return 0;
            }
            pj_set_string(c->interfaces, relative, interface_digest);
            free(relative); free(path); free(interface_digest);
        }
    }
    if (!c->installed && (!pc_source_tree(c, c->home, "stage1_l0/src", sources, NULL, 0) ||
        !pc_source_tree(c, c->home, "stage1_l0/support", sources, NULL, 0))) {
        free(memo_key); return 0;
    }
    c->dea_key = pc_json_digest(c->dea);
    pc_save_input_memo(c, memo_key, NULL);
    free(memo_key);
    return 1;
}

/** Keep process selection inputs separate from native artifact roots. */
static PcJson *pc_selection_environment(void) {
    static const char *const names[] = {"PATH",
                                        "PATHEXT",
                                        "CPATH",
                                        "C_INCLUDE_PATH",
                                        "CPLUS_INCLUDE_PATH",
                                        "LIBRARY_PATH",
                                        "COMPILER_PATH",
                                        "GCC_EXEC_PREFIX",
                                        "SDKROOT",
                                        "DEVELOPER_DIR",
                                        "MACOSX_DEPLOYMENT_TARGET",
                                        "CCC_OVERRIDE_OPTIONS",
                                        "CLANG_CONFIG_FILE_SYSTEM_DIR",
                                        "CLANG_CONFIG_FILE_USER_DIR",
                                        "TCCDIR",
                                        "HOME",
                                        "XDG_CONFIG_HOME",
                                        "LD_LIBRARY_PATH",
                                        "LD_PRELOAD",
                                        "DYLD_LIBRARY_PATH",
                                        "DYLD_FALLBACK_LIBRARY_PATH",
                                        "DYLD_INSERT_LIBRARIES",
                                        NULL};
    PcJson *env = pj_new(PJ_OBJECT);
    int i;
    for (i = 0; names[i]; ++i)
        pj_set_string(env, names[i], pc_env(names[i]));
#if defined(__APPLE__)
    {
        char build[256];
        size_t n = sizeof(build);
        if (sysctlbyname("kern.osversion", build, &n, NULL, 0) == 0)
            pj_set_string(env, "darwin_os_build", build);
    }
#endif
    return env;
}
/** Include resolved native CPU selection when an option asks the host to choose. */
static char *pc_cpu_identity(const PcJson *options) {
    const PcJson *o;
    int needed = 0;
    PcBuffer b = {0};
    char hex[65];
    for (o = options->child; o; o = o->next)
        if (strstr(o->text, "native") || o->text[0] == '@')
            needed = 1;
    if (!needed)
        return pc_string("");
#if defined(__i386__) || defined(__x86_64__)
    {
        static const uint32_t leaves[] = {
            0, 1, 7, 0x80000000, 0x80000001, 0x80000002, 0x80000003, 0x80000004, 0x80000008};
        size_t i;
        uint32_t a, bb, cc, d, max = 0, max_ext = 0;
        for (i = 0; i < sizeof(leaves) / sizeof(leaves[0]); ++i) {
            uint32_t leaf = leaves[i];
            if (leaf < 0x80000000 && leaf > max && i)
                continue;
            if (leaf > 0x80000000 && leaf > max_ext)
                continue;
            __asm__ volatile("cpuid" : "=a"(a), "=b"(bb), "=c"(cc), "=d"(d) : "a"(leaf), "c"(0));
            if (leaf == 0)
                max = a;
            if (leaf == 0x80000000)
                max_ext = a;
            /* APIC/topology fields do not affect compilation. */
            if (leaf == 1)
                bb &= 0x00ffffff;
            pc_bytes(&b, (const char *)&leaf, sizeof(leaf));
            pc_bytes(&b, (const char *)&a, sizeof(a));
            pc_bytes(&b, (const char *)&bb, sizeof(bb));
            pc_bytes(&b, (const char *)&cc, sizeof(cc));
            pc_bytes(&b, (const char *)&d, sizeof(d));
            if (leaf == 1 && (cc & (1u << 27))) {
                uint32_t low, high;
                /* Byte spelling also works with TinyCC's smaller assembler. */
                __asm__ volatile(".byte 0x0f, 0x01, 0xd0" : "=a"(low), "=d"(high) : "c"(0));
                pc_bytes(&b, (const char *)&low, sizeof(low));
                pc_bytes(&b, (const char *)&high, sizeof(high));
            }
        }
    }
#elif defined(__APPLE__)
    {
        static const char *const names[] = {"hw.cpufamily", "hw.cpusubtype",
                                            "machdep.cpu.brand_string", NULL};
        int i;
        for (i = 0; names[i]; ++i) {
            char data[1024];
            size_t n = sizeof(data);
            if (sysctlbyname(names[i], data, &n, NULL, 0) == 0)
                pc_bytes(&b, data, n);
        }
    }
#elif defined(_WIN32)
    {
        SYSTEM_INFO info;
        int i;
        GetNativeSystemInfo(&info);
        pc_bytes(&b, (const char *)&info.wProcessorArchitecture,
                 sizeof(info.wProcessorArchitecture));
        for (i = 0; i < 64; ++i)
            pc_char(&b, IsProcessorFeaturePresent((DWORD)i) ? '1' : '0');
    }
#else
    {
        size_t n;
        char *info = pc_read_file("/proc/cpuinfo", 4 * 1024 * 1024, &n);
        if (info) {
            pc_bytes(&b, info, n);
            free(info);
        }
    }
#endif
    pc_sha_bytes(b.s ? b.s : "", b.n, hex);
    free(b.s);
    return pc_string(hex);
}
static PcJson *pc_runtime_words(PcContext *c) {
    PcJson *words = pj_new(PJ_ARRAY);
    const PcJson *o;
    pj_add(words, NULL, pj_string(c->compiler));
    for (o = c->runtime_options->child; o; o = o->next) pj_add(words, NULL, pj_clone(o));
    return words;
}
static PcJson *pc_words(PcContext *c, int options) {
    PcJson *words = pj_new(PJ_ARRAY);
    const PcJson *o;
    pj_add(words, NULL, pj_string(c->compiler));
    if (options)
        for (o = c->options->child; o; o = o->next)
            pj_add(words, NULL, pj_string(o->text));
    return words;
}
/** TinyCC handles search queries before ordinary compilation option parsing. */
static PcJson *pc_search_words(PcContext *c, const char *family) {
    PcJson *words;
    const PcJson *option;
    if (strcmp(family, "tcc"))
        return pc_words(c, 1);
    words = pc_words(c, 0);
    for (option = c->options->child; option; option = option->next) {
        const char *word = option->text;
        if (!strncmp(word, "-B", 2) || !strcmp(word, "-m32") || !strcmp(word, "-m64")) {
            pj_add(words, NULL, pj_string(word));
            if (!strcmp(word, "-B") && option->next) {
                option = option->next;
                pj_add(words, NULL, pj_string(option->text));
            }
        }
    }
    return words;
}
static PcProbe pc_context_probe(PcContext *c, PcJson *words) {
    PcProbe p;
    const PcJson *timeout = pj_get(c->config, "probe_timeout_ms");
    int ms =
        timeout && timeout->type == PJ_NUMBER && timeout->number > 0 && timeout->number <= 60000
            ? (int)timeout->number
            : 15000;
    ++c->probes;
    p = pc_probe(words, ms);
    pj_free(words);
    return p;
}
static int pc_probe_ok(PcContext *c, const PcProbe *p, const char *purpose) {
    if (p->status == 0 && !p->timed_out)
        return 1;
    {
        PcBuffer reason = {0};
        pc_text(&reason, p->timed_out ? "toolchain probe timed out: " : "toolchain probe failed: ");
        pc_text(&reason, purpose);
        if (p->err && *p->err) {
            pc_char(&reason, '\n');
            pc_text(&reason, p->err);
        }
        if (p->out && *p->out) {
            pc_char(&reason, '\n');
            pc_text(&reason, p->out);
        }
        pc_fail(c, 2154, reason.s, c->compiler);
        free(reason.s);
    }
    return 0;
}
static void pc_dependency(PcJson *dependencies, const char *path) {
    PcJson *metadata;
    if (pj_get(dependencies, path))
        return;
    metadata = pc_meta(path);
    pj_add(dependencies, path, metadata ? metadata : pj_new(PJ_NULL));
}
static void pc_directory_dependency(PcJson *dependencies, const char *path) {
    if (!path || !*path)
        return;
    char *absolute = pc_path_call(path, l1c_fs_absolute_path);
    if (absolute) {
        pc_dependency(dependencies, absolute);
        free(absolute);
    }
}
static void pc_path_list_dependencies(PcJson *dependencies, const char *paths) {
    const char *p = paths, *start = p;
    if (!*paths)
        return;
#if defined(_WIN32)
    const char separator = ';';
#else
    const char separator = ':';
#endif
    for (;; ++p)
        if (!*p || *p == separator) {
            char *path = pc_slice(start, (size_t)(p - start));
            pc_directory_dependency(dependencies, *path ? path : ".");
            free(path);
            if (!*p)
                break;
            start = p + 1;
        }
}
static void pc_add_component(PcJson *paths, const char *path) {
    char *absolute = pc_path_call(path, l1c_fs_absolute_path);
    if (absolute && pc_kind(absolute, 1) == 1 && !pj_get(paths, absolute))
        pj_set_string(paths, absolute, absolute);
    free(absolute);
}
/** Track directory-selection options in both direct and expanded response arguments. */
static void pc_option_directory_dependencies(const PcJson *options, PcJson *dependencies) {
    const PcJson *o;
    for (o = options->child; o; o = o->next) {
        const char *s = o->text, *path = NULL;
        if (!strcmp(s, "-I") || !strcmp(s, "-isystem") || !strcmp(s, "-isysroot") ||
            !strcmp(s, "--sysroot") || !strcmp(s, "-B") || !strcmp(s, "-L")) {
            if (o->next)
                path = o->next->text;
        } else if ((!strncmp(s, "-I", 2) || !strncmp(s, "-B", 2) || !strncmp(s, "-L", 2)) && s[2])
            path = s + 2;
        else if (!strncmp(s, "--sysroot=", 10))
            path = s + 10;
        else if (!strncmp(s, "--config-system-dir=", 20))
            path = s + 20;
        else if (!strncmp(s, "--config-user-dir=", 18))
            path = s + 18;
        if (path)
            pc_directory_dependency(dependencies, path);
    }
}
static void pc_selection_dependencies(PcContext *c, PcJson *dependencies) {
    char *parent = pc_parent(c->compiler);
    pc_directory_dependency(dependencies, parent);
    free(parent);
    pc_path_list_dependencies(dependencies, pc_env("PATH"));
    pc_path_list_dependencies(dependencies, pc_env("COMPILER_PATH"));
    pc_path_list_dependencies(dependencies, pc_env("LIBRARY_PATH"));
    pc_path_list_dependencies(dependencies, pc_env("CPATH"));
    pc_path_list_dependencies(dependencies, pc_env("C_INCLUDE_PATH"));
    pc_path_list_dependencies(dependencies, pc_env("LD_LIBRARY_PATH"));
    pc_path_list_dependencies(dependencies, pc_env("DYLD_LIBRARY_PATH"));
    pc_path_list_dependencies(dependencies, pc_env("DYLD_FALLBACK_LIBRARY_PATH"));
    {
        char *user = *pc_env("XDG_CONFIG_HOME") ? pc_string(pc_env("XDG_CONFIG_HOME"))
                                                : pc_join(pc_env("HOME"), ".config");
        char *config = pc_join(user, "clang"), *bin = pc_parent(c->compiler),
             *prefix = pc_parent(bin), *system = pc_join(prefix, "etc/clang");
        pc_directory_dependency(dependencies, config);
        pc_directory_dependency(dependencies, system);
        pc_directory_dependency(dependencies, pc_env("CLANG_CONFIG_FILE_SYSTEM_DIR"));
        pc_directory_dependency(dependencies, pc_env("CLANG_CONFIG_FILE_USER_DIR"));
        free(user);
        free(config);
        free(bin);
        free(prefix);
        free(system);
    }
}
static int pc_discovery_current(PcContext *c, const PcJson *memo) {
    const PcJson *discovery = pj_get(memo, "discovery"), *memo_files = pj_get(memo, "files");
    const PcJson *deps = pj_get(discovery, "dependencies"), *paths = pj_get(discovery, "paths"), *p;
    const PcJson *tc = pj_get(discovery, "toolchain");
    char *digest;
    int sealed;
    if (c->force || !pj_is_number(pj_get(discovery, "schema"), 1) || !deps ||
        deps->type != PJ_OBJECT || !paths || paths->type != PJ_OBJECT || !pj_count(paths) ||
        !pj_field(discovery, "version") || !tc || tc->type != PJ_OBJECT ||
        !pj_field(tc, "family") || !pj_field(tc, "invocation") || !pj_field(tc, "target") ||
        (strcmp(pj_field(tc, "family"), "tcc") && !pj_field(tc, "archiver")) ||
        !pc_hex_digest(pj_field(tc, "target_macros")) || !memo_files ||
        memo_files->type != PJ_OBJECT)
        return 0;
    digest = pc_json_digest(discovery);
    sealed =
        pj_field(memo, "discovery_digest") && !strcmp(digest, pj_field(memo, "discovery_digest"));
    free(digest);
    if (!sealed)
        return 0;
    for (p = deps->child; p; p = p->next) {
        PcJson *now = pc_meta(p->key);
        int same = p->type == PJ_NULL
                       ? !now
                       : (now && pj_is_number(pj_get(now, "reliable"), 1) && pj_equal(p, now));
        pj_free(now);
        if (!same)
            return 0;
    }
    for (p = paths->child; p; p = p->next) {
        PcJson *old = pj_get(memo_files, p->key), *now = pc_meta(p->key);
        int same = now && pc_hex_digest(pj_field(old, "sha256")) &&
                   pj_is_number(pj_get(now, "reliable"), 1) &&
                   pj_equal(now, pj_get(old, "metadata"));
        pj_free(now);
        if (!same)
            return 0;
    }
    return 1;
}
/** A tiny scratch source is used only for bounded toolchain queries. */
static char *pc_probe_directory(void) {
#if defined(_WIN32)
    char parent[MAX_PATH], name[MAX_PATH];
    if (!GetTempPathA(sizeof(parent), parent) || !GetTempFileNameA(parent, "l1p", 0, name))
        return NULL;
    DeleteFileA(name);
    if (!CreateDirectoryA(name, NULL))
        return NULL;
    return pc_string(name);
#else
    const char *temp = pc_env("TMPDIR");
    char *pattern = pc_join(*temp ? temp : "/tmp", "l1-preparation-probe-XXXXXX");
    if (!mkdtemp(pattern)) {
        free(pattern);
        return NULL;
    }
    return pattern;
#endif
}
static void pc_probe_directory_free(const char *directory) {
    static const char *const children[] = {"probe.c", "dependencies.d", NULL};
    int i;
    for (i = 0; children[i]; ++i) {
        char *p = pc_join(directory, children[i]);
        remove(p);
        free(p);
    }
#if defined(_WIN32)
    _rmdir(directory);
#else
    rmdir(directory);
#endif
}
/** Parse make dependency escaping, including continued lines and spaces. */
static int pc_parse_dependencies(PcContext *c, const char *text, PcJson *paths, PcJson *directories,
                                 const char *scratch) {
    const char *p = text;
    PcBuffer token = {0};
    while (*p && !(*p == ':' && (!p[1] || strchr(" \t\r\n", p[1]))))
        ++p;
    if (!*p)
        return pc_fail(c, 2154, "malformed compiler dependency response", c->compiler);
    ++p;
    for (;; ++p) {
        char ch = *p;
        if (ch == '\\' && p[1]) {
            ++p;
            if (*p == '\n')
                continue;
            if (*p == '\r' && p[1] == '\n') {
                ++p;
                continue;
            }
            pc_char(&token, *p);
            continue;
        }
        if (!ch || strchr(" \t\r\n", ch)) {
            if (token.n) {
                char *absolute = pc_path_call(token.s, l1c_fs_absolute_path);
                if (!absolute) {
                    free(token.s);
                    return pc_fail(c, 2154, "invalid compiler dependency path", c->compiler);
                }
                if (!pc_within(absolute, scratch)) {
                    char *parent = pc_parent(absolute);
                    pc_add_component(paths, absolute);
                    pc_directory_dependency(directories, parent);
                    free(parent);
                    if (pc_kind(absolute, 1) != 1) {
                        pc_fail(c, 2154, "compiler dependency is unavailable", absolute);
                        free(absolute);
                        free(token.s);
                        return 0;
                    }
                }
                free(absolute);
                token.n = 0;
                token.s[0] = 0;
            }
            if (!ch)
                break;
        } else
            pc_char(&token, ch);
    }
    free(token.s);
    return 1;
}
static void pc_search_directories(PcJson *dependencies, const char *text) {
    const char *p = text, *start = p;
    for (;; ++p)
        if (!*p || *p == '\n') {
            char *line = pc_slice(start, (size_t)(p - start)), *colon;
            pc_trim(line);
            colon = strchr(line, ':');
            if (colon && colon[1] == ' ' && colon[2] == '=')
                pc_path_list_dependencies(dependencies, colon + 3);
            else if (*line == '/' || (strlen(line) > 2 && line[1] == ':'))
                pc_directory_dependency(dependencies, line);
            free(line);
            if (!*p)
                break;
            start = p + 1;
        }
}
/** Resolve Apple's active toolchain on every invocation, not just on memo misses. */
static int pc_apple_selection(PcContext *c, PcJson *selection) {
#if defined(__APPLE__)
    char *resolved = pc_path_call(c->compiler, l1c_fs_canonical_existing_path);
    struct stat invocation, shim;
    int apple = resolved && pc_within(resolved, "/usr/bin") &&
                (!strcmp(pc_base(resolved), "clang") || !strcmp(pc_base(resolved), "cc") ||
                 !strcmp(pc_base(resolved), "gcc"));
    if (!apple && stat(c->compiler, &invocation) == 0) {
        static const char *const shims[] = {"/usr/bin/clang", "/usr/bin/cc", "/usr/bin/gcc", NULL};
        int i;
        for (i = 0; shims[i]; ++i)
            if (stat(shims[i], &shim) == 0 && shim.st_dev == invocation.st_dev &&
                shim.st_ino == invocation.st_ino)
                apple = 1;
    }
    free(resolved);
    if (apple) {
        PcJson *words = pj_new(PJ_ARRAY);
        PcProbe p;
        pj_add(words, NULL, pj_string("/usr/bin/xcrun"));
        pj_add(words, NULL, pj_string("--find"));
        pj_add(words, NULL, pj_string("clang"));
        p = pc_context_probe(c, words);
        if (!pc_probe_ok(c, &p, "active Apple compiler")) {
            pc_probe_free(&p);
            return 0;
        }
        pc_trim(p.out);
        pj_set_string(selection, "apple_compiler", p.out);
        pc_probe_free(&p);
        words = pj_new(PJ_ARRAY);
        pj_add(words, NULL, pj_string("/usr/bin/xcrun"));
        pj_add(words, NULL, pj_string("--show-sdk-path"));
        p = pc_context_probe(c, words);
        if (!pc_probe_ok(c, &p, "active Apple SDK")) {
            pc_probe_free(&p);
            return 0;
        }
        pc_trim(p.out);
        pj_set_string(selection, "apple_sdk", p.out);
        pc_probe_free(&p);
    }
#else
    (void)c;
    (void)selection;
#endif
    return 1;
}
/** Record ordered include roots, including currently absent search candidates. */
static void pc_include_search(const char *text, PcJson *roots, PcJson *dependencies, int tcc) {
    const char *start = text, *p;
    int active = 0;
    for (p = text;; ++p) {
        char *line, *suffix;
        if (*p && *p != '\n')
            continue;
        line = pc_slice(start, (size_t)(p - start));
        pc_trim(line);
        if ((!tcc && strstr(line, "search starts here:")) || (tcc && !strcmp(line, "include:")))
            active = 1;
        else if ((!tcc && strstr(line, "End of search list.")) ||
                 (tcc && !strcmp(line, "libraries:")))
            active = 0;
        else if (active && *line) {
            char *absolute;
            suffix = strstr(line, " (framework directory)");
            if (suffix)
                *suffix = 0;
            absolute = pc_path_call(line, l1c_fs_absolute_path);
            if (absolute && !pj_get(roots, absolute))
                pj_set_string(roots, absolute, absolute);
            if (absolute)
                pc_dependency(dependencies, absolute);
            free(absolute);
        } else if (!tcc && !strncmp(line, "ignoring nonexistent directory \"",
                                    strlen("ignoring nonexistent directory \""))) {
            char *path = strchr(line, '"'), *end = strrchr(line, '"');
            if (path && end > path) {
                *end = 0;
                pc_directory_dependency(dependencies, path + 1);
            }
        }
        free(line);
        if (!*p)
            break;
        start = p + 1;
    }
}
/** Track nested parents where a newly introduced header could shadow a prior selection. */
static void pc_header_shadow_dependencies(const PcJson *roots, const PcJson *paths,
                                          PcJson *dependencies) {
    const PcJson *file, *selected_root, *candidate_root;
    for (file = paths->child; file; file = file->next) {
        for (selected_root = roots->child; selected_root; selected_root = selected_root->next) {
            const char *relative;
            if (!pc_within(file->key, selected_root->key) || !strcmp(file->key, selected_root->key))
                continue;
            relative = file->key + strlen(selected_root->key);
            while (*relative == '/' || *relative == '\\')
                ++relative;
            for (candidate_root = roots->child; candidate_root;
                 candidate_root = candidate_root->next) {
                char *candidate = pc_join(candidate_root->key, relative);
                char *parent = pc_parent(candidate);
                pc_dependency(dependencies, parent);
                free(parent);
                free(candidate);
            }
            break;
        }
    }
}
/** Normalize UTF-8 and BOM-marked UTF-16 option files without silently truncating malformed text. */
static char *pc_option_file_text(const char *path) {
    size_t n = 0, i;
    char *raw = pc_read_file(path, 1024 * 1024, &n);
    const unsigned char *bytes = (const unsigned char *)raw;
    PcBuffer decoded = {0};
    int little;
    if (!raw)
        return NULL;
    if (n >= 2 && ((bytes[0] == 0xff && bytes[1] == 0xfe) ||
                   (bytes[0] == 0xfe && bytes[1] == 0xff))) {
        little = bytes[0] == 0xff;
        if (n % 2)
            goto invalid;
        for (i = 2; i < n; i += 2) {
            unsigned value = little ? bytes[i] | (bytes[i + 1] << 8) : (bytes[i] << 8) | bytes[i + 1];
            if (value >= 0xd800 && value <= 0xdbff) {
                unsigned low;
                if (i + 3 >= n)
                    goto invalid;
                i += 2;
                low = little ? bytes[i] | (bytes[i + 1] << 8) : (bytes[i] << 8) | bytes[i + 1];
                if (low < 0xdc00 || low > 0xdfff)
                    goto invalid;
                value = 0x10000 + ((value - 0xd800) << 10) + low - 0xdc00;
            } else if (!value || (value >= 0xdc00 && value <= 0xdfff))
                goto invalid;
            pj_utf8(&decoded, value);
        }
        free(raw);
        return pc_take(&decoded);
    }
    if (memchr(raw, 0, n) || !pj_valid_utf8(raw, n))
        goto invalid;
    if (n >= 3 && bytes[0] == 0xef && bytes[1] == 0xbb && bytes[2] == 0xbf)
        memmove(raw, raw + 3, n - 2);
    return raw;
invalid:
    free(raw);
    free(decoded.s);
    return NULL;
}
/** Decode bounded GNU response arguments and Clang configuration-file syntax. */
static PcJson *pc_read_option_file(PcContext *c, const char *path, int configuration) {
    char *raw = pc_option_file_text(path), *directory = pc_parent(path);
    const char *p;
    PcBuffer prepared = {0}, token = {0};
    PcJson *words = pj_new(PJ_ARRAY);
    int quote = 0, line_start = 1, token_started = 0;
    if (!raw)
        goto invalid;
    for (p = raw; *p; ++p) {
        if (configuration && line_start) {
            const char *first = p;
            while (*first == ' ' || *first == '\t' || *first == '\r')
                ++first;
            if (*first == '#') {
                p = first;
                while (*p && *p != '\n')
                    ++p;
                if (!*p)
                    break;
            }
        }
        if (configuration && *p == '\\' && (p[1] == '\n' || (p[1] == '\r' && p[2] == '\n'))) {
            p += p[1] == '\r' ? 2 : 1;
            continue;
        }
        pc_char(&prepared, *p);
        line_start = *p == '\n';
    }
    for (p = prepared.s; p && *p; ++p) {
        if (*p == '\\' && p[1]) {
            pc_char(&token, *++p);
            token_started = 1;
        } else if (*p == '\'' || *p == '"') {
            token_started = 1;
            if (!quote)
                quote = *p;
            else if (quote == *p)
                quote = 0;
            else
                pc_char(&token, *p);
        } else if (!quote && strchr(" \t\r\n", *p)) {
            if (token_started) {
                pj_add(words, NULL, pj_string(token.s ? token.s : ""));
                token.n = 0;
                if (token.s) token.s[0] = 0;
                token_started = 0;
            }
        } else {
            pc_char(&token, *p);
            token_started = 1;
        }
    }
    if (quote)
        goto invalid;
    if (token_started)
        pj_add(words, NULL, pj_string(token.s ? token.s : ""));
    if (configuration) {
        PcJson *word;
        for (word = words->child; word; word = word->next) {
            PcBuffer expanded = {0};
            for (p = word->text; *p;) {
                if (!strncmp(p, "<CFGDIR>", 8)) {
                    pc_text(&expanded, directory);
                    p += 8;
                } else
                    pc_char(&expanded, *p++);
            }
            free(word->text);
            word->text = pc_take(&expanded);
        }
    }
    free(directory);
    free(raw);
    free(prepared.s);
    free(token.s);
    return words;
invalid:
    pc_fail(c, 2154, "unsupported or unreadable compiler option file", path);
    free(directory);
    free(raw);
    free(prepared.s);
    free(token.s);
    pj_free(words);
    return NULL;
}
/** Own parsed files once per resolution; only direct and selected-config roots are flattened. */
typedef struct PcOptionFile {
    char *path;
    int configuration;
    PcJson *parsed, *root;
    struct PcOptionFile *next;
} PcOptionFile;
typedef struct {
    PcJson *direct;
    PcOptionFile *files;
} PcOptionInputs;

static void pc_option_inputs_free(PcOptionInputs *inputs) {
    PcOptionFile *file = inputs->files;
    while (file) {
        PcOptionFile *next = file->next;
        free(file->path); pj_free(file->parsed); pj_free(file->root); free(file);
        file = next;
    }
    pj_free(inputs->direct);
}

/** Preserve lexical directories for configuration includes and <CFGDIR>, including aliases. */
static PcOptionFile *pc_option_file(PcContext *c, PcOptionInputs *inputs,
                                    const char *path, int configuration) {
    char *absolute = pc_path_call(path, l1c_fs_absolute_path);
    PcOptionFile *file;
    PcJson *parsed;
    if (!absolute) return pc_fail(c, 2154, "cannot resolve compiler option file", path), NULL;
    for (file = inputs->files; file; file = file->next)
        if (file->configuration == configuration && !strcmp(file->path, absolute)) {
            free(absolute); return file;
        }
    ++c->option_file_parses;
    parsed = pc_read_option_file(c, absolute, configuration);
    if (!parsed) { free(absolute); return NULL; }
    file = pc_alloc(sizeof(*file));
    file->path = absolute; file->configuration = configuration; file->parsed = parsed;
    file->next = inputs->files; inputs->files = file;
    return file;
}

/** Expand every occurrence in order; cached parsed files never bypass the current nesting bound. */
static int pc_expand_options(PcContext *c, PcOptionInputs *inputs, const PcJson *options,
                             const char *config_directory, int depth, PcJson *expanded) {
    const PcJson *option;
    if (depth > 16)
        return pc_fail(c, 2154, "nested compiler response files exceed the supported depth", NULL);
    for (option = options->child; option; option = option->next) {
        const char *word = option->text;
        if (*word == '@') {
            const char *name = word + 1;
            int drive = pc_separator('\\') && strlen(name) > 1 &&
                isalpha((unsigned char)name[0]) && name[1] == ':';
            char *path = config_directory && !pc_separator(*name) && !drive
                ? pc_join(config_directory, name) : pc_string(name);
            PcOptionFile *file = pc_option_file(c, inputs, path, config_directory != NULL);
            char *parent = file && config_directory ? pc_parent(file->path) : NULL;
            int ok = file && pc_expand_options(c, inputs, file->parsed, parent, depth + 1, expanded);
            free(path); free(parent);
            if (!ok) return 0;
        } else {
            pj_add(expanded, NULL, pj_clone(option));
        }
    }
    return 1;
}

static const PcJson *pc_direct_options(PcContext *c, PcOptionInputs *inputs) {
    if (!inputs->direct) {
        PcJson *expanded = pj_new(PJ_ARRAY);
        ++c->option_root_expansions;
        if (!pc_expand_options(c, inputs, c->options, NULL, 0, expanded)) {
            pj_free(expanded); return NULL;
        }
        inputs->direct = expanded;
    }
    return inputs->direct;
}

/** Selected configuration roots are shared by runtime extraction and later observation. */
static const PcJson *pc_config_options(PcContext *c, PcOptionInputs *inputs, const char *path) {
    PcOptionFile *file = pc_option_file(c, inputs, path, 1);
    if (!file) return NULL;
    if (!file->root) {
        char *parent = pc_parent(file->path);
        PcJson *expanded = pj_new(PJ_ARRAY);
        int ok;
        ++c->option_root_expansions;
        ok = pc_expand_options(c, inputs, file->parsed, parent, 0, expanded);
        free(parent);
        if (!ok) { pj_free(expanded); return NULL; }
        file->root = expanded;
    }
    return file->root;
}

/** Observe flat operands while retaining every source file removed by @ expansion. */
static void pc_option_word_dependencies(const PcJson *words, PcJson *paths, PcJson *dependencies) {
    const PcJson *word;
    pc_option_directory_dependencies(words, dependencies);
    for (word = words->child; word; word = word->next) {
        const char *path = word->text;
        char *absolute;
        if (*path == '-') {
            path = strchr(path, '=');
            if (!path || !*++path) continue;
        }
        absolute = pc_path_call(path, l1c_fs_absolute_path);
        if (absolute && pc_kind(absolute, 1) == 1) {
            char *parent = pc_parent(absolute);
            pc_add_component(paths, absolute); pc_directory_dependency(dependencies, parent);
            free(parent);
        }
        free(absolute);
    }
}

static void pc_option_inputs_dependencies(const PcOptionInputs *inputs, PcJson *paths, PcJson *dependencies) {
    const PcOptionFile *file;
    pc_option_word_dependencies(inputs->direct, paths, dependencies);
    for (file = inputs->files; file; file = file->next) {
        char *parent = pc_parent(file->path);
        pc_add_component(paths, file->path); pc_directory_dependency(dependencies, parent);
        free(parent);
        if (file->root) pc_option_word_dependencies(file->root, paths, dependencies);
    }
}

/** Capture SDK driver metadata from Clang's effective frontend arguments, including response/config selection. */
static int pc_clang_sdk_inputs(PcContext *c, const char *text, PcJson *paths,
                                PcJson *dependencies) {
    const char *line = text;
    while (*line) {
        const char *end = strchr(line, '\n'), *frontend, *p;
        int next_root = 0;
        if (!end)
            end = line + strlen(line);
        frontend = strstr(line, " -cc1 ");
        if (!frontend || frontend >= end)
            frontend = strstr(line, "\"-cc1\"");
        if (frontend && frontend < end) {
            p = frontend;
            while (p < end) {
                PcBuffer word = {0};
                int quoted = 0;
                while (p < end && isspace((unsigned char)*p))
                    ++p;
                while (p < end && (quoted || !isspace((unsigned char)*p))) {
                    if (*p == '"')
                        quoted = !quoted;
                    else if (*p == '\\' && p + 1 < end)
                        pc_char(&word, *++p);
                    else
                        pc_char(&word, *p);
                    ++p;
                }
                if (quoted) {
                    free(word.s);
                    return pc_fail(c, 2154, "malformed Clang frontend arguments", c->compiler);
                }
                if (next_root && word.n) {
                    static const char *const names[] = {"SDKSettings.json", "SDKSettings.plist", NULL};
                    char *root = pc_path_call(word.s, l1c_fs_absolute_path);
                    int i;
                    if (!root) {
                        free(word.s);
                        return pc_fail(c, 2154, "cannot resolve effective Clang SDK", NULL);
                    }
                    for (i = 0; names[i]; ++i) {
                        char *path = pc_join(root, names[i]);
                        /* Remember absent candidates so later creation invalidates discovery. */
                        pc_dependency(dependencies, path);
                        pc_add_component(paths, path);
                        free(path);
                    }
                    free(root);
                }
                next_root = word.s && !strcmp(word.s, "-isysroot");
                free(word.s);
            }
        }
        line = *end ? end + 1 : end;
    }
    return 1;
}


/** Hash target macros without probe-location or wall-clock predefined expansions. */
static void pc_target_macro_digest(const char *output, char digest[65]) {
    static const char *const incidental[] = {"__BASE_FILE__", "__FILE__",      "__DATE__",
                                             "__TIME__",      "__TIMESTAMP__", NULL};
    const char *line = output;
    PcBuffer stable = {0};
    while (*line) {
        const char *end = strchr(line, '\n');
        size_t length = end ? (size_t)(end - line) : strlen(line);
        int skip = 0, i;
        for (i = 0; incidental[i]; ++i) {
            size_t name_length = strlen(incidental[i]);
            if (length > 8 + name_length && !strncmp(line, "#define ", 8) &&
                !strncmp(line + 8, incidental[i], name_length) &&
                isspace((unsigned char)line[8 + name_length]))
                skip = 1;
        }
        if (!skip) {
            size_t i;
            for (i = 0; i < length; ++i)
                pc_char(&stable, line[i]);
            pc_char(&stable, '\n');
        }
        if (!end)
            break;
        line = end + 1;
    }
    pc_sha_bytes(stable.s ? stable.s : "", stable.n, digest);
    free(stable.s);
}

#include "libraries.h"

static void pc_decline(PcContext *c, const char *reason);

/** Mirror generated-C header branches before recording their effective dependencies. */
static int pc_stdlib_probe(PcContext *c, const char *path, int uses_real, int uses_float) {
    const PcJson *codegen = pj_get(c->config, "codegen");
    PcBuffer source = {0};
    int ok;
    pc_text(&source, "#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\n");
    if (uses_float) pc_text(&source, "#include <float.h>\n#include <math.h>\n");
    if (uses_real) pc_text(&source, "#define DEA_USE_SYS_REAL 1\n");
    if (pj_is_number(pj_get(codegen, "unchecked"), 1)) pc_text(&source, "#define DEA_RT_UNCHECKED 1\n");
    if (pj_is_number(pj_get(codegen, "check_basic"), 1)) pc_text(&source, "#define DEA_RT_CHECK_BASIC 1\n");
    pc_text(&source, "#include \"dea_rt.h\"\n");
    ok = pc_write_file(path, source.s, source.n); free(source.s);
    return ok || pc_fail(c, 2154, "cannot write generated-C dependency probe", path);
}

static PcJson *pc_discover_toolchain(PcContext *c, const PcJson *selection, PcOptionInputs *options) {
    PcJson *discovery = pj_new(PJ_OBJECT), *paths = pj_new(PJ_OBJECT),
           *dependencies = pj_new(PJ_OBJECT), *toolchain = pj_new(PJ_OBJECT), *words,
           *include_roots = pj_new(PJ_OBJECT);
    PcProbe p;
    const char *family;
    char *scratch = NULL, *source = NULL, *depfile = NULL, *include = NULL, *internal = NULL;
    int i;
    const PcJson *input;
    pj_set_number(discovery, "schema", 1);
    pj_add(discovery, "paths", paths);
    pj_add(discovery, "dependencies", dependencies);
    pj_add(discovery, "toolchain", toolchain);
    pj_add(discovery, "include_roots", include_roots);
    pc_add_component(paths, c->compiler);
    if (pj_field(selection, "apple_compiler"))
        pc_add_component(paths, pj_field(selection, "apple_compiler"));
    pc_selection_dependencies(c, dependencies);
    family = c->family;
    pj_set_string(discovery, "version", c->description);
    pj_set_string(toolchain, "family", family);
    pj_set_string(toolchain, "invocation", c->compiler);
    words = pc_words(c, 1);
    pj_add(words, NULL, pj_string("-dumpmachine"));
    p = pc_context_probe(c, words);
    if (!pc_probe_ok(c, &p, "effective target")) {
        pc_probe_free(&p);
        goto fail;
    }
    pc_trim(p.out);
    if (!*p.out) {
        pc_fail(c, 2154, "compiler returned no effective target", c->compiler);
        pc_probe_free(&p); goto fail;
    }
    pj_set_string(toolchain, "target", p.out);
    pc_probe_free(&p);
    words = pc_search_words(c, family);
    pj_add(words, NULL, pj_string("-print-search-dirs"));
    p = pc_context_probe(c, words);
    if (!pc_probe_ok(c, &p, "toolchain search directories")) {
        pc_probe_free(&p);
        goto fail;
    }
    pc_search_directories(dependencies, p.out);
    if (!strcmp(family, "tcc"))
        pc_include_search(p.out, include_roots, dependencies, 1);
    pc_probe_free(&p);
    if (strcmp(family, "tcc")) {
        /* GCC invokes separate tools. Clang's supported persistent path uses its
           integrated frontend/assembler; explicit external assembly declines reuse. */
        static const char *const programs[] = {"cc1", "as", NULL};
        pc_add_component(paths, c->archiver);
        pj_set_string(toolchain, "archiver", c->archiver);
        for (i = 0; !strcmp(family, "gcc") && programs[i]; ++i) {
            PcBuffer arg = {0};
            char *resolved;
            pc_text(&arg, "-print-prog-name=");
            pc_text(&arg, programs[i]);
            words = pc_words(c, 1);
            pj_add(words, NULL, pj_string(arg.s));
            free(arg.s);
            p = pc_context_probe(c, words);
            if (!pc_probe_ok(c, &p, "subordinate compiler tool")) {
                pc_probe_free(&p);
                goto fail;
            }
            pc_trim(p.out);
            resolved = pc_executable(p.out);
            if (resolved) {
                pc_add_component(paths, resolved);
                if (!pc_image_kind(resolved))
                    pc_decline(c, "opaque subordinate compiler-tool wrapper cannot authorize persistent reuse");
                free(resolved);
            }
            pc_probe_free(&p);
        }
    } else {
        words = pc_search_words(c, family);
        pj_add(words, NULL, pj_string("-print-search-dirs"));
        p = pc_context_probe(c, words);
        if (!pc_probe_ok(c, &p, "TinyCC support library")) {
            pc_probe_free(&p);
            goto fail;
        }
        {
            char *start = strstr(p.out, "libtcc1:");
            if (start) {
                char *line = strchr(start, '\n');
                if (line) {
                    char *end = strchr(++line, '\n');
                    char *library = pc_slice(line, end ? (size_t)(end - line) : strlen(line));
                    pc_trim(library);
                    pc_add_component(paths, library);
                    free(library);
                }
            }
        }
        pc_probe_free(&p);
    }
    scratch = pc_probe_directory();
    if (!scratch) {
        pc_fail(c, 2154, "cannot create toolchain probe workspace", NULL);
        goto fail;
    }
    source = pc_join(scratch, "probe.c");
    depfile = pc_join(scratch, "dependencies.d");
    include = pc_string(c->include);
    internal = pc_join(c->home, "shared/runtime/internal");
    if (!pc_stdlib_probe(c, source, 0, 0)) goto fail;
    words = pc_words(c, 1);
    pj_add(words, NULL, pj_string("-I"));
    pj_add(words, NULL, pj_string(include));
    pj_add(words, NULL, pj_string("-dM"));
    pj_add(words, NULL, pj_string("-E"));
    pj_add(words, NULL, pj_string("-x"));
    pj_add(words, NULL, pj_string("c"));
    pj_add(words, NULL, pj_string(source));
    p = pc_context_probe(c, words);
    if (!pc_probe_ok(c, &p, "effective target macros")) {
        pc_probe_free(&p);
        goto fail;
    }
    {
        char hex[65];
        pc_target_macro_digest(p.out, hex);
        pj_set_string(toolchain, "target_macros", hex);
    }
    pc_probe_free(&p);
    if (strcmp(family, "tcc")) {
        words = pc_words(c, 1);
        pj_add(words, NULL, pj_string("-I"));
        pj_add(words, NULL, pj_string(include));
        pj_add(words, NULL, pj_string("-v"));
        pj_add(words, NULL, pj_string("-E"));
        pj_add(words, NULL, pj_string(source));
        pj_add(words, NULL, pj_string("-o"));
#if defined(_WIN32)
        pj_add(words, NULL, pj_string("NUL"));
#else
        pj_add(words, NULL, pj_string("/dev/null"));
#endif
        p = pc_context_probe(c, words);
        if (!pc_probe_ok(c, &p, "effective header search roots")) {
            pc_probe_free(&p);
            goto fail;
        }
        pc_include_search(p.err, include_roots, dependencies, 0);
        if (!strcmp(family, "clang") && !pc_clang_sdk_inputs(c, p.err, paths, dependencies)) {
            pc_probe_free(&p);
            goto fail;
        }
        {
            const char *line = p.err;
            while ((line = strstr(line, "Configuration file: ")) != NULL) {
                const char *end;
                char *file;
                line += strlen("Configuration file: ");
                end = strchr(line, '\n');
                file = pc_slice(line, end ? (size_t)(end - line) : strlen(line));
                pc_trim(file);
                if (!pc_config_options(c, options, file)) {
                    free(file);
                    pc_probe_free(&p);
                    goto fail;
                }
                free(file);
            }
        }
        pc_probe_free(&p);
        {
            static const char *const files[] = {"specs", NULL};
            for (i = 0; files[i]; ++i) {
                PcBuffer flag = {0};
                pc_text(&flag, "-print-file-name=");
                pc_text(&flag, files[i]);
                words = pc_words(c, 1);
                pj_add(words, NULL, pj_string(flag.s));
                free(flag.s);
                p = pc_context_probe(c, words);
                if (!pc_probe_ok(c, &p, "compiler support component")) {
                    pc_probe_free(&p);
                    goto fail;
                }
                pc_trim(p.out);
                pc_add_component(paths, p.out);
                pc_probe_free(&p);
            }
        }
    }
    /* Headers of every runtime translation unit participate, including platform conditionals. */
    for (i = -4; i < 10; ++i) {
        char *runtime_source = NULL;
        size_t n;
        char *deps;
        if (i < 0 && !pc_stdlib_probe(c, source, (i + 4) & 1, ((i + 4) >> 1) & 1)) goto fail;
        if (i >= 0) {
            PcBuffer rel = {0};
            pc_text(&rel, "shared/runtime/src/");
            pc_text(&rel, i == 9 ? "dea_rt_trace" : pc_runtime_sources[i]);
            pc_text(&rel, ".c");
            runtime_source = pc_join(c->home, rel.s);
            free(rel.s);
        }
        words = i >= 0 ? pc_runtime_words(c) : pc_words(c, 1);
        pj_add(words, NULL, pj_string("-I"));
        if (i >= 0) {
            char *public = pc_join(c->home, "shared/runtime/include");
            pj_add(words, NULL, pj_string(public)); free(public);
        } else pj_add(words, NULL, pj_string(include));
        pj_add(words, NULL, pj_string("-I"));
        pj_add(words, NULL, pj_string(internal));
        pj_add(words, NULL, pj_string("-M"));
        pj_add(words, NULL, pj_string("-MF"));
        pj_add(words, NULL, pj_string(depfile));
        pj_add(words, NULL, pj_string(runtime_source ? runtime_source : source));
        p = pc_context_probe(c, words);
        free(runtime_source);
        if (!pc_probe_ok(c, &p, "SDK and runtime header dependencies")) {
            pc_probe_free(&p);
            goto fail;
        }
        pc_probe_free(&p);
        deps = pc_read_file(depfile, 4 * 1024 * 1024, &n);
        if (!deps || !pc_parse_dependencies(c, deps, paths, dependencies, scratch)) {
            free(deps);
            if (!c->error)
                pc_fail(c, 2154, "missing compiler dependency output", depfile);
            goto fail;
        }
        free(deps);
    }
    pc_option_inputs_dependencies(options, paths, dependencies);
    for (input = paths->child; input; input = input->next) {
        char *parent = pc_parent(input->key);
        pc_directory_dependency(dependencies, parent);
        free(parent);
    }
    if (!pc_implementation_libraries(c, paths, dependencies)) goto fail;
    pc_header_shadow_dependencies(include_roots, paths, dependencies);
    pc_probe_directory_free(scratch);
    free(scratch);
    free(source);
    free(depfile);
    free(include);
    free(internal);
    return discovery;
fail:
    if (scratch)
        pc_probe_directory_free(scratch);
    free(scratch);
    free(source);
    free(depfile);
    free(include);
    free(internal);
    pj_free(discovery);
    return NULL;
}
static void pc_decline(PcContext *c, const char *reason);
static void pc_option_eligibility(PcContext *c, const PcJson *options);

/** Forward target/ABI settings while keeping application flags out of runtime implementation builds. */
static int pc_runtime_target_options(PcContext *c, const PcJson *options) {
    const PcJson *o;
    for (o = options->child; o; o = o->next) {
        const char *s = o->text;
        int paired = !strcmp(s, "-target") || !strcmp(s, "--target") || !strcmp(s, "-isysroot") ||
            !strcmp(s, "--sysroot") || !strcmp(s, "-arch") || !strcmp(s, "-B") ||
            !strcmp(s, "-resource-dir") || !strcmp(s, "--gcc-toolchain") ||
            !strcmp(s, "--config-system-dir") || !strcmp(s, "--config-user-dir");
        if (!strcmp(s, "-mllvm")) {
            if (o->next) o = o->next;
            continue;
        }
        if (paired || !strcmp(s, "--no-default-config") ||
            !strncmp(s, "--config-system-dir=", 20) || !strncmp(s, "--config-user-dir=", 18) || !strncmp(s, "-m", 2) || !strncmp(s, "--target=", 9) ||
            !strncmp(s, "--sysroot=", 10) || !strncmp(s, "-isysroot", 9) ||
            !strncmp(s, "--gcc-toolchain=", 16) || !strncmp(s, "-resource-dir=", 14) ||
            (!strncmp(s, "-B", 2) && s[2]) || !strncmp(s, "-fshort-", 8) || !strncmp(s, "-fno-short-", 11) ||
            !strncmp(s, "-ffixed-", 8) || !strncmp(s, "-fcall-used-", 12) || !strncmp(s, "-fcall-saved-", 13) ||
            !strcmp(s, "-fpcc-struct-return") || !strcmp(s, "-freg-struct-return") ||
            !strcmp(s, "-fleading-underscore") || !strcmp(s, "-fno-leading-underscore") ||
            !strncmp(s, "-fpack-struct", 13) || !strncmp(s, "-fno-pack-struct", 16) || !strcmp(s, "-fPIC") || !strcmp(s, "-fpic") ||
            !strcmp(s, "-fPIE") || !strcmp(s, "-fpie") ||
            !strcmp(s, "-fno-PIC") || !strcmp(s, "-fno-pic") || !strcmp(s, "-fno-PIE") || !strcmp(s, "-fno-pie") ||
            !strcmp(s, "-pthread") || !strcmp(s, "-no-pthread")) {
            pj_add(c->runtime_options, NULL, pj_clone(o));
            if (paired) {
                if (!o->next) return pc_fail(c, 2154, "native target option requires a value", s);
                o = o->next; pj_add(c->runtime_options, NULL, pj_clone(o));
            }
        }
    }
    return 1;
}
/** Fall back to directly readable explicit config files when a wrapper cannot report selection. */
static int pc_runtime_known_configs(PcContext *c, PcOptionInputs *inputs) {
    const PcJson *option;
    for (option = inputs->direct->child; option; option = option->next) {
        const char *s = option->text, *file = NULL;
        if (!strncmp(s, "--config=", 9)) file = s + 9;
        else if (!strcmp(s, "--config") && option->next) { option = option->next; file = option->text; }
        if (file) {
            const PcJson *expanded = pc_config_options(c, inputs, file);
            if (!expanded || !pc_runtime_target_options(c, expanded)) return 0;
        }
    }
    return 1;
}

/** Observe Clang's selected configuration files before extracting target options only. */
static int pc_runtime_explicit_configs(PcContext *c, PcOptionInputs *inputs) {
    PcJson *words;
    PcProbe probe;
    const char *line;
    int ok = 1;
    if (strcmp(c->family, "clang")) return 1;
    words = pc_words(c, 1);
    pj_add(words, NULL, pj_string("-###"));
    pj_add(words, NULL, pj_string("-x")); pj_add(words, NULL, pj_string("c"));
    pj_add(words, NULL, pj_string("-c"));
#if defined(_WIN32)
    pj_add(words, NULL, pj_string("NUL"));
#else
    pj_add(words, NULL, pj_string("/dev/null"));
#endif
    probe = pc_context_probe(c, words);
    if (!pc_probe_ok(c, &probe, "effective configuration target options")) {
        pc_decline(c, c->error); pc_clear_error(c); pc_probe_free(&probe);
        return pc_runtime_known_configs(c, inputs);
    }
    c->runtime_config_observed = 1;
    line = probe.err;
    while (ok && (line = strstr(line, "Configuration file: ")) != NULL) {
        const char *end;
        char *path;
        const PcJson *expanded;
        line += strlen("Configuration file: "); end = strchr(line, '\n');
        path = pc_slice(line, end ? (size_t)(end - line) : strlen(line)); pc_trim(path);
        expanded = pc_config_options(c, inputs, path);
        if (expanded) pc_option_eligibility(c, expanded);
        ok = expanded && pc_runtime_target_options(c, expanded);
        free(path);
    }
    pc_probe_free(&probe);
    if (!ok) return 0;
    return 1;
}

/** The runtime baseline and tuning are compiler-owned, independent of legacy Make variables. */
static int pc_runtime_configuration(PcContext *c, const char *variant, PcOptionInputs *inputs) {
    c->runtime_options = pj_new(PJ_ARRAY);
    pj_add(c->runtime_options, NULL, pj_string("-O2"));
    pj_add(c->runtime_options, NULL, pj_string("-std=c99"));
    if (!pc_direct_options(c, inputs) || !pc_runtime_explicit_configs(c, inputs) ||
        !pc_runtime_target_options(c, inputs->direct)) return 0;
    /* All effective config targets were extracted above. Do not reload arbitrary
       generated-C configuration flags while compiling the runtime implementation. */
    if (c->runtime_config_observed) pj_add(c->runtime_options, NULL, pj_string("--no-default-config"));
    if (!strcmp(variant, "traced")) {
        pj_add(c->runtime_options, NULL, pj_string("-DDEA_TRACE_ARC"));
        pj_add(c->runtime_options, NULL, pj_string("-DDEA_TRACE_MEMORY"));
    } else if (!strcmp(variant, "unchecked")) pj_add(c->runtime_options, NULL, pj_string("-DDEA_RT_UNCHECKED"));
    else if (!strcmp(variant, "check_basic")) pj_add(c->runtime_options, NULL, pj_string("-DDEA_RT_CHECK_BASIC"));
    if (strcmp(variant, "unchecked")) {
        pj_add(c->runtime_options, NULL, pj_string("-D_RT_QUARANTINE_MAX_BYTES=16777216"));
        pj_add(c->runtime_options, NULL, pj_string("-D_RT_QUARANTINE_MAX_COUNT=4096"));
    }
    return 1;
}
/** Record a conservative refusal without preventing command-private compilation. */
static void pc_decline(PcContext *c, const char *reason) {
    if (!c->ineligible) c->ineligible = pc_string(reason);
}
/** These indirections require observations outside the supported adapter boundary. */
static void pc_option_eligibility(PcContext *c, const PcJson *options) {
    const PcJson *option;
    for (option = options->child; option; option = option->next) {
        const char *s = option->text;
        if (c->family && !strcmp(c->family, "clang") &&
                   (!strcmp(s, "-fno-integrated-as") || !strcmp(s, "-no-integrated-as"))) {
            pc_decline(c, "Clang external assembler selection is outside persistent reuse support");
        } else if (!strncmp(s, "-fplugin", 8) || !strncmp(s, "-fpass-plugin", 13) ||
            !strncmp(s, "-fprofile", 9) || !strncmp(s, "-fauto-profile", 14) || !strncmp(s, "-flto", 5) ||
            !strcmp(s, "-mllvm") || !strcmp(s, "-Xclang") || !strcmp(s, "-Xassembler") || !strcmp(s, "-Xpreprocessor") ||
            !strcmp(s, "-wrapper") || !strncmp(s, "-specs", 6) || !strncmp(s, "--specs", 7)) {
            pc_decline(c, "compiler plugin, profile, or opaque option indirection is outside persistent reuse support");
        }
    }
}

/** Resolve an invocable existing compiler family and its archive tool. */
static int pc_compilation_family(PcContext *c) {
    PcJson *words = pc_words(c, 0);
    PcProbe p;
    const char *family = NULL, *base = pc_base(c->compiler);
    unsigned char magic[4] = {0};
    FILE *f = fopen(c->compiler, "rb");
    if (f) { (void)fread(magic, 1, sizeof(magic), f); fclose(f); }
    if (magic[0] == '#' && magic[1] == '!') pc_decline(c, "opaque compiler wrapper is invocable but cannot authorize persistent reuse");
    pj_add(words, NULL, pj_string("--version"));
    p = pc_context_probe(c, words);
    if (p.status == 0 && !p.timed_out) {
        if (strstr(p.out, "clang") || strstr(p.err, "clang")) family = "clang";
        else if (strstr(p.out, "tcc") || strstr(p.out, "Tiny C")) family = "tcc";
        else if (strstr(p.out, "gcc") || strstr(p.out, "GCC") || strstr(p.out, "Free Software Foundation")) family = "gcc";
    }
    if (!family) {
        if (strstr(base, "clang")) family = "clang";
        else if (strstr(base, "tcc")) family = "tcc";
        else if (strstr(base, "gcc") || !strcmp(base, "cc")) family = "gcc";
        pc_decline(c, "compiler family/version observation is unavailable");
    }
    c->description = pc_string(p.out && *p.out ? p.out : (p.err ? p.err : ""));
    pc_trim(c->description); pc_probe_free(&p);
    if (!family) return pc_fail(c, 2154, "cannot identify an invocable GCC, Clang, or TinyCC compiler", c->compiler);
    c->family = pc_string(family);
    return 1;
}
/** Query the archive tool with the runtime configuration actually used to produce it. */
static int pc_compilation_toolchain(PcContext *c) {
    PcJson *words;
    PcProbe p;
    if (!strcmp(c->family, "tcc")) return 1;
    words = pc_runtime_words(c);
    pj_add(words, NULL, pj_string("-print-prog-name=ar"));
    p = pc_context_probe(c, words);
    if (p.status == 0 && !p.timed_out) { pc_trim(p.out); c->archiver = pc_executable(p.out); }
    pc_probe_free(&p);
    if (!c->archiver) return pc_fail(c, 2154, "selected compiler must locate a usable runtime archiver with -print-prog-name=ar", c->compiler);
    if (!pc_image_kind(c->archiver)) pc_decline(c, "opaque archive-tool wrapper cannot authorize persistent reuse");
    return 1;
}
/** Resolve D and N once. Probe failure declines reuse without disabling compilation. */
static int pc_resolve_native(PcContext *c) {
    PcJson *selection = NULL, *memo = NULL, *discovery = NULL, *components, *toolchain, *stdlib, *runtime;
    PcOptionInputs options = {0};
    const PcJson *path;
    char *memo_key = NULL, *memo_path, *cpu;
    const char *variant = pc_config(c, "variant");
    int ok = 0;
    if (c->native_resolved) return !c->error;
    ++c->resolutions;
    if (!pc_roots(c) || !pc_resolve_dea(c)) goto finish;
    c->compiler = pc_executable(pc_config(c, "compiler"));
    if (!c->compiler) {
        pc_fail(c, 2154, "cannot resolve selected C compiler", pc_config(c, "compiler")); goto finish;
    }
    if (!*variant) variant = "default";
    if (!pc_runtime_archive(variant)) { pc_fail(c, 2154, "invalid runtime variant", variant); goto finish; }
    if (!pc_compilation_family(c) || !pc_runtime_configuration(c, variant, &options)) goto finish;
    pc_option_eligibility(c, options.direct);
    selection = pj_new(PJ_OBJECT);
    pj_set_number(selection, "adapter", 1);
    /* A compiler implementation change can tighten observation rules. Old
       discovery memos must not bypass the current adapter through a new D. */
    pj_set_string(selection, "D", c->dea_key);
    pj_set_string(selection, "compiler", c->compiler);
    pj_set_string(selection, "include", c->include);
    pj_set_string(selection, "source_home", c->home);
    {
        char *cwd = pc_path_call(".", l1c_fs_absolute_path);
        if (cwd) { pj_set_string(selection, "cwd", cwd); free(cwd); }
    }
    pj_add(selection, "options", pj_clone(c->options));
    pj_add(selection, "runtime_options", pj_clone(c->runtime_options));
    pj_add(selection, "environment", pc_selection_environment());
    cpu = pc_cpu_identity(c->options);
    pj_set_string(selection, "native_cpu", cpu); free(cpu);
    if (!pc_apple_selection(c, selection)) { pc_decline(c, c->error); pc_clear_error(c); }
    if (*pc_env("LD_PRELOAD") || *pc_env("LD_AUDIT") || *pc_env("CCC_OVERRIDE_OPTIONS"))
        pc_decline(c, "unsupported native compiler indirection in the environment");
#if defined(__APPLE__)
    {
        char **variable;
        for (variable = *_NSGetEnviron(); *variable; ++variable) {
            const char *value = strchr(*variable, '=');
            if (!strncmp(*variable, "DYLD_", 5) && value && value[1])
                pc_decline(c, "unsupported dynamic-loader indirection in the environment");
        }
    }
#endif
    memo_key = pc_json_digest(selection);
    memo_path = pc_memo_path(c, "toolchains", memo_key, 0);
    if (memo_path && !c->force && !c->ineligible) memo = pc_read_json(memo_path);
    free(memo_path);
    if (pc_memo_valid(memo, "identity") && pc_discovery_current(c, memo)) {
        discovery = pj_clone(pj_get(memo, "discovery"));
        pj_free(c->old_files); c->old_files = pj_clone(pj_get(memo, "files"));
        if (strcmp(c->family, "tcc")) c->archiver = pc_string(pj_field(pj_get(discovery, "toolchain"), "archiver"));
        if (pc_verbosity(c) >= 3) fputs("Preparation toolchain memo: validated observation\n", stderr);
    } else {
        if (!pc_compilation_toolchain(c)) goto finish;
        pc_load_input_memo(c, memo_key);
        if (!c->ineligible) discovery = pc_discover_toolchain(c, selection, &options);
        if (!discovery && c->error) { pc_decline(c, c->error); pc_clear_error(c); }
    }
    pj_free(memo); memo = NULL;
    components = pj_new(PJ_OBJECT);
    if (discovery) {
        for (path = pj_get(discovery, "paths")->child; path; path = path->next) {
            char *digest = pc_input_digest(c, path->key);
            if (!digest) { pc_decline(c, c->error); pc_clear_error(c); break; }
            pj_set_string(components, path->key, digest); free(digest);
        }
        toolchain = pj_clone(pj_get(discovery, "toolchain"));
    } else {
        toolchain = pj_new(PJ_OBJECT);
        pj_set_string(toolchain, "family", c->family);
        pj_set_string(toolchain, "target", "unobserved");
        pj_set_string(toolchain, "invocation", c->compiler);
    }
    if (c->archiver && !pj_get(toolchain, "archiver"))
        pj_set_string(toolchain, "archiver", c->archiver);
    pj_add(toolchain, "components", components);
    pj_add(toolchain, "environment", pj_clone(pj_get(selection, "environment")));
    if (pj_field(selection, "apple_sdk")) pj_set_string(toolchain, "apple_sdk", pj_field(selection, "apple_sdk"));
    pj_set_string(toolchain, "native_cpu", pj_field(selection, "native_cpu"));
    c->native = pj_new(PJ_OBJECT);
    pj_set_number(c->native, "schema", 1);
    pj_set_number(c->native, "adapter", 1);
    pj_set_string(c->native, "D", c->dea_key);
    pj_add(c->native, "dea_inputs", pj_clone(c->dea));
    pj_add(c->native, "toolchain", toolchain);
    stdlib = pj_new(PJ_OBJECT);
    pj_add(stdlib, "options", pj_clone(c->options));
    pj_add(stdlib, "codegen", pj_get(c->config, "codegen") ? pj_clone(pj_get(c->config, "codegen")) : pj_new(PJ_OBJECT));
    pj_set_string(stdlib, "include", c->include);
    pj_add(c->native, "stdlib", stdlib);
    runtime = pj_new(PJ_OBJECT);
    pj_add(runtime, "options", pj_clone(c->runtime_options));
    pj_set_string(runtime, "variant", variant);
    pj_add(c->native, "runtime", runtime);
    c->native_key = pc_json_digest(c->native);
    c->native_resolved = 1;
    if (discovery && !c->ineligible) pc_save_input_memo(c, memo_key, discovery);
    ok = 1;
finish:
    pj_free(memo); pj_free(discovery); pj_free(selection); free(memo_key);
    pc_option_inputs_free(&options);
    return ok;
}
#endif
