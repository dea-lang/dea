/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */
/** @file failure_probe.c Saved errno, terminal cursor errors, and partial copy. */
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#include "dea_rt.h"
#include <dirent.h>
#include <unistd.h>
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "failure line %d: %s\n", __LINE__, #x); return 1; } } while (0)
static int fail_next, fail_close, read_mode, write_mode, calls, close_file_error;

/** Simulate cross-device renaming: no copy or unlink fallback is allowed. */
int fs_probe_rename(const char *source, const char *destination) {
    (void)source; (void)destination;
    errno = EXDEV; return -1;
}
/** Close the real descriptor, then inject a deferred storage error. */
int fs_probe_close(int fd) {
    int result = close(fd);
    if (close_file_error) { errno = EIO; return -1; }
    return result;
}
/** Inject a read-directory error, or a clean end with stale errno cleared by runtime. */
struct dirent *fs_probe_readdir(DIR *dir) {
    if (fail_next) { errno = EACCES; return NULL; }
    return readdir(dir);
}
/** Consume the actual cursor before simulating its close error. */
int fs_probe_closedir(DIR *dir) {
    int result = closedir(dir);
    if (fail_close) { errno = EIO; return -1; }
    return result;
}
/** Inject interruption without implicit retry. */
ssize_t fs_probe_read(int fd, void *buffer, size_t size) {
    ++calls;
    if (read_mode) { errno = EINTR; return -1; }
    return read(fd, buffer, size);
}
/** Simulate positive partial writes, zero progress, or a captured failure. */
ssize_t fs_probe_write(int fd, const void *buffer, size_t size) {
    if (write_mode == 1) { errno = ENOSPC; return -1; }
    if (write_mode == 2) return 0;
    return write(fd, buffer, size > 1 ? 1 : size);
}
/** Borrow one terminated fixture path. */
static dea_string text(const char *s) { return (dea_string)DEA_STRING_CONST((char *)s, (dea_int)strlen(s)); }
/** Run direct cursor failure and copy partial-progress scenarios. */
int main(int argc, char **argv) {
    REQUIRE(argc == 7);
    struct __deaM3sys2fsS9RtDirOpen opened = rt_dir_open(text(argv[1]));
    REQUIRE(opened.ok);
    fail_next = 1;
    struct __deaM3sys2fsS9RtDirNext next = rt_dir_next(opened.handle);
    REQUIRE(next.state == 2 && next.error.native_code == EACCES);
    fail_next = 0; errno = ENOENT;
    next = rt_dir_next(opened.handle);
    REQUIRE(next.state == 2 && next.error.native_code == EACCES);
    fail_close = 1;
    struct __deaM3sys2fsS10RtFsStatus closed = rt_dir_close(opened.handle);
    REQUIRE(!closed.ok && closed.error.native_code == EIO);
    /* Recursive traversal keeps its first error even if cleanup also fails. */
    fail_next = 1;
    struct __deaM3sys2fsS10RtFsStatus removed = rt_fs_remove_dir(text(argv[1]), 1);
    REQUIRE(!removed.ok && removed.error.native_code == EACCES);
    REQUIRE(rt_fs_metadata(text(argv[1]), 1).ok);
    fail_next = fail_close = 0;
    struct __deaM3sys2fsS10RtFsStatus renamed = rt_fs_rename(text(argv[2]), text(argv[3]), 0);
    REQUIRE(!renamed.ok && renamed.error.native_code == EXDEV);
    REQUIRE(rt_fs_metadata(text(argv[2]), 1).ok && !rt_fs_metadata(text(argv[3]), 1).ok);
    fail_close = 0;
    REQUIRE(rt_fs_copy_file(text(argv[2]), text(argv[3])).ok);
    read_mode = 1; calls = 0;
    struct __deaM3sys2fsS10RtFsStatus result = rt_fs_copy_file(text(argv[2]), text(argv[4]));
    REQUIRE(!result.ok && result.error.native_code == EINTR && calls == 1);
    REQUIRE(result.error.kind == DEA_OS_ERROR_INTERRUPTED);
    read_mode = 0; write_mode = 1;
    result = rt_fs_copy_file(text(argv[2]), text(argv[5]));
    REQUIRE(!result.ok && result.error.native_code == ENOSPC);
    REQUIRE(result.error.kind == DEA_OS_ERROR_NO_SPACE);
    REQUIRE(rt_fs_remove_file(text(argv[5])).ok);
    write_mode = 2;
    result = rt_fs_copy_file(text(argv[2]), text(argv[5]));
    REQUIRE(!result.ok && result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.kind == DEA_OS_ERROR_IO_ERROR);
    REQUIRE(rt_fs_remove_file(text(argv[5])).ok);
    write_mode = 0; close_file_error = 1;
    result = rt_fs_copy_file(text(argv[2]), text(argv[5]));
    REQUIRE(!result.ok && result.error.native_code == EIO);
    close_file_error = 0;
    result = rt_fs_remove_dir(text(argv[6]), 1);
    REQUIRE(!result.ok && result.error.kind == DEA_OS_ERROR_RESOURCE_EXHAUSTED);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME);
    return 0;
}
