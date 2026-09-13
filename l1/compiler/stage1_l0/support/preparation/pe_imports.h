/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file pe_imports.h Bounded normal PE import names without unrelated image tables. */
#ifndef L1_PREPARATION_PE_IMPORTS_H
#define L1_PREPARATION_PE_IMPORTS_H

typedef struct {
    uint32_t address, size, raw_size, offset;
} PcPeSection;
typedef struct {
    FILE *file;
    uint64_t size;
    uint32_t headers;
    unsigned count;
    PcPeSection sections[96];
} PcPeReader;

static uint32_t pc_pe_u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static unsigned pc_pe_u16(const unsigned char *p) { return (unsigned)p[0] | (unsigned)p[1] << 8; }

/** Read only an already checked file range, including on Windows with 32-bit long. */
static int pc_pe_read(PcPeReader *r, uint64_t offset, void *bytes, size_t size) {
    if (offset > r->size || size > r->size - offset) return 0;
#if defined(_WIN32)
    if (_fseeki64(r->file, (int64_t)offset, SEEK_SET) != 0) return 0;
#else
    if (fseeko(r->file, (off_t)offset, SEEK_SET) != 0) return 0;
#endif
    return fread(bytes, 1, size, r->file) == size && !ferror(r->file);
}

/** Map an RVA to its file-backed range; virtual-only data cannot hold import records. */
static int pc_pe_range(const PcPeReader *r, uint32_t address, uint64_t *offset, uint32_t *size) {
    unsigned i;
    if (address < r->headers) {
        *offset = address;
        *size = r->headers - address;
        return 1;
    }
    for (i = 0; i < r->count; ++i) {
        const PcPeSection *s = &r->sections[i];
        if (address >= s->address && (uint64_t)address - s->address < s->raw_size) {
            *offset = (uint64_t)s->offset + address - s->address;
            *size = s->raw_size - (address - s->address);
            return 1;
        }
    }
    return 0;
}

/** Return normal imported DLL names, preserving the previous objdump discovery boundary. */
static PcJson *pc_pe_imports(PcContext *c, const char *path) {
    PcPeReader r = {0};
    PcJson *names = pj_new(PJ_ARRAY);
    unsigned char dos[64], coff[24], optional[240], section[40], descriptor[20];
    unsigned i, j, optional_size, directories;
    uint32_t pe, import_address = 0, import_size = 0;
    uint64_t section_offset, offset;
    int64_t file_size;
    int ok = 0;
    r.file = fopen(path, "rb");
    if (!r.file) goto finish;
#if defined(_WIN32)
    if (_fseeki64(r.file, 0, SEEK_END) != 0) goto finish;
    file_size = _ftelli64(r.file);
#else
    if (fseeko(r.file, 0, SEEK_END) != 0) goto finish;
    file_size = ftello(r.file);
#endif
    if (file_size < 0) goto finish;
    r.size = (uint64_t)file_size;
    if (!pc_pe_read(&r, 0, dos, sizeof(dos)) || memcmp(dos, "MZ", 2)) goto finish;
    pe = pc_pe_u32(dos + 60);
    if (pe < sizeof(dos) || !pc_pe_read(&r, pe, coff, sizeof(coff)) || memcmp(coff, "PE\0\0", 4))
        goto finish;
    r.count = pc_pe_u16(coff + 6);
    optional_size = pc_pe_u16(coff + 20);
    if (!r.count || r.count > 96 || optional_size < 96 ||
        !pc_pe_read(&r, (uint64_t)pe + 24, optional,
                    optional_size < sizeof(optional) ? optional_size : sizeof(optional))) goto finish;
    if (pc_pe_u16(optional) == 0x10b) directories = 96;
    else if (pc_pe_u16(optional) == 0x20b && optional_size >= 112) directories = 112;
    else goto finish;
    if (pc_pe_u32(optional + directories - 4) > (optional_size - directories) / 8) goto finish;
    r.headers = pc_pe_u32(optional + 60);
    section_offset = (uint64_t)pe + 24 + optional_size;
    if (r.headers > r.size || section_offset + r.count * 40 > r.headers) goto finish;
    for (i = 0; i < r.count; ++i) {
        PcPeSection *s = &r.sections[i];
        if (!pc_pe_read(&r, section_offset + i * 40, section, sizeof(section))) goto finish;
        s->size = pc_pe_u32(section + 8);
        s->address = pc_pe_u32(section + 12);
        s->raw_size = pc_pe_u32(section + 16);
        s->offset = pc_pe_u32(section + 20);
        if (s->size < s->raw_size) s->size = s->raw_size;
        if ((uint64_t)s->address + s->size > (uint64_t)UINT32_MAX + 1 ||
            (s->size && s->address < r.headers) ||
            (s->raw_size && (s->offset < r.headers ||
                            (uint64_t)s->offset + s->raw_size > r.size))) goto finish;
        for (j = 0; j < i; ++j)
            if (s->size && r.sections[j].size &&
                (uint64_t)s->address < (uint64_t)r.sections[j].address + r.sections[j].size &&
                (uint64_t)r.sections[j].address < (uint64_t)s->address + s->size) goto finish;
    }
    if (pc_pe_u32(optional + directories - 4) > 1) {
        import_address = pc_pe_u32(optional + directories + 8);
        import_size = pc_pe_u32(optional + directories + 12);
    }
    if (!import_address && !import_size) { ok = 1; goto finish; }
    if (!import_address || import_size < sizeof(descriptor) ||
        (uint64_t)import_address + import_size > (uint64_t)UINT32_MAX + 1) goto finish;
    /* Each image admits at most 256 names of 4095 bytes, independently of its
       code, symbol, resource or unwind-table size. The closure keeps its own cap. */
    for (i = 0; i <= 256 && (uint64_t)i * 20 + 20 <= import_size; ++i) {
        uint32_t available, name_address;
        unsigned char name[4096];
        size_t length;
        if (!pc_pe_range(&r, import_address + i * 20, &offset, &available) || available < 20 ||
            !pc_pe_read(&r, offset, descriptor, sizeof(descriptor))) goto finish;
        for (j = 0; j < sizeof(descriptor) && !descriptor[j]; ++j) {}
        if (j == sizeof(descriptor)) { ok = 1; goto finish; }
        if (i == 256) goto finish;
        name_address = pc_pe_u32(descriptor + 12);
        if (!name_address || !pc_pe_range(&r, name_address, &offset, &available)) goto finish;
        length = available < sizeof(name) ? available : sizeof(name);
        if (!pc_pe_read(&r, offset, name, length) || !name[0] || !memchr(name, 0, length)) goto finish;
        pj_add(names, NULL, pj_string((const char *)name));
    }
finish:
    if (r.file && fclose(r.file) != 0) ok = 0;
    if (!ok) {
        pj_free(names);
        pc_fail(c, 2154, "cannot read bounded compiler implementation PE imports", path);
        return NULL;
    }
    return names;
}
#endif
