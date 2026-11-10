/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file native_probe.c
 * Wide offsets, cursor independence, and non-seekable native file boundaries.
 */
#ifndef _WIN32
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#endif
#include "dea_rt.h"
#ifdef _WIN32
#include <windows.h>
#endif
#include "../filesystem_runtime/path_arguments.h"

#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "file native line %d: %s\n", __LINE__, #x); return 1; } } while (0)
typedef struct __deaM3sys2fsS10RtFileOpen Open;
typedef struct __deaM3sys2fsS12RtFileOffset Offset;
typedef struct __deaM3sys2osS10RtIoResult Io;

#ifdef _WIN32
static unsigned sequential_reads, positional_reads;

/**
 * Check inheritance on the actual Windows endpoint before delegating a read.
 *
 * @param handle Native handle chosen by the file runtime.
 * @param buffer Destination passed unchanged to ReadFile.
 * @param count Maximum byte count passed unchanged to ReadFile.
 * @param transferred Immediate byte-count destination, or NULL for overlapped I/O.
 * @param overlap Positional operation state, or NULL for a sequential read.
 * @return Native ReadFile result; inheritance violations terminate the probe.
 */
BOOL file_probe_read_file(HANDLE handle, LPVOID buffer, DWORD count,
                          LPDWORD transferred, LPOVERLAPPED overlap) {
    DWORD flags;
    if (!GetHandleInformation(handle, &flags) || (flags & HANDLE_FLAG_INHERIT)) {
        fputs("file native: readable handle must disable inheritance\n", stderr);
        exit(1);
    }
    if (overlap == NULL) ++sequential_reads;
    else ++positional_reads;
    return ReadFile(handle, buffer, count, transferred, overlap);
}
#endif

/**
 * Borrow terminated fixture path bytes for a runtime operation.
 *
 * @param value NUL-terminated filename bytes.
 * @return A non-owning string valid while the source bytes remain live.
 */
static dea_string text(const char *value) {
    return (dea_string)DEA_STRING_CONST((char *)value, (dea_int)strlen(value));
}

/**
 * Validate wide file positions independently of int-sized transfer lengths.
 *
 * @param path Existing empty file made sparse by the host fixture where required.
 * @return Zero on success, otherwise one after reporting the violated assertion.
 */
static int wide_offsets(dea_string path) {
    const dea_long wide = INT64_C(4294967313);
    Open opened = rt_file_open(path, 2, 0, 0);
    REQUIRE(opened.ok && opened.handle);
    unsigned char source[3] = { 0, 255, 65 }, destination[4] = { 7, 7, 7, 7 };
    Offset position = rt_file_seek(opened.handle, wide, 0);
    REQUIRE(position.ok && position.value == wide);
    Io result = rt_file_write(opened.handle, source, 3);
    REQUIRE(result.state == DEA_IO_OK && result.count == 3);
    REQUIRE(rt_file_size(opened.handle).value == wide + 3);
    REQUIRE(rt_file_position(opened.handle).value == wide + 3);
    position = rt_file_seek(opened.handle, wide, 0);
    REQUIRE(position.ok && position.value == wide);
    result = rt_file_read(opened.handle, destination, 3);
    REQUIRE(result.state == DEA_IO_OK && result.count == 3);
    REQUIRE(memcmp(destination, source, 3) == 0 && destination[3] == 7);
    REQUIRE(rt_file_position(opened.handle).value == wide + 3);
    result = rt_file_read_at(opened.handle, destination, 4, wide);
    REQUIRE(result.state == DEA_IO_OK && result.count == 3);
    REQUIRE(memcmp(destination, source, 3) == 0 && destination[3] == 7);
    REQUIRE(rt_file_position(opened.handle).value == wide + 3);
    result = rt_file_write_at(opened.handle, source + 1, 1, wide - 1);
    REQUIRE(result.state == DEA_IO_OK && result.count == 1);
    REQUIRE(rt_file_position(opened.handle).value == wide + 3);
    struct __deaM3sys2fsS12RtFsMetadata info = rt_file_metadata(opened.handle);
    REQUIRE(info.ok && info.size.has_value && info.size.value == wide + 3);
    REQUIRE(rt_file_truncate(opened.handle, wide + 1).ok);
    REQUIRE(rt_file_size(opened.handle).value == wide + 1);
    REQUIRE(rt_file_position(opened.handle).value == wide + 3);
    REQUIRE(rt_file_truncate(opened.handle, 0).ok);
    REQUIRE(rt_file_free(opened.handle).ok);
    return 0;
}

/**
 * Verify runtime input validation and native non-seekable handle behavior.
 *
 * @param argc Argument count including executable name.
 * @param argv Wide-file path and optional POSIX FIFO path.
 * @return Zero when all native checks pass, otherwise one.
 */
int main(int argc, char **argv) {
    REQUIRE(argc == 2 || argc == 3);
    argv = fixture_path_arguments(argc, argv);
    REQUIRE(argv != NULL);
    REQUIRE(wide_offsets(text(argv[1])) == 0);
    REQUIRE(!rt_file_open(text(argv[1]), -1, 0, 0).ok);
    REQUIRE(!rt_file_open(text(argv[1]), 0, 99, 0).ok);
    REQUIRE(!rt_file_open(DEA_STRING_EMPTY, 0, 0, 0).ok);
    Open opened = rt_file_open(text(argv[1]), 2, 0, 0);
    REQUIRE(opened.ok);
    unsigned char byte = 1;
    REQUIRE(rt_file_read(opened.handle, NULL, 1).error.kind == DEA_OS_ERROR_INVALID_INPUT);
    REQUIRE(rt_file_write(opened.handle, &byte, -1).error.kind == DEA_OS_ERROR_INVALID_INPUT);
    REQUIRE(rt_file_read_at(opened.handle, &byte, 1, -1).error.kind == DEA_OS_ERROR_INVALID_INPUT);
    REQUIRE(!rt_file_truncate(opened.handle, -1).ok);
    REQUIRE(!rt_file_seek(opened.handle, 0, 99).ok);
    REQUIRE(rt_file_read(opened.handle, NULL, 0).state == DEA_IO_OK);
    REQUIRE(rt_file_write(opened.handle, NULL, 0).state == DEA_IO_OK);
    REQUIRE(rt_file_close(opened.handle).ok);
    REQUIRE(rt_file_close(opened.handle).ok);
    REQUIRE(rt_file_read(opened.handle, NULL, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_write(opened.handle, NULL, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_read_at(opened.handle, NULL, 0, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_write_at(opened.handle, NULL, 0, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_seek(opened.handle, 0, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_truncate(opened.handle, 0).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_sync_data(opened.handle).error.kind == DEA_OS_ERROR_INVALID_HANDLE);
    REQUIRE(rt_file_free(opened.handle).ok);
#ifdef _WIN32
    Open device = rt_file_open(text("NUL"), 2, 0, 0);
    REQUIRE(device.ok);
    REQUIRE(rt_file_seek(device.handle, 0, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_position(device.handle).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_read_at(device.handle, &byte, 1, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_write_at(device.handle, &byte, 1, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_read_at(device.handle, NULL, 0, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_write_at(device.handle, NULL, 0, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_truncate(device.handle, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
    REQUIRE(rt_file_sync_data(device.handle).error.kind == DEA_OS_ERROR_UNSUPPORTED);
    REQUIRE(rt_file_sync_all(device.handle).error.kind == DEA_OS_ERROR_UNSUPPORTED);
    REQUIRE(rt_file_flush(device.handle).ok);
    REQUIRE(rt_file_free(device.handle).ok);
    REQUIRE(sequential_reads > 0 && positional_reads > 0);
#else
    if (argc == 3) {
        Open fifo = rt_file_open(text(argv[2]), 2, 0, 0);
        REQUIRE(fifo.ok);
        REQUIRE(rt_file_seek(fifo.handle, 0, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
        REQUIRE(rt_file_position(fifo.handle).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
        REQUIRE(rt_file_read_at(fifo.handle, &byte, 1, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
        REQUIRE(rt_file_write_at(fifo.handle, &byte, 1, 0).error.kind == DEA_OS_ERROR_NOT_SEEKABLE);
        REQUIRE(rt_file_free(fifo.handle).ok);
    }
#endif
    fixture_free_arguments(argc, argv);
    puts("file native: PASS");
    return 0;
}
