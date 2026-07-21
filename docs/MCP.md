<!-- NG-HEADER: Nombre de archivo: MCP.md -->
<!-- NG-HEADER: Ubicación: docs/MCP.md -->
<!-- NG-HEADER: Descripción: Protocolo MCP real, servidores, seguridad y operación -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# MCP en Growen

## Tags en Products MCP (2026-07-18)

`find_products_by_name` delega en `/catalog/search`, que busca por nombre, descripción, SKU y tags manteniendo AND entre términos. `find_products_by_name`, `get_product_info` y `get_product_full_info` devuelven siempre `tags: list[str]`, incluso como lista vacía. No se agregó una tool paralela: se conserva el flujo búsqueda → detalle y los roles existentes.

Growen utiliza Model Context Protocol real mediante el SDK oficial de Python. Cada servidor expone Streamable HTTP en `/mcp`, permite descubrimiento con `tools/list` e invocación con `tools/call`. `/invoke_tool` queda disponible temporalmente como adaptador RPC deprecado.

La dependencia está acotada a `mcp>=1.27,<2`: v1 es la línea estable. La adopción de v2 se tratará en una tarea independiente cuando exista una versión estable y pase los contract tests de Growen.

## Inicio local

```powershell
# DB + API + Products MCP + Vue
.\scripts\start-dev.ps1

# Incluye Web Search
.\scripts\start-dev.ps1 -McpMode All

# Solo verifica configuración
.\scripts\start-dev.ps1 -CheckOnly
```

Endpoints locales:

- Products: `http://localhost:8100/mcp`.
- Web Search: `http://localhost:8102/mcp`.
- Health: reemplazar `/mcp` por `/health`.

## Descubrimiento e invocación

`agent_core/mcp_client.py` crea una sesión autenticada, ejecuta `initialize`, obtiene `tools/list`, filtra por rol y convierte `inputSchema` al formato de function calling. La ejecución utiliza `tools/call` y prefiere `structuredContent`.

Tools actuales:

| Servidor | Tool | Roles |
|---|---|---|
| Products | `find_products_by_name` | Todo usuario autenticado |
| Products | `get_product_info` | Todo usuario autenticado |
| Products | `get_product_full_info` | admin, colaborador |
| Web Search | `search_web` | admin, colaborador |

## Seguridad

- Header: `Authorization: Bearer <JWT>`.
- Claims requeridos: `iss`, `aud`, `sub`, `role`, `iat`, `exp`, `jti`.
- El rol no forma parte de los argumentos visibles para el modelo.
- El cliente filtra tools y el servidor vuelve a autorizar cada llamada.
- Cada servidor filtra también `tools/list` según el rol autenticado, evitando revelar tools no autorizadas a clientes MCP externos.
- Rate limiting en memoria por proceso durante desarrollo.
- Auditoría estructurada sin tokens ni parámetros sensibles.
- `X-MCP-Token` solo es aceptado por los adaptadores legacy; los clientes MCP nuevos usan Bearer.

## Configuración

```env
MCP_PRODUCTS_URL=http://localhost:8100/mcp
MCP_WEB_SEARCH_URL=http://localhost:8102/mcp
MCP_PROTOCOL_VERSION=2025-11-25
MCP_JWT_ISSUER=growen-api
MCP_PRODUCTS_JWT_AUDIENCE=growen-mcp-products
MCP_WEB_SEARCH_JWT_AUDIENCE=growen-mcp-web-search
MCP_TOOL_CATALOG_TTL_SECONDS=60
MCP_RATE_LIMIT_PER_MINUTE=60
MCP_LEGACY_RPC_ENABLED=0
# Solo al exponer detrás de proxy/LAN; listas explícitas separadas por coma
MCP_ALLOWED_HOSTS=
MCP_ALLOWED_ORIGINS=
```

`MCP_PRODUCTS_SECRET_KEY` y `MCP_WEB_SEARCH_SECRET_KEY` deben ser aleatorios, diferentes y tener al menos 32 bytes. Cada servidor valida una audience y un `kid` propios; durante una rotación puede configurarse únicamente la clave anterior correspondiente. El bootstrap genera valores locales sin mostrarlos.

El rate limiting y la revocación de `jti` usan Redis en Compose. Si Redis falla, el control falla cerrado. El backend en memoria queda limitado a desarrollo y tests de un solo proceso.

La publicación remota no está habilitada por esta autenticación interna. Antes de exponer `/mcp` fuera de loopback o de la red privada se debe incorporar OAuth 2.1, metadata del recurso protegido y tokens ligados a cada recurso MCP.

La protección contra DNS rebinding está activa. Por defecto acepta únicamente loopback y los nombres internos de Compose; cualquier hostname u origen adicional debe declararse explícitamente con las variables anteriores.

## Compatibilidad y retiro del RPC

`POST /invoke_tool` emite warnings, incrementa `legacy_invocations_total` (visible en `/health`) y está marcado deprecado. No se permiten consumidores nuevos. Se eliminará cuando todo el repositorio use `/mcp` y no se observen llamadas legacy durante dos semanas de pruebas.

## Testing

```powershell
.\scripts\check-quality.ps1
```

La suite incluye seguridad, roles, adaptador legacy, catálogo dinámico y contratos MCP. El workflow remoto es manual y solo consume créditos al ejecutarlo desde GitHub Actions.
