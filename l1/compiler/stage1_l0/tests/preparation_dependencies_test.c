/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file preparation_dependencies_test.c Exercise the private production dependency decoder. */
#include "../support/preparation_support.c"

#define BS "\\"

/** Fail with a named case without relying on assertion build flags. */
static void require_case(int condition, const char *name) {
    if (!condition) {
        fprintf(stderr, "preparation dependency fixture failed: %s\n", name);
        exit(1);
    }
}

/** Cover compiler Make quoting with explicit expected prerequisite spellings. */
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

/** Quote fixture paths using the documented compiler Make output spelling. */
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

/** Preserve malformed-response diagnostics, real-file checks and scratch exclusion. */
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

/** Read failures decline reuse while leaving the existing version probe and family fallback active. */
static void check_family(const char *path, const char *reason, const char *name) {
    PcContext *c = pc_alloc(sizeof(*c));
    c->config = pj_new(PJ_OBJECT);
    pj_set_number(c->config, "probe_timeout_ms", 2000);
    c->compiler = pc_string(path);
    require_case(pc_compilation_family(c) && !c->error && c->probes == 1 && !strcmp(c->family, "gcc"), name);
    require_case(reason ? c->ineligible && strstr(c->ineligible, reason) : !c->ineligible, name);
    l1c_prep_free(c);
}

/** Resolve the archive tool reported by a compiler while preserving a path with spaces. */
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

#if defined(_WIN32)
/** Accept MSYS-style and extensionless tool paths when the compiler is native Windows. */
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

/** Clean short reads are not I/O failures, and only a complete shebang prefix identifies a wrapper. */
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

/** Run privately linked production checks in a caller-owned empty directory. */
int main(int argc, char **argv) {
    char *directory, *self;
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
    check_image_reads(self, directory);
    check_reported_tool(self);
#if defined(_WIN32)
    check_windows_reported_path(self);
#endif
    free(directory); free(self);
    puts("preparation dependency decoding and compiler image reads: PASS");
    return 0;
}
