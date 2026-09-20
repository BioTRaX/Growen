# MCP Web Search

Servidor MCP Streamable HTTP para búsqueda web externa controlada.

## Endpoints y tool

- `POST/GET /mcp`: protocolo MCP real.
- `GET /health`: salud operativa.
- `POST /invoke_tool`: adaptador RPC deprecado.
- `search_web(query, max_results=5)`: requiere JWT con rol admin o colaborador; limita resultados a 1–10.

## Configuración

```env
MCP_WEB_SEARCH_SECRET_KEY=<secreto-aleatorio-exclusivo>
MCP_JWT_ISSUER=growen-api
MCP_WEB_SEARCH_JWT_AUDIENCE=growen-mcp-web-search
MCP_RATE_LIMIT_PER_MINUTE=60
MCP_LEGACY_RPC_ENABLED=0
WEB_SEARCH_BASE=https://duckduckgo.com/html/
```

Desarrollo local: `http://localhost:8102/mcp`. Docker: `http://mcp_web_search:8002/mcp`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest mcp_servers\web_search_server\tests -v
```
