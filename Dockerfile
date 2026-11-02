FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-web.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-web.txt

COPY app.py .
COPY web/ ./web/
COPY data/processed/davao_predictions.gpkg ./data/processed/davao_predictions.gpkg

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
