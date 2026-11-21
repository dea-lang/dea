/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file dea_rt_temp_posix.h
 * Descriptor-relative creation and deletion inside a trusted POSIX hierarchy.
 */
#if defined(__APPLE__)
#include <sys/acl.h>
#include <sys/mount.h>
#elif defined(__linux__)
#include <sys/vfs.h>
#include <linux/magic.h>
#endif

/**
 * Select the POSIX environment override or the host temporary directory.
 *
 * @param error Receives allocation failure.
 * @return Owned spelling.
 */
static char *temp_default(FsError *error) {
    const char *env = getenv("TMPDIR");
    char *path = strdup(env && *env ? env : "/tmp");
    if (!path) *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY);
    return path;
}

/**
 * Check that the selected filesystem implements private POSIX creation modes.
 *
 * @param fd Open parent directory.
 * @return Success for reviewed local filesystems, Unsupported for other semantics.
 */
static FsError temp_private_volume(int fd) {
#if defined(__APPLE__) || defined(__linux__)
    struct statfs volume;
    if (fstatfs(fd, &volume) < 0) return fs_native_error();
#if defined(__APPLE__)
    if (!(volume.f_flags & MNT_IGNORE_OWNERSHIP) &&
        (!strcmp(volume.f_fstypename, "apfs") || !strcmp(volume.f_fstypename, "hfs"))) return fs_error(0);
#else
    switch ((unsigned long)volume.f_type) {
    case EXT4_SUPER_MAGIC:
    case BTRFS_SUPER_MAGIC:
    case XFS_SUPER_MAGIC:
    case TMPFS_MAGIC:
    case RAMFS_MAGIC:
    case OVERLAYFS_SUPER_MAGIC:
        return fs_error(0);
    }
#endif
#else
    (void)fd;
#endif
    return fs_error(DEA_OS_ERROR_UNSUPPORTED);
}

#if defined(__APPLE__)

/**
 * Reject extended grants that can override mode bits or propagate to children.
 *
 * @param fd Pinned directory or symbolic-link descriptor.
 * @return Permission denial for any allow entry, or a captured inspection error.
 */
static FsError temp_trusted_acl(int fd) {
    acl_t acl = acl_get_fd_np(fd, ACL_TYPE_EXTENDED);
    if (!acl) {
        if (errno == ENOENT) return fs_error(0);
        return fs_native_error();
    }
    FsError error = {0};
    acl_entry_t entry;
    int position = ACL_FIRST_ENTRY;
    while (acl_get_entry(acl, position, &entry) == 0) {
        acl_tag_t tag;
        if (acl_get_tag_type(entry, &tag) < 0) { error = fs_native_error(); break; }
        if (tag != ACL_EXTENDED_DENY) { error = fs_error(DEA_OS_ERROR_PERMISSION_DENIED); break; }
        position = ACL_NEXT_ENTRY;
    }
    acl_free(acl);
    return error;
}
#endif

/**
 * Verify ownership and namespace protection on a pinned directory.
 *
 * Sticky shared directories protect existing entries owned by trusted users.
 * Darwin extended allow entries can bypass mode-only reasoning or be inherited
 * by new children. Reject those directory hierarchies conservatively.
 *
 * @param fd Borrowed directory descriptor.
 * @return Captured inspection failure or permission denial for unsafe permissions.
 */
static FsError temp_trusted(int fd) {
    struct stat st;
    if (fstat(fd, &st) < 0) return fs_native_error();
    if ((st.st_uid != 0 && st.st_uid != geteuid()) ||
        ((st.st_mode & (S_IWGRP | S_IWOTH)) && !(st.st_mode & S_ISVTX)))
        return fs_error(DEA_OS_ERROR_PERMISSION_DENIED);
#if defined(__APPLE__)
    return temp_trusted_acl(fd);
#else
    return fs_error(0);
#endif
}

/**
 * Read one trusted link relative to its pinned parent without truncation.
 *
 * @param fd Borrowed directory descriptor.
 * @param name Single entry component.
 * @param error Receives the first failure.
 * @return Owned link contents.
 */
static char *temp_link(int fd, const char *name, FsError *error) {
#if defined(__APPLE__)
    int link = openat(fd, name, O_RDONLY | O_SYMLINK | O_CLOEXEC);
    if (link < 0) { *error = fs_native_error(); return NULL; }
    struct stat opened, named;
    if (fstat(link, &opened) < 0) *error = fs_native_error();
    else if (!S_ISLNK(opened.st_mode) || (opened.st_uid != 0 && opened.st_uid != geteuid()))
        *error = fs_error(DEA_OS_ERROR_PERMISSION_DENIED);
    else *error = temp_trusted_acl(link);
    if (fs_status(*error).ok) {
        if (fstatat(fd, name, &named, AT_SYMLINK_NOFOLLOW) < 0) *error = fs_native_error();
        else if (named.st_dev != opened.st_dev || named.st_ino != opened.st_ino)
            *error = fs_error(DEA_OS_ERROR_PERMISSION_DENIED);
    }
    FsError closed = temp_close(link);
    if (fs_status(*error).ok) *error = closed;
    if (!fs_status(*error).ok) return NULL;
#endif
    for (size_t cap = 128; cap <= INT_MAX; cap *= 2) {
        char *target = malloc(cap + 1);
        if (!target) { *error = fs_error(DEA_OS_ERROR_OUT_OF_MEMORY); return NULL; }
        ssize_t n = readlinkat(fd, name, target, cap);
        if (n < 0) { *error = fs_native_error(); free(target); return NULL; }
        if ((size_t)n < cap) { target[n] = 0; return target; }
        free(target);
    }
    *error = fs_error(DEA_OS_ERROR_FILE_TOO_LARGE);
    return NULL;
}

/**
 * Resolve each component and each trusted symlink target through verified directories.
 *
 * @param fd Owned starting directory for a relative spelling, consumed.
 * @param path Mutable spelling, with separators temporarily split.
 * @param links Shared remaining symlink expansion budget.
 * @param error Receives the first failure.
 * @return Pinned descriptor or -1 on failure.
 */
static int temp_walk(int fd, char *path, unsigned *links, FsError *error) {
    const int flags = O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC;
    if (*path == '/') {
        temp_close(fd);
        fd = open("/", flags);
        if (fd < 0) { *error = fs_native_error(); return -1; }
        *error = temp_trusted(fd);
    }
    while (*path && fs_status(*error).ok) {
        if (*path == '/') { ++path; continue; }
        char *end = strchr(path, '/');
        if (end) *end = 0;
        struct stat st;
        int next = -1;
        if (fstatat(fd, path, &st, AT_SYMLINK_NOFOLLOW) < 0) *error = fs_native_error();
        else if (S_ISLNK(st.st_mode)) {
            if (st.st_uid != 0 && st.st_uid != geteuid()) *error = fs_error(DEA_OS_ERROR_PERMISSION_DENIED);
            else if (!*links) *error = rt_os_error_from_errno(ELOOP);
            else {
                --*links;
                char *target = temp_link(fd, path, error);
                if (target) { next = temp_walk(fd, target, links, error); fd = -1; free(target); }
            }
        } else {
            next = openat(fd, path, flags);
            if (next < 0) *error = fs_native_error();
            else *error = temp_trusted(next);
        }
        temp_close(fd);
        fd = next;
        if (!end) break;
        *end = '/';
        path = end + 1;
    }
    if (!fs_status(*error).ok) { temp_close(fd); return -1; }
    return fd;
}

/**
 * Pin and validate an absolute temporary parent.
 *
 * @param path Writable absolute spelling.
 * @param error Receives the first inspection failure.
 * @return Owned parent descriptor or -1.
 */
static int temp_open_parent(char *path, FsError *error) {
    unsigned links = 40;
    int fd = temp_walk(-1, path, &links, error);
    if (fd < 0) return -1;
    *error = temp_private_volume(fd);
    if (fs_status(*error).ok && faccessat(fd, ".", W_OK | X_OK, AT_EACCESS) != 0) *error = fs_native_error();
    if (!fs_status(*error).ok) { temp_close(fd); return -1; }
    return fd;
}

/**
 * Exclusively create an object and retain its identity through publication.
 *
 * @param owner Initialized owner with pinned parent and selected name.
 * @param file Preallocated ordinary file wrapper, or NULL for directories.
 * @param collision Receives one only for a genuine creation collision.
 * @param out Receives removal failure after partial creation.
 * @return Primary creation or adoption outcome.
 */
static FsError temp_exclusive(TempOwner *owner, DeaFile *file, int *collision, TempOpen *out) {
    int fd;
    if (file) {
        fd = openat(owner->parent, owner->name, O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
        if (fd < 0) { *collision = errno == EEXIST; return fs_native_error(); }
        owner->object = fcntl(fd, F_DUPFD_CLOEXEC, 0);
        if (owner->object >= 0) { file->fd = fd; return fs_error(0); }
    } else {
        if (mkdirat(owner->parent, owner->name, 0700) < 0) {
            *collision = errno == EEXIST;
            return fs_native_error();
        }
        fd = -1;
        owner->object = openat(owner->parent, owner->name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (owner->object >= 0) return fs_error(0);
    }
    FsError error = fs_native_error();
    if (unlinkat(owner->parent, owner->name, file ? 0 : AT_REMOVEDIR) < 0)
        temp_rollback(out, TEMP_REMOVE, fs_native_error());
    temp_rollback(out, TEMP_CLOSE, temp_close(fd));
    return error;
}

/**
 * Delete children using a pinned directory, treating links as leaf entries.
 *
 * @param fd Owned descriptor transferred into enumeration.
 * @param path Diagnostic path to this directory.
 * @param depth Depth below the private root.
 * @param out Accumulating first failure and removal count.
 */
static void temp_empty(int fd, const char *path, unsigned depth, TempCleanup *out) {
    DIR *dir = fdopendir(fd);
    if (!dir) { temp_failure(out, TEMP_ENUMERATE, path, fs_native_error()); temp_close(fd); return; }
    while (!out->operation) {
        errno = 0;
        struct dirent *entry = DEA_FS_READDIR(dir);
        if (!entry) { if (errno) temp_failure(out, TEMP_ENUMERATE, path, fs_native_error()); break; }
        const char *name = entry->d_name;
        if (!strcmp(name, ".") || !strcmp(name, "..")) continue;
        FsError error = {0};
        char *child = fs_join(path, name, &error);
        if (!child) { temp_failure(out, TEMP_ENUMERATE, path, error); break; }
        struct stat st;
        if (fstatat(fd, name, &st, AT_SYMLINK_NOFOLLOW) < 0)
            temp_failure(out, TEMP_VERIFY, child, fs_native_error());
        else {
            int directory = S_ISDIR(st.st_mode);
            if (directory) {
                if (depth == 256) temp_failure(out, TEMP_ENUMERATE, child, fs_error(DEA_OS_ERROR_RESOURCE_EXHAUSTED));
                else {
                    int sub = openat(fd, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
                    if (sub < 0) temp_failure(out, TEMP_ENUMERATE, child, fs_native_error());
                    else temp_empty(sub, child, depth + 1, out);
                }
            }
            if (!out->operation) {
                if (unlinkat(fd, name, directory ? AT_REMOVEDIR : 0) < 0)
                    temp_failure(out, TEMP_REMOVE, child, fs_native_error());
                else ++out->removed;
            }
        }
        free(child);
    }
    if (DEA_FS_CLOSEDIR(dir) < 0) temp_failure(out, TEMP_CLOSE, path, fs_native_error());
}

/**
 * Remove the original entry only while it denotes the retained identity.
 *
 * @param owner Live owner retaining the parent and original object's descriptor.
 * @param out Accumulating first failure and removal count.
 */
static void temp_remove_owned(TempOwner *owner, TempCleanup *out) {
    struct stat entry, pinned;
    if (fstatat(owner->parent, owner->name, &entry, AT_SYMLINK_NOFOLLOW) < 0) {
        if (errno != ENOENT) temp_failure(out, TEMP_VERIFY, owner->path, fs_native_error());
        return;
    }
    if (fstat(owner->object, &pinned) < 0) {
        temp_failure(out, TEMP_VERIFY, owner->path, fs_native_error()); return;
    }
    if (entry.st_dev != pinned.st_dev || entry.st_ino != pinned.st_ino) {
        temp_failure(out, TEMP_VERIFY, owner->path, fs_error(DEA_OS_ERROR_INVALID_INPUT)); return;
    }
    if (owner->directory) {
        int copy = fcntl(owner->object, F_DUPFD_CLOEXEC, 0);
        if (copy < 0) temp_failure(out, TEMP_ENUMERATE, owner->path, fs_native_error());
        else temp_empty(copy, owner->path, 0, out);
    }
    if (!out->operation) {
        if (unlinkat(owner->parent, owner->name, owner->directory ? AT_REMOVEDIR : 0) < 0)
            temp_failure(out, TEMP_REMOVE, owner->path, fs_native_error());
        else ++out->removed;
    }
}
