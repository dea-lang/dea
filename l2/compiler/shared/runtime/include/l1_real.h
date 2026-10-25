/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#ifndef DEA_RUNTIME_REAL_H
#define DEA_RUNTIME_REAL_H

#include <math.h>
#include <stdint.h>
#include <stdbool.h>

/* Helper structs for output parameters matching L1 layout */
#ifndef DEA_DEFINED___deaM3sys4realS10RtFloatOut
#define DEA_DEFINED___deaM3sys4realS10RtFloatOut
struct __deaM3sys4realS10RtFloatOut { dea_float val; };
#endif

#ifndef DEA_DEFINED___deaM3sys4realS11RtDoubleOut
#define DEA_DEFINED___deaM3sys4realS11RtDoubleOut
struct __deaM3sys4realS11RtDoubleOut { dea_double val; };
#endif

#ifndef DEA_DEFINED___deaM3sys4realS8RtIntOut
#define DEA_DEFINED___deaM3sys4realS8RtIntOut
struct __deaM3sys4realS8RtIntOut { dea_int val; };
#endif

/* Constants */

/**
 * Return a quiet NaN in the runtime floating-point format.
 * @return Quiet not-a-number value.
 */
static inline dea_float rt_real_get_nan_f(void) { return (dea_float)NAN; }

/**
 * Return a quiet NaN in the runtime floating-point format.
 * @return Quiet not-a-number value.
 */
static inline dea_double rt_real_get_nan_d(void) { return (dea_double)NAN; }

/**
 * Return positive infinity in the runtime floating-point format.
 * @return Positive infinity.
 */
static inline dea_float rt_real_get_inf_f(void) { return (dea_float)INFINITY; }

/**
 * Return positive infinity in the runtime floating-point format.
 * @return Positive infinity.
 */
static inline dea_double rt_real_get_inf_d(void) { return (dea_double)INFINITY; }

/* Phase 1: Classification */

/**
 * Test whether a floating-point value is NaN.
 *
 * @param x Floating-point input value.
 * @return True exactly when the input is NaN.
 */
static inline dea_bool rt_real_is_nan_f(dea_float x) { return isnan((float)x) != 0; }

/**
 * Test whether a floating-point value is NaN.
 *
 * @param x Floating-point input value.
 * @return True exactly when the input is NaN.
 */
static inline dea_bool rt_real_is_nan_d(dea_double x) { return isnan((double)x) != 0; }

/**
 * Test whether a floating-point value is infinite.
 *
 * @param x Floating-point input value.
 * @return True for either positive or negative infinity.
 */
static inline dea_bool rt_real_is_inf_f(dea_float x) { return isinf((float)x) != 0; }

/**
 * Test whether a floating-point value is infinite.
 *
 * @param x Floating-point input value.
 * @return True for either positive or negative infinity.
 */
static inline dea_bool rt_real_is_inf_d(dea_double x) { return isinf((double)x) != 0; }

/**
 * Test whether a floating-point value is finite.
 *
 * @param x Floating-point input value.
 * @return True for finite values, including signed zero.
 */
static inline dea_bool rt_real_is_finite_f(dea_float x) { return isfinite((float)x) != 0; }

/**
 * Test whether a floating-point value is finite.
 *
 * @param x Floating-point input value.
 * @return True for finite values, including signed zero.
 */
static inline dea_bool rt_real_is_finite_d(dea_double x) { return isfinite((double)x) != 0; }

/**
 * Test the sign bit of a floating-point value.
 *
 * @param x Floating-point input value.
 * @return True when the sign bit is set, including negative zero.
 */
static inline dea_bool rt_real_signbit_f(dea_float x) { return signbit((float)x) != 0; }

/**
 * Test the sign bit of a floating-point value.
 *
 * @param x Floating-point input value.
 * @return True when the sign bit is set, including negative zero.
 */
static inline dea_bool rt_real_signbit_d(dea_double x) { return signbit((double)x) != 0; }

/* Phase 1: Basic ops */

/**
 * Return the floating-point magnitude of the input.
 *
 * @param x Floating-point input value.
 * @return Absolute value under the host math-library semantics.
 */
static inline dea_float rt_real_abs_f(dea_float x) { return fabsf(x); }

/**
 * Return the floating-point magnitude of the input.
 *
 * @param x Floating-point input value.
 * @return Absolute value under the host math-library semantics.
 */
static inline dea_double rt_real_abs_d(dea_double x) { return fabs(x); }

/**
 * Compute the principal floating-point square root.
 *
 * @param x Floating-point input value.
 * @return Square root; negative finite inputs follow host domain-error semantics.
 */
static inline dea_float rt_real_sqrt_f(dea_float x) { return sqrtf(x); }

/**
 * Compute the principal floating-point square root.
 *
 * @param x Floating-point input value.
 * @return Square root; negative finite inputs follow host domain-error semantics.
 */
static inline dea_double rt_real_sqrt_d(dea_double x) { return sqrt(x); }

/**
 * Compute the real floating-point cube root.
 *
 * @param x Floating-point input value.
 * @return Signed real cube root.
 */
static inline dea_float rt_real_cbrt_f(dea_float x) { return cbrtf(x); }

/**
 * Compute the real floating-point cube root.
 *
 * @param x Floating-point input value.
 * @return Signed real cube root.
 */
static inline dea_double rt_real_cbrt_d(dea_double x) { return cbrt(x); }

/**
 * Compute the Euclidean magnitude of two floating-point components.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Square root of the sum of squares under host math-library semantics.
 */
static inline dea_float rt_real_hypot_f(dea_float x, dea_float y) { return hypotf(x, y); }

/**
 * Compute the Euclidean magnitude of two floating-point components.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Square root of the sum of squares under host math-library semantics.
 */
static inline dea_double rt_real_hypot_d(dea_double x, dea_double y) { return hypot(x, y); }

/* Phase 1: Rounding */

/**
 * Round a floating-point value toward negative infinity.
 *
 * @param x Floating-point input value.
 * @return Greatest integral floating-point value no greater than the input.
 */
static inline dea_float rt_real_floor_f(dea_float x) { return floorf(x); }

/**
 * Round a floating-point value toward negative infinity.
 *
 * @param x Floating-point input value.
 * @return Greatest integral floating-point value no greater than the input.
 */
static inline dea_double rt_real_floor_d(dea_double x) { return floor(x); }

/**
 * Round a floating-point value toward positive infinity.
 *
 * @param x Floating-point input value.
 * @return Least integral floating-point value no smaller than the input.
 */
static inline dea_float rt_real_ceil_f(dea_float x) { return ceilf(x); }

/**
 * Round a floating-point value toward positive infinity.
 *
 * @param x Floating-point input value.
 * @return Least integral floating-point value no smaller than the input.
 */
static inline dea_double rt_real_ceil_d(dea_double x) { return ceil(x); }

/**
 * Round a floating-point value toward zero.
 *
 * @param x Floating-point input value.
 * @return Integral floating-point value formed by discarding the fractional part.
 */
static inline dea_float rt_real_trunc_f(dea_float x) { return truncf(x); }

/**
 * Round a floating-point value toward zero.
 *
 * @param x Floating-point input value.
 * @return Integral floating-point value formed by discarding the fractional part.
 */
static inline dea_double rt_real_trunc_d(dea_double x) { return trunc(x); }

/**
 * Round a floating-point value to the nearest integer with halfway cases away from zero.
 *
 * @param x Floating-point input value.
 * @return Rounded integral floating-point value.
 */
static inline dea_float rt_real_round_f(dea_float x) { return roundf(x); }

/**
 * Round a floating-point value to the nearest integer with halfway cases away from zero.
 *
 * @param x Floating-point input value.
 * @return Rounded integral floating-point value.
 */
static inline dea_double rt_real_round_d(dea_double x) { return round(x); }

/* Phase 1: Remainder and decomposition */

/**
 * Compute the floating-point remainder with a quotient truncated toward zero.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Remainder with the input dividend sign; invalid divisors follow host domain rules.
 */
static inline dea_float rt_real_fmod_f(dea_float x, dea_float y) { return fmodf(x, y); }

/**
 * Compute the floating-point remainder with a quotient truncated toward zero.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Remainder with the input dividend sign; invalid divisors follow host domain rules.
 */
static inline dea_double rt_real_fmod_d(dea_double x, dea_double y) { return fmod(x, y); }

/**
 * Compute the IEEE remainder using a nearest-integer quotient.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Remainder under host remainder semantics; invalid divisors follow host domain rules.
 */
static inline dea_float rt_real_remainder_f(dea_float x, dea_float y) { return remainderf(x, y); }

/**
 * Compute the IEEE remainder using a nearest-integer quotient.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Remainder under host remainder semantics; invalid divisors follow host domain rules.
 */
static inline dea_double rt_real_remainder_d(dea_double x, dea_double y) { return remainder(x, y); }

/**
 * Split a floating-point value into fractional and integral parts.
 *
 * @param x Floating-point input value.
 * @param iptr Caller-owned output receiving the integral part.
 * @return Fractional part with the input sign; the integral part is written to iptr.
 */
static inline dea_float rt_real_modf_f(dea_float x, struct __deaM3sys4realS10RtFloatOut* iptr) { return modff(x, (float*)&iptr->val); }

/**
 * Split a floating-point value into fractional and integral parts.
 *
 * @param x Floating-point input value.
 * @param iptr Caller-owned output receiving the integral part.
 * @return Fractional part with the input sign; the integral part is written to iptr.
 */
static inline dea_double rt_real_modf_d(dea_double x, struct __deaM3sys4realS11RtDoubleOut* iptr) { return modf(x, (double*)&iptr->val); }

/**
 * Decompose a floating-point value into a fraction and base-two exponent.
 *
 * @param x Floating-point input value.
 * @param exp Caller-owned output receiving the base-two exponent.
 * @return Signed fraction; its exponent is written to exp under host frexp semantics.
 */
static inline dea_float rt_real_frexp_f(dea_float x, struct __deaM3sys4realS8RtIntOut* exp) { return frexpf(x, (int*)&exp->val); }

/**
 * Decompose a floating-point value into a fraction and base-two exponent.
 *
 * @param x Floating-point input value.
 * @param exp Caller-owned output receiving the base-two exponent.
 * @return Signed fraction; its exponent is written to exp under host frexp semantics.
 */
static inline dea_double rt_real_frexp_d(dea_double x, struct __deaM3sys4realS8RtIntOut* exp) { return frexp(x, (int*)&exp->val); }

/**
 * Scale a floating-point value by an integral power of two.
 *
 * @param x Floating-point input value.
 * @param exp Base-two exponent used to scale the input.
 * @return Scaled value under host overflow and underflow semantics.
 */
static inline dea_float rt_real_ldexp_f(dea_float x, dea_int exp) { return ldexpf(x, (int)exp); }

/**
 * Scale a floating-point value by an integral power of two.
 *
 * @param x Floating-point input value.
 * @param exp Base-two exponent used to scale the input.
 * @return Scaled value under host overflow and underflow semantics.
 */
static inline dea_double rt_real_ldexp_d(dea_double x, dea_int exp) { return ldexp(x, (int)exp); }

/* Phase 1: Sign and neighboring-value helpers */

/**
 * Copy the sign of the second floating-point operand onto the first magnitude.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Magnitude of x with the sign bit of y.
 */
static inline dea_float rt_real_copy_sign_f(dea_float x, dea_float y) { return copysignf(x, y); }

/**
 * Copy the sign of the second floating-point operand onto the first magnitude.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Magnitude of x with the sign bit of y.
 */
static inline dea_double rt_real_copy_sign_d(dea_double x, dea_double y) { return copysign(x, y); }

/**
 * Return the next representable floating-point value toward the second operand.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Adjacent value toward y, or y itself when the operands compare equal.
 */
static inline dea_float rt_real_next_after_f(dea_float x, dea_float y) { return nextafterf(x, y); }

/**
 * Return the next representable floating-point value toward the second operand.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Adjacent value toward y, or y itself when the operands compare equal.
 */
static inline dea_double rt_real_next_after_d(dea_double x, dea_double y) { return nextafter(x, y); }

/* Phase 2: Exponential and logarithmic */

/**
 * Compute the natural floating-point exponential.
 *
 * @param x Floating-point input value.
 * @return Exponential of x under host overflow and underflow semantics.
 */
static inline dea_float rt_real_exp_f(dea_float x) { return expf(x); }

/**
 * Compute the natural floating-point exponential.
 *
 * @param x Floating-point input value.
 * @return Exponential of x under host overflow and underflow semantics.
 */
static inline dea_double rt_real_exp_d(dea_double x) { return exp(x); }

/**
 * Compute the base-two floating-point exponential.
 *
 * @param x Floating-point input value.
 * @return Two raised to x under host overflow and underflow semantics.
 */
static inline dea_float rt_real_exp2_f(dea_float x) { return exp2f(x); }

/**
 * Compute the base-two floating-point exponential.
 *
 * @param x Floating-point input value.
 * @return Two raised to x under host overflow and underflow semantics.
 */
static inline dea_double rt_real_exp2_d(dea_double x) { return exp2(x); }

/**
 * Compute the natural floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Natural logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_float rt_real_log_f(dea_float x) { return logf(x); }

/**
 * Compute the natural floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Natural logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_double rt_real_log_d(dea_double x) { return log(x); }

/**
 * Compute the base-ten floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Base-ten logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_float rt_real_log10_f(dea_float x) { return log10f(x); }

/**
 * Compute the base-ten floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Base-ten logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_double rt_real_log10_d(dea_double x) { return log10(x); }

/**
 * Compute the base-two floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Base-two logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_float rt_real_log2_f(dea_float x) { return log2f(x); }

/**
 * Compute the base-two floating-point logarithm.
 *
 * @param x Floating-point input value.
 * @return Base-two logarithm; nonpositive inputs follow host pole and domain rules.
 */
static inline dea_double rt_real_log2_d(dea_double x) { return log2(x); }

/**
 * Raise a floating-point base to a floating-point exponent.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return x raised to y under host domain, overflow, and underflow semantics.
 */
static inline dea_float rt_real_pow_f(dea_float x, dea_float y) { return powf(x, y); }

/**
 * Raise a floating-point base to a floating-point exponent.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return x raised to y under host domain, overflow, and underflow semantics.
 */
static inline dea_double rt_real_pow_d(dea_double x, dea_double y) { return pow(x, y); }

/* Phase 2: Trigonometric */

/**
 * Compute the floating-point sine of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Sine under host math-library semantics.
 */
static inline dea_float rt_real_sin_f(dea_float x) { return sinf(x); }

/**
 * Compute the floating-point sine of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Sine under host math-library semantics.
 */
static inline dea_double rt_real_sin_d(dea_double x) { return sin(x); }

/**
 * Compute the floating-point cosine of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Cosine under host math-library semantics.
 */
static inline dea_float rt_real_cos_f(dea_float x) { return cosf(x); }

/**
 * Compute the floating-point cosine of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Cosine under host math-library semantics.
 */
static inline dea_double rt_real_cos_d(dea_double x) { return cos(x); }

/**
 * Compute the floating-point tangent of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Tangent under host math-library semantics.
 */
static inline dea_float rt_real_tan_f(dea_float x) { return tanf(x); }

/**
 * Compute the floating-point tangent of an angle in radians.
 *
 * @param x Floating-point input value.
 * @return Tangent under host math-library semantics.
 */
static inline dea_double rt_real_tan_d(dea_double x) { return tan(x); }

/**
 * Compute the principal floating-point inverse sine.
 *
 * @param x Floating-point input value.
 * @return Angle in radians; values outside [-1, 1] follow host domain rules.
 */
static inline dea_float rt_real_asin_f(dea_float x) { return asinf(x); }

/**
 * Compute the principal floating-point inverse sine.
 *
 * @param x Floating-point input value.
 * @return Angle in radians; values outside [-1, 1] follow host domain rules.
 */
static inline dea_double rt_real_asin_d(dea_double x) { return asin(x); }

/**
 * Compute the principal floating-point inverse cosine.
 *
 * @param x Floating-point input value.
 * @return Angle in radians; values outside [-1, 1] follow host domain rules.
 */
static inline dea_float rt_real_acos_f(dea_float x) { return acosf(x); }

/**
 * Compute the principal floating-point inverse cosine.
 *
 * @param x Floating-point input value.
 * @return Angle in radians; values outside [-1, 1] follow host domain rules.
 */
static inline dea_double rt_real_acos_d(dea_double x) { return acos(x); }

/**
 * Compute the principal floating-point inverse tangent.
 *
 * @param x Floating-point input value.
 * @return Angle in radians under host math-library semantics.
 */
static inline dea_float rt_real_atan_f(dea_float x) { return atanf(x); }

/**
 * Compute the principal floating-point inverse tangent.
 *
 * @param x Floating-point input value.
 * @return Angle in radians under host math-library semantics.
 */
static inline dea_double rt_real_atan_d(dea_double x) { return atan(x); }

/**
 * Compute the quadrant-aware inverse tangent of the first operand divided by the second.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Angle in radians equivalent to the host atan2(x, y) call.
 */
static inline dea_float rt_real_atan2_f(dea_float x, dea_float y) { return atan2f(x, y); }

/**
 * Compute the quadrant-aware inverse tangent of the first operand divided by the second.
 *
 * @param x Floating-point input value.
 * @param y Second floating-point operand.
 * @return Angle in radians equivalent to the host atan2(x, y) call.
 */
static inline dea_double rt_real_atan2_d(dea_double x, dea_double y) { return atan2(x, y); }

/* DEA_RUNTIME_REAL_H */
#endif
