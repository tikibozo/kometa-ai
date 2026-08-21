# Stage 1: Builder stage
FROM python:3.14-slim AS builder

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
FROM python:3.14-slim

# Set label metadata
LABEL maintainer="Kometa-AI Team" \
      version="1.0.0" \
      description="AI-powered movie collection manager for Radarr and Kometa"

# Install gosu for dropping privileges, plus curl/ca-certificates for the
# optional Claude Code CLI install below.
# `apt-get upgrade` matters: the base tag lags fresh Debian security fixes
# between Docker's periodic rebuilds, so without it a rebuild ships known-CVE OS
# packages and the scheduled Trivy re-scan of :latest goes red.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    gosu \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with default UID/GID of 1000
RUN groupadd -g 1000 kometa && useradd -u 1000 -g kometa -d /app kometa

# Set working directory
WORKDIR /app

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels

# Install dependencies
# Remove pip after installing. Nothing runs pip at runtime (the entrypoint
# installs the Claude CLI via curl, and the app itself never shells out to pip),
# and pip 26.2+ ships a CycloneDX SBOM of its vendored dependencies at
# pip/_vendor/bom.cdx.json which scanners read as installed software — blocking
# the Trivy gate on CVEs in packages this project does not depend on.
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && rm -rf /wheels \
    && python -m pip uninstall -y pip

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

# The Claude Code CLI (CLAUDE_BACKEND=cli, subscription billing) is not baked
# in — the entrypoint downloads it on first start when that backend is
# selected, keeping the image small. Mount credentials at /app/.claude.

# Copy entrypoint script
COPY scripts/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Healthcheck
HEALTHCHECK --interval=5m --timeout=30s --start-period=1m --retries=3 \
  CMD python -m kometa_ai --health-check || exit 1

# Entry point handles user setup and runs the main script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh", "python", "-m", "kometa_ai"]