/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file preparation_libraries_test.c Exercise production PE import reads on every host. */
#include "../support/preparation_support.c"
#include "../support/preparation/pe_imports.h"

static void require_case(int condition, const char *name) {
    if (!condition) {
        fprintf(stderr, "preparation PE fixture failed: %s\n", name);
        exit(1);
    }
}
static void fixture_u16(unsigned char *p, unsigned value) {
    p[0] = (unsigned char)value; p[1] = (unsigned char)(value >> 8);
}
static void fixture_u32(unsigned char *p, uint32_t value) {
    unsigned i;
    for (i = 0; i < 4; ++i) p[i] = (unsigned char)(value >> (i * 8));
}

/** Keep import descriptors and names in separate sections to exercise RVA mapping. */
static unsigned char *fixture_image(int plus, int large, size_t *size) {
    unsigned optional_size = plus ? 240 : 224, directories = plus ? 112 : 96;
    unsigned char *bytes, *optional, *section;
    unsigned i;
    *size = 0xa00 + (large ? 70000 * 12 : 0);
    bytes = pc_alloc(*size);
    memcpy(bytes, "MZ", 2); fixture_u32(bytes + 60, 0x80);
    memcpy(bytes + 0x80, "PE\0\0", 4);
    fixture_u16(bytes + 0x84, plus ? 0x8664 : 0x14c);
    fixture_u16(bytes + 0x86, large ? 3 : 2);
    fixture_u16(bytes + 0x94, optional_size);
    fixture_u16(bytes + 0x96, 0x22);
    optional = bytes + 0x98;
    fixture_u16(optional, plus ? 0x20b : 0x10b);
    fixture_u32(optional + (plus ? 24 : 28), 0x400000);
    fixture_u32(optional + 32, 0x1000); fixture_u32(optional + 36, 0x200);
    fixture_u32(optional + 56, 0x100000); fixture_u32(optional + 60, 0x200);
    fixture_u16(optional + 68, 3);
    fixture_u32(optional + directories - 4, 16);
    fixture_u32(optional + directories + 8, 0x1000);
    fixture_u32(optional + directories + 12, 60);
    section = optional + optional_size;
    for (i = 0; i < (large ? 3u : 2u); ++i, section += 40) {
        uint32_t raw_size = i == 2 ? 70000 * 12 : 0x400;
        memcpy(section, i == 0 ? ".idata" : i == 1 ? ".names" : ".pdata", 6);
        fixture_u32(section + 8, raw_size); fixture_u32(section + 12, (i + 1) * 0x1000);
        fixture_u32(section + 16, raw_size); fixture_u32(section + 20, 0x200 + i * 0x400);
        fixture_u32(section + 36, 0x40000040);
    }
    fixture_u32(bytes + 0x200, 0x1080); fixture_u32(bytes + 0x20c, 0x2010);
    fixture_u32(bytes + 0x210, 0x1080);
    fixture_u32(bytes + 0x214, 0x1080); fixture_u32(bytes + 0x220, 0x2040);
    fixture_u32(bytes + 0x224, 0x1080);
    memcpy(bytes + 0x610, "KERNEL32.dll", 13);
    memcpy(bytes + 0x640, "private#name.dll", 17);
    if (large) {
        fixture_u32(optional + directories + 24, 0x3000);
        fixture_u32(optional + directories + 28, 70000 * 12);
        for (i = 0; i < 70000; ++i) {
            fixture_u32(bytes + 0xa00 + i * 12, 0x100000 + i * 16);
            fixture_u32(bytes + 0xa04 + i * 12, 0x100008 + i * 16);
        }
    }
    return bytes;
}

/** Each rejection must use the established eligibility diagnostic and release partial names. */
static void check_image(const char *path, const unsigned char *bytes, size_t size,
                        int expected, const char *name) {
    PcContext c = {0};
    PcJson *imports;
    require_case(pc_write_file(path, (const char *)bytes, size), "write PE fixture");
    imports = pc_pe_imports(&c, path);
    if (expected < 0)
        require_case(!imports && c.error_code == 2154 && c.error, name);
    else {
        require_case(imports && !c.error && imports->count == (size_t)expected, name);
        if (expected == 2)
            require_case(!strcmp(imports->child->text, "KERNEL32.dll") &&
                         !strcmp(imports->child->next->text, "private#name.dll"), name);
    }
    pj_free(imports); pc_clear_error(&c);
}

/** Malformed offsets, section mappings, import lists and names fail without oversized reads. */
static void check_malformed(const char *path) {
    unsigned char *base, *bytes;
    size_t size;
    unsigned i;
    static const struct { size_t offset; uint32_t value; const char *name; } changes[] = {
        {0, 0, "DOS signature"}, {60, UINT32_MAX, "PE offset overflow"},
        {0x80, 0, "PE signature"}, {0x86, 97, "section bound"},
        {0x94, 80, "short optional header"}, {0x98, 0x107, "unsupported optional header"},
        {0x98 + 108, 17, "directory count outside optional header"},
        {0x98 + 60, 0x100, "section table outside headers"},
        {0x188 + 20, UINT32_MAX, "raw offset outside file"},
        {0x188 + 16, UINT32_MAX, "raw range outside file"},
        {0x1b0 + 12, 0x1100, "overlapping virtual sections"},
        {0x98 + 120, 0x5000, "unmapped import table"},
        {0x98 + 124, 19, "short descriptor table"},
        {0x98 + 124, 40, "missing descriptor terminator"},
        {0x98 + 120, UINT32_MAX - 10, "import RVA overflow"},
        {0x20c, 0, "partial descriptor is not a terminator"},
        {0x20c, 0x5000, "unmapped name RVA"},
        {0x20c, 0x2800, "virtual-only name RVA"},
        {0x610, 0, "empty DLL name"}
    };
    base = fixture_image(1, 0, &size);
    bytes = pc_alloc(size);
    for (i = 0; i < sizeof(changes) / sizeof(changes[0]); ++i) {
        memcpy(bytes, base, size);
        fixture_u32(bytes + changes[i].offset, changes[i].value);
        check_image(path, bytes, size, -1, changes[i].name);
    }
    for (i = 0; i < 5; ++i) {
        static const size_t lengths[] = {0, 63, 0x90, 0x180, 0x650};
        check_image(path, base, lengths[i], -1, "truncated image");
    }
    memcpy(bytes, base, size);
    memset(bytes + 0x610, 'x', size - 0x610);
    check_image(path, bytes, size, -1, "unterminated DLL name");
    memcpy(bytes, base, size);
    fixture_u32(bytes + 0x1b0 + 8, 0x1000);
    fixture_u32(bytes + 0x20c, 0x2800);
    check_image(path, bytes, size, -1, "virtual range without file-backed name");
    free(bytes); free(base);
}

/** Descriptor and name limits are independent of unrelated PE data size. */
static void check_limits(const char *path) {
    size_t size;
    unsigned char *bytes = fixture_image(1, 1, &size);
    unsigned i;
    check_image(path, bytes, size, 2, "large unrelated pdata");
    /* Move the import list into the large section; every entry names the same DLL. */
    fixture_u32(bytes + 0x98 + 120, 0x3000);
    fixture_u32(bytes + 0x98 + 124, 258 * 20);
    memset(bytes + 0xa00, 0, 258 * 20);
    for (i = 0; i < 256; ++i) fixture_u32(bytes + 0xa00 + i * 20 + 12, 0x2010);
    check_image(path, bytes, size, 256, "maximum import count");
    fixture_u32(bytes + 0xa00 + 256 * 20 + 12, 0x2010);
    check_image(path, bytes, size, -1, "excessive import count");
    fixture_u32(bytes + 0x98 + 120, 0x1000);
    fixture_u32(bytes + 0x98 + 124, 40);
    memset(bytes + 0x214, 0, 20);
    fixture_u32(bytes + 0x20c, 0x3000);
    memset(bytes + 0xa00, 'x', 4096); bytes[0xa00 + 4095] = 0;
    check_image(path, bytes, size, 1, "maximum name length");
    bytes[0xa00 + 4095] = 'x';
    check_image(path, bytes, size, -1, "excessive name length");
    free(bytes);
}

#if defined(_WIN32)
/** Exercise the actual DLL resolver and closure on this native test executable. */
static void check_windows_closure(const char *self) {
    PcContext c = {0};
    PcJson *paths = pj_new(PJ_OBJECT), *dependencies = pj_new(PJ_OBJECT);
    int ok;
    pc_add_component(paths, self);
    require_case(paths->count == 1, "native executable component");
    ok = pc_implementation_libraries(&c, paths, dependencies);
    if (!ok && c.error) fprintf(stderr, "%s\n", c.error);
    require_case(ok && !c.error && paths->count > 1, "native Windows DLL closure");
    pj_free(paths); pj_free(dependencies); pc_clear_error(&c);
}
#endif

/** Run the same private helper used on Windows, even when validating on another host. */
int main(int argc, char **argv) {
    char *directory, *path;
    unsigned char *bytes;
    size_t size;
    int plus;
    require_case(argc == 2, "expected owned fixture directory argument");
    directory = pc_path_call(argv[1], l1c_fs_canonical_existing_path);
    require_case(directory && pc_kind(directory, 1) == 2, "existing fixture directory");
    path = pc_join(directory, "imports.exe");
    for (plus = 0; plus <= 1; ++plus) {
        unsigned directories = plus ? 112 : 96;
        bytes = fixture_image(plus, 0, &size);
        check_image(path, bytes, size, 2, plus ? "PE32+ imports" : "PE32 imports");
        fixture_u32(bytes + 0x98 + directories + 8, 0);
        fixture_u32(bytes + 0x98 + directories + 12, 0);
        check_image(path, bytes, size, 0, "no normal imports");
        free(bytes);
    }
    check_malformed(path);
    check_limits(path);
    require_case(remove(path) == 0, "remove PE fixture");
#if defined(_WIN32)
    check_windows_closure(argv[0]);
#endif
    free(path); free(directory);
    puts("preparation PE import names, bounds and unrelated-table independence: PASS");
    return 0;
}
