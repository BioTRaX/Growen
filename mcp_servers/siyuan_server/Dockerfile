# NG-HEADER: Nombre de archivo: Dockerfile
# NG-HEADER: Ubicación: mcp_servers/siyuan_server/Dockerfile
# NG-HEADER: Descripción: Imagen multi-stage y no-root del MCP de SiYuan.
# NG-HEADER: Lineamientos: Ver AGENTS.md

FROM python:3.14.6-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build
COPY mcp_servers/siyuan_server/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.14.6-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8104

RUN useradd --create-home --shell /usr/sbin/nologin appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser mcp_servers/siyuan_server /app/mcp_servers/siyuan_server
COPY --chown=appuser:appuser mcp_servers/__init__.py mcp_servers/security.py /app/mcp_servers/

USER appuser
EXPOSE 8104
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8104/health', timeout=3)" || exit 1

CMD ["uvicorn", "mcp_servers.siyuan_server.main:app", "--host", "0.0.0.0", "--port", "8104"]

