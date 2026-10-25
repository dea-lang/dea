/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file preparation_dependencies_test.c Exercise the private production dependency decoder.
 */
#if defined(_WIN32)
#include <windows.h>

static int probe_exit_race, probe_exit_observed, probe_exit_error;

/**
 * Model output arriving after empty pipe checks but before process exit is observed.
 *
 * @param pipe Borrowed native pipe handle.
 * @param buffer Address of the owned growable byte buffer.
 * @param size Requested storage size in bytes.
 * @param read Caller-owned output for bytes copied by the pipe query.
 * @param available Caller-owned output for available pipe bytes.
 * @param remaining Caller-owned output for bytes remaining in the current message.
 * @return Native query status under the controlled fixture schedule.
 */
static BOOL WINAPI fixture_peek_pipe(HANDLE pipe, LPVOID buffer, DWORD size,
                                     LPDWORD read, LPDWORD available, LPDWORD remaining) {
    if (probe_exit_race && !probe_exit_observed) {
        *available = 0;
        return TRUE;
    }
    return PeekNamedPipe(pipe, buffer, size, read, available, remaining);
}

/**
 * Make the competing child completion deterministic without a timing assumption.
 *
 * @param process Borrowed native process handle.
 * @param code Diagnostic code to retain.
 * @return Native success status after writing the controlled child exit code.
 */
static BOOL WINAPI fixture_exit_code(HANDLE process, LPDWORD code) {
    BOOL ok;
    if (probe_exit_error) return FALSE;
    if (probe_exit_race && WaitForSingleObject(process, 5000) != WAIT_OBJECT_0)
        return FALSE;
    ok = GetExitCodeProcess(process, code);
    if (probe_exit_race && ok && *code != STILL_ACTIVE) probe_exit_observed = 1;
    return ok;
}
#define PeekNamedPipe fixture_peek_pipe
#define GetExitCodeProcess fixture_exit_code
#endif
#include "../support/preparation_support.c"

#define BS "\\"

/**
 * Fail with a named case without relying on assertion build flags.
 *
 * @param condition Predicate required to hold for the fixture.
 * @param name Borrowed NUL-terminated name.
 */
static void require_case(int condition, const char *name) {
    if (!condition) {
        fprintf(stderr, "preparation dependency fixture failed: %s\n", name);
        exit(1);
    }
}

/**
 * Cover compiler Make quoting with explicit expected prerequisite spellings.
 */
static void check_tokens(void) {
    static const struct {
        const char *name, *text, *expected[8];
    } cases[] = {
        {"empty", " \t\r\n", {NULL}},
        {"ordinary", "first second\tthird\r\nfourth", {"first", "second", "third", "fourth", NULL}},
        {"drive", "D:" BS "a" BS "_temp" BS "msys64" BS "tmp" BS "l1p4584.tmp/probe.c",
         {"D:" BS "a" BS "_temp" BS "msys64" BS "tmp" BS "l1p4584.tmp/probe.c", NULL}},
        {"UNC", BS BS "server" BS "share/header.h", {BS BS "server" BS "share/header.h", NULL}},
        {"literal backslashes", "/tmp/a" BS "b/one.h /tmp/a" BS BS "b/two.h",
         {"/tmp/a" BS "b/one.h", "/tmp/a" BS BS "b/two.h", NULL}},
        {"escaped spaces and tabs", "one" BS " two three" BS "\tfour",
         {"one two", "three\tfour", NULL}},
        {"two slashes before space", "one" BS BS " two", {"one" BS, "two", NULL}},
        {"three slashes before space", "one" BS BS BS " two", {"one" BS " two", NULL}},
        {"four slashes before space", "one" BS BS BS BS " two", {"one" BS BS, "two", NULL}},
        {"five slashes before space", "one" BS BS BS BS BS " two", {"one" BS BS " two", NULL}},
        {"two slashes before tab", "one" BS BS "\ttwo", {"one" BS, "two", NULL}},
        {"three slashes before tab", "one" BS BS BS "\ttwo", {"one" BS "\ttwo", NULL}},
        {"hashes", "one" BS "#two three" BS BS "#four five" BS BS BS "#six #seven",
         {"one#two", "three" BS "#four", "five" BS BS "#six", "#seven", NULL}},
        {"dollars", "one$$two $$$$three $four end$", {"one$two", "$$three", "$four", "end$", NULL}},
        {"LF continuation", "one " BS "\n two" BS "\nthree", {"one", "two", "three", NULL}},
        {"CRLF continuation", "one " BS "\r\n two" BS "\r\nthree", {"one", "two", "three", NULL}},
        {"paired slashes at continuation", "one" BS BS BS "\n two" BS BS BS "\r\nthree",
         {"one" BS, "two" BS, "three", NULL}},
        {"even slashes at newline", "one" BS BS "\n two" BS BS BS BS "\r\nthree",
         {"one" BS, "two" BS BS, "three", NULL}},
        {"adjacent continuations", BS "\n" BS "\r\n one", {"one", NULL}},
        {"trailing backslashes", "one" BS " two" BS BS, {"one two" BS BS, NULL}},
        {"bare carriage return", "one" BS "\rtwo", {"one" BS, "two", NULL}}
    };
    PcBuffer token = {0};
    size_t i, j;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        const char *p = cases[i].text;
        for (j = 0; cases[i].expected[j]; ++j) {
            require_case(pc_dependency_token(&p, &token), cases[i].name);
            if (strcmp(token.s, cases[i].expected[j])) {
                fprintf(stderr, "expected [%s], decoded [%s]\n", cases[i].expected[j], token.s);
                require_case(0, cases[i].name);
            }
        }
        require_case(!pc_dependency_token(&p, &token) && !*p, cases[i].name);
    }
    free(token.s);
}

/**
 * Quote fixture paths using the documented compiler Make output spelling.
 *
 * @param text Mutable growable byte buffer owned by the caller.
 * @param path Borrowed NUL-terminated filesystem path.
 */
static void fixture_path(PcBuffer *text, const char *path) {
    size_t slashes = 0;
    for (; *path; ++path) {
        if (*path == ' ' || *path == '\t') {
            while (slashes) { pc_char(text, '\\'); --slashes; }
            pc_char(text, '\\');
        } else if (*path == '#') pc_char(text, '\\');
        else if (*path == '$') pc_char(text, '$');
        slashes = *path == '\\' ? slashes + 1 : 0;
        pc_char(text, *path);
    }
}

/**
 * Preserve malformed-response diagnostics, real-file checks and scratch exclusion.
 *
 * @param directory Borrowed directory path.
 */
static void check_dependencies(const char *directory) {
    static const char *const malformed[] = {"", "target", "D:" BS "path" BS "probe.c"};
    PcContext c = {0};
    PcJson *paths = pj_new(PJ_OBJECT), *directories = pj_new(PJ_OBJECT);
    PcBuffer text = {0};
    char *scratch = pc_join(directory, "scratch"), *header = pc_join(directory, "header.h");
    char *source = pc_join(scratch, "probe.c"), *missing = pc_join(directory, "missing.h");
    char *absolute_header = pc_path_call(header, l1c_fs_absolute_path);
    size_t i;
    c.compiler = "dependency-fixture";
    require_case(pc_mkdirs(scratch), "create scratch");
    require_case(pc_write_file(header, "/* fixture */\n", 14), "write header");
    for (i = 0; i < sizeof(malformed) / sizeof(malformed[0]); ++i) {
        require_case(!pc_parse_dependencies(&c, malformed[i], paths, directories, scratch) &&
                     c.error_code == 2154 && strstr(c.error, "malformed compiler dependency response"),
                     "malformed response diagnostic");
        pc_clear_error(&c);
    }
    require_case(pc_parse_dependencies(&c, "target:", paths, directories, scratch), "empty prerequisites");
    pc_text(&text, "D:/output.o: ");
    fixture_path(&text, source); pc_char(&text, ' '); fixture_path(&text, header);
    require_case(pc_parse_dependencies(&c, text.s, paths, directories, scratch), "regular dependency");
    require_case(paths->count == 1 && directories->count == 1, "scratch excluded, header retained");
    require_case(absolute_header && !strcmp(paths->child->text, absolute_header), "retained absolute spelling");
    text.n = 0; text.s[0] = 0;
    pc_text(&text, "target: "); fixture_path(&text, missing);
    require_case(!pc_parse_dependencies(&c, text.s, paths, directories, scratch) &&
                 c.error_code == 2154 && strstr(c.error, "compiler dependency is unavailable"),
                 "missing dependency diagnostic");
    pc_clear_error(&c);
    text.n = 0; text.s[0] = 0;
    pc_text(&text, "target: "); fixture_path(&text, directory);
    require_case(!pc_parse_dependencies(&c, text.s, paths, directories, scratch) &&
                 c.error_code == 2154 && strstr(c.error, "compiler dependency is unavailable"),
                 "nonregular dependency diagnostic");
    pc_clear_error(&c);
    pj_free(paths); pj_free(directories); free(text.s);
    require_case(remove(header) == 0 && pc_remove_owned_tree(scratch), "remove dependency fixture");
    free(scratch); free(header); free(source); free(missing); free(absolute_header);
}

/**
 * Require complete source coverage before accepting any batched dependency evidence.
 *
 * @param directory Borrowed directory path.
 */
static void check_dependency_batches(const char *directory) {
    PcContext c = {0};
    PcJson *sources = pj_new(PJ_ARRAY), *paths = pj_new(PJ_OBJECT), *directories = pj_new(PJ_OBJECT);
    PcBuffer first = {0}, second = {0}, combined = {0};
    char *scratch = pc_join(directory, "batch scratch"), *header = pc_join(directory, "batch #$.h");
    char *a = pc_join(scratch, "a.c"), *b = pc_join(scratch, "b.c");
    size_t i;
    c.compiler = "dependency-batch-fixture";
    require_case(pc_mkdirs(scratch) && pc_write_file(header, "/* fixture */\n", 14), "batch fixture files");
    pj_add(sources, NULL, pj_string(a)); pj_add(sources, NULL, pj_string(b));
    pc_text(&first, "l1-preparation: "); fixture_path(&first, a);
    pc_text(&first, " \\\r\n "); fixture_path(&first, header); pc_text(&first, "\r\n");
    pc_text(&second, "l1-preparation: "); fixture_path(&second, b); pc_char(&second, '\n');
    pc_text(&combined, first.s); pc_text(&combined, second.s);
    require_case(pc_parse_dependency_batch(&c, combined.s, sources, paths, directories, scratch) &&
                 pj_count(paths) == 1 && pj_count(directories) == 1,
                 "all source rules and escaped prerequisites retained");
    pj_free(paths); pj_free(directories);
    paths = pj_new(PJ_OBJECT); directories = pj_new(PJ_OBJECT);
    for (i = 0; i < 5; ++i) {
        PcBuffer invalid = {0};

        /* Missing source rule. */
        if (i == 0) pc_text(&invalid, first.s);

        /* Duplicate source. */
        if (i == 1) { pc_text(&invalid, first.s); pc_text(&invalid, first.s); }
        if (i == 2) { pc_text(&invalid, combined.s); pc_text(&invalid, "other-target: unknown.h\n"); }
        if (i == 3) pc_text(&invalid, "l1-preparation: unknown-source.c\n");
        if (i == 4) {
            pc_text(&invalid, first.s); pc_text(&invalid, "l1-preparation: "); fixture_path(&invalid, b);
            pc_text(&invalid, " "); fixture_path(&invalid, directory); pc_char(&invalid, '\n');
        }
        require_case(!pc_parse_dependency_batch(&c, invalid.s, sources, paths, directories, scratch) &&
                     !pj_count(paths) && !pj_count(directories), "invalid batch cannot publish partial evidence");
        pc_clear_error(&c); free(invalid.s);
    }
    {
        PcJson *spelling_sources = pj_new(PJ_ARRAY);
        PcBuffer spelling_rule = {0};
        char *spelling = pc_string(a);
#if defined(_WIN32)

        /* Exercise native drive paths, spaces, mixed separators and case. */
        for (i = 0; spelling[i]; ++i)
            spelling[i] = spelling[i] == '/' && (i & 1) ? '\\' : (char)toupper((unsigned char)spelling[i]);
        pj_add(spelling_sources, NULL, pj_string(a));
#else

        /* POSIX filename backslashes remain distinct from directory separators. */
        free(spelling); spelling = pc_join(scratch, "literal\\backslash.c");
        pj_add(spelling_sources, NULL, pj_string(spelling));
#endif
        pc_text(&spelling_rule, "l1-preparation: "); fixture_path(&spelling_rule, spelling);
        require_case(pc_parse_dependency_batch(&c, spelling_rule.s, spelling_sources, paths, directories, scratch),
                     "native equivalent source spelling");
        spelling_rule.n = 0; spelling_rule.s[0] = 0;
#if defined(_WIN32)
        pc_text(&spelling_rule, "l1-preparation: "); fixture_path(&spelling_rule, b);
#else
        for (i = 0; spelling[i]; ++i) if (spelling[i] == '\\') spelling[i] = '/';
        pc_text(&spelling_rule, "l1-preparation: "); fixture_path(&spelling_rule, spelling);
#endif
        require_case(!pc_parse_dependency_batch(&c, spelling_rule.s, spelling_sources, paths, directories, scratch),
                     "genuinely different source spelling rejected");
        pj_free(spelling_sources); free(spelling_rule.s); free(spelling);
    }
    require_case(remove(header) == 0 && pc_remove_owned_tree(scratch), "remove batch fixture");
    pj_free(sources); pj_free(paths); pj_free(directories);
    free(first.s); free(second.s); free(combined.s); free(scratch); free(header); free(a); free(b);
}

/**
 * Model optional batch rejection and preserve the original individual dependency contract.
 *
 * @param argc Number of process argument words.
 * @param argv Borrowed NUL-terminated process argument vector.
 * @return Zero after serving a fixture command, or the child failure status.
 */
static int dependency_probe_fixture(int argc, char **argv) {
    const char *mode = argv[1] + strlen("--dependency-fixture="), *depfile = NULL;
    int i, batch = 0, first = 1;
    PcBuffer output = {0};
    for (i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "-MT")) { batch = 1; ++i; }
        else if (!strcmp(argv[i], "-MF")) depfile = argv[++i];
    }
    if (!strcmp(mode, "failure")) { fputs("fixture dependency failure", stderr); return 7; }
    if (batch && !strcmp(mode, "unsupported")) return 8;
    if (batch && !strcmp(mode, "timeout")) {
#if defined(_WIN32)
        Sleep(1200);
#else
        struct timespec delay = {1, 200000000};
        nanosleep(&delay, NULL);
#endif
        return 0;
    }
    if (batch && !strcmp(mode, "overflow")) {
        for (i = 0; i < 4 * 1024 * 1024 + 8192; ++i) putchar('x');
        return 0;
    }
    for (i = 2; i < argc; ++i) {
        if (!pc_ends(argv[i], ".c")) continue;
        if (batch && !strcmp(mode, "incomplete") && !first) continue;
        pc_text(&output, "l1-preparation: "); fixture_path(&output, argv[i]); pc_char(&output, '\n');
        first = 0;
    }
    if (depfile) {
        int ok = pc_write_file(depfile, output.s, output.n);
        free(output.s); return ok ? 0 : 9;
    }
    fputs(output.s ? output.s : "", stdout); free(output.s);
    return 0;
}

/**
 * Exercise unsupported, incomplete, failed, timed-out and oversized optional batches.
 *
 * @param self Borrowed path of the running fixture executable.
 * @param directory Borrowed directory path.
 */
static void check_dependency_probe_fallback(const char *self, const char *directory) {
    static const char *const modes[] = {"valid", "unsupported", "incomplete", "timeout", "overflow", "failure"};
    PcContext c = {0};
    PcJson *sources = pj_new(PJ_ARRAY);
    char *scratch = pc_join(directory, "fallback"), *a = pc_join(scratch, "a.c"),
         *b = pc_join(scratch, "b.c"), *depfile = pc_join(scratch, "dependencies.d");
    size_t i;
    c.compiler = (char *)self; c.family = "gcc";
    c.config = pj_new(PJ_OBJECT); c.options = pj_new(PJ_ARRAY); c.runtime_options = pj_new(PJ_ARRAY);
    require_case(pc_mkdirs(scratch), "create fallback fixture");
    pj_add(sources, NULL, pj_string(a)); pj_add(sources, NULL, pj_string(b));
    for (i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i) {
        PcBuffer option = {0};
        PcJson *paths = pj_new(PJ_OBJECT), *directories = pj_new(PJ_OBJECT);
        int ok;
        pc_text(&option, "--dependency-fixture="); pc_text(&option, modes[i]);
        pj_free(c.options); c.options = pj_new(PJ_ARRAY); pj_add(c.options, NULL, pj_string(option.s));
        pj_free(c.config); c.config = pj_new(PJ_OBJECT);
        pj_set_number(c.config, "probe_timeout_ms", i == 3 ? 1000 : 2000);
        c.probes = 0;
        ok = pc_dependency_probes(&c, sources, 0, 1, directory, directory, scratch, depfile, paths, directories);
        require_case(i == 5 ? !ok && c.probes == 2 && c.error_code == 2154 &&
                     strstr(c.error, "fixture dependency failure") : ok && !c.error &&
                     c.probes == (i ? 3 : 1), "batch fallback status and probe count");
        require_case(!pj_count(paths) && !pj_count(directories), "scratch source exclusion after fallback");
        pc_clear_error(&c); pj_free(paths); pj_free(directories); free(option.s);
    }
    require_case(pc_remove_owned_tree(scratch), "remove fallback fixture");
    pj_free(sources); pj_free(c.config); pj_free(c.options); pj_free(c.runtime_options);
    free(scratch); free(a); free(b); free(depfile);
}

/**
 * Keep unmeasured adapters and hosts on their original individual dependency probes.
 */
static void check_dependency_batch_policy(void) {
    PcContext c = {0};
    c.family = "clang"; c.description = "Apple clang version 17.0.0";
#if defined(__APPLE__)
    require_case(pc_dependency_batch_supported(&c), "measured Apple Clang enables batching");
#else
    require_case(!pc_dependency_batch_supported(&c), "unmeasured host retains individual probes");
#endif
    c.family = "gcc";
    require_case(!pc_dependency_batch_supported(&c), "GCC retains individual probes");
    c.family = "clang"; c.description = "Debian clang version 19.1.7";
    require_case(!pc_dependency_batch_supported(&c), "upstream Clang retains individual probes");
    c.description = NULL;
    require_case(!pc_dependency_batch_supported(&c), "unavailable compiler description retains individual probes");
}

/**
 * Read failures decline reuse while leaving the existing version probe and family fallback active.
 *
 * @param path Borrowed NUL-terminated filesystem path.
 * @param reason Borrowed diagnostic or observation reason.
 * @param name Borrowed NUL-terminated name.
 */
static void check_family(const char *path, const char *reason, const char *name) {
    PcContext *c = pc_alloc(sizeof(*c));
    c->config = pj_new(PJ_OBJECT);
    pj_set_number(c->config, "probe_timeout_ms", 2000);
    c->compiler = pc_string(path);
    require_case(pc_compilation_family(c) && !c->error && c->probes == 1 && !strcmp(c->family, "gcc"), name);
    require_case(reason ? c->ineligible && strstr(c->ineligible, reason) : !c->ineligible, name);
    l1c_prep_free(c);
}

/**
 * Resolve the archive tool reported by a compiler while preserving a path with spaces.
 *
 * @param self Borrowed path of the running fixture executable.
 */
static void check_reported_tool(const char *self) {
    PcContext *c = pc_alloc(sizeof(*c));
    c->config = pj_new(PJ_OBJECT);
    pj_set_number(c->config, "probe_timeout_ms", 2000);
    c->compiler = pc_string(self);
    c->family = pc_string("gcc");
    c->runtime_options = pj_new(PJ_ARRAY);
    require_case(pc_compilation_toolchain(c) && !c->error && c->archiver && pc_path_equal(c->archiver, self),
                 "reported archive tool path");
    l1c_prep_free(c);
}

/**
 * Retain both output streams and the exit status when a short-lived probe finishes.
 *
 * @param self Borrowed path of the running fixture executable.
 */
static void check_probe_output(const char *self) {
    PcJson *words = pj_new(PJ_ARRAY);
    PcProbe probe;
#if defined(_WIN32)
    probe_exit_race = 1;
    probe_exit_observed = 0;
#endif
    pj_add(words, NULL, pj_string(self));
    pj_add(words, NULL, pj_string("--probe-output"));
    probe = pc_probe(words, 10000);
    require_case(probe.status == 23 && !probe.timed_out &&
                 !strcmp(probe.out, "probe stdout") && !strcmp(probe.err, "probe stderr"),
                 "completed probe retains stdout, stderr and exit status");
    pc_probe_free(&probe);
#if defined(_WIN32)
    probe_exit_observed = 0;
    check_family(self, NULL, "completed version probe remains eligible");
    probe_exit_race = 0;
    probe_exit_error = 1;
    probe = pc_probe(words, 10000);
    require_case(probe.status == -1 && !probe.timed_out, "failed exit-status query fails the probe");
    pc_probe_free(&probe);
    probe_exit_error = 0;
#endif
    pj_free(words);
}

/**
 * Preserve synthetic POSIX, drive, UNC and mixed-separator config paths through real argv.
 *
 * @param self Borrowed path of the running fixture executable.
 */
static void check_runtime_isolation_argv(const char *self) {
    static const char *const paths[] = {
        "/tmp/config directory/empty.cfg",
        "C:" BS "config directory" BS "empty.cfg",
        "C:/config directory" BS "nested/empty.cfg",
        BS BS "server" BS "shared directory" BS "empty.cfg",
        "/tmp/config with \"quotes\"/empty.cfg"
    };
    PcContext c = {0};
    size_t i;
    c.compiler = (char *)self;
    c.runtime_options = pj_new(PJ_ARRAY);
    pj_add(c.runtime_options, NULL, pj_string("--runtime-isolation-argv"));
    c.clang_isolation = 2;
    for (i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
        PcJson *words;
        PcProbe probe;
        c.clang_config_path = (char *)paths[i];
        words = pc_runtime_words(&c);
        probe = pc_probe(words, 10000);
        require_case(probe.status == 0 && !probe.timed_out && !strcmp(probe.out, paths[i]),
                     "physical config path survives subprocess argv exactly");
        require_case(!strcmp(pc_runtime_isolation(&c), "clang-explicit-empty-config-v1"),
                     "different physical paths retain one stable isolation identity");
        require_case(c.runtime_options->child && !c.runtime_options->child->next,
                     "physical config arguments do not mutate identity options");
        pc_probe_free(&probe);
        pj_free(words);
    }
    pj_free(c.runtime_options);
}

#if defined(_WIN32)

/**
 * Accept MSYS-style and extensionless tool paths when the compiler is native Windows.
 *
 * @param self Borrowed path of the running fixture executable.
 */
static void check_windows_reported_path(const char *self) {
    const char *base = pc_base(self);
    size_t length = strlen(base);
    char *reported = pc_join("/ucrt64/bin", base);
    char *extensionless;
    char *reported_extensionless;
    char *resolved;
    require_case(length > 4 && !strcmp(base + length - 4, ".exe"), "Windows executable fixture suffix");
    extensionless = pc_slice(base, length - 4);
    reported_extensionless = pc_join("/ucrt64/bin", extensionless);
    resolved = pc_reported_executable(reported, self);
    require_case(resolved && pc_path_equal(resolved, self), "MSYS reported executable path");
    free(resolved);
    resolved = pc_reported_executable(reported_extensionless, self);
    require_case(resolved && pc_path_equal(resolved, self), "extensionless reported executable path");
    free(resolved);
    free(reported);
    free(extensionless);
    free(reported_extensionless);
}
#endif

/**
 * Clean short reads are not I/O failures, and only a complete shebang prefix identifies a wrapper.
 *
 * @param self Borrowed path of the running fixture executable.
 * @param directory Borrowed directory path.
 */
static void check_image_reads(const char *self, const char *directory) {
    static const char *const contents[] = {"", "#", "#!", "ABCD"};
    char *path = pc_join(directory, "gcc");
    size_t i;
    check_family(self, NULL, "readable native compiler image");
    check_family(path, "compiler image cannot be read", "missing image still probes");
    for (i = 0; i < sizeof(contents) / sizeof(contents[0]); ++i) {
        require_case(pc_write_file(path, contents[i], strlen(contents[i])), "write compiler image");
        check_family(path, i == 2 ? "opaque compiler wrapper" : "compiler family/version observation is unavailable",
                     "short image and shebang classification");
    }
    require_case(remove(path) == 0 && pc_mkdirs(path), "create unreadable directory image");
    check_family(path, "compiler image cannot be read", "failed image read still probes");
    require_case(pc_remove_owned_tree(path), "remove compiler image fixture");
    free(path);
}

/**
 * Run privately linked production checks in a caller-owned empty directory.
 *
 * @param argc Number of process argument words.
 * @param argv Borrowed NUL-terminated process argument vector.
 * @return Zero when all requested checks succeed; nonzero for invalid invocation or a fixture failure.
 */
int main(int argc, char **argv) {
    char *directory, *self;
    if (argc == 4 && !strcmp(argv[1], "--runtime-isolation-argv") && !strcmp(argv[2], "--config")) {
        fputs(argv[3], stdout);
        return 0;
    }
    if (argc > 2 && !strncmp(argv[1], "--dependency-fixture=", strlen("--dependency-fixture=")))
        return dependency_probe_fixture(argc, argv);
    if (argc == 2 && !strcmp(argv[1], "--probe-output")) {
        fputs("probe stdout", stdout);
        fputs("probe stderr", stderr);
        return 23;
    }
    if (argc == 2 && !strcmp(argv[1], "--version")) {
        puts("gcc (preparation dependency fixture)");
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "-print-prog-name=ar")) {
        puts(argv[0]);
        return 0;
    }
    require_case(argc == 2, "expected owned fixture directory argument");
    directory = pc_path_call(argv[1], l1c_fs_canonical_existing_path);
    self = pc_path_call(argv[0], l1c_fs_absolute_path);
    require_case(directory && self && pc_kind(directory, 1) == 2, "existing fixture directory");
    check_tokens();
    check_dependencies(directory);
    check_dependency_batches(directory);
    check_dependency_probe_fallback(self, directory);
    check_dependency_batch_policy();
    check_image_reads(self, directory);
    check_reported_tool(self);
    check_probe_output(self);
    check_runtime_isolation_argv(self);
#if defined(_WIN32)
    check_windows_reported_path(self);
#endif
    free(directory); free(self);
    puts("preparation dependency decoding and compiler image reads: PASS");
    return 0;
}
