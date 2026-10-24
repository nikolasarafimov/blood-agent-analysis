FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/blood-agent:/app/blood-agent-api

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ocrmypdf \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-mkd \
        tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY blood-agent/requirements.txt /app/blood-agent/requirements.txt
COPY blood-agent-api/requirements.txt /app/blood-agent-api/requirements.txt

RUN python -m pip install --no-cache-dir \
        -r /app/blood-agent/requirements.txt \
        -r /app/blood-agent-api/requirements.txt \
    && python -m spacy download en_core_web_lg-3.8.0 --direct \
    && python -m pip check

RUN python -c "import shutil; required = ('ocrmypdf', 'pdfinfo', 'pdftoppm', 'tesseract'); missing = [x for x in required if not shutil.which(x)]; assert not missing, f'Missing executables: {missing}'" \
    && python -c "import pytesseract; languages = set(pytesseract.get_languages(config='')); assert {'eng', 'mkd', 'osd'}.issubset(languages), f'Missing OCR languages: {languages}'" \
    && python -c "from presidio_analyzer import AnalyzerEngine; AnalyzerEngine()"

COPY blood-agent/db/*.py /app/blood-agent/db/
COPY blood-agent/src/*.py /app/blood-agent/src/
COPY blood-agent/src/tools/*.py /app/blood-agent/src/tools/
COPY blood-agent/storage/*.py /app/blood-agent/storage/
COPY blood-agent-api/app/*.py /app/blood-agent-api/app/
COPY blood-agent-api/main.py /app/blood-agent-api/main.py

WORKDIR /app/blood-agent-api

RUN python -c "from main import app; assert app.title == 'Blood Analysis Agent API'"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8000/health > /dev/null || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]