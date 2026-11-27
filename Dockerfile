# Imagen del backend para desplegar (Render u otro servidor con Docker).
#
#   docker build -t chatbot-uae .
#   docker run --rm -p 8000:8000 --memory=512m -e DB_ENABLED=false chatbot-uae
#
# Embeddings ONNX int8 (sin PyTorch). El modelo se descarga y el índice se
# construye durante el build, así el servidor arranca sin internet ni
# reindexar. Las credenciales (DATABASE_URL, LLM_API_KEY...) NO van aquí:
# se pasan como variables de entorno del servicio (en Render, "Environment").

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Menos arenas de malloc por hilo: evita que glibc retenga memoria
    # que ya no se usa (importante con el límite de 512 MB).
    MALLOC_ARENA_MAX=2 \
    APP_ENV=production \
    EMBEDDINGS_PROVIDER=onnx \
    # El índice viene construido en la imagen; si no coincide con el modelo
    # configurado, la aplicación lo reconstruye igual al arrancar.
    INDEX_ON_STARTUP=false \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Código y modelo antes que las fichas: editar una ficha no vuelve a
# descargar el modelo (solo se reconstruye el índice).
COPY app/ app/
COPY scripts/ scripts/
RUN python -m scripts.descargar_modelo --sin-indice

COPY fichas/ fichas/
COPY frontend/ frontend/
RUN python -m scripts.indexar \
    && chown -R app:app /app/data

USER app
EXPOSE 8000

# Render asigna el puerto en $PORT; en local se usa 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
