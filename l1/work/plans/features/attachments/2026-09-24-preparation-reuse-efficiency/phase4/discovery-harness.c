/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * @file discovery-harness.c Measure production native identity resolution without a compiler bootstrap.
 */
#include "preparation_support.c"

/**
 * Keep source, semantic inputs, digest backend and identity coverage equal across discovery variants.
 *
 * @param argc Number of process argument words.
 * @param argv Borrowed NUL-terminated process argument vector.
 * @return Zero when all requested checks succeed; nonzero for invalid invocation or a fixture failure.
 */
int main(int argc, char **argv) {
    PcJson *config = pj_new(PJ_OBJECT), *options = pj_new(PJ_ARRAY), *record = pj_new(PJ_OBJECT);
    PcContext *context;
    char *encoded, *output;
    double started;
    int ok;
    if (argc != 9) return 2;
    pj_set_string(record, "label", argv[8]);
    pj_set_string(config, "home", argv[1]);
    pj_set_string(config, "build_dir", argv[2]);
    pj_set_string(config, "self", argv[3]);
    pj_set_string(config, "cache", argv[4]);
    pj_set_string(config, "compiler", argv[5]);
    pj_set_string(config, "runtime_include", argv[6]);
    pj_set_number(config, "verbosity", atoi(argv[7]));
    pj_add(options, NULL, pj_string("-std=c99"));
    pj_add(config, "options", options);
    encoded = pj_encode(config);
    context = l1c_prep_create((const uint8_t *)encoded, (int32_t)strlen(encoded));
    free(encoded); pj_free(config);
    started = pc_milliseconds();
    ok = l1c_prep_resolve(context);
    pj_set_number(record, "elapsed_us", (int64_t)((pc_milliseconds() - started) * 1000.0));
    pj_set_number(record, "success", ok);
    pj_set_number(record, "probes", context->probes);
    pj_set_number(record, "identity_content_reads", context->identity_reads);
    pj_set_string(record, "dea_key", context->dea_key ? context->dea_key : "");
    pj_set_string(record, "native_key", context->native_key ? context->native_key : "");
    if (context->native) pj_add(record, "native_identity", pj_clone(context->native));
    pj_set_string(record, "error", context->error ? context->error : "");
    pj_set_string(record, "ineligible", context->ineligible ? context->ineligible : "");
    output = pj_encode(record); puts(output); free(output);
    pj_free(record); l1c_prep_free(context);
    return ok ? 0 : 1;
}
