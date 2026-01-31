# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install the application
RUN uv pip install --system --no-cache .

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/notion-time-capsule /usr/local/bin/

# Copy templates and example config
COPY templates ./templates
COPY config.example.toml ./config.example.toml

# Create non-root user and set up directories
RUN useradd -m -u 1000 notionuser && \
    mkdir -p /app/backups && \
    chown -R notionuser:notionuser /app

USER notionuser

# Ensure Python output is not buffered (important for Docker logs)
ENV PYTHONUNBUFFERED=1

# Health check using the status command
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD notion-time-capsule status || exit 1

# Default command runs the scheduler
CMD ["notion-time-capsule", "schedule"]
