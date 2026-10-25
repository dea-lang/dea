/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file directory_failures.c
 * Native failures for a generated L1 materialization consumer.
 */
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#include <dirent.h>
#include <errno.h>
#include <string.h>
static int mode, named, closes;

/**
 * Reset independent read/close fault scenarios.
 *
 * @param value Fault scenario selected for subsequent native calls.
 */
void fs_dir_probe_config(int value) { mode = value; named = closes = 0; }

/**
 * Return the expected saved native code.
 * @return The native error code expected for the selected scenario.
 */
int fs_dir_probe_error(void) { return mode == 2 ? EIO : EACCES; }

/**
 * Expose native close consumption, independent of wrapper aliases.
 * @return Number of native cursors consumed since the last reset.
 */
int fs_dir_probe_closes(void) { return closes; }

/**
 * Fail after a named entry, or preserve an unknown hint without stat fallback.
 *
 * @param dir Live native cursor to advance.
 * @return The next entry, or NULL on the selected failure or native end.
 */
struct dirent *fs_dir_probe_readdir(DIR *dir) {
    if ((mode == 1 || mode == 3) && named) { errno = EACCES; return NULL; }
    struct dirent *entry = readdir(dir);
    if (entry && strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) {
        ++named;
#if defined(_DIRENT_HAVE_D_TYPE) || defined(__APPLE__)
        if (mode == 4) entry->d_type = DT_UNKNOWN;
#endif
    }
    return entry;
}

/**
 * Always consume the real cursor before reporting a simulated close failure.
 *
 * @param dir Live native cursor consumed by this call.
 * @return The native close result, or -1 with EIO for an injected failure.
 */
int fs_dir_probe_closedir(DIR *dir) {
    int result = closedir(dir);
    ++closes;
    if (mode == 2 || mode == 3) { errno = EIO; return -1; }
    return result;
}
