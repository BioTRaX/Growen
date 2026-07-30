<!-- NG-HEADER: Nombre de archivo: MARKET_CURRENT_STATE_20260721.md -->
<!-- NG-HEADER: Ubicación: docs/MARKET_CURRENT_STATE_20260721.md -->
<!-- NG-HEADER: Descripción: Auditoría operativa, técnica y de migración Vue del dominio Mercado. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

> Documento histórico al 2026-07-21. Desde `20260726_canonical_knowledge_v1`, `market_sources` fue reemplazada por activos de conocimiento y perfiles técnicos. Los conteos reales del despliegue 2026-07-26 están en `CANONICAL_KNOWLEDGE_DEPLOYMENT_SMOKE_20260726.md`.

# Estado actual y evolución del módulo Mercado — 2026-07-21

> **Baseline histórico.** Este relevamiento conserva el estado previo y la secuencia de decisiones del 2026-07-21. No debe usarse como fuente del runtime vigente: `/mercado` está `active/vue`. Consultar `docs/API_MARKET.md` para el contrato actual y `docs/FRONTEND_MIGRATION_VUE.md` para el estado de migración.

## Resultado posterior a la implementación

La auditoría que sigue se conserva como baseline previo. Sus bloqueos quedaron resueltos: `/mercado` está activo en Vue; `market_worker` Docker está healthy y consume la cola exclusiva; los dos mensajes legacy fueron removidos por ID; PostgreSQL está en `20260721_market_observability_v1`; refresh y batch usan jobs idempotentes con estado terminal; fuentes/observaciones/promedios son ARS y auditables; el histórico tiene retención de tres años. La credencial de desarrollo fue rotada, incluyendo `DB_URL`, sin imprimir el reemplazo.

El smoke real confirmó `deduplicated=true`, consumo por el worker y finalización. El producto local 1 terminó `failed` correctamente porque aún no tiene fuentes; lista y diferidos quedaron en cero. React permanece sólo como fallback temporal.

### Incidentes post-implementación verificados

- Administración informó falsamente `Docker no disponible` mientras `market_worker` estaba activo en Docker Desktop. La detección se reconcilió contra Compose, se amplió el timeout mediante `DOCKER_PROBE_TIMEOUT_S` y el health específico distingue broker, heartbeat y cola.
- Para `SUS_0001_INE`, el extractor genérico tomó `79750 ARS` desde contenido secundario en lugar del `3700 ARS` del producto. Los scrapers estático y Chromium ahora priorizan JSON-LD Schema.org `Product/Offer/priceSpecification` y contenedores del producto; un job real dejó fuente y promedio vigentes en `3700 ARS`.
- La tabla repetía el SKU como nombre porque el contrato priorizaba `sku_custom`. `preferred_name` y `product_name` ahora exponen el nombre canónico, mientras `product_sku` conserva el SKU.
- Vue no actualizaba la fila al finalizar el polling. La vista vuelve a consultar el listado al recibir `partial`, `succeeded`, `failed` o `cancelled`.
- Dos procesos API coexistieron sobre `127.0.0.1:8000`, por lo que respuestas viejas y nuevas podían alternarse aunque `/health` fuera exitoso. Windows impidió detener el proceso antiguo sin elevación; el reinicio posterior dejó el sistema operativo. El flujo de diagnóstico ahora exige enumerar todos los listeners antes de validar una corrección.
- Las observaciones incorrectas anteriores se conservaron como histórico inmutable. Actualmente no existe una marca explícita de observación invalidada; es una evolución recomendable para impedir interpretaciones analíticas erróneas sin borrar auditoría.

La sección siguiente es una fotografía histórica previa a la implementación y no describe el runtime actual.

## 1. Contexto

Mercado compara el precio de venta canónico con fuentes competidoras. FastAPI produce trabajos en Redis, Dramatiq consume la cola `market`, el worker extrae precios estáticos o dinámicos y PostgreSQL conserva fuentes, referencia y alertas. Al iniciar este baseline, `/mercado` todavía se servía en React y Vue figuraba `pending/legacy`; ese estado fue superado por la activación Vue documentada al comienzo del archivo.

## 2. Observaciones

Estado local relevado:

- API `:8000`, proxy Vue `:5176`, PostgreSQL `:5433` y Redis `:6379`: accesibles.
- El contenedor `dramatiq` está saludable, pero su comando consume únicamente `drive_sync` y `catalog`; no consume `market`.
- No existe un proceso local `workers.market_scraping` activo.
- Redis contiene dos mensajes listos en `dramatiq:market`; no se consumieron ni eliminaron durante esta auditoría.
- PostgreSQL contiene `0` filas en `market_sources` y `0` en `market_price_history`.
- El scheduler persistente está deshabilitado; umbral 2 días, máximo 50 productos y prioridad para fuentes obligatorias.
- La UI React implementa listado, filtros, edición de precios, detalle de fuentes, alta/baja, descubrimiento y actualización individual/masiva.
- La actualización devuelve `202` y la UI hace una recarga diferida; no existe estado persistente por trabajo ni confirmación terminal por producto.
- `market_price_history` existe en el modelo, pero el worker no escribe observaciones. La capacidad histórica está incompleta.

Flujo operativo real:

```text
React /mercado -> FastAPI -> Redis (market) -> worker local market -> sitios externos -> PostgreSQL
                                      X
                           consumidor actualmente detenido
```

## 3. Errores y/u outputs

Corregidos en esta revisión:

- Credencial embebida en `check_market_tables.py`: reemplazada por `settings.db_url`. La credencial expuesta debe rotarse porque pudo quedar en historial o copias locales.
- Scraper dinámico en Windows: `multiprocessing` impedía aplicar mocks y hacía requests reales durante tests. Ahora Playwright usa un thread dedicado con `ProactorEventLoop`.
- Worker: ya no mezcla precios USD/EUR con el promedio ARS, usa `Decimal`, distingue `completed/partial/failed` y permite reintento cuando todas las fuentes fallan.
- Alertas: la variación ahora compara contra el precio anterior explícito, no contra el valor nuevo ya asignado.
- Scheduler: libera el indicador `working` al terminar y usa la configuración persistida en estado y corridas manuales.
- Health Dramatiq: actualizado a claves reales de Dramatiq 2.x (`dramatiq:<cola>`, `.DQ`, `__heartbeats__`).
- Launchers/diagnóstico: usan la venv, `127.0.0.1`, ocultan URLs sensibles y detectan cola lista, diferida y consumidor sin auto-detectarse como worker.
- API Mercado: restaurado el contrato `sku_custom` primero y nombre original como fallback.
- React: preserva unidades alfanuméricas como `5L` y `20kg`.
- Tests: el entorno fuerza `RUN_INLINE_JOBS=1` para no publicar mensajes en Redis local.

Validaciones ejecutadas:

- Scraper dinámico: 17 aprobadas, 8 omitidas.
- Validaciones de Mercado: 12 aprobadas.
- Regresiones nuevas del worker: 3 aprobadas.
- React Mercado y modal: 37 aprobadas.
- Selección consolidada inicial: 141 aprobadas, 8 omitidas y 7 fallos de contrato de nombre; los 7 fueron corregidos y revalidados.

Deuda confirmada:

- Dos mensajes `market` quedaron pendientes sin consumidor.
- El health global puede confirmar heartbeats Dramatiq, pero un heartbeat no demuestra qué colas consume; el diagnóstico específico sigue siendo necesario.
- Se usa `datetime.utcnow()` ampliamente y Python 3.14.6 ya emite deprecaciones.
- Hay ocho pruebas dinámicas omitidas y una advertencia de coroutine no esperada en un edge case.

## 4. Objetivo

Antes de migrar la pantalla, convertir Mercado en un flujo observable, idempotente y con estados terminales. Vue debe consumir contratos estables; no debe copiar el polling por temporizador ni asumir que `202 Accepted` significa procesamiento exitoso.

## 5. Propuesta de código o pasos

### Prioridad 0 — operatividad

1. Definir el modo productivo del consumidor `market`: servicio Docker dedicado con Playwright/Chromium o worker local administrado. No agregar `market` al contenedor liviano actual sin incluir sus dependencias nativas.
2. Resolver los dos mensajes pendientes sólo con decisión explícita: consumir, reencolar o descartar después de inspeccionar IDs e idempotencia.
3. Crear `market_update_jobs` y `market_update_items` con estados `queued/running/partial/succeeded/failed/cancelled`, `correlation_id`, intentos, timestamps y error tipado.
4. Hacer idempotente el enqueue por producto/ventana temporal y evitar duplicados entre scheduler, batch y botón manual.

### Prioridad 1 — exactitud y rendimiento

1. Separar `market_price_manual` de `market_price_computed`; hoy el scraping puede sobrescribir una corrección humana.
2. Persistir cada observación en `market_price_history`, con retención y downsampling documentados.
3. Definir moneda objetivo ARS y snapshot de conversión FX; hasta entonces, fuentes no ARS quedan fuera del agregado.
4. Reemplazar promedio simple por mediana o media recortada, con detección de outliers, mínimo de fuentes y score de confianza.
5. Paralelizar sólo I/O de scraping con semáforo global y límite por dominio; persistir en serie o con sesiones independientes para no compartir `AsyncSession` concurrentemente.
6. Evitar commits internos por fuente/alerta; delimitar transacciones y guardar resultados parciales de forma explícita.
7. Agregar retry exponencial con jitter, circuit breaker por dominio y cooldown para 403/429.
8. Migrar timestamps a UTC aware y usar `ZoneInfo` para el scheduler.

### Prioridad 2 — migración Vue

Proponer un primer corte en `frontend-vue/src/modules/market/`:

- `api/marketApi.ts`: contratos HTTP y errores tipados.
- `types/market.ts`: producto, fuente, job e item de job.
- `composables/useMarketProducts.ts`: filtros paginados con cancelación de respuestas obsoletas.
- `composables/useMarketJob.ts`: polling cancelable hasta estado terminal y cleanup al desmontar.
- `components/MarketTable.vue`, `MarketFilters.vue`, `MarketSourceList.vue`, `MarketJobStatus.vue`.
- `views/MarketView.vue` y `MarketDetailView.vue` o drawer persistente.

El corte inicial debe conservar `/mercado`, roles `colaborador|admin`, CSRF, fallback React y todos los códigos 401/403/404/409/422/500. Activar Vue sólo después de pruebas, typecheck, build y smoke con worker real.

### Evolución funcional

- Score de salud y confianza por fuente: frescura, tasa de éxito, latencia, volatilidad y último error.
- Recomendación de precio con margen objetivo y explicación, sin aplicar cambios automáticamente.
- Alertas accionables: reconocer, silenciar, resolver y vincular a la observación que las originó.
- Descubrimiento asistido con deduplicación canónica de URL y aprobación humana.
- Dashboard histórico de dispersión, tendencia, cobertura y antigüedad por categoría/proveedor.
- Métricas: jobs por estado, profundidad de cola, p50/p95, éxito por dominio, browser fallback, fuentes frescas y productos sin cobertura.

### Dudas y sugerencias

1. ¿El valor manual debe prevalecer siempre, tener vencimiento o convivir con el calculado?
2. ¿La referencia oficial será exclusivamente ARS? Si se admiten USD/EUR, ¿qué proveedor y momento de FX se auditan?
3. ¿Qué competidores están autorizados y qué políticas de robots/Términos de Servicio deben respetarse?
4. ¿Cuál es la retención requerida para observaciones e incidentes?
5. ¿El worker debe ser Docker en producción y local sólo en desarrollo?
6. ¿Se autoriza inspeccionar y resolver los dos mensajes actualmente pendientes?

## 6. Criterios de aceptación

- Broker y consumidor `market` se distinguen y se monitorean por separado.
- Un trabajo posee estado persistente, idempotencia, intentos y resultado terminal por producto/fuente.
- No se promedian monedas distintas ni se sobrescribe un valor manual sin regla explícita.
- Las observaciones históricas y alertas son trazables al job y fuente que las generó.
- Vue conserva ruta, roles, contratos y fallback hasta completar la paridad.
- Pruebas backend/React/Vue, typecheck, build y smoke operativo quedan aprobados.
- Se documentan los cambios y se actualiza cualquier contenido desactualizado en `Roadmap.md`, `README.md` y `docs/`.
