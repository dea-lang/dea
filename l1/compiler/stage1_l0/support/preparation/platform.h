/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file platform.h Native metadata, stable reads, coordination, and bounded probes. */
#ifndef L1_PREPARATION_PLATFORM_H
#define L1_PREPARATION_PLATFORM_H
#include <limits.h>
#include <ctype.h>
#include <time.h>
#include <sys/stat.h>
#include <fcntl.h>
#if defined(_WIN32)
#include <windows.h>
#include <direct.h>
#include <io.h>
#else
#include <dirent.h>
#include <poll.h>
#include <signal.h>
#include <sys/file.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <mach-o/dyld.h>
#include <crt_externs.h>
#include <sys/sysctl.h>
#endif
#endif

int32_t l1c_fs_absolute_path(const uint8_t *, int32_t, uint8_t *, int32_t);
int32_t l1c_fs_canonical_existing_path(const uint8_t *, int32_t, uint8_t *, int32_t);
int32_t l1c_fs_resolve_executable(const uint8_t *, int32_t, uint8_t *, int32_t);
int32_t l1c_fs_path_kind_nofollow(const uint8_t *, int32_t);
int32_t l1c_fs_path_kind_follow(const uint8_t *, int32_t);
int32_t l1c_fs_remove_empty_dir(const uint8_t *, int32_t);

typedef int32_t (*PcPathFunction)(const uint8_t *, int32_t, uint8_t *, int32_t);
static char *pc_path_call(const char *path, PcPathFunction fn) {
    int32_t n, actual;
    char *s;
    if (!path || strlen(path) > INT32_MAX)
        return NULL;
    n = fn((const uint8_t *)path, (int32_t)strlen(path), NULL, 0);
    if (n <= 0)
        return NULL;
    s = pc_alloc((size_t)n + 1);
    actual = fn((const uint8_t *)path, (int32_t)strlen(path), (uint8_t *)s, n);
    if (actual != n) {
        free(s);
        return NULL;
    }
    return s;
}
/** Backslashes are ordinary filename bytes on POSIX hosts. */
static int pc_separator(char ch) {
#if defined(_WIN32)
    return ch == '/' || ch == '\\';
#else
    return ch == '/';
#endif
}
static char *pc_join(const char *a, const char *b) {
    PcBuffer s = {0};
    pc_text(&s, a);
    if (s.n && !pc_separator(s.s[s.n - 1]))
        pc_char(&s, '/');
    pc_text(&s, b);
    return pc_take(&s);
}
static char *pc_parent(const char *path) {
    char *s = pc_string(path);
    size_t n = strlen(s), root = 1;
#if defined(_WIN32)
    if (n >= 3 && isalpha((unsigned char)s[0]) && s[1] == ':' && pc_separator(s[2]))
        root = 3;
    else if (n >= 2 && pc_separator(s[0]) && pc_separator(s[1])) {
        /* Never turn a drive root into C: or cross above an absolute UNC share. */
        root = 2;
        while (root < n && !pc_separator(s[root]))
            ++root;
        if (root < n)
            ++root;
        while (root < n && !pc_separator(s[root]))
            ++root;
        if (root < n)
            ++root;
    }
#endif
    while (n > root && pc_separator(s[n - 1]))
        s[--n] = 0;
    while (n > root && !pc_separator(s[n - 1]))
        s[--n] = 0;
    if (n > root)
        s[n - 1] = 0;
    return s;
}
static const char *pc_base(const char *s) {
    const char *p, *base = s;
    for (p = s; *p; ++p)
        if (pc_separator(*p))
            base = p + 1;
    return base;
}
static int pc_kind(const char *s, int follow) {
    return follow ? l1c_fs_path_kind_follow((const uint8_t *)s, (int32_t)strlen(s))
                  : l1c_fs_path_kind_nofollow((const uint8_t *)s, (int32_t)strlen(s));
}
static char *pc_executable(const char *name) {
    char *path;
    if (strchr(name, '/') || (pc_separator('\\') && strchr(name, '\\'))) {
        path = pc_path_call(name, l1c_fs_absolute_path);
        if (path && pc_kind(path, 1) != 1) {
            free(path);
            return NULL;
        }
#if !defined(_WIN32)
        if (path && access(path, X_OK) != 0) {
            free(path);
            return NULL;
        }
#endif
        return path;
    }
    return pc_path_call(name, l1c_fs_resolve_executable);
}
static int pc_path_equal(const char *a, const char *b) {
#if defined(_WIN32)
    for (; *a && *b; ++a, ++b) {
        int left = *a == '\\' ? '/' : tolower((unsigned char)*a);
        int right = *b == '\\' ? '/' : tolower((unsigned char)*b);
        if (left != right)
            return 0;
    }
    return !*a && !*b;
#else
    return !strcmp(a, b);
#endif
}
static int pc_within(const char *path, const char *root) {
    size_t n = strlen(root);
    char *prefix;
    int same;
    if (!n || strlen(path) < n)
        return 0;
    prefix = pc_slice(path, n);
    same = pc_path_equal(prefix, root);
    free(prefix);
    return same && (!path[n] || pc_separator(root[n - 1]) || pc_separator(path[n]));
}
/** Resolve aliases through the nearest existing parent, also for future roots. */
static char *pc_canonical_future(const char *path) {
    char *absolute = pc_path_call(path, l1c_fs_absolute_path), *resolved, *parent, *base, *joined;
    if (!absolute)
        return NULL;
    resolved = pc_path_call(absolute, l1c_fs_canonical_existing_path);
    if (resolved) {
        free(absolute);
        return resolved;
    }
    if (pc_kind(absolute, 0) != 0) {
        free(absolute);
        return NULL;
    }
    parent = pc_parent(absolute);
    base = pc_string(pc_base(absolute));
    if (!strcmp(parent, absolute) || !*base) {
        free(parent);
        free(base);
        free(absolute);
        return NULL;
    }
    resolved = pc_canonical_future(parent);
    free(parent);
    free(absolute);
    if (!resolved) {
        free(base);
        return NULL;
    }
    joined = pc_join(resolved, base);
    free(resolved);
    free(base);
    return joined;
}
/** Create directories without traversing substituted children. */
static int pc_mkdirs(const char *path) {
    int kind = pc_kind(path, 0), ok;
    char *parent;
    if (kind != 0 && kind != 2)
        return 0;
    /* Existing descendants can still have substituted ancestors. Walk all of
       them before accepting a path, including coordination directories. */
#if defined(_WIN32)
    if (kind == 2 && strlen(path) == 3 && path[1] == ':' && (path[2] == '/' || path[2] == '\\'))
        return 1;
    if (kind == 2 && (path[0] == '/' || path[0] == '\\') && (path[1] == '/' || path[1] == '\\')) {
        const char *p = path + 2, *share;
        while (*p && *p != '/' && *p != '\\')
            ++p;
        if (*p)
            ++p;
        share = p;
        while (*p && *p != '/' && *p != '\\')
            ++p;
        if (p > share && (!*p || !p[1]))
            return 1;
    }
#endif
    parent = pc_parent(path);
    if (!strcmp(parent, path)) {
        free(parent);
        return kind == 2;
    }
    ok = pc_mkdirs(parent);
    free(parent);
    if (!ok)
        return 0;
    if (kind == 2)
        return 1;
#if defined(_WIN32)
    ok = _mkdir(path) == 0;
#else
    ok = mkdir(path, 0700) == 0;
#endif
    return ok || (errno == EEXIST && pc_kind(path, 0) == 2);
}
static char *pc_read_file_checked(const char *path, size_t limit, size_t *size, int *io_error) {
    FILE *f;
    PcBuffer b = {0};
    char buffer[16384];
    size_t n;
    int bad, kind = pc_kind(path, 1);
    if (io_error)
        *io_error = 0;
    /* In particular, never block opening a FIFO masquerading as a memo or
       completion record. Concurrent hostile substitution is outside the contract. */
    if (kind != 1) {
        if (kind < 0 && io_error)
            *io_error = EIO;
        return NULL;
    }
    f = fopen(path, "rb");
    if (!f) {
        if (io_error && errno != ENOENT && errno != ENOTDIR)
            *io_error = errno ? errno : EIO;
        return NULL;
    }
    while ((n = fread(buffer, 1, sizeof(buffer), f)) > 0) {
        if (n > limit - b.n) {
            free(b.s);
            fclose(f);
            return NULL;
        }
        pc_bytes(&b, buffer, n);
    }
    bad = ferror(f);
    if (fclose(f) != 0)
        bad = 1;
    if (bad) {
        if (io_error)
            *io_error = EIO;
        free(b.s);
        return NULL;
    }
    if (size)
        *size = b.n;
    return pc_take(&b);
}
static char *pc_read_file(const char *path, size_t limit, size_t *size) {
    return pc_read_file_checked(path, limit, size, NULL);
}
static int pc_write_file(const char *path, const char *s, size_t n) {
    FILE *f;
    int ok;
    if (pc_kind(path, 0) != 0 && pc_kind(path, 0) != 1)
        return 0;
    f = fopen(path, "wb");
    if (!f)
        return 0;
    ok = fwrite(s, 1, n, f) == n;
    if (fclose(f) != 0)
        ok = 0;
    return ok;
}
static PcJson *pc_read_json(const char *path) {
    size_t n;
    char *s = pc_read_file(path, 16 * 1024 * 1024, &n);
    PcJson *j;
    if (!s)
        return NULL;
    j = pj_parse(s, n);
    free(s);
    return j;
}
static int pc_write_json(const char *path, const PcJson *j) {
    char *s = pj_encode(j);
    int ok = pc_write_file(path, s, strlen(s));
    free(s);
    return ok;
}

#if defined(_WIN32)
static PcJson *pc_meta_handle(HANDLE h) {
    BY_HANDLE_FILE_INFORMATION i;
    FILE_BASIC_INFO basic;
    PcJson *m;
    if (!GetFileInformationByHandle(h, &i) ||
        !GetFileInformationByHandleEx(h, FileBasicInfo, &basic, sizeof(basic)))
        return NULL;
    m = pj_new(PJ_OBJECT);
    pj_set_number(m, "device", i.dwVolumeSerialNumber);
    pj_set_number(m, "inode", (int64_t)(((uint64_t)i.nFileIndexHigh << 32) | i.nFileIndexLow));
    pj_set_number(m, "size", (int64_t)(((uint64_t)i.nFileSizeHigh << 32) | i.nFileSizeLow));
    pj_set_number(m, "mtime", basic.LastWriteTime.QuadPart);
    pj_set_number(m, "ctime", basic.ChangeTime.QuadPart);
    pj_set_number(m, "mode", i.dwFileAttributes);
    pj_set_number(m, "reliable", basic.ChangeTime.QuadPart != 0);
    return m;
}
static PcJson *pc_meta(const char *path) {
    HANDLE h = CreateFileA(path, FILE_READ_ATTRIBUTES,
                           FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                           OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    PcJson *m;
    if (h == INVALID_HANDLE_VALUE)
        return NULL;
    m = pc_meta_handle(h);
    CloseHandle(h);
    return m;
}
static PcJson *pc_meta_file(FILE *f) { return pc_meta_handle((HANDLE)_get_osfhandle(_fileno(f))); }
#else
static PcJson *pc_meta_stat(const struct stat *s) {
    PcJson *m = pj_new(PJ_OBJECT);
    pj_set_number(m, "device", (int64_t)s->st_dev);
    pj_set_number(m, "inode", (int64_t)s->st_ino);
    pj_set_number(m, "size", (int64_t)s->st_size);
    pj_set_number(m, "mode", s->st_mode);
#if defined(__APPLE__)
    pj_set_number(m, "mtime", (int64_t)s->st_mtimespec.tv_sec);
    pj_set_number(m, "mtime_ns", s->st_mtimespec.tv_nsec);
    pj_set_number(m, "ctime", (int64_t)s->st_ctimespec.tv_sec);
    pj_set_number(m, "ctime_ns", s->st_ctimespec.tv_nsec);
#else
    pj_set_number(m, "mtime", (int64_t)s->st_mtim.tv_sec);
    pj_set_number(m, "mtime_ns", s->st_mtim.tv_nsec);
    pj_set_number(m, "ctime", (int64_t)s->st_ctim.tv_sec);
    pj_set_number(m, "ctime_ns", s->st_ctim.tv_nsec);
#endif
    pj_set_number(m, "reliable", s->st_ino != 0 && s->st_ctime != 0);
    return m;
}
static PcJson *pc_meta(const char *path) {
    struct stat s;
    if (stat(path, &s) != 0)
        return NULL;
    return pc_meta_stat(&s);
}
static PcJson *pc_meta_file(FILE *f) {
    struct stat s;
    if (fstat(fileno(f), &s) != 0)
        return NULL;
    return pc_meta_stat(&s);
}
#endif
/** Hash a stable regular file; metadata binds the descriptor and selected path. */
static int pc_hash_file_checked(const char *path, char digest[65], PcJson **metadata,
                                int *io_error) {
    FILE *f;
    PcJson *before, *after, *current;
    PcSha sha;
    char buffer[65536];
    size_t n;
    int ok, kind = pc_kind(path, 1);
    if (io_error)
        *io_error = 0;
    if (kind != 1) {
        if (kind < 0 && io_error)
            *io_error = EIO;
        return 0;
    }
    f = fopen(path, "rb");
    if (!f) {
        if (io_error && errno != ENOENT && errno != ENOTDIR)
            *io_error = errno ? errno : EIO;
        return 0;
    }
    before = pc_meta_file(f);
    pc_sha_init(&sha);
    while ((n = fread(buffer, 1, sizeof(buffer), f)) > 0)
        pc_sha_update(&sha, buffer, n);
    ok = !ferror(f);
    after = pc_meta_file(f);
    if (fclose(f) != 0)
        ok = 0;
    current = pc_meta(path);
    ok = ok && before && after && current && pj_equal(before, after) && pj_equal(after, current);
    pj_free(after);
    pj_free(current);
    if (!ok) {
        if (io_error)
            *io_error = EIO;
        pj_free(before);
        return 0;
    }
    pc_sha_finish(&sha, digest);
    if (metadata)
        *metadata = before;
    else
        pj_free(before);
    return 1;
}
static int pc_hash_file(const char *path, char digest[65], PcJson **metadata) {
    return pc_hash_file_checked(path, digest, metadata, NULL);
}
static int pc_hex_digest(const char *s) {
    size_t i;
    if (!s || strlen(s) != 64)
        return 0;
    for (i = 0; i < 64; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f')))
            return 0;
    return 1;
}
static char *pc_json_digest(const PcJson *j) {
    char *s = pj_encode(j);
    char hex[65];
    pc_sha_bytes(s, strlen(s), hex);
    free(s);
    return pc_string(hex);
}

/** List only direct names, deterministically, without assuming file kinds. */
static PcJson *pc_list(const char *path) {
    PcJson *names = pj_new(PJ_OBJECT);
#if defined(_WIN32)
    char *pattern = pc_join(path, "*");
    WIN32_FIND_DATAA data;
    HANDLE h = FindFirstFileA(pattern, &data);
    free(pattern);
    if (h == INVALID_HANDLE_VALUE) {
        pj_free(names);
        return NULL;
    }
    do {
        if (strcmp(data.cFileName, ".") && strcmp(data.cFileName, ".."))
            pj_set_string(names, data.cFileName, data.cFileName);
    } while (FindNextFileA(h, &data));
    if (GetLastError() != ERROR_NO_MORE_FILES) {
        FindClose(h);
        pj_free(names);
        return NULL;
    }
    FindClose(h);
#else
    DIR *d = opendir(path);
    struct dirent *e;
    if (!d) {
        pj_free(names);
        return NULL;
    }
    errno = 0;
    while ((e = readdir(d)) != NULL) {
        if (strcmp(e->d_name, ".") && strcmp(e->d_name, ".."))
            pj_set_string(names, e->d_name, e->d_name);
    }
    if (errno) {
        closedir(d);
        pj_free(names);
        return NULL;
    }
    closedir(d);
#endif
    {
        char *sorted = pj_encode(names);
        PcJson *result = pj_parse(sorted, strlen(sorted));
        free(sorted);
        pj_free(names);
        return result;
    }
}

typedef struct {
#if defined(_WIN32)
    HANDLE handle;
#else
    int fd;
#endif
} PcLock;
static PcLock *pc_lock_file(const char *path) {
    PcLock *l = pc_alloc(sizeof(*l));
    if (pc_kind(path, 0) != 0 && pc_kind(path, 0) != 1) {
        free(l);
        return NULL;
    }
#if defined(_WIN32)
    OVERLAPPED o;
    memset(&o, 0, sizeof(o));
    l->handle = CreateFileA(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            NULL, OPEN_ALWAYS, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
    if (l->handle == INVALID_HANDLE_VALUE) {
        free(l);
        return NULL;
    }
    if (!LockFileEx(l->handle, LOCKFILE_EXCLUSIVE_LOCK, 0, 1, 0, &o)) {
        CloseHandle(l->handle);
        free(l);
        return NULL;
    }
#else
    l->fd = open(path, O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (l->fd < 0) {
        free(l);
        return NULL;
    }
    while (flock(l->fd, LOCK_EX) != 0) {
        if (errno != EINTR) {
            close(l->fd);
            free(l);
            return NULL;
        }
    }
#endif
    return l;
}
static void pc_unlock(PcLock *l) {
    if (!l)
        return;
#if defined(_WIN32)
    CloseHandle(l->handle);
#else
    close(l->fd);
#endif
    free(l);
}

static double pc_milliseconds(void) {
#if defined(_WIN32)
    return (double)GetTickCount64();
#else
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
        return 0;
    return (double)t.tv_sec * 1000 + (double)t.tv_nsec / 1000000;
#endif
}
typedef struct {
    char *out, *err;
    int status, timed_out;
} PcProbe;
static void pc_probe_free(PcProbe *p) {
    free(p->out);
    free(p->err);
    memset(p, 0, sizeof(*p));
}
#if defined(_WIN32)
/** Quote one native Windows argv word using the CRT backslash convention. */
static void pc_windows_word(PcBuffer *b, const char *s) {
    size_t slashes = 0;
    pc_char(b, '"');
    for (;; ++s) {
        if (*s == '\\') {
            ++slashes;
            continue;
        }
        if (*s == '"' || !*s) {
            while (slashes) {
                pc_text(b, "\\\\");
                --slashes;
            }
        } else {
            while (slashes) {
                pc_char(b, '\\');
                --slashes;
            }
        }
        if (!*s)
            break;
        if (*s == '"')
            pc_char(b, '\\');
        pc_char(b, *s);
    }
    pc_char(b, '"');
}
#endif
/** Run bounded argv probes with captured output and no shell interpolation. */
static PcProbe pc_probe(const PcJson *words, int timeout_ms) {
    PcProbe result = {NULL, NULL, -1, 0};
    PcBuffer out = {0}, err = {0};
    const PcJson *w;
    size_t count = pj_count(words), i = 0;
    char **argv = pc_alloc((count + 1) * sizeof(*argv));
    double deadline = pc_milliseconds() + timeout_ms;
    for (w = words->child; w; w = w->next) {
        if (!pj_str(w)) {
            free(argv);
            return result;
        }
        argv[i++] = w->text;
    }
    if (!count) {
        free(argv);
        return result;
    }
#if defined(_WIN32)
    SECURITY_ATTRIBUTES sa = {sizeof(sa), NULL, TRUE};
    HANDLE reads[2] = {0}, writes[2] = {0}, job = NULL;
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    PcBuffer command = {0};
    int started = 0, failed = 0;
    memset(&si, 0, sizeof(si));
    memset(&pi, 0, sizeof(pi));
    si.cb = sizeof(si);
    for (i = 0; i < count; ++i) {
        if (i)
            pc_char(&command, ' ');
        pc_windows_word(&command, argv[i]);
    }
    if (!CreatePipe(&reads[0], &writes[0], &sa, 0) || !CreatePipe(&reads[1], &writes[1], &sa, 0))
        failed = 1;
    if (!failed) {
        SetHandleInformation(reads[0], HANDLE_FLAG_INHERIT, 0);
        SetHandleInformation(reads[1], HANDLE_FLAG_INHERIT, 0);
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdOutput = writes[0];
        si.hStdError = writes[1];
        si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        started = CreateProcessA(NULL, command.s, NULL, NULL, TRUE,
                                 CREATE_SUSPENDED | CREATE_NO_WINDOW, NULL, NULL, &si, &pi) != 0;
    }
    if (started) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
        memset(&limits, 0, sizeof(limits));
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        job = CreateJobObjectA(NULL, NULL);
        if (!job ||
            !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits,
                                     sizeof(limits)) ||
            !AssignProcessToJobObject(job, pi.hProcess)) {
            TerminateProcess(pi.hProcess, 1);
            failed = 1;
        } else
            ResumeThread(pi.hThread);
    }
    for (i = 0; i < 2; ++i)
        if (writes[i]) {
            CloseHandle(writes[i]);
            writes[i] = NULL;
        }
    while (started && !failed) {
        DWORD exit_code;
        int active = 0;
        char buffer[8192];
        for (i = 0; i < 2; ++i) {
            DWORD available = 0, n = 0;
            if (reads[i] && PeekNamedPipe(reads[i], NULL, 0, NULL, &available, NULL) && available) {
                if (available > sizeof(buffer))
                    available = sizeof(buffer);
                if (ReadFile(reads[i], buffer, available, &n, NULL) && n) {
                    PcBuffer *b = i ? &err : &out;
                    pc_bytes(b, buffer, n);
                    active = 1;
                }
            }
        }
        if (out.n + err.n > 4 * 1024 * 1024) {
            failed = 1;
            break;
        }
        GetExitCodeProcess(pi.hProcess, &exit_code);
        if (exit_code != STILL_ACTIVE && !active) {
            result.status = (int)exit_code;
            break;
        }
        if (pc_milliseconds() > deadline) {
            result.timed_out = 1;
            break;
        }
        Sleep(1);
    }
    if (job)
        CloseHandle(job);
    if (started) {
        WaitForSingleObject(pi.hProcess, 5000);
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
    }
    for (i = 0; i < 2; ++i)
        if (reads[i])
            CloseHandle(reads[i]);
    free(command.s);
#else
    int pipes[2][2] = {{-1, -1}, {-1, -1}}, live = 2, status = 0, done = 0, failed = 0;
    pid_t pid = -1;
    if (pipe(pipes[0]) != 0 || pipe(pipes[1]) != 0)
        failed = 1;
    if (!failed)
        pid = fork();
    if (pid == 0) {
        int nullfd;
        setpgid(0, 0);
        dup2(pipes[0][1], STDOUT_FILENO);
        dup2(pipes[1][1], STDERR_FILENO);
        for (i = 0; i < 2; ++i) {
            close(pipes[i][0]);
            close(pipes[i][1]);
        }
        nullfd = open("/dev/null", O_RDONLY);
        if (nullfd >= 0) {
            dup2(nullfd, STDIN_FILENO);
            close(nullfd);
        }
        execvp(argv[0], argv);
        _exit(127);
    }
    if (pid < 0)
        failed = 1;
    if (!failed) {
        setpgid(pid, pid);
        for (i = 0; i < 2; ++i) {
            close(pipes[i][1]);
            pipes[i][1] = -1;
            if (fcntl(pipes[i][0], F_SETFL, O_NONBLOCK) < 0)
                failed = 1;
        }
    }
    while (!failed && (live || !done)) {
        struct pollfd fds[2];
        char buffer[8192];
        ssize_t n;
        for (i = 0; i < 2; ++i) {
            fds[i].fd = pipes[i][0];
            fds[i].events = POLLIN | POLLHUP;
            fds[i].revents = 0;
        }
        if (poll(fds, 2, 10) < 0 && errno != EINTR) {
            failed = 1;
            break;
        }
        for (i = 0; i < 2; ++i) {
            if (pipes[i][0] < 0)
                continue;
            while ((n = read(pipes[i][0], buffer, sizeof(buffer))) > 0) {
                PcBuffer *b = i ? &err : &out;
                pc_bytes(b, buffer, (size_t)n);
                if (out.n + err.n > 4 * 1024 * 1024) {
                    failed = 1;
                    break;
                }
            }
            if (n == 0) {
                close(pipes[i][0]);
                pipes[i][0] = -1;
                --live;
            } else if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)
                failed = 1;
        }
        if (!done) {
            pid_t waited = waitpid(pid, &status, WNOHANG);
            if (waited == pid)
                done = 1;
            else if (waited < 0 && errno != EINTR)
                failed = 1;
        }
        if (pc_milliseconds() > deadline) {
            result.timed_out = 1;
            break;
        }
    }
    if (pid > 0 && (failed || result.timed_out)) {
        kill(-pid, SIGKILL);
        kill(pid, SIGKILL);
        if (!done)
            while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {
            };
    }
    if (pid > 0 && !failed && !result.timed_out && done)
        result.status = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    for (i = 0; i < 2; ++i) {
        if (pipes[i][0] >= 0)
            close(pipes[i][0]);
        if (pipes[i][1] >= 0)
            close(pipes[i][1]);
    }
#endif
    free(argv);
    result.out = pc_take(&out);
    result.err = pc_take(&err);
    return result;
}

static char *pc_self_executable(void) {
    char buffer[32768];
#if defined(_WIN32)
    DWORD n = GetModuleFileNameA(NULL, buffer, sizeof(buffer));
    if (!n || n == sizeof(buffer))
        return NULL;
    return pc_slice(buffer, n);
#elif defined(__APPLE__)
    uint32_t n = sizeof(buffer);
    if (_NSGetExecutablePath(buffer, &n) != 0)
        return NULL;
    return pc_path_call(buffer, l1c_fs_canonical_existing_path);
#else
    ssize_t n = readlink("/proc/self/exe", buffer, sizeof(buffer));
    if (n <= 0 || (size_t)n == sizeof(buffer))
        return NULL;
    return pc_slice(buffer, (size_t)n);
#endif
}
#endif
