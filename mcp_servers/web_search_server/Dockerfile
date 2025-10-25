# NG-HEADER: Nombre de archivo: Dockerfile
# NG-HEADER: Ubicación: mcp_servers/web_search_server/Dockerfile
# NG-HEADER: Descripción: Imagen Docker para MCP Web Search.
# NG-HEADER: Lineamientos: Ver AGENTS.md
FROM python:3.13-slim-bookworm as runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Puerto sugerido 8002
ENV PORT=8002
EXPOSE 8002
CMD ["uvicorn", "mcp_servers.web_search_server.main:app", "--host", "0.0.0.0", "--port", "8002"]
