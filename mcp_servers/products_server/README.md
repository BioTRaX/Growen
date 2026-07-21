# MCP Products

Servidor MCP Streamable HTTP que consulta la API principal sin acceder directamente a la base.

## Endpoints

- `POST/GET /mcp`: protocolo MCP real (`initialize`, `tools/list`, `tools/call`).
- `GET /health`: salud operativa.
- `POST /invoke_tool`: adaptador RPC deprecado, controlado por `MCP_LEGACY_RPC_ENABLED`.

## Tools

- `find_products_by_name(query)`: todo usuario autenticado.
- `get_product_info(sku?, product_id?)`: todo usuario autenticado.
- `get_product_full_info(sku?, product_id?)`: admin y colaborador.

Las tres tools devuelven `tags: list[str]`, incluida una lista vacía cuando el producto no tiene tags. `find_products_by_name` usa `/catalog/search`, por lo que cada término puede coincidir por nombre, descripción, SKU o tag y se mantiene la lógica AND entre términos.

El rol se obtiene exclusivamente del JWT Bearer; no forma parte de los argumentos de las tools.

## Configuración

```env
API_BASE_URL=http://localhost:8000
MCP_PRODUCTS_SECRET_KEY=<secreto-aleatorio-exclusivo>
MCP_JWT_ISSUER=growen-api
MCP_PRODUCTS_JWT_AUDIENCE=growen-mcp-products
MCP_RATE_LIMIT_PER_MINUTE=60
MCP_CACHE_TTL_SECONDS=0
MCP_LEGACY_RPC_ENABLED=0
```

Desarrollo local: `http://localhost:8100/mcp`. Docker: `http://mcp_products:8100/mcp`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest mcp_servers\products_server\tests -v
```
