# NG-HEADER: Nombre de archivo: Dockerfile
# NG-HEADER: Ubicación: mcp_servers/web_search_server/Dockerfile
# NG-HEADER: Descripción: Imagen multi-stage Python 3.14.6 para MCP Web Search.
# NG-HEADER: Lineamientos: Ver AGENTS.md

FROM python:3.14.6-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY mcp_servers/web_search_server/requirements-lock.txt /app/requirements-lock.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade --no-cache-dir pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /app/requirements-lock.txt

FROM python:3.14.6-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8002

RUN useradd --create-home --shell /usr/sbin/nologin app
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app mcp_servers/web_search_server/ /app/mcp_servers/web_search_server/
COPY --chown=app:app mcp_servers/__init__.py mcp_servers/security.py /app/mcp_servers/
COPY --chown=app:app agent_core/__init__.py agent_core/chat_policy.py agent_core/tool_security.py /app/agent_core/
COPY --chown=app:app infra/swarm-entrypoint.sh /app/infra/swarm-entrypoint.sh
RUN chmod 0755 /app/infra/swarm-entrypoint.sh

USER app
EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8002/health', timeout=2)"

CMD ["uvicorn", "mcp_servers.web_search_server.main:app", "--host", "0.0.0.0", "--port", "8002"]
