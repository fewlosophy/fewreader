# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    BOOKS_DIR=/app/books \
    APP_TITLE=ReadLite

WORKDIR /app

# Create a non-root system user and group for security
RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --gid 1000 --no-create-home appuser

# Install dependencies first to optimize Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code, static assets, and configuration
COPY app /app/app
COPY static /app/static
COPY pyproject.toml /app/pyproject.toml

# Prepare books mount directory with proper ownership
RUN mkdir -p /app/books && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

EXPOSE 8000

# Built-in health check using Python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
