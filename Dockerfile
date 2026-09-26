FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002

WORKDIR /app

# Create non-root application user
RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser

# Install Python dependencies
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app ./app
COPY templates ./templates
COPY frontend ./frontend
COPY sql ./sql

# Copy project documentation/example environment file
COPY README.md IMPLEMENTATION_STEPS.md ./
COPY .env.example ./

# Create persistent upload directory
RUN mkdir -p /app/uploads \
    && chown -R appuser:appuser /app

# Run application as non-root user
USER appuser

EXPOSE 8000

# Container health check
HEALTHCHECK --interval=10s \
            --timeout=5s \
            --start-period=20s \
            --retries=5 \
            CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
