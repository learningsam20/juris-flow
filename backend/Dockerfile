FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential tesseract-ocr && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-cloud.txt* ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ -f requirements-cloud.txt ]; then pip install --no-cache-dir -r requirements-cloud.txt; fi


COPY . .
RUN if [ -d policies ]; then cp -r policies /policies; fi

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

