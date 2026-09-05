---
name: diagnose-local-services
description: Usar cuando un servicio local de Growen figura activo pero no responde, un job queda pendiente o los logs de la ejecución parecen vacíos.
---

# Diagnosticar servicios locales

**REQUIRED BACKGROUND:** aplicar `superpowers:systematic-debugging` para el método causal. Esta skill sólo define la topología y las comprobaciones propias de Growen.

1. Leer `AGENTS.md`, `.agent/workflows/python-commands.md`, `docs/DEVELOPMENT_WORKFLOW.md` y la documentación del dominio afectado.
2. Registrar el modo real de cada componente: proceso local, servicio Compose, puerto host, red interna, URL y archivo o comando de logs.
3. Correlacionar en este orden: mensaje UI, request/correlation ID, job ID persistido, API productora, broker Redis, actor Dramatiq y efecto final en PostgreSQL.
4. Distinguir `running` de accesible: comprobar health interno, puerto publicado al host y resolución por nombre de servicio dentro de Docker.
5. Enumerar todos los listeners del puerto, PID, proceso padre, hora de inicio y comando. Más de un listener saludable es un estado ambiguo: una respuesta `/health` no demuestra qué versión atendió el request.
6. Consultar `logs/dev/<run>/state.json`; si un proceso fue reutilizado, seguir `*_log_source_hint` o localizar la ejecución que realmente lo inició.
7. Para servicios en imagen Docker, comprobar si el contenedor activo usa una imagen anterior al cambio. Reconstruir sólo el servicio afectado cuando cambió código copiado durante el build.
8. Usar nombres de servicio de Compose; no depender de nombres concretos de contenedor ni exponer la salida completa de `docker compose config`.
9. Antes de reparar, preservar volúmenes y trabajos persistidos. No ejecutar `down -v`, borrar colas ni reenviar trabajos sin autorización.
10. Si la reparación está autorizada, restaurar en orden PostgreSQL, Redis, consumidor Dramatiq y API productora; aplicar el cambio mínimo reproducible. Detener procesos mediante su launcher propietario; si Windows deniega acceso, registrar el PID y solicitar reinicio elevado en vez de ocultar el residuo.
11. Validar con un trabajo controlado: debe encolarse, emitir eventos estructurados, terminar y persistir exactamente una vez.
12. Entregar evidencia antes/después, causal raíz, impacto, riesgo residual y documentación actualizada.

Ejecutar Python únicamente con `.venv\Scripts\python.exe` o dentro de Docker.
