# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: Build frontend assets with Node.js
# ============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY webpack.common.js webpack.prod.js webpack.dev.js tsconfig.json ./
COPY wine_cellar/assets/ wine_cellar/assets/
COPY wine_cellar/react/ wine_cellar/react/

RUN --mount=type=cache,target=/app/node_modules/.cache \
    npm run build:prod


# ============================================================
# Stage 2: Python application
# ============================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies:
#  libzbar0 - barcode reading (pyzbar)
#  libpq5 - PostgreSQL client library (psycopg[binary] runtime)
#  libjpeg62-turbo libpng16-16 libwebp7 - image processing (Pillow)
#  curl - health checks
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    libpq5 \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    curl \
    git \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Using cache mount for pip to speed up repeated installs
COPY requirements/ requirements/
ARG REQUIREMENTS_FILE=requirements/prod.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r ${REQUIREMENTS_FILE}

# Copy application code
COPY manage.py pyproject.toml ./
COPY wine_cellar/ wine_cellar/
COPY fixtures/ fixtures/

# Copy built frontend assets from Node stage
COPY --from=frontend-builder /app/wine_cellar/static/ wine_cellar/static/

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create media and static directories
RUN mkdir -p /app/media /app/staticfiles

# Non-root user (entrypoint runs as root to fix volume permissions, then drops to django)
RUN addgroup --system django && adduser --system --ingroup django django
RUN chown -R django:django /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
