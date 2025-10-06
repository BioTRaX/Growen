# NG-HEADER: Nombre de archivo: Dockerfile
# NG-HEADER: Ubicación: mcp_servers/products_server/Dockerfile
# NG-HEADER: Descripción: Imagen Docker para servidor MCP de productos
# NG-HEADER: Lineamientos: Ver AGENTS.md

FROM python:3.11-slim

WORKDIR /app

# Dependencias sistema mínimas (curl para diagnósticos futuros)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY mcp_servers/products_server/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_servers/products_server /app/mcp_servers/products_server

EXPOSE 8100

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "mcp_servers.products_server.main:app", "--host", "0.0.0.0", "--port", "8100"]
