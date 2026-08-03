FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt-get/lists/*

COPY pyproject.toml setup.py README.md ./
RUN pip install --no-cache-dir .

COPY proto/ ./proto/
COPY generated/ ./generated/
COPY shared/ ./shared/
COPY gateway/ ./gateway/
COPY worker/ ./worker/

ENV PYTHONPATH=/app:/app/generated

CMD ["python", "-m", "worker.server"]
