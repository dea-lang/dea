# syntax=docker/dockerfile:1.7
# Supply an explicitly installed Linux L1 prefix as the named bootstrap context.
FROM python:3.14-bookworm AS validated
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /project
# Permitted root-owned tooling only; no sibling source or build tree is copied.
COPY scripts/dea_tooling /project/scripts/dea_tooling
COPY scripts/check_examples.py scripts/asan_test_support.py /project/scripts/
COPY l2 /project/l2
COPY --from=bootstrap / /opt/l1/
RUN python -m venv /project/.venv && /project/.venv/bin/python -m pip install --no-cache-dir pytest pytest-xdist
ENV L2_BOOTSTRAP_L1C=/opt/l1/bin/l1c L1_CC=gcc L2_CC=gcc L2_RUNTIME_CC=gcc
WORKDIR /project/l2
# The copied host's generated outputs are not valid evidence in this environment.
RUN rm -rf build && test ! -e /project/l0 && test ! -e /project/l1 && make --old-file=venv test-tooling test-compiler TESTS="source_paths_test compiler_filesystem_support_test.py l2_language_identity_test.py"

FROM debian:bookworm-slim AS operation
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
# The upstream compiler and implementation test tooling are absent in this phase.
COPY --from=validated /project/l2 /project/l2
WORKDIR /project/l2
ENV L2_CC=gcc L2_RUNTIME_CC=gcc L2_STDLIB_CACHE=/tmp/l2-cold-cache
RUN rm -rf build/dea/bootstrap-cache build/dea/cache /root/.cache/dea/l2 /tmp/l2-cold-cache && \
    test ! -e /opt/l1 && test ! -e /project/l0 && test ! -e /project/l1 && \
    ! command -v l1c && ! command -v python && ! command -v make && \
    build/dea/bin/l2c --prepare-stdlib && \
    mkdir -p /tmp/l2-isolation && \
    printf '%s\n' 'module provider;' 'func answer() -> int { return 42; }' >/tmp/l2-isolation/provider.l2 && \
    printf '%s\n' 'module main;' 'import std.io;' 'import provider;' 'func main() -> int { printl_s("L2 isolated execution"); return answer() - 42; }' >/tmp/l2-isolation/main.l2 && \
    build/dea/bin/l2c --compile -Rp /tmp/l2-isolation provider -o /tmp/l2-isolation/provider.o && \
    test -f /tmp/l2-isolation/provider.l2m && rm /tmp/l2-isolation/provider.l2 && \
    build/dea/bin/l2c --compile -Rp /tmp/l2-isolation -I /tmp/l2-isolation main -o /tmp/l2-isolation/main.o && \
    build/dea/bin/l2c --link /tmp/l2-isolation/main.o /tmp/l2-isolation/provider.o -o /tmp/l2-isolation/program && \
    /tmp/l2-isolation/program && \
    cp /tmp/l2-isolation/main.l2 /tmp/l2-isolation/main.l1 && \
    ! build/dea/bin/l2c --check /tmp/l2-isolation/main.l1
CMD ["/project/l2/build/dea/bin/l2c", "--version"]
