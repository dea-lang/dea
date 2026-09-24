# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

FROM dea-preparation-investigation-clang:latest AS upstream
FROM l1-test:latest AS builder
COPY --from=upstream /opt/dea /opt/dea
COPY . /project
WORKDIR /project/l1
RUN L1_BOOTSTRAP_L0C=/opt/dea/bin/l0c-stage2 python3 scripts/build_stage1_l1c.py
FROM dea-preparation-investigation-clang:latest
USER root
COPY --from=builder /project/l1/build/dea /opt/dea/l1/build/playground-sandbox
COPY --from=builder /project/l1/build/dea/bin/l1c-stage1.native /opt/dea/bin/l1c-stage1.native
COPY --from=builder /project/l1/build/dea/interfaces /opt/dea/l1/compiler/interfaces
COPY --from=builder /project/l1/build/dea/include /opt/dea/l1/compiler/include
COPY --from=builder /project/l1/compiler/shared /opt/dea/l1/compiler/shared
WORKDIR /work
RUN rm -rf /opt/dea/l1/cache-template/v1 && HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template --c-compiler gcc --c-options=-O0 && HOME=/work TMPDIR=/work L1_STDLIB_CACHE=/opt/dea/l1/cache-template /opt/dea/bin/l1c-stage1 --prepare-stdlib --stdlib-cache /opt/dea/l1/cache-template --c-compiler clang --c-options=-O0
RUN chmod -R a+rX /opt/dea/l1/cache-template
