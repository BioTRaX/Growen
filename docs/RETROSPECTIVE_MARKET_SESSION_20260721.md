<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_MARKET_SESSION_20260721.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_MARKET_SESSION_20260721.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica y de conocimiento agéntico de la estabilización y migración de Mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica de Mercado — 2026-07-21

## 1. Contexto

La sesión relevó y evolucionó el servicio de precios de competencia desde un scraper sin consumidor productivo ni seguimiento terminal hasta un módulo Vue con worker Docker dedicado, jobs observables e histórico ARS. Luego se resolvieron dos incidentes post-implementación observados en uso real: discrepancia entre Docker Desktop y Administración, y extracción/presentación incorrecta del primer producto configurado.

## 2. Observaciones

Tareas completadas con evidencia:

- Se creó el esquema focal de Mercado mediante Alembic: alertas, jobs, items, resultados por fuente, validación y observaciones inmutables.
- Se eliminaron por ID los dos mensajes legacy sin vaciar otras colas.
- Refresh individual y batch generan trabajos idempotentes con estados terminales y trazabilidad por producto/fuente.
- Las fuentes y promedios efectivos aceptan exclusivamente ARS; el promedio usa una observación vigente por fuente activa y el histórico se retiene tres años.
- Se reemplazó la referencia manual directa por observaciones auditables.
- Se eliminó el patrón N+1 del listado y se expusieron histórico, jobs, cobertura y posición de precio.
- Se creó `market_worker` Docker no-root con Chromium, HTTP primero, fallback dinámico, límites de concurrencia, heartbeat y control administrativo.
- `/mercado` se activó en Vue con ocho bandas accesibles, filtros, batch, detalle, histórico SVG y polling terminal; React quedó como fallback temporal.
- La credencial de desarrollo expuesta se rotó e invalidó sin reescribir Git ni imprimir valores.
- Para `SUS_0001_INE`, un job real `d9b2b019-91d5-4cb5-b6b3-e38bd7217746` terminó `succeeded` y persistió fuente/promedio en `3700 ARS`.

Validación final disponible: `118 passed, 8 skipped` en la selección backend focal, `20 passed` en Vue, typecheck/build Vue aprobados, imagen del worker reconstruida y smoke real job → worker → PostgreSQL completado.

## 3. Errores y/u outputs

| Síntoma | Causa comprobada | Estado |
|---|---|---|
| Administración mostraba `Docker no disponible` con contenedor verde | El estado local fallido prevalecía sobre Compose y la sonda de Docker Desktop agotaba un timeout insuficiente | Corregido mediante reconciliación Compose, timeout configurable y health específico |
| Mercado mostraba `79750 ARS` para una página cuyo precio era `3700 ARS` | El selector genérico encontraba primero cuotas/carrusel; el HTML incluía JSON-LD `Product/Offer` correcto | Corregido priorizando datos estructurados y contenedores del producto en ambos scrapers |
| Nombre y SKU mostraban `SUS_0001_INE` | El backend usaba `sku_custom` como `preferred_name` | Corregido separando nombre canónico y `product_sku` |
| La fila no cambiaba al finalizar un job | El composable seguía el job, pero la vista no refrescaba el listado al llegar a estado terminal | Corregido con recarga terminal |
| La UI podía seguir mostrando el contrato anterior | Dos procesos Uvicorn escuchaban simultáneamente en `127.0.0.1:8000`; el proceso antiguo no pudo detenerse por `Acceso denegado` | Resuelto operativamente mediante reinicio; prevención automática pendiente |
| Suite focal emitió `coroutine 'scrape_dynamic_price' was never awaited` | Caso de borde de mocks/cleanup dinámico en Windows | Deuda conocida; no afecta el job real validado, pero no debe normalizarse ni ocultarse |
| Ocho pruebas dinámicas quedaron omitidas | Condiciones/plataforma documentadas en la suite | Deuda conocida; revisar antes de endurecer el gate multiplataforma |
| Capturas erróneas siguen visibles en histórico | La inmutabilidad conserva evidencia, pero el modelo no permite marcar una observación como invalidada | Evolución pendiente |

## 4. Objetivo

Conservar una fuente de verdad factual para futuras intervenciones, evitando repetir tres errores de diagnóstico: equiparar contenedor verde con servicio operativo, aceptar un health exitoso con múltiples listeners y validar un scraper sólo contra selectores genéricos sin contrastar datos estructurados y persistencia final.

## 5. Propuesta de código o pasos

Mejoras agénticas sustentadas en obstáculos de esta sesión:

1. Se amplió `diagnose-local-services` para enumerar listeners/PID/proceso padre, comprobar frescura de imágenes Docker y declarar explícitamente los bloqueos de permisos.
2. No se justifica un nuevo agente especializado: los incidentes dependían de correlacionar UI, API, Docker, Redis y PostgreSQL en una única línea causal. Separar agentes habría aumentado el riesgo de conclusiones parciales sobre estado compartido.
3. Sí conviene agregar al launcher una guarda automática que falle si detecta más de un listener en el puerto de la API. La sesión sólo documenta esta evolución porque terminar procesos ajenos requiere una política explícita de propiedad y privilegios.
4. Conviene extender `market_price_history` con `invalidated_at`, `invalidated_by` y `invalidation_reason`, excluyendo esas filas de analítica sin borrarlas.
5. El prompt de diagnóstico futuro debería aportar al inicio una matriz de ejecución esperada —componente, modo local/Docker, puerto, cola e imagen— y exigir IDs de job/correlación. Esto habría reducido la investigación del falso estado Docker y de la API duplicada.
6. Corregir el warning de coroutine con `tracemalloc` y convertir warnings async en error dentro de la suite dinámica una vez saneada.

## 6. Criterios de aceptación

- El reporte diferencia tareas completadas, incidentes corregidos y deuda residual.
- Cada solución está vinculada a una causa observada durante la sesión.
- La documentación de API, scraping, desarrollo y estado actual refleja el runtime vigente.
- La skill de diagnóstico incorpora listeners duplicados, imágenes Docker obsoletas y límites de permisos.
- Se documentan los cambios y se mantienen actualizados `Roadmap.md`, `CHANGELOG.md` y los documentos bajo `docs/`.
