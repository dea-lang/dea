# The L1 Standard Library

Version: 2026-05-09

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
| math, optional, path, rand, string, system, text, time, |
| unit, vector                                            |
+---------------------------------------------------------+
                             |
                             v
+---------------------------------------------------------+
|                      sys.* Modules                      |
|      hash, rt (runtime API), memory                     |
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

| Function | Signature                           | Description                             |
| -------- | ----------------------------------- | --------------------------------------- |
| `assert` | `(cond: bool, msg: string) -> void` | Aborts with `msg` when `cond` is false. |

### `std.array`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`

| Type/Function | Signature                                                             | Description                                        |
| ------------- | --------------------------------------------------------------------- | -------------------------------------------------- |
| `ArrayBase`   | `struct ArrayBase { capacity: int; element_size: int; data: void*; }` | Untyped fixed-size backing storage.                |
| `ByteArray`   | `struct ByteArray { storage: ArrayBase*; }`                           | Byte-specialized fixed-size array wrapper.         |
| `arr_create`  | `(element_size: int, length: int) -> ArrayBase*`                      | Allocates and zero-initializes storage.            |
| `arr_check`   | `(self: ArrayBase*, index: int) -> void`                              | Bounds-check helper (`0 <= index < capacity`).     |
| `arr_resize`  | `(self: ArrayBase*, new_length: int) -> void`                         | Reallocates backing storage and zero-fills growth. |
| `arr_get`     | `(self: ArrayBase*, index: int) -> void*`                             | Returns element pointer at index.                  |
| `arr_zap`     | `(self: ArrayBase*, index: int) -> void`                              | Zeroes one element slot.                           |
| `arr_free`    | `(self: ArrayBase*) -> void`                                          | Frees backing storage and drops container.         |
| `ba_create`   | `(length: int) -> ByteArray*`                                         | Allocates a fixed-size byte array.                 |
| `ba_capacity` | `(self: ByteArray*) -> int`                                           | Returns the number of byte slots.                  |
| `ba_get`      | `(self: ByteArray*, index: int) -> byte`                              | Returns one byte with bounds checking.             |
| `ba_set`      | `(self: ByteArray*, index: int, value: byte) -> void`                 | Stores one byte with bounds checking.              |
| `ba_zap`      | `(self: ByteArray*, index: int) -> void`                              | Zeroes one byte slot with bounds checking.         |
| `ba_free`     | `(self: ByteArray*) -> void`                                          | Frees the wrapper and its backing storage.         |

### `std.fs`

**Imports:** `sys.rt`, `std.unit`

| Type/Function | Signature                                                                                              | Description                                             |
| ------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| `FileInfo`    | `struct { exists: bool; is_file: bool; is_dir: bool; size: int?; mtime_sec: int?; mtime_nsec: int?; }` | Public file-metadata wrapper type.                      |
| `exists`      | `(path: string) -> bool`                                                                               | Returns whether any filesystem object exists at `path`. |
| `stat`        | `(path: string) -> FileInfo`                                                                           | Returns path metadata with nullable size/timestamps.    |
| `is_file`     | `(path: string) -> bool`                                                                               | Returns whether path exists and is a regular file.      |
| `is_dir`      | `(path: string) -> bool`                                                                               | Returns whether path exists and is a directory.         |
| `file_size`   | `(path: string) -> int?`                                                                               | Returns file size in bytes when available.              |
| `mtime_sec`   | `(path: string) -> int?`                                                                               | Returns modification time in Unix seconds if available. |
| `delete_file` | `(path: string) -> Unit?`                                                                              | Deletes a file; returns `null` on failure.              |
| `read_file`   | `(path: string) -> string?`                                                                            | Reads entire file; `null` on error.                     |
| `write_file`  | `(path: string, data: string) -> Unit?`                                                                | Writes entire file; `null` on error.                    |

### `std.vector`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `std.array`

| Type/Function                | Signature                                                   | Description                                     |
| ---------------------------- | ----------------------------------------------------------- | ----------------------------------------------- |
| `VectorBase`                 | `struct VectorBase { arr: ArrayBase*; length: int; }`       | Untyped growable vector.                        |
| `vec_create`                 | `(element_size: int, initial_capacity: int) -> VectorBase*` | Creates vector storage.                         |
| `vec_grow`                   | `(self: VectorBase*) -> void`                               | Ensures capacity and increments length.         |
| `vec_reserve`                | `(self: VectorBase*, total_capacity: int) -> void`          | Ensures at least requested capacity.            |
| `vec_get`                    | `(self: VectorBase*, index: int) -> void*`                  | Returns element pointer.                        |
| `vec_push`                   | `(self: VectorBase*) -> void*`                              | Grows and returns pointer to new slot.          |
| `vec_size`                   | `(self: VectorBase*) -> int`                                | Returns logical length.                         |
| `vec_capacity`               | `(self: VectorBase*) -> int`                                | Returns current capacity.                       |
| `vec_clear`                  | `(self: VectorBase*) -> void`                               | Clears vector and resets backing capacity to 1. |
| `vec_free`                   | `(self: VectorBase*) -> void`                               | Frees vector storage.                           |
| `vec_push_int/byte/bool/ptr` | typed push helpers                                          | Push typed scalar/pointer values.               |
| `vi_sort`                    | `(self: VectorBase*) -> void`                               | Insertion sort for `int` vectors (ascending).   |
| `VectorString`               | `type VectorString = VectorBase`                            | String-specialized vector alias.                |
| `vs_*`                       | `vs_create/push/get/size/capacity/sort/clear/free`          | String vector API with ARC-aware clear/free.    |

### `std.hashmap`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.array`, `std.vector`

| Type/Function                     | Signature                                | Description                                  |
| --------------------------------- | ---------------------------------------- | -------------------------------------------- |
| `StringPtrMap`                    | `struct`                                 | Open-addressed `string -> void*` map.        |
| `spm_create/create_with_capacity` | constructors                             | Create map with default or minimum capacity. |
| `spm_put/get/has/remove`          | map ops                                  | Insert/update/lookup/presence/remove.        |
| `spm_size/capacity/clear/free`    | management                               | Size, capacity, clear entries, free map.     |
| `spm_keys`                        | `(self: StringPtrMap*) -> VectorString*` | Returns keys as new string vector.           |
| `spm_slot_occupied/key/value`     | iteration helpers                        | Slot-level iteration support.                |
| `StringIntMap`                    | `struct`                                 | Open-addressed `string -> int` map.          |
| `sim_create/create_with_capacity` | constructors                             | Create map with default or minimum capacity. |
| `sim_put/get/has/remove`          | map ops                                  | Insert/update/lookup/presence/remove.        |
| `sim_size/capacity/clear/free`    | management                               | Size, capacity, clear entries, free map.     |
| `sim_keys`                        | `(self: StringIntMap*) -> VectorString*` | Returns keys as new string vector.           |
| `sim_slot_occupied/key/value`     | iteration helpers                        | Slot-level iteration support.                |

### `std.hashset`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.array`, `std.vector`

| Type/Function                    | Signature                                 | Description                                  |
| -------------------------------- | ----------------------------------------- | -------------------------------------------- |
| `StringSet`                      | `struct`                                  | Open-addressed set of strings.               |
| `ss_create/create_with_capacity` | constructors                              | Create set with default or minimum capacity. |
| `ss_add`                         | `(self: StringSet*, key: string) -> bool` | Adds key; returns false if already present.  |
| `ss_has/remove`                  | set ops                                   | Presence check and removal.                  |
| `ss_size/capacity/clear/free`    | management                                | Size, capacity, clear entries, free set.     |
| `ss_to_vector`                   | `(self: StringSet*) -> VectorString*`     | Returns elements as new vector.              |
| `ss_slot_occupied/key`           | iteration helpers                         | Slot-level iteration support.                |

### `std.linear_map`

**Imports:** `sys.rt`, `sys.memory`, `std.assert`, `std.string`, `sys.hash`, `std.vector`

| Type/Function           | Signature                                                 | Description                                 |
| ----------------------- | --------------------------------------------------------- | ------------------------------------------- |
| `LinearMapBase`         | `struct`                                                  | Generic byte-comparison linear map storage. |
| `lm_create/free/len`    | base lifecycle                                            | Create, free, and query length.             |
| `lm_set/get/remove`     | base ops                                                  | Set/get/remove key-value by raw key bytes.  |
| `lm_contains_key/value` | base queries                                              | Presence checks by key/value bytes.         |
| `LinearMapStringString` | `struct`                                                  | `string -> string` specialization.          |
| `lmss_*`                | `create/free/len/set/get/contains/remove/key_at/value_at` | ARC-aware string map API.                   |
| `LinearMapIntString`    | `struct`                                                  | `int -> string` specialization.             |
| `lmis_*`                | `create/free/len/set/get/contains/remove/key_at/value_at` | ARC-aware int/string map API.               |

### `std.io`

**Imports:** `sys.rt`, `sys.memory`, `std.array`, `std.assert`, `std.string`, `std.text`, `std.unit`

`std.io` classifies I/O success/failure from direct runtime return values (optional/boolean/sentinel results). Wide
numeric helpers use `_ui`, `_l`, `_ul`, `_f`, and `_d` suffixes for `uint`, `long`, `ulong`, `float`, and `double`.

| Function            | Signature                                            | Description                                                                         |
| ------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `read_line`         | `() -> string?`                                      | Reads line from stdin; `null` on EOF/error.                                         |
| `read_char`         | `() -> int?`                                         | Reads one byte as int; `null` on EOF/error.                                         |
| `read_char_or_eof`  | `() -> int`                                          | Reads one byte; returns `-1` on EOF/error.                                          |
| `read_delim`        | `(delim: byte) -> string?`                           | Reads through one delimiter byte; excludes and consumes it.                         |
| `read_delim_any`    | `(delims: string) -> string?`                        | Reads through any byte in a non-empty delimiter set.                                |
| `read_delim_ws`     | `() -> string?`                                      | Skips leading ASCII whitespace, then reads one whitespace-delimited token.          |
| `read_i`            | `() -> int?`                                         | Parses the next whitespace token as `int`; `null` on EOF, invalid text, or range.   |
| `read_ui`           | `() -> uint?`                                        | Parses the next whitespace token as `uint`; `null` on EOF, invalid text, or range.  |
| `read_l`            | `() -> long?`                                        | Parses the next whitespace token as `long`; `null` on EOF, invalid text, or range.  |
| `read_ul`           | `() -> ulong?`                                       | Parses the next whitespace token as `ulong`; `null` on EOF, invalid text, or range. |
| `read_stdin_some`   | `(buf: ByteArray*, start: int, count: int) -> int?`  | Reads raw bytes into one checked subrange; `0` means EOF and `null` means error.    |
| `write_stdout_some` | `(buf: ByteArray*, start: int, count: int) -> int?`  | Writes bytes from one checked subrange to stdout.                                   |
| `write_stderr_some` | `(buf: ByteArray*, start: int, count: int) -> int?`  | Writes bytes from one checked subrange to stderr.                                   |
| `write_stdout_all`  | `(buf: ByteArray*, start: int, count: int) -> Unit?` | Writes exactly `count` bytes from one checked subrange to stdout or returns `null`. |
| `write_stderr_all`  | `(buf: ByteArray*, start: int, count: int) -> Unit?` | Writes exactly `count` bytes from one checked subrange to stderr or returns `null`. |
| `flush_stdout`      | `() -> void`                                         | Flushes stdout.                                                                     |
| `flush_stderr`      | `() -> void`                                         | Flushes stderr.                                                                     |
| `printl`            | `() -> void`                                         | Prints newline to stdout.                                                           |
| `print_s`           | `(s: string) -> void`                                | Prints string to stdout.                                                            |
| `print_i`           | `(x: int) -> void`                                   | Prints int to stdout.                                                               |
| `print_ui`          | `(x: uint) -> void`                                  | Prints uint to stdout.                                                              |
| `print_l`           | `(x: long) -> void`                                  | Prints long to stdout.                                                              |
| `print_ul`          | `(x: ulong) -> void`                                 | Prints ulong to stdout.                                                             |
| `print_f`           | `(x: float) -> void`                                 | Prints float to stdout.                                                             |
| `print_d`           | `(x: double) -> void`                                | Prints double to stdout.                                                            |
| `print_b`           | `(x: bool) -> void`                                  | Prints bool to stdout.                                                              |
| `printl_s`          | `(s: string) -> void`                                | Prints string + newline to stdout.                                                  |
| `printl_i`          | `(x: int) -> void`                                   | Prints int + newline to stdout.                                                     |
| `printl_ui`         | `(x: uint) -> void`                                  | Prints uint + newline to stdout.                                                    |
| `printl_l`          | `(x: long) -> void`                                  | Prints long + newline to stdout.                                                    |
| `printl_ul`         | `(x: ulong) -> void`                                 | Prints ulong + newline to stdout.                                                   |
| `printl_f`          | `(x: float) -> void`                                 | Prints float + newline to stdout.                                                   |
| `printl_d`          | `(x: double) -> void`                                | Prints double + newline to stdout.                                                  |
| `printl_b`          | `(x: bool) -> void`                                  | Prints bool + newline to stdout.                                                    |
| `print_ss`          | `(s1: string, s2: string) -> void`                   | Prints two values separated by space.                                               |
| `print_si`          | `(s: string, x: int) -> void`                        | Prints two values separated by space.                                               |
| `print_sb`          | `(s: string, b: bool) -> void`                       | Prints two values separated by space.                                               |
| `print_is`          | `(x: int, s: string) -> void`                        | Prints two values separated by space.                                               |
| `print_ii`          | `(x1: int, x2: int) -> void`                         | Prints two values separated by space.                                               |
| `print_ib`          | `(x: int, b: bool) -> void`                          | Prints two values separated by space.                                               |
| `print_bs`          | `(b: bool, s: string) -> void`                       | Prints two values separated by space.                                               |
| `print_bi`          | `(b: bool, x: int) -> void`                          | Prints two values separated by space.                                               |
| `print_bb`          | `(b1: bool, b2: bool) -> void`                       | Prints two values separated by space.                                               |
| `printl_ss`         | `(s1: string, s2: string) -> void`                   | `print_ss` + newline.                                                               |
| `printl_si`         | `(s: string, x: int) -> void`                        | `print_si` + newline.                                                               |
| `printl_sb`         | `(s: string, b: bool) -> void`                       | `print_sb` + newline.                                                               |
| `printl_is`         | `(x: int, s: string) -> void`                        | `print_is` + newline.                                                               |
| `printl_ii`         | `(x1: int, x2: int) -> void`                         | `print_ii` + newline.                                                               |
| `printl_ib`         | `(x: int, b: bool) -> void`                          | `print_ib` + newline.                                                               |
| `printl_bs`         | `(b: bool, s: string) -> void`                       | `print_bs` + newline.                                                               |
| `printl_bi`         | `(b: bool, x: int) -> void`                          | `print_bi` + newline.                                                               |
| `printl_bb`         | `(b1: bool, b2: bool) -> void`                       | `print_bb` + newline.                                                               |
| `err_printl`        | `() -> void`                                         | Prints newline to stderr.                                                           |
| `err_print_s`       | `(s: string) -> void`                                | Prints string to stderr.                                                            |
| `err_print_i`       | `(x: int) -> void`                                   | Prints int to stderr.                                                               |
| `err_print_ui`      | `(x: uint) -> void`                                  | Prints uint to stderr.                                                              |
| `err_print_l`       | `(x: long) -> void`                                  | Prints long to stderr.                                                              |
| `err_print_ul`      | `(x: ulong) -> void`                                 | Prints ulong to stderr.                                                             |
| `err_print_f`       | `(x: float) -> void`                                 | Prints float to stderr.                                                             |
| `err_print_d`       | `(x: double) -> void`                                | Prints double to stderr.                                                            |
| `err_print_b`       | `(x: bool) -> void`                                  | Prints bool to stderr.                                                              |
| `err_printl_s`      | `(s: string) -> void`                                | Prints string + newline to stderr.                                                  |
| `err_printl_i`      | `(x: int) -> void`                                   | Prints int + newline to stderr.                                                     |
| `err_printl_ui`     | `(x: uint) -> void`                                  | Prints uint + newline to stderr.                                                    |
| `err_printl_l`      | `(x: long) -> void`                                  | Prints long + newline to stderr.                                                    |
| `err_printl_ul`     | `(x: ulong) -> void`                                 | Prints ulong + newline to stderr.                                                   |
| `err_printl_f`      | `(x: float) -> void`                                 | Prints float + newline to stderr.                                                   |
| `err_printl_d`      | `(x: double) -> void`                                | Prints double + newline to stderr.                                                  |
| `err_printl_b`      | `(x: bool) -> void`                                  | Prints bool + newline to stderr.                                                    |
| `err_print_ss`      | `(s1: string, s2: string) -> void`                   | Prints two values separated by space.                                               |
| `err_print_si`      | `(s: string, x: int) -> void`                        | Prints two values separated by space.                                               |
| `err_print_sb`      | `(s: string, b: bool) -> void`                       | Prints two values separated by space.                                               |
| `err_print_is`      | `(x: int, s: string) -> void`                        | Prints two values separated by space.                                               |
| `err_print_ii`      | `(x1: int, x2: int) -> void`                         | Prints two values separated by space.                                               |
| `err_print_ib`      | `(x: int, b: bool) -> void`                          | Prints two values separated by space.                                               |
| `err_print_bs`      | `(b: bool, s: string) -> void`                       | Prints two values separated by space.                                               |
| `err_print_bi`      | `(b: bool, x: int) -> void`                          | Prints two values separated by space.                                               |
| `err_print_bb`      | `(b1: bool, b2: bool) -> void`                       | Prints two values separated by space.                                               |

### `std.math`

**Imports:** `std.assert`

Integer helper module. The unsuffixed surface is the shared `int` API; L1-only fixed-width helpers use explicit `_ui`,
`_l`, and `_ul` suffixes for `uint`, `long`, and `ulong`. Floating-point helpers stay out of `std.math`.

| Function      | Signature                           | Description                                                                                               |
| ------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `emod`        | `(a: int, b: int) -> int`           | Euclidean modulo. Requires `b > 0`; always returns a result in `[0, b)`.                                  |
| `ediv`        | `(a: int, b: int) -> int`           | Euclidean quotient paired with `emod`. Requires `b > 0`.                                                  |
| `div_floor`   | `(a: int, b: int) -> int`           | Mathematical floor quotient. Requires `b != 0` and a representable result (excluding `int_min() / -1`).   |
| `div_ceil`    | `(a: int, b: int) -> int`           | Mathematical ceiling quotient. Requires `b != 0` and a representable result (excluding `int_min() / -1`). |
| `min`         | `(a: int, b: int) -> int`           | Returns the smaller operand.                                                                              |
| `max`         | `(a: int, b: int) -> int`           | Returns the larger operand.                                                                               |
| `clamp`       | `(x: int, lo: int, hi: int) -> int` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                          |
| `sign`        | `(x: int) -> int`                   | Returns `-1`, `0`, or `1` based on the sign of `x`.                                                       |
| `is_even`     | `(x: int) -> bool`                  | Returns whether `x` is evenly divisible by 2.                                                             |
| `is_odd`      | `(x: int) -> bool`                  | Returns whether `x` is not evenly divisible by 2.                                                         |
| `is_multiple` | `(a: int, b: int) -> bool`          | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                        |
| `abs`         | `(x: int) -> int?`                  | Absolute value. Returns `null` when the mathematical result is not representable as `int`.                |
| `gcd`         | `(a: int, b: int) -> int?`          | Non-negative greatest common divisor. Returns `null` when the mathematical result is not representable.   |
| `lcm`         | `(a: int, b: int) -> int?`          | Non-negative least common multiple. Returns `null` on overflow or non-representable results.              |
| `pow`         | `(base: int, exp: int) -> int?`     | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                         |
| `isqrt`       | `(x: int) -> int?`                  | Floor integer square root. Returns `null` when `x < 0`.                                                   |
| `align_down`  | `(x: int, align: int) -> int?`      | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.     |
| `align_up`    | `(x: int, align: int) -> int?`      | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.       |
| `is_aligned`  | `(x: int, align: int) -> bool`      | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                                  |

Unsigned `uint` helpers use ordinary unsigned division names because Euclidean and ordinary unsigned division coincide.

| Function         | Signature                               | Description                                                                                         |
| ---------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `div_ui`         | `(a: uint, b: uint) -> uint`            | Unsigned quotient. Requires `b != 0`.                                                               |
| `mod_ui`         | `(a: uint, b: uint) -> uint`            | Unsigned remainder. Requires `b != 0`.                                                              |
| `div_ceil_ui`    | `(a: uint, b: uint) -> uint`            | Unsigned ceiling quotient. Requires `b != 0`.                                                       |
| `min_ui`         | `(a: uint, b: uint) -> uint`            | Returns the smaller operand.                                                                        |
| `max_ui`         | `(a: uint, b: uint) -> uint`            | Returns the larger operand.                                                                         |
| `clamp_ui`       | `(x: uint, lo: uint, hi: uint) -> uint` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                    |
| `is_even_ui`     | `(x: uint) -> bool`                     | Returns whether `x` is evenly divisible by 2.                                                       |
| `is_odd_ui`      | `(x: uint) -> bool`                     | Returns whether `x` is not evenly divisible by 2.                                                   |
| `is_multiple_ui` | `(a: uint, b: uint) -> bool`            | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                  |
| `gcd_ui`         | `(a: uint, b: uint) -> uint`            | Greatest common divisor.                                                                            |
| `lcm_ui`         | `(a: uint, b: uint) -> uint?`           | Least common multiple. Returns `null` on overflow.                                                  |
| `pow_ui`         | `(base: uint, exp: int) -> uint?`       | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                   |
| `isqrt_ui`       | `(x: uint) -> uint`                     | Floor integer square root.                                                                          |
| `align_down_ui`  | `(x: uint, align: uint) -> uint`        | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`.                           |
| `align_up_ui`    | `(x: uint, align: uint) -> uint?`       | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow. |
| `is_aligned_ui`  | `(x: uint, align: uint) -> bool`        | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                            |

Signed `long` helpers mirror the shared signed policy, including nullable results for `LONG_MIN` representability and
overflow edges.

| Function        | Signature                               | Description                                                                                                |
| --------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `emod_l`        | `(a: long, b: long) -> long`            | Euclidean modulo. Requires `b > 0`; always returns a result in `[0, b)`.                                   |
| `ediv_l`        | `(a: long, b: long) -> long`            | Euclidean quotient paired with `emod_l`. Requires `b > 0`.                                                 |
| `div_floor_l`   | `(a: long, b: long) -> long`            | Mathematical floor quotient. Requires `b != 0` and a representable result (excluding `long_min() / -1`).   |
| `div_ceil_l`    | `(a: long, b: long) -> long`            | Mathematical ceiling quotient. Requires `b != 0` and a representable result (excluding `long_min() / -1`). |
| `min_l`         | `(a: long, b: long) -> long`            | Returns the smaller operand.                                                                               |
| `max_l`         | `(a: long, b: long) -> long`            | Returns the larger operand.                                                                                |
| `clamp_l`       | `(x: long, lo: long, hi: long) -> long` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                           |
| `sign_l`        | `(x: long) -> int`                      | Returns `-1`, `0`, or `1` based on the sign of `x`.                                                        |
| `is_even_l`     | `(x: long) -> bool`                     | Returns whether `x` is evenly divisible by 2.                                                              |
| `is_odd_l`      | `(x: long) -> bool`                     | Returns whether `x` is not evenly divisible by 2.                                                          |
| `is_multiple_l` | `(a: long, b: long) -> bool`            | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                         |
| `abs_l`         | `(x: long) -> long?`                    | Absolute value. Returns `null` when the mathematical result is not representable as `long`.                |
| `gcd_l`         | `(a: long, b: long) -> long?`           | Non-negative greatest common divisor. Returns `null` when the mathematical result is not representable.    |
| `lcm_l`         | `(a: long, b: long) -> long?`           | Non-negative least common multiple. Returns `null` on overflow or non-representable results.               |
| `pow_l`         | `(base: long, exp: int) -> long?`       | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                          |
| `isqrt_l`       | `(x: long) -> long?`                    | Floor integer square root. Returns `null` when `x < 0`.                                                    |
| `align_down_l`  | `(x: long, align: long) -> long?`       | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.      |
| `align_up_l`    | `(x: long, align: long) -> long?`       | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow.        |
| `is_aligned_l`  | `(x: long, align: long) -> bool`        | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                                   |

Unsigned `ulong` helpers intentionally omit signed-only concepts such as `sign_ul`, `abs_ul`, `ediv_ul`, and `emod_ul`.

| Function         | Signature                                   | Description                                                                                         |
| ---------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `div_ul`         | `(a: ulong, b: ulong) -> ulong`             | Unsigned quotient. Requires `b != 0`.                                                               |
| `mod_ul`         | `(a: ulong, b: ulong) -> ulong`             | Unsigned remainder. Requires `b != 0`.                                                              |
| `div_ceil_ul`    | `(a: ulong, b: ulong) -> ulong`             | Unsigned ceiling quotient. Requires `b != 0`.                                                       |
| `min_ul`         | `(a: ulong, b: ulong) -> ulong`             | Returns the smaller operand.                                                                        |
| `max_ul`         | `(a: ulong, b: ulong) -> ulong`             | Returns the larger operand.                                                                         |
| `clamp_ul`       | `(x: ulong, lo: ulong, hi: ulong) -> ulong` | Clamps `x` into `[lo, hi]`. Requires `lo <= hi`.                                                    |
| `is_even_ul`     | `(x: ulong) -> bool`                        | Returns whether `x` is evenly divisible by 2.                                                       |
| `is_odd_ul`      | `(x: ulong) -> bool`                        | Returns whether `x` is not evenly divisible by 2.                                                   |
| `is_multiple_ul` | `(a: ulong, b: ulong) -> bool`              | Returns whether `a` is evenly divisible by `b`. Requires `b != 0`.                                  |
| `gcd_ul`         | `(a: ulong, b: ulong) -> ulong`             | Greatest common divisor.                                                                            |
| `lcm_ul`         | `(a: ulong, b: ulong) -> ulong?`            | Least common multiple. Returns `null` on overflow.                                                  |
| `pow_ul`         | `(base: ulong, exp: int) -> ulong?`         | Integer exponentiation. Returns `null` for `exp < 0` or overflow.                                   |
| `isqrt_ul`       | `(x: ulong) -> ulong`                       | Floor integer square root.                                                                          |
| `align_down_ul`  | `(x: ulong, align: ulong) -> ulong`         | Rounds `x` down to the nearest multiple of `align`. Requires `align > 0`.                           |
| `align_up_ul`    | `(x: ulong, align: ulong) -> ulong?`        | Rounds `x` up to the nearest multiple of `align`. Requires `align > 0`; returns `null` on overflow. |
| `is_aligned_ul`  | `(x: ulong, align: ulong) -> bool`          | Returns whether `x` is already aligned to `align`. Requires `align > 0`.                            |

### `std.real`

**Imports:** `sys.real`

Floating-point helper module for classification, basic operations, rounding, remainder/decomposition, and transcendental
math.

`PI_F`, `PI`, `E_F`, `E`, `NAN_F`, `NAN`, `INFINITY_F`, and `INFINITY` are module-level `let` values. Stage 1 now lowers
runtime-initialized top-level `let` bindings through hidden module-init functions that run before user `main`.

| Member         | Signature / Type                                          | Description                                                           |
| -------------- | --------------------------------------------------------- | --------------------------------------------------------------------- |
| `PI_F`         | `float`                                                   | Single-precision approximation of pi.                                 |
| `PI`           | `double`                                                  | Double-precision approximation of pi.                                 |
| `E_F`          | `float`                                                   | Single-precision approximation of Euler's number.                     |
| `E`            | `double`                                                  | Double-precision approximation of Euler's number.                     |
| `NAN_F`        | `float`                                                   | Single-precision NaN value.                                           |
| `NAN`          | `double`                                                  | Double-precision NaN value.                                           |
| `INFINITY_F`   | `float`                                                   | Single-precision positive infinity.                                   |
| `INFINITY`     | `double`                                                  | Double-precision positive infinity.                                   |
| `is_nan_*`     | `(x: float) -> bool`, `(x: double) -> bool`               | Returns true if `x` is NaN.                                           |
| `is_inf_*`     | `(x: float) -> bool`, `(x: double) -> bool`               | Returns true if `x` is positive or negative infinity.                 |
| `is_finite_*`  | `(x: float) -> bool`, `(x: double) -> bool`               | Returns true if `x` is neither NaN nor infinite.                      |
| `signbit_*`    | `(x: float) -> bool`, `(x: double) -> bool`               | Returns true if the sign bit of `x` is set.                           |
| `abs_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns the absolute value of `x`.                                    |
| `sqrt_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the square root of `x`.                                       |
| `cbrt_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the cube root of `x`.                                         |
| `hypot_*`      | `(x: float, y: float) -> float`, `...`                    | Returns the hypotenuse without intermediate overflow or underflow.    |
| `floor_*`      | `(x: float) -> float`, `(x: double) -> double`            | Returns the largest integral value not greater than `x`.              |
| `ceil_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the smallest integral value not less than `x`.                |
| `trunc_*`      | `(x: float) -> float`, `(x: double) -> double`            | Rounds `x` toward zero to an integral value.                          |
| `round_*`      | `(x: float) -> float`, `(x: double) -> double`            | Rounds `x` to the nearest integral value.                             |
| `fmod_*`       | `(x: float, y: float) -> float`, `...`                    | Returns the floating-point remainder of `x/y`.                        |
| `remainder_*`  | `(x: float, y: float) -> float`, `...`                    | Returns the IEEE 754 floating-point remainder.                        |
| `modf_*`       | `(x: float) -> FracPartsF`, `(x: double) -> FracPartsD`   | Decomposes `x` into integral and fractional parts.                    |
| `frexp_*`      | `(x: float) -> FrexpPartsF`, `(x: double) -> FrexpPartsD` | Decomposes `x` into a normalized fraction and an integral power of 2. |
| `ldexp_*`      | `(x: float, exp: int) -> float`, `...`                    | Multiplies `x` by 2 raised to the power `exp`.                        |
| `copy_sign_*`  | `(x: float, y: float) -> float`, `...`                    | Returns a value with the magnitude of `x` and the sign of `y`.        |
| `next_after_*` | `(x: float, y: float) -> float`, `...`                    | Returns the next representable value of `x` in the direction of `y`.  |
| `exp_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns e raised to the power of `x`.                                 |
| `exp2_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns 2 raised to the power of `x`.                                 |
| `log_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns the natural logarithm of `x`.                                 |
| `log10_*`      | `(x: float) -> float`, `(x: double) -> double`            | Returns the base-10 logarithm of `x`.                                 |
| `log2_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the base-2 logarithm of `x`.                                  |
| `pow_*`        | `(x: float, y: float) -> float`, `...`                    | Returns `x` raised to the power `y`.                                  |
| `sin_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns the sine of `x`.                                              |
| `cos_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns the cosine of `x`.                                            |
| `tan_*`        | `(x: float) -> float`, `(x: double) -> double`            | Returns the tangent of `x`.                                           |
| `asin_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the arc-sine of `x`.                                          |
| `acos_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the arc-cosine of `x`.                                        |
| `atan_*`       | `(x: float) -> float`, `(x: double) -> double`            | Returns the arc-tangent of `x`.                                       |
| `atan2_*`      | `(x: float, y: float) -> float`, `...`                    | Returns the quadrant-aware arc-tangent for the pair `(x, y)`.         |

### `std.optional`

**Imports:** `std.assert`

| Function      | Signature                                   | Description                           |
| ------------- | ------------------------------------------- | ------------------------------------- |
| `unwrap_or_s` | `(opt: string?, default: string) -> string` | Returns value or default.             |
| `unwrap_or_i` | `(opt: int?, default: int) -> int`          | Returns value or default.             |
| `unwrap_or_b` | `(opt: bool?, default: bool) -> bool`       | Returns value or default.             |
| `expect_s`    | `(opt: string?, msg: string) -> string`     | Returns value or aborts with message. |
| `expect_i`    | `(opt: int?, msg: string) -> int`           | Returns value or aborts with message. |
| `expect_b`    | `(opt: bool?, msg: string) -> bool`         | Returns value or aborts with message. |

### `std.path`

**Imports:** `std.string`, `std.text`

| Function        | Signature                               | Description                                                    |
| --------------- | --------------------------------------- | -------------------------------------------------------------- |
| `is_sep`        | `(c: byte) -> bool`                     | Returns whether byte is `/` or `\\`.                           |
| `is_absolute`   | `(path: string) -> bool`                | Supports POSIX absolute paths and Windows drive roots.         |
| `has_parent`    | `(path: string) -> bool`                | Returns whether the path contains a separator.                 |
| `basename`      | `(path: string) -> string`              | Returns final path component with trailing separators trimmed. |
| `parent`        | `(path: string) -> string`              | Returns parent directory or `.` when no parent exists.         |
| `stem`          | `(path: string) -> string`              | Removes the final extension from the basename when present.    |
| `join`          | `(root: string, rel: string) -> string` | Appends one path separator between `root` and `rel`.           |
| `has_extension` | `(path: string, ext: string) -> bool`   | Matches the final basename extension, with or without `.`.     |

### `std.rand`

**Imports:** `sys.rt`

| Function         | Signature                         | Description                                           |
| ---------------- | --------------------------------- | ----------------------------------------------------- |
| `rand_seed`      | `(seed: int) -> void`             | Seeds RNG. `0` selects time-based seed.               |
| `rand_int`       | `(max: int) -> int`               | Returns random int in `[0, max)`.                     |
| `rand_int_range` | `(min: int, max: int) -> int`     | Returns random int in `[min, max)`.                   |
| `rand_bool`      | `() -> bool`                      | Returns random bool.                                  |
| `rand_dice`      | `(sides: int, rolls: int) -> int` | Rolls `rolls` dice of `sides` sides and sums results. |

### `std.string`

**Imports:** `sys.rt`, `std.assert`

| Function        | Signature                                             | Description                                                              |
| --------------- | ----------------------------------------------------- | ------------------------------------------------------------------------ |
| `len_s`         | `(s: string) -> int`                                  | Returns string byte length.                                              |
| `is_empty_s`    | `(s: string) -> bool`                                 | Returns whether string length is zero.                                   |
| `char_at_s`     | `(s: string, index: int) -> byte`                     | Returns byte at index.                                                   |
| `eq_s`          | `(a: string, b: string) -> bool`                      | Compares strings for equality.                                           |
| `cmp_s`         | `(a: string, b: string) -> int`                       | Compares strings lexicographically (`<0`, `0`, `>0`).                    |
| `concat_s`      | `(a: string, b: string) -> string`                    | Concatenates strings (equivalent to `+`).                                |
| `slice_s`       | `(s: string, start: int, end: int) -> string`         | Returns substring `[start, end)`.                                        |
| `byte_to_s`     | `(b: byte) -> string`                                 | Creates one-character string from a byte value.                          |
| `bytes_to_s`    | `(bytes: byte*, len: int) -> string`                  | Creates string from byte buffer.                                         |
| `find_s`        | `(haystack: string, needle: string) -> int`           | Returns first match index or `-1`.                                       |
| `find_last_s`   | `(haystack: string, needle: string) -> int`           | Returns last match index or `-1` (`len_s(haystack)` for empty needle).   |
| `find_from_s`   | `(haystack: string, needle: string, pos: int) -> int` | Returns first match index at/after `pos`, or `-1`. Requires `pos >= 0`.  |
| `contains_s`    | `(haystack: string, needle: string) -> bool`          | Returns whether `needle` occurs in `haystack`.                           |
| `starts_with_s` | `(s: string, prefix: string) -> bool`                 | Returns whether `s` starts with `prefix`.                                |
| `ends_with_s`   | `(s: string, suffix: string) -> bool`                 | Returns whether `s` ends with `suffix`.                                  |
| `is_space`      | `(c: byte) -> bool`                                   | Whitespace check (`' '`, `'\n'`, `'\t'`, `'\r'`).                        |
| `is_digit`      | `(c: byte) -> bool`                                   | Decimal digit check (`'0'..'9'`).                                        |
| `is_digit_base` | `(c: byte, base: int) -> bool`                        | Valid digit check for base `2..16`.                                      |
| `is_alpha`      | `(c: byte) -> bool`                                   | ASCII alphabetic check.                                                  |
| `is_alnum`      | `(c: byte) -> bool`                                   | ASCII alphanumeric check.                                                |
| `to_digit`      | `(c: byte) -> int`                                    | Converts decimal ASCII digit byte to integer value.                      |
| `to_digit_base` | `(c: byte, base: int) -> int?`                        | Converts base `2..16` digit byte to integer value or `null`.             |
| `to_upper`      | `(c: byte) -> byte`                                   | Uppercases ASCII letter; returns input otherwise.                        |
| `to_lower`      | `(c: byte) -> byte`                                   | Lowercases ASCII letter; returns input otherwise.                        |
| `trim_s`        | `(s: string) -> string`                               | Trims leading/trailing ASCII whitespace (`' '`, `'\n'`, `'\t'`, `'\r'`). |

### `std.system`

**Imports:** `sys.rt`

| Function  | Signature                       | Description                                                         |
| --------- | ------------------------------- | ------------------------------------------------------------------- |
| `exit`    | `(code: int) -> void`           | Exits program with status code.                                     |
| `env_get` | `(var_name: string) -> string?` | Returns environment variable or `null`.                             |
| `argc`    | `() -> int`                     | Returns command-line argument count.                                |
| `get_pid` | `() -> int`                     | Returns the current process identifier.                             |
| `argv`    | `(index: int) -> string`        | Returns command-line argument string at index.                      |
| `abort`   | `(message: string) -> void`     | Aborts program with message.                                        |
| `errno`   | `() -> int`                     | Returns runtime error number.                                       |
| `system`  | `(cmd: string) -> int`          | Executes command in shell and returns normalized child exit status. |

### `std.text`

**Imports:** `std.string`, `std.math`, `std.assert`, `std.vector`

| Type/Function                                       | Signature                                                                                           | Description                                                                                               |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `StringBuffer`                                      | `struct`                                                                                            | String-part buffer with cached total size.                                                                |
| `sb_*`                                              | `create/append/append_int/append_byte/to_string/size/free`                                          | String buffer API.                                                                                        |
| `CharBuffer`                                        | `struct`                                                                                            | Byte-backed buffer for incremental string assembly.                                                       |
| `cb_*`                                              | `create/capacity/size/reserve/append/append_s/append_slice/append_int/reverse/to_string/clear/free` | Char buffer API.                                                                                          |
| `to_upper_s/to_lower_s`                             | case helpers                                                                                        | Convert full string case.                                                                                 |
| `repeat_s/reverse_s`                                | string helpers                                                                                      | Repeat or reverse string content.                                                                         |
| `split_s`                                           | `(s: string, sep: string) -> VectorString*`                                                         | Splits by non-empty separator and keeps empty tokens. Caller owns result (`vs_free`).                     |
| `lines_s`                                           | `(s: string) -> VectorString*`                                                                      | Splits on `\n`, strips trailing `\r` per line. Caller owns result (`vs_free`).                            |
| `join_s`                                            | `(parts: VectorString*, sep: string) -> string`                                                     | Joins vector elements with separator.                                                                     |
| `replace_s`                                         | `(s: string, old: string, replacement: string) -> string`                                           | Replaces all non-overlapping matches of non-empty `old` with `replacement`.                               |
| `int_to_string_base`                                | `(value: int, base: int) -> string`                                                                 | Base conversion for signed ints (`2..16`).                                                                |
| `int_to_string/int_to_hex_string/int_to_bin_string` | format helpers                                                                                      | Decimal, hex, and binary formatting helpers.                                                              |
| `bool_to_string/string_to_bool`                     | `(bool) -> string`, `(string) -> bool?`                                                             | Converts booleans to `"true"`/`"false"` and parses strict lowercase boolean text.                         |
| `byte_to_string/byte_to_string_base`                | `(byte) -> string`, `(byte, base: int) -> string`                                                   | Numeric byte formatting (decimal or base `2..16`).                                                        |
| `uint_to_string/uint_to_string_base`                | `(uint) -> string`, `(uint, base: int) -> string`                                                   | Numeric uint formatting (decimal or base `2..16`).                                                        |
| `long_to_string/long_to_string_base`                | `(long) -> string`, `(long, base: int) -> string`                                                   | Numeric long formatting (decimal or base `2..16`).                                                        |
| `ulong_to_string/ulong_to_string_base`              | `(ulong) -> string`, `(ulong, base: int) -> string`                                                 | Numeric ulong formatting (decimal or base `2..16`).                                                       |
| `string_to_int`                                     | `(s: string) -> int?`                                                                               | Parses decimal signed integer text; returns `null` on invalid input or 32-bit overflow/underflow.         |
| `string_to_int_base`                                | `(s: string, base: int) -> int?`                                                                    | Parses signed integer text in base `2..16`; returns `null` on invalid input or 32-bit overflow/underflow. |
| `string_to_byte/string_to_byte_base`                | `(s: string) -> byte?`, `(s: string, base: int) -> byte?`                                           | Parses numeric byte text; returns `null` on invalid input or out-of-range values (`0..255`).              |
| `string_to_uint/string_to_uint_base`                | `(s: string) -> uint?`, `(s: string, base: int) -> uint?`                                           | Parses unsigned integer text; rejects negative or out-of-range values.                                    |
| `string_to_long/string_to_long_base`                | `(s: string) -> long?`, `(s: string, base: int) -> long?`                                           | Parses signed 64-bit integer text; returns `null` on invalid input or overflow/underflow.                 |
| `string_to_ulong/string_to_ulong_base`              | `(s: string) -> ulong?`, `(s: string, base: int) -> ulong?`                                         | Parses unsigned 64-bit integer text; rejects negative or out-of-range values.                             |

### `std.time`

**Imports:** `sys.rt`, `std.math`

| Type/Function            | Signature                                                 | Description                                                    |
| ------------------------ | --------------------------------------------------------- | -------------------------------------------------------------- |
| `WallTime`               | `struct { sec: int; nsec: int; }`                         | Unix wall-clock snapshot with nanosecond fraction.             |
| `MonotonicTime`          | `struct { sec: int; nsec: int; }`                         | Monotonic-clock snapshot with nanosecond fraction.             |
| `Duration`               | `struct { sec: int; nsec: int; }`                         | Non-negative normalized duration (`0 <= nsec < 1e9`).          |
| `DateTime`               | `struct`                                                  | Calendar breakdown (date/time, weekday, yearday, offset, DST). |
| `wall_now`               | `() -> WallTime?`                                         | Captures current wall-clock time.                              |
| `monotonic_supported`    | `() -> bool`                                              | Returns monotonic clock capability.                            |
| `monotonic_now`          | `() -> MonotonicTime?`                                    | Captures current monotonic time when supported.                |
| `monotonic_diff`         | `(start: MonotonicTime, end: MonotonicTime) -> Duration?` | Returns `end - start` or `null` for invalid/reversed inputs.   |
| `wall_to_utc_datetime`   | `(t: WallTime) -> DateTime?`                              | Converts wall time to UTC calendar representation.             |
| `wall_to_local_datetime` | `(t: WallTime) -> DateTime?`                              | Converts wall time to local calendar representation.           |
| `utc_now_datetime`       | `() -> DateTime?`                                         | Convenience wrapper for current UTC calendar time.             |
| `local_now_datetime`     | `() -> DateTime?`                                         | Convenience wrapper for current local calendar time.           |

### `std.unit`

| Type/Function | Signature        | Description                     |
| ------------- | ---------------- | ------------------------------- |
| `Unit`        | `struct Unit {}` | Unit type.                      |
| `unit`        | `() -> Unit`     | Returns unit value.             |
| `present`     | `() -> Unit?`    | Returns non-null optional unit. |

### `sys.hash`

Low-level runtime FFI for hashing raw values and pointers. Uses the siphash-1-3 algorithm. Used by `std.hashmap` and
`std.hashset` for hash calculations.

### `sys.rt`

Low-level runtime FFI for strings, I/O, process/system, time, and errors. Also defines `RtTimeParts`
(`struct { sec: int; nsec: int; }`) and `RtFileInfo`
(`struct { exists: bool; is_file: bool; is_dir: bool; size: int?; mtime_sec: int?; mtime_nsec: int?; }`).

### `sys.real`

Low-level runtime FFI for floating-point math helpers. Used by `std.real` for classification, roots,
remainder/decomposition, rounding, and transcendental math.

### `sys.memory`

Low-level raw memory FFI. Misuse can cause undefined behavior.

## FFI Inventory (`extern func` / `unsafe extern func`)

All `extern func` and `unsafe extern func` symbols exposed to L1 from stdlib modules are listed here.

### Declared in `sys.rt` (42)

| Function                      | Signature                                     | Description                            |
| ----------------------------- | --------------------------------------------- | -------------------------------------- |
| `rt_string_get`               | `(s: string, index: int) -> byte`             | Returns one byte from a string.        |
| `rt_string_bytes_ptr`         | `(s: string) -> byte*`                        | Returns a raw pointer to string bytes. |
| `rt_strlen`                   | `(str: string) -> int`                        | Returns string byte length.            |
| `rt_string_equals`            | `(a: string, b: string) -> bool`              | Compares strings for equality.         |
| `rt_string_compare`           | `(a: string, b: string) -> int`               | Compares strings lexicographically.    |
| `rt_string_concat`            | `(a: string, b: string) -> string`            | Concatenates two strings.              |
| `rt_string_slice`             | `(s: string, start: int, end: int) -> string` | Returns a string slice by byte range.  |
| `rt_string_from_byte_array`   | `(bytes: byte*, len: int) -> string`          | Creates a string from raw bytes.       |
| `rt_string_from_byte`         | `(b: byte) -> string`                         | Creates a one-byte string.             |
| `rt_string_retain`            | `(s: string) -> void`                         | Increments heap-string refcount.       |
| `rt_string_release`           | `(s: string) -> void`                         | Decrements heap-string refcount.       |
| `rt_read_file_all`            | `(path: string) -> string?`                   | Reads a whole file into a string.      |
| `rt_write_file_all`           | `(path: string, data: string) -> bool`        | Writes a whole string to a file.       |
| `rt_flush_stdout`             | `() -> void`                                  | Flushes standard output.               |
| `rt_flush_stderr`             | `() -> void`                                  | Flushes standard error.                |
| `rt_print`                    | `(s: string) -> void`                         | Prints a string to stdout.             |
| `rt_print_stderr`             | `(s: string) -> void`                         | Prints a string to stderr.             |
| `rt_println`                  | `() -> void`                                  | Prints a newline to stdout.            |
| `rt_println_stderr`           | `() -> void`                                  | Prints a newline to stderr.            |
| `rt_print_int`                | `(x: int) -> void`                            | Prints an int to stdout.               |
| `rt_print_int_stderr`         | `(x: int) -> void`                            | Prints an int to stderr.               |
| `rt_print_uint`               | `(x: uint) -> void`                           | Prints a uint to stdout.               |
| `rt_print_uint_stderr`        | `(x: uint) -> void`                           | Prints a uint to stderr.               |
| `rt_print_long`               | `(x: long) -> void`                           | Prints a long to stdout.               |
| `rt_print_long_stderr`        | `(x: long) -> void`                           | Prints a long to stderr.               |
| `rt_print_ulong`              | `(x: ulong) -> void`                          | Prints a ulong to stdout.              |
| `rt_print_ulong_stderr`       | `(x: ulong) -> void`                          | Prints a ulong to stderr.              |
| `rt_print_float`              | `(x: float) -> void`                          | Prints a float to stdout.              |
| `rt_print_float_stderr`       | `(x: float) -> void`                          | Prints a float to stderr.              |
| `rt_print_double`             | `(x: double) -> void`                         | Prints a double to stdout.             |
| `rt_print_double_stderr`      | `(x: double) -> void`                         | Prints a double to stderr.             |
| `rt_print_bool`               | `(x: bool) -> void`                           | Prints a bool to stdout.               |
| `rt_print_bool_stderr`        | `(x: bool) -> void`                           | Prints a bool to stderr.               |
| `rt_read_line`                | `() -> string?`                               | Reads one line from stdin.             |
| `rt_read_char`                | `() -> int`                                   | Reads one byte from stdin.             |
| `rt_abort`                    | `(message: string) -> void`                   | Aborts execution with a message.       |
| `rt_exit`                     | `(code: int) -> void`                         | Exits the current process.             |
| `rt_srand`                    | `(seed: int) -> void`                         | Seeds the runtime RNG.                 |
| `rt_rand`                     | `(max: int) -> int`                           | Returns a random int below `max`.      |
| `rt_errno`                    | `() -> int`                                   | Returns the current errno value.       |
| `rt_get_env_var`              | `(name: string) -> string?`                   | Reads an environment variable.         |
| `rt_get_argc`                 | `() -> int`                                   | Returns process argument count.        |
| `rt_get_pid`                  | `() -> int`                                   | Returns the current process id.        |
| `rt_get_argv`                 | `(i: int) -> string`                          | Returns one process argument.          |
| `rt_time_unix`                | `(out: RtTimeParts*) -> bool`                 | Captures wall-clock time.              |
| `rt_time_monotonic`           | `(out: RtTimeParts*) -> bool`                 | Captures monotonic time.               |
| `rt_time_monotonic_supported` | `() -> bool`                                  | Reports monotonic-clock availability.  |
| `rt_time_local_offset_sec`    | `(unix_sec: int) -> int?`                     | Looks up local UTC offset.             |
| `rt_time_local_is_dst`        | `(unix_sec: int) -> bool?`                    | Looks up local DST state.              |
| `rt_system`                   | `(cmd: string) -> int`                        | Runs a shell command.                  |
| `rt_file_info`                | `(path: string) -> RtFileInfo`                | Returns stat-like file metadata.       |
| `rt_delete_file`              | `(path: string) -> bool`                      | Deletes a file by path.                |

### Declared in `sys.memory` (11)

These are unsafe raw-memory primitives.

| Function           | Signature                                                                | Description                  |
| ------------------ | ------------------------------------------------------------------------ | ---------------------------- |
| `rt_alloc`         | `(bytes: int) -> void*?`                                                 | Allocates raw heap memory.   |
| `rt_calloc`        | `(count: int, elem_size: int) -> void*?`                                 | Allocates zeroed raw memory. |
| `rt_realloc`       | `unsafe func(ptr: void*, new_bytes: int) -> void*?`                      | Resizes raw heap memory.     |
| `rt_free`          | `unsafe func(ptr: void*?) -> void`                                       | Frees raw heap memory.       |
| `rt_memcpy`        | `unsafe func(dest: void*, src: void*, bytes: int) -> void*`              | Copies raw bytes.            |
| `rt_memset`        | `unsafe func(dest: void*, value: int, bytes: int) -> void*`              | Fills raw bytes.             |
| `rt_memcmp`        | `unsafe func(a: void*, b: void*, bytes: int) -> int`                     | Compares raw bytes.          |
| `rt_array_element` | `unsafe func(array_data: void*, element_size: int, index: int) -> void*` | Computes an element pointer. |
| `rt_stdin_read`    | `unsafe func(buf: byte*, capacity: int) -> int`                          | Reads raw bytes from stdin.  |
| `rt_stdout_write`  | `unsafe func(buf: byte*, len: int) -> int`                               | Writes raw bytes to stdout.  |
| `rt_stderr_write`  | `unsafe func(buf: byte*, len: int) -> int`                               | Writes raw bytes to stderr.  |

### Declared in `sys.hash` (11)

These are runtime-backed hash externs declared directly in `sys.hash`.

| Function             | Signature                         | Description                     |
| -------------------- | --------------------------------- | ------------------------------- |
| `rt_hash_bool`       | `(value: bool) -> int`            | Hashes a bool value.            |
| `rt_hash_byte`       | `(value: byte) -> int`            | Hashes a byte value.            |
| `rt_hash_int`        | `(value: int) -> int`             | Hashes an int value.            |
| `rt_hash_string`     | `(value: string) -> int`          | Hashes a string value.          |
| `rt_hash_data`       | `(data: void*, size: int) -> int` | Hashes raw byte data.           |
| `rt_hash_opt_bool`   | `(opt: bool?) -> int`             | Hashes an optional bool.        |
| `rt_hash_opt_byte`   | `(opt: byte?) -> int`             | Hashes an optional byte.        |
| `rt_hash_opt_int`    | `(opt: int?) -> int`              | Hashes an optional int.         |
| `rt_hash_opt_string` | `(opt: string?) -> int`           | Hashes an optional string.      |
| `rt_hash_ptr`        | `(ptr: void*) -> int`             | Hashes a raw pointer value.     |
| `rt_hash_opt_ptr`    | `(opt: void*?) -> int`            | Hashes an optional raw pointer. |
