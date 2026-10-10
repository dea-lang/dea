/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

#include "../include/dea_rt.h"

#if defined(DEA_TRACE_ARC) || defined(DEA_TRACE_MEMORY)

#define _RT_TRACE_STDERR_BUFFER_SIZE (64u * 1024u)

static int _rt_trace_flush_each_event = 1;
static int _rt_trace_output_started = 0;
static char _rt_trace_stderr_buffer[_RT_TRACE_STDERR_BUFFER_SIZE];

/** Select the process-wide trace flush policy before user initialization. */
void _rt_trace_init(void) {
    const char *policy = getenv("DEA_TRACE_FLUSH");

    if (_rt_trace_output_started) {
        return;
    }
    if (policy != NULL && strcmp(policy, "block") == 0) {
        if (setvbuf(
                stderr,
                _rt_trace_stderr_buffer,
                _IOFBF,
                sizeof(_rt_trace_stderr_buffer)
            ) == 0) {
            _rt_trace_flush_each_event = 0;
        }
    }
}

/** Flush one completed trace event when the durable policy is active. */
void _rt_trace_event_end(void) {
    _rt_trace_output_started = 1;
    if (_rt_trace_flush_each_event) {
        fflush(stderr);
    }
}

/** Flush pending block-buffered trace bytes at a process boundary. */
void _rt_trace_flush_pending(void) {
    fflush(stderr);
}

#endif
