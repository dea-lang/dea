/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file temp_faults.c
 * Fixture-only host substitutions for creation, publication and cleanup failures.
 */
#ifndef _WIN32
#define _DARWIN_C_SOURCE 1
#define _DEFAULT_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700
#else
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0602
#endif
#endif
#include "dea_rt.h"
#include <assert.h>

static int scenario, fills, removals;

/**
 * Select a deterministic failure scenario and reset progress counters.
 *
 * @param mode Scenario number chosen by the target fixture.
 */
void temp_probe_mode(dea_int mode) { scenario = mode; fills = 0; removals = 0; }

/**
 * Return the number of candidate entropy requests.
 *
 * @return Attempts made since the last mode change.
 */
dea_int temp_probe_calls(void) { return fills; }

/**
 * Supply a repeatable candidate or a captured entropy error for each request.
 *
 * @param buffer Writable random-byte destination.
 * @param count Exactly 16 requested bytes.
 * @return Filled result or a simulated partial entropy failure.
 */
static struct __deaM3sys2osS10RtIoResult temp_probe_fill(void *buffer, dea_int count) {
    assert(count == 16);
    ++fills;
    if (scenario == 2) return (struct __deaM3sys2osS10RtIoResult){DEA_IO_FAILED, 3,
        {DEA_OS_ERROR_INTERRUPTED, DEA_OS_DOMAIN_ERRNO, EINTR}};
    memset(buffer, (scenario == 1 ? 0 : fills - 1), (size_t)count);
    return (struct __deaM3sys2osS10RtIoResult){DEA_IO_OK, count, {0}};
}

#if defined(_WIN32)
#include <windows.h>

/**
 * Simulate a volume which discards the protection bit from the creation descriptor.
 *
 * @param sd Actual security descriptor.
 * @param control Receives the reported control flags.
 * @param revision Receives the actual revision.
 * @return Native descriptor inspection outcome.
 */
static BOOL WINAPI temp_probe_control(PSECURITY_DESCRIPTOR sd, PSECURITY_DESCRIPTOR_CONTROL control, LPDWORD revision) {
    BOOL ok = GetSecurityDescriptorControl(sd, control, revision);
    if (ok && scenario == 6) *control &= ~SE_DACL_PROTECTED;
    return ok;
}

/**
 * Inject an adoption failure after the host object exists.
 *
 * @param source Source process.
 * @param original Original native handle.
 * @param destination Destination process.
 * @param duplicate Receives the new handle.
 * @param access Desired access.
 * @param inherit Inheritance policy.
 * @param options Duplication flags.
 * @return Native result unless adoption failure is selected.
 */
static BOOL WINAPI temp_probe_duplicate(HANDLE source, HANDLE original, HANDLE destination, LPHANDLE duplicate,
                                        DWORD access, BOOL inherit, DWORD options) {
    if (scenario == 5) { SetLastError(ERROR_TOO_MANY_OPEN_FILES); return FALSE; }
    return DuplicateHandle(source, original, destination, duplicate, access, inherit, options);
}

/**
 * Fail a selected deletion while allowing earlier entries to be removed.
 *
 * @param handle Opened native object.
 * @param kind Requested information class.
 * @param input Native disposition.
 * @param size Disposition size.
 * @return Native outcome or injected access denial.
 */
static BOOL WINAPI temp_probe_disposition(HANDLE handle, FILE_INFO_BY_HANDLE_CLASS kind, LPVOID input, DWORD size) {
    if (kind == FileDispositionInfo && (scenario == 5 || (scenario == 4 && ++removals == 2))) {
        SetLastError(ERROR_ACCESS_DENIED); return FALSE;
    }
    return SetFileInformationByHandle(handle, kind, input, size);
}

/**
 * Close the real handle and report a synthetic first-close failure on request.
 *
 * @param handle File handle to retire.
 * @return Native or injected outcome.
 */
BOOL temp_probe_close(HANDLE handle) {
    BOOL ok = CloseHandle(handle);
    if (scenario == 3) { SetLastError(ERROR_WRITE_FAULT); return FALSE; }
    return ok;
}

#define DuplicateHandle temp_probe_duplicate
#define SetFileInformationByHandle temp_probe_disposition
#define GetSecurityDescriptorControl temp_probe_control
#define DEA_FILE_CLOSE_HANDLE temp_probe_close
#else
#include <fcntl.h>
#include <unistd.h>
#include <stdarg.h>

/**
 * Intercept descriptor duplication after exclusive creation.
 *
 * @param fd Native descriptor.
 * @param command Descriptor operation.
 * @param ... Optional integer operand.
 * @return Native or injected outcome.
 */
static int temp_probe_fcntl(int fd, int command, ...) {
    if (command == F_GETFD) return fcntl(fd, command);
    va_list args;
    va_start(args, command);
    int argument = va_arg(args, int);
    va_end(args);
    if (scenario == 5 && command == F_DUPFD_CLOEXEC) { errno = EMFILE; return -1; }
    return fcntl(fd, command, argument);
}

/**
 * Fail the selected entry removal after earlier confirmed progress.
 *
 * @param fd Parent descriptor.
 * @param name Single child name.
 * @param flags Native unlink flags.
 * @return Native outcome or injected denial.
 */
static int temp_probe_unlink(int fd, const char *name, int flags) {
    if (scenario == 5 || (scenario == 4 && ++removals == 2)) { errno = EACCES; return -1; }
    return unlinkat(fd, name, flags);
}

/**
 * Close the real descriptor and report a synthetic first-close failure on request.
 *
 * @param fd File descriptor to retire.
 * @return Native or injected outcome.
 */
int temp_probe_close(int fd) {
    int result = close(fd);
    if (scenario == 3) { errno = EIO; return -1; }
    return result;
}

#define fcntl temp_probe_fcntl
#define unlinkat temp_probe_unlink
#define DEA_FILE_CLOSE temp_probe_close
#endif

#define rt_entropy_fill temp_probe_fill
#include "dea_rt_io.c"

#if defined(_WIN32)

/**
 * Refuse files and directories when the host fails to preserve their requested DACL.
 *
 * @param path Owned test directory spelling to use as the parent.
 */
static void temp_probe_discarded_acl(const wchar_t *path) {
    int previous = scenario, previous_fills = fills;
    FsError error = {0};
    dea_string parent = fs_string(path, &error);
    assert(fs_status(error).ok);
    scenario = 6;
    for (int directory = 0; directory <= 1; ++directory) {
        TempOpen rejected = rt_temp_create((dea_opt_string){.has_value = 1, .value = parent}, directory);
        assert(!rejected.owner && rejected.operation == TEMP_CREATE && rejected.error.kind == DEA_OS_ERROR_UNSUPPORTED);
        assert(!rejected.rollback_operation);
        wchar_t *residual = fs_path(rejected.path, &error);
        assert(residual && GetFileAttributesW(residual) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND);
        free(residual);
        rt_string_release(rejected.path);
    }
    scenario = previous;
    fills = previous_fills;
    rt_string_release(parent);
}
#endif

/**
 * Inspect the actual created object's privacy and child inheritance policy.
 *
 * @param raw Live cleanup owner used internally by sys.fs.
 * @param directory Expected object type.
 */
void temp_probe_private(void *raw, dea_bool directory) {
    TempOwner *owner = raw;
    assert(owner->directory == directory);
#if defined(_WIN32)
    PACL acl;
    PSECURITY_DESCRIPTOR sd;
    FsError error = {0};
    TOKEN_USER *user = temp_user(&error);
    assert(user);
    assert(GetSecurityInfo(owner->object, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        NULL, NULL, &acl, NULL, &sd) == ERROR_SUCCESS);
    SECURITY_DESCRIPTOR_CONTROL control;
    DWORD revision, flags;
    assert(GetSecurityDescriptorControl(sd, &control, &revision) && (control & SE_DACL_PROTECTED));
    ACCESS_ALLOWED_ACE *ace;
    assert(acl && acl->AceCount == 1 && GetAce(acl, 0, (void **)&ace));
    assert(ace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE && EqualSid(&ace->SidStart, user->User.Sid));
    assert(GetHandleInformation(owner->object, &flags) && !(flags & HANDLE_FLAG_INHERIT));
    LocalFree(sd); free(user);
    if (directory) temp_probe_discarded_acl(owner->path);
#else
    struct stat st;
    assert(fstat(owner->object, &st) == 0 && st.st_uid == geteuid());
    assert((st.st_mode & 0777) == (directory ? 0700 : 0600));
    assert((fcntl(owner->object, F_GETFD) & FD_CLOEXEC) != 0);
#endif
}
