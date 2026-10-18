# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Pin uv by digest so the dependency layer stays cacheable and reproducible. This is the
# image `uv:latest` resolved to when the cache was introduced.
COPY --from=ghcr.io/astral-sh/uv@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/

WORKDIR /app

# FFmpeg powers the reviewer visual-context tools and caption burn-in. Noto Core covers the
# catalog's Arabic, Indic and Thai scripts; the regional CJK package covers Japanese, Korean,
# Simplified/Traditional Chinese and Cantonese. libass resolves these system faces through
# fontconfig, while app/assets/fonts remains the source for Montserrat/Poppins Latin captions.
# Prune unrelated scripts and CJK serif faces after installation to keep the image bounded.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        fontconfig \
        fonts-noto-cjk \
        fonts-noto-core \
    && find /usr/share/fonts/truetype/noto -type f \
        ! -name 'NotoSansArabic-*.ttf' \
        ! -name 'NotoSansBengali-*.ttf' \
        ! -name 'NotoSansDevanagari-*.ttf' \
        ! -name 'NotoSansGujarati-*.ttf' \
        ! -name 'NotoSansGurmukhi-*.ttf' \
        ! -name 'NotoSansKannada-*.ttf' \
        ! -name 'NotoSansMalayalam-*.ttf' \
        ! -name 'NotoSansTamil-*.ttf' \
        ! -name 'NotoSansTelugu-*.ttf' \
        ! -name 'NotoSansThai-*.ttf' \
        -delete \
    && find /usr/share/fonts/opentype/noto -type f -name 'NotoSerifCJK-*.ttc' -delete \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

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

COPY --chown=10001:10001 app ./app

ENV PATH="/app/.venv/bin:$PATH"
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1

# Dependencies are immutable and already readable by the runtime user. Recursively
# chowning the venv would copy every dependency into a second large image layer.
RUN useradd --create-home --uid 10001 appuser && chown appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
