# Stage 1: Builder stage
FROM python:3.11-slim-bullseye AS builder

# Set environment variables for pip
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Install build dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install wheel \
    && pip wheel --wheel-dir=/wheels -r requirements.txt

# Stage 2: Final image
FROM python:3.11-slim-bullseye

# Set label metadata
LABEL maintainer="Kometa-AI Team" \
      version="1.0.0" \
      description="AI-powered movie collection manager for Radarr and Kometa"

# Install gosu for dropping privileges
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with default UID/GID of 1000
RUN groupadd -g 1000 kometa && useradd -u 1000 -g kometa -d /app kometa

# Set working directory
WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Install dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY --chown=kometa:kometa . .

# Create mount points for volumes and ensure proper permissions
RUN mkdir -p /app/kometa-config /app/state /app/logs \
    && chown -R kometa:kometa /app/kometa-config /app/state /app/logs
VOLUME ["/app/kometa-config", "/app/state", "/app/logs"]

# Set default environment variables
ENV TZ=UTC \
    SCHEDULE_INTERVAL=1d \
    SCHEDULE_START_TIME=03:00 \
    DEBUG_LOGGING=false \
    SMTP_PORT=25 \
    PYTHONUNBUFFERED=1 \
    # Default UID/GID - can be overridden at runtime
    PUID=1000 \
    PGID=1000

# Copy entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Healthcheck
HEALTHCHECK --interval=5m --timeout=30s --start-period=1m --retries=3 \
  CMD python -m kometa_ai --health-check || exit 1

# Entry point handles user setup and runs the main script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh", "python", "-m", "kometa_ai"]