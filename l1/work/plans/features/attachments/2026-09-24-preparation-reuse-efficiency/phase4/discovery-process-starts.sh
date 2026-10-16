#!/bin/sh
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz
#
# Observe loader starts separately from timings inside the modern Linux measurement image.
set -eu
discovery_repo=$1
discovery_work=$(mktemp -d)
trap 'rm -rf "$discovery_work"' EXIT HUP INT TERM
discovery_source="$discovery_repo/l1/work/plans/features/attachments/2026-09-24-preparation-reuse-efficiency/phase4/discovery-process-starts.c"
gcc -shared -fPIC -O2 "$discovery_source" -o "$discovery_work/process-starts.so"
printf '#include <stdint.h>\n' > "$discovery_work/one.c"
printf '#include <stdbool.h>\n' > "$discovery_work/two.c"
for discovery_compiler in gcc clang; do
    for discovery_input in one two; do
        LD_PRELOAD="$discovery_work/process-starts.so" DISCOVERY_PROCESS_LABEL="$discovery_compiler-individual" \
            "$discovery_compiler" -M -MT fixture "$discovery_work/$discovery_input.c" >/dev/null
    done
    LD_PRELOAD="$discovery_work/process-starts.so" DISCOVERY_PROCESS_LABEL="$discovery_compiler-batch" \
        "$discovery_compiler" -M -MT fixture "$discovery_work/one.c" "$discovery_work/two.c" >/dev/null
done
