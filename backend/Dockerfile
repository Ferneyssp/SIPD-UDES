# Imagen del backend (Django + inferencia ML). Contexto de build: raíz del proyecto.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ML_DIR=/app/ml \
    ML_MODELS_DIR=/app/ml/models \
    MEDIA_ROOT=/app/media

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY ml/requirements.txt /app/ml/requirements.txt
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

COPY ml /app/ml
COPY data/sample /app/data/sample
COPY backend /app/backend

RUN useradd --create-home --uid 1000 sipd \
    && mkdir -p /app/media /app/backend/staticfiles \
    && chown -R sipd:sipd /app \
    && chmod +x /app/backend/docker-entrypoint.sh
USER sipd

EXPOSE 8000
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
