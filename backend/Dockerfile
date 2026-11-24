# InvoiceFlow backend — FastAPI + LangGraph + SQLite + Tesseract OCR
FROM python:3.12-slim

# Tesseract OCR (needed by app/services/ocr.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app

# Persistent data dir for SQLite
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/data/invoiceflow.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
