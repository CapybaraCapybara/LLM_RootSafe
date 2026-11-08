# RootSafe Arborist - Ultra-Slim Production Dockerfile (Optimized for 512MB RAM Free Tier)
# Memory limit: ~200MB working set, single async worker
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    ONNXRUNTIME_NUM_THREADS=1 \
    PORT=8000

WORKDIR /app

# Install minimal curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install lightweight Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache Chroma ONNX embedding model inside image for instant container startup
RUN python -c "from chromadb.utils import embedding_functions; embedding_functions.DefaultEmbeddingFunction()"

# Copy application source code and data
COPY app/ ./app/
COPY data/ ./data/
COPY static/ ./static/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/health || exit 1

# Start single-worker Uvicorn (Crucial for 512MB RAM tier: keeps total memory under ~200MB)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
