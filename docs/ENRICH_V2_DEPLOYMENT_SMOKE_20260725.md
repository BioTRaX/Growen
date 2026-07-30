<!-- NG-HEADER: Nombre de archivo: ENRICH_V2_DEPLOYMENT_SMOKE_20260725.md -->
<!-- NG-HEADER: Ubicación: docs/ENRICH_V2_DEPLOYMENT_SMOKE_20260725.md -->
<!-- NG-HEADER: Descripción: Evidencia del despliegue local y smoke autenticado de Enrich v2. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Despliegue y smoke de Enrich v2 — 2026-07-25

## Contexto

El despliegue se ejecutó sobre el stack Compose local de Growen, preservando los
volúmenes PostgreSQL y Redis. Se validó migración, MCP Web Search, worker
dedicado, API, detalle Vue, permisos y activación del feature flag.

## Configuración efectiva

- PostgreSQL: `growen/postgres:pgvector`, publicado sólo en loopback.
- Alembic: `20260725_canonical_enrichment_v2 (head)`.
- Redis: disponible para broker y heartbeat.
- MCP Web Search: saludable, protocolo `2025-11-25`, sin RPC legacy.
- Worker: un proceso, dos threads, cola `enrichment`, heartbeat v2.
- API: saludable y conectada a Redis por el nombre de servicio Compose.
- Frontend: React/Vue dual; `/productos/:id` entrega el shell Vue.
- `ENRICH_V2_ENABLED=1`.
- IA: modo `auto`; OpenAI no tiene clave y Ollama no está accesible en el host.

No se registraron ni documentaron credenciales.

## Resultado por etapa

| Etapa | Resultado | Evidencia |
|---|---|---|
| Extensión `vector` | Aprobado | Ya existía en `pg_extension`; no fue necesario crearla. |
| Migración | Aprobado | Upgrade desde `20260722_chat_observability_v3` al head nuevo. |
| Auditoría de esquema | Aprobado | Jobs, revisión canónica y retiro del campo legacy verificados. |
| MCP Web Search | Aprobado | Health 200, negociación MCP y búsqueda autenticada con cinco resultados. |
| Redis y worker | Aprobado | Consumidor listo y heartbeat con `queue=enrichment`. |
| API | Aprobado | `/health`, `/health/db` y `/health/enrichment-worker`. |
| Vue | Aprobado | `/health` 200 y `/productos/1` entrega `/vue-assets/`. |
| Roles | Aprobado | Matriz autenticada detallada debajo. |
| Job real | Parcial esperado | Cinco fuentes; generación bloqueada por falta de proveedor IA. |
| Activación | Aplicada | Flag efectivo `ENRICH_V2_ENABLED=1` dentro de la API. |

## Pruebas finales

- Backend/MCP focal: 24 aprobadas; una advertencia deprecada de Starlette/httpx.
- Productos Vue y manifiesto: 32 aprobadas.
- Typecheck Vue: aprobado sin errores.
- `docker compose config --quiet`: aprobado.

## Smoke autenticado

Se usó el producto interno `11`, vinculado al canónico `2`. Los usuarios de smoke
`cliente` y `colaborador` fueron temporales y se eliminaron en `finally`. No se
alteró stock ni contenido canónico.

| Rol | Login y `/auth/me` | `GET /products/11` | Historial | Versiones |
|---|---:|---:|---:|---:|
| `guest` | Aprobado | 200, canónico 2 | 403 | No solicitado |
| `cliente` | Aprobado | 200, canónico 2 | 403 | 403 |
| `colaborador` | Aprobado | 200, canónico 2 | 200 | 200 |
| `admin` | Aprobado | 200, canónico 2 | 200 | 200 |

## Hallazgos y correcciones

1. El lock del MCP incluía `pywin32` sin marcador. Se restauró
   `sys_platform == "win32"` para el build Linux reproducible.
2. La imagen MCP no copiaba `agent_core/chat_policy.py`; ahora lo incluye.
3. FastMCP canonicaliza `/mcp` como `/mcp/`; el cliente normaliza la barra final.
4. El descubrimiento con `server_name="web_search"` ahora excluye MCP Products.
5. El parser desenvuelve href DuckDuckGo `//duckduckgo.com/l/?uddg=...`.
6. Los retries reutilizan fuentes persistidas y conservan como máximo cinco URLs.
7. Los errores de integridad ya no guardan parámetros SQL ni evidencia.
8. `frontend` incorpora `host_access` para publicar `127.0.0.1:5173`.
9. La API recibe `REDIS_URL=redis://redis:6379/0` dentro de Compose.
10. Al recrear la API para activar el flag, Nginx conservó la IP anterior del
    upstream y su healthcheck respondió 502. Se recreó `frontend` después de la
    API; el contenedor volvió a `healthy` y `/health` respondió 200. En Compose,
    respetar el orden API → frontend también al cambiar configuración.

## Job final controlado

El job `a7d57550c82441658094af8744ae3b18` confirmó:

- creación HTTP 202 y consumo en la cola dedicada;
- tres intentos según configuración;
- cinco fuentes persistidas;
- cero campos aplicados;
- estado terminal `failed`;
- error explícito: no existe proveedor IA válido.

Esto valida el manejo seguro de ausencia de proveedor, pero no una generación
exitosa. Para aprobar contenido end-to-end debe configurarse `OPENAI_API_KEY` o
levantarse Ollama con el modelo declarado y repetir un job hasta
`review_required`, `partially_applied` o `applied`.

## Operación y rollback

- Salud: `GET http://127.0.0.1:8000/health/enrichment-worker`.
- Worker: `docker compose logs -f enrichment_worker`.
- MCP: `docker compose logs -f mcp_web_search`.
- Para impedir nuevos jobs, usar `ENRICH_V2_ENABLED=0` y recrear la API.
- El rollback visual cambia el runtime del detalle a React; no requiere downgrade.
- El downgrade de `20260725_canonical_enrichment_v2` permanece bloqueado.

## Criterio pendiente

Antes de considerar Enrich v2 plenamente operativo debe documentarse un segundo
smoke con proveedor real, propuesta estructurada válida y revisión/aplicación sin
sobrescribir `content_revision`. Actualizar este documento y cualquier instrucción
que resulte desactualizada durante esa ejecución.
