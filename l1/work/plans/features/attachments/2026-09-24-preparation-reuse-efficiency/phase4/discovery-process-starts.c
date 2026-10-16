/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file discovery-process-starts.c External Linux loader observer, excluded from timing runs. */
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/** Record each dynamically loaded process without changing compiler arguments or job configuration. */
__attribute__((constructor)) static void record_start(void) {
    char command[8192];
    const char *label = getenv("DISCOVERY_PROCESS_LABEL");
    int descriptor = open("/proc/self/cmdline", O_RDONLY);
    ssize_t n = descriptor >= 0 ? read(descriptor, command, sizeof(command)) : -1;
    ssize_t i;
    if (descriptor >= 0) close(descriptor);
    if (n <= 0 || !label) return;
    for (i = 0; i < n; ++i) if (!command[i]) command[i] = ' ';
    (void)write(STDERR_FILENO, "process-start ", 14);
    (void)write(STDERR_FILENO, label, strlen(label));
    (void)write(STDERR_FILENO, " ", 1);
    (void)write(STDERR_FILENO, command, (size_t)n);
    (void)write(STDERR_FILENO, "\n", 1);
}
