<!-- NG-HEADER: Nombre de archivo: README.md -->
<!-- NG-HEADER: Ubicación: mcp_servers/web_search_server/README.md -->
<!-- NG-HEADER: Descripción: Documentación del servidor MCP de búsqueda web. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# MCP Web Search Server (MVP)

Servidor MCP mínimo que expone un tool `search_web(query)` para obtener resultados básicos (título/URL/snippet) desde DuckDuckGo HTML.

- Endpoint estándar: `POST /invoke_tool` con `{ tool_name, parameters }`.
- Herramientas: `search_web` (requiere `user_role` admin|colaborador).
- Variables:
  - `WEB_SEARCH_BASE` (opcional): Base URL del buscador (por defecto DuckDuckGo HTML).

Uso local:

```bash
uvicorn mcp_servers.web_search_server.main:app --host 127.0.0.1 --port 8002
```

Ejemplo de invocación:

```json
{
  "tool_name": "search_web",
  "parameters": { "query": "sustrato coco uso indoor", "user_role": "colaborador", "max_results": 3 }
}
```

Notas:
- Es un MVP sin API de búsqueda dedicada; en producción, preferir un proveedor con SLA (Serper/Bing API) y caching.
- Manejo de red a mejor esfuerzo; devuelve `{ error: 'network_failure' }` ante problemas.

Integración con la API principal (enriquecimiento IA):
- La API `POST /products/{id}/enrich` puede anexar resultados de `search_web` al prompt cuando `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true`.
- Variables relacionadas:
  - `MCP_WEB_SEARCH_URL`: endpoint de este servicio (default `http://mcp_web_search:8002/invoke_tool`).
  - `AI_WEB_SEARCH_MAX_RESULTS`: máximo de resultados a incluir en el prompt (default 3).
