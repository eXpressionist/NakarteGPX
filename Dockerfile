# Multi-stage Dockerfile for Nakarte GPX Bot

# Stage 1: Base image with Python dependencies
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Playwright browser dependencies manually (Debian-compatible)
RUN apt-get update && apt-get install -y \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcb-shm0 \
    libegl1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder to a location accessible by all users
COPY --from=builder /root/.local /usr/local

# Copy application code
COPY src/ ./src/
COPY .env.example .env.example

# Create cache directory
RUN mkdir -p /app/cache

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Install Playwright browsers as botuser (skip system dependencies since we installed them manually)
USER botuser
RUN playwright install chromium

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "-m", "src.main"]
