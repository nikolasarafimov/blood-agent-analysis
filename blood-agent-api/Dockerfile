FROM python:3.11-slim

# System deps needed for:
# - pdf2image: poppler-utils
# - pytesseract: tesseract-ocr (+ eng traineddata)
# - OpenCV/Pillow runtime libs: libgl1, libglib2.0-0
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY blood-agent/requirements.txt /app/blood-agent/requirements.txt
COPY blood-agent-api/requirements.txt /app/blood-agent-api/requirements.txt

RUN pip install --no-cache-dir -r /app/blood-agent/requirements.txt \
 && pip install --no-cache-dir -r /app/blood-agent-api/requirements.txt

# Copy source code
COPY blood-agent /app/blood-agent
COPY blood-agent-api /app/blood-agent-api

# Make both importable
ENV PYTHONPATH="/app/blood-agent:/app/blood-agent-api"

EXPOSE 8000

# Run from the folder that contains main.py so uvicorn can import "main:app"
WORKDIR /app/blood-agent-api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]