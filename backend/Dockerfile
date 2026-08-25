# Build Go engines (linux binaries so plugins work inside the container)
FROM golang:1.24-alpine AS engines
WORKDIR /src/engines
COPY engines/ ./
RUN go build -o /out/portscan ./cmd/portscan && \
    go build -o /out/subdomain ./cmd/subdomain && \
    go build -o /out/fingerprint ./cmd/fingerprint

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install SDK first (local dependency, no PyPI needed)
COPY sdk/ /sdk/
RUN pip install --no-cache-dir --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple /sdk

# Copy and install backend dependencies
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies (includes WeasyPrint system libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ .

# Copy Go engine binaries built for the container platform
COPY --from=engines /out /app/engines/bin

# Create non-root user
RUN useradd -m -u 1000 netkitx && \
    chown -R netkitx:netkitx /app && \
    mkdir -p /app/plugins /app/engines/bin && \
    chown -R netkitx:netkitx /app/plugins /app/engines

USER netkitx

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
