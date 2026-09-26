# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Pin uv by digest so the dependency layer stays cacheable and reproducible. This is the
# image `uv:latest` resolved to when the cache was introduced.
COPY --from=ghcr.io/astral-sh/uv@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

WORKDIR /app

# Bytecode-compile at build time (faster Cloud Run cold start) and copy rather than
# hardlink so the cache mount and the final layer cannot share inodes.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, app code second: a code-only change reuses this layer. The
# gha layer cache (`cache-from: type=gha` in the workflow) keeps it warm across runs.
# The cache mount only helps a persistent local builder: BuildKit does not export
# `--mount=type=cache` contents with the gha backend, so in CI it starts empty.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"
ENV ENVIRONMENT=production

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
