/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2025-2026 gwz
 */

#include "../include/dea_rt.h"

/* =========================================================================
 * Runtime support for safe integer arithmetic, narrowing, and checked casts.
 * All operations panic on overflow, division by zero, or out-of-range
 * conversion.
 * ========================================================================= */

/**
 * Safe integer division.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Quotient.
 */
dea_int _rt_idiv(dea_int a, dea_int b) {
    if (b == 0) {
        _rt_panic("division by zero");
    }
    if (a == INT32_MIN && b == -1) {
        _rt_panic("division overflow: INT32_MIN / -1");
    }
    return a / b;
}

/**
 * Safe integer modulo.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Remainder.
 */
dea_int _rt_imod(dea_int a, dea_int b) {
    if (b == 0) {
        _rt_panic("modulo by zero");
    }
    if (a == INT32_MIN && b == -1) {
        _rt_panic("modulo overflow: INT32_MIN % -1");
    }
    return a % b;
}

/**
 * Safe integer addition with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Sum.
 */
dea_int _rt_iadd(dea_int a, dea_int b) {
    if ((b > 0 && a > INT32_MAX - b) || (b < 0 && a < INT32_MIN - b)) {
        _rt_panic("integer addition overflow");
    }
    return a + b;
}

/**
 * Safe integer subtraction with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Difference.
 */
dea_int _rt_isub(dea_int a, dea_int b) {
    if ((b < 0 && a > INT32_MAX + b) || (b > 0 && a < INT32_MIN + b)) {
        _rt_panic("integer subtraction overflow");
    }
    return a - b;
}

/**
 * Safe integer multiplication with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Product.
 */
dea_int _rt_imul(dea_int a, dea_int b) {

    /* Zero multiplication always succeeds */
    if (a == 0 || b == 0) {
        return 0;
    }

    /* Special case: -1 * INT32_MIN or INT32_MIN * -1 = 2147483648, which overflows int32_t */
    if ((a == -1 && b == INT32_MIN) || (b == -1 && a == INT32_MIN)) {
        _rt_panic("integer multiplication overflow");
    }

    /* Both operands positive: overflow if a > INT32_MAX / b */
    if (a > 0 && b > 0) {
        if (a > INT32_MAX / b) {
            _rt_panic("integer multiplication overflow");
        }
    }

    /* Both operands negative: result is positive, overflow if a < INT32_MAX / b
     * Note: We already handled the a=-1,b=INT32_MIN case above, so b != INT32_MIN here
     * and INT32_MAX / b is safe */
    else if (a < 0 && b < 0) {
        if (a < INT32_MAX / b) {
            _rt_panic("integer multiplication overflow");
        }
    }

    /* Mixed signs: result is negative or zero */
    else {

        /* We already handled the special cases where b=-1,a=INT32_MIN or a=-1,b=INT32_MIN
         * So all divisions below are safe from overflow */
        if (a > 0) {

            /* a > 0, b < 0: underflow if a > INT32_MIN / b
             * Since b != -1 (handled above), INT32_MIN / b is safe */
            if (b != -1 && a > INT32_MIN / b) {
                _rt_panic("integer multiplication overflow");
            }
        } else {

            /* a < 0, b > 0: underflow if a < INT32_MIN / b */
            if (a < INT32_MIN / b) {
                _rt_panic("integer multiplication overflow");
            }
        }
    }

    return a * b;
}

/**
 * Narrow dea_int to dea_tiny with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_tiny _rt_narrow_dea_tiny(dea_int value) {
    if (value < -128 || value > 127) {
        _rt_panic("integer to tiny cast overflow");
    }
    return (dea_tiny)value;
}

/**
 * Narrow dea_int to dea_byte with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_byte _rt_narrow_dea_byte(dea_int value) {
    if (value < 0 || value > 255) {
        _rt_panic("integer to byte cast overflow");
    }
    return (dea_byte)value;
}

/**
 * Narrow dea_int to dea_short with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_short _rt_narrow_dea_short(dea_int value) {
    if (value < -32768 || value > 32767) {
        _rt_panic("integer to short cast overflow");
    }
    return (dea_short)value;
}

/**
 * Narrow dea_int to dea_ushort with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_ushort _rt_narrow_dea_ushort(dea_int value) {
    if (value < 0 || value > 65535) {
        _rt_panic("integer to ushort cast overflow");
    }
    return (dea_ushort)value;
}

/**
 * Narrow dea_int to dea_uint with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_uint _rt_narrow_dea_uint(dea_int value) {
    if (value < 0) {
        _rt_panic("integer to uint cast overflow");
    }
    return (dea_uint)value;
}

/**
 * Narrow dea_int to dea_ulong with range check.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented in the destination integer type.
 */
dea_ulong _rt_narrow_dea_ulong(dea_int value) {
    if (value < 0) {
        _rt_panic("integer to ulong cast overflow");
    }
    return (dea_ulong)value;
}

/**
 * Safe unsigned integer division.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Quotient.
 */
dea_uint _rt_udiv(dea_uint a, dea_uint b) {
    if (b == 0) {
        _rt_panic("division by zero");
    }
    return a / b;
}

/**
 * Safe unsigned integer modulo.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Remainder.
 */
dea_uint _rt_umod(dea_uint a, dea_uint b) {
    if (b == 0) {
        _rt_panic("modulo by zero");
    }
    return a % b;
}

/**
 * Safe unsigned integer addition with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Sum.
 */
dea_uint _rt_uadd(dea_uint a, dea_uint b) {
    if (UINT32_MAX - a < b) {
        _rt_panic("uint addition overflow");
    }
    return a + b;
}

/**
 * Safe unsigned integer subtraction with underflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Difference.
 */
dea_uint _rt_usub(dea_uint a, dea_uint b) {
    if (a < b) {
        _rt_panic("uint subtraction underflow");
    }
    return a - b;
}

/**
 * Safe unsigned integer multiplication with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Product.
 */
dea_uint _rt_umul(dea_uint a, dea_uint b) {
    if (a == 0 || b == 0) {
        return 0;
    }
    if (a > UINT32_MAX / b) {
        _rt_panic("uint multiplication overflow");
    }
    return a * b;
}

/**
 * Safe 64-bit signed integer division.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Quotient.
 */
dea_long _rt_ldiv(dea_long a, dea_long b) {
    if (b == 0) {
        _rt_panic("division by zero");
    }
    if (a == INT64_MIN && b == -1) {
        _rt_panic("division overflow: INT64_MIN / -1");
    }
    return a / b;
}

/**
 * Safe 64-bit signed integer modulo.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Remainder.
 */
dea_long _rt_lmod(dea_long a, dea_long b) {
    if (b == 0) {
        _rt_panic("modulo by zero");
    }
    if (a == INT64_MIN && b == -1) {
        _rt_panic("modulo overflow: INT64_MIN % -1");
    }
    return a % b;
}

/**
 * Safe 64-bit signed integer addition with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Sum.
 */
dea_long _rt_ladd(dea_long a, dea_long b) {
    if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) {
        _rt_panic("long addition overflow");
    }
    return a + b;
}

/**
 * Safe 64-bit signed integer subtraction with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Difference.
 */
dea_long _rt_lsub(dea_long a, dea_long b) {
    if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b)) {
        _rt_panic("long subtraction overflow");
    }
    return a - b;
}

/**
 * Safe 64-bit signed integer multiplication with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Product.
 */
dea_long _rt_lmul(dea_long a, dea_long b) {
    if (a == 0 || b == 0) {
        return 0;
    }
    if ((a == -1 && b == INT64_MIN) || (b == -1 && a == INT64_MIN)) {
        _rt_panic("long multiplication overflow");
    }
    if (a > 0 && b > 0) {
        if (a > INT64_MAX / b) {
            _rt_panic("long multiplication overflow");
        }
    } else if (a < 0 && b < 0) {
        if (a < INT64_MAX / b) {
            _rt_panic("long multiplication overflow");
        }
    } else {
        if (a > 0) {
            if (b != -1 && a > INT64_MIN / b) {
                _rt_panic("long multiplication overflow");
            }
        } else {
            if (a < INT64_MIN / b) {
                _rt_panic("long multiplication overflow");
            }
        }
    }
    return a * b;
}

/**
 * Safe 64-bit unsigned integer division.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Quotient.
 */
dea_ulong _rt_uldiv(dea_ulong a, dea_ulong b) {
    if (b == 0) {
        _rt_panic("division by zero");
    }
    return a / b;
}

/**
 * Safe 64-bit unsigned integer modulo.
 *
 * @param a Dividend.
 * @param b Divisor.
 * @return Remainder.
 */
dea_ulong _rt_ulmod(dea_ulong a, dea_ulong b) {
    if (b == 0) {
        _rt_panic("modulo by zero");
    }
    return a % b;
}

/**
 * Safe 64-bit unsigned integer addition with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Sum.
 */
dea_ulong _rt_uladd(dea_ulong a, dea_ulong b) {
    if (UINT64_MAX - a < b) {
        _rt_panic("ulong addition overflow");
    }
    return a + b;
}

/**
 * Safe 64-bit unsigned integer subtraction with underflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Difference.
 */
dea_ulong _rt_ulsub(dea_ulong a, dea_ulong b) {
    if (a < b) {
        _rt_panic("ulong subtraction underflow");
    }
    return a - b;
}

/**
 * Safe 64-bit unsigned integer multiplication with overflow check.
 *
 * @param a First operand.
 * @param b Second operand.
 * @return Product.
 */
dea_ulong _rt_ulmul(dea_ulong a, dea_ulong b) {
    if (a == 0 || b == 0) {
        return 0;
    }
    if (a > UINT64_MAX / b) {
        _rt_panic("ulong multiplication overflow");
    }
    return a * b;
}

/**
 * Shift a signed 32-bit integer left with checked representability.
 *
 * Negative operands use mathematical scaling, without a signed C shift.
 * Counts outside 0 through 31 and unrepresentable results panic in every mode.
 *
 * @param a Value to multiply by two raised to b.
 * @param b Shift count in the normalized signed domain.
 * @return Exactly representable signed product.
 */
dea_int _rt_ishl(dea_int a, dea_int b) {
    if (b < 0 || b >= 32) {
        _rt_panic("integer shift count out of range");
    }
    dea_uint magnitude = a < 0 ? (dea_uint)(-(a + 1)) + 1U : (dea_uint)a;
    dea_uint negative_limit = (dea_uint)INT32_MAX + 1U;
    dea_uint limit = a < 0 ? negative_limit : (dea_uint)INT32_MAX;
    if (magnitude > (limit >> b)) {
        _rt_panic("integer left shift overflow");
    }
    dea_uint shifted = magnitude << b;
    if (a < 0) {
        if (shifted == negative_limit) {
            return INT32_MIN;
        }
        return -(dea_int)shifted;
    }
    return (dea_int)shifted;
}

/**
 * Shift a signed 32-bit integer right arithmetically with a checked count.
 *
 * The negative path uses unsigned shifts and representable signed values.
 * Counts outside 0 through 31 panic in every runtime mode.
 *
 * @param a Value whose high sign bits are preserved.
 * @param b Shift count in the normalized signed domain.
 * @return Quotient by two raised to b, rounded toward negative infinity.
 */
dea_int _rt_ishr(dea_int a, dea_int b) {
    if (b < 0 || b >= 32) {
        _rt_panic("integer shift count out of range");
    }
    if (a < 0) {
        return -1 - (dea_int)((dea_uint)(-1 - a) >> b);
    }
    return a >> b;
}

/**
 * Shift an unsigned 32-bit integer left with a checked count.
 *
 * High bits are discarded, preserving fixed-width unsigned bit-pattern behavior.
 * Counts outside 0 through 31 panic in every runtime mode.
 *
 * @param a Bit pattern to shift.
 * @param b Shift count in the normalized unsigned domain.
 * @return Shifted low 32 bits with zero low bits inserted.
 */
dea_uint _rt_ushl(dea_uint a, dea_uint b) {
    if (b >= 32) {
        _rt_panic("uint shift count out of range");
    }
    return a << b;
}

/**
 * Shift an unsigned 32-bit integer right with a checked count.
 *
 * Counts outside 0 through 31 panic in every runtime mode.
 *
 * @param a Bit pattern to shift.
 * @param b Shift count in the normalized unsigned domain.
 * @return Logically shifted value with zero high bits inserted.
 */
dea_uint _rt_ushr(dea_uint a, dea_uint b) {
    if (b >= 32) {
        _rt_panic("uint shift count out of range");
    }
    return a >> b;
}

/**
 * Shift a signed 64-bit integer left with checked representability.
 *
 * Negative operands use mathematical scaling, without a signed C shift.
 * Counts outside 0 through 63 and unrepresentable results panic in every mode.
 *
 * @param a Value to multiply by two raised to b.
 * @param b Shift count in the normalized signed domain.
 * @return Exactly representable signed product.
 */
dea_long _rt_lshl(dea_long a, dea_long b) {
    if (b < 0 || b >= 64) {
        _rt_panic("long shift count out of range");
    }
    dea_ulong magnitude = a < 0 ? (dea_ulong)(-(a + 1)) + 1ULL : (dea_ulong)a;
    dea_ulong negative_limit = (dea_ulong)INT64_MAX + 1ULL;
    dea_ulong limit = a < 0 ? negative_limit : (dea_ulong)INT64_MAX;
    if (magnitude > (limit >> b)) {
        _rt_panic("long left shift overflow");
    }
    dea_ulong shifted = magnitude << b;
    if (a < 0) {
        if (shifted == negative_limit) {
            return INT64_MIN;
        }
        return -(dea_long)shifted;
    }
    return (dea_long)shifted;
}

/**
 * Shift a signed 64-bit integer right arithmetically with a checked count.
 *
 * The negative path uses unsigned shifts and representable signed values.
 * Counts outside 0 through 63 panic in every runtime mode.
 *
 * @param a Value whose high sign bits are preserved.
 * @param b Shift count in the normalized signed domain.
 * @return Quotient by two raised to b, rounded toward negative infinity.
 */
dea_long _rt_lshr(dea_long a, dea_long b) {
    if (b < 0 || b >= 64) {
        _rt_panic("long shift count out of range");
    }
    if (a < 0) {
        return -1 - (dea_long)((dea_ulong)(-1 - a) >> b);
    }
    return a >> b;
}

/**
 * Shift an unsigned 64-bit integer left with a checked count.
 *
 * High bits are discarded, preserving fixed-width unsigned bit-pattern behavior.
 * Counts outside 0 through 63 panic in every runtime mode.
 *
 * @param a Bit pattern to shift.
 * @param b Shift count in the normalized unsigned domain.
 * @return Shifted low 64 bits with zero low bits inserted.
 */
dea_ulong _rt_ulshl(dea_ulong a, dea_ulong b) {
    if (b >= 64) {
        _rt_panic("ulong shift count out of range");
    }
    return a << b;
}

/**
 * Shift an unsigned 64-bit integer right with a checked count.
 *
 * Counts outside 0 through 63 panic in every runtime mode.
 *
 * @param a Bit pattern to shift.
 * @param b Shift count in the normalized unsigned domain.
 * @return Logically shifted value with zero high bits inserted.
 */
dea_ulong _rt_ulshr(dea_ulong a, dea_ulong b) {
    if (b >= 64) {
        _rt_panic("ulong shift count out of range");
    }
    return a >> b;
}

/**
 * Checked cast from signed 64-bit to dea_tiny.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_tiny; an out-of-range input panics.
 */
dea_tiny _rt_cast_dea_tiny_from_signed(dea_long value) {
    if (value < INT8_MIN || value > INT8_MAX) {
        _rt_panic("integer to tiny cast overflow");
    }
    return (dea_tiny)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_tiny.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_tiny; an out-of-range input panics.
 */
dea_tiny _rt_cast_dea_tiny_from_unsigned(dea_ulong value) {
    if (value > (dea_ulong)INT8_MAX) {
        _rt_panic("integer to tiny cast overflow");
    }
    return (dea_tiny)value;
}

/**
 * Checked cast from signed 64-bit to dea_byte.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_byte; an out-of-range input panics.
 */
dea_byte _rt_cast_dea_byte_from_signed(dea_long value) {
    if (value < 0 || value > UINT8_MAX) {
        _rt_panic("integer to byte cast overflow");
    }
    return (dea_byte)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_byte.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_byte; an out-of-range input panics.
 */
dea_byte _rt_cast_dea_byte_from_unsigned(dea_ulong value) {
    if (value > UINT8_MAX) {
        _rt_panic("integer to byte cast overflow");
    }
    return (dea_byte)value;
}

/**
 * Checked cast from signed 64-bit to dea_short.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_short; an out-of-range input panics.
 */
dea_short _rt_cast_dea_short_from_signed(dea_long value) {
    if (value < INT16_MIN || value > INT16_MAX) {
        _rt_panic("integer to short cast overflow");
    }
    return (dea_short)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_short.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_short; an out-of-range input panics.
 */
dea_short _rt_cast_dea_short_from_unsigned(dea_ulong value) {
    if (value > (dea_ulong)INT16_MAX) {
        _rt_panic("integer to short cast overflow");
    }
    return (dea_short)value;
}

/**
 * Checked cast from signed 64-bit to dea_ushort.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_ushort; an out-of-range input panics.
 */
dea_ushort _rt_cast_dea_ushort_from_signed(dea_long value) {
    if (value < 0 || value > UINT16_MAX) {
        _rt_panic("integer to ushort cast overflow");
    }
    return (dea_ushort)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_ushort.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_ushort; an out-of-range input panics.
 */
dea_ushort _rt_cast_dea_ushort_from_unsigned(dea_ulong value) {
    if (value > UINT16_MAX) {
        _rt_panic("integer to ushort cast overflow");
    }
    return (dea_ushort)value;
}

/**
 * Checked cast from signed 64-bit to dea_int.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_int; an out-of-range input panics.
 */
dea_int _rt_cast_dea_int_from_signed(dea_long value) {
    if (value < INT32_MIN || value > INT32_MAX) {
        _rt_panic("integer to int cast overflow");
    }
    return (dea_int)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_int.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_int; an out-of-range input panics.
 */
dea_int _rt_cast_dea_int_from_unsigned(dea_ulong value) {
    if (value > (dea_ulong)INT32_MAX) {
        _rt_panic("integer to int cast overflow");
    }
    return (dea_int)value;
}

/**
 * Checked cast from signed 64-bit to dea_uint.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_uint; an out-of-range input panics.
 */
dea_uint _rt_cast_dea_uint_from_signed(dea_long value) {
    if (value < 0 || value > UINT32_MAX) {
        _rt_panic("integer to uint cast overflow");
    }
    return (dea_uint)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_uint.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_uint; an out-of-range input panics.
 */
dea_uint _rt_cast_dea_uint_from_unsigned(dea_ulong value) {
    if (value > UINT32_MAX) {
        _rt_panic("integer to uint cast overflow");
    }
    return (dea_uint)value;
}

/**
 * Checked cast from signed 64-bit to dea_long.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_long; an out-of-range input panics.
 */
dea_long _rt_cast_dea_long_from_signed(dea_long value) {
    return value;
}

/**
 * Checked cast from unsigned 64-bit to dea_long.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_long; an out-of-range input panics.
 */
dea_long _rt_cast_dea_long_from_unsigned(dea_ulong value) {
    if (value > (dea_ulong)INT64_MAX) {
        _rt_panic("integer to long cast overflow");
    }
    return (dea_long)value;
}

/**
 * Checked cast from signed 64-bit to dea_ulong.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_ulong; an out-of-range input panics.
 */
dea_ulong _rt_cast_dea_ulong_from_signed(dea_long value) {
    if (value < 0) {
        _rt_panic("integer to ulong cast overflow");
    }
    return (dea_ulong)value;
}

/**
 * Checked cast from unsigned 64-bit to dea_ulong.
 *
 * @param value Integer value to convert under the checked range rules.
 * @return Value represented as dea_ulong; an out-of-range input panics.
 */
dea_ulong _rt_cast_dea_ulong_from_unsigned(dea_ulong value) {
    return value;
}
