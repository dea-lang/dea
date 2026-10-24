# Filesystem Paths, Mutation, and Directory Traversal

Version: 2026-10-24

`std.fs` provides path operations with direct `std.os::OsError` results, backed by `sys.fs` and the L1 runtime.
`std.dir` owns streaming directory cursors. The signatures and result constructors are listed in
[l1/docs/reference/standard-library.md][stdlib]. Compiler-private support remains separate reference material; this
surface does not change the L0 bootstrap boundary or migrate L2 consumers.

## Path representation and resolution

Empty paths and embedded NUL return `InvalidInput` in the `Runtime` domain with code zero before filesystem calls.
Windows decodes strict UTF-8 and calls wide APIs. Invalid UTF-8 is a captured Win32 error. POSIX passes string bytes
unchanged, including literal backslashes and non-UTF-8 bytes when the filesystem permits them. Host path-length limits
return errors; dynamic output buffers grow instead of truncating. Explicit Windows extended paths are accepted subject
to the host APIs. The library does not promise to bypass host long-path configuration. Managed string allocation and
container allocation retain the stdlib's fatal allocation policy; native temporary allocation failures return
`OutOfMemory`.

`absolute` anchors the spelling to process current-directory state at call time without querying the object. On POSIX,
an initial `/` is absolute; relative input is joined to `getcwd`, preserving dots, repeated separators, and literal
backslashes. On Windows, `GetFullPathNameW` applies host lexical normalization: `C:child` uses drive C's current
directory, `\child` uses the current drive root, drive-rooted paths retain their drive, and UNC paths retain their
server/share root. Both slash spellings are Windows separators. Existence is unnecessary. Concurrent changes to the
process working directory or Windows per-drive state require application synchronization.

`canonicalize` requires an existing path, follows aliases, and returns POSIX `realpath` or the normalized Win32 final
handle path. Windows results retain the `\\?\` prefix, including `\\?\UNC\` for network paths. An unavailable normalized
name, access failure, or missing object is a structured error. Canonical output is a spelling, not an object identity
token, containment proof, or promise that later path operations address the same object.

`same_file` follows both inputs and compares `st_dev`/`st_ino` on POSIX or the native 64-bit volume serial and 128-bit
file ID on Windows. Failed identity queries return failure, including filesystems that cannot supply the requested
Windows identity information. Hard links and followed symbolic links can identify the same object despite different
spellings; different objects remain distinct. No lowercasing, lexical normalization, or canonical-string comparison
substitutes for identity. Lookup races remain possible between the two observations.

## Metadata and symbolic links

`metadata` follows the final symbolic link; `symlink_metadata` inspects the final entry itself. Ancestor components use
normal host following in both operations. For entry operations that do not follow the final link, trailing separators
are removed (except host roots), so a directory link with trailing separators is still inspected/unlinked as a link. All
Windows reparse points are conservatively classified as `Symlink`; the API does not expose their individual tags.

`Metadata` uses nullable signed `long` size and Unix modification seconds, plus normalized `int` nanoseconds. A native
value outside its field's representable range remains unavailable, never narrowed. Windows FILETIME provides 100 ns
precision, including supported pre-epoch values. POSIX uses native nanosecond metadata. Non-regular-object sizes have
host-defined meaning. Legacy `FileInfo` and nullable whole-file convenience APIs remain available; Windows `stat` now
uses the same wide handle metadata. Whole-file strings remain bounded by `INT32_MAX` bytes.

## Mutations and failure behavior

| Operation         | Final link and destination behavior                                                                                                                                                                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create_dir`      | Create one directory; any existing entry is an error. Parent links follow. POSIX mode is `0777` filtered by umask; Windows uses inherited defaults.                                                                                                                                                                  |
| `create_dir_all`  | Create prefixes in order and accept existing followed directories, including directory links. Stop at the first failure without rolling back earlier creations. Dot components use native path semantics; Windows ordinary paths normalize before prefix creation, while verbatim paths preserve literal components. |
| `remove_file`     | Unlink a non-directory entry, including a dangling link or a directory link itself. Reject real directories.                                                                                                                                                                                                         |
| `remove_dir`      | Remove an empty real directory. Reject a final link, including a directory reparse point.                                                                                                                                                                                                                            |
| `remove_dir_all`  | Remove a directory tree, or unlink a final link itself. Reject an ordinary file at the root. Never traverse descendant links/reparse points. Missing roots fail.                                                                                                                                                     |
| `rename`          | Rename entries themselves. Replace existing non-directory destinations using the native rename operation; source/destination type restrictions remain native. POSIX may replace an empty real directory; Windows rejects an existing directory destination.                                                          |
| `replace`         | Rename a non-directory source over a non-directory destination, or into an absent name. Links are entries, so replacing a destination link leaves its target intact. Real directories are rejected.                                                                                                                  |
| `copy_file`       | Follow the source to a regular file, and copy into a new destination. An existing destination, including a link or hard-link alias, fails without overwriting it. Copying across filesystems is allowed.                                                                                                             |
| `set_current_dir` | Follow the directory path and mutate process-global state.                                                                                                                                                                                                                                                           |

`rename` and `replace` use POSIX `rename` or Windows `MoveFileExW(MOVEFILE_REPLACE_EXISTING)` without copy fallback.
Cross-filesystem moves fail with the captured native error (typically `EXDEV`/`ERROR_NOT_SAME_DEVICE`, normalized as
`Other`). Atomicity and visibility are those of the host rename and filesystem; neither operation requests durability.
POSIX same-entry or hard-link aliases are successful no-ops. Windows alias/case-only renames retain the native
operation's behavior; call `same_file` when object identity is the question. Classification checks are observations, not
locks against concurrent source/destination replacement. Applications requiring stable classifications must synchronize
writers.

There is no public atomic no-replace rename in this version. Portable check-then-rename cannot guarantee absence against
a competing writer. Linux `renameat2` and Darwin exclusive-rename capabilities need independent availability and
filesystem-support handling; a future capability API must never silently weaken the guarantee. `copy_file`'s exclusive
creation protects its destination name, but copying is not an atomic rename or atomic publication operation.

Copies process bounded chunks, handle positive partial writes, and stop on interruption or failure. They promise file
bytes, not preserved permissions, times, ACLs, extended attributes, sparse layout, or a consistent snapshot of a
changing source. Read/write/close failures can leave a newly created partial destination; the library does not delete it
during cleanup. Explicit removal lets the caller choose recovery without another path race. Success includes closing the
opened endpoints, and provides no durable-storage guarantee.

Recursive removal stops on the first error in host enumeration order and keeps prior removals. Its Windows root parser
recognizes both DOS device prefixes, case-insensitive UNC markers, server/share component boundaries despite separator
runs, drive roots, and volume GUID roots. Recursive creation/removal rejects unsupported device namespaces (including
`GLOBALROOT`) with runtime `InvalidInput`; it does not infer a root from separator counts. Recursive removal also
rejects ordinary Windows final components consisting only of dots/spaces to avoid normalized root/current-directory
aliases. Traversal deeper than 256 child levels returns runtime `ResourceExhausted`, closing the owned traversal stack.
It rejects a host root or a final `.`/`..` component. POSIX recursion uses owned directory descriptors, relative lookup,
and `O_NOFOLLOW`; Windows holds visited directories without delete sharing, opens final reparse points without following
them, and requests deletion by handle. Operations follow ancestors leading to the selected root; callers must trust and
stabilize those ancestors. Windows denies delete sharing while visiting each directory, preventing its name from being
replaced. This does not prevent a writable directory from becoming a reparse point in place. Callers must stabilize
ancestor and reparse/mount state; concurrent in-place reparse changes, arbitrary renames, and mount changes are outside
these traversal guarantees. Cleanup closes handles even when an earlier operation fails; the first failure takes
precedence over a cleanup failure. No rollback is promised.

## Directory lifetime and explicit materialization

Directory-child joining preserves a bare drive-relative `C:` and existing root separators; opening `C:` enumerates that
drive's current directory rather than changing the input into `C:\`. Ordinary and extended paths with a trailing
separator are accepted according to their host namespace semantics.

`open` follows the directory path. `next` reads one native iterator entry, omits `.`/`..`, and copies the name into an
owned string. Entry order is host-defined, and changes during traversal have host-defined visibility. `file_type` is a
cheap hint: POSIX `DT_UNKNOWN` stays `Unknown` without a metadata fallback. Entries are not stable handles; later
metadata requires an explicit path query and can observe a different object.

`OpenDirResult` owns the cursor returned by `open`; `OpenedDir(dir)` gives access to that cursor. Clean end and captured
iteration failure repeat while it remains alive. Operations on one cursor require caller synchronization. POSIX cursor
descriptors are close-on-exec; Windows search handles are not inherited.

`free_open_dir_result(result)` closes and destroys a successful cursor even when native close fails, returning that
captured `FsFailed` result. For `OpenDirFailed`, it performs no cleanup and returns `FsOk`. The lower-level `close` and
`free_dir` helpers are private. Use a cleanup block when a close failure must be observed:

```dea
with (let result = open(path)) {
    match (result) {
        OpenedDir(dir) => {
            while (true) {
                match (next(dir)) {
                    Entry(entry) => { printl_s(entry.name); }
                    End => { break; }
                    NextFailed(error) => {
                        printl_s(error_message(error));
                        break;
                    }
                }
            }
        }
        OpenDirFailed(error) => { printl_s(error_message(error)); }
    }
} cleanup {
    match (free_open_dir_result(result)) {
        FsOk => {}
        FsFailed(error) => { printl_s(error_message(error)); }
    }
}
```

`read_all` opens, collects, and closes before returning, discarding partial entries on iteration or close failure.
Success is `Entries(entries)`, where `entries` is a `DirEntries*` container bounded by `int` storage limits. Failure is
`EntriesFailed(error)`. `entries_size` reports the count; `entries_get` returns an owning entry copy. The result owns
its collection, released by `free_entries_result(result)`; a failed result needs no cleanup. The lower-level
`free_entries` helper is private. Streaming `next` performs neither sorting nor materialization.

Sorting composes with materialization:

```dea
with (
    let result = entries_sort_default(read_all(path))
    => free_entries_result(result)
) {
    match (result) {
        Entries(entries) => {
            for (let i = 0; i < entries_size(entries); i = i + 1) {
                printl_s(entries_get(entries, i).name);
            }
        }
        EntriesFailed(error) => { printl_s(error_message(error)); }
    }
}
```

These examples import `std.dir`, `std.fs`, `std.io`, and `std.os`. The shorter
`with (let result = open(path) => free_open_dir_result(result))` form also cleans up on early exits but discards the
close result.

`entries_sort(result, compare)` returns an `EntriesResult`; `compare` has type `func(DirEntry, DirEntry) -> int` and
returns a negative value, zero, or a positive value for less, equal, or greater. It receives whole entries, allowing
orders such as directories first or descending names. `entries_sort_default(result)` uses
`std.string::cmp_s(left.name, right.name)`, comparing unsigned name bytes without locale or case folding. Both sort the
successful collection in place and return the same pointer; failed results pass through unchanged without invoking the
comparator. There is no `read_all_sorted` API.

The private iterative max-heapsort uses worst-case `O(n log n)` comparisons, constant auxiliary entry storage, and no
recursion. Equal-key order is unspecified. Comparators must define a consistent ordering and must not mutate or free the
collection. Custom comparison cost is additional to the sorting algorithm's comparison count.

Result copies alias one resource; returning a result from sorting neither copies nor transfers its collection. Each
successful resource requires exactly one cleanup call across all aliases. Cleanup is not idempotent, and L1 does not
enforce a move or invalidate the input binding. Sorting an existing result within its owning `with` scope is safe; the
returned alias may be ignored. All extracted cursor or collection pointers expire after result cleanup. Independently
owned `DirEntry` copies and saved names remain valid; they are not handles to stable filesystem objects.

Do not return a resource from a scope that cleans it up. Resolve fallible arguments before resource creation, or
establish `with` cleanup before subsequent fallible work. An outer cleanup binding does not protect a resource if its
initializer exits before the binding completes.

## Windows path references

The root and normalization distinctions follow Microsoft's [Windows path formats][windows-paths] and
[FindFirstFileW][find-first] contracts. Portable tests exercise the production spelling helpers under both Windows and
POSIX character semantics; they do not establish native Win32 execution. Native-conditional fixtures transport path
bytes as ASCII hexadecimal and decode them inside the test consumers, independently of narrow CRT argument encoding.

[find-first]: https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-findfirstfilew
[stdlib]: standard-library.md
[windows-paths]: https://learn.microsoft.com/dotnet/standard/io/file-path-formats
