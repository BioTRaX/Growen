<!-- NG-HEADER: Nombre de archivo: CANONICAL_KNOWLEDGE_DEPLOYMENT_SMOKE_20260726.md -->
<!-- NG-HEADER: Ubicación: docs/CANONICAL_KNOWLEDGE_DEPLOYMENT_SMOKE_20260726.md -->
<!-- NG-HEADER: Descripción: Evidencia del despliegue y smoke real de conocimiento canónico. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Despliegue y smoke real — 2026-07-26

## Resultado

- Backup previo validado: `backups/pg/pre_canonical_knowledge_20260726_1911.dump` (314079 bytes).
- PostgreSQL avanzó de `20260725_canonical_enrichment_v2` a `20260726_canonical_knowledge_v1`.
- `vector` ya existía. La prueba desde PostgreSQL vacío también creó la extensión y alcanzó head.
- Backfill real: 1 fuente → 1 activo + 1 perfil Mercado; se conservaron 6 observaciones, 3 resultados y 1 alerta, con 0 referencias históricas huérfanas.
- Imágenes Docker construidas: MCP Web Search, knowledge worker, Enrich, Mercado, API y frontend dual.
- Despliegue efectivo: PostgreSQL/Redis/workers en Docker; API y Vue permanecieron en los launchers locales canónicos (`8000` y `5176`) para evitar listeners duplicados.
- Health final: knowledge worker, Enrich, Mercado y Dramatiq saludables; colas `canonical_knowledge` y `enrichment` sin pendientes.
- `ENRICH_V2_ENABLED=1` y API key OpenAI configurada dentro del worker, verificada sin imprimirla.

## Smoke autenticado

`scripts/test_login_flow.py` dejó de contener credenciales/cookies hardcodeadas. Lee `.env`, no muestra secretos y verificó:

1. `/health` 200.
2. login admin 200 y `/auth/me` autenticado.
3. Mercado 200.
4. Centro de Conocimiento 200 con el activo migrado.
5. mutación con CSRF real, encolado 202 y polling.
6. job final `2a6096b532f440128323cdcec2c18d85` en `completed` (también completaron las pasadas previas de diagnóstico).
7. `/health/knowledge-worker` 200.

## Hallazgos corregidos durante el despliegue

- Las rutas estáticas `/knowledge/jobs|facts|history|upload` podían ser capturadas por `/{asset_id}`; los converters enteros preservan el contrato y evitan `422`.
- El MCP local rechazó `host.docker.internal` con `421`; los workers híbridos usan el gateway con hostname permitido sin ampliar allowlists.
- Una salida IA no JSON hacía fallar la ingesta. Ahora se descarta sólo la extracción IA, se conserva versión/hash/metadatos y el job completa con confianza determinista.
- `DELETE /market/sources/{id}` archiva el activo y desactiva el perfil; no borra histórico.
- Worker, promedio y agregados de Mercado filtran conocimiento confirmado con etiqueta `market` y capacidad `price`; para fuentes automáticas exigen ARS y entrega argentina confirmados. Una fuente descubierta pendiente ya no puede afectar referencias.
- El perfil migrado quedó `warning`, ARS confirmado y entrega argentina desconocida. Se preservó sin inventar la atestación; staff puede confirmarla desde el formulario Mercado del Centro **Conocimiento**.
- Uvicorn con `--reload` reinicia la API al modificar cualquier Python del workspace. Un smoke iniciado durante ese intervalo puede autenticar y perder el siguiente request; esperar `Application startup complete` antes de medir.

## Alembic y drift

`alembic heads` y `alembic current` devolvieron `20260726_canonical_knowledge_v1`. `alembic check` continúa informando drift histórico amplio (defaults, tipos, índices y tablas anteriores, incluido `sku_sequences`); no señaló una segunda head y no se generó una revisión automática para mezclar esa deuda con Conocimiento. La prueba PostgreSQL vacía es el gate reproducible de esta entrega.

## Recreación por cambios de entorno

`env_file` y `environment` se leen al crear el contenedor. Un cambio de `.env` requiere recrear los contenedores afectados (`docker compose up -d --force-recreate <servicio>`); `restart` no actualiza el entorno. No hace falta reconstruir imagen salvo cambios de código copiado, Dockerfile o dependencias. Los procesos locales deben reiniciarse.
