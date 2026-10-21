#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#

"""Direct-error ABI, standard-stream states, and public L1 OS result coverage."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from support.compiler_subject import selected_compiler
from support.driver_inputs import native_driver_args


REPO_ROOT = Path(__file__).resolve().parents[3]
L1_ROOT = REPO_ROOT / "l1"
RUNTIME_ROOT = L1_ROOT / "compiler/shared/runtime"
FIXTURE_ROOT = L1_ROOT / "compiler/tests/fixtures/os_runtime"
RUNTIME_SOURCES = (
    "dea_rt_panic.c", "dea_rt_sys.c", "dea_rt_math.c", "dea_rt_rand.c",
    "dea_rt_string.c", "dea_rt_alloc.c", "dea_rt_io.c", "dea_rt_hash.c",
    "dea_rt_time.c",
)


def runtime_c_compiler() -> str:
    """Resolve an explicitly configured compiler or an available C99 compiler.

    Returns:
        Absolute path of the selected compiler.

    Raises:
        AssertionError: An explicit compiler is missing or no compiler exists.
    """
    configured = os.environ.get("L1_RUNTIME_CC") or os.environ.get("L1_CC")
    for candidate in ([configured] if configured else ["clang", "gcc", "cc"]):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise AssertionError(f"OS runtime test requires a C compiler: {configured or 'clang/gcc/cc'}")


def compiler_path() -> Path:
    """Return the selected canonical L1 compiler launcher.

    Returns:
        Host-compatible launcher path for the selected L1 compiler.
    """
    build_dir = Path(os.environ.get("L1_BUILD_DIR", "build/dea"))
    if not build_dir.is_absolute():
        build_dir = L1_ROOT / build_dir
    base = selected_compiler(build_dir / "bin/l1c")
    if os.name == "nt":
        for candidate in (base.with_suffix(".cmd"), base.with_suffix(".exe"), base):
            if candidate.is_file():
                return candidate
    return base


def require_success(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run a command and retain its diagnostics on failure.

    Args:
        command: Executable and arguments.
        **kwargs: Additional subprocess options.

    Returns:
        Successful completed process.

    Raises:
        AssertionError: The command fails.
    """
    completed = subprocess.run(
        command, cwd=L1_ROOT, capture_output=True, text=True, check=False, **kwargs
    )
    assert completed.returncode == 0, (
        f"{command[0]} exited {completed.returncode}:\n{completed.stdout}\n{completed.stderr}"
    )
    return completed


def probe_source() -> str:
    """Return a C probe for mappings and injected stream outcomes.

    Returns:
        C99 source for the runtime mapping and failure-injection probe.
    """
    return r'''
#include "dea_rt.h"
#include <limits.h>
#include <signal.h>
#if defined(_WIN32)
#include <windows.h>
#endif

typedef struct __deaM3sys2osS9RtOsError OsError;
typedef struct __deaM3sys2osS10RtIoResult IoResult;

#define REQUIRE(test) do { if (!(test)) { \
    fprintf(stderr, "OS probe line %d: %s\n", __LINE__, #test); return 1; \
} } while (0)

static int operation_calls;
static int indicator_calls;
static int clear_calls;
static int fake_error;
static int fake_eof;
static int operation_errno;
static int observed_entry_errno;
static size_t transfer_count;
static int flush_result;
static FILE *expected_stream;

/** Require every primitive and status check to inspect the selected endpoint. */
static void require_stream(FILE *stream, const char *operation) {
    if (stream != expected_stream) {
        fprintf(stderr, "OS probe %s routed to the wrong stream\n", operation);
        exit(1);
    }
}

size_t injected_read(void *buffer, size_t size, size_t count, FILE *stream) {
    require_stream(stream, "read");
    operation_calls += 1;
    observed_entry_errno = errno;
    if (transfer_count > 0 && buffer != NULL && count > 0) {
        ((unsigned char *)buffer)[0] = 'x';
    }
    errno = operation_errno;
    return size == 1 ? transfer_count : 0;
}

size_t injected_write(const void *buffer, size_t size, size_t count, FILE *stream) {
    (void)buffer; (void)count;
    require_stream(stream, "write");
    operation_calls += 1;
    observed_entry_errno = errno;
    errno = operation_errno;
    return size == 1 ? transfer_count : 0;
}

int injected_flush(FILE *stream) {
    require_stream(stream, "flush");
    operation_calls += 1;
    observed_entry_errno = errno;
    errno = operation_errno;
    return flush_result;
}

int injected_error(FILE *stream) {
    require_stream(stream, "error indicator");
    indicator_calls += 1;
    errno = EDOM;
    return fake_error;
}

int injected_eof(FILE *stream) {
    require_stream(stream, "EOF indicator");
    indicator_calls += 1;
    errno = ERANGE;
    return fake_eof;
}

void injected_clear(FILE *stream) {
    require_stream(stream, "clear indicators");
    clear_calls += 1;
    errno = EDOM;
}

static void reset(FILE *stream) {
    operation_calls = indicator_calls = clear_calls = 0;
    fake_error = fake_eof = operation_errno = flush_result = 0;
    observed_entry_errno = -1;
    transfer_count = 0;
    expected_stream = stream;
    errno = EACCES;
}

static int mapped_errno(int code, int kind) {
    OsError error = rt_os_error_from_errno(code);
    REQUIRE(error.kind == kind);
    REQUIRE(error.domain == DEA_OS_DOMAIN_ERRNO);
    REQUIRE(error.native_code == code);
    return 0;
}

static int mapped_win32(dea_long code, int kind) {
    OsError error = rt_os_error_from_win32(code);
    REQUIRE(error.kind == kind);
    REQUIRE(error.domain == DEA_OS_DOMAIN_WIN32);
    REQUIRE(error.native_code == code);
    return 0;
}

static int fallback(OsError error, const char *kind, const char *domain, const char *code) {
    dea_string rendered = rt_os_error_message(error);
    const char *text = _rt_string_bytes(rendered);
    REQUIRE(rt_strlen(rendered) > 0);
    REQUIRE(strstr(text, kind) != NULL);
    REQUIRE(strstr(text, domain) != NULL);
    REQUIRE(strstr(text, code) != NULL);
    REQUIRE(strstr(text, "Success") == NULL && strstr(text, "success") == NULL);
    rt_string_release(rendered);
    return 0;
}

static int messages(void) {
    OsError native = rt_os_error_from_errno(ENOENT);
    dea_string first = rt_os_error_message(native);
    REQUIRE(rt_strlen(first) > 0);
    errno = EINVAL;
    REQUIRE(native.native_code == ENOENT);
    dea_string second = rt_os_error_message(native);
    REQUIRE(rt_string_equals(first, second));
    rt_string_release(first);
    rt_string_release(second);

    OsError win = rt_os_error_from_win32(4294967295LL);
    dea_string text;
    REQUIRE(fallback(rt_os_error_from_errno(0), "Other", "Errno", "0") == 0);
    REQUIRE(fallback(rt_os_error_from_errno(-1), "Other", "Errno", "-1") == 0);
    REQUIRE(fallback(rt_os_error_from_errno(123456789), "Other", "Errno", "123456789") == 0);
    REQUIRE(fallback(rt_os_error_from_win32(0), "Other", "Win32", "0") == 0);
    REQUIRE(fallback(rt_os_error_from_win32(-1), "Other", "Win32", "-1") == 0);
    REQUIRE(fallback(rt_os_error_from_win32(4294967296LL), "Other", "Win32", "4294967296") == 0);
    REQUIRE(fallback(rt_os_error_from_win32(9223372036854775807LL),
                     "Other", "Win32", "9223372036854775807") == 0);
    REQUIRE(fallback(win, "Other", "Win32", "4294967295") == 0);
    OsError unknown_domain = { DEA_OS_ERROR_OTHER, 99, -9223372036854775807LL - 1 };
    REQUIRE(fallback(unknown_domain, "Other", "domain 99", "-9223372036854775808") == 0);
    OsError unknown_errno = { DEA_OS_ERROR_OTHER, DEA_OS_DOMAIN_ERRNO, 9223372036854775807LL };
    REQUIRE(fallback(unknown_errno, "Other", "Errno", "9223372036854775807") == 0);
    OsError runtime = { DEA_OS_ERROR_INVALID_INPUT, DEA_OS_DOMAIN_RUNTIME, 0 };
    REQUIRE(fallback(runtime, "InvalidInput", "Runtime", "0") == 0);

#if defined(_WIN32)
    REQUIRE(mapped_win32(ERROR_FILE_NOT_FOUND, DEA_OS_ERROR_NOT_FOUND) == 0);
    REQUIRE(mapped_win32(ERROR_ACCESS_DENIED, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
    REQUIRE(mapped_win32(ERROR_INVALID_HANDLE, DEA_OS_ERROR_INVALID_HANDLE) == 0);
    REQUIRE(mapped_win32(ERROR_INVALID_PARAMETER, DEA_OS_ERROR_INVALID_INPUT) == 0);
    REQUIRE(mapped_win32(ERROR_OPERATION_ABORTED, DEA_OS_ERROR_INTERRUPTED) == 0);
    REQUIRE(mapped_win32(ERROR_BROKEN_PIPE, DEA_OS_ERROR_BROKEN_PIPE) == 0);
    REQUIRE(mapped_win32(ERROR_SEM_TIMEOUT, DEA_OS_ERROR_TIMED_OUT) == 0);
    REQUIRE(mapped_win32(ERROR_NOT_SUPPORTED, DEA_OS_ERROR_UNSUPPORTED) == 0);
    win = rt_os_error_from_win32(ERROR_ACCESS_DENIED);
    text = rt_os_error_message(win);
    REQUIRE(rt_strlen(text) > 0);
    {
        WCHAR host_text[1024];
        char utf8[4096];
        DWORD length = FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                                      NULL, ERROR_ACCESS_DENIED, 0, host_text, 1024, NULL);
        int bytes;
        REQUIRE(length > 0);
        while (length > 0 && (host_text[length - 1] == L'\r' || host_text[length - 1] == L'\n')) {
            length -= 1;
        }
        bytes = WideCharToMultiByte(CP_UTF8, 0, host_text, (int)length,
                                    utf8, (int)sizeof(utf8) - 1, NULL, NULL);
        REQUIRE(bytes > 0);
        utf8[bytes] = '\0';
        REQUIRE(strcmp(_rt_string_bytes(text), utf8) == 0);
    }
    rt_string_release(text);
    puts("native Windows mappings and messages: PASS");
#else
    win = rt_os_error_from_win32(5);
    text = rt_os_error_message(win);
    REQUIRE(strstr(_rt_string_bytes(text), "Win32") != NULL);
    REQUIRE(strstr(_rt_string_bytes(text), "5") != NULL);
    rt_string_release(text);
    puts("simulated Win32 numeric mappings and fallback: PASS");
#endif
    return 0;
}

static int mappings(void) {
    REQUIRE(mapped_errno(ENOENT, DEA_OS_ERROR_NOT_FOUND) == 0);
    REQUIRE(mapped_errno(EACCES, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
    REQUIRE(mapped_errno(EPERM, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
#ifdef EROFS
    REQUIRE(mapped_errno(EROFS, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
#endif
    REQUIRE(mapped_errno(EEXIST, DEA_OS_ERROR_ALREADY_EXISTS) == 0);
    REQUIRE(mapped_errno(EINVAL, DEA_OS_ERROR_INVALID_INPUT) == 0);
#ifdef ENAMETOOLONG
    REQUIRE(mapped_errno(ENAMETOOLONG, DEA_OS_ERROR_INVALID_INPUT) == 0);
#endif
    REQUIRE(mapped_errno(EBADF, DEA_OS_ERROR_INVALID_HANDLE) == 0);
    REQUIRE(mapped_errno(EINTR, DEA_OS_ERROR_INTERRUPTED) == 0);
    REQUIRE(mapped_errno(EAGAIN, DEA_OS_ERROR_WOULD_BLOCK) == 0);
#ifdef EWOULDBLOCK
    REQUIRE(mapped_errno(EWOULDBLOCK, DEA_OS_ERROR_WOULD_BLOCK) == 0);
#endif
    REQUIRE(mapped_errno(EPIPE, DEA_OS_ERROR_BROKEN_PIPE) == 0);
#ifdef ETIMEDOUT
    REQUIRE(mapped_errno(ETIMEDOUT, DEA_OS_ERROR_TIMED_OUT) == 0);
#endif
#ifdef ENOSYS
    REQUIRE(mapped_errno(ENOSYS, DEA_OS_ERROR_UNSUPPORTED) == 0);
#endif
#ifdef ENOTSUP
    REQUIRE(mapped_errno(ENOTSUP, DEA_OS_ERROR_UNSUPPORTED) == 0);
#endif
#ifdef EOPNOTSUPP
    REQUIRE(mapped_errno(EOPNOTSUPP, DEA_OS_ERROR_UNSUPPORTED) == 0);
#endif
    REQUIRE(mapped_errno(ESPIPE, DEA_OS_ERROR_NOT_SEEKABLE) == 0);
    REQUIRE(mapped_errno(ENOMEM, DEA_OS_ERROR_OUT_OF_MEMORY) == 0);
    REQUIRE(mapped_errno(EMFILE, DEA_OS_ERROR_RESOURCE_EXHAUSTED) == 0);
    REQUIRE(mapped_errno(ENFILE, DEA_OS_ERROR_RESOURCE_EXHAUSTED) == 0);
    REQUIRE(mapped_errno(EIO, DEA_OS_ERROR_IO_ERROR) == 0);
    REQUIRE(mapped_errno(EISDIR, DEA_OS_ERROR_IS_DIRECTORY) == 0);
    REQUIRE(mapped_errno(ENOTDIR, DEA_OS_ERROR_NOT_DIRECTORY) == 0);
    REQUIRE(mapped_errno(ENOTEMPTY, DEA_OS_ERROR_DIRECTORY_NOT_EMPTY) == 0);
    REQUIRE(mapped_errno(ENOSPC, DEA_OS_ERROR_NO_SPACE) == 0);
    REQUIRE(mapped_errno(EFBIG, DEA_OS_ERROR_FILE_TOO_LARGE) == 0);
    REQUIRE(mapped_errno(123456789, DEA_OS_ERROR_OTHER) == 0);
    REQUIRE(mapped_win32(2, DEA_OS_ERROR_NOT_FOUND) == 0);
    REQUIRE(mapped_win32(3, DEA_OS_ERROR_NOT_FOUND) == 0);
    REQUIRE(mapped_win32(5, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
    REQUIRE(mapped_win32(19, DEA_OS_ERROR_PERMISSION_DENIED) == 0);
    REQUIRE(mapped_win32(6, DEA_OS_ERROR_INVALID_HANDLE) == 0);
    REQUIRE(mapped_win32(80, DEA_OS_ERROR_ALREADY_EXISTS) == 0);
    REQUIRE(mapped_win32(87, DEA_OS_ERROR_INVALID_INPUT) == 0);
    REQUIRE(mapped_win32(206, DEA_OS_ERROR_INVALID_INPUT) == 0);
    REQUIRE(mapped_win32(109, DEA_OS_ERROR_BROKEN_PIPE) == 0);
    REQUIRE(mapped_win32(112, DEA_OS_ERROR_NO_SPACE) == 0);
    REQUIRE(mapped_win32(121, DEA_OS_ERROR_TIMED_OUT) == 0);
    REQUIRE(mapped_win32(50, DEA_OS_ERROR_UNSUPPORTED) == 0);
    REQUIRE(mapped_win32(995, DEA_OS_ERROR_INTERRUPTED) == 0);
    REQUIRE(mapped_win32(231, DEA_OS_ERROR_WOULD_BLOCK) == 0);
    REQUIRE(mapped_win32(132, DEA_OS_ERROR_NOT_SEEKABLE) == 0);
    REQUIRE(mapped_win32(8, DEA_OS_ERROR_OUT_OF_MEMORY) == 0);
    REQUIRE(mapped_win32(4, DEA_OS_ERROR_RESOURCE_EXHAUSTED) == 0);
    REQUIRE(mapped_win32(1117, DEA_OS_ERROR_IO_ERROR) == 0);
    REQUIRE(mapped_win32(267, DEA_OS_ERROR_NOT_DIRECTORY) == 0);
    REQUIRE(mapped_win32(145, DEA_OS_ERROR_DIRECTORY_NOT_EMPTY) == 0);
    REQUIRE(mapped_win32(223, DEA_OS_ERROR_FILE_TOO_LARGE) == 0);
    /* Winsock has its own namespace; unrecognized Win32 codes stay intact. */
    REQUIRE(mapped_win32(10035, DEA_OS_ERROR_OTHER) == 0);
    REQUIRE(mapped_win32(4294967295LL, DEA_OS_ERROR_OTHER) == 0);
    REQUIRE(mapped_win32(9223372036854775807LL, DEA_OS_ERROR_OTHER) == 0);
    REQUIRE(mapped_win32(-1, DEA_OS_ERROR_OTHER) == 0);
    return messages();
}

static int check_failure(IoResult result, int kind, int code, int state) {
    REQUIRE(result.state == state && result.count == 0);
    REQUIRE(result.error.kind == kind);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_ERRNO);
    REQUIRE(result.error.native_code == code);
    REQUIRE(operation_calls == 1);
    REQUIRE(observed_entry_errno == 0);
    return 0;
}

static int streams(void) {
    dea_byte bytes[8] = { 0 };
    IoResult result;
    reset(stdin);
    result = rt_stdin_read_result(NULL, 0);
    REQUIRE(result.state == DEA_IO_OK && result.count == 0);
    result = rt_stdout_write_result(NULL, 0);
    REQUIRE(result.state == DEA_IO_OK && result.count == 0);
    result = rt_stderr_write_result(NULL, 0);
    REQUIRE(result.state == DEA_IO_OK && result.count == 0);
    REQUIRE(operation_calls == 0 && indicator_calls == 0 && clear_calls == 0);

    result = rt_stdin_read_result(bytes, -1);
    REQUIRE(result.state == DEA_IO_FAILED);
    REQUIRE(result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    result = rt_stdin_read_result(NULL, 1);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    result = rt_stdout_write_result(NULL, 1);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    result = rt_stderr_write_result(bytes, -1);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_INVALID_INPUT);
    REQUIRE(operation_calls == 0 && indicator_calls == 0 && clear_calls == 0);

    reset(stdin); transfer_count = 2;
    result = rt_stdin_read_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_OK && result.count == 2 && bytes[0] == 'x');
    REQUIRE(operation_calls == 1 && observed_entry_errno == 0);
    reset(stdin); transfer_count = 2; fake_error = 1; operation_errno = EINTR;
    result = rt_stdin_read_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_OK && result.count == 2);
    REQUIRE(operation_calls == 1);
    reset(stdin);
    result = rt_stdin_read_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_IO_ERROR);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    reset(stdin); fake_error = 1;
    result = rt_stdin_read_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_IO_ERROR);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    reset(stdin); fake_eof = 1;
    result = rt_stdin_read_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_EOF && result.count == 0);
    REQUIRE(operation_calls == 1);
    reset(stdin); fake_error = 1; operation_errno = EACCES;
    REQUIRE(check_failure(rt_stdin_read_result(bytes, 8), DEA_OS_ERROR_PERMISSION_DENIED,
                          EACCES, DEA_IO_FAILED) == 0);
    reset(stdin); fake_error = 1; operation_errno = EINTR;
    REQUIRE(check_failure(rt_stdin_read_result(bytes, 8), DEA_OS_ERROR_INTERRUPTED,
                          EINTR, DEA_IO_FAILED) == 0);
    reset(stdin); fake_error = 1; operation_errno = EAGAIN;
    REQUIRE(check_failure(rt_stdin_read_result(bytes, 8), DEA_OS_ERROR_WOULD_BLOCK,
                          EAGAIN, DEA_IO_FAILED) == 0);
#ifdef ETIMEDOUT
    reset(stdin); fake_error = 1; operation_errno = ETIMEDOUT;
    REQUIRE(check_failure(rt_stdin_read_result(bytes, 8), DEA_OS_ERROR_TIMED_OUT,
                          ETIMEDOUT, DEA_IO_TIMED_OUT) == 0);
#endif
    reset(stdin); fake_error = 1; fake_eof = 1; operation_errno = EIO;
    REQUIRE(check_failure(rt_stdin_read_result(bytes, 8), DEA_OS_ERROR_IO_ERROR,
                          EIO, DEA_IO_FAILED) == 0);

    reset(stdout); transfer_count = 3; fake_error = 1; operation_errno = EPIPE;
    result = rt_stdout_write_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_OK && result.count == 3 && operation_calls == 1);
    reset(stderr); transfer_count = 1;
    result = rt_stderr_write_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_OK && result.count == 1 && operation_calls == 1);
    reset(stdout);
    result = rt_stdout_write_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_OK && result.count == 0 && operation_calls == 1);
    reset(stderr); fake_error = 1;
    result = rt_stderr_write_result(bytes, 8);
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_IO_ERROR);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    reset(stdout); fake_error = 1; operation_errno = EPIPE;
    REQUIRE(check_failure(rt_stdout_write_result(bytes, 8), DEA_OS_ERROR_BROKEN_PIPE,
                          EPIPE, DEA_IO_FAILED) == 0);
    reset(stderr); fake_error = 1; operation_errno = EINTR;
    REQUIRE(check_failure(rt_stderr_write_result(bytes, 8), DEA_OS_ERROR_INTERRUPTED,
                          EINTR, DEA_IO_FAILED) == 0);
#ifdef ETIMEDOUT
    reset(stdout); fake_error = 1; operation_errno = ETIMEDOUT;
    REQUIRE(check_failure(rt_stdout_write_result(bytes, 8), DEA_OS_ERROR_TIMED_OUT,
                          ETIMEDOUT, DEA_IO_TIMED_OUT) == 0);
#endif
    reset(stdout);
    result = rt_flush_stdout_result();
    REQUIRE(result.state == DEA_IO_OK && result.count == 0 && operation_calls == 1);
    REQUIRE(clear_calls == 1 && observed_entry_errno == 0);
    reset(stderr);
    result = rt_flush_stderr_result();
    REQUIRE(result.state == DEA_IO_OK && result.count == 0 && operation_calls == 1);
    REQUIRE(clear_calls == 1 && observed_entry_errno == 0);
    reset(stdout); flush_result = EOF;
    result = rt_flush_stdout_result();
    REQUIRE(result.state == DEA_IO_FAILED && result.error.kind == DEA_OS_ERROR_IO_ERROR);
    REQUIRE(result.error.domain == DEA_OS_DOMAIN_RUNTIME && result.error.native_code == 0);
    REQUIRE(operation_calls == 1 && clear_calls == 1 && observed_entry_errno == 0);
    REQUIRE(fallback(result.error, "IoError", "Runtime", "0") == 0);
    reset(stdout); flush_result = EOF; operation_errno = EPIPE;
    REQUIRE(check_failure(rt_flush_stdout_result(), DEA_OS_ERROR_BROKEN_PIPE,
                          EPIPE, DEA_IO_FAILED) == 0);
    reset(stderr); flush_result = EOF; operation_errno = EINTR;
    REQUIRE(check_failure(rt_flush_stderr_result(), DEA_OS_ERROR_INTERRUPTED,
                          EINTR, DEA_IO_FAILED) == 0);
#ifdef ETIMEDOUT
    reset(stdout); flush_result = EOF; operation_errno = ETIMEDOUT;
    REQUIRE(check_failure(rt_flush_stdout_result(), DEA_OS_ERROR_TIMED_OUT,
                          ETIMEDOUT, DEA_IO_TIMED_OUT) == 0);
#endif
    return 0;
}

int main(void) {
    REQUIRE(mappings() == 0);
    REQUIRE(streams() == 0);
    return 0;
}
'''


def require_runtime_probes(work: Path, c_compiler: str) -> None:
    """Build the runtime with deterministic stream hooks and verify direct results.

    Args:
        work: Temporary directory for C probe artifacts.
        c_compiler: Explicit selected C compiler.

    Raises:
        AssertionError: Compilation, mapping, or injected stream checks fail.
    """
    source = work / "os_runtime_probe.c"
    source.write_text(probe_source(), encoding="utf-8")
    executable = work / ("os_runtime_probe.exe" if os.name == "nt" else "os_runtime_probe")
    hooks = {
        "FREAD": "injected_read", "FWRITE": "injected_write", "FFLUSH": "injected_flush",
        "FERROR": "injected_error", "FEOF": "injected_eof", "CLEARERR": "injected_clear",
    }
    require_success([
        c_compiler, "-std=c99", f"-I{RUNTIME_ROOT / 'include'}",
        f"-I{RUNTIME_ROOT / 'internal'}",
        *(f"-DDEA_RUNTIME_OS_{name}={symbol}" for name, symbol in hooks.items()),
        str(source), *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm", "-o", str(executable),
    ])
    completed = require_success([str(executable)])
    print(completed.stdout, end="")


def require_public_results(work: Path, c_compiler: str) -> None:
    """Compile each runtime variant once and execute public result scenarios.

    Args:
        work: Temporary directory for compiled fixtures.
        c_compiler: Explicit selected C compiler.

    Raises:
        AssertionError: A compiled public result scenario violates its contract.
    """
    compiler = compiler_path()
    for name, flags in (
        ("checked", []), ("check-basic", ["--check-basic"]),
        ("unchecked", ["--unchecked"]), ("traced", ["--trace-arc", "--trace-memory"]),
    ):
        executable = work / (f"os-{name}.exe" if os.name == "nt" else f"os-{name}")
        require_success([
            str(compiler), "--project-root", str(FIXTURE_ROOT),
            "--c-compiler", c_compiler, *native_driver_args(compiler, c_compiler),
            *flags, "--build", "os_error_main", "-o", str(executable),
        ])
        completed = require_success([str(executable)])
        assert completed.stdout == "os_error_main: PASS\n", completed.stdout
        completed = require_success([str(executable), "read"], input="xy")
        assert completed.stdout == "", completed.stdout
        if name != "traced":
            assert completed.stderr == "", completed.stderr
            completed = require_success([str(executable), "write"])
            assert completed.stdout == "ab", completed.stdout
            assert completed.stderr == "cd", completed.stderr
            for mode, message in (
                ("invalid-read-range", "byte range start must be non-negative"),
                ("invalid-write-range", "byte range must fit within capacity"),
                ("invalid-stderr-range", "byte range count must be non-negative"),
            ):
                failed = subprocess.run(
                    [str(executable), mode], cwd=L1_ROOT, input="", capture_output=True,
                    text=True, check=False,
                )
                assert failed.returncode not in (0, 99), failed.stdout + failed.stderr
                assert message in failed.stderr, failed.stderr


def require_broken_pipe(work: Path, c_compiler: str) -> None:
    """Verify ignored POSIX SIGPIPE reaches direct write and deferred flush errors.

    Args:
        work: Temporary directory for C probe artifacts.
        c_compiler: Explicit selected C compiler.

    Raises:
        AssertionError: Compilation or the native broken-pipe check fails.
    """
    if os.name == "nt":
        print("SKIP POSIX SIGPIPE: native Windows uses a different pipe contract")
        return
    source = work / "os_broken_pipe.c"
    source.write_text(r'''
#include "dea_rt.h"
#include <signal.h>
int main(int argc, char **argv) {
    int endpoints[2];
    dea_byte byte = 'x';
    char output_buffer[4096];
    int deferred = argc == 2 && strcmp(argv[1], "deferred") == 0;
    struct __deaM3sys2osS10RtIoResult result;
    if (pipe(endpoints) != 0) return 1;
    if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) return 2;
    if (!deferred && close(endpoints[0]) != 0) return 3;
    if (dup2(endpoints[1], STDOUT_FILENO) < 0) return 4;
    if (close(endpoints[1]) != 0) return 5;
    if (deferred) {
        if (setvbuf(stdout, output_buffer, _IOFBF, sizeof(output_buffer)) != 0) return 6;
    } else if (setvbuf(stdout, NULL, _IONBF, 0) != 0) {
        return 6;
    }
    result = rt_stdout_write_result(&byte, 1);
    if (deferred) {
        if (result.state != DEA_IO_OK || result.count != 1) return 10;
        if (close(endpoints[0]) != 0) return 11;
        result = rt_flush_stdout_result();
    }
    if (result.state != DEA_IO_FAILED) return 7;
    if (result.error.kind != DEA_OS_ERROR_BROKEN_PIPE) return 8;
    if (result.error.domain != DEA_OS_DOMAIN_ERRNO || result.error.native_code != EPIPE) return 9;
    (void)fclose(stdout);
    return 0;
}
''', encoding="utf-8")
    executable = work / "os_broken_pipe"
    require_success([
        c_compiler, "-std=c99", f"-I{RUNTIME_ROOT / 'include'}",
        f"-I{RUNTIME_ROOT / 'internal'}", str(source),
        *(str(RUNTIME_ROOT / "src" / name) for name in RUNTIME_SOURCES),
        "-lm", "-o", str(executable),
    ])
    require_success([str(executable)])
    require_success([str(executable), "deferred"])


def main() -> int:
    """Exercise native mappings, deterministic failures, and compiled L1 wrappers.

    Returns:
        Zero after all OS runtime scenarios pass.

    Raises:
        AssertionError: A compiler or runtime scenario violates its contract.
    """
    c_compiler = runtime_c_compiler()
    version = require_success([c_compiler, "--version"]).stdout.splitlines()[0]
    print(f"OS runtime compiler: {c_compiler}: {version}")
    with tempfile.TemporaryDirectory(prefix="l1-os-errors-") as temporary:
        work = Path(temporary)
        require_runtime_probes(work, c_compiler)
        require_broken_pipe(work, c_compiler)
        require_public_results(work, c_compiler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
