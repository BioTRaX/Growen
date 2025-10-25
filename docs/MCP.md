<!-- NG-HEADER: Nombre de archivo: MCP.md -->
<!-- NG-HEADER: Ubicación: docs/MCP.md -->
<!-- NG-HEADER: Descripción: Capa MCP (Model Context Protocol simplificado): servers y tools disponibles, contrato y flags de entorno -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# MCP Servers (capa de herramientas para IA)

Esta página consolida la documentación de la capa MCP (Model Context Protocol simplificado) usada para exponer "tools" a los modelos de IA mediante un contrato HTTP uniforme. Cada server MCP es un microservicio independiente que actúa como fachada hacia el dominio (productos, búsqueda web, etc.), sin acceso directo a la base de datos.

## Objetivos
- Separar preocupaciones: evitar que los modelos llamen directamente la API o la DB.
- Homogeneizar invocaciones: contrato estándar `POST /invoke_tool` en todos los MCP.
- Controlar acceso por rol de usuario (MVP) y preparar el camino para autenticación firmada y auditoría.

## Contrato de invocación
- Endpoint: `POST /invoke_tool`
- Request JSON:
  ```json
  { "tool_name": "<string>", "parameters": { "user_role": "<rol>", "...": "..." } }
  ```
- Response JSON (éxito):
  ```json
  { "tool_name": "<string>", "result": { /* objeto plano serializable */ } }
  ```
- Códigos de error típicos:
  - 400: parámetros inválidos
  - 403: permiso insuficiente (rol)
  - 404: tool desconocida
  - 502: error interno del tool o de red hacia upstream

Notas:
- `user_role` es obligatorio en MVP (admin|colaborador|proveedor|cliente|guest). Algunas tools restringen a admin/colaborador.
- Las respuestas deben ser serializables a JSON y no incluir tipos complejos.

## Servidores disponibles

### 1) MCP Products (`mcp_servers/products_server`)
- Propósito: exponer herramientas de consulta de productos internos.
- Tools:
  - `get_product_info({ sku, user_role })` → información básica (name, sale_price, stock, sku).
  - `get_product_full_info({ sku, user_role })` → información extendida (MVP: igual a básica). Requiere rol `admin|colaborador`.
- Variables de entorno relevantes (consumidas por la API al invocar):
  - `MCP_PRODUCTS_URL` (default: `http://mcp_products:8001/invoke_tool`)
- Notas de seguridad: el server products MCP consulta la API principal vía HTTP y aplica validación de rol en parámetros; no accede directo a la DB.

### 2) MCP Web Search (`mcp_servers/web_search_server`)
- Propósito: exponer `search_web(query)` para obtener resultados básicos desde un motor HTML público (MVP: DuckDuckGo HTML).
- Tools:
  - `search_web({ query, user_role, max_results?=5 })` → lista `items[]` con `{ title, url, snippet? }`. Roles permitidos: `admin|colaborador`.
- Variables de entorno:
  - `MCP_WEB_SEARCH_URL` (default: `http://mcp_web_search:8002/invoke_tool`)
  - `WEB_SEARCH_BASE` (opcional, default: `https://duckduckgo.com/html/`)
- Notas: En producción se recomienda sustituir por proveedor con SLA (Serper/Bing API) y cachear resultados.

## Integración con la API principal
- Enriquecimiento de productos (`POST /products/{id}/enrich`):
  - Integra opcionalmente `get_product_info` (contexto interno por SKU de variante).
  - Integra opcionalmente `search_web` para anexar resultados al prompt cuando:
    - `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true`.
    - Se pasa el rol del usuario (`sess.user.role`) al tool.
  - Auditoría: incluye `web_search_query` y `web_search_hits` cuando hay búsqueda web, además de `prompt_hash`, `fields_generated` y `source_file` (si se generó `.txt` de fuentes).

## Variables de entorno (resumen)
- `MCP_PRODUCTS_URL`: endpoint del server MCP de productos.
- `MCP_WEB_SEARCH_URL`: endpoint del server MCP de búsqueda web.
- `AI_USE_WEB_SEARCH`: `0/1|true/false|yes/no` para activar búsqueda web en enrich.
- `AI_WEB_SEARCH_MAX_RESULTS`: entero, top N resultados a anexar al prompt (default 3).
- `ai_allow_external` (configuración de `agent_core.config.Settings`): debe ser `true` para permitir llamadas externas.

## Seguridad y roles
- MVP: autorización basada en el campo `user_role` en los parámetros del tool.
- Próximos pasos (obligatorios antes de exponer externamente):
  - Token firmado (HMAC/JWT) con claims (`role`, expiración).
  - Lista blanca de tools por rol y rate limiting por IP/rol.
  - Auditoría estructurada: `tool_name`, `elapsed_ms`, `status`/`error`.

## Testing
- Unit/integración recomendadas:
  - Mock de red con `respx` para las llamadas HTTP de los MCP hacia la API principal.
  - Pruebas de roles (403) y parámetros faltantes (400).
  - Simular fallos de red (timeouts) y validar que el resultado sea `{ error: 'tool_network_failure' }` en la API consumidora.
- La API principal ya contempla degradaciones (maneja errores devolviendo estructuras con `error` en contexto para no romper prompts).

## Roadmap MCP
- Autenticación mediante token firmado (HMAC/JWT) y whitelists por rol.
- Métricas: invocaciones por tool, latencia p50/p95, tasa de error, ranking de queries.
- Caching de resultados para `search_web` y consultas internas frecuentes.
- Consolidar documentación viva con matrices rol→tool y SLA por entorno.

## Troubleshooting
- `403 rol insuficiente`: revisar `user_role` enviado al tool.
- `502 tool failure` o `{ error: 'tool_network_failure' }`: validar `MCP_*_URL`, conectividad y timeouts.
- El enrich no adjunta resultados web: verificar `AI_USE_WEB_SEARCH` y `ai_allow_external=true` (Settings). También revisar `AI_WEB_SEARCH_MAX_RESULTS`.
- Fuentes `.txt` no generadas: la generación depende de que la IA devuelva un objeto `"Fuentes"` en el JSON; el backend registra `num_sources` en la auditoría.
