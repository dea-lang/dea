/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */
/** @file path_arguments.h ASCII-only transport for UTF-8/filename bytes in C probes. */
#ifndef DEA_FS_TEST_PATH_ARGUMENTS_H
#define DEA_FS_TEST_PATH_ARGUMENTS_H

/** Decode one ASCII hexadecimal digit, returning -1 for invalid transport data. */
static int fixture_hex_digit(unsigned char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

/** Free one owned decoded argument vector. */
static void fixture_free_arguments(int argc, char **argv) {
    if (!argv) return;
    for (int i = 0; i < argc; ++i) free(argv[i]);
    free(argv);
}

/**
 * Copy arguments, decoding hex-prefixed path bytes without depending on the
 * Windows CRT's active code page. Every returned argument is owned by the probe.
 */
static char **fixture_path_arguments(int argc, char **argv) {
    char **out = (char **)calloc((size_t)argc + 1, sizeof(char *));
    if (!out) return NULL;
    for (int i = 0; i < argc; ++i) {
        size_t len = strlen(argv[i]);
        int encoded = len >= 4 && !strncmp(argv[i], "hex:", 4);
        if (encoded && (len - 4) % 2) { fixture_free_arguments(argc, out); return NULL; }
        size_t bytes = encoded ? (len - 4) / 2 : len;
        out[i] = (char *)malloc(bytes + 1);
        if (!out[i]) { fixture_free_arguments(argc, out); return NULL; }
        for (size_t j = 0; j < bytes; ++j) {
            if (encoded) {
                int high = fixture_hex_digit((unsigned char)argv[i][4 + j * 2]);
                int low = fixture_hex_digit((unsigned char)argv[i][5 + j * 2]);
                if (high < 0 || low < 0) { fixture_free_arguments(argc, out); return NULL; }
                out[i][j] = (char)(high * 16 + low);
            } else out[i][j] = argv[i][j];
        }
        out[i][bytes] = 0;
    }
    return out;
}
#endif
