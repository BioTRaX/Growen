---
name: diagnose-local-services
description: Diagnostica fallos del stack local Growen correlacionando UI, API, PostgreSQL, Redis, Dramatiq, Docker Compose y logs por ejecución. Usar cuando un servicio figura activo pero no responde, un lote queda pendiente o los logs parecen vacíos.
---

# Diagnosticar servicios locales

1. Leer `AGENTS.md`, `.agent/workflows/python-commands.md`, `docs/DEVELOPMENT_WORKFLOW.md` y la documentación del dominio afectado.
2. Registrar el modo real de cada componente: proceso local, servicio Compose, puerto host, red interna, URL y archivo o comando de logs.
3. Correlacionar en este orden: mensaje UI, request/correlation ID, job ID persistido, API productora, broker Redis, actor Dramatiq y efecto final en PostgreSQL.
4. Distinguir `running` de accesible: comprobar health interno, puerto publicado al host y resolución por nombre de servicio dentro de Docker.
5. Consultar `logs/dev/<run>/state.json`; si un proceso fue reutilizado, seguir `*_log_source_hint` o localizar la ejecución que realmente lo inició.
6. Usar nombres de servicio de Compose; no depender de nombres concretos de contenedor ni exponer la salida completa de `docker compose config`.
7. Antes de reparar, preservar volúmenes y trabajos persistidos. No ejecutar `down -v`, borrar colas ni reenviar trabajos sin autorización.
8. Si la reparación está autorizada, restaurar en orden PostgreSQL, Redis, consumidor Dramatiq y API productora; aplicar el cambio mínimo reproducible.
9. Validar con un trabajo controlado: debe encolarse, emitir eventos estructurados, terminar y persistir exactamente una vez.
10. Entregar evidencia antes/después, causal raíz, impacto, riesgo residual y documentación actualizada.

Ejecutar Python únicamente con `.venv\Scripts\python.exe` o dentro de Docker.
