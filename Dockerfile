# Stage 1: Dependency builder
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final runner stage
FROM python:3.12-slim AS runner

WORKDIR /app

# Install curl for the healthcheck tool
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

# Run as non-root user for security hardening
RUN groupadd -r appgroup && useradd -r -g appgroup -u 10001 appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Docker healthcheck querying the unauthenticated /health API
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run with multi-worker configuration for production scaling
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
