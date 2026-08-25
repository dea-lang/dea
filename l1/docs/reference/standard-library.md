# The L1 Standard Library

Version: 2026-08-25

The standard library provides ergonomic L1 modules (`std.*`) and low-level runtime bindings (`sys.*`).

For canonical ownership behavior around `new`/`drop`, ARC strings, and container-specific retain/release patterns, see
[ownership.md](ownership.md).

## Architecture Overview

```
+---------------------------------------------------------+
|                      L1 User Code                       |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
|                      std.* Modules                      |
| array, assert, fs, hashmap, hashset, io, linear_map,    |
| integer, optional, path, rand, real, string, system,    |
| text, time, types, unit, vector                         |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
|                      sys.* Modules                      |
|      hash, memory, real, rt (runtime API)               |
+---------------------------------------------------------+
                             |
                             v
+------------------------------------------------------------------+
|          C Runtime (`dea_rt.h` + `libdea_rt*.a`)                 |
+------------------------------------------------------------------+
```

## Module Reference

### `std.assert`

**Imports:** `sys.rt`

| Function | Signature                               | Description                             |
| -------- | --------------------------------------- | --------------------------------------- |
| `assert` | `func(cond: bool, msg: string) -> void` | Aborts with `msg` when `cond` is false. |

### `std.array`

L1 also has a language-level fixed-size array primitive `T[N]` and a non-owning slice view `T[]` with the compiler-owned
`dea::len` and `dea::slice` intrinsics. The `std.array` module remains the low-level untyped runtime-backed storage
abstraction used by existing containers and raw-memory helpers; it is not the representation of `T[N]` or `T[]`.

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
| `vec_push_int/byte/bool/ptr` | typed push helpers                                              | Push typed scalar/pointer values.               |
| `vi_sort`                    | `func(self: VectorBase*) -> void`                               | Insertion sort for `int` vectors (ascending).   |
| `StringVector`               | `type StringVector = VectorBase`                                | String-specialized vector alias.                |
| `sv_*`                       | `sv_create/push/get/size/capacity/sort/clear/free`              | String vector API with ARC-aware clear/free.    |

`vec_get` and the typed/string get helpers validate against logical length, never merely reserved capacity.

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

**Imports:** `sys.rt`, `sys.memory`, `std.array`, `std.assert`, `std.string`, `std.text`, `std.unit`

`std.io` classifies I/O success/failure from direct runtime return values (optional/boolean/sentinel results). Wide
numeric helpers use `_ui`, `_l`, `_ul`, `_f`, and `_d` suffixes for `uint`, `long`, `ulong`, `float`, and `double`.

| Function            | Signature                                                | Description                                                                         |
| ------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `read_line`         | `func() -> string?`                                      | Reads line from stdin; `null` on EOF/error.                                         |
| `read_char`         | `func() -> int?`                                         | Reads one byte as int; `null` on EOF/error.                                         |
| `read_char_or_eof`  | `func() -> int`                                          | Reads one byte; returns `-1` on EOF/error.                                          |
| `read_delim`        | `func(delim: byte) -> string?`                           | Reads through one delimiter byte; excludes and consumes it.                         |
| `read_delim_any`    | `func(delims: string) -> string?`                        | Reads through any byte in a non-empty delimiter set.                                |
| `read_delim_ws`     | `func() -> string?`                                      | Skips leading ASCII whitespace, then reads one whitespace-delimited token.          |
| `read_i`            | `func() -> int?`                                         | Parses the next whitespace token as `int`; `null` on EOF, invalid text, or range.   |
| `read_ui`           | `func() -> uint?`                                        | Parses the next whitespace token as `uint`; `null` on EOF, invalid text, or range.  |
| `read_l`            | `func() -> long?`                                        | Parses the next whitespace token as `long`; `null` on EOF, invalid text, or range.  |
| `read_ul`           | `func() -> ulong?`                                       | Parses the next whitespace token as `ulong`; `null` on EOF, invalid text, or range. |
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
| `print_ui`          | `func(x: uint) -> void`                                  | Prints uint to stdout.                                                              |
| `print_l`           | `func(x: long) -> void`                                  | Prints long to stdout.                                                              |
| `print_ul`          | `func(x: ulong) -> void`                                 | Prints ulong to stdout.                                                             |
| `print_f`           | `func(x: float) -> void`                                 | Prints float to stdout.                                                             |
| `print_d`           | `func(x: double) -> void`                                | Prints double to stdout.                                                            |
| `print_b`           | `func(x: bool) -> void`                                  | Prints bool to stdout.                                                              |
| `printl_s`          | `func(s: string) -> void`                                | Prints string + newline to stdout.                                                  |
| `printl_i`          | `func(x: int) -> void`                                   | Prints int + newline to stdout.                                                     |
| `printl_ui`         | `func(x: uint) -> void`                                  | Prints uint + newline to stdout.                                                    |
| `printl_l`          | `func(x: long) -> void`                                  | Prints long + newline to stdout.                                                    |
| `printl_ul`         | `func(x: ulong) -> void`                                 | Prints ulong + newline to stdout.                                                   |
| `printl_f`          | `func(x: float) -> void`                                 | Prints float + newline to stdout.                                                   |
| `printl_d`          | `func(x: double) -> void`                                | Prints double + newline to stdout.                                                  |
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
| `err_print_ui`      | `func(x: uint) -> void`                                  | Prints uint to stderr.                                                              |
| `err_print_l`       | `func(x: long) -> void`                                  | Prints long to stderr.                                                              |
| `err_print_ul`      | `func(x: ulong) -> void`                                 | Prints ulong to stderr.                                                             |
| `err_print_f`       | `func(x: float) -> void`                                 | Prints float to stderr.                                                             |
| `err_print_d`       | `func(x: double) -> void`                                | Prints double to stderr.                                                            |
| `err_print_b`       | `func(x: bool) -> void`                                  | Prints bool to stderr.                                                              |
| `err_printl_s`      | `func(s: string) -> void`                                | Prints string + newline to stderr.                                                  |
| `err_printl_i`      | `func(x: int) -> void`                                   | Prints int + newline to stderr.                                                     |
| `err_printl_ui`     | `func(x: uint) -> void`                                  | Prints uint + newline to stderr.                                                    |
| `err_printl_l`      | `func(x: long) -> void`                                  | Prints long + newline to stderr.                                                    |
| `err_printl_ul`     | `func(x: ulong) -> void`                                 | Prints ulong + newline to stderr.                                                   |
| `err_printl_f`      | `func(x: float) -> void`                                 | Prints float + newline to stderr.                                                   |
| `err_printl_d`      | `func(x: double) -> void`                                | Prints double + newline to stderr.                                                  |
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

Integer helper module. The unsuffixed surface is the shared `int` API; L1-only fixed-width helpers use explicit `_ui`,
`_l`, and `_ul` suffixes for `uint`, `long`, and `ulong`. Floating-point helpers stay out of `std.integer`.

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

Unsigned `uint` helpers use ordinary unsigned division names because Euclidean and ordinary unsigned division coincide.

| Function         | Signature                                   | Description                                                                                         |
| ---------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `div_ui`         | `func(a: uint, b: uint) -> uint`            | Unsigned quotient. Requires `b != 0`.                                                               |
| `mod_ui`         | `func(a: uint, b: uint) -> uint`            | Unsigned remainder. Requires `b != 0`.                                                              |
| `div_ceil_ui`    | `func(a: uint, b: uint) -> uint`            | Unsigned ceiling quotient. Requires `b != 0`.                                                       |
| `min_ui`         | `func(a: uint, b: uint) -> uint`            | Returns the smaller operand.                                                                        |
| `max_ui`         | `func(a: uint, b: uint) -> uint`            | Returns the larger operand.                                                                         |
| `clamp_ui`       | `func(x: uint, lo: uint, hi: uint) -> uint` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                    |
| `is_even_ui`     | `func(x: uint) -> bool`                     | Returns whether `x` is evenly divisible by 2.                                                       |
| `is_odd_ui`      | `func(x: uint) -> bool`                     | Returns whether `x` is not evenly divisible by 2.                                                   |
| `is_multiple_ui` | `func(a: uint, b: uint) -> bool`            | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                  |
| `gcd_ui`         | `func(a: uint, b: uint) -> uint`            | Greatest common divisor.                                                                            |
| `lcm_ui`         | `func(a: uint, b: uint) -> uint?`           | Least common multiple. Returns `null` on overflow.                                                  |
| `pow_ui`         | `func(base: uint, exp: int) -> uint?`       | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                   |
| `isqrt_ui`       | `func(x: uint) -> uint`                     | Floor integer square root.                                                                          |
| `align_down_ui`  | `func(x: uint, align: uint) -> uint`        | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`.                           |
| `align_up_ui`    | `func(x: uint, align: uint) -> uint?`       | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow. |
| `is_aligned_ui`  | `func(x: uint, align: uint) -> bool`        | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                            |

Signed `long` helpers mirror the shared signed policy, including nullable results for `LONG_MIN` representability and
overflow edges.

| Function        | Signature                                   | Description                                                                                                |
| --------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `emod_l`        | `func(a: long, b: long) -> long`            | Euclidean modulo. Requires `b > 0`; always returns a result in `[0, b)`.                                   |
| `ediv_l`        | `func(a: long, b: long) -> long`            | Euclidean quotient paired with `emod_l`. Requires `b > 0`.                                                 |
| `div_floor_l`   | `func(a: long, b: long) -> long`            | Mathematical floor quotient. Requires `b != 0` and a representable result (excluding `long_min() / -1`).   |
| `div_ceil_l`    | `func(a: long, b: long) -> long`            | Mathematical ceiling quotient. Requires `b != 0` and a representable result (excluding `long_min() / -1`). |
| `min_l`         | `func(a: long, b: long) -> long`            | Returns the smaller operand.                                                                               |
| `max_l`         | `func(a: long, b: long) -> long`            | Returns the larger operand.                                                                                |
| `clamp_l`       | `func(x: long, lo: long, hi: long) -> long` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                           |
| `sign_l`        | `func(x: long) -> int`                      | Returns `-1`, `0`, or `1` based on the sign of `x`.                                                        |
| `is_even_l`     | `func(x: long) -> bool`                     | Returns whether `x` is evenly divisible by 2.                                                              |
| `is_odd_l`      | `func(x: long) -> bool`                     | Returns whether `x` is not evenly divisible by 2.                                                          |
| `is_multiple_l` | `func(a: long, b: long) -> bool`            | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                         |
| `abs_l`         | `func(x: long) -> long?`                    | Absolute value. Returns `null` when the mathematical result is not representable as `long`.                |
| `gcd_l`         | `func(a: long, b: long) -> long?`           | Non-negative greatest common divisor. Returns `null` when the mathematical result is not representable.    |
| `lcm_l`         | `func(a: long, b: long) -> long?`           | Non-negative least common multiple. Returns `null` on overflow or non-representable results.               |
| `pow_l`         | `func(base: long, exp: int) -> long?`       | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                          |
| `isqrt_l`       | `func(x: long) -> long?`                    | Floor integer square root. Returns `null` when `x < 0`.                                                    |
| `align_down_l`  | `func(x: long, align: long) -> long?`       | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.      |
| `align_up_l`    | `func(x: long, align: long) -> long?`       | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.        |
| `is_aligned_l`  | `func(x: long, align: long) -> bool`        | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                                   |

Unsigned `ulong` helpers intentionally omit signed-only concepts such as `sign_ul`, `abs_ul`, `ediv_ul`, and `emod_ul`.

| Function         | Signature                                       | Description                                                                                         |
| ---------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `div_ul`         | `func(a: ulong, b: ulong) -> ulong`             | Unsigned quotient. Requires `b != 0`.                                                               |
| `mod_ul`         | `func(a: ulong, b: ulong) -> ulong`             | Unsigned remainder. Requires `b != 0`.                                                              |
| `div_ceil_ul`    | `func(a: ulong, b: ulong) -> ulong`             | Unsigned ceiling quotient. Requires `b != 0`.                                                       |
| `min_ul`         | `func(a: ulong, b: ulong) -> ulong`             | Returns the smaller operand.                                                                        |
| `max_ul`         | `func(a: ulong, b: ulong) -> ulong`             | Returns the larger operand.                                                                         |
| `clamp_ul`       | `func(x: ulong, lo: ulong, hi: ulong) -> ulong` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                    |
| `is_even_ul`     | `func(x: ulong) -> bool`                        | Returns whether `x` is evenly divisible by 2.                                                       |
| `is_odd_ul`      | `func(x: ulong) -> bool`                        | Returns whether `x` is not evenly divisible by 2.                                                   |
| `is_multiple_ul` | `func(a: ulong, b: ulong) -> bool`              | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                  |
| `gcd_ul`         | `func(a: ulong, b: ulong) -> ulong`             | Greatest common divisor.                                                                            |
| `lcm_ul`         | `func(a: ulong, b: ulong) -> ulong?`            | Least common multiple. Returns `null` on overflow.                                                  |
| `pow_ul`         | `func(base: ulong, exp: int) -> ulong?`         | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                   |
| `isqrt_ul`       | `func(x: ulong) -> ulong`                       | Floor integer square root.                                                                          |
| `align_down_ul`  | `func(x: ulong, align: ulong) -> ulong`         | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`.                           |
| `align_up_ul`    | `func(x: ulong, align: ulong) -> ulong?`        | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow. |
| `is_aligned_ul`  | `func(x: ulong, align: ulong) -> bool`          | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                            |

### `std.real`

**Imports:** `sys.real`

Floating-point helper module for classification, basic operations, rounding, remainder/decomposition, and transcendental
math.

`PI_F`, `PI`, `E_F`, `E`, `NAN_F`, `NAN`, `INFINITY_F`, and `INFINITY` are module-level `let` values. Stage 1 now lowers
runtime-initialized top-level `let` bindings through hidden module-init functions that run before user `main`.

The `modf_*` and `frexp_*` helpers return small named result structs:

| Type          | Definition                                                   | Description                                            |
| ------------- | ------------------------------------------------------------ | ------------------------------------------------------ |
| `FracPartsF`  | `struct FracPartsF { int_part: float; frac_part: float; }`   | Result of `modf_f`: integral and fractional parts.     |
| `FracPartsD`  | `struct FracPartsD { int_part: double; frac_part: double; }` | Result of `modf_d`: integral and fractional parts.     |
| `FrexpPartsF` | `struct FrexpPartsF { significand: float; exp: int; }`       | Result of `frexp_f`: normalized fraction and exponent. |
| `FrexpPartsD` | `struct FrexpPartsD { significand: double; exp: int; }`      | Result of `frexp_d`: normalized fraction and exponent. |

| Member         | Signature / Type                                                  | Description                                                           |
| -------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------- |
| `PI_F`         | `float`                                                           | Single-precision approximation of pi.                                 |
| `PI`           | `double`                                                          | Double-precision approximation of pi.                                 |
| `E_F`          | `float`                                                           | Single-precision approximation of Euler's number.                     |
| `E`            | `double`                                                          | Double-precision approximation of Euler's number.                     |
| `NAN_F`        | `float`                                                           | Single-precision NaN value.                                           |
| `NAN`          | `double`                                                          | Double-precision NaN value.                                           |
| `INFINITY_F`   | `float`                                                           | Single-precision positive infinity.                                   |
| `INFINITY`     | `double`                                                          | Double-precision positive infinity.                                   |
| `is_nan_*`     | `func(x: float) -> bool`, `func(x: double) -> bool`               | Returns true if `x` is NaN.                                           |
| `is_inf_*`     | `func(x: float) -> bool`, `func(x: double) -> bool`               | Returns true if `x` is positive or negative infinity.                 |
| `is_finite_*`  | `func(x: float) -> bool`, `func(x: double) -> bool`               | Returns true if `x` is neither NaN nor infinite.                      |
| `signbit_*`    | `func(x: float) -> bool`, `func(x: double) -> bool`               | Returns true if the sign bit of `x` is set.                           |
| `abs_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the absolute value of `x`.                                    |
| `sqrt_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the square root of `x`.                                       |
| `cbrt_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the cube root of `x`.                                         |
| `hypot_*`      | `func(x: float, y: float) -> float`, `...`                        | Returns the hypotenuse without intermediate overflow or underflow.    |
| `floor_*`      | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the largest integral value not greater than `x`.              |
| `ceil_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the smallest integral value not less than `x`.                |
| `trunc_*`      | `func(x: float) -> float`, `func(x: double) -> double`            | Rounds `x` toward zero to an integral value.                          |
| `round_*`      | `func(x: float) -> float`, `func(x: double) -> double`            | Rounds `x` to the nearest integral value.                             |
| `fmod_*`       | `func(x: float, y: float) -> float`, `...`                        | Returns the floating-point remainder of `x/y`.                        |
| `remainder_*`  | `func(x: float, y: float) -> float`, `...`                        | Returns the IEEE 754 floating-point remainder.                        |
| `modf_*`       | `func(x: float) -> FracPartsF`, `func(x: double) -> FracPartsD`   | Decomposes `x` into integral and fractional parts.                    |
| `frexp_*`      | `func(x: float) -> FrexpPartsF`, `func(x: double) -> FrexpPartsD` | Decomposes `x` into a normalized fraction and an integral power of 2. |
| `ldexp_*`      | `func(x: float, exp: int) -> float`, `...`                        | Multiplies `x` by 2 raised to the power `exp`.                        |
| `copy_sign_*`  | `func(x: float, y: float) -> float`, `...`                        | Returns a value with the magnitude of `x` and the sign of `y`.        |
| `next_after_*` | `func(x: float, y: float) -> float`, `...`                        | Returns the next representable value of `x` in the direction of `y`.  |
| `exp_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns e raised to the power of `x`.                                 |
| `exp2_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns 2 raised to the power of `x`.                                 |
| `log_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the natural logarithm of `x`.                                 |
| `log10_*`      | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the base-10 logarithm of `x`.                                 |
| `log2_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the base-2 logarithm of `x`.                                  |
| `pow_*`        | `func(x: float, y: float) -> float`, `...`                        | Returns `x` raised to the power `y`.                                  |
| `sin_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the sine of `x`.                                              |
| `cos_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the cosine of `x`.                                            |
| `tan_*`        | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the tangent of `x`.                                           |
| `asin_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the arc-sine of `x`.                                          |
| `acos_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the arc-cosine of `x`.                                        |
| `atan_*`       | `func(x: float) -> float`, `func(x: double) -> double`            | Returns the arc-tangent of `x`.                                       |
| `atan2_*`      | `func(x: float, y: float) -> float`, `...`                        | Returns the quadrant-aware arc-tangent for the pair `(x, y)`.         |

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
| `uint_to_string/uint_to_string_base`                | `func(uint) -> string`, `func(uint, base: int) -> string`                                           | Numeric uint formatting (decimal or base `2..16`).                                                        |
| `long_to_string/long_to_string_base`                | `func(long) -> string`, `func(long, base: int) -> string`                                           | Numeric long formatting (decimal or base `2..16`).                                                        |
| `ulong_to_string/ulong_to_string_base`              | `func(ulong) -> string`, `func(ulong, base: int) -> string`                                         | Numeric ulong formatting (decimal or base `2..16`).                                                       |
| `string_to_int`                                     | `func(s: string) -> int?`                                                                           | Parses decimal signed integer text; returns `null` on invalid input or 32-bit overflow/underflow.         |
| `string_to_int_base`                                | `func(s: string, base: int) -> int?`                                                                | Parses signed integer text in base `2..16`; returns `null` on invalid input or 32-bit overflow/underflow. |
| `string_to_byte/string_to_byte_base`                | `func(s: string) -> byte?`, `func(s: string, base: int) -> byte?`                                   | Parses numeric byte text; returns `null` on invalid input or out-of-range values (`0..255`).              |
| `string_to_uint/string_to_uint_base`                | `func(s: string) -> uint?`, `func(s: string, base: int) -> uint?`                                   | Parses unsigned integer text; rejects negative or out-of-range values.                                    |
| `string_to_long/string_to_long_base`                | `func(s: string) -> long?`, `func(s: string, base: int) -> long?`                                   | Parses signed 64-bit integer text; returns `null` on invalid input or overflow/underflow.                 |
| `string_to_ulong/string_to_ulong_base`              | `func(s: string) -> ulong?`, `func(s: string, base: int) -> ulong?`                                 | Parses unsigned 64-bit integer text; rejects negative or out-of-range values.                             |

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

### `std.types`

Provides a type-erased `Value` enum representing any built-in primitive value (and its optional counterpart), useful for
generic argument or return passing across types of unknown type, plus matching predicates and unwrapping helpers.

The `Value` enum (rendered here in full, since it has 24 variants):

```
enum Value {
    Bool(b: bool);
    Tiny(t: tiny);
    Byte(b: byte);
    Short(sh: short);
    UShort(us: ushort);
    Int(i: int);
    UInt(ui: uint);
    Long(l: long);
    ULong(ul: ulong);
    Float(f: float);
    Double(d: double);
    String(s: string);
    OptBool(b: bool?);
    OptTiny(t: tiny?);
    OptByte(b: byte?);
    OptShort(sh: short?);
    OptUShort(us: ushort?);
    OptInt(i: int?);
    OptUInt(ui: uint?);
    OptLong(l: long?);
    OptULong(ul: ulong?);
    OptFloat(f: float?);
    OptDouble(d: double?);
    OptString(s: string?);
}
```

| Function                                                                                                                                                                                              | Signature                  | Description                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `is_optional`                                                                                                                                                                                         | `func(v: Value) -> bool`   | Returns whether `v` is an optional variant.                                                                                                                        |
| `is_null`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is an optional variant carrying `null`.                                                                                                        |
| `get_opt_value`                                                                                                                                                                                       | `func(v: Value) -> Value?` | Unwraps an optional variant: returns the matching non-optional variant when present, `null` when the optional is null, or `v` unchanged for non-optional variants. |
| `is_bool`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is a `Bool` variant.                                                                                                                           |
| `is_tiny`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is a `Tiny` variant.                                                                                                                           |
| `is_byte`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is a `Byte` variant.                                                                                                                           |
| `is_short`                                                                                                                                                                                            | `func(v: Value) -> bool`   | Returns whether `v` is a `Short` variant.                                                                                                                          |
| `is_ushort`                                                                                                                                                                                           | `func(v: Value) -> bool`   | Returns whether `v` is a `UShort` variant.                                                                                                                         |
| `is_int`                                                                                                                                                                                              | `func(v: Value) -> bool`   | Returns whether `v` is an `Int` variant.                                                                                                                           |
| `is_uint`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is a `UInt` variant.                                                                                                                           |
| `is_long`                                                                                                                                                                                             | `func(v: Value) -> bool`   | Returns whether `v` is a `Long` variant.                                                                                                                           |
| `is_ulong`                                                                                                                                                                                            | `func(v: Value) -> bool`   | Returns whether `v` is a `ULong` variant.                                                                                                                          |
| `is_float`                                                                                                                                                                                            | `func(v: Value) -> bool`   | Returns whether `v` is a `Float` variant.                                                                                                                          |
| `is_double`                                                                                                                                                                                           | `func(v: Value) -> bool`   | Returns whether `v` is a `Double` variant.                                                                                                                         |
| `is_string`                                                                                                                                                                                           | `func(v: Value) -> bool`   | Returns whether `v` is a `String` variant.                                                                                                                         |
| `is_opt_bool` / `is_opt_tiny` / `is_opt_byte` / `is_opt_short` / `is_opt_ushort` / `is_opt_int` / `is_opt_uint` / `is_opt_long` / `is_opt_ulong` / `is_opt_float` / `is_opt_double` / `is_opt_string` | `func(v: Value) -> bool`   | Per-type optional-variant predicates.                                                                                                                              |

### `std.unit`

| Type/Function | Signature         | Description                     |
| ------------- | ----------------- | ------------------------------- |
| `Unit`        | `struct Unit {}`  | Unit type.                      |
| `unit`        | `func() -> Unit`  | Returns unit value.             |
| `present`     | `func() -> Unit?` | Returns non-null optional unit. |

### `sys.hash`

Low-level runtime FFI for hashing raw values and pointers. Uses the siphash-1-3 algorithm. Used by `std.hashmap` and
`std.hashset` for hash calculations.

### `sys.rt`

Low-level runtime FFI for strings, I/O, process/system, time, and errors. Also defines `RtTimeParts`
(`struct RtTimeParts { sec: int; nsec: int; }`) and `RtFileInfo`
(`struct RtFileInfo { exists: bool; is_file: bool; is_dir: bool; size: int?; mtime_sec: int?; mtime_nsec: int?; }`).

### `sys.real`

Low-level runtime FFI for floating-point math helpers. Used by `std.real` for classification, roots,
remainder/decomposition, rounding, and transcendental math.

### `sys.memory`

Low-level raw memory FFI. Misuse can cause undefined behavior.

In checked runtime builds (the default), allocations are tracked with distinct raw, `new`, ARC, static, and foreign
provenance, and pointer accesses are validated. `drop` accepts only `new` allocations; `rt_free` and `rt_realloc` accept
only raw allocations. Dropped and freed owned blocks pass through a bounded quarantine before returning to the C
allocator. The quarantine limits default to 16 MiB and 4096 records and can be retuned per process through the
`DEA_RT_QUARANTINE_MAX_BYTES` and `DEA_RT_QUARANTINE_MAX_COUNT` environment variables, read once at first tracker use,
or baked into the archives with the `make` variables `L1_RT_QUARANTINE_MAX_BYTES`/`L1_RT_QUARANTINE_MAX_COUNT`. Smaller
retention (including `0`) speeds allocation-heavy code at the cost of a shorter use-after-drop detection window. The
default record limit (4096) is detection-first and right for development; `256` is the suggested setting for
performance-sensitive checked deployments, per the corrected monotonic `make bench-runtime` matrix. Smaller caps
generally reduce allocation-heavy costs, but the magnitude and the value of intermediate settings vary by compiler and
workload, so deployments that need more temporal depth should measure their own 1024-or-higher tradeoff. Record-pool and
tracker-table metadata have different retention: record-pool memory is peak-driven, while table capacity follows the
current live record count with resize hysteresis. Quarantined payload memory is bounded by the byte/count caps, so lower
caps can reduce both the retained live tracker set and freed payload memory. The `l1c --check-basic` flag selects the
prebuilt `libdea_rt_check_basic.a` archive variant and defines `DEA_RT_CHECK_BASIC` in generated C; this keeps
exact-base hash validation, quarantine, generation caches, null checks, double-drop and untracked-drop diagnostics,
exact-base ARC/static string read-only protection, and alignment checks for hash-miss accesses while compiling out the
interior-pointer treap. The `l1c --unchecked` flag selects the prebuilt `libdea_rt_unchecked.a` archive variant and
defines `DEA_RT_UNCHECKED` in generated C, compiling pointer tracking and access validation out; neither mode can be
combined with the trace flags. Basic runtime API argument checks still apply. Externally owned storage can be registered
for checked access through `rt_register_foreign(ptr, bytes, read_only)` and unregistered without freeing through
`rt_unregister_foreign(ptr)`; unchecked mode validates basic arguments but keeps no registration state.

## FFI Inventory (`extern func` / `unsafe extern func`)

All `extern func` and `unsafe extern func` symbols exposed to L1 from `sys.*` modules are listed here.

### Declared in `sys.rt` (52)

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
| `rt_print_uint`               | `func(x: uint) -> void`                           | Prints a uint to stdout.                                                                                   |
| `rt_print_uint_stderr`        | `func(x: uint) -> void`                           | Prints a uint to stderr.                                                                                   |
| `rt_print_long`               | `func(x: long) -> void`                           | Prints a long to stdout.                                                                                   |
| `rt_print_long_stderr`        | `func(x: long) -> void`                           | Prints a long to stderr.                                                                                   |
| `rt_print_ulong`              | `func(x: ulong) -> void`                          | Prints a ulong to stdout.                                                                                  |
| `rt_print_ulong_stderr`       | `func(x: ulong) -> void`                          | Prints a ulong to stderr.                                                                                  |
| `rt_print_float`              | `func(x: float) -> void`                          | Prints a float to stdout.                                                                                  |
| `rt_print_float_stderr`       | `func(x: float) -> void`                          | Prints a float to stderr.                                                                                  |
| `rt_print_double`             | `func(x: double) -> void`                         | Prints a double to stdout.                                                                                 |
| `rt_print_double_stderr`      | `func(x: double) -> void`                         | Prints a double to stderr.                                                                                 |
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

### Declared in `sys.real` (68)

These runtime-backed floating-point bindings are provided in matched `float` (`_f`) and `double` (`_d`) forms.

| Functions                                       | Signatures                                                                                     | Description                                     |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `rt_real_get_nan_f` / `rt_real_get_nan_d`       | `func() -> float` / `func() -> double`                                                         | Return quiet NaN values.                        |
| `rt_real_get_inf_f` / `rt_real_get_inf_d`       | `func() -> float` / `func() -> double`                                                         | Return positive infinity values.                |
| `rt_real_is_nan_f` / `rt_real_is_nan_d`         | `func(x: float) -> bool` / `func(x: double) -> bool`                                           | Test whether `x` is NaN.                        |
| `rt_real_is_inf_f` / `rt_real_is_inf_d`         | `func(x: float) -> bool` / `func(x: double) -> bool`                                           | Test whether `x` is infinite.                   |
| `rt_real_is_finite_f` / `rt_real_is_finite_d`   | `func(x: float) -> bool` / `func(x: double) -> bool`                                           | Test whether `x` is finite.                     |
| `rt_real_signbit_f` / `rt_real_signbit_d`       | `func(x: float) -> bool` / `func(x: double) -> bool`                                           | Test the sign bit of `x`.                       |
| `rt_real_abs_f` / `rt_real_abs_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the absolute value.                      |
| `rt_real_sqrt_f` / `rt_real_sqrt_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the square root.                         |
| `rt_real_cbrt_f` / `rt_real_cbrt_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the cube root.                           |
| `rt_real_hypot_f` / `rt_real_hypot_d`           | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return the Euclidean norm of `x` and `y`.       |
| `rt_real_floor_f` / `rt_real_floor_d`           | `func(x: float) -> float` / `func(x: double) -> double`                                        | Round toward negative infinity.                 |
| `rt_real_ceil_f` / `rt_real_ceil_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Round toward positive infinity.                 |
| `rt_real_trunc_f` / `rt_real_trunc_d`           | `func(x: float) -> float` / `func(x: double) -> double`                                        | Round toward zero.                              |
| `rt_real_round_f` / `rt_real_round_d`           | `func(x: float) -> float` / `func(x: double) -> double`                                        | Round to the nearest integral value.            |
| `rt_real_fmod_f` / `rt_real_fmod_d`             | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return the truncated-quotient remainder.        |
| `rt_real_remainder_f` / `rt_real_remainder_d`   | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return the IEEE remainder.                      |
| `rt_real_modf_f` / `rt_real_modf_d`             | `func(x: float, iptr: RtFloatOut*) -> float` / `func(x: double, iptr: RtDoubleOut*) -> double` | Split fractional and integral parts.            |
| `rt_real_frexp_f` / `rt_real_frexp_d`           | `func(x: float, exp: RtIntOut*) -> float` / `func(x: double, exp: RtIntOut*) -> double`        | Split into normalized fraction and exponent.    |
| `rt_real_ldexp_f` / `rt_real_ldexp_d`           | `func(x: float, exp: int) -> float` / `func(x: double, exp: int) -> double`                    | Scale `x` by an integral power of two.          |
| `rt_real_copy_sign_f` / `rt_real_copy_sign_d`   | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Copy the sign of `y` onto `x`.                  |
| `rt_real_next_after_f` / `rt_real_next_after_d` | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return the next representable value toward `y`. |
| `rt_real_exp_f` / `rt_real_exp_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return `e` raised to `x`.                       |
| `rt_real_exp2_f` / `rt_real_exp2_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return 2 raised to `x`.                         |
| `rt_real_log_f` / `rt_real_log_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the natural logarithm.                   |
| `rt_real_log10_f` / `rt_real_log10_d`           | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the base-10 logarithm.                   |
| `rt_real_log2_f` / `rt_real_log2_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the base-2 logarithm.                    |
| `rt_real_pow_f` / `rt_real_pow_d`               | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return `x` raised to `y`.                       |
| `rt_real_sin_f` / `rt_real_sin_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the sine.                                |
| `rt_real_cos_f` / `rt_real_cos_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the cosine.                              |
| `rt_real_tan_f` / `rt_real_tan_d`               | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the tangent.                             |
| `rt_real_asin_f` / `rt_real_asin_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the arc sine.                            |
| `rt_real_acos_f` / `rt_real_acos_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the arc cosine.                          |
| `rt_real_atan_f` / `rt_real_atan_d`             | `func(x: float) -> float` / `func(x: double) -> double`                                        | Return the arc tangent.                         |
| `rt_real_atan2_f` / `rt_real_atan2_d`           | `func(x: float, y: float) -> float` / `func(x: double, y: double) -> double`                   | Return the quadrant-aware arc tangent.          |

### Declared in `sys.memory` (13)

These are unsafe raw-memory primitives. Foreign registration transfers no ownership and never authorizes runtime
release.

| Function                | Signature                                                                | Description                                      |
| ----------------------- | ------------------------------------------------------------------------ | ------------------------------------------------ |
| `rt_alloc`              | `func(bytes: int) -> void*?`                                             | Allocates raw heap memory.                       |
| `rt_calloc`             | `func(count: int, elem_size: int) -> void*?`                             | Allocates zeroed raw memory.                     |
| `rt_realloc`            | `unsafe func(ptr: void*?, new_bytes: int) -> void*?`                     | Resizes raw heap memory.                         |
| `rt_free`               | `unsafe func(ptr: void*?) -> void`                                       | Frees raw heap memory.                           |
| `rt_register_foreign`   | `unsafe func(ptr: void*, bytes: int, read_only: bool) -> void`           | Registers externally owned storage for checks.   |
| `rt_unregister_foreign` | `unsafe func(ptr: void*) -> void`                                        | Invalidates a foreign registration without free. |
| `rt_memcpy`             | `unsafe func(dest: void*, src: void*, bytes: int) -> void*`              | Copies raw bytes.                                |
| `rt_memset`             | `unsafe func(dest: void*, value: int, bytes: int) -> void*`              | Fills raw bytes.                                 |
| `rt_memcmp`             | `unsafe func(a: void*, b: void*, bytes: int) -> int`                     | Compares raw bytes.                              |
| `rt_array_element`      | `unsafe func(array_data: void*, element_size: int, index: int) -> void*` | Computes an element pointer.                     |
| `rt_stdin_read`         | `unsafe func(buf: byte*?, capacity: int) -> int`                         | Reads raw bytes from stdin.                      |
| `rt_stdout_write`       | `unsafe func(buf: byte*?, len: int) -> int`                              | Writes raw bytes to stdout.                      |
| `rt_stderr_write`       | `unsafe func(buf: byte*?, len: int) -> int`                              | Writes raw bytes to stderr.                      |

### Declared in `sys.hash` (11)

These are runtime-backed hash externs declared directly in `sys.hash`.

| Function             | Signature                             | Description                     |
| -------------------- | ------------------------------------- | ------------------------------- |
| `rt_hash_bool`       | `func(value: bool) -> int`            | Hashes a bool value.            |
| `rt_hash_byte`       | `func(value: byte) -> int`            | Hashes a byte value.            |
| `rt_hash_int`        | `func(value: int) -> int`             | Hashes an int value.            |
| `rt_hash_string`     | `func(value: string) -> int`          | Hashes a string value.          |
| `rt_hash_data`       | `func(data: void*, size: int) -> int` | Hashes raw byte data.           |
| `rt_hash_opt_bool`   | `func(opt: bool?) -> int`             | Hashes an optional bool.        |
| `rt_hash_opt_byte`   | `func(opt: byte?) -> int`             | Hashes an optional byte.        |
| `rt_hash_opt_int`    | `func(opt: int?) -> int`              | Hashes an optional int.         |
| `rt_hash_opt_string` | `func(opt: string?) -> int`           | Hashes an optional string.      |
| `rt_hash_ptr`        | `func(ptr: void*) -> int`             | Hashes a raw pointer value.     |
| `rt_hash_opt_ptr`    | `func(opt: void*?) -> int`            | Hashes an optional raw pointer. |
