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
#ifndef DEA_DEFINED_dea_sys_real_RtFloatOut
#define DEA_DEFINED_dea_sys_real_RtFloatOut
struct dea_sys_real_RtFloatOut { dea_float val; };
#endif

#ifndef DEA_DEFINED_dea_sys_real_RtDoubleOut
#define DEA_DEFINED_dea_sys_real_RtDoubleOut
struct dea_sys_real_RtDoubleOut { dea_double val; };
#endif

#ifndef DEA_DEFINED_dea_sys_real_RtIntOut
#define DEA_DEFINED_dea_sys_real_RtIntOut
struct dea_sys_real_RtIntOut { dea_int val; };
#endif

/* Constants */
static inline dea_float rt_real_get_nan_f() { return (dea_float)NAN; }
static inline dea_double rt_real_get_nan_d() { return (dea_double)NAN; }
static inline dea_float rt_real_get_inf_f() { return (dea_float)INFINITY; }
static inline dea_double rt_real_get_inf_d() { return (dea_double)INFINITY; }

/* Phase 1: Classification */
static inline dea_bool rt_real_is_nan_f(dea_float x) { return isnan((float)x); }
static inline dea_bool rt_real_is_nan_d(dea_double x) { return isnan((double)x); }
static inline dea_bool rt_real_is_inf_f(dea_float x) { return isinf((float)x); }
static inline dea_bool rt_real_is_inf_d(dea_double x) { return isinf((double)x); }
static inline dea_bool rt_real_is_finite_f(dea_float x) { return isfinite((float)x); }
static inline dea_bool rt_real_is_finite_d(dea_double x) { return isfinite((double)x); }
static inline dea_bool rt_real_signbit_f(dea_float x) { return signbit((float)x); }
static inline dea_bool rt_real_signbit_d(dea_double x) { return signbit((double)x); }

/* Phase 1: Basic ops */
static inline dea_float rt_real_abs_f(dea_float x) { return fabsf(x); }
static inline dea_double rt_real_abs_d(dea_double x) { return fabs(x); }
static inline dea_float rt_real_sqrt_f(dea_float x) { return sqrtf(x); }
static inline dea_double rt_real_sqrt_d(dea_double x) { return sqrt(x); }
static inline dea_float rt_real_cbrt_f(dea_float x) { return cbrtf(x); }
static inline dea_double rt_real_cbrt_d(dea_double x) { return cbrt(x); }
static inline dea_float rt_real_hypot_f(dea_float x, dea_float y) { return hypotf(x, y); }
static inline dea_double rt_real_hypot_d(dea_double x, dea_double y) { return hypot(x, y); }

/* Phase 1: Rounding */
static inline dea_float rt_real_floor_f(dea_float x) { return floorf(x); }
static inline dea_double rt_real_floor_d(dea_double x) { return floor(x); }
static inline dea_float rt_real_ceil_f(dea_float x) { return ceilf(x); }
static inline dea_double rt_real_ceil_d(dea_double x) { return ceil(x); }
static inline dea_float rt_real_trunc_f(dea_float x) { return truncf(x); }
static inline dea_double rt_real_trunc_d(dea_double x) { return trunc(x); }
static inline dea_float rt_real_round_f(dea_float x) { return roundf(x); }
static inline dea_double rt_real_round_d(dea_double x) { return round(x); }

/* Phase 1: Remainder and decomposition */
static inline dea_float rt_real_fmod_f(dea_float x, dea_float y) { return fmodf(x, y); }
static inline dea_double rt_real_fmod_d(dea_double x, dea_double y) { return fmod(x, y); }
static inline dea_float rt_real_remainder_f(dea_float x, dea_float y) { return remainderf(x, y); }
static inline dea_double rt_real_remainder_d(dea_double x, dea_double y) { return remainder(x, y); }
static inline dea_float rt_real_modf_f(dea_float x, struct dea_sys_real_RtFloatOut* iptr) { return modff(x, (float*)&iptr->val); }
static inline dea_double rt_real_modf_d(dea_double x, struct dea_sys_real_RtDoubleOut* iptr) { return modf(x, (double*)&iptr->val); }
static inline dea_float rt_real_frexp_f(dea_float x, struct dea_sys_real_RtIntOut* exp) { return frexpf(x, (int*)&exp->val); }
static inline dea_double rt_real_frexp_d(dea_double x, struct dea_sys_real_RtIntOut* exp) { return frexp(x, (int*)&exp->val); }
static inline dea_float rt_real_ldexp_f(dea_float x, dea_int exp) { return ldexpf(x, (int)exp); }
static inline dea_double rt_real_ldexp_d(dea_double x, dea_int exp) { return ldexp(x, (int)exp); }

/* Phase 1: Sign and neighboring-value helpers */
static inline dea_float rt_real_copy_sign_f(dea_float x, dea_float y) { return copysignf(x, y); }
static inline dea_double rt_real_copy_sign_d(dea_double x, dea_double y) { return copysign(x, y); }
static inline dea_float rt_real_next_after_f(dea_float x, dea_float y) { return nextafterf(x, y); }
static inline dea_double rt_real_next_after_d(dea_double x, dea_double y) { return nextafter(x, y); }

/* Phase 2: Exponential and logarithmic */
static inline dea_float rt_real_exp_f(dea_float x) { return expf(x); }
static inline dea_double rt_real_exp_d(dea_double x) { return exp(x); }
static inline dea_float rt_real_exp2_f(dea_float x) { return exp2f(x); }
static inline dea_double rt_real_exp2_d(dea_double x) { return exp2(x); }
static inline dea_float rt_real_log_f(dea_float x) { return logf(x); }
static inline dea_double rt_real_log_d(dea_double x) { return log(x); }
static inline dea_float rt_real_log10_f(dea_float x) { return log10f(x); }
static inline dea_double rt_real_log10_d(dea_double x) { return log10(x); }
static inline dea_float rt_real_log2_f(dea_float x) { return log2f(x); }
static inline dea_double rt_real_log2_d(dea_double x) { return log2(x); }
static inline dea_float rt_real_pow_f(dea_float x, dea_float y) { return powf(x, y); }
static inline dea_double rt_real_pow_d(dea_double x, dea_double y) { return pow(x, y); }

/* Phase 2: Trigonometric */
static inline dea_float rt_real_sin_f(dea_float x) { return sinf(x); }
static inline dea_double rt_real_sin_d(dea_double x) { return sin(x); }
static inline dea_float rt_real_cos_f(dea_float x) { return cosf(x); }
static inline dea_double rt_real_cos_d(dea_double x) { return cos(x); }
static inline dea_float rt_real_tan_f(dea_float x) { return tanf(x); }
static inline dea_double rt_real_tan_d(dea_double x) { return tan(x); }
static inline dea_float rt_real_asin_f(dea_float x) { return asinf(x); }
static inline dea_double rt_real_asin_d(dea_double x) { return asin(x); }
static inline dea_float rt_real_acos_f(dea_float x) { return acosf(x); }
static inline dea_double rt_real_acos_d(dea_double x) { return acos(x); }
static inline dea_float rt_real_atan_f(dea_float x) { return atanf(x); }
static inline dea_double rt_real_atan_d(dea_double x) { return atan(x); }
static inline dea_float rt_real_atan2_f(dea_float x, dea_float y) { return atan2f(x, y); }
static inline dea_double rt_real_atan2_d(dea_double x, dea_double y) { return atan2(x, y); }

#endif /* DEA_RUNTIME_REAL_H */
