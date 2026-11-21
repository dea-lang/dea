/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_temp_windows.h
 * Handle-relative Windows temporary objects with private creation descriptors.
 */
#include <aclapi.h>
#include <sddl.h>
#include <winternl.h>
#include <winioctl.h>

typedef NTSTATUS (NTAPI *TempNtCreate)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES, PIO_STATUS_BLOCK,
    PLARGE_INTEGER, ULONG, ULONG, ULONG, ULONG, PVOID, ULONG);
typedef ULONG (NTAPI *TempDosError)(NTSTATUS);
typedef DWORD (WINAPI *TempPathW)(DWORD, LPWSTR);

#ifndef OBJ_DONT_REPARSE
#define OBJ_DONT_REPARSE 0x1000u
#endif

#define TEMP_SHARE (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)

/**
 * Query the host default, including the SYSTEM-specific modern selection.
 *
 * @param error Receives a discovery or allocation error.
 * @return Owned host path.
 */
static wchar_t *temp_default(FsError *error) {
    TempPathW query = (TempPathW)(void (*)(void))GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "GetTempPath2W");
    if (!query) query = GetTempPathW;
    DWORD cap = MAX_PATH + 1;
    for (;;) {
        wchar_t *path = calloc(cap, sizeof(*path));
        if (!path) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
        DWORD n = query(cap, path);
        if (n && n < cap) return path;
        if (!n) *error = fs_native_error();
        free(path);
        if (!n) return NULL;
        cap = n;
    }
}

/**
 * Obtain the SID of the effective thread or process token.
 *
 * @param error Receives token inspection or allocation failure.
 * @return Owned token information containing its SID.
 */
static TOKEN_USER *temp_user(FsError *error) {
    HANDLE token;
    if (!OpenThreadToken(GetCurrentThread(), TOKEN_QUERY, TRUE, &token)) {
        if (GetLastError() != ERROR_NO_TOKEN || !OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
            *error = fs_native_error(); return NULL;
        }
    }
    DWORD n = 0;
    GetTokenInformation(token, TokenUser, NULL, 0, &n);
    TOKEN_USER *user = NULL;
    if (!n) *error = fs_native_error();
    else {
        user = malloc(n);
        if (!user) *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY);
        else if (!GetTokenInformation(token, TokenUser, user, n, &n)) {
            *error = fs_native_error(); free(user); user = NULL;
        }
    }
    CloseHandle(token);
    return user;
}

/**
 * Identify the effective user and trusted operating-system principals.
 *
 * @param sid Valid SID from an inspected security descriptor.
 * @param user Effective user SID.
 * @param installer TrustedInstaller service SID.
 * @return True only for an explicitly trusted principal.
 */
static int temp_trusted_sid(PSID sid, PSID user, PSID installer) {
    return EqualSid(sid, user) || EqualSid(sid, installer) ||
        IsWellKnownSid(sid, WinLocalSystemSid) || IsWellKnownSid(sid, WinBuiltinAdministratorsSid);
}

/**
 * Inspect a directory or alias before using it as a namespace component.
 *
 * @param handle Pinned directory or link with READ_CONTROL access.
 * @param user Effective user SID.
 * @param installer TrustedInstaller SID.
 * @return Permission denial for untrusted owners, unsafe grants or unrecognized ACLs.
 */
static FsError temp_trusted(HANDLE handle, PSID user, PSID installer) {
    PSID owner;
    PACL acl;
    PSECURITY_DESCRIPTOR sd = NULL;
    DWORD code = GetSecurityInfo(handle, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        &owner, NULL, &acl, NULL, &sd);
    if (code != ERROR_SUCCESS) return rt_os_error_from_win32(code);
    int trusted = owner && temp_trusted_sid(owner, user, installer) && acl;
    for (DWORD i = 0; trusted && i < acl->AceCount; ++i) {
        ACE_HEADER *ace;
        if (!GetAce(acl, i, (void **)&ace)) { trusted = 0; break; }
        if ((ace->AceFlags & INHERIT_ONLY_ACE) || ace->AceType == ACCESS_DENIED_ACE_TYPE) continue;
        if (ace->AceType != ACCESS_ALLOWED_ACE_TYPE) { trusted = 0; break; }
        ACCESS_ALLOWED_ACE *allow = (ACCESS_ALLOWED_ACE *)ace;
        DWORD unsafe = WRITE_DAC | WRITE_OWNER | DELETE | FILE_DELETE_CHILD | FILE_WRITE_ATTRIBUTES |
            FILE_WRITE_DATA | FILE_WRITE_EA | GENERIC_WRITE | GENERIC_ALL;
        if ((allow->Mask & unsafe) && !temp_trusted_sid(&allow->SidStart, user, installer)) trusted = 0;
    }
    LocalFree(sd);
    return fs_error(trusted ? 0 : DEA_OS_ERROR_PERMISSION_DENIED);
}

/**
 * Open or exclusively create one child against an already pinned directory.
 *
 * @param parent Directory handle.
 * @param name Single terminated entry name, or empty to reopen the pinned directory itself.
 * @param access Explicit desired rights.
 * @param disposition Native open (1) or exclusive create (2).
 * @param options Native object and reparse options.
 * @param sd Optional security descriptor applied at creation.
 * @param error Receives normalized kind and original NTSTATUS.
 * @return Non-inheritable handle, or INVALID_HANDLE_VALUE.
 */
static HANDLE temp_child(HANDLE parent, const wchar_t *name, DWORD access, ULONG disposition,
                         ULONG options, PSECURITY_DESCRIPTOR sd, FsError *error) {
    HMODULE module = GetModuleHandleW(L"ntdll.dll");
    TempNtCreate create = (TempNtCreate)(void (*)(void))GetProcAddress(module, "NtCreateFile");
    TempDosError translate = (TempDosError)(void (*)(void))GetProcAddress(module, "RtlNtStatusToDosError");
    size_t len = wcslen(name);
    if (!create || !translate) { *error = fs_error(DEA_OS_ERROR_UNSUPPORTED); return INVALID_HANDLE_VALUE; }
    if ((!len && !(disposition == FILE_OPEN && (options & FILE_DIRECTORY_FILE))) ||
        len > USHRT_MAX / sizeof(wchar_t) || wcspbrk(name, L"\\/:") ||
        !wcscmp(name, L".") || !wcscmp(name, L"..")) {
        *error = fs_error(DEA_OS_ERROR_INVALID_INPUT); return INVALID_HANDLE_VALUE;
    }
    UNICODE_STRING component;
    component.Length = component.MaximumLength = (USHORT)(len * sizeof(wchar_t));
    component.Buffer = (wchar_t *)name;
    OBJECT_ATTRIBUTES attrs = {0};
    attrs.Length = sizeof(attrs);
    attrs.RootDirectory = parent;
    attrs.ObjectName = &component;
    attrs.Attributes = OBJ_CASE_INSENSITIVE;
    if (disposition == FILE_CREATE) attrs.Attributes |= OBJ_DONT_REPARSE;
    attrs.SecurityDescriptor = sd;
    IO_STATUS_BLOCK io;
    HANDLE handle;
    NTSTATUS status = create(&handle, access | SYNCHRONIZE, &attrs, &io, NULL, FILE_ATTRIBUTE_NORMAL,
        TEMP_SHARE, disposition, options | FILE_SYNCHRONOUS_IO_NONALERT, NULL, 0);
    if (status >= 0) return handle;
    *error = rt_os_error_from_win32(translate(status));
    error->domain = DEA_OS_DOMAIN_NTSTATUS;
    error->native_code = (dea_long)(uint32_t)status;
    return INVALID_HANDLE_VALUE;
}

/**
 * Read a junction or symbolic link without traversing its target.
 *
 * @param link Open reparse-point handle.
 * @param parent Retained handle to the physical containing directory.
 * @param error Receives invalid, unsupported or inaccessible target errors.
 * @return Owned absolute path to inspect from its volume root.
 */
static wchar_t *temp_link(HANDLE link, HANDLE parent, FsError *error) {
    union { DWORD align; BYTE bytes[MAXIMUM_REPARSE_DATA_BUFFER_SIZE]; } storage;
    DWORD used;
    if (!DeviceIoControl(link, FSCTL_GET_REPARSE_POINT, NULL, 0, storage.bytes,
        sizeof(storage.bytes), &used, NULL)) { *error = fs_native_error(); return NULL; }
    DWORD tag, flags = 0;
    WORD offset, length;
    if (used < 16) { *error = fs_error(DEA_OS_ERROR_INVALID_INPUT); return NULL; }
    memcpy(&tag, storage.bytes, sizeof(tag));
    DWORD start = 16;
    if (tag == IO_REPARSE_TAG_SYMLINK && used >= 20) {
        memcpy(&flags, storage.bytes + 16, sizeof(flags));
        start = 20;
    } else if (tag != IO_REPARSE_TAG_MOUNT_POINT) { *error = fs_error(DEA_OS_ERROR_UNSUPPORTED); return NULL; }
    memcpy(&offset, storage.bytes + 8, sizeof(offset));
    memcpy(&length, storage.bytes + 10, sizeof(length));
    if (!length || (offset | length) % sizeof(wchar_t) || start + offset + length > used) {
        *error = fs_error(DEA_OS_ERROR_INVALID_INPUT); return NULL;
    }
    wchar_t *target = calloc(length / sizeof(wchar_t) + 1, sizeof(wchar_t));
    if (!target) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
    memcpy(target, storage.bytes + start + offset, length);
    if (wcslen(target) != length / sizeof(wchar_t)) *error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
    else if (flags == 1) {
        DWORD size = GetFinalPathNameByHandleW(parent, NULL, 0, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
        wchar_t *physical = NULL, *joined = NULL;
        if (!size) *error = fs_native_error();
        else if (!(physical = calloc(size, sizeof(*physical)))) *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY);
        else {
            DWORD n = GetFinalPathNameByHandleW(parent, physical, size, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
            if (!n) *error = fs_native_error();
            else if (n >= size) *error = fs_error(DEA_OS_ERROR_RESOURCE_EXHAUSTED);
            else {

                /* Use ordinary DOS/UNC semantics to normalize relative dot components. */
                wchar_t *base = physical;
                if (!wcsncmp(base, L"\\\\?\\UNC\\", 8)) { base += 6; base[0] = L'\\'; }
                else if (!wcsncmp(base, L"\\\\?\\", 4)) base += 4;
                joined = fs_join(base, target, error);
            }
        }
        free(physical); free(target); target = joined;
    } else if (!wcsncmp(target, L"\\??\\", 4)) {
        target[1] = L'\\';
    } else *error = fs_error(DEA_OS_ERROR_UNSUPPORTED);
    if (!fs_status(*error).ok) { free(target); return NULL; }
    return target;
}

/**
 * Walk an absolute Windows path and recursively validate each alias target.
 *
 * @param path Mutable absolute spelling restored before return.
 * @param user Effective user SID.
 * @param installer TrustedInstaller SID.
 * @param links Remaining alias expansion budget.
 * @param error Receives first lookup or protection failure.
 * @return Retained directory handle or INVALID_HANDLE_VALUE.
 */
static HANDLE temp_walk(wchar_t *path, PSID user, PSID installer, unsigned *links, FsError *error) {
    size_t root = fs_root_length(path);
    if (root == SIZE_MAX || !root) { *error = fs_error(DEA_OS_ERROR_UNSUPPORTED); return INVALID_HANDLE_VALUE; }
    DWORD access = READ_CONTROL | FILE_READ_ATTRIBUTES | FILE_TRAVERSE;
    wchar_t saved = path[root];
    path[root] = 0;
    HANDLE dir = fs_handle(path, 0, access, TEMP_SHARE);
    path[root] = saved;
    if (dir == INVALID_HANDLE_VALUE) { *error = fs_native_error(); return dir; }
    *error = temp_trusted(dir, user, installer);
    size_t at = root;
    while (path[at] && fs_status(*error).ok) {
        if (fs_path_sep(path, path[at])) { ++at; continue; }
        size_t end = at;
        while (path[end] && !fs_path_sep(path, path[end])) ++end;
        saved = path[end];
        path[end] = 0;
        HANDLE child = temp_child(dir, path + at, access, FILE_OPEN, FILE_OPEN_REPARSE_POINT, NULL, error);
        if (child != INVALID_HANDLE_VALUE) {
            *error = temp_trusted(child, user, installer);
            BY_HANDLE_FILE_INFORMATION info;
            if (fs_status(*error).ok) {
                if (!GetFileInformationByHandle(child, &info)) *error = fs_native_error();
                else if (!(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) *error = fs_error(DEA_OS_ERROR_NOT_DIRECTORY);
                else if (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
                    wchar_t *target = NULL;
                    if (!*links) *error = fs_error(DEA_OS_ERROR_INVALID_INPUT);
                    else { --*links; target = temp_link(child, dir, error); }
                    CloseHandle(child); child = INVALID_HANDLE_VALUE;
                    if (target) {
                        FsPath absolute;
                        dea_string text = fs_string(target, error);
                        free(target);
                        if (fs_status(*error).ok) {
                            absolute = rt_fs_absolute(text);
                            if (!absolute.ok) *error = absolute.error;
                            else {
                                target = fs_path(absolute.value, error);
                                if (target) { child = temp_walk(target, user, installer, links, error); free(target); }
                            }
                            rt_string_release(absolute.value);
                        }
                        rt_string_release(text);
                    }
                }
            }
        }
        path[end] = saved;
        CloseHandle(dir);
        dir = child;
        at = end;
    }
    if (!fs_status(*error).ok) { temp_close(dir); return INVALID_HANDLE_VALUE; }
    return dir;
}

/**
 * Pin a trusted parent on a filesystem supporting persistent file ACLs.
 *
 * @param path Writable absolute spelling.
 * @param error Receives the first failure.
 * @return Validated directory handle or INVALID_HANDLE_VALUE.
 */
static HANDLE temp_open_parent(wchar_t *path, FsError *error) {
    TOKEN_USER *user = temp_user(error);
    if (!user) return INVALID_HANDLE_VALUE;
    PSID installer;
    HANDLE dir = INVALID_HANDLE_VALUE;
    if (!ConvertStringSidToSidW(L"S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464", &installer))
        *error = fs_native_error();
    else {
        unsigned links = 40;
        dir = temp_walk(path, user->User.Sid, installer, &links, error);
        LocalFree(installer);
    }
    free(user);
    if (dir != INVALID_HANDLE_VALUE) {
        DWORD flags;
        if (!GetVolumeInformationByHandleW(dir, NULL, 0, NULL, NULL, &flags, NULL, 0)) *error = fs_native_error();
        else if (!(flags & FILE_PERSISTENT_ACLS)) *error = fs_error(DEA_OS_ERROR_UNSUPPORTED);
        if (fs_status(*error).ok) {
            HANDLE writable = temp_child(dir, L"", FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE |
                FILE_READ_ATTRIBUTES, FILE_OPEN, FILE_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT, NULL, error);
            if (writable != INVALID_HANDLE_VALUE) { CloseHandle(dir); dir = writable; }
        }
        if (!fs_status(*error).ok) { CloseHandle(dir); dir = INVALID_HANDLE_VALUE; }
    }
    return dir;
}

/**
 * Mark an already opened entry for deletion by handle.
 *
 * @param handle Handle with DELETE access to the exact entry.
 * @return Captured disposition result.
 */
static FsError temp_dispose(HANDLE handle) {
    FILE_DISPOSITION_INFO disposition = {TRUE};
    if (!SetFileInformationByHandle(handle, FileDispositionInfo, &disposition, sizeof(disposition))) return fs_native_error();
    return fs_error(0);
}

/**
 * Verify the filesystem applied the private creation descriptor to the new object.
 *
 * @param handle Exclusively created object with READ_CONTROL access.
 * @param user Effective user SID supplied at creation.
 * @param directory Whether the grant must propagate to this directory's children.
 * @return Unsupported if the host discarded or changed the required protection.
 */
static FsError temp_private_object(HANDLE handle, PSID user, int directory) {
    PSID owner;
    PACL acl;
    PSECURITY_DESCRIPTOR sd = NULL;
    DWORD code = GetSecurityInfo(handle, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        &owner, NULL, &acl, NULL, &sd);
    if (code != ERROR_SUCCESS) return rt_os_error_from_win32(code);
    SECURITY_DESCRIPTOR_CONTROL control;
    DWORD revision;
    BYTE flags = directory ? CONTAINER_INHERIT_ACE | OBJECT_INHERIT_ACE : 0;
    FsError error = fs_error(DEA_OS_ERROR_UNSUPPORTED);
    if (!GetSecurityDescriptorControl(sd, &control, &revision)) error = fs_native_error();
    else if ((control & SE_DACL_PROTECTED) && owner && EqualSid(owner, user) && acl && acl->AceCount == 1) {
        ACCESS_ALLOWED_ACE *ace;
        if (!GetAce(acl, 0, (void **)&ace)) error = fs_native_error();
        else if (ace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE && ace->Header.AceFlags == flags &&
                 ace->Mask == FILE_ALL_ACCESS && EqualSid(&ace->SidStart, user)) error = fs_error(0);
    }
    LocalFree(sd);
    return error;
}

/**
 * Create with an effective-user-only protected DACL and adopt the open file.
 *
 * @param owner Initialized owner with pinned parent and selected name.
 * @param file Preallocated ordinary file wrapper, or NULL for directories.
 * @param collision Receives one only for an exclusive name collision.
 * @param out Receives disposal failure after partial creation.
 * @return Captured creation or adoption outcome.
 */
static FsError temp_exclusive(TempOwner *owner, DeaFile *file, int *collision, TempOpen *out) {
    FsError error = {0};
    TOKEN_USER *user = temp_user(&error);
    if (!user) return error;
    SECURITY_DESCRIPTOR sd;
    union { DWORD align; BYTE bytes[sizeof(ACL) + sizeof(ACCESS_ALLOWED_ACE) + SECURITY_MAX_SID_SIZE]; } storage;
    PACL acl = (PACL)storage.bytes;
    DWORD access = DELETE | READ_CONTROL | FILE_READ_ATTRIBUTES |
        (file ? GENERIC_READ | GENERIC_WRITE : FILE_LIST_DIRECTORY | FILE_TRAVERSE);
    if (!InitializeAcl(acl, sizeof(storage), ACL_REVISION) ||
        !AddAccessAllowedAceEx(acl, ACL_REVISION, file ? 0 : CONTAINER_INHERIT_ACE | OBJECT_INHERIT_ACE,
                               FILE_ALL_ACCESS, user->User.Sid) ||
        !InitializeSecurityDescriptor(&sd, SECURITY_DESCRIPTOR_REVISION) ||
        !SetSecurityDescriptorOwner(&sd, user->User.Sid, FALSE) ||
        !SetSecurityDescriptorDacl(&sd, TRUE, acl, FALSE) ||
        !SetSecurityDescriptorControl(&sd, SE_DACL_PROTECTED, SE_DACL_PROTECTED)) error = fs_native_error();
    else {
        HANDLE h = temp_child(owner->parent, owner->name, access, FILE_CREATE,
            file ? FILE_NON_DIRECTORY_FILE : FILE_DIRECTORY_FILE, &sd, &error);
        if (h == INVALID_HANDLE_VALUE) *collision = error.native_code == (dea_long)0xc0000035u;
        else {
            error = temp_private_object(h, user->User.Sid, !file);
            if (file && fs_status(error).ok && !DuplicateHandle(GetCurrentProcess(), h, GetCurrentProcess(),
                &owner->object, READ_CONTROL | FILE_READ_ATTRIBUTES, FALSE, 0)) error = fs_native_error();
            if (!fs_status(error).ok) {
                temp_rollback(out, TEMP_REMOVE, temp_dispose(h));
                temp_rollback(out, TEMP_CLOSE, temp_close(h));
            } else if (file) {
                file->handle = h;
                file->positional = INVALID_HANDLE_VALUE;
                file->access = GENERIC_READ | GENERIC_WRITE;
            } else owner->object = h;
        }
    }
    free(user);
    return error;
}

/**
 * Enumerate a handle and dispose each child without traversing reparse points.
 *
 * @param dir Borrowed directory handle with list access.
 * @param path Diagnostic path only.
 * @param depth Depth below the private directory root.
 * @param out Accumulating first failure and removal count.
 */
static void temp_empty(HANDLE dir, const wchar_t *path, unsigned depth, TempCleanup *out) {
    DWORD capacity = 65536;
    BYTE *buffer = malloc(capacity);
    if (!buffer) { temp_failure(out, TEMP_ENUMERATE, path, fs_error(DEA_OS_ERROR_OUT_OF_MEMORY)); return; }
    FILE_INFO_BY_HANDLE_CLASS query = FileIdBothDirectoryRestartInfo;
    while (!out->operation) {
        if (!GetFileInformationByHandleEx(dir, query, buffer, capacity)) {
            DWORD code = GetLastError();
            if (code != ERROR_NO_MORE_FILES && code != ERROR_FILE_NOT_FOUND)
                temp_failure(out, TEMP_ENUMERATE, path, rt_os_error_from_win32(code));
            break;
        }
        query = FileIdBothDirectoryInfo;
        for (DWORD at = 0; !out->operation;) {
            FILE_ID_BOTH_DIR_INFO *info = (FILE_ID_BOTH_DIR_INFO *)(buffer + at);
            size_t count = info->FileNameLength / sizeof(wchar_t);
            wchar_t *name = calloc(count + 1, sizeof(*name));
            if (!name) { temp_failure(out, TEMP_ENUMERATE, path, fs_error(DEA_OS_ERROR_OUT_OF_MEMORY)); break; }
            memcpy(name, info->FileName, info->FileNameLength);
            if (wcscmp(name, L".") && wcscmp(name, L"..")) {
                FsError error = {0};
                wchar_t *child_path = fs_join(path, name, &error);
                if (!child_path) temp_failure(out, TEMP_ENUMERATE, path, error);
                else {
                    HANDLE h = temp_child(dir, name, DELETE | FILE_READ_ATTRIBUTES, FILE_OPEN, FILE_OPEN_REPARSE_POINT, NULL, &error);
                    BY_HANDLE_FILE_INFORMATION actual;
                    if (h == INVALID_HANDLE_VALUE) temp_failure(out, TEMP_VERIFY, child_path, error);
                    else {
                        if (!GetFileInformationByHandle(h, &actual)) temp_failure(out, TEMP_VERIFY, child_path, fs_native_error());
                        else if ((actual.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) &&
                                !(actual.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
                            if (depth == 256) temp_failure(out, TEMP_ENUMERATE, child_path, fs_error(DEA_OS_ERROR_RESOURCE_EXHAUSTED));
                            else {
                                HANDLE list = temp_child(h, L"", FILE_LIST_DIRECTORY, FILE_OPEN,
                                    FILE_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT, NULL, &error);
                                if (list == INVALID_HANDLE_VALUE) temp_failure(out, TEMP_ENUMERATE, child_path, error);
                                else {
                                    temp_empty(list, child_path, depth + 1, out);
                                    error = temp_close(list);
                                    if (!fs_status(error).ok) temp_failure(out, TEMP_CLOSE, child_path, error);
                                }
                            }
                        }
                        if (!out->operation) {
                            error = temp_dispose(h);
                            if (fs_status(error).ok) ++out->removed;
                            else temp_failure(out, TEMP_REMOVE, child_path, error);
                        }
                        error = temp_close(h);
                        if (!fs_status(error).ok) temp_failure(out, TEMP_CLOSE, child_path, error);
                    }
                    free(child_path);
                }
            }
            free(name);
            if (!info->NextEntryOffset) break;
            at += info->NextEntryOffset;
        }
    }
    free(buffer);
}

/**
 * Match the named entry to the retained file ID before traversing or disposing.
 *
 * @param owner Live original identity and pinned parent.
 * @param out Accumulating first failure and removal count.
 */
static void temp_remove_owned(TempOwner *owner, TempCleanup *out) {
    FsError error = {0};
    HANDLE entry = temp_child(owner->parent, owner->name, DELETE | FILE_READ_ATTRIBUTES, FILE_OPEN,
                              FILE_OPEN_REPARSE_POINT, NULL, &error);
    FsError remove_access = {0};
    if (entry == INVALID_HANDLE_VALUE && error.kind == DEA_OS_ERROR_PERMISSION_DENIED) {

        /* A readable replacement can deny DELETE. Still establish its identity. */
        remove_access = error;
        error = fs_error(0);
        entry = temp_child(owner->parent, owner->name, FILE_READ_ATTRIBUTES, FILE_OPEN,
                           FILE_OPEN_REPARSE_POINT, NULL, &error);
    }
    if (entry == INVALID_HANDLE_VALUE) {
        if (error.kind != DEA_OS_ERROR_NOT_FOUND) temp_failure(out, TEMP_VERIFY, owner->path, error);
        return;
    }
    FILE_ID_INFO pinned, actual;
    if (!GetFileInformationByHandleEx(owner->object, FileIdInfo, &pinned, sizeof(pinned)) ||
        !GetFileInformationByHandleEx(entry, FileIdInfo, &actual, sizeof(actual)))
        temp_failure(out, TEMP_VERIFY, owner->path, fs_native_error());
    else if (pinned.VolumeSerialNumber != actual.VolumeSerialNumber ||
             memcmp(&pinned.FileId, &actual.FileId, sizeof(actual.FileId)))
        temp_failure(out, TEMP_VERIFY, owner->path, fs_error(DEA_OS_ERROR_INVALID_INPUT));
    else if (!fs_status(remove_access).ok)
        temp_failure(out, TEMP_REMOVE, owner->path, remove_access);
    else {
        FILE_ATTRIBUTE_TAG_INFO attrs;
        if (!GetFileInformationByHandleEx(entry, FileAttributeTagInfo, &attrs, sizeof(attrs)))
            temp_failure(out, TEMP_VERIFY, owner->path, fs_native_error());
        else if (owner->directory && !(attrs.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT))
            temp_empty(owner->object, owner->path, 0, out);
        if (!out->operation) {
            error = temp_dispose(entry);
            if (fs_status(error).ok) ++out->removed;
            else temp_failure(out, TEMP_REMOVE, owner->path, error);
        }
    }
    error = temp_close(entry);
    if (!fs_status(error).ok) temp_failure(out, TEMP_CLOSE, owner->path, error);
}
