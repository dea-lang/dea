# The L0 Standard Library

Version: 2026-09-02

The standard library provides ergonomic L0 modules (`std.*`) and low-level runtime bindings (`sys.*`).

For canonical ownership behavior around `new`/`drop`, ARC strings, and container-specific retain/release patterns, see
[ownership.md](ownership.md).

## Architecture Overview

```
+---------------------------------------------------------+
|                      L0 User Code                       |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
|                      std.* Modules                      |
| array, assert, fs, hashmap, hashset, io, linear_map,    |
| integer, optional, path, rand, string, system, text,    |
| time, unit, vector                                      |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
|                      sys.* Modules                      |
|      hash, rt (runtime API), memory                     |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
| C Runtime (dea_rt.h API; l0_runtime.h implementation)  |
+---------------------------------------------------------+
```

## Module Reference

### `std.assert`

**Imports:** `sys.rt`

| Function | Signature                               | Description                             |
| -------- | --------------------------------------- | --------------------------------------- |
| `assert` | `func(cond: bool, msg: string) -> void` | Aborts with `msg` when `cond` is false. |

### `std.array`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`

| Type/Function | Signature                                                             | Description                                        |
| ------------- | --------------------------------------------------------------------- | -------------------------------------------------- |
| `ArrayBase`   | `struct ArrayBase { capacity: int; element_size: int; data: void*; }` | Untyped fixed-size backing storage.                |
| `ByteArray`   | `struct ByteArray { storage: ArrayBase*; }`                           | Byte-specialized fixed-size array wrapper.         |
| `arr_create`  | `func(element_size: int, length: int) -> ArrayBase*`                  | Allocates and zero-initializes storage.            |
| `arr_check`   | `func(self: ArrayBase*, index: int) -> void`                          | Bounds-check helper (`0 <= index < capacity`).     |
| `arr_resize`  | `func(self: ArrayBase*, new_length: int) -> void`                     | Reallocates backing storage and zero-fills growth. |
| `arr_get`     | `func(self: ArrayBase*, index: int) -> void*`                         | Returns element pointer at index.                  |
| `arr_zap`     | `func(self: ArrayBase*, index: int) -> void`                          | Zeroes one element slot.                           |
| `arr_free`    | `func(self: ArrayBase*) -> void`                                      | Frees backing storage and drops container.         |
| `ba_create`   | `func(length: int) -> ByteArray*`                                     | Allocates a fixed-size byte array.                 |
| `ba_capacity` | `func(self: ByteArray*) -> int`                                       | Returns the number of byte slots.                  |
| `ba_get`      | `func(self: ByteArray*, index: int) -> byte`                          | Returns one byte with bounds checking.             |
| `ba_set`      | `func(self: ByteArray*, index: int, value: byte) -> void`             | Stores one byte with bounds checking.              |
| `ba_zap`      | `func(self: ByteArray*, index: int) -> void`                          | Zeroes one byte slot with bounds checking.         |
| `ba_free`     | `func(self: ByteArray*) -> void`                                      | Frees the wrapper and its backing storage.         |

### `std.fs`

**Imports:** `sys.rt`, `std.unit`

| Type/Function | Signature                                                                                                       | Description                                             |
| ------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `FileInfo`    | `struct FileInfo { exists: bool; is_file: bool; is_dir: bool; size: int?; mtime_sec: int?; mtime_nsec: int?; }` | Public file-metadata wrapper type.                      |
| `exists`      | `func(path: string) -> bool`                                                                                    | Returns whether any filesystem object exists at `path`. |
| `stat`        | `func(path: string) -> FileInfo`                                                                                | Returns path metadata with nullable size/timestamps.    |
| `is_file`     | `func(path: string) -> bool`                                                                                    | Returns whether path exists and is a regular file.      |
| `is_dir`      | `func(path: string) -> bool`                                                                                    | Returns whether path exists and is a directory.         |
| `file_size`   | `func(path: string) -> int?`                                                                                    | Returns file size in bytes when available.              |
| `mtime_sec`   | `func(path: string) -> int?`                                                                                    | Returns modification time in Unix seconds if available. |
| `delete_file` | `func(path: string) -> Unit?`                                                                                   | Deletes a file; returns `null` on failure.              |
| `read_file`   | `func(path: string) -> string?`                                                                                 | Reads entire file; `null` on error.                     |
| `write_file`  | `func(path: string, data: string) -> Unit?`                                                                     | Writes entire file; `null` on error.                    |

All path-taking operations treat an empty path as failure without invoking host filesystem APIs. A whole-file write
succeeds only when both the write and stream close succeed.

### `std.vector`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `std.array`

| Type/Function                | Signature                                                       | Description                                     |
| ---------------------------- | --------------------------------------------------------------- | ----------------------------------------------- |
| `VectorBase`                 | `struct VectorBase { arr: ArrayBase*; length: int; }`           | Untyped growable vector.                        |
| `vec_create`                 | `func(element_size: int, initial_capacity: int) -> VectorBase*` | Creates vector storage.                         |
| `vec_grow`                   | `func(self: VectorBase*) -> void`                               | Ensures capacity and increments length.         |
| `vec_reserve`                | `func(self: VectorBase*, total_capacity: int) -> void`          | Ensures at least requested capacity.            |
| `vec_get`                    | `func(self: VectorBase*, index: int) -> void*`                  | Returns element pointer.                        |
| `vec_push`                   | `func(self: VectorBase*) -> void*`                              | Grows and returns pointer to new slot.          |
| `vec_size`                   | `func(self: VectorBase*) -> int`                                | Returns logical length.                         |
| `vec_capacity`               | `func(self: VectorBase*) -> int`                                | Returns current capacity.                       |
| `vec_clear`                  | `func(self: VectorBase*) -> void`                               | Clears vector and resets backing capacity to 1. |
| `vec_free`                   | `func(self: VectorBase*) -> void`                               | Frees vector storage.                           |
| `vec_push_bytes`             | `func(self: VectorBase*, src: byte*, count: int) -> void`       | Bulk-appends bytes, including logical aliases.  |
| `vec_push_int/byte/bool/ptr` | typed push helpers                                              | Push typed scalar/pointer values.               |
| `vi_sort`                    | `func(self: VectorBase*) -> void`                               | Insertion sort for `int` vectors (ascending).   |
| `StringVector`               | `type StringVector = VectorBase`                                | String-specialized vector alias.                |
| `sv_*`                       | `sv_create/push/get/size/capacity/sort/clear/free`              | String vector API with ARC-aware clear/free.    |

`vec_get` and the typed/string get helpers validate against logical length, never merely reserved capacity.
`vec_push_bytes` accepts a source range wholly within the vector's current logical bytes, including base and interior
aliases when growth moves the backing allocation. A backing-derived range that includes reserved but non-logical bytes
is rejected before reserve, copy, or length mutation. A positive source range that starts below but crosses into the
backing storage is also rejected defensively. Non-positive counts remain no-ops.

### `std.hashmap`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.array`, `std.vector`

| Type/Function                     | Signature                                                                                                                                           | Description                                  |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `StringPtrMap`                    | `struct StringPtrMap { capacity: int; count: int; tomb_count: int; states: ArrayBase*; hashes: ArrayBase*; keys: ArrayBase*; values: ArrayBase*; }` | Open-addressed `string -> void*` map.        |
| `spm_create/create_with_capacity` | constructors                                                                                                                                        | Create map with default or minimum capacity. |
| `spm_put/get/has/remove`          | map ops                                                                                                                                             | Insert/update/lookup/presence/remove.        |
| `spm_size/capacity/clear/free`    | management                                                                                                                                          | Size, capacity, clear entries, free map.     |
| `spm_keys`                        | `func(self: StringPtrMap*) -> StringVector*`                                                                                                        | Returns keys as new string vector.           |
| `spm_slot_occupied/key/value`     | iteration helpers                                                                                                                                   | Slot-level iteration support.                |
| `StringIntMap`                    | `struct StringIntMap { capacity: int; count: int; tomb_count: int; states: ArrayBase*; hashes: ArrayBase*; keys: ArrayBase*; values: ArrayBase*; }` | Open-addressed `string -> int` map.          |
| `sim_create/create_with_capacity` | constructors                                                                                                                                        | Create map with default or minimum capacity. |
| `sim_put/get/has/remove`          | map ops                                                                                                                                             | Insert/update/lookup/presence/remove.        |
| `sim_size/capacity/clear/free`    | management                                                                                                                                          | Size, capacity, clear entries, free map.     |
| `sim_keys`                        | `func(self: StringIntMap*) -> StringVector*`                                                                                                        | Returns keys as new string vector.           |
| `sim_slot_occupied/key/value`     | iteration helpers                                                                                                                                   | Slot-level iteration support.                |

### `std.hashset`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.array`, `std.vector`

| Type/Function                    | Signature                                                                                                                    | Description                                  |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `StringSet`                      | `struct StringSet { capacity: int; count: int; tomb_count: int; states: ArrayBase*; hashes: ArrayBase*; keys: ArrayBase*; }` | Open-addressed set of strings.               |
| `ss_create/create_with_capacity` | constructors                                                                                                                 | Create set with default or minimum capacity. |
| `ss_add`                         | `func(self: StringSet*, key: string) -> bool`                                                                                | Adds key; returns false if already present.  |
| `ss_has/remove`                  | set ops                                                                                                                      | Presence check and removal.                  |
| `ss_size/capacity/clear/free`    | management                                                                                                                   | Size, capacity, clear entries, free set.     |
| `ss_to_vector`                   | `func(self: StringSet*) -> StringVector*`                                                                                    | Returns elements as new vector.              |
| `ss_slot_occupied/key`           | iteration helpers                                                                                                            | Slot-level iteration support.                |

### `std.linear_map`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.vector`

| Type/Function           | Signature                                                                        | Description                                 |
| ----------------------- | -------------------------------------------------------------------------------- | ------------------------------------------- |
| `LinearMapBase`         | `struct LinearMapBase { entries: VectorBase*; key_size: int; value_size: int; }` | Generic byte-comparison linear map storage. |
| `lm_create/free/len`    | base lifecycle                                                                   | Create, free, and query length.             |
| `lm_set/get/remove`     | base ops                                                                         | Set/get/remove key-value by raw key bytes.  |
| `lm_contains_key/value` | base queries                                                                     | Presence checks by key/value bytes.         |
| `StringStringLinearMap` | `struct StringStringLinearMap { base: LinearMapBase*; }`                         | `string -> string` specialization.          |
| `sslm_*`                | `create/free/len/set/get/contains/remove/key_at/value_at`                        | ARC-aware string map API.                   |
| `IntStringLinearMap`    | `struct IntStringLinearMap { base: LinearMapBase*; }`                            | `int -> string` specialization.             |
| `islm_*`                | `create/free/len/set/get/contains/remove/key_at/value_at`                        | ARC-aware int/string map API.               |

### `std.io`

**Imports:** `sys.rt`, `sys.memory`, `std.array`, `std.assert`, `std.unit`

`std.io` classifies I/O success/failure from direct runtime return values (optional/boolean/sentinel results).

| Function            | Signature                                                | Description                                                                         |
| ------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `read_line`         | `func() -> string?`                                      | Reads line from stdin; `null` on EOF/error.                                         |
| `read_char`         | `func() -> int?`                                         | Reads one byte as int; `null` on EOF/error.                                         |
| `read_char_or_eof`  | `func() -> int`                                          | Reads one byte; returns `-1` on EOF/error.                                          |
| `read_stdin_some`   | `func(buf: ByteArray*, start: int, count: int) -> int?`  | Reads raw bytes into one checked subrange; `0` means EOF and `null` means error.    |
| `write_stdout_some` | `func(buf: ByteArray*, start: int, count: int) -> int?`  | Writes bytes from one checked subrange to stdout.                                   |
| `write_stderr_some` | `func(buf: ByteArray*, start: int, count: int) -> int?`  | Writes bytes from one checked subrange to stderr.                                   |
| `write_stdout_all`  | `func(buf: ByteArray*, start: int, count: int) -> Unit?` | Writes exactly `count` bytes from one checked subrange to stdout or returns `null`. |
| `write_stderr_all`  | `func(buf: ByteArray*, start: int, count: int) -> Unit?` | Writes exactly `count` bytes from one checked subrange to stderr or returns `null`. |
| `flush_stdout`      | `func() -> void`                                         | Flushes stdout.                                                                     |
| `flush_stderr`      | `func() -> void`                                         | Flushes stderr.                                                                     |
| `printl`            | `func() -> void`                                         | Prints newline to stdout.                                                           |
| `print_s`           | `func(s: string) -> void`                                | Prints string to stdout.                                                            |
| `print_i`           | `func(x: int) -> void`                                   | Prints int to stdout.                                                               |
| `print_b`           | `func(x: bool) -> void`                                  | Prints bool to stdout.                                                              |
| `printl_s`          | `func(s: string) -> void`                                | Prints string + newline to stdout.                                                  |
| `printl_i`          | `func(x: int) -> void`                                   | Prints int + newline to stdout.                                                     |
| `printl_b`          | `func(x: bool) -> void`                                  | Prints bool + newline to stdout.                                                    |
| `print_ss`          | `func(s1: string, s2: string) -> void`                   | Prints two values separated by space.                                               |
| `print_si`          | `func(s: string, x: int) -> void`                        | Prints two values separated by space.                                               |
| `print_sb`          | `func(s: string, b: bool) -> void`                       | Prints two values separated by space.                                               |
| `print_is`          | `func(x: int, s: string) -> void`                        | Prints two values separated by space.                                               |
| `print_ii`          | `func(x1: int, x2: int) -> void`                         | Prints two values separated by space.                                               |
| `print_ib`          | `func(x: int, b: bool) -> void`                          | Prints two values separated by space.                                               |
| `print_bs`          | `func(b: bool, s: string) -> void`                       | Prints two values separated by space.                                               |
| `print_bi`          | `func(b: bool, x: int) -> void`                          | Prints two values separated by space.                                               |
| `print_bb`          | `func(b1: bool, b2: bool) -> void`                       | Prints two values separated by space.                                               |
| `printl_ss`         | `func(s1: string, s2: string) -> void`                   | `print_ss` + newline.                                                               |
| `printl_si`         | `func(s: string, x: int) -> void`                        | `print_si` + newline.                                                               |
| `printl_sb`         | `func(s: string, b: bool) -> void`                       | `print_sb` + newline.                                                               |
| `printl_is`         | `func(x: int, s: string) -> void`                        | `print_is` + newline.                                                               |
| `printl_ii`         | `func(x1: int, x2: int) -> void`                         | `print_ii` + newline.                                                               |
| `printl_ib`         | `func(x: int, b: bool) -> void`                          | `print_ib` + newline.                                                               |
| `printl_bs`         | `func(b: bool, s: string) -> void`                       | `print_bs` + newline.                                                               |
| `printl_bi`         | `func(b: bool, x: int) -> void`                          | `print_bi` + newline.                                                               |
| `printl_bb`         | `func(b1: bool, b2: bool) -> void`                       | `print_bb` + newline.                                                               |
| `err_printl`        | `func() -> void`                                         | Prints newline to stderr.                                                           |
| `err_print_s`       | `func(s: string) -> void`                                | Prints string to stderr.                                                            |
| `err_print_i`       | `func(x: int) -> void`                                   | Prints int to stderr.                                                               |
| `err_print_b`       | `func(x: bool) -> void`                                  | Prints bool to stderr.                                                              |
| `err_printl_s`      | `func(s: string) -> void`                                | Prints string + newline to stderr.                                                  |
| `err_printl_i`      | `func(x: int) -> void`                                   | Prints int + newline to stderr.                                                     |
| `err_printl_b`      | `func(x: bool) -> void`                                  | Prints bool + newline to stderr.                                                    |
| `err_print_ss`      | `func(s1: string, s2: string) -> void`                   | Prints two values separated by space.                                               |
| `err_print_si`      | `func(s: string, x: int) -> void`                        | Prints two values separated by space.                                               |
| `err_print_sb`      | `func(s: string, b: bool) -> void`                       | Prints two values separated by space.                                               |
| `err_print_is`      | `func(x: int, s: string) -> void`                        | Prints two values separated by space.                                               |
| `err_print_ii`      | `func(x1: int, x2: int) -> void`                         | Prints two values separated by space.                                               |
| `err_print_ib`      | `func(x: int, b: bool) -> void`                          | Prints two values separated by space.                                               |
| `err_print_bs`      | `func(b: bool, s: string) -> void`                       | Prints two values separated by space.                                               |
| `err_print_bi`      | `func(b: bool, x: int) -> void`                          | Prints two values separated by space.                                               |
| `err_print_bb`      | `func(b1: bool, b2: bool) -> void`                       | Prints two values separated by space.                                               |

### `std.integer`

**Imports:** `std.assert`

Shared integer helper module. Floating-point helpers stay out of `std.integer`.

| Function      | Signature                               | Description                                                                                               |
| ------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `emod`        | `func(a: int, b: int) -> int`           | Euclidean modulo. Requires `b > 0`; always returns a result in `[0, b)`.                                  |
| `ediv`        | `func(a: int, b: int) -> int`           | Euclidean quotient paired with `emod`. Requires `b > 0`.                                                  |
| `div_floor`   | `func(a: int, b: int) -> int`           | Mathematical floor quotient. Requires `b != 0` and a representable result (excluding `int_min() / -1`).   |
| `div_ceil`    | `func(a: int, b: int) -> int`           | Mathematical ceiling quotient. Requires `b != 0` and a representable result (excluding `int_min() / -1`). |
| `min`         | `func(a: int, b: int) -> int`           | Returns the smaller operand.                                                                              |
| `max`         | `func(a: int, b: int) -> int`           | Returns the larger operand.                                                                               |
| `clamp`       | `func(x: int, lo: int, hi: int) -> int` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                          |
| `sign`        | `func(x: int) -> int`                   | Returns `-1`, `0`, or `1` based on the sign of `x`.                                                       |
| `is_even`     | `func(x: int) -> bool`                  | Returns whether `x` is evenly divisible by 2.                                                             |
| `is_odd`      | `func(x: int) -> bool`                  | Returns whether `x` is not evenly divisible by 2.                                                         |
| `is_multiple` | `func(a: int, b: int) -> bool`          | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                        |
| `abs`         | `func(x: int) -> int?`                  | Absolute value. Returns `null` when the mathematical result is not representable as `int`.                |
| `gcd`         | `func(a: int, b: int) -> int?`          | Non-negative greatest common divisor. Returns `null` when the mathematical result is not representable.   |
| `lcm`         | `func(a: int, b: int) -> int?`          | Non-negative least common multiple. Returns `null` on overflow or non-representable results.              |
| `pow`         | `func(base: int, exp: int) -> int?`     | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                         |
| `isqrt`       | `func(x: int) -> int?`                  | Floor integer square root. Returns `null` when `x < 0`.                                                   |
| `align_down`  | `func(x: int, align: int) -> int?`      | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.     |
| `align_up`    | `func(x: int, align: int) -> int?`      | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.       |
| `is_aligned`  | `func(x: int, align: int) -> bool`      | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                                  |

### `std.optional`

**Imports:** `std.assert`

| Function      | Signature                                       | Description                           |
| ------------- | ----------------------------------------------- | ------------------------------------- |
| `unwrap_or_s` | `func(opt: string?, default: string) -> string` | Returns value or default.             |
| `unwrap_or_i` | `func(opt: int?, default: int) -> int`          | Returns value or default.             |
| `unwrap_or_b` | `func(opt: bool?, default: bool) -> bool`       | Returns value or default.             |
| `expect_s`    | `func(opt: string?, msg: string) -> string`     | Returns value or aborts with message. |
| `expect_i`    | `func(opt: int?, msg: string) -> int`           | Returns value or aborts with message. |
| `expect_b`    | `func(opt: bool?, msg: string) -> bool`         | Returns value or aborts with message. |

### `std.path`

**Imports:** `std.string`, `std.text`

| Function        | Signature                                   | Description                                                    |
| --------------- | ------------------------------------------- | -------------------------------------------------------------- |
| `is_sep`        | `func(c: byte) -> bool`                     | Returns whether byte is `/` or `\\`.                           |
| `is_absolute`   | `func(path: string) -> bool`                | Supports POSIX absolute paths and Windows drive roots.         |
| `has_parent`    | `func(path: string) -> bool`                | Returns whether the path contains a separator.                 |
| `basename`      | `func(path: string) -> string`              | Returns final path component with trailing separators trimmed. |
| `parent`        | `func(path: string) -> string`              | Returns parent directory or `.` when no parent exists.         |
| `stem`          | `func(path: string) -> string`              | Removes the final extension from the basename when present.    |
| `join`          | `func(root: string, rel: string) -> string` | Appends one path separator between `root` and `rel`.           |
| `has_extension` | `func(path: string, ext: string) -> bool`   | Matches the final basename extension, with or without `.`.     |

### `std.rand`

**Imports:** `sys.rt`

| Function         | Signature                             | Description                                           |
| ---------------- | ------------------------------------- | ----------------------------------------------------- |
| `rand_seed`      | `func(seed: int) -> void`             | Seeds RNG. `0` selects time-based seed.               |
| `rand_int`       | `func(max: int) -> int`               | Returns random int in `[0, max)`.                     |
| `rand_int_range` | `func(min: int, max: int) -> int`     | Returns random int in `[min, max)`.                   |
| `rand_bool`      | `func() -> bool`                      | Returns random bool.                                  |
| `rand_dice`      | `func(sides: int, rolls: int) -> int` | Rolls `rolls` dice of `sides` sides and sums results. |

### `std.string`

**Imports:** `sys.rt`, `std.assert`

| Function        | Signature                                                 | Description                                                              |
| --------------- | --------------------------------------------------------- | ------------------------------------------------------------------------ |
| `len_s`         | `func(s: string) -> int`                                  | Returns string byte length.                                              |
| `is_empty_s`    | `func(s: string) -> bool`                                 | Returns whether string length is zero.                                   |
| `char_at_s`     | `func(s: string, index: int) -> byte`                     | Returns byte at index.                                                   |
| `eq_s`          | `func(a: string, b: string) -> bool`                      | Compares strings for equality.                                           |
| `cmp_s`         | `func(a: string, b: string) -> int`                       | Compares strings lexicographically (`<0`, `0`, `>0`).                    |
| `concat_s`      | `func(a: string, b: string) -> string`                    | Concatenates strings (equivalent to `+`).                                |
| `slice_s`       | `func(s: string, start: int, end: int) -> string`         | Returns substring `[start, end)`.                                        |
| `byte_to_s`     | `func(b: byte) -> string`                                 | Creates one-character string from a byte value.                          |
| `bytes_to_s`    | `func(bytes: byte*, len: int) -> string`                  | Creates string from byte buffer.                                         |
| `find_s`        | `func(haystack: string, needle: string) -> int`           | Returns first match index or `-1`.                                       |
| `find_last_s`   | `func(haystack: string, needle: string) -> int`           | Returns last match index or `-1` (`len_s(haystack)` for empty needle).   |
| `find_from_s`   | `func(haystack: string, needle: string, pos: int) -> int` | Returns first match index at/after `pos`, or `-1`. Requires `pos >= 0`.  |
| `contains_s`    | `func(haystack: string, needle: string) -> bool`          | Returns whether `needle` occurs in `haystack`.                           |
| `starts_with_s` | `func(s: string, prefix: string) -> bool`                 | Returns whether `s` starts with `prefix`.                                |
| `ends_with_s`   | `func(s: string, suffix: string) -> bool`                 | Returns whether `s` ends with `suffix`.                                  |
| `is_space`      | `func(c: byte) -> bool`                                   | Whitespace check (`' '`, `'\n'`, `'\t'`, `'\r'`).                        |
| `is_digit`      | `func(c: byte) -> bool`                                   | Decimal digit check (`'0'..'9'`).                                        |
| `is_digit_base` | `func(c: byte, base: int) -> bool`                        | Valid digit check for base `2..16`.                                      |
| `is_alpha`      | `func(c: byte) -> bool`                                   | ASCII alphabetic check.                                                  |
| `is_alnum`      | `func(c: byte) -> bool`                                   | ASCII alphanumeric check.                                                |
| `to_digit`      | `func(c: byte) -> int`                                    | Converts decimal ASCII digit byte to integer value.                      |
| `to_digit_base` | `func(c: byte, base: int) -> int?`                        | Converts base `2..16` digit byte to integer value or `null`.             |
| `to_upper`      | `func(c: byte) -> byte`                                   | Uppercases ASCII letter; returns input otherwise.                        |
| `to_lower`      | `func(c: byte) -> byte`                                   | Lowercases ASCII letter; returns input otherwise.                        |
| `trim_s`        | `func(s: string) -> string`                               | Trims leading/trailing ASCII whitespace (`' '`, `'\n'`, `'\t'`, `'\r'`). |

### `std.system`

**Imports:** `sys.rt`

| Function  | Signature                           | Description                                                         |
| --------- | ----------------------------------- | ------------------------------------------------------------------- |
| `exit`    | `func(code: int) -> void`           | Exits program with status code.                                     |
| `env_get` | `func(var_name: string) -> string?` | Returns environment variable or `null`.                             |
| `argc`    | `func() -> int`                     | Returns command-line argument count.                                |
| `get_pid` | `func() -> int`                     | Returns the current process identifier.                             |
| `argv`    | `func(index: int) -> string`        | Returns command-line argument string at index.                      |
| `abort`   | `func(message: string) -> void`     | Aborts program with message.                                        |
| `errno`   | `func() -> int`                     | Returns runtime error number.                                       |
| `system`  | `func(cmd: string) -> int`          | Executes command in shell and returns normalized child exit status. |

### `std.text`

**Imports:** `std.string`, `std.integer`, `std.assert`, `std.vector`

| Type/Function                                       | Signature                                                                                           | Description                                                                                               |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `StringBuffer`                                      | `struct StringBuffer { parts: StringVector*; size: int; }`                                          | String-part buffer with cached total size.                                                                |
| `sb_*`                                              | `create/append/append_int/append_byte/to_string/size/free`                                          | String buffer API.                                                                                        |
| `CharBuffer`                                        | `struct CharBuffer { chars: VectorBase*; }`                                                         | Byte-backed buffer for incremental string assembly.                                                       |
| `cb_*`                                              | `create/capacity/size/reserve/append/append_s/append_slice/append_int/reverse/to_string/clear/free` | Char buffer API.                                                                                          |
| `to_upper_s/to_lower_s`                             | case helpers                                                                                        | Convert full string case.                                                                                 |
| `repeat_s/reverse_s`                                | string helpers                                                                                      | Repeat or reverse string content.                                                                         |
| `split_s`                                           | `func(s: string, sep: string) -> StringVector*`                                                     | Splits by non-empty separator and keeps empty tokens. Caller owns result (`sv_free`).                     |
| `lines_s`                                           | `func(s: string) -> StringVector*`                                                                  | Splits on `\n`, strips trailing `\r` per line. Caller owns result (`sv_free`).                            |
| `join_s`                                            | `func(parts: StringVector*, sep: string) -> string`                                                 | Joins vector elements with separator.                                                                     |
| `replace_s`                                         | `func(s: string, old: string, replacement: string) -> string`                                       | Replaces all non-overlapping matches of non-empty `old` with `replacement`.                               |
| `int_to_string_base`                                | `func(value: int, base: int) -> string`                                                             | Base conversion for signed ints (`2..16`).                                                                |
| `int_to_string/int_to_hex_string/int_to_bin_string` | format helpers                                                                                      | Decimal, hex, and binary formatting helpers.                                                              |
| `bool_to_string/string_to_bool`                     | `func(bool) -> string`, `func(string) -> bool?`                                                     | Converts booleans to `"true"`/`"false"` and parses strict lowercase boolean text.                         |
| `byte_to_string/byte_to_string_base`                | `func(byte) -> string`, `func(byte, base: int) -> string`                                           | Numeric byte formatting (decimal or base `2..16`).                                                        |
| `string_to_int`                                     | `func(s: string) -> int?`                                                                           | Parses decimal signed integer text; returns `null` on invalid input or 32-bit overflow/underflow.         |
| `string_to_int_base`                                | `func(s: string, base: int) -> int?`                                                                | Parses signed integer text in base `2..16`; returns `null` on invalid input or 32-bit overflow/underflow. |
| `string_to_byte/string_to_byte_base`                | `func(s: string) -> byte?`, `func(s: string, base: int) -> byte?`                                   | Parses numeric byte text; returns `null` on invalid input or out-of-range values (`0..255`).              |

### `std.time`

**Imports:** `sys.rt`, `std.integer`

| Type/Function            | Signature                                                                                                                                                                   | Description                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `WallTime`               | `struct WallTime { sec: int; nsec: int; }`                                                                                                                                  | Unix wall-clock snapshot with nanosecond fraction.             |
| `MonotonicTime`          | `struct MonotonicTime { sec: int; nsec: int; }`                                                                                                                             | Monotonic-clock snapshot with nanosecond fraction.             |
| `Duration`               | `struct Duration { sec: int; nsec: int; }`                                                                                                                                  | Non-negative normalized duration (`0 <= nsec < 1e9`).          |
| `DateTime`               | `struct DateTime { year: int; month: int; day: int; hour: int; minute: int; second: int; nanosecond: int; weekday: int; yearday: int; utc_offset_sec: int; is_dst: bool; }` | Calendar breakdown (date/time, weekday, yearday, offset, DST). |
| `wall_now`               | `func() -> WallTime?`                                                                                                                                                       | Captures current wall-clock time.                              |
| `monotonic_supported`    | `func() -> bool`                                                                                                                                                            | Returns monotonic clock capability.                            |
| `monotonic_now`          | `func() -> MonotonicTime?`                                                                                                                                                  | Captures current monotonic time when supported.                |
| `monotonic_diff`         | `func(start: MonotonicTime, end: MonotonicTime) -> Duration?`                                                                                                               | Returns `end - start` or `null` for invalid/reversed inputs.   |
| `wall_to_utc_datetime`   | `func(t: WallTime) -> DateTime?`                                                                                                                                            | Converts wall time to UTC calendar representation.             |
| `wall_to_local_datetime` | `func(t: WallTime) -> DateTime?`                                                                                                                                            | Converts wall time to local calendar representation.           |
| `utc_now_datetime`       | `func() -> DateTime?`                                                                                                                                                       | Convenience wrapper for current UTC calendar time.             |
| `local_now_datetime`     | `func() -> DateTime?`                                                                                                                                                       | Convenience wrapper for current local calendar time.           |

### `std.unit`

| Type/Function | Signature         | Description                     |
| ------------- | ----------------- | ------------------------------- |
| `Unit`        | `struct Unit {}`  | Unit type.                      |
| `unit`        | `func() -> Unit`  | Returns unit value.             |
| `present`     | `func() -> Unit?` | Returns non-null optional unit. |

### `sys.hash`

Low-level runtime FFI for hashing raw values and pointers. Uses the SipHash-1-3 algorithm. Used by `std.hashmap` and
`std.hashset` for hash calculations. Equal optional scalar values hash identically across the C ABI: inactive payload
bytes and wrapper padding do not contribute. Type tags and optional-state tags are intentional semantic inputs.
Optional-string absence uses a distinct input domain from every present optional-string value, including `""`. Raw-data
hashes require a non-null pointer even for a zero-byte extent, but a zero-byte hash reads no payload. Pointer hashing
rejects null, including an empty optional pointer. Equal semantic values produce equal hashes, and repeated calls are
deterministic within one runtime process. Ordinary 32-bit collisions remain possible and do not imply equality. Exact
runtime hash values are not stable identifiers and must not be persisted or used as compatibility fingerprints; hash
values and accidental collisions are not API guarantees across runtime versions, implementations, keys, or process
executions.

### `sys.rt`

Low-level runtime FFI for strings, I/O, process/system, time, and errors. Also defines `RtTimeParts`
(`struct RtTimeParts { sec: int; nsec: int; }`) and `RtFileInfo`
(`struct RtFileInfo { exists: bool; is_file: bool; is_dir: bool; size: int?; mtime_sec: int?; mtime_nsec: int?; }`).

### `sys.memory`

Low-level raw memory FFI. Misuse can cause undefined behavior.

## FFI Inventory (`extern func`)

All `extern func` symbols exposed to L0 from stdlib modules are listed here.

The same declarations are available to additional C translation units through the declaration-only public header
`compiler/shared/runtime/dea_rt.h`, introduced for L0 2.1.0. Foreign C should use its `dea_*` types and public `rt_*`
functions and must not include the implementation-bearing `l0_runtime.h`.

The exact source-compatible subset with L1 is:

- every scalar `dea_*` type and `dea_string`;
- `dea_opt_bool`, `dea_opt_byte`, `dea_opt_int`, and `dea_opt_string`;
- `DEA_STRING_*` and `DEA_OPT_STRING_*` value macros;
- identically typed common `rt_*` functions in the string, process/environment, scalar-time, file-content, stream/I/O,
  memory, and hash groups below.

`rt_time_unix`, `rt_time_monotonic`, and `rt_file_info` are not portable C calls across levels because their record tags
are level-mangled. L1's wider optional types and unsigned/long/floating-point print functions are not L0 APIs. The
common subset promises source compatibility and common-type representation, not that L0 and L1 objects or runtime
binaries can be mixed. L0-specific `l0_*` aliases remain supported; `_rt_*` helpers, tracker internals, build macros,
and packaging are private or level-specific.

### Declared in `sys.rt` (42)

| Function                      | Signature                                         | Description                                                                                                |
| ----------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `rt_string_get`               | `func(s: string, index: int) -> byte`             | Returns one byte from a string.                                                                            |
| `rt_string_bytes_ptr`         | `func(s: string) -> byte*`                        | Returns a pointer to runtime-managed string bytes; checked reads are valid, checked writes and drops fail. |
| `rt_strlen`                   | `func(str: string) -> int`                        | Returns string byte length.                                                                                |
| `rt_string_equals`            | `func(a: string, b: string) -> bool`              | Compares strings for equality.                                                                             |
| `rt_string_compare`           | `func(a: string, b: string) -> int`               | Compares strings lexicographically.                                                                        |
| `rt_string_concat`            | `func(a: string, b: string) -> string`            | Concatenates two strings.                                                                                  |
| `rt_string_slice`             | `func(s: string, start: int, end: int) -> string` | Returns a string slice by byte range.                                                                      |
| `rt_string_from_byte_array`   | `func(bytes: byte*, len: int) -> string`          | Creates a string from raw bytes.                                                                           |
| `rt_string_from_byte`         | `func(b: byte) -> string`                         | Creates a one-byte string.                                                                                 |
| `rt_string_retain`            | `func(s: string) -> void`                         | Increments heap-string refcount.                                                                           |
| `rt_string_release`           | `func(s: string) -> void`                         | Decrements heap-string refcount.                                                                           |
| `rt_read_file_all`            | `func(path: string) -> string?`                   | Reads a nonempty path; returns `null` on failure.                                                          |
| `rt_write_file_all`           | `func(path: string, data: string) -> bool`        | Writes a nonempty path; returns false on write or close failure.                                           |
| `rt_flush_stdout`             | `func() -> void`                                  | Flushes standard output.                                                                                   |
| `rt_flush_stderr`             | `func() -> void`                                  | Flushes standard error.                                                                                    |
| `rt_print`                    | `func(s: string) -> void`                         | Prints a string to stdout.                                                                                 |
| `rt_print_stderr`             | `func(s: string) -> void`                         | Prints a string to stderr.                                                                                 |
| `rt_println`                  | `func() -> void`                                  | Prints a newline to stdout.                                                                                |
| `rt_println_stderr`           | `func() -> void`                                  | Prints a newline to stderr.                                                                                |
| `rt_print_int`                | `func(x: int) -> void`                            | Prints an int to stdout.                                                                                   |
| `rt_print_int_stderr`         | `func(x: int) -> void`                            | Prints an int to stderr.                                                                                   |
| `rt_print_bool`               | `func(x: bool) -> void`                           | Prints a bool to stdout.                                                                                   |
| `rt_print_bool_stderr`        | `func(x: bool) -> void`                           | Prints a bool to stderr.                                                                                   |
| `rt_read_line`                | `func() -> string?`                               | Reads one line from stdin.                                                                                 |
| `rt_read_char`                | `func() -> int`                                   | Reads one byte from stdin.                                                                                 |
| `rt_abort`                    | `func(message: string) -> void`                   | Aborts execution with a message.                                                                           |
| `rt_exit`                     | `func(code: int) -> void`                         | Exits the current process.                                                                                 |
| `rt_srand`                    | `func(seed: int) -> void`                         | Seeds the runtime RNG.                                                                                     |
| `rt_rand`                     | `func(max: int) -> int`                           | Returns a random int below `max`.                                                                          |
| `rt_errno`                    | `func() -> int`                                   | Returns the current errno value.                                                                           |
| `rt_get_env_var`              | `func(name: string) -> string?`                   | Reads an environment variable.                                                                             |
| `rt_get_argc`                 | `func() -> int`                                   | Returns process argument count.                                                                            |
| `rt_get_pid`                  | `func() -> int`                                   | Returns the current process id.                                                                            |
| `rt_get_argv`                 | `func(i: int) -> string`                          | Returns one process argument.                                                                              |
| `rt_time_unix`                | `func(out: RtTimeParts*) -> bool`                 | Captures wall-clock time.                                                                                  |
| `rt_time_monotonic`           | `func(out: RtTimeParts*) -> bool`                 | Captures monotonic time.                                                                                   |
| `rt_time_monotonic_supported` | `func() -> bool`                                  | Reports monotonic-clock availability.                                                                      |
| `rt_time_local_offset_sec`    | `func(unix_sec: int) -> int?`                     | Looks up local UTC offset.                                                                                 |
| `rt_time_local_is_dst`        | `func(unix_sec: int) -> bool?`                    | Looks up local DST state.                                                                                  |
| `rt_system`                   | `func(cmd: string) -> int`                        | Runs a shell command.                                                                                      |
| `rt_file_info`                | `func(path: string) -> RtFileInfo`                | Returns stat-like file metadata.                                                                           |
| `rt_delete_file`              | `func(path: string) -> bool`                      | Deletes a nonempty path; returns false on failure.                                                         |

### Declared in `sys.memory` (13)

These are unsafe raw-memory primitives. `rt_free` and `rt_realloc` accept only raw allocations; `new` allocations use
`drop`. Foreign registration supplies checked lifetime/range information without transferring ownership or authorizing
runtime release.

| Function                | Signature                                                         | Description                                      |
| ----------------------- | ----------------------------------------------------------------- | ------------------------------------------------ |
| `rt_alloc`              | `func(bytes: int) -> void*?`                                      | Allocates raw heap memory.                       |
| `rt_realloc`            | `func(ptr: void*?, new_bytes: int) -> void*?`                     | Resizes raw heap memory.                         |
| `rt_free`               | `func(ptr: void*?) -> void`                                       | Frees raw heap memory.                           |
| `rt_calloc`             | `func(count: int, elem_size: int) -> void*?`                      | Allocates zeroed raw memory.                     |
| `rt_register_foreign`   | `func(ptr: void*, bytes: int, read_only: bool) -> void`           | Registers externally owned storage for checks.   |
| `rt_unregister_foreign` | `func(ptr: void*) -> void`                                        | Invalidates a foreign registration without free. |
| `rt_memcpy`             | `func(dest: void*, src: void*, bytes: int) -> void*`              | Copies raw bytes.                                |
| `rt_memset`             | `func(dest: void*, value: int, bytes: int) -> void*`              | Fills raw bytes.                                 |
| `rt_memcmp`             | `func(a: void*, b: void*, bytes: int) -> int`                     | Compares raw bytes.                              |
| `rt_array_element`      | `func(array_data: void*, element_size: int, index: int) -> void*` | Computes an element pointer.                     |
| `rt_stdin_read`         | `func(buf: byte*?, capacity: int) -> int`                         | Reads raw bytes from stdin.                      |
| `rt_stdout_write`       | `func(buf: byte*?, len: int) -> int`                              | Writes raw bytes to stdout.                      |
| `rt_stderr_write`       | `func(buf: byte*?, len: int) -> int`                              | Writes raw bytes to stderr.                      |

### Declared in `sys.hash` (11)

These are runtime-backed hash externs declared directly in `sys.hash`.

| Function             | Signature                             | Description                                               |
| -------------------- | ------------------------------------- | --------------------------------------------------------- |
| `rt_hash_bool`       | `func(value: bool) -> int`            | Hashes a bool value.                                      |
| `rt_hash_byte`       | `func(value: byte) -> int`            | Hashes a byte value.                                      |
| `rt_hash_int`        | `func(value: int) -> int`             | Hashes an int value.                                      |
| `rt_hash_string`     | `func(value: string) -> int`          | Hashes a string value.                                    |
| `rt_hash_data`       | `func(data: void*, size: int) -> int` | Hashes non-null raw byte data.                            |
| `rt_hash_opt_bool`   | `func(opt: bool?) -> int`             | Hashes a canonical optional bool.                         |
| `rt_hash_opt_byte`   | `func(opt: byte?) -> int`             | Hashes a canonical optional byte.                         |
| `rt_hash_opt_int`    | `func(opt: int?) -> int`              | Hashes a canonical optional int.                          |
| `rt_hash_opt_string` | `func(opt: string?) -> int`           | Hashes contents with optional-presence domain separation. |
| `rt_hash_ptr`        | `func(ptr: void*) -> int`             | Hashes a non-null raw pointer value.                      |
| `rt_hash_opt_ptr`    | `func(opt: void*?) -> int`            | Hashes a present optional raw pointer.                    |
