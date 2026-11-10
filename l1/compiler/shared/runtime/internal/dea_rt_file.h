/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_file.h
 * Stateful file implementation included only after dea_rt_fs.h by dea_rt_io.c.
 * Wrappers remain live after close and retain the first captured close outcome.
 */
#ifndef DEA_RT_FILE_H
#define DEA_RT_FILE_H

#if defined(_WIN32)
#ifdef DEA_FILE_CLOSE_HANDLE

/* Close a handle through the fixture-selectable Win32 hook. */
extern BOOL DEA_FILE_CLOSE_HANDLE(HANDLE handle);
#else
#define DEA_FILE_CLOSE_HANDLE CloseHandle
#endif
#ifdef DEA_FILE_READ_FILE

/* Read bytes through the fixture-selectable Win32 hook. */
extern BOOL DEA_FILE_READ_FILE(HANDLE file, LPVOID buffer, DWORD count, LPDWORD transferred,
                               LPOVERLAPPED overlap);
#else
#define DEA_FILE_READ_FILE ReadFile
#endif
#ifdef DEA_FILE_WRITE_FILE

/* Write bytes through the fixture-selectable Win32 hook. */
extern BOOL DEA_FILE_WRITE_FILE(HANDLE file, LPCVOID buffer, DWORD count, LPDWORD transferred,
                                LPOVERLAPPED overlap);
#else
#define DEA_FILE_WRITE_FILE WriteFile
#endif
#ifdef DEA_FILE_GET_FILE_INFORMATION

/* Query opened-object metadata through the fixture-selectable Win32 hook. */
extern BOOL DEA_FILE_GET_FILE_INFORMATION(HANDLE file, LPBY_HANDLE_FILE_INFORMATION info);
#else
#define DEA_FILE_GET_FILE_INFORMATION GetFileInformationByHandle
#endif
#ifdef DEA_FILE_FLUSH_FILE_BUFFERS

/* Synchronize file data and metadata through the fixture-selectable Win32 hook. */
extern BOOL DEA_FILE_FLUSH_FILE_BUFFERS(HANDLE file);
#else
#define DEA_FILE_FLUSH_FILE_BUFFERS FlushFileBuffers
#endif
#else
#ifdef DEA_FILE_CLOSE

/* Close a descriptor through the fixture-selectable hook. */
extern int DEA_FILE_CLOSE(int fd);
#else
#define DEA_FILE_CLOSE close
#endif
#ifdef DEA_FILE_READ

/* Read bytes through the fixture-selectable hook. */
extern ssize_t DEA_FILE_READ(int fd, void *buffer, size_t count);
#else
#define DEA_FILE_READ read
#endif
#ifdef DEA_FILE_WRITE

/* Write bytes through the fixture-selectable hook. */
extern ssize_t DEA_FILE_WRITE(int fd, const void *buffer, size_t count);
#else
#define DEA_FILE_WRITE write
#endif
#ifdef DEA_FILE_PREAD

/* Read at an offset through the fixture-selectable hook. */
extern ssize_t DEA_FILE_PREAD(int fd, void *buffer, size_t count, off_t offset);
#else
#define DEA_FILE_PREAD pread
#endif
#ifdef DEA_FILE_PWRITE

/* Write at an offset through the fixture-selectable hook. */
extern ssize_t DEA_FILE_PWRITE(int fd, const void *buffer, size_t count, off_t offset);
#else
#define DEA_FILE_PWRITE pwrite
#endif
#ifdef DEA_FILE_FSTAT

/* Query opened-object metadata through the fixture-selectable hook. */
extern int DEA_FILE_FSTAT(int fd, struct stat *info);
#else
#define DEA_FILE_FSTAT fstat
#endif
#ifdef DEA_FILE_FSYNC

/* Synchronize file data and metadata through the fixture-selectable hook. */
extern int DEA_FILE_FSYNC(int fd);
#else
#define DEA_FILE_FSYNC fsync
#endif
#ifdef DEA_FILE_FDATASYNC

/* Synchronize file data through the fixture-selectable hook. */
extern int DEA_FILE_FDATASYNC(int fd);
#else
#define DEA_FILE_FDATASYNC fdatasync
#endif
#endif

typedef struct __deaM3sys2fsS10RtFileOpen FileOpen;
typedef struct __deaM3sys2fsS12RtFileOffset FileOffset;
typedef struct __deaM3sys2osS10RtIoResult FileIo;

/**
 * Owns one native file and its first close result until explicit destruction.
 */
typedef struct DeaFile {
#if defined(_WIN32)
    HANDLE handle;
    HANDLE positional;
    DWORD access;
#else
    int fd;
#endif
    int closed;
    int append;
    FsStatus close_result;
} DeaFile;

/**
 * Validate the runtime-owned wrapper before accessing its native state.
 *
 * @param handle Live wrapper, or NULL for a recoverable invalid-handle result.
 * @return Validated wrapper, or NULL; expired pointers terminate checked builds.
 */
static DeaFile *file_wrapper(void *handle) {
    if (handle == NULL) return NULL;
    return (DeaFile *)_rt_check_ptr_site(NULL, handle, (dea_int)sizeof(DeaFile),
        _RT_ALIGNOF(DeaFile), _RT_ACCESS_WRITE, __FILE__, __LINE__);
}

/**
 * Return whether a wrapper still has a logically open native file.
 *
 * @param file Validated wrapper or NULL.
 * @return Nonzero only before the first close attempt.
 */
static int file_live(DeaFile *file) {
    return file != NULL && !file->closed;
}

/**
 * Build a captured transfer failure without consulting ambient host state.
 *
 * @param error Captured runtime or host error.
 * @return Timeout or failure with zero bytes transferred by this native attempt.
 */
static FileIo file_io_error(FsError error) {
    FileIo out = {0};
    out.state = error.kind == DEA_OS_ERROR_TIMED_OUT ? DEA_IO_TIMED_OUT : DEA_IO_FAILED;
    out.error = error;
    return out;
}

/**
 * Open a non-inherited native file with explicit access and creation policy.
 *
 * Access tags are read (0), write (1), and read/write (2). Creation tags are
 * existing (0), open-or-create (1), exclusive create (2), and truncate/create (3).
 * Creation and append require write access. The returned wrapper owns one cleanup
 * obligation and remains allocated after close. Path conversion preserves native
 * POSIX bytes and requires valid UTF-8 on Windows. No operation retries EINTR.
 *
 * @param path Nonempty path without embedded NUL.
 * @param access Access policy tag.
 * @param create Creation policy tag.
 * @param append Whether writes use native append behavior.
 * @return Owned wrapper on success, or captured validation, allocation, or host error.
 */
FileOpen rt_file_open(dea_string path, dea_int access, dea_int create, dea_bool append) {
    FileOpen out = {0};
    if (access < 0 || access > 2 || create < 0 || create > 3 ||
        (access == 0 && (create != 0 || append))) {
        out.error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
        return out;
    }
    FsChar *native = fs_path(path, &out.error);
    if (native == NULL) return out;
    DeaFile *file = (DeaFile *)rt_alloc((dea_int)sizeof(DeaFile));
    if (file == NULL) {
        free(native);
        out.error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY);
        return out;
    }
    memset(file, 0, sizeof(*file));
    file->append = append;
#if defined(_WIN32)
    static const DWORD creation[] = {OPEN_EXISTING, OPEN_ALWAYS, CREATE_NEW, CREATE_ALWAYS};
    file->access = access == 0 ? GENERIC_READ : access == 1 ? GENERIC_WRITE : GENERIC_READ | GENERIC_WRITE;
    file->positional = INVALID_HANDLE_VALUE;
    file->handle = CreateFileW(native, file->access,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, creation[create], FILE_ATTRIBUTE_NORMAL, NULL);
    if (file->handle == INVALID_HANDLE_VALUE) out.error = fs_native_error();
#else
    int flags = access == 0 ? O_RDONLY : access == 1 ? O_WRONLY : O_RDWR;
    if (create != 0) flags |= O_CREAT;
    if (create == 2) flags |= O_EXCL;
    if (create == 3) flags |= O_TRUNC;
    if (append) flags |= O_APPEND;
#ifdef O_CLOEXEC
    flags |= O_CLOEXEC;
#endif
    file->fd = open(native, flags, 0666);
    if (file->fd < 0) out.error = fs_native_error();
    else {
        int fd_flags = fcntl(file->fd, F_GETFD);
        if (fd_flags < 0 || fcntl(file->fd, F_SETFD, fd_flags | FD_CLOEXEC) < 0) {
            out.error = fs_native_error();
            close(file->fd);
        } else {
            struct stat info;
            if (fstat(file->fd, &info) != 0) {
                out.error = fs_native_error();
                close(file->fd);
            } else if (S_ISDIR(info.st_mode)) {
                out.error = fs_error(DEA_OS_ERROR_IS_DIRECTORY);
                close(file->fd);
            }
        }
    }
#endif
    free(native);
    if (!fs_status(out.error).ok) { rt_free(file); return out; }
    out.ok = 1;
    out.handle = file;
    return out;
}

/**
 * Retire the handle on its first close attempt and preserve the captured result.
 *
 * Logical retirement occurs even on native failure; no native close is retried.
 * POSIX EINTR does not prove native release on every host. Repeated calls return
 * the original result while the wrapper remains allocated.
 *
 * @param handle Live file wrapper; aliases share the same close state.
 * @return Saved first close result, or InvalidHandle for NULL.
 */
FsStatus rt_file_close(void *handle) {
    DeaFile *file = file_wrapper(handle);
    if (file == NULL) return fs_status(fs_error(DEA_OS_ERROR_INVALID_HANDLE));
    if (file->closed) return file->close_result;
    file->closed = 1;
    FsError error = {0};
#if defined(_WIN32)
    if (!DEA_FILE_CLOSE_HANDLE(file->handle)) error = fs_native_error();
    if (file->positional != INVALID_HANDLE_VALUE && !DEA_FILE_CLOSE_HANDLE(file->positional)) {
        FsError secondary = fs_native_error();
        if (fs_status(error).ok) error = secondary;
    }
#else
    if (DEA_FILE_CLOSE(file->fd) != 0) error = fs_native_error();
#endif
    file->close_result = fs_status(error);
    return file->close_result;
}

/**
 * Close if needed and destroy a file wrapper exactly once.
 *
 * @param handle Live wrapper whose cleanup obligation is consumed, even on failure.
 * @return First close result; all aliases expire when this function returns.
 */
FsStatus rt_file_free(void *handle) {
    FsStatus result = rt_file_close(handle);
    if (handle != NULL) rt_free(handle);
    return result;
}

#if defined(_WIN32)

/**
 * Obtain an independent overlapped handle to the already opened object.
 *
 * Reopening by handle preserves object identity after path rename/replacement.
 * The positional handle never maintains or changes the primary file pointer.
 *
 * @param file Live file wrapper.
 * @return Success or captured failure; non-disk objects return NotSeekable.
 */
static FsStatus file_positional_handle(DeaFile *file) {
    if (GetFileType(file->handle) != FILE_TYPE_DISK)
        return fs_status(fs_error(DEA_OS_ERROR_NOT_SEEKABLE));
    if (file->positional == INVALID_HANDLE_VALUE) {
        file->positional = ReOpenFile(file->handle, file->access,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, FILE_FLAG_OVERLAPPED);
        if (file->positional == INVALID_HANDLE_VALUE) return fs_status(fs_native_error());
        if (!SetHandleInformation(file->positional, HANDLE_FLAG_INHERIT, 0)) {
            FsError error = fs_native_error();
            DEA_FILE_CLOSE_HANDLE(file->positional);
            file->positional = INVALID_HANDLE_VALUE;
            return fs_status(error);
        }
    }
    return fs_status(fs_error(0));
}
#endif

/**
 * Perform one direct native transfer without implicit retries or buffering.
 *
 * @param handle Live file wrapper.
 * @param buffer Borrowed storage valid for count bytes; never retained.
 * @param count Nonnegative transfer count.
 * @param offset Nonnegative positional offset when positional is set.
 * @param write_operation Whether to write instead of read.
 * @param positional Whether to preserve the sequential cursor.
 * @return Successful partial progress, EOF, timeout, or captured failure.
 */
static FileIo file_transfer(void *handle, void *buffer, dea_int count, dea_long offset,
                            int write_operation, int positional) {
    DeaFile *file = file_wrapper(handle);
    if (!file_live(file)) return file_io_error(fs_error(DEA_OS_ERROR_INVALID_HANDLE));
    if (count < 0 || (count > 0 && buffer == NULL) || (positional && offset < 0) ||
        (positional && write_operation && file->append))
        return file_io_error(fs_error(DEA_OS_ERROR_INVALID_INPUT));
    FileIo out = {0};
#if defined(_WIN32)
    if (positional) {
        FsStatus prepared = file_positional_handle(file);
        if (!prepared.ok) return file_io_error(prepared.error);
    }
#else
    off_t native_offset = (off_t)offset;
    if (positional && (dea_long)native_offset != offset)
        return file_io_error(fs_error(DEA_OS_ERROR_FILE_TOO_LARGE));
    if (positional && lseek(file->fd, 0, SEEK_CUR) == (off_t)-1)
        return file_io_error(fs_native_error());
#endif
    if (count == 0) return out;
#if defined(_WIN32)
    HANDLE native = positional ? file->positional : file->handle;
    OVERLAPPED overlap;
    memset(&overlap, 0, sizeof(overlap));
    OVERLAPPED *overlap_ptr = NULL;
    if (positional || (write_operation && file->append)) {
        uint64_t position = positional ? (uint64_t)offset : UINT64_MAX;
        overlap.Offset = (DWORD)position;
        overlap.OffsetHigh = (DWORD)(position >> 32);
        overlap_ptr = &overlap;
    }
    DWORD transferred = 0;
    DWORD *immediate_count = positional ? NULL : &transferred;
    BOOL ok = write_operation ? DEA_FILE_WRITE_FILE(native, buffer, (DWORD)count, immediate_count, overlap_ptr)
                              : DEA_FILE_READ_FILE(native, buffer, (DWORD)count, immediate_count, overlap_ptr);
    DWORD code = ok ? ERROR_SUCCESS : GetLastError();
    if (positional && (ok || code == ERROR_IO_PENDING)) {
        ok = GetOverlappedResult(native, &overlap, &transferred, TRUE);
        code = ok ? ERROR_SUCCESS : GetLastError();
    }
    if (transferred > 0) { out.count = (dea_int)transferred; return out; }
    if (!ok) {
        if (!write_operation && (code == ERROR_HANDLE_EOF || code == ERROR_BROKEN_PIPE)) {
            out.state = DEA_IO_EOF;
            return out;
        }
        return file_io_error(rt_os_error_from_win32((dea_long)code));
    }
#else
    size_t request = (size_t)count;
#ifdef SSIZE_MAX
    if (request > (size_t)SSIZE_MAX) request = (size_t)SSIZE_MAX;
#endif
    ssize_t transferred;
    if (positional) {
        transferred = write_operation ? DEA_FILE_PWRITE(file->fd, buffer, request, native_offset)
                                      : DEA_FILE_PREAD(file->fd, buffer, request, native_offset);
    } else {
        transferred = write_operation ? DEA_FILE_WRITE(file->fd, buffer, request)
                                      : DEA_FILE_READ(file->fd, buffer, request);
    }
    if (transferred < 0) return file_io_error(fs_native_error());
    if (transferred > 0) { out.count = (dea_int)transferred; return out; }
#endif
    if (write_operation) return file_io_error(fs_error(DEA_OS_ERROR_IO_ERROR));
    out.state = DEA_IO_EOF;
    return out;
}

/**
 * Read once at the sequential cursor, preserving successful partial transfers.
 *
 * @param handle Live file wrapper.
 * @param buffer Borrowed writable storage of at least count bytes.
 * @param count Nonnegative count; zero succeeds without probing EOF.
 * @return Read count, EOF, timeout, or captured failure.
 */
FileIo rt_file_read(void *handle, void *buffer, dea_int count) {
    return file_transfer(handle, buffer, count, 0, 0, 0);
}

/**
 * Write once at the sequential cursor or through native append semantics.
 *
 * @param handle Live file wrapper.
 * @param buffer Borrowed readable storage of at least count bytes.
 * @param count Nonnegative count; positive zero-progress writes fail.
 * @return Written count, timeout, or captured failure.
 */
FileIo rt_file_write(void *handle, void *buffer, dea_int count) {
    return file_transfer(handle, buffer, count, 0, 1, 0);
}

/**
 * Read once at a wide offset without changing the sequential cursor.
 *
 * @param handle Live seekable file wrapper.
 * @param buffer Borrowed writable storage of at least count bytes.
 * @param count Nonnegative count; zero does not probe EOF.
 * @param offset Nonnegative representable file offset.
 * @return Read count, EOF, timeout, or captured failure.
 */
FileIo rt_file_read_at(void *handle, void *buffer, dea_int count, dea_long offset) {
    return file_transfer(handle, buffer, count, offset, 0, 1);
}

/**
 * Write once at a wide offset without changing the sequential cursor.
 *
 * @param handle Live seekable non-append file wrapper.
 * @param buffer Borrowed readable storage of at least count bytes.
 * @param count Nonnegative count; positive zero-progress writes fail.
 * @param offset Nonnegative representable file offset.
 * @return Written count, timeout, or captured failure; append is InvalidInput.
 */
FileIo rt_file_write_at(void *handle, void *buffer, dea_int count, dea_long offset) {
    return file_transfer(handle, buffer, count, offset, 1, 1);
}

/**
 * Move the sequential cursor relative to the start, current position, or end.
 *
 * Seeking beyond EOF does not extend the file. Failure leaves native host error
 * data intact; negative resulting offsets are rejected by the native operation.
 *
 * @param handle Live file wrapper.
 * @param offset Signed relative offset in bytes.
 * @param origin Start (0), current (1), or end (2).
 * @return New nonnegative cursor, or captured failure including NotSeekable.
 */
FileOffset rt_file_seek(void *handle, dea_long offset, dea_int origin) {
    FileOffset out = {0};
    DeaFile *file = file_wrapper(handle);
    if (!file_live(file)) { out.error = fs_error(DEA_OS_ERROR_INVALID_HANDLE); return out; }
    if (origin < 0 || origin > 2) { out.error = fs_error(DEA_OS_ERROR_INVALID_INPUT); return out; }
#if defined(_WIN32)
    if (GetFileType(file->handle) != FILE_TYPE_DISK) {
        out.error = fs_error(DEA_OS_ERROR_NOT_SEEKABLE); return out;
    }
    static const DWORD origins[] = {FILE_BEGIN, FILE_CURRENT, FILE_END};
    LARGE_INTEGER distance, result;
    distance.QuadPart = offset;
    if (!SetFilePointerEx(file->handle, distance, &result, origins[origin])) {
        out.error = fs_native_error(); return out;
    }
    out.value = result.QuadPart;
#else
    off_t distance = (off_t)offset;
    if ((dea_long)distance != offset) { out.error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return out; }
    static const int origins[] = {SEEK_SET, SEEK_CUR, SEEK_END};
    off_t result = lseek(file->fd, distance, origins[origin]);
    if (result == (off_t)-1) { out.error = fs_native_error(); return out; }
    if ((off_t)(dea_long)result != result) { out.error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE); return out; }
    out.value = (dea_long)result;
#endif
    out.ok = 1;
    return out;
}

/**
 * Query the sequential cursor without moving it.
 *
 * @param handle Live seekable file wrapper.
 * @return Current wide cursor, or captured failure.
 */
FileOffset rt_file_position(void *handle) {
    return rt_file_seek(handle, 0, 1);
}

/**
 * Query metadata for the opened object independently of its former path.
 *
 * @param handle Live file wrapper.
 * @return Metadata with wide nullable fields, or captured failure.
 */
FsMetadata rt_file_metadata(void *handle) {
    FsMetadata out = {0};
    DeaFile *file = file_wrapper(handle);
    if (!file_live(file)) { out.error = fs_error(DEA_OS_ERROR_INVALID_HANDLE); return out; }
#if defined(_WIN32)
    BY_HANDLE_FILE_INFORMATION info;
    if (!DEA_FILE_GET_FILE_INFORMATION(file->handle, &info)) { out.error = fs_native_error(); return out; }
    out.file_type = fs_attributes_type(info.dwFileAttributes);
    uint64_t size = ((uint64_t)info.nFileSizeHigh << 32) | info.nFileSizeLow;
    if (size <= INT64_MAX) out.size = (dea_opt_long){1, (dea_long)size};
    uint64_t ticks = ((uint64_t)info.ftLastWriteTime.dwHighDateTime << 32) | info.ftLastWriteTime.dwLowDateTime;
    out.mtime_sec = (dea_opt_long){1, (dea_long)(ticks / 10000000) - INT64_C(11644473600)};
    out.mtime_nsec = (dea_opt_int){1, (dea_int)((ticks % 10000000) * 100)};
#else
    struct stat info;
    if (DEA_FILE_FSTAT(file->fd, &info) != 0) { out.error = fs_native_error(); return out; }
    out.file_type = S_ISREG(info.st_mode) ? 1 : S_ISDIR(info.st_mode) ? 2 : S_ISLNK(info.st_mode) ? 3 : 4;
    if (info.st_size >= 0 && (off_t)(dea_long)info.st_size == info.st_size)
        out.size = (dea_opt_long){1, (dea_long)info.st_size};
    if ((time_t)(dea_long)info.st_mtime == info.st_mtime) {
        out.mtime_sec = (dea_opt_long){1, (dea_long)info.st_mtime};
#if defined(__APPLE__)
        out.mtime_nsec = (dea_opt_int){1, (dea_int)info.st_mtimespec.tv_nsec};
#else
        out.mtime_nsec = (dea_opt_int){1, (dea_int)info.st_mtim.tv_nsec};
#endif
    }
#endif
    out.ok = 1;
    return out;
}

/**
 * Query the opened object's wide byte extent without moving its cursor.
 *
 * @param handle Live file wrapper.
 * @return Nonnegative byte extent, or captured failure/Unsupported if unavailable.
 */
FileOffset rt_file_size(void *handle) {
    FileOffset out = {0};
    FsMetadata metadata = rt_file_metadata(handle);
    if (!metadata.ok) { out.error = metadata.error; return out; }
    if (!metadata.size.has_value) { out.error = fs_error(DEA_OS_ERROR_UNSUPPORTED); return out; }
    out.ok = 1;
    out.value = metadata.size.value;
    return out;
}

/**
 * Set the file extent without changing its sequential cursor.
 *
 * @param handle Live writable file wrapper.
 * @param size Nonnegative new byte extent representable by the host.
 * @return Success or captured validation/host failure.
 */
FsStatus rt_file_truncate(void *handle, dea_long size) {
    DeaFile *file = file_wrapper(handle);
    if (!file_live(file)) return fs_status(fs_error(DEA_OS_ERROR_INVALID_HANDLE));
    if (size < 0) return fs_status(fs_error(DEA_OS_ERROR_INVALID_INPUT));
#if defined(_WIN32)
    if (GetFileType(file->handle) != FILE_TYPE_DISK)
        return fs_status(fs_error(DEA_OS_ERROR_NOT_SEEKABLE));
    FILE_END_OF_FILE_INFO info;
    info.EndOfFile.QuadPart = size;
    if (!SetFileInformationByHandle(file->handle, FileEndOfFileInfo, &info, sizeof(info)))
        return fs_status(fs_native_error());
#else
    off_t native_size = (off_t)size;
    if ((dea_long)native_size != size) return fs_status(fs_error(DEA_OS_ERROR_FILE_TOO_LARGE));
    if (ftruncate(file->fd, native_size) != 0) return fs_status(fs_native_error());
#endif
    return fs_status(fs_error(0));
}

/**
 * Validate an open handle without issuing a durability or buffering operation.
 *
 * @param handle Live file wrapper.
 * @return Success for an open wrapper, or InvalidHandle after close.
 */
FsStatus rt_file_flush(void *handle) {
    return fs_status(fs_error(file_live(file_wrapper(handle)) ? 0 : DEA_OS_ERROR_INVALID_HANDLE));
}

/**
 * Request host synchronization, allowing a stronger full-sync fallback.
 *
 * Apple and Windows use their full file synchronization operation for both
 * requests. Successful synchronization retains the host/filesystem guarantees;
 * it cannot guarantee against hardware that fails to honor cache-flush requests.
 *
 * @param handle Live file wrapper.
 * @param data_only Whether associated metadata beyond data retrieval is optional.
 * @return Success, Unsupported when the minimum is unavailable, or captured error.
 */
static FsStatus file_sync(void *handle, int data_only) {
    DeaFile *file = file_wrapper(handle);
    if (!file_live(file)) return fs_status(fs_error(DEA_OS_ERROR_INVALID_HANDLE));
#if defined(_WIN32)
    (void)data_only;
    if (GetFileType(file->handle) != FILE_TYPE_DISK)
        return fs_status(fs_error(DEA_OS_ERROR_UNSUPPORTED));
    if (!DEA_FILE_FLUSH_FILE_BUFFERS(file->handle)) {
        FsError error = fs_native_error();
        if (error.native_code == ERROR_INVALID_FUNCTION || error.native_code == ERROR_NOT_SUPPORTED)
            error.kind = DEA_OS_ERROR_UNSUPPORTED;
        return fs_status(error);
    }
#else
    int result;
#if defined(__APPLE__)
    (void)data_only;
    result = DEA_FILE_FSYNC(file->fd);
#else
    result = data_only ? DEA_FILE_FDATASYNC(file->fd) : DEA_FILE_FSYNC(file->fd);
#endif
    if (result != 0) {
        FsError error = fs_native_error();
        if (error.native_code == EINVAL || error.native_code == ENOSYS)
            error.kind = DEA_OS_ERROR_UNSUPPORTED;
        return fs_status(error);
    }
#endif
    return fs_status(fs_error(0));
}

/**
 * Synchronize data at minimum, using full synchronization where required.
 *
 * @param handle Live file wrapper.
 * @return Success, Unsupported, or captured host failure.
 */
FsStatus rt_file_sync_data(void *handle) {
    return file_sync(handle, 1);
}

/**
 * Synchronize file data and its associated metadata through the host operation.
 *
 * @param handle Live file wrapper.
 * @return Success, Unsupported, or captured host failure.
 */
FsStatus rt_file_sync_all(void *handle) {
    return file_sync(handle, 0);
}

#endif
