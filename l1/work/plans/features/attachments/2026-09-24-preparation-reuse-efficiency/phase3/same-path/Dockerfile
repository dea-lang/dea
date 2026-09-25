# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

# The two consumers share this exact compiler build and preparation step.
# Their cache stays at the same canonical path during preparation and use.
FROM dea-preparation-investigation-clang:latest AS upstream
FROM l1-test:latest AS builder
COPY --from=upstream /opt/dea /opt/dea
COPY . /project
WORKDIR /project/l1
RUN L1_BOOTSTRAP_L0C=/opt/dea/bin/l0c-stage2 python3 scripts/build_stage1_l1c.py

FROM dea-preparation-investigation-clang:latest AS prepared
USER root
COPY --from=builder /project/l1/build/dea /opt/dea/l1/build/playground-sandbox
COPY --from=builder /project/l1/build/dea/bin/l1c-stage1.native /opt/dea/bin/l1c-stage1.native
COPY --from=builder /project/l1/build/dea/interfaces /opt/dea/l1/compiler/interfaces
COPY --from=builder /project/l1/build/dea/include /opt/dea/l1/compiler/include
COPY --from=builder /project/l1/compiler/shared /opt/dea/l1/compiler/shared
COPY --from=builder /project/l1/examples/hello.l1 /work/hello.l1
WORKDIR /work
RUN rm -rf /opt/dea/l1/cache-template/v1 && \
    chown -R 65534:65534 /opt/dea/l1/cache-template && chmod 1777 /work
USER 65534:65534
RUN HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template --c-compiler gcc --c-options=-O0 && \
    HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template --c-compiler clang --c-options=-O0
RUN HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --build --no-auto-prepare --c-compiler gcc --c-options=-O0 \
      --project-root /work -o /work/hello-gcc /work/hello.l1 && \
    HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template \
      /opt/dea/bin/l1c-stage1 --build --no-auto-prepare --c-compiler clang --c-options=-O0 \
      --project-root /work -o /work/hello-clang /work/hello.l1 && \
    test "$(find /opt/dea/l1/cache-template/v1/memo/artifacts -name '*.json' | wc -l)" -eq 2
FROM prepared AS inherited
LABEL org.dea.preparation.phase3="inherited"

FROM dea-preparation-investigation-clang:latest AS copied
USER root
RUN rm -rf /opt/dea/l1/build/playground-sandbox /opt/dea/l1/compiler/interfaces \
    /opt/dea/l1/compiler/include /opt/dea/l1/compiler/shared /opt/dea/l1/cache-template/v1
COPY --from=prepared /opt/dea/bin/l1c-stage1 /opt/dea/bin/l1c-stage1
COPY --from=prepared /opt/dea/bin/l1c-stage1.native /opt/dea/bin/l1c-stage1.native
COPY --from=prepared /opt/dea/bin/l1c /opt/dea/bin/l1c
COPY --from=prepared /opt/dea/l1/build/playground-sandbox /opt/dea/l1/build/playground-sandbox
COPY --from=prepared /opt/dea/l1/compiler/interfaces /opt/dea/l1/compiler/interfaces
COPY --from=prepared /opt/dea/l1/compiler/include /opt/dea/l1/compiler/include
COPY --from=prepared /opt/dea/l1/compiler/shared /opt/dea/l1/compiler/shared
COPY --chown=65534:65534 --from=prepared /opt/dea/l1/cache-template/v1 /opt/dea/l1/cache-template/v1
WORKDIR /work
USER 65534:65534
LABEL org.dea.preparation.phase3="copied"

# Corrupt optional observation evidence while leaving completed profiles intact.
FROM copied AS stale-evidence
RUN find /opt/dea/l1/cache-template/v1/memo/toolchains -name '*.json' -type f \
    -exec sh -c 'printf "{invalid memo}" > "$1"' sh '{}' \;
LABEL org.dea.preparation.phase3="stale-evidence"
