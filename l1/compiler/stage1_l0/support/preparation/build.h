/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/** @file build.h Coordinated output writes and native stdlib/runtime preparation. */
#ifndef L1_PREPARATION_BUILD_H
#define L1_PREPARATION_BUILD_H

/** Validate one declared output and detach old files before writing new contents. */
static char *pc_output_path(PcContext *c, const char *relative) {
    PcJson *expected;
    char *path, *parent;
    int valid;
    if ((!c->lock && !c->private_root) || !c->begun || !c->selected || !pc_relative(relative))
        return pc_fail(c, 2152, "artifact writes require begun preparation", relative), NULL;
    expected = pc_expected_artifacts(c->native);
    valid = expected && pj_get(expected, relative);
    if (!valid) {
        const PcJson *module;
        for (module = c->modules->child; module; module = module->next) {
            char *scratch = pc_module_artifact(module->key, ".c", "generated");
            if (!strcmp(relative, scratch)) valid = 1;
            free(scratch);
        }
    }
    pj_free(expected);
    if (!valid)
        return pc_fail(c, 2151, "undeclared preparation output", relative), NULL;
    path = pc_join(c->selected, relative);
    parent = pc_parent(path);
    if (!pc_mkdirs(parent) || (pc_kind(path, 0) != 0 && remove(path) != 0)) {
        pc_fail(c, 2150, "cannot establish preparation output", path);
        free(path);
        path = NULL;
    }
    free(parent);
    return path;
}
static int pc_output_write(PcContext *c, const char *relative, const char *data, size_t size) {
    char *path = pc_output_path(c, relative);
    int ok;
    if (!path)
        return 0;
    ok = pc_write_file(path, data, size);
    if (!ok)
        pc_fail(c, 2150, "cannot write preparation output", path);
    free(path);
    return ok;
}
/** Preserve captured host diagnostics at all verbosity levels, including failed builds. */
static int pc_build_command(PcContext *c, PcJson *words, const char *purpose) {
    const PcJson *verbosity = pj_get(c->config, "verbosity");
    PcProbe result;
    int ok;
    if (verbosity && verbosity->number >= 1) {
        char *command = pj_encode(words);
        fprintf(stderr, "Preparation command (%s): %s\n", purpose, command);
        free(command);
    }
    ++c->build_commands;
    result = pc_probe(words, 120000);
    pj_free(words);
    ok = result.status == 0 && !result.timed_out;
    if (result.err && *result.err)
        fputs(result.err, stderr);
    if (result.out && *result.out && (!ok || (verbosity && verbosity->number >= 1)))
        fputs(result.out, stderr);
    if (!ok)
        pc_fail(c, 2156,
                result.timed_out ? "native preparation timed out"
                                 : "native preparation command failed",
                purpose);
    pc_probe_free(&result);
    return ok;
}
/** Require unchanged Dea inputs before publishing outputs for their resolved key. */
static int pc_preparation_inputs_current(PcContext *c) {
    const PcJson *file;
    for (file = c->new_files->child; file; file = file->next) {
        PcJson *now = pc_meta(file->key);
        int same = now && pj_equal(now, pj_get(file, "metadata"));
        pj_free(now);
        if (!same)
            return pc_fail(c, 2151, "preparation input changed while building", file->key);
    }
    return 1;
}
/** Write caller-generated canonical interface or C bytes to a declared output role. */
int32_t l1c_prep_write(void *context, const uint8_t *relative, int32_t length, const uint8_t *data,
                       int32_t size) {
    PcContext *c = context;
    char *path;
    int ok;
    if (!c || c->error || !relative || length < 0 || size < 0 || (!data && size) ||
        memchr(relative, 0, (size_t)length))
        return 0;
    path = pc_slice((const char *)relative, (size_t)length);
    ok = pc_output_write(c, path, (const char *)data, (size_t)size);
    free(path);
    return ok;
}
/** Copy the exact selected toolchain semantic bytes; never re-emit profile interfaces. */
int32_t l1c_prep_copy_interfaces(void *context) {
    PcContext *c = context;
    const PcJson *item;
    if (!c || c->error || !c->begun) return 0;
    for (item = c->interfaces->child; item; item = item->next) {
        char *source = pc_join(c->semantic_root, item->key + strlen("modules/")), *data;
        size_t size;
        char digest[65];
        int ok;
        data = pc_read_file(source, 16 * 1024 * 1024, &size);
        if (data) pc_sha_bytes(data, size, digest);
        ok = data && !strcmp(digest, item->text) && pc_output_write(c, item->key, data, size);
        if (!ok && !c->error) pc_fail(c, 2158, "selected toolchain interface changed or is unavailable; rerun bootstrap", source);
        free(source); free(data);
        if (!ok) return 0;
    }
    return 1;
}
/** Compile already-emitted module C using the exact options resolved by this context. */
int32_t l1c_prep_compile(void *context, const uint8_t *module, int32_t length) {
    PcContext *c = context;
    char *name, *relative, *object, *generated, *source, *include;
    PcJson *words;
    int ok;
    if (!c || c->error || !module || length < 0 || memchr(module, 0, (size_t)length))
        return 0;
    name = pc_slice((const char *)module, (size_t)length);
    if ((!c->lock && !c->private_root) || !c->begun || !c->selected || !c->native ||
        !pc_module_name(name) || !pj_get(c->modules, name)) {
        free(name);
        return pc_fail(c, 2151, "unknown native preparation module", NULL);
    }
    relative = pc_module_artifact(name, ".o", "modules");
    object = pc_output_path(c, relative);
    generated = pc_module_artifact(name, ".c", "generated");
    source = pc_join(c->selected, generated);
    include = pc_string(c->include);
    words = pc_words(c, 1);
    pj_add(words, NULL, pj_string("-I"));
    pj_add(words, NULL, pj_string(include));
    pj_add(words, NULL, pj_string("-c"));
    pj_add(words, NULL, pj_string(source));
    pj_add(words, NULL, pj_string("-o"));
    if (object)
        pj_add(words, NULL, pj_string(object));
    ++c->module_compiles;
    if (object)
        ok = pc_build_command(c, words, name);
    else {
        pj_free(words);
        ok = 0;
    }
    free(name);
    free(relative);
    free(object);
    free(generated);
    free(source);
    free(include);
    return ok;
}
/** Build the selected runtime with the same compiler with compiler-owned runtime options and variant. */
int32_t l1c_prep_runtime(void *context) {
    PcContext *c = context;
    const char *variant, *family;
    char *include, *internal, *scratch = NULL, *archive = NULL;
    PcJson *objects = pj_new(PJ_ARRAY);
    const PcJson *object;
    int traced, tcc, i, ok = 1;
    if (!c || c->error || !c->native || !c->begun || (!c->lock && !c->private_root)) {
        pj_free(objects);
        return 0;
    }
    variant = pj_field(pj_get(c->native, "runtime"), "variant");
    family = pj_field(pj_get(c->native, "toolchain"), "family");
    traced = !strcmp(variant, "traced");
    tcc = !strcmp(family, "tcc");
    include = pc_join(c->home, "shared/runtime/include");
    internal = pc_join(c->home, "shared/runtime/internal");
    if (!tcc) {
        scratch = pc_join(c->selected, "runtime-build");
        if (!pc_mkdirs(scratch))
            ok = pc_fail(c, 2150, "cannot create runtime build directory", scratch);
        if (ok)
            archive = pc_output_path(c, pc_runtime_archive(variant));
        if (!archive)
            ok = 0;
    }
    for (i = traced ? -1 : 0; i < 9 && ok; ++i) {
        const char *name = i == -1 ? "dea_rt_trace" : pc_runtime_sources[i];
        PcBuffer filename = {0};
        char *source, *output, *stem, *relative;
        PcJson *words = pc_runtime_words(c);
        pc_text(&filename, name);
        pc_text(&filename, ".c");
        stem = pc_join(c->home, "shared/runtime/src");
        source = pc_join(stem, filename.s);
        free(stem);
        free(filename.s);
        memset(&filename, 0, sizeof(filename));
        pc_text(&filename, name);
        pc_text(&filename, ".o");
        if (tcc) {
            stem = pc_join("lib/tcc", variant);
            relative = pc_join(stem, filename.s);
            output = pc_output_path(c, relative);
            free(relative);
            free(stem);
        } else {
            output = pc_join(scratch, filename.s);
            if (pc_kind(output, 0) != 0 && remove(output) != 0) {
                free(output);
                output = NULL;
            }
        }
        pj_add(words, NULL, pj_string("-I"));
        pj_add(words, NULL, pj_string(include));
        pj_add(words, NULL, pj_string("-I"));
        pj_add(words, NULL, pj_string(internal));
        pj_add(words, NULL, pj_string("-c"));
        pj_add(words, NULL, pj_string(source));
        pj_add(words, NULL, pj_string("-o"));
        if (output) {
            pj_add(words, NULL, pj_string(output));
            pj_add(objects, NULL, pj_string(output));
            ok = pc_build_command(c, words, name);
        } else {
            pj_free(words);
            ok = pc_fail(c, 2150, "cannot establish runtime object output", name);
        }
        free(filename.s);
        free(source);
        free(output);
    }
    if (ok && !tcc) {
        const char *ar = pj_field(pj_get(c->native, "toolchain"), "archiver");
        PcJson *words = pj_new(PJ_ARRAY);
        if (!ar) {
            pj_free(words);
            ok = pc_fail(c, 2156, "cannot find runtime archiver", "ar");
        } else {
            pj_add(words, NULL, pj_string(ar));
            pj_add(words, NULL, pj_string("rcs"));
            pj_add(words, NULL, pj_string(archive));
            for (object = objects->child; object; object = object->next)
                pj_add(words, NULL, pj_clone(object));
            ok = pc_build_command(c, words, "runtime archive");
        }
    }
    if (!tcc) {
        for (object = objects->child; object; object = object->next)
            remove(object->text);
        if (scratch) {
#if defined(_WIN32)
            _rmdir(scratch);
#else
            rmdir(scratch);
#endif
        }
    }
    pj_free(objects);
    free(include);
    free(internal);
    free(scratch);
    free(archive);
    return ok;
}
#endif
