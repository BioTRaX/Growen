<!-- NG-HEADER: Nombre de archivo: RETROSPECTIVE_CANONICAL_BATCH_OPERATIONS_20260720.md -->
<!-- NG-HEADER: Ubicación: docs/RETROSPECTIVE_CANONICAL_BATCH_OPERATIONS_20260720.md -->
<!-- NG-HEADER: Descripción: Retrospectiva técnica del incidente operativo de Redis, Dramatiq y alta canónica batch. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Retrospectiva técnica — Operación del alta canónica batch

Fecha de corte: 2026-07-20.

## 1. Contexto

La sesión comenzó con el mensaje **No se pudo enviar el lote** en el wizard Vue de alta masiva canónica. El diagnóstico abarcó UI, API local, PostgreSQL y Redis en Docker, workers Dramatiq y el panel administrativo de servicios. Durante la recuperación se reprodujeron dos estados diferentes: rechazo de encolado por Redis ausente y pérdida posterior del acceso local a PostgreSQL/Redis al recrear contenedores sobre una red Compose interna.

El alcance terminó incluyendo recuperación de infraestructura, corrección persistente de redes, reintento idempotente de jobs, una acción explícita de reintento en Vue, pruebas focales, documentación operativa y un diagrama editable en FigJam.

## 2. Observaciones

### Entregas verificadas

- Se identificó que el wizard usa siempre `POST /canonical-products/batch-job`, incluso para una sola fila. El alta individual `POST /canonical-products` continúa siendo síncrona y no depende de Redis/Dramatiq.
- PostgreSQL conservó los jobs fallidos y sus ítems; no hubo pérdida del volumen `pgdata` durante las recreaciones.
- `db` y `redis` quedaron conectados a `backend` y `host_access`: se conserva el aislamiento entre servicios y se publican únicamente `127.0.0.1:5433` y `127.0.0.1:6379` para procesos locales.
- `start-dev.ps1 -McpMode All` volvió a completar prerrequisitos, Alembic, API, MCP y Vue.
- `start-dev.ps1 -McpMode All -WithCatalogWorker` completó un arranque real, verificó Redis/Dramatiq y detectó los PID de consumidores `catalog` locales coexistentes.
- Un job `FAILED` con `processed_items=0` puede volver a `QUEUED` usando el mismo `client_request_id`. La selección `FOR UPDATE` evita dos reencolados concurrentes sobre la misma clave.
- El wizard muestra **Reintentar lote** para un job fallido antes de procesar filas. Los fallos parciales por ítem conservan el flujo independiente **Corregir fallidos** con una nueva clave idempotente.
- Se creó un diagrama FigJam del flujo Vue → FastAPI → PostgreSQL/Redis → Dramatiq → equivalencia: `https://www.figma.com/board/Qjg7FmlHI2bjiuyB7umr8P`.

### Evidencia final

- Job final: `COMPLETED`, 10 ítems procesados, 10 éxitos y 0 errores.
- Persistencia final: 10 `canonical_products` y 10 `product_equivalences`.
- Redis conserva el heartbeat de Dramatiq y no dejó mensajes pendientes de la cola procesada.
- Backend batch y orquestación: 13 pruebas aprobadas; incluyen reencolado idempotente, logging estructurado, ejecución fuera del event loop, rollback seguro, preflight de Redis y redirección del worker local.
- Seguridad/red Compose: 8 pruebas aprobadas.
- Frontend: `vue-tsc -b` aprobado.
- `git diff --check` aprobado en los archivos del incidente.

### Límites al cierre

- Los dos jobs originalmente rechazados permanecen `FAILED` como trazabilidad. No deben borrarse ni reprocesarse automáticamente.
- Los jobs anteriores al ajuste no poseen eventos estructurados retroactivos. Los trabajos nuevos emiten NDJSON a stdout de Dramatiq; la persistencia continúa siendo la fuente de verdad del resultado.
- No se ejecutó stage, commit ni push.

## 3. Errores y/u outputs

| Incidente | Causa comprobada | Solución aplicada | Estado residual |
|---|---|---|---|
| `POST /canonical-products/batch-job` devolvió 503 | Redis no estaba escuchando en `localhost:6379`; el arranque base no incluía workers | Se agregó `start-dev.ps1 -WithCatalogWorker`, que inicia/verifica Redis y Dramatiq | Pendiente sólo el preflight visible dentro del wizard |
| Iniciar `catalog_worker` no produjo trabajo | El worker local se inició sin levantar Redis | El orquestador ahora inicia/verifica Redis antes del worker y falla explícitamente si el broker no publica `6379` | Corregido con prueba focal |
| Iniciar Dramatiq desde Administración dejó DB inaccesible | Compose recreó dependencias y materializó `backend: internal`; DB/Redis estaban conectados sólo a esa red y Docker omitió sus bindings host | Se agregó la red no interna `host_access` exclusivamente a DB/Redis, manteniendo los puertos ligados a loopback | Corregido y cubierto por prueba de configuración |
| PostgreSQL estaba `healthy` pero `start-dev.ps1` agotaba 60 segundos | El healthcheck era interno al contenedor; no existía listener real en Windows para `5433` | Además de `host_access`, el launcher prueba el puerto y reconcilia `docker compose up -d db` si el servicio figura activo pero inaccesible | Corregido; validación `-CheckOnly` aprobada |
| Reiniciar Docker Desktop no recuperó inmediatamente los puertos | Los contenedores defectuosos fueron arrancados, no recreados, después del reinicio | Un contenedor temporal confirmó que el motor publicaba puertos; luego se forzó la recreación con la red corregida | Resuelto |
| La API acumuló `ConnectionTimeout` y `PendingRollbackError` | El arranque administrativo de Compose bloqueó la petición; al perder DB se intentó registrar el error con la misma sesión sin `rollback()` | `start`, `stop`, `status` y parada general ejecutan el orquestador con `asyncio.to_thread`; el registro de fallos hace rollback previo | Corregido con pruebas focales |
| Un reintento devolvió 202 pero Redis siguió vacío | La idempotencia devolvía el job `FAILED` existente sin volver a despacharlo | Jobs fallidos sin filas procesadas pasan a `QUEUED` bajo bloqueo y se reencolan | Corregido con prueba focal |
| El wizard no ofrecía cómo recuperar el job | `error_count=0` ocultaba **Corregir fallidos**, aunque el job global estaba `FAILED` | Se agregó **Reintentar lote** para `FAILED && processed_items === 0` | Corregido; typecheck aprobado |
| Dramatiq no mostraba logs de trabajo aun con un job 10/10 | `logger.info()` de `services.jobs.catalog_jobs` no aparecía en la configuración efectiva del contenedor | El actor emite NDJSON explícito a stdout con `job_id`, `item_id`, evento, duración y resultado | Corregido para trabajos nuevos y cubierto por prueba |
| Un mensaje de observabilidad no apareció en logs Docker | Existían simultáneamente un consumidor `catalog` local y Dramatiq Docker; Redis lo entregó al local, cuyo `stdout/stderr=PIPE` no tenía lector | El worker local redirige ambas salidas a `logs/worker_catalog.log`; `start-dev.ps1` advierte y registra PID competidores | El código aplica al próximo inicio; el proceso local heredado requiere reinicio coordinado y no se detuvo automáticamente |
| La ejecución nueva no contenía logs de la API reutilizada | `start-dev.ps1` reutilizó el proceso anterior, que continuó escribiendo en el directorio de logs original | `state.json` agrega `*_log_source_hint` buscando la ejecución que inició API, MCP o Vue | Corregido como pista operativa; puede ser `null` si el origen fue externo |
| La venv pareció rota durante una ejecución del agente | El sandbox negó ejecutar `.venv\Scripts\python.exe`; la versión real era Python 3.14.6 y los imports funcionaban | Se repitió la verificación con autorización acotada; no se recreó la venv | Control agéntico: no recomendar recreación ante `Access denied` sin verificar fuera del sandbox |
| `docker compose config` expandió variables sensibles en salida diagnóstica | El comando renderiza valores de `.env` | No se reprodujeron secretos en reportes ni respuestas | Control agéntico pendiente: preferir `config --services`, `config --quiet` o salida redactada |

## 4. Objetivo

Conservar la cadena causal y transformar los obstáculos observados en controles repetibles: verificar dependencias antes de aceptar trabajo, distinguir salud interna de accesibilidad host, preservar idempotencia sin inmovilizar jobs fallidos, ofrecer recuperación visible en UI y registrar actividad del worker con datos suficientes para operar sin consultar tablas manualmente.

## 5. Propuesta de código o pasos

### Mejoras de producto y operación pendientes

1. Añadir en la UI un preflight previo al wizard que compruebe Redis y un consumidor de la cola `catalog`; el launcher y el panel ya cubren el arranque operativo, pero la pantalla aún no lo anticipa.
2. Agregar timeout explícito y cancelación al subproceso Compose interno del orquestador; el event loop ya no se bloquea, pero un comando Docker colgado conserva un thread ocupado.
3. Enviar eventos del worker a un backend de observabilidad central cuando exista; NDJSON/Docker resuelve el diagnóstico local, no retención ni métricas agregadas.
4. Mantener la prueba Compose que exige una red no interna para servicios publicados al host mientras `backend` permanezca interna.

### Arquitectura agéntica recomendada

- **Skill creada: `diagnose-local-services`.** Ordena la correlación entre UI, IDs, API, DB, Redis, Dramatiq, redes/puertos y logs reutilizados; preserva volúmenes y separa diagnóstico de reparación.
- **Skill ampliada: `create-service`.** Exige grafo de dependencias, modo local/Docker, compatibilidad de red, preflight, eventos estructurados y smoke de encolado/consumo/persistencia.
- **Controles de seguridad registrados.** La nueva skill prohíbe imprimir configuración Compose completa, mostrar `.env`, eliminar volúmenes o reenviar trabajos sin autorización, y usa nombres de servicio en lugar de contenedores hardcodeados.
- **Prompt contextual recomendado.** Incluir ruta exacta del run, modo de cada componente, perfiles Compose, puertos esperados, `RUN_INLINE_JOBS`, job ID/client request ID, estado visible, autorización para reiniciar/recrear y confirmación de si se permite mutar datos de negocio.
- **Agente adicional.** No habría evitado la falla principal: la línea temporal debía mantenerse en una sola coordinación. Un subagente de sólo lectura podría acelerar inventario de logs y documentación, pero no debe operar Docker ni reprocesar jobs en paralelo.
- **Skill de Figma.** Fue suficiente. El primer intento pidió `planKey`; `whoami` resolvió el único plan y el segundo intento creó el FigJam. No se justifica una skill adicional por ese paso.

## 6. Criterios de aceptación

- La cadena UI/API/DB/Redis/Dramatiq se contrastó con logs, código y estado persistido.
- Las tareas entregadas tienen evidencia de pruebas y estado final 10/10.
- Cada incidente incluye causa, solución y deuda residual sin declarar arreglos no realizados.
- La recuperación no eliminó volúmenes ni reprocesó silenciosamente jobs fallidos.
- Se documentan controles agénticos basados sólo en obstáculos observados durante la sesión.
- README, Roadmap, Changelog y guías operativas enlazan o incorporan los hallazgos.
- No se incluyen secretos, cookies ni URLs con credenciales.
