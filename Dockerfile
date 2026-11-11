# Imagen para Google Cloud Run (también sirve para cualquier servicio de contenedores).
# Cloud Run indica el puerto en $PORT (8080 por defecto). Las imágenes base vienen
# de mirror.gcr.io (copia de Docker Hub en Google): sin límites de descarga.

# ---- 1. Compilar el frontend (React + Vite) ----
FROM mirror.gcr.io/library/node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 2. Servidor de Python ----
FROM mirror.gcr.io/library/python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Solo lo que necesita el servidor: nada de data/ ni salidas/ (tus datos
# privados viven en Supabase) ni del .env (las claves van como variables
# de entorno del servicio). .dockerignore lo refuerza.
COPY app/ app/
COPY config/ config/
COPY --from=web /web/dist web/dist

# Sin privilegios de root dentro del contenedor.
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
