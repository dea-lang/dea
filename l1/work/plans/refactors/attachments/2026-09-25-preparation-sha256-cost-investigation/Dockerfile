# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

FROM dea-preparation-investigation-clang:latest AS upstream

FROM l1-test:latest AS experiment-source
ARG VARIANT=baseline
COPY --from=upstream /opt/dea /opt/dea
COPY . /project
WORKDIR /project
RUN case "$VARIANT" in \
      baseline) ;; \
      direct-block) patch -p1 < l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/candidates/direct-block.patch ;; \
      ring-schedule) patch -p1 < l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/candidates/ring-schedule.patch ;; \
      *) echo "unknown experiment variant: $VARIANT" >&2; exit 2 ;; \
    esac

FROM upstream AS benchmark
USER root
COPY --from=experiment-source /project /project
WORKDIR /project
RUN mkdir -p /opt/dea/investigation && \
    gcc -std=c99 -O1 -Wall -Wextra -Werror -pedantic \
      l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/benchmark.c \
      l1/compiler/stage1_l0/support/compiler_support.c -o /opt/dea/investigation/sha256-benchmark && \
    gcc -std=c99 -O1 -S -fverbose-asm \
      l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/benchmark.c \
      -o /opt/dea/investigation/benchmark.s && \
    dd if=/dev/zero of=/opt/dea/investigation/control-4k.bin bs=4096 count=1 status=none && \
    dd if=/dev/zero of=/opt/dea/investigation/control-8m.bin bs=1048576 count=8 status=none

FROM experiment-source AS compiler
RUN patch -p1 < l1/work/plans/refactors/attachments/2026-09-25-preparation-sha256-cost-investigation/candidates/verbose-build.patch
WORKDIR /project/l1
RUN mkdir -p /opt/dea/investigation && \
    L1_BOOTSTRAP_L0C=/opt/dea/bin/l0c-stage2 python3 scripts/build_stage1_l1c.py \
      > /opt/dea/investigation/compiler-build.log 2>&1 && \
    cat /opt/dea/investigation/compiler-build.log
RUN result=0; \
    L0_CC=gcc L1_CC=gcc L1_RUNTIME_CC=gcc make test-stage1 \
      TESTS='preparation_support_test preparation_identity_test l1c_stage1_preparation_test' \
      > /opt/dea/investigation/focused-tests.log 2>&1 || result=$?; \
    cat /opt/dea/investigation/focused-tests.log; \
    exit "$result"

FROM upstream AS prepared
ARG VARIANT=baseline
USER root
COPY --from=compiler /project/l1/build/dea /opt/dea/l1/build/playground-sandbox
COPY --from=compiler /project/l1/build/dea/bin/l1c-stage1.native /opt/dea/bin/l1c-stage1.native
COPY --from=compiler /project/l1/build/dea/interfaces /opt/dea/l1/compiler/interfaces
COPY --from=compiler /project/l1/build/dea/include /opt/dea/l1/compiler/include
COPY --from=compiler /project/l1/compiler/shared /opt/dea/l1/compiler/shared
COPY --from=compiler /opt/dea/investigation /opt/dea/investigation
COPY --from=benchmark /opt/dea/investigation/sha256-benchmark /opt/dea/investigation/sha256-benchmark
COPY --from=benchmark /opt/dea/investigation/benchmark.s /opt/dea/investigation/benchmark.s
COPY --from=benchmark /opt/dea/investigation/control-4k.bin /opt/dea/investigation/control-4k.bin
COPY --from=benchmark /opt/dea/investigation/control-8m.bin /opt/dea/investigation/control-8m.bin
COPY --from=compiler /project/l1/examples/hello.l1 /work/hello.l1
WORKDIR /work
RUN rm -rf /opt/dea/l1/cache-template/v1 && \
    chown -R 65534:65534 /opt/dea/l1/cache-template /opt/dea/investigation /work && \
    chmod 1777 /work
USER 65534:65534
RUN HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template \
      --c-compiler gcc --c-options=-O0 -vvv \
      > /opt/dea/investigation/image-prepare-gcc.stdout \
      2> /opt/dea/investigation/image-prepare-gcc.stderr && \
    HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template \
      --c-compiler clang --c-options=-O0 -vvv \
      > /opt/dea/investigation/image-prepare-clang.stdout \
      2> /opt/dea/investigation/image-prepare-clang.stderr
RUN HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --build --no-auto-prepare --c-compiler gcc --c-options=-O0 \
      --project-root /work -o /work/hello-gcc -vvv /work/hello.l1 \
      > /opt/dea/investigation/image-build-gcc.stdout \
      2> /opt/dea/investigation/image-build-gcc.stderr && \
    HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --build --no-auto-prepare --c-compiler clang --c-options=-O0 \
      --project-root /work -o /work/hello-clang -vvv /work/hello.l1 \
      > /opt/dea/investigation/image-build-clang.stdout \
      2> /opt/dea/investigation/image-build-clang.stderr
LABEL org.dea.preparation.sha256-variant="$VARIANT"
