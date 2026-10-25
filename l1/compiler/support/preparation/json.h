/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file json.h Bounded compiler-private JSON and canonical identity encoding.
 */
#ifndef L1_PREPARATION_JSON_H
#define L1_PREPARATION_JSON_H

#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/**
 * Fail closed on allocation failure, including during diagnostic construction.
 *
 * @param size Requested storage size in bytes.
 * @return Owned storage released with free; never NULL.
 */
static void *pc_alloc(size_t size) {
    void *p = calloc(size ? size : 1, 1);
    if (!p) {
        fputs("error: [L1C-2151] preparation support ran out of memory\n", stderr);
        exit(1);
    }
    return p;
}

/**
 * Copy a byte span into a newly allocated NUL-terminated string.
 *
 * @param s Readable source span of n bytes.
 * @param n Number of bytes to process.
 * @return Owned string released with free.
 */
static char *pc_slice(const char *s, size_t n) {
    char *p = pc_alloc(n + 1);
    memcpy(p, s, n);
    return p;
}

/**
 * Duplicate a NUL-terminated string into preparation-owned storage.
 *
 * @param s Borrowed NUL-terminated string to duplicate.
 * @return Owned string released with free.
 */
static char *pc_string(const char *s) { return pc_slice(s, strlen(s)); }

typedef struct {
    char *s;
    size_t n, cap;
} PcBuffer;

/**
 * Append bytes to a growable NUL-terminated preparation buffer.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param s Borrowed source span of n readable bytes.
 * @param n Number of bytes to process.
 */
static void pc_bytes(PcBuffer *b, const char *s, size_t n) {
    if (n > SIZE_MAX - b->n - 1) {
        fputs("preparation input too large\n", stderr);
        exit(1);
    }
    if (b->n + n + 1 > b->cap) {
        size_t cap = (b->n + n + 1) * 2;
        char *p = pc_alloc(cap);
        if (b->n)
            memcpy(p, b->s, b->n);
        free(b->s);
        b->s = p;
        b->cap = cap;
    }
    memcpy(b->s + b->n, s, n);
    b->n += n;
    b->s[b->n] = 0;
}

/**
 * Append a NUL-terminated string to a preparation buffer.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param s Borrowed NUL-terminated text to append.
 */
static void pc_text(PcBuffer *b, const char *s) { pc_bytes(b, s, strlen(s)); }

/**
 * Append one byte to a preparation buffer.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param c Byte value to append.
 */
static void pc_char(PcBuffer *b, char c) { pc_bytes(b, &c, 1); }

/**
 * Expose a buffer allocation or allocate an owned empty string.
 *
 * @param b Buffer whose allocation is transferred without resetting its fields; the caller releases it
 *     once.
 * @return Owned NUL-terminated storage; the buffer must not be freed separately.
 */
static char *pc_take(PcBuffer *b) { return b->s ? b->s : pc_string(""); }

enum { PJ_NULL, PJ_STRING, PJ_NUMBER, PJ_ARRAY, PJ_OBJECT, PJ_BOOL, PJ_RAW_NUMBER };
typedef struct PcJson {
    int type;
    char *key, *text;
    int64_t number;
    struct PcJson *child, *last, *next;
    struct PcJson *collision, **index;
    size_t count, index_size;
    uint32_t key_hash;
} PcJson;

/**
 * Allocate an empty JSON node with the requested type.
 *
 * @param type JSON node type tag.
 * @return Owned node released recursively with pj_free.
 */
static PcJson *pj_new(int type) {
    PcJson *j = pc_alloc(sizeof(*j));
    j->type = type;
    return j;
}

/**
 * Create a JSON string node with its own copy of the text.
 *
 * @param s Borrowed NUL-terminated string copied into the new node.
 * @return Owned JSON node released with pj_free.
 */
static PcJson *pj_string(const char *s) {
    PcJson *j = pj_new(PJ_STRING);
    j->text = pc_string(s);
    return j;
}

/**
 * Create a JSON node containing an exact signed integer.
 *
 * @param n Exact signed integer payload stored in the new node.
 * @return Owned JSON node released with pj_free.
 */
static PcJson *pj_number(int64_t n) {
    PcJson *j = pj_new(PJ_NUMBER);
    j->number = n;
    return j;
}

/**
 * Compute the FNV-1a bucket hash of a JSON object key.
 *
 * @param key Borrowed NUL-terminated object or identity key.
 * @return 32-bit key hash.
 */
static uint32_t pj_key_hash(const char *key) {
    uint32_t hash = 2166136261u;
    for (; *key; ++key)
        hash = (hash ^ (unsigned char)*key) * 16777619u;
    return hash;
}

/**
 * Find an object member by its exact key bytes.
 *
 * @param j Borrowed JSON node.
 * @param key Borrowed NUL-terminated object or identity key.
 * @return Borrowed child node, or NULL for an absent key or non-object.
 */
static PcJson *pj_get(const PcJson *j, const char *key) {
    PcJson *c;
    if (!j || j->type != PJ_OBJECT)
        return NULL;
    if (j->index) {
        uint32_t hash = pj_key_hash(key);
        for (c = j->index[hash & (j->index_size - 1)]; c; c = c->collision)
            if (c->key_hash == hash && !strcmp(c->key, key))
                return c;
        return NULL;
    }
    for (c = j->child; c; c = c->next)
        if (!strcmp(c->key, key))
            return c;
    return NULL;
}

/**
 * Read the borrowed string bytes of a JSON string node.
 *
 * @param j Borrowed JSON node.
 * @return Borrowed text, or NULL for a non-string or absent node.
 */
static const char *pj_str(const PcJson *j) { return j && j->type == PJ_STRING ? j->text : NULL; }

/**
 * Read a borrowed string-valued object member.
 *
 * @param j Borrowed JSON node.
 * @param key Borrowed NUL-terminated object or identity key.
 * @return Borrowed member text, or NULL when missing or not a string.
 */
static const char *pj_field(const PcJson *j, const char *key) { return pj_str(pj_get(j, key)); }

/**
 * Test whether a JSON node contains the specified exact integer.
 *
 * @param j Borrowed JSON node.
 * @param n Expected exact signed integer value.
 * @return Nonzero only for a matching integer node.
 */
static int pj_is_number(const PcJson *j, int64_t n) {
    return j && j->type == PJ_NUMBER && j->number == n;
}

/**
 * Read the number of children in a JSON container.
 *
 * @param j Borrowed JSON node.
 * @return Child count, or zero for a null container.
 */
static size_t pj_count(const PcJson *j) { return j ? j->count : 0; }

/**
 * Append an owned JSON child and update object lookup indexing.
 *
 * @param j Mutable destination object or array taking ownership of appended nodes.
 * @param key Borrowed NUL-terminated object or identity key.
 * @param value Owned child node transferred to the destination container.
 */
static void pj_add(PcJson *j, const char *key, PcJson *value) {
    if (key) {
        value->key = pc_string(key);
        value->key_hash = pj_key_hash(key);
    }
    if (j->last)
        j->last->next = value;
    else
        j->child = value;
    j->last = value;
    ++j->count;

    /* Large path inventories need indexed lookup on the warm path. Small
       metadata records retain allocation-free linear lookup. */
    if (j->type == PJ_OBJECT && j->count >= 32) {
        if (!j->index || j->count * 2 > j->index_size) {
            PcJson *child;
            size_t size = j->index_size ? j->index_size * 2 : 64;
            free(j->index);
            j->index = pc_alloc(size * sizeof(*j->index));
            j->index_size = size;
            for (child = j->child; child; child = child->next) {
                size_t bucket = child->key_hash & (size - 1);
                child->collision = j->index[bucket];
                j->index[bucket] = child;
            }
        } else {
            size_t bucket = value->key_hash & (j->index_size - 1);
            value->collision = j->index[bucket];
            j->index[bucket] = value;
        }
    }
}

/**
 * Append a named JSON string field, copying its text.
 *
 * @param j Mutable destination object or array taking ownership of appended nodes.
 * @param key Borrowed NUL-terminated object or identity key.
 * @param s Borrowed NUL-terminated string copied into the new field.
 */
static void pj_set_string(PcJson *j, const char *key, const char *s) {
    pj_add(j, key, pj_string(s));
}

/**
 * Append a named exact-integer JSON field.
 *
 * @param j Mutable destination object or array taking ownership of appended nodes.
 * @param key Borrowed NUL-terminated object or identity key.
 * @param n Exact signed integer payload assigned to the new field.
 */
static void pj_set_number(PcJson *j, const char *key, int64_t n) { pj_add(j, key, pj_number(n)); }

/**
 * Release a JSON node chain, its owned strings, and all descendants.
 *
 * @param j Owned node to release, or NULL.
 */
static void pj_free(PcJson *j) {
    while (j) {
        PcJson *next = j->next;
        pj_free(j->child);
        free(j->key);
        free(j->text);
        free(j->index);
        free(j);
        j = next;
    }
}

/**
 * Append a JSON-escaped quoted string to a buffer.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param s Borrowed NUL-terminated string to escape.
 */
static void pj_quote(PcBuffer *b, const char *s) {
    static const char hex[] = "0123456789abcdef";
    const unsigned char *p = (const unsigned char *)s;
    pc_char(b, '"');
    for (; *p; ++p) {
        if (*p == '"' || *p == '\\') {
            pc_char(b, '\\');
            pc_char(b, (char)*p);
        } else if (*p < 32) {
            pc_text(b, "\\u00");
            pc_char(b, hex[*p >> 4]);
            pc_char(b, hex[*p & 15]);
        } else {
            const unsigned char *start = p;
            while (p[1] >= 32 && p[1] != '"' && p[1] != '\\')
                ++p;
            pc_bytes(b, (const char *)start, (size_t)(p - start + 1));
        }
    }
    pc_char(b, '"');
}

/**
 * Compare JSON child pointers by their object key bytes.
 *
 * @param a Pointer to the first JSON object-member pointer.
 * @param b Pointer to the second JSON object-member pointer.
 * @return Negative, zero, or positive strcmp ordering.
 */
static int pj_key_compare(const void *a, const void *b) {
    return strcmp((*(const PcJson *const *)a)->key, (*(const PcJson *const *)b)->key);
}

/**
 * Canonical encoding: UTF-8, sorted object keys, integral decimal numbers, no whitespace.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param j Borrowed JSON value to serialize.
 */
static void pj_write(PcBuffer *b, const PcJson *j) {
    const PcJson *c;
    char number[40];
    size_t n, i;
    const PcJson **ordered;
    switch (j->type) {
    case PJ_STRING:
        pj_quote(b, j->text);
        break;
    case PJ_NUMBER:
        snprintf(number, sizeof(number), "%" PRId64, j->number);
        pc_text(b, number);
        break;
    case PJ_RAW_NUMBER:
        pc_text(b, j->text);
        break;
    case PJ_BOOL:
        pc_text(b, j->number ? "true" : "false");
        break;
    case PJ_NULL:
        pc_text(b, "null");
        break;
    case PJ_ARRAY:
        pc_char(b, '[');
        for (c = j->child; c; c = c->next) {
            if (c != j->child)
                pc_char(b, ',');
            pj_write(b, c);
        }
        pc_char(b, ']');
        break;
    default:
        n = pj_count(j);
        ordered = pc_alloc(n * sizeof(*ordered));
        i = 0;
        for (c = j->child; c; c = c->next)
            ordered[i++] = c;
        qsort(ordered, n, sizeof(*ordered), pj_key_compare);
        pc_char(b, '{');
        for (i = 0; i < n; ++i) {
            if (i)
                pc_char(b, ',');
            pj_quote(b, ordered[i]->key);
            pc_char(b, ':');
            pj_write(b, ordered[i]);
        }
        pc_char(b, '}');
        free(ordered);
        break;
    }
}

/**
 * Serialize a JSON tree into a newly owned canonical string.
 *
 * @param j Borrowed JSON node.
 * @return Owned NUL-terminated JSON released with free.
 */
static char *pj_encode(const PcJson *j) {
    PcBuffer b = {0};
    pj_write(&b, j);
    return pc_take(&b);
}

typedef struct {
    const char *s;
    size_t i, n, nodes;
    int failed, general_numbers;
} PjParser;

/**
 * Advance a JSON parser past supported ASCII whitespace.
 *
 * @param p Mutable bounded JSON parser state.
 */
static void pj_space(PjParser *p) {
    while (p->i < p->n && strchr(" \t\r\n", p->s[p->i]))
        ++p->i;
}

/**
 * Decode an ASCII hexadecimal digit for JSON escapes.
 *
 * @param c ASCII character to decode as a hexadecimal digit.
 * @return Digit value from zero to fifteen, or -1 for invalid input.
 */
static int pj_hex(char c) {
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

/**
 * Consume four hexadecimal digits from a JSON Unicode escape.
 *
 * @param p Mutable bounded JSON parser state.
 * @return Decoded UTF-16 code unit; malformed input sets the parser error flag.
 */
static unsigned pj_u16(PjParser *p) {
    unsigned n = 0;
    int i, h;
    for (i = 0; i < 4; ++i) {
        if (p->i >= p->n || (h = pj_hex(p->s[p->i++])) < 0) {
            p->failed = 1;
            return 0;
        }
        n = n * 16 + (unsigned)h;
    }
    return n;
}

/**
 * Append a Unicode scalar value in UTF-8 encoding.
 *
 * @param b Mutable growable byte buffer owned by the caller.
 * @param c Unicode scalar value to encode.
 */
static void pj_utf8(PcBuffer *b, unsigned c) {
    if (c < 128)
        pc_char(b, (char)c);
    else if (c < 2048) {
        pc_char(b, (char)(192 | (c >> 6)));
        pc_char(b, (char)(128 | (c & 63)));
    } else if (c < 65536) {
        pc_char(b, (char)(224 | (c >> 12)));
        pc_char(b, (char)(128 | ((c >> 6) & 63)));
        pc_char(b, (char)(128 | (c & 63)));
    } else {
        pc_char(b, (char)(240 | (c >> 18)));
        pc_char(b, (char)(128 | ((c >> 12) & 63)));
        pc_char(b, (char)(128 | ((c >> 6) & 63)));
        pc_char(b, (char)(128 | (c & 63)));
    }
}

/**
 * Parse a quoted JSON string with Unicode and escape validation.
 *
 * @param p Mutable bounded JSON parser state.
 * @return Owned decoded string, or NULL after marking invalid input.
 */
static char *pj_parse_string(PjParser *p) {
    PcBuffer b = {0};
    unsigned c, low;
    int closed = 0;
    if (p->i >= p->n || p->s[p->i++] != '"') {
        p->failed = 1;
        return NULL;
    }
    while (p->i < p->n && !p->failed) {
        c = (unsigned char)p->s[p->i++];
        if (c == '"') {
            closed = 1;
            break;
        }
        if (c < 32) {
            p->failed = 1;
            break;
        }
        if (c == '\\') {
            if (p->i == p->n)
                break;
            c = (unsigned char)p->s[p->i++];
            switch (c) {
            case '"':
            case '\\':
            case '/':
                pc_char(&b, (char)c);
                break;
            case 'b':
                pc_char(&b, '\b');
                break;
            case 'f':
                pc_char(&b, '\f');
                break;
            case 'n':
                pc_char(&b, '\n');
                break;
            case 'r':
                pc_char(&b, '\r');
                break;
            case 't':
                pc_char(&b, '\t');
                break;
            case 'u':
                c = pj_u16(p);
                if (c >= 0xd800 && c <= 0xdbff) {
                    if (p->n - p->i < 6 || p->s[p->i] != '\\' || p->s[p->i + 1] != 'u') {
                        p->failed = 1;
                        break;
                    }
                    p->i += 2;
                    low = pj_u16(p);
                    if (low < 0xdc00 || low > 0xdfff) {
                        p->failed = 1;
                        break;
                    }
                    c = 0x10000 + ((c - 0xd800) << 10) + low - 0xdc00;
                } else if (c >= 0xdc00 && c <= 0xdfff) {
                    p->failed = 1;
                    break;
                }
                if (!c) {
                    p->failed = 1;
                    break;
                }
                pj_utf8(&b, c);
                break;
            default:
                p->failed = 1;
                break;
            }
        } else {
            size_t start = p->i - 1;
            while (p->i < p->n && (unsigned char)p->s[p->i] >= 32 && p->s[p->i] != '"' &&
                   p->s[p->i] != '\\')
                ++p->i;
            pc_bytes(&b, p->s + start, p->i - start);
        }
    }
    if (!closed || p->failed) {
        p->failed = 1;
        free(b.s);
        return NULL;
    }
    return pc_take(&b);
}

/**
 * Parse a bounded JSON value and its nested children.
 *
 * @param p Mutable bounded JSON parser state.
 * @param depth Current nesting depth checked against the operation limit.
 * @return Owned node, or NULL for invalid syntax, excessive nesting, or an invalid value.
 */
static PcJson *pj_parse_value(PjParser *p, int depth) {
    PcJson *j = NULL, *child;
    char c, close, *key;
    size_t start;
    char *num, *end;
    int64_t value;
    if (depth > 64 || ++p->nodes > 100000) {
        p->failed = 1;
        return NULL;
    }
    pj_space(p);
    if (p->i == p->n) {
        p->failed = 1;
        return NULL;
    }
    c = p->s[p->i];
    if (c == '"') {
        j = pj_new(PJ_STRING);
        j->text = pj_parse_string(p);
    } else if (c == '{' || c == '[') {
        ++p->i;
        j = pj_new(c == '{' ? PJ_OBJECT : PJ_ARRAY);
        close = c == '{' ? '}' : ']';
        pj_space(p);
        if (p->i < p->n && p->s[p->i] == close) {
            ++p->i;
            return j;
        }
        while (!p->failed) {
            key = NULL;
            if (c == '{') {
                pj_space(p);
                key = pj_parse_string(p);
                pj_space(p);
                if (!key || pj_get(j, key) || p->i >= p->n || p->s[p->i++] != ':') {
                    free(key);
                    p->failed = 1;
                    break;
                }
            }
            child = pj_parse_value(p, depth + 1);
            if (!child) {
                free(key);
                break;
            }
            pj_add(j, key, child);
            free(key);
            pj_space(p);
            if (p->i < p->n && p->s[p->i] == close) {
                ++p->i;
                return j;
            }
            if (p->i >= p->n || p->s[p->i++] != ',') {
                p->failed = 1;
                break;
            }
        }
    } else if (c == '-' || (c >= '0' && c <= '9')) {
        start = p->i;
        if (c == '-')
            ++p->i;
        if (p->i == p->n || p->s[p->i] < '0' || p->s[p->i] > '9')
            p->failed = 1;
        else if (p->s[p->i] == '0')
            ++p->i;
        else
            while (p->i < p->n && p->s[p->i] >= '0' && p->s[p->i] <= '9')
                ++p->i;
        if (p->general_numbers) {
            if (p->i < p->n && p->s[p->i] == '.') {
                size_t digits = ++p->i;
                while (p->i < p->n && p->s[p->i] >= '0' && p->s[p->i] <= '9') ++p->i;
                if (digits == p->i) p->failed = 1;
            }
            if (p->i < p->n && (p->s[p->i] == 'e' || p->s[p->i] == 'E')) {
                size_t digits;
                ++p->i;
                if (p->i < p->n && (p->s[p->i] == '+' || p->s[p->i] == '-')) ++p->i;
                digits = p->i;
                while (p->i < p->n && p->s[p->i] >= '0' && p->s[p->i] <= '9') ++p->i;
                if (digits == p->i) p->failed = 1;
            }
        }
        num = pc_slice(p->s + start, p->i - start);
        errno = 0;
        value = strtoll(num, &end, 10);
        if (!errno && !*end) {
            j = pj_number(value);
            free(num);
        } else if (p->general_numbers) {

            /* Preserve non-integral and large values in opaque provenance. Schema
               integers still require PJ_NUMBER, so 1.0 never means schema 1. */
            if (strpbrk(num, ".eE") && !isfinite(strtod(num, NULL))) p->failed = 1;
            j = pj_new(PJ_RAW_NUMBER);
            j->text = num;
        } else {
            free(num);
            p->failed = 1;
        }
    } else if (p->n - p->i >= 4 && !memcmp(p->s + p->i, "null", 4)) {
        p->i += 4;
        j = pj_new(PJ_NULL);
    } else if (p->n - p->i >= 4 && !memcmp(p->s + p->i, "true", 4)) {
        p->i += 4;
        j = pj_new(PJ_BOOL);
        j->number = 1;
    } else if (p->n - p->i >= 5 && !memcmp(p->s + p->i, "false", 5)) {
        p->i += 5;
        j = pj_new(PJ_BOOL);
    } else
        p->failed = 1;
    if (p->failed) {
        pj_free(j);
        return NULL;
    }
    return j;
}

/**
 * Reject invalid raw UTF-8 as well as invalid JSON escape sequences.
 *
 * @param text Borrowed text to parse or caller-owned buffer receiving constructed text.
 * @param n Number of bytes to process.
 * @return Nonzero only for a complete valid UTF-8 byte span.
 */
static int pj_valid_utf8(const char *text, size_t n) {
    const unsigned char *s = (const unsigned char *)text;
    size_t i = 0;
    while (i < n) {
        unsigned c = s[i++], value, minimum;
        int more;
        if (c < 128)
            continue;
        if (c >= 194 && c <= 223) {
            more = 1;
            value = c & 31;
            minimum = 128;
        } else if (c >= 224 && c <= 239) {
            more = 2;
            value = c & 15;
            minimum = 2048;
        } else if (c >= 240 && c <= 244) {
            more = 3;
            value = c & 7;
            minimum = 65536;
        } else
            return 0;
        while (more--) {
            if (i == n || (s[i] & 192) != 128)
                return 0;
            value = (value << 6) | (s[i++] & 63);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff))
            return 0;
    }
    return 1;
}

/**
 * Parse one complete JSON value using the selected number policy.
 *
 * @param s Borrowed readable JSON span of n bytes; no terminator is required.
 * @param n Number of bytes to process.
 * @param general_numbers Nonzero to accept general JSON numbers in addition to exact integers.
 * @return Owned JSON tree, or NULL for malformed, trailing, or unsupported input.
 */
static PcJson *pj_parse_mode(const char *s, size_t n, int general_numbers) {
    PjParser p = {s, 0, n, 0, 0, general_numbers};
    PcJson *j;
    if (n > 16 * 1024 * 1024 || memchr(s, 0, n) || !pj_valid_utf8(s, n))
        return NULL;
    j = pj_parse_value(&p, 0);
    pj_space(&p);
    if (p.failed || p.i != n) {
        pj_free(j);
        return NULL;
    }
    return j;
}

/**
 * Preparation identities retain their integral-only canonical JSON contract.
 *
 * @param s Borrowed readable JSON span of n bytes; no terminator is required.
 * @param n Number of bytes to process.
 * @return Owned JSON tree, or NULL for malformed or unsupported input.
 */
static PcJson *pj_parse(const char *s, size_t n) { return pj_parse_mode(s, n, 0); }

/**
 * Deep-copy a JSON tree and all its owned strings.
 *
 * @param j Borrowed JSON node.
 * @return Independent owned tree, or NULL for a null input.
 */
static PcJson *pj_clone(const PcJson *j) {
    PcJson *copy;
    const PcJson *child;
    if (!j)
        return NULL;
    copy = pj_new(j->type);
    copy->number = j->number;
    if (j->text)
        copy->text = pc_string(j->text);
    for (child = j->child; child; child = child->next)
        pj_add(copy, child->key, pj_clone(child));
    return copy;
}

/**
 * Compare JSON values recursively without relying on object member order.
 *
 * @param a First input operand.
 * @param b Second input operand.
 * @return Nonzero for equal values, including two null pointers.
 */
static int pj_equal(const PcJson *a, const PcJson *b) {
    const PcJson *left, *right;
    if (!a || !b)
        return a == b;
    if (a->type != b->type || a->number != b->number)
        return 0;
    if (a->type == PJ_STRING || a->type == PJ_RAW_NUMBER)
        return !strcmp(a->text, b->text);
    if (pj_count(a) != pj_count(b))
        return 0;
    for (left = a->child, right = b->child; left; left = left->next) {
        if (!pj_equal(left, a->type == PJ_OBJECT ? pj_get(b, left->key) : right))
            return 0;
        if (right)
            right = right->next;
    }
    return 1;
}
#endif
