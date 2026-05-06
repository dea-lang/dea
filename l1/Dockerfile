# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.10.9 AS uv

FROM python:3.14-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential clang && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/project/.venv

# Deps layer (only rebuilds when the workspace lock or any member pyproject changes).
WORKDIR /project
COPY pyproject.toml uv.lock ./
COPY l0/pyproject.toml /project/l0/pyproject.toml
COPY l1/pyproject.toml /project/l1/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --all-groups

# Source layer
COPY Makefile /project/Makefile
COPY scripts /project/scripts
COPY l0 /project/l0
COPY l1 /project/l1
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-groups

WORKDIR /project/l1
CMD ["make", "help"]
