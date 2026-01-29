FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY blood-agent/requirements.txt /app/blood-agent/requirements.txt
COPY blood-agent-api/requirements.txt /app/blood-agent-api/requirements.txt

RUN pip install --no-cache-dir -r /app/blood-agent/requirements.txt \
 && pip install --no-cache-dir -r /app/blood-agent-api/requirements.txt

COPY blood-agent /app/blood-agent
COPY blood-agent-api /app/blood-agent-api

ENV PYTHONPATH="/app/blood-agent:/app/blood-agent-api"

EXPOSE 8000

WORKDIR /app/blood-agent-api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]