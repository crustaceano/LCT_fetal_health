FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy project
COPY src/ /app/src/

# Expose both ports
EXPOSE 8000 9000

# Default command runs both services
CMD ["sh", "-c", "uvicorn src.model_api.model_app:app --host 0.0.0.0 --port 8000 & uvicorn src.backend.app:app --host 0.0.0.0 --port 9000 & wait"]
