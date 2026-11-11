/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#ifndef DEA_ENTROPY_SIMULATED_WINDOWS_H
#define DEA_ENTROPY_SIMULATED_WINDOWS_H

/* Only declarations used by the BCrypt adapter and its injected native calls.
 * Fixed-width Windows LONG/ULONG/DWORD remain 32-bit on a 64-bit POSIX host. */
typedef int32_t LONG;
typedef uint32_t ULONG;
typedef uint32_t DWORD;
typedef int BOOL;
typedef void *HANDLE;
typedef void *HMODULE;
typedef const wchar_t *LPCWSTR;
typedef const char *LPCSTR;
typedef intptr_t (*FARPROC)(void);
#define WINAPI
#define TRUE 1
#define ERROR_FILE_NOT_FOUND 2
#define ERROR_INVALID_HANDLE 6
#define ERROR_MOD_NOT_FOUND 126
#define ERROR_PROC_NOT_FOUND 127
extern DWORD entropy_simulated_last_error;
#define GetLastError() entropy_simulated_last_error
#define SetLastError(value) ((void)(entropy_simulated_last_error = (DWORD)(value)))
#endif
