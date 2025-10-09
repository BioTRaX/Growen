# NG-HEADER: Nombre de archivo: Dockerfile
# NG-HEADER: Ubicación: mcp_servers/products_server/Dockerfile
# NG-HEADER: Descripción: Imagen Docker para servidor MCP de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

############################
# Etapa 1: builder
############################
FROM python:3.13-slim-bookworm AS builder

# NG-COMMENT: Endurecemos entorno base y deshabilitamos bytecode para builds reproducibles.
ENV DEBIAN_FRONTEND=noninteractive \
        PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1

# NG-COMMENT: Instalar toolchain mínimo sólo en builder (no quedará en runtime final).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NG-COMMENT: Copiamos sólo requirements para maximizar cache de capas.
COPY mcp_servers/products_server/requirements.txt ./requirements.txt

# NG-COMMENT: Creamos venv aislado e instalamos dependencias sin caches.
RUN python -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --upgrade --no-cache-dir pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# NG-COMMENT: Copiamos el código fuente (invalida cache solo cuando cambia el código).
COPY mcp_servers/products_server /app/mcp_servers/products_server

############################
# Etapa 2: runtime delgado
############################
FROM python:3.13-slim-bookworm AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
        PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        PIP_NO_CACHE_DIR=1 \
        PATH="/opt/venv/bin:$PATH"

# NG-COMMENT: Sólo utilidades mínimas necesarias en ejecución (curl para health debugging).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# NG-COMMENT: Usuario no privilegiado para reducir superficie.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

# NG-COMMENT: Copiamos entorno virtual construido y código.
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser mcp_servers/products_server /app/mcp_servers/products_server

# NG-COMMENT: Ajuste de permisos conservador (lectura para archivos, ejecución para dirs).
RUN find /app -type f -exec chmod 0644 {} \; && \
        find /app -type d -exec chmod 0755 {} \;

USER appuser

EXPOSE 8100

# NG-COMMENT: Healthcheck simple contra raíz; sustituir por /health si se implementa.
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8100/ || exit 1

ENV UVICORN_HOST=0.0.0.0 \
        UVICORN_PORT=8100 \
        UVICORN_WORKERS=1

CMD ["uvicorn", "mcp_servers.products_server.main:app", "--host", "0.0.0.0", "--port", "8100"]
