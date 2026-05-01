# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.10.9 AS uv

FROM python:3.14-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential clang && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /project/l0
ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/project/.venv

# Deps layer (only rebuilds when lock/pyproject changes)
COPY l0/pyproject.toml l0/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --group dev --group docs

# Source layer
COPY scripts /project/scripts
COPY l0 /project/l0
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group dev --group docs

CMD ["make", "help"]
