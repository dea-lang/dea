/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#ifndef DEA_TIME_TEST_FAULTS_H
#define DEA_TIME_TEST_FAULTS_H

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#ifndef _DARWIN_C_SOURCE
#define _DARWIN_C_SOURCE 1
#endif

#include "dea_rt.h"

/* Reset the test clock and fault scenario without reading any host clock. */
void time_probe_config(dea_int value);

/* Report how many clock samples the current scenario consumed. */
dea_int time_probe_reads(void);

/* Report how many host wait attempts the current scenario consumed. */
dea_int time_probe_waits(void);

/* Report wait-context opens since configuration. */
dea_int time_probe_opens(void);

/* Report consumed wait contexts since configuration. */
dea_int time_probe_closes(void);

/* Report the largest requested whole-second wait component. */
dea_long time_probe_max_wait_sec(void);

/* Report the fractional part of the largest requested wait. */
dea_int time_probe_max_wait_nsec(void);

/* Report the original absolute deadline passed to the wait adapter. */
dea_long time_probe_deadline_sec(void);

/* Report the original absolute deadline fraction passed to the wait adapter. */
dea_int time_probe_deadline_nsec(void);

/* Read a deterministic monotonic sample or captured clock failure. */
struct __deaM3sys4timeS12RtTimeResult time_probe_clock(void);

/* Open a test wait context or report its configured failure. */
struct __deaM3sys4timeS12RtTimeResult time_probe_open(void **context);

/* Perform one deterministic wait while retaining the absolute deadline. */
struct __deaM3sys4timeS12RtTimeResult time_probe_wait(void *context, dea_long sec, dea_int nsec,
                                                  dea_long remaining_sec, dea_int remaining_nsec);

/* Consume the test wait context and report its configured cleanup outcome. */
struct __deaM3sys4timeS12RtTimeResult time_probe_close(void *context);

#define DEA_TIME_READ_CLOCK time_probe_clock
#define DEA_TIME_OPEN_WAIT time_probe_open
#define DEA_TIME_WAIT_ONCE time_probe_wait
#define DEA_TIME_CLOSE_WAIT time_probe_close

#endif
