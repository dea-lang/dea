/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file file_faults.c
 * Deterministic native primitive faults for actual generated L1 consumers.
 */
#if !defined(_WIN32)
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdlib.h>
#if defined(_WIN32)
#include <windows.h>
#else
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

static int mode, reads, writes, closes, syncs, stats;

/**
 * Reset fault selection and primitive counters.
 *
 * @param value Scenario selected for subsequent file primitives.
 */
void file_probe_config(int value) {
    mode = value;
    reads = writes = closes = syncs = stats = 0;
}

/**
 * Report primitive invocation counts independently of public wrappers.
 *
 * @param which Counter selector: read, write, close, synchronization or metadata.
 * @return Number of calls to the selected primitive family since configuration.
 */
int file_probe_calls(int which) {
    switch (which) {
        case 0: return reads;
        case 1: return writes;
        case 2: return closes;
        case 3: return syncs;
        default: return stats;
    }
}

/**
 * Return the native error expected from the current fault scenario.
 *
 * @return The unchanged native code expected in the public captured error.
 */
int file_probe_error(void) {
#if defined(_WIN32)
    if (mode == 1) return ERROR_OPERATION_ABORTED;
    if (mode == 2) return ERROR_DISK_FULL;
    if (mode == 6) return ERROR_NOT_SUPPORTED;
    if (mode == 7) return ERROR_ACCESS_DENIED;
    if (mode == 9 || mode == 10) return ERROR_SEM_TIMEOUT;
    return ERROR_IO_DEVICE;
#else
    if (mode == 1) return EINTR;
    if (mode == 2) return ENOSPC;
    if (mode == 6) return ENOTSUP;
    if (mode == 7) return EACCES;
    if (mode == 9 || mode == 10) return ETIMEDOUT;
    return EIO;
#endif
}

/**
 * Return the native error domain selected by the host fixture.
 *
 * @return Errno (1) on POSIX or Win32 (2) on Windows.
 */
int file_probe_domain(void) {
#if defined(_WIN32)
    return 2;
#else
    return 1;
#endif
}

#if defined(_WIN32)

/**
 * Require each live native handle to disable inheritance before any transfer.
 *
 * @param handle Native handle selected by the runtime.
 */
static void require_private(HANDLE handle) {
    DWORD flags;
    if (!GetHandleInformation(handle, &flags) || (flags & HANDLE_FLAG_INHERIT)) abort();
}

/**
 * Limit successful Windows reads or inject a terminal outcome after partial progress.
 *
 * Real successful operations retain their native synchronous or overlapped
 * completion behavior. Injected failures do not submit native operations.
 *
 * @param handle Live file handle selected by the runtime.
 * @param buffer Destination bytes passed unchanged to ReadFile.
 * @param count Maximum destination extent, reduced by selected partial scenarios.
 * @param transferred Immediate byte-count destination, or NULL for overlapped I/O.
 * @param overlap Positional operation state, or NULL for a sequential read.
 * @return Native ReadFile result, or FALSE with the selected Win32 error.
 */
BOOL file_probe_read_file(HANDLE handle, LPVOID buffer, DWORD count,
                          LPDWORD transferred, LPOVERLAPPED overlap) {
    require_private(handle);
    ++reads;
    if (mode == 12 && count > 1) count = 1;
    if (mode == 1 || mode == 8 || mode == 9) {
        if (reads > 1) {
            if (transferred != NULL) *transferred = 0;
            SetLastError(mode == 8 ? ERROR_HANDLE_EOF : (DWORD)file_probe_error());
            return FALSE;
        }
        if (count > 2) count = 2;
    }
    return ReadFile(handle, buffer, count, transferred, overlap);
}

/**
 * Limit successful Windows writes or inject a terminal fault or zero progress.
 *
 * Real successful operations retain their native completion behavior. Mode 3
 * returns zero progress for sequential writes and an I/O failure for positional
 * writes, without submitting an operation or fabricating overlapped completion.
 *
 * @param handle Live file handle selected by the runtime.
 * @param buffer Source bytes passed unchanged to WriteFile.
 * @param count Maximum source extent, reduced by selected partial scenarios.
 * @param transferred Immediate byte-count destination, or NULL for overlapped I/O.
 * @param overlap Positional operation state, or NULL for a sequential write.
 * @return Native WriteFile result, deliberate zero progress, or a selected failure.
 */
BOOL file_probe_write_file(HANDLE handle, LPCVOID buffer, DWORD count,
                           LPDWORD transferred, LPOVERLAPPED overlap) {
    require_private(handle);
    ++writes;
    if (mode == 13 && count > 1) count = 1;
    if (mode == 3) {
        if (transferred != NULL) *transferred = 0;
        if (overlap == NULL) return TRUE;
        SetLastError(ERROR_IO_DEVICE);
        return FALSE;
    }
    if (mode == 2 || mode == 10) {
        if (writes > 1) {
            if (transferred != NULL) *transferred = 0;
            SetLastError((DWORD)file_probe_error());
            return FALSE;
        }
        if (count > 2) count = 2;
    }
    return WriteFile(handle, buffer, count, transferred, overlap);
}

/**
 * Consume a Windows handle before injecting a deferred close failure.
 *
 * @param handle Native handle consumed exactly once.
 * @return Native close outcome, or FALSE after consumption with ERROR_IO_DEVICE
 * for the first close and ERROR_ACCESS_DENIED for a secondary close.
 */
BOOL file_probe_close_handle(HANDLE handle) {
    BOOL result = CloseHandle(handle);
    ++closes;
    if (mode == 4) {
        SetLastError(closes == 1 ? ERROR_IO_DEVICE : ERROR_ACCESS_DENIED);
        return FALSE;
    }
    return result;
}

/**
 * Inject opened-object metadata failure or an unrepresentable unsigned size.
 *
 * @param handle Opened handle whose metadata is requested.
 * @param info Destination for native metadata.
 * @return Native metadata result, or FALSE with ERROR_ACCESS_DENIED.
 */
BOOL file_probe_get_file_information(HANDLE handle, LPBY_HANDLE_FILE_INFORMATION info) {
    ++stats;
    if (mode == 7) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    BOOL result = GetFileInformationByHandle(handle, info);
    if (result && mode == 11) {
        info->nFileSizeHigh = 0x80000000u;
        info->nFileSizeLow = 0;
    }
    return result;
}

/**
 * Count Windows synchronization and inject failure or unsupported guarantees.
 *
 * @param handle File handle to synchronize when no fault is selected.
 * @return Native synchronization result, or FALSE with the selected Win32 error.
 */
BOOL file_probe_flush_file_buffers(HANDLE handle) {
    ++syncs;
    if (mode == 5 || mode == 6) { SetLastError((DWORD)file_probe_error()); return FALSE; }
    return FlushFileBuffers(handle);
}

#else

/**
 * Require each live descriptor to disable inheritance before any transfer.
 *
 * @param fd Native descriptor selected by the runtime.
 */
static void require_private(int fd) {
    if (!(fcntl(fd, F_GETFD) & FD_CLOEXEC)) abort();
}

/**
 * Limit successful reads or return partial progress followed by a terminal outcome.
 *
 * @param fd Live file descriptor.
 * @param buffer Destination bytes.
 * @param count Maximum destination extent.
 * @return Native transferred count, zero EOF, or minus one with selected errno.
 */
ssize_t file_probe_read(int fd, void *buffer, size_t count) {
    require_private(fd);
    ++reads;
    if (mode == 12 && count > 1) count = 1;
    if (mode == 1 || mode == 8 || mode == 9) {
        if (reads > 1) {
            if (mode == 8) return 0;
            errno = file_probe_error();
            return -1;
        }
        if (count > 2) count = 2;
    }
    return read(fd, buffer, count);
}

/**
 * Limit successful writes or return a terminal fault or deliberate zero progress.
 *
 * @param fd Live file descriptor.
 * @param buffer Source bytes.
 * @param count Maximum source extent.
 * @return Native transferred count, zero progress, or minus one with selected errno.
 */
ssize_t file_probe_write(int fd, const void *buffer, size_t count) {
    require_private(fd);
    ++writes;
    if (mode == 13 && count > 1) count = 1;
    if (mode == 3) return 0;
    if (mode == 2 || mode == 10) {
        if (writes > 1) { errno = file_probe_error(); return -1; }
        if (count > 2) count = 2;
    }
    return write(fd, buffer, count);
}

/**
 * Limit positional reads or inject a terminal outcome without changing the cursor.
 *
 * @param fd Live file descriptor.
 * @param buffer Destination bytes.
 * @param count Maximum destination extent.
 * @param offset Absolute native file offset passed unchanged to pread.
 * @return Native transferred count, zero EOF, or minus one with selected errno.
 */
ssize_t file_probe_pread(int fd, void *buffer, size_t count, off_t offset) {
    require_private(fd);
    ++reads;
    if (mode == 12 && count > 1) count = 1;
    if (mode == 1 || mode == 8 || mode == 9) {
        if (reads > 1) {
            if (mode == 8) return 0;
            errno = file_probe_error();
            return -1;
        }
        if (count > 2) count = 2;
    }
    return pread(fd, buffer, count, offset);
}

/**
 * Limit positional writes or inject a terminal fault without changing the cursor.
 *
 * @param fd Live file descriptor.
 * @param buffer Source bytes.
 * @param count Maximum source extent.
 * @param offset Absolute native file offset passed unchanged to pwrite.
 * @return Native transferred count, zero progress, or minus one with selected errno.
 */
ssize_t file_probe_pwrite(int fd, const void *buffer, size_t count, off_t offset) {
    require_private(fd);
    ++writes;
    if (mode == 13 && count > 1) count = 1;
    if (mode == 3) return 0;
    if (mode == 2 || mode == 10) {
        if (writes > 1) { errno = file_probe_error(); return -1; }
        if (count > 2) count = 2;
    }
    return pwrite(fd, buffer, count, offset);
}

/**
 * Consume a descriptor before injecting a deferred close failure.
 *
 * @param fd Native descriptor consumed exactly once.
 * @return Native close outcome, or minus one with EIO after actual consumption.
 */
int file_probe_close(int fd) {
    int result = close(fd);
    ++closes;
    if (mode == 4) { errno = EIO; return -1; }
    return result;
}

/**
 * Inject metadata failure without substituting a path lookup.
 *
 * @param fd Opened descriptor whose metadata is requested.
 * @param info Destination for native metadata.
 * @return Native fstat outcome, or minus one with EACCES.
 */
int file_probe_fstat(int fd, struct stat *info) {
    ++stats;
    if (mode == 7) { errno = EACCES; return -1; }
    int result = fstat(fd, info);
    if (result == 0 && mode == 11) info->st_size = -1;
    return result;
}

/**
 * Count synchronization and inject a failure or unsupported minimum guarantee.
 *
 * @param fd Descriptor to synchronize when no fault is selected.
 * @return Native synchronization result, or minus one with the captured fault.
 */
int file_probe_fsync(int fd) {
    ++syncs;
    if (mode == 5 || mode == 6) { errno = file_probe_error(); return -1; }
    return fsync(fd);
}

#if !defined(__APPLE__)

/**
 * Count data synchronization separately from flush and inject selected faults.
 *
 * @param fd Descriptor whose data is synchronized.
 * @return Native data synchronization result, or minus one with a captured fault.
 */
int file_probe_fdatasync(int fd) {
    ++syncs;
    if (mode == 5 || mode == 6) { errno = file_probe_error(); return -1; }
    return fdatasync(fd);
}
#endif
#endif
