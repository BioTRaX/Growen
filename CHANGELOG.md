<!-- NG-HEADER: Nombre de archivo: CHANGELOG.md -->
<!-- NG-HEADER: Ubicación: CHANGELOG.md -->
<!-- NG-HEADER: Descripción: Historial de cambios y dependencias añadidas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Changelog

## 2026-08-17 — RAG operativo y paridad de Chat Vue

- Se cargó en desarrollo el corpus RAG v1: 8 fuentes sintéticas/centinela y 2 documentos reales curados, todos con scopes explícitos de rol y canal.
- El gate real aprobó sin fugas: recall@5 sintético y curado 1,00, MRR 1,00, citas 100 %, presupuesto de contexto 100 % y cache separada/invalidation correcta.
- Los documentos curados ahora se fragmentan antes de generar embeddings; se eliminó el uso de `datetime.utcnow()` en el runner RAG para Python 3.14.
- WebSocket incorpora RAG autorizado dentro de `ChatOrchestrator` y devuelve citas tanto en respuestas normales como al finalizar streaming.
- HTTP usa el resolver local determinista de catálogo con Ollama. HTTP y WebSocket sanitizan en backend SKU, proveedor, fuentes internas y stock exacto para perfiles públicos.
- Chat Vue consume el contrato real `data.results`, renderiza precio/disponibilidad pública y campos operativos sólo para staff. Aprobaron typecheck, 91 pruebas Vue y build.
- El smoke guest real aprobó carga y respuesta WebSocket sin errores de consola; la UI deja de quedar bloqueada si el socket se corta durante una respuesta.
- `/chat` conserva `ready/legacy`: estos avances habilitan smoke local, no activación automática de tráfico Vue.

- Se agregó captura segura de `telegram_canary_user_id` mediante long polling y
  comando privado `/canary`, junto con una guía específica que separa canary y
  controlador de rollout.
- `OPENAI_API_KEY_FILE` usa el lector central de secretos; el generador admite
  captura oculta y el proveedor OpenAI deja de devolver prompts como fallback.
- Se activó el preflight local restringido al canary, se validó el primer
  procesamiento Telegram y se corrigió el filtro JSONB de scopes RAG en
  PostgreSQL.
- Se eliminó el fallback legacy que clasificaba cualquier frase general como
  consulta de precio; Telegram deriva ahora el smalltalk al chat general.
- Se corrigió `OLLAMA_MODEL`/`ENRICH_OLLAMA_MODEL` a `llama3.1:8b`; el nombre
  incompleto provocaba HTTP 404 antes de reservar VRAM para generación.
- Telegram usa resolución determinista para catálogo cuando el proveedor es
  Ollama y aplica un render público sin SKU, proveedor ni stock exacto.
- Los fallos internos Telegram se registran como `ChatRun.failed` con códigos
  seguros, aunque el usuario reciba un mensaje público controlado.

## 2026-08-17 — Perfil Ollama con VRAM prioritaria

- Se reemplazó el requisito fijo de 16 GiB de RAM libre por gates de VRAM, overhead de RAM, pagefile y disco.
- Se agregó `scripts/ollama-preflight.ps1`, contexto explícito de 4096 y separación entre `OLLAMA_HOST` local y `OLLAMA_HOST_DOCKER`.
- El generador de secretos admite captura interactiva oculta del token y del canary.
- El preflight Ollama real aprobó y se agregó un modo `--development` sin autoavance para probar Telegram con un único usuario permitido.

## 2026-08-16 — Chat local y rollout auditable

- WebSocket asíncrono con orquestación completa y fixtures SQLite sin `dispose()` por prueba.
- Ollama async fail-closed y RAG local de 1536 dimensiones con corpus/evaluador controlado.
- Rate limit Redis multiproceso, polling recuperable, secretos `*_FILE` y worker Compose dedicado.
- Migración `20260816_chat_rollout_v1`, controlador automático y activación Vue condicionada a `vue_eligible` con rollback.
- Tráfico no habilitado: preflight de RAM/modelos y smokes productivos siguen pendientes.

## 2026-08-15 — Gate explícito para retrospectivas de sesión

- `retrospectiva-tecnica-sesion` sólo se activa cuando el usuario informa que llegó el final de la sesión o chat.
- Completar una implementación, diagnóstico o migración, pedir estado o nombrar la skill sin declarar el cierre ya no genera una retrospectiva.
- Se actualizaron las instrucciones compartidas y los ejemplos para Codex, Gemini CLI y GitHub Copilot.

## 2026-08-15 — Auditoría de implementación Chat/Telegram/RAG

- Se verificó el head único `20260726_canonical_knowledge_v1`, el esquema local y la ausencia de datos operativos Chat/Telegram/RAG y de sesiones Telegram numéricas legacy.
- La suite focal backend aprobó 50 pruebas (6 omitidas); Vue aprobó typecheck, 89 pruebas y build. Persisten como deuda warnings de conexiones SQLite heredadas.
- Se retiró el router webhook de la API, la configuración rechaza transportes distintos de `polling` y Telegram permanece apagado por flags.
- WebSocket recarga `User.role` por mensaje y sus rutas principales —tools, fallback local, respuesta general y streaming— pasan por `ChatOrchestrator`; las aclaraciones heredadas aún deben converger.
- `Chat 😎` incorpora streaming WebSocket sin mensajes duplicados, sanitización defensiva de cards, panel de vínculos propios y aprobación/revocación administrativa. Continúa `ready/legacy`: React conserva `/chat` hasta el smoke por rol.
- El dashboard técnico recibe health seguro del worker; la trazabilidad estima tokens sin conservar contenido. El costo real queda pendiente de un proveedor configurado.
- Se confirmó la rotación de secretos y que el entorno queda deliberadamente sin API keys; no se habilitó ningún flag ni worker.
- Se reconciliaron README, Roadmap y documentación de Chat, arquitectura, Vue, pruebas, migraciones, seguridad, RAG y roles con el estado comprobado y el plan de implementación pendiente.
- Se agregó la skill `git-secret-forensics`; `git-commit-push` deriva hacia ella
  cualquier reescritura destructiva de historia y exige autorización separada.
- `scripts/check-quality.ps1` incorpora `-SkillsOnly` y `-SkillName` para
  validar skills focalmente sin confundir ese chequeo estructural con el gate
  ampliado `-AgentOnly`; la metadata acepta LF y CRLF.
- La retrospectiva forense registra tareas, bloqueos, soluciones y deuda
  residual sin reproducir valores de credenciales.
- La retrospectiva de Chat/Telegram registra evidencia de pruebas, obstáculos,
  endurecimiento de logs y gates pendientes sin habilitar flags ni credenciales.

## 2026-07-30 — Saneamiento histórico del token Telegram

- Se reescribieron con `git filter-repo` y publicaron coordinadamente `main`
  (`1e117589d8547e07d12d30c94ddc0513a6452695`) y `dev`
  (`5eaf36a42771c0a3ed7104b60a08a9f488fd75af`) sin alterar el árbol final de
  desarrollo.
- Se eliminaron cuatro ramas Dependabot que heredaban el secreto y una
  clonación independiente confirmó cero coincidencias en 130 referencias de
  ramas y tags.
- Diez referencias internas `refs/pull/*`, administradas por GitHub, todavía
  alcanzan el objeto antiguo. Su purga queda pendiente de GitHub Support.

## 2026-07-26 — Edición segura del SKU canónico

- La ficha Vue suma lápiz, confirmación y cancelación explícitas para el SKU canónico.
- `PATCH /canonical-products/{id}` normaliza el SKU, exige `XXX_0000_YYY`, detecta duplicados antes del commit y convierte carreras de unicidad en `409 duplicate_sku`.
- Ante colisión, el editor permanece abierto, muestra el error y conserva el SKU anterior sin aplicar cambios.

## 2026-07-26 — Base de Conocimiento del Producto Canónico

- `20260726_canonical_knowledge_v1` creó activos, ubicaciones, etiquetas, capacidades, versiones, claims, hechos, eventos, jobs y perfiles técnicos Mercado; `market_sources` dejó de existir.
- Mercado conserva IDs de perfil y contratos legacy, pero URLs/nombres/producto pertenecen al activo; `DELETE` archiva y conserva histórico.
- Enrich knowledge-first reutiliza hechos y fuentes antes de buscar y persiste descubrimientos; las clasificaciones dudosas quedan excluidas.
- Se agregó `knowledge_worker` con HTML/PDF seguro vía MCP, PDF/OCR, imagen, video, transcripción, heartbeat y health.
- Vue suma el Centro **Conocimiento** compartido por Producto y Mercado.
- Las fuentes Mercado automáticas sólo participan con activo confirmado, etiqueta `market`, capacidad `price`, ARS y entrega argentina confirmados; el Centro permite registrar esa confirmación con revisión y auditoría.
- El despliegue real conservó 1 fuente, 6 observaciones, 3 resultados y 1 alerta, y completó un job autenticado con CSRF/polling.

## 2026-07-25 — Detalle canónico Vue y Enrich v2

- Se agregó la revisión irreversible `20260725_canonical_enrichment_v2`, con backfill conservador, jobs, evidencias acotadas y versiones restaurables.
- Se retiró `products.market_price_reference`; `/market` y `CanonicalProduct.market_price_reference` continúan como autoridad exclusiva.
- Los contratos canónicos soportan idempotencia, aplicación parcial, descarte, restore y conflicto `409` por revisión.
- MCP Web Search suma `fetch_web_document` para HTML/PDF público con controles SSRF; `pypdf>=6.4,<7` quedó fijado en su lock.
- Se creó `enrichment_worker` con cola y health dedicados y configuración híbrida OpenAI/Ollama sin fallback de eco.
- El detalle `/productos/:id` pasó a Vue y agrega registros equivalentes; la edición avanzada de imágenes conserva React.
- El despliegue real corrigió el marcador Linux de `pywin32`, el contenido de la
  imagen MCP, la normalización `/mcp/`, el descubrimiento dirigido, redirects
  DuckDuckGo, retries idempotentes, sanitización de errores, Redis de la API y el
  binding loopback del frontend.
- Se activó `ENRICH_V2_ENABLED=1`; el smoke autenticado persistió cinco fuentes y
  confirmó un error explícito por falta de proveedor IA, sin aplicar contenido.

## 2026-07-25 — Reconciliación documental de Stock y Mercado

- Se contrastaron manifiesto, reglas Nginx, componentes Vue, clientes HTTP, roles y pruebas.
- Stock y Mercado quedan documentados como `active/vue`; React se conserva únicamente como fallback temporal para rollback.
- `docs/STOCK.md` pasa a ser el contrato operativo de Stock y Faltantes, y `docs/API_MARKET.md` la fuente canónica de Mercado.
- Se retiraron referencias `legacy/pending` desactualizadas y se marcó la integración React de Mercado como histórica.

## 2026-07-22 — Chat multicanal, Telegram, RAG y observabilidad

- Se incorporaron identidades externas cifradas, vínculos de un uso, doble aprobación admin y revocación inmediata basada en `User.role`.
- Telegram ahora usa `from.id`, sesiones opacas, rate limit, deduplicación persistente, cola acotada, orden por remitente, retries seguros y health sin datos personales.
- Se centralizaron políticas MCP/tools con denegación por defecto y sanitización de catálogo público.
- RAG suma scopes de rol/canal, estado y vigencia, búsqueda híbrida, cache versionado, presupuesto de tokens y citas tipadas.
- Se agregaron trazas y métricas sin prompts, argumentos ni resultados completos, junto al archivado automático a 90 días.
- Se implementó `Chat 😎` en Vue como módulo independiente en estado `ready/legacy`.
- Se corrigió la pérdida de tablas SQLite en pruebas WebSocket usando una base temporal aislada por proceso.
- Alembic y los scripts de diagnóstico dejaron de imprimir DB URLs, incluso enmascaradas.
- `cryptography` quedó declarada como dependencia directa para AES-GCM; ya formaba parte de los locks existentes como dependencia transitiva. No se agregaron paquetes npm.

## 2026-07-21 — Retrospectiva técnica de Mercado

- Se documentaron las tareas completadas, los incidentes post-implementación, sus causas y la deuda residual de Mercado.
- El flujo de diagnóstico ahora exige detectar listeners duplicados, comprobar la frescura de imágenes Docker y registrar bloqueos de permisos.
- Se corrigieron instrucciones desactualizadas de pruebas, estado del módulo y warnings async en la documentación de Mercado.

## 2026-07-21 — Corrección de extracción y presentación en Mercado

- Los scrapers estático y Chromium priorizan `Product/Offer` de JSON-LD y contenedores del producto antes de clases genéricas, evitando capturar carrito, cuotas o carruseles.
- Mercado separa el nombre canónico del SKU personalizado y refresca la tabla automáticamente cuando un job llega a estado terminal.
- Se corrigió la observación de `SUS_0001_INE`: la fuente y el promedio vigente quedaron en `3700 ARS`; las capturas incorrectas permanecen en el histórico auditable.

## 2026-07-21 — Reconciliación del worker Mercado en Administración

- El panel de workers deja de conservar un falso estado `failed` cuando `market_worker` fue iniciado fuera de la UI.
- La detección de Docker Desktop amplía su timeout configurable y el health genérico delega al chequeo específico de broker, heartbeat y cola de Mercado.

## 2026-07-21 — Auditoría y estabilización de Mercado

- Se incorporó la revisión focal `20260721_market_observability_v1` con alertas, jobs/items/resultados por fuente, validación y observaciones inmutables; se validó upgrade incremental y desde PostgreSQL vacío.
- Mercado opera exclusivamente en ARS y calcula un promedio aritmético con una observación efectiva por fuente activa; automáticas vencen por defecto a los siete días y manuales al ser reemplazadas.
- Refresh individual y batch crean trabajos idempotentes y consultables; los fallos de broker y scraping terminan de forma explícita y conservan trazabilidad.
- Se agregó `market_worker` Docker no-root con dependencias bloqueadas, Chromium, cola exclusiva, cuatro hilos configurables, lock por dominio, heartbeat y health de broker/consumidor/cola.
- `/mercado` pasó a Vue con filtros, selección masiva, detalle de fuentes, histórico SVG, polling terminal y ocho bandas accesibles; React conserva compatibilidad temporal.
- Se retiraron puntualmente dos mensajes obsoletos de Redis, se rotó e invalidó la credencial local expuesta y se incorporó un rotador que también actualiza `DB_URL` sin imprimir secretos.

## 2026-07-21 — Publicación segura y cierre de conocimiento agéntico

- Se documentó la publicación de 327 archivos en `dev`, separados en cuatro commits de plataforma, backend, frontend y documentación.
- SQLite de tests conserva `sqlite+aiosqlite:///:memory:` con `StaticPool`; se eliminó la interpretación Windows de la URI nombrada como archivo físico y el gate consolidado aprobó 39/39 pruebas Python.
- El smoke E2E de Compras usa un encabezado semántico y una espera explícita para absorber la compilación lazy inicial de Vite sin relajar la ruta ni el rol esperado.
- La skill `git-commit-push` exige auditoría de secretos redactada, clasificación contextual de locks, verificación del remoto, aprobación informada cuando corresponda y comparación de SHA tras el push.
- Se agregó `docs/RETROSPECTIVE_REPOSITORY_PUBLICATION_20260721.md` con tareas, incidentes, soluciones y mejoras derivadas exclusivamente de esta sesión.

## 2026-07-20 — Migración de Stock a Vue preparada para smoke

- Se incorporaron vistas Vue para Stock y Faltantes con filtros persistidos en URL, búsqueda cancelable, paginación, permisos por rol y descargas mediante blobs.
- El stock manual acepta dos decimales, usa control optimista con `expected_stock`, bloquea la fila y registra `manual_adjustment` en ledger junto con auditoría atómica.
- Faltantes acepta cantidades decimales, bloquea el producto y registra saldo/delta independientes; la UI advierte y confirma saldos negativos.
- `GET /stock/export.csv` y `GET /stock/export.pdf` quedaron operativos; XLSX, CSV y PDF comparten consulta, filtros y reglas de precio/categoría/SKU. PDF usa ReportLab sin dependencia nueva.
- Productos Vue incorpora enriquecimiento masivo, completar precios faltantes, generación de catálogo e histórico/descarga de catálogos.
- El módulo permanece `legacy/pending`: React sigue atendiendo producción hasta activar Productos/Catálogos Vue y completar smoke visual por rol.
- Validación: 65/65 Vitest, 12/12 pytest funcionales y contrato CSRF aislado, typecheck y builds Vue/React aprobados. El rerun conjunto expuso una URI SQLite interpretada como archivo físico en Windows; el incidente no pertenecía al endpoint y quedó corregido el 2026-07-21.

## 2026-07-20 — Recuperación operativa del batch canónico

- DB y Redis conservan bindings loopback mediante `host_access` sin retirar el aislamiento de la red `backend`.
- Los jobs canónicos `FAILED` sin filas procesadas se reencolan idempotentemente con la misma clave y bloqueo transaccional.
- Vue ofrece **Reintentar lote** para fallos de infraestructura previos al procesamiento.
- Se agregaron regresiones de red Compose y reencolado batch; aprobaron suites focales backend y typecheck Vue.
- Las operaciones Compose del panel se ejecutan mediante `asyncio.to_thread`; los fallos revierten la sesión antes de persistir `ServiceLog`.
- El worker `catalog` emite eventos NDJSON por actor, job e ítem con duración y resultado; `state.json` referencia logs de procesos reutilizados.
- `start-dev.ps1 -WithCatalogWorker` inicia/verifica Redis+Dramatiq y reconcilia DB cuando Compose figura activo sin puerto host.
- El inicio administrativo de `catalog_worker` verifica Redis y lo inicia mediante Compose cuando falta.
- El worker local deja de usar pipes sin lector: persiste stdout/stderr en `logs/worker_catalog.log`; el launcher advierte si compite con Dramatiq Docker.
- Se crearon la skill canónica `diagnose-local-services`, su adaptador y controles adicionales en `create-service`.
- Se agregó `docs/RETROSPECTIVE_CANONICAL_BATCH_OPERATIONS_20260720.md`.

## 2026-07-20 — Retrospectiva de taxonomía, tags y QA agéntico

- Se documentaron entregas, fallos, soluciones y límites verificables de la convivencia entre taxonomía plana y tags.
- Testing formaliza el montaje con Vuetify real, los polyfills JSDOM y la distinción entre rerun focal y suite consolidada.
- La skill Vue exige buscar consumidores antes de cambiar contratos, revisar el impacto de auto-imports y ejecutar smoke autenticado con navegador cuando esté disponible.
- La skill de migraciones clasifica `alembic check` por objetos del cambio y exige head y objetos concretos en la prueba PostgreSQL limpia.
- Se corrigieron referencias heredadas que aún presentaban categoría/subcategoría como jerarquía funcional.

## 2026-07-18 — Taxonomía plana y tags en Productos Vue

- Categoría y subcategoría pasan a ser clasificaciones planas e independientes mediante `categories.kind`; `parent_id` permanece como compatibilidad temporal.
- Productos internos incorporan `subcategory_id`; los canónicos requieren ambos tipos y exportan `Categoría > Subcategoría`.
- Vue recupera creación escribible de ambas taxonomías y gestión de tags individual, masiva y por fila del wizard.
- El batch persiste `tag_names`, combina tags comunes/particulares e inserta tags y relaciones idempotentes en la transacción canónica.
- `/catalog/search` busca por tags con AND entre términos; las tres tools MCP de Productos devuelven `tags`.
- Alembic agrega unicidad normalizada por tipo/nombre y aborta ante colisiones sin fusionar datos.
- El alta inline normaliza los valores `Decimal` del audit para que una falla de serialización no deje la sesión en rollback pendiente.

## 2026-07-18 — Finalización del panel administrativo Vue

- Servicios Vue incorpora previsualización y limpieza de logs físicos con retención, eliminación de carpetas completas `logs/dev/<ejecución>` y protección de ejecuciones activas e historiales auditables.
- Workers diferencia el borrado de `ServiceLog` en PostgreSQL; Imágenes limpia conjuntamente `ImageJobLog`, NDJSON y snapshots.
- `cleanup_logs.py`, `clean_all_logs.ps1`, `clear_logs.py` y `clear_backend_log.py` se alinean con la estructura vigente de `start-dev.ps1`; se retiró la afirmación incorrecta de que `docker logs --tail 0` trunca Docker.
- Se activaron en Vue Drive Sync, Scheduler, Conocimiento, Imágenes administrativas, Diagnóstico de catálogos, Dashboard técnico y Chat Inbox.
- Las revisiones `20260718_admin_operations_v1` y `20260718_admin_jsonb_v2` incorporan ejecuciones y elementos de Drive, configuración/historial del Scheduler, tareas RAG, eventos de Catálogos, feedback de Chat y versiones/evaluaciones de prompts con metadatos JSONB.
- Todas las mutaciones administrativas aplican sesión, rol y CSRF; Drive autentica el WebSocket antes de aceptar conexiones.
- Catálogos elimina la purga automática y expone logs persistentes descargables en NDJSON/CSV.
- Chat incorpora asignación, tags, acciones masivas, clasificación, métricas y promoción reversible de prompts con aprobación admin.
- Se documentó operación, errores, smoke y rollback en `docs/ADMIN_VUE_OPERATIONS.md`.

## 2026-07-18 — QA de Productos y conocimiento agéntico

- Se documentó el cierre técnico del catálogo Vue, alta masiva canónica y creación inline de categorías.
- Las guías distinguen `GET /catalog/next-seq` heredado de `POST /canonical-products/sku-preview`; ambos son no reservantes.
- Testing documenta la sintaxis focal de Vitest y la necesidad de ejecutar `vue-tsc` para opciones discriminadas de componentes.
- QA frontend incorpora preflight de Chrome, alcance de la validación HTTP y auditoría npm bajo entornos restringidos.
- El workflow vuelve a identificar `start-dev.ps1` y Vue 5176 como inicio canónico, diferenciándolo del launcher React heredado.
- Se agregó la skill canónica `vue-module-migration` y su adaptador temporal para estandarizar futuros cortes React → Vue.
- Se agregó `docs/RETROSPECTIVE_PRODUCTS_20260718.md`.

## 2026-07-17 — QA de Compras, sesión y Proveedores

- El marker `no_auth_override` deja de desactivar CSRF y representa el ciclo real de autenticación.
- La regresión de sesión valida login, `/auth/me` y una mutación protegida.
- Los mocks iAVaL se alinearon con `AIRouter.run_async`.
- Se documentaron la carrera de procesos pytest paralelos, la deuda de `TestClient` y los prerrequisitos locales de OCR.
- Se agregó `docs/RETROSPECTIVE_PURCHASES_20260717.md` como registro técnico de la entrega.

## 2026-07-16 — Compras Vue e ingesta transaccional Santa Planta

- Compras crea productos y ofertas faltantes durante la confirmación, nunca durante el borrador.
- Confirmación y rollback registran movimientos `purchase`/`purchase_rollback` en `stock_ledger`.
- Se agregaron snapshots documentales, hash SHA-256, costo bruto/neto, bonificación e historial por producto.
- El importador admite PDF, JPG y PNG, deduplica idempotentemente por remito o hash y conserva el original.
- Vue incorpora listado, importación, revisión, confirmación, impacto e historial básico de productos.
- Migración: `20260716_purchase_ingestion_v2`.
- Se corrigió la cookie de autenticación: el navegador recibe el SID crudo y el servidor conserva/verifica sólo su hash, evitando 403 falsos tras iniciar sesión.
- Compras reemplaza el ID manual por un selector buscable y habilita alta rápida; `/proveedores` queda activo en Vue con búsqueda y creación básica.

## [Unreleased]
### Added
- MCP real mediante SDK oficial, Streamable HTTP en `/mcp`, descubrimiento dinámico y cliente central.
- Seguridad MCP compartida con JWT Bearer, issuer/audience por servidor, rotación por `kid`, revocación JTI, rate limiting Redis y auditoría seudonimizada.
- Bootstrap Python 3.14.6, modos MCP en `start-dev.ps1`, detención segura y quality gate local/CI manual.
- Skills canónicas descubribles bajo `.agents/skills/`.
- Dependencias `mcp>=1.27,<2` y `PyJWT>=2.8,<3`, documentadas para API y servidores MCP.
- Locks reproducibles con hashes, SBOM CycloneDX y auditoría local con Ruff, Bandit y `pip-audit`.

### Changed
- OpenAI usa cliente asíncrono en `generate_async` y obtiene schemas desde MCP.
- `/invoke_tool` queda deprecado durante la ventana de compatibilidad.
- Los puertos Docker quedan ligados a loopback; los contenedores MCP son read-only, sin capabilities y sin privilegios adicionales.
- El workflow manual usa permisos mínimos y GitHub Actions fijadas a commits inmutables.
- Las sesiones de chat persisten identificadores hasheados y las salidas de tools externas se tratan como datos no confiables y acotados.

### Security
- Se retiraron `python-jose/ecdsa` y `PyPDF2` al detectarse vulnerabilidades; JWT usa PyJWT y PDF usa `pypdf`.
- Web Search limita destinos, redirects, tiempos, tamaño y consultas con material sensible.
- El bypass de roles por headers queda disponible únicamente bajo entorno de tests.

### Added
- **Estilización de nombres de productos canónicos** (Title Case):
  - Función `stylize_product_name()` en `db/text_utils.py` convierte nombres en mayúsculas a formato legible.
  - Preserva unidades de medida en mayúsculas (GR, KG, L, ML, etc.) y acrónimos (LED, NPK, UV, etc.).
  - Aplica conectores en español en minúsculas (de, la, el, etc.) excepto al inicio.
  - Integrada en: listado de Stock, exports XLS, export TiendaNegocio, detalle de producto, API de productos canónicos.
  - Ejemplo: `"FEEDING BIO GROW (125 GR)"` → `"Feeding Bio Grow (125 GR)"`.
  - Tests: `tests/test_text_utils.py`.
- Endpoint `DELETE /suppliers` mejorado con detalles extendidos y eliminación en cascada opcional:
  - Parámetro `force_cascade` para eliminar automáticamente `import_jobs` y `product_equivalences`
  - Respuesta incluye `details` con IDs de registros bloqueantes, estados y acciones sugeridas
  - Campo `help` con guía de uso de `force_cascade` y limpieza manual
  - Validación de integridad referencial completa: compras, archivos, import_jobs, equivalencias, líneas de compra
  - Retorna nombre del proveedor en `blocked[]` para facilitar identificación
- Enriquecimiento de productos con IA:
	- Backend: `POST /products/{id}/enrich` (force=true), `DELETE /products/{id}/enrichment`, `POST /products/enrich-multiple` (máx 20). Guardas, validaciones y auditoría (`enrich|reenrich|delete_enrichment`).
	- Modelo `products`: `enrichment_sources_url`, campos técnicos (`weight_kg`, `height_cm`, `width_cm`, `depth_cm`, `market_price_reference`) y metadatos `last_enriched_at`, `enriched_by`.
	- Migraciones: `20251021_add_product_enrichment_sources.py`, `20251021_add_product_technical_fields.py`, `20251021_add_product_enrichment_trace.py`.
	- UI: botón “Enriquecer con IA”, menú IA (Reenriquecer, Borrar), edición inline de datos técnicos, modal “Fuentes consultadas”, acción masiva en Stock.
- MCP Web Search Server (MVP): `mcp_servers/web_search_server` con tool `search_web(query)`; integración opcional en enrich vía flag `AI_USE_WEB_SEARCH`.
- Flags: `AI_USE_WEB_SEARCH` (0/1) y `AI_WEB_SEARCH_MAX_RESULTS` (default 3); `MCP_WEB_SEARCH_URL` para endpoint del servidor MCP.
- mcp_servers: primer MCP Server `mcp_products` (MVP) con tools `get_product_info` (abierto) y `get_product_full_info` (roles admin|colaborador). Endpoint unificado `POST /invoke_tool`, Dockerfile propio y dependencia HTTP hacia API principal (sin acceso directo a DB). README y Roadmap actualizados.
- Columna `purchase_lines.meta` (JSON) para trazabilidad de autocompletado de líneas.
- Persistencia de `meta.enrichment` (algorithm_version, timestamp, fields, stats) al ejecutar `PUT /purchases/{id}` con `PURCHASE_COMPLETION_ENABLED`.

### Documentation
- `PURCHASES.md`: sección Metadatos de enriquecimiento.
- `API_PRODUCTS.md`: documentados endpoints de enrich (single/bulk/delete), campos técnicos, `enrichment_sources_url`, metadatos `last_enriched_at`/`enriched_by` y flags de Web Search.
- `PRODUCTS_UI.md`: actualizado con botón/menú IA, edición técnica, fuentes y acción masiva.
- `roles-endpoints.md`: añadidos endpoints de enriquecimiento y roles requeridos.
- `MIGRATIONS_NOTES.md`: añadidas las migraciones de 2025-10-21 y hotfix SQLite en memoria.
- `SECURITY.md`: sección de salida a Internet (flags IA/MCP) y auditoría relacionada.
- `README.md`: sección de Enriquecimiento IA y MCP Web Search.


### Added
- Heurísticas post-proceso para recuperación de SKUs en remitos Santa Planta (`embedded_sku_recovered`, `known_title_sku_mapped`).
 - import(SantaPlanta Fase 2): eventos adicionales para estabilidad del parser (`header_long_sequence_removed`, `multiline_fallback_forced`, `quantity_fallback_forced`, `multiline_pct_detected`, `multiline_discount_attached`, `remito_number_rewritten_from_filename_forced`).
 - import(SantaPlanta Fase 2): documentación ampliada (`docs/IMPORT_PDF.md`) describiendo patrón contextual de remito `0001-XXXXXXXX`, filtrado de secuencias largas y segunda pasada de cantidades.
 - import(SantaPlanta Fase 2.1): tercera pasada híbrida (`third_pass_attempt|third_pass_lines|third_pass_empty|third_pass_error`) y evento global `all_fallbacks_empty`.
 - import(SantaPlanta Fase 2.1): eventos de encabezado agregados `header_long_sequence_removed_count`, `header_invalid_reset`; extensión segunda pasada `second_pass_qty_pattern_extended`.
 - compras: servicio de autocompletado (scaffolding interno) para enriquecer líneas (descuentos, outliers de precio, sugerencias SKU) – pendiente de integración vía flag `PURCHASE_COMPLETION_ENABLED`.
- Endpoint de pagos de ventas permite múltiples pagos con control de sobrepago y actualización precisa de `payment_status`.
 - Reporte de cobranzas: `GET /reports/sales/payments` con filtros (from_date,to_date,method) y agregados (`total_amount`, `by_method`).
 - Tests: transición de estados de pago (PENDIENTE→PARCIAL→PAGADA) y validación de guard contra sobrepago.

### Changed
- Creación mínima de producto: `supplier_id` ahora es opcional; si se omite no se genera `SupplierProduct` ni historial de precios.

### Fixed
- Test de remito de ejemplo ahora reconoce SKUs cortos esperados con nuevas heurísticas (antes sólo detectaba tokens numéricos largos ambiguos).
 - (En progreso) Refactor de enforcement SKU SantaPlanta: se añadieron pasos de trimming y compactación temprana (tokens como 56584 -> 6584) y se documentó en `IMPORT_PDF.md`; siguiente paso unificar eventos duplicados (`expected_sku_forced_global`, `expected_sku_enforced_final`) en uno canónico.
 - import(SantaPlanta): extracción de `remito_number` estabilizada. Se filtran prefijos no `0001` y números largos tipo CUIT; se añaden eventos `header_pattern_ignored`, `discarded_cuit_like`, `header_source`.
 - import(SantaPlanta): fallback multiline textual instrumentado con eventos `multiline_fallback_attempt|multiline_fallback_used|multiline_fallback_empty|multiline_error` para eliminar flakiness de 0 líneas silenciosas.
 - import(SantaPlanta Fase 2): forzado de fallback multiline cuando <5 líneas iniciales y rewrite desde filename si el remito carece de guion, evitando números fantasmas intermitentes.
 - import(SantaPlanta Fase 2): detección y aplicación de descuentos porcentuales (`-20% DESC`) normalizados a `pct_bonif`.
### Sprint 2 (Ventas Reporting & Stock Ledger Parcial) - 2025-09-26
#### Added
- sales: endpoint timeline `GET /sales/{id}/timeline` consolidando audit/pagos/devoluciones ordenado por fecha.
- sales: reportes agregados `GET /sales/reports/net`, `GET /sales/reports/top-products`, `GET /sales/reports/top-customers`.
- sales: cache in-memory TTL (60s) para reportes con invalidación en confirmación y devoluciones.
- stock: tabla `stock_ledger` con `product_id, source_type(sale|return), source_id, delta, balance_after, created_at`.
- stock: endpoint `GET /products/{id}/stock/history` (paginado, descendente) para auditoría de movimientos.
- sales: búsqueda rápida de clientes `GET /sales/customers/search?q=` con ranking heurístico.
- sales: endpoint dedicado `GET /sales/{id}/payments` para UI modular.
- sales: auditoría `sale_discount_clamped` cuando `discount_amount` se reduce al subtotal al confirmar.
- tests: cobertura para timeline, reportes (net/top), ledger consistencia y clamp descuento.
#### Changed
- sales: confirmación ahora recalcula y aplica clamp de descuento antes de validar stock y afectar inventario.
#### Docs
- docs/SALES.md actualizado con timeline, reportes, búsqueda rápida, ledger y clamp de descuento.
- Roadmap: sección Ventas ampliada (Sprint 1 + Sprint 2 parcial) y próximos pasos.

### Sprint 1 (Ventas / Auditoría) - 2025-09-26
#### Added
- sales: campo `sale_kind` (MOSTRADOR|PEDIDO) + validación en creación.
- sales: índices sobre `sale_lines.product_id` y compuesto (`product_id`,`sale_id`) para consultas de productos en ventas.
- sales: endpoints de devoluciones (`POST /sales/{id}/returns`, `GET /sales/{id}/returns`) con validaciones de saldo y reposición de stock.
- sales: reporting básico (`GET /reports/sales`, `GET /reports/sales/export.csv`).
- sales: snapshots de producto (`title_snapshot`, `sku_snapshot`) poblados al confirmar la venta.
- audit: helper unificado `_audit` con `correlation_id`, `user_id`, IP y `elapsed_ms`.
- audit: logs detallados de operaciones de líneas (`sale_lines_ops`) con before/after y de pagos (`sale_payment_add`) con estado previo y posterior (paid_total/payment_status).
- tests: unidad para `_recalc_totals` cubriendo descuentos %, prioridad discount_amount, estados de pago y guard de total negativo.
#### Changed
- sales: confirmación ahora rellena snapshots sólo si están vacíos (idempotente) y registra deltas de stock.
- customers: normalización y validación de documento (`document_number`) para CUIT/DNI (limpieza de separadores, reglas básicas de longitud).
#### Docs
- docs/SALES.md: actualizado con devoluciones, reporting, snapshots, auditoría extendida y normalización de CUIT/DNI.
#### Notes
- Próximos pasos propuestos (Sprint 2): timeline consolidado de venta (audit + pagos + devoluciones), reportes avanzados (top productos / clientes / neto post devoluciones), refactor a libro de stock, métricas de margen, endpoints de búsqueda rápida de clientes/productos optimizados.

### Added
- ui: botón flotante global “Reportar” (abajo a la derecha) disponible en todas las secciones. Abre un modal con campo “Comentario” y envía reportes manuales al backend.
- api: nuevo endpoint `POST /bug-report` que registra los reportes en `logs/BugReport.log` con rotación (5×5MB). Cada entrada incluye `ts` (UTC), `ts_gmt3` (servidor), `url`, `user_agent`, `cid` si está disponible y `context.client_ts_gmt3` desde el cliente.
- docs: `docs/BUG_REPORTS.md` con guía de uso; `docs/roles-endpoints.md` lista `/bug-report`; `docs/SECURITY.md` documenta excepción CSRF controlada; `docs/FRONTEND_DEBUG.md` referencia el botón.
 - ui: captura de pantalla opcional al enviar reporte; el backend persiste la imagen en `logs/bugreport_screenshots/` y agrega metadatos al log.
- purchases: verificación de totales en confirmación (`purchase_total` vs `applied_total`) con tolerancia configurable (`PURCHASE_TOTAL_MISMATCH_TOLERANCE_PCT`). La respuesta incluye `totals` y `can_rollback` cuando hay mismatch.
- api: nuevo endpoint `POST /purchases/{id}/rollback` que revierte el impacto de stock de una compra CONFIRMADA y la marca `ANULADA`; registra `purchase_rollback` con detalle de productos revertidos.
- ui(compras): en `PurchaseDetail`, si al confirmar hay mismatch se ofrece ejecutar Rollback inmediato.
- ui(compras): botón “Rollback” en el listado para compras en `CONFIRMADA`.
### Changed
 - ui(proveedores): listado “Proveedores” ahora usa panel oscuro consistente, encabezado claro y tabla con buen contraste; botones “Volver” y “Volver al inicio” unificados a `btn-dark` (se mantiene “Nuevo proveedor” en fucsia). Hover de filas con acento translúcido.
 - deps(PDF): se fijan versiones `pypdf>=4.3` y `pdfplumber>=0.11` para evitar `CryptographyDeprecationWarning` (ARC4) en importación de PDFs; verificar `requirements.txt`.
- ops: `logs/BugReport.log` queda excluido de endpoint `/debug/clear-logs` y scripts de limpieza para preservar historial (persistente con rotación).
 - ops: `logs/bugreport_screenshots/` se excluye de limpiezas generales hasta definir una política de retención específica.
 - admin: nuevo endpoint `GET /admin/services/metrics/bug-reports` para contar reportes por día (con filtro `with_screenshot`) leyendo `logs/BugReport.log`.
 - scripts: `scripts/cleanup_logs.py` agrega flags `--screenshots-keep-days` (por defecto 30) y `--screenshots-max-mb` (por defecto 200) para gestionar retención de capturas; `--dry-run` lista sin eliminar.
- ui(proveedores): ficha de proveedor actualizada para usar el tema global (mejor contraste y soporte dark). Se reemplazaron fondos/bordes grises por tokens `bg/text/card/border` del ThemeProvider.
 - ui(proveedores): listado y formulario modal de creación ajustados para respetar el modo oscuro (tokens de ThemeProvider en panel, tabla y campos).
- ui(compras): en “Nueva compra” el campo Proveedor ahora es un autocompletado con soporte dark mode (reemplaza el input libre de ID).
- ui: `SupplierAutocomplete` ahora respeta el tema (inputs y dropdown estilizados para dark/light).
- ui(compras): toasts de confirmación incluyen ID de producto para facilitar depuración de “productos erróneos”.
 - ui: el modal del botón “Reportar” ahora respeta el tema (dark/light) y usa los tokens del ThemeProvider; se reemplazaron colores fijos.
 - ui(compras): se limita la cantidad de toasts individuales al confirmar (máximo 5) y se agrega un resumen “(+N más)” para evitar ruido visual en compras grandes.
 - purchases: `POST /purchases/{id}/validate` ahora intenta auto-vincular líneas por `supplier_sku` del proveedor cuando falta vínculo, y devuelve en la respuesta `linked` (cantidad autovinculada) y `missing_skus` (lista de SKUs no encontrados). La UI muestra toasts con este detalle.
 - import(SantaPlanta): heurística reforzada para no confundir medidas (500 ML, 250 G/GR, etc.) con SKUs cuando se extrae un número desde el título; se ignoran tokens numéricos seguidos por unidades.
- feat(import): nuevo endpoint `GET /admin/services/pdf_import/ai_stats` con estad?sticas detalladas de fallback IA (latencias promedio/p95, uso por modelo, l?neas propuestas/agregadas e ignoradas, desglose de errores y ventana rolling 24h).
- infra/tests: `pytest.ini` ahora marca `CryptographyDeprecationWarning` (ARC4) como error y se agreg? `tests/test_pytest_filter_arc4.py` para asegurar el filtro.
- ai/router: fallback automático a Ollama cuando la política elige OpenAI pero falta OPENAI_API_KEY; evita ecos y resultados no JSON.
- purchases(iAVaL): `preview` ahora maneja respuestas no-JSON del proveedor IA devolviendo propuesta vacía con comentarios en lugar de 502.
- purchases(iAVaL): `POST /purchases/{id}/iaval/apply` ahora acepta flag `emit_log=1` para generar un archivo JSON de cambios con timestamp y metadatos del remito en `data/purchases/{id}/logs/iaval_changes_<timestamp>.json`; se agrega auditoría `purchase.iaval.emit_change_log` y el nombre de archivo en la respuesta.
- ui(compras): en el modal iAVaL se agrega la casilla "Enviar logs de cambios" que activa `emit_log=1` y muestra un toast con el nombre del archivo generado.
- docs/tests(iAVaL): `docs/PURCHASES.md` y `Roadmap.md` actualizados con el flujo de emisión de logs; se añadió prueba que valida `emit_log=1` (respuesta incluye `log.filename`).
- purchases(iAVaL): nuevos endpoints `POST /purchases/{id}/iaval/preview` y `POST /purchases/{id}/iaval/apply` para validación IA de remitos y aplicación de cambios en BORRADOR. Incluye extracción de texto de PDF, prompt con esquema JSON estricto, parsing robusto y auditoría `purchase.iaval.apply`.
- ui(compras): botón “iAVaL” en `PurchaseDetail` (sólo BORRADOR) y modal con confianza, comentarios y diffs (header y líneas) + confirmación “Sí, aplicar cambios”.
- docs: `Roadmap.md` creado con estado actual y pendientes; `docs/PURCHASES.md` ampliado con sección iAVaL y variables de entorno IA.
 - stock: nuevo endpoint `GET /stock/export-tiendanegocio.xlsx` y botón en la UI “Exportar a TiendaNegocio” que respeta filtros activos y genera un XLSX con el formato requerido (SKU, Nombre, Precio, Stock, Visibilidad, Descripción, Peso/Dimensiones, Categoría, variantes vacías).

### Removed
- Integración Tiendanube (push de imágenes):
	- Se eliminaron los endpoints `POST /products/{pid}/images/push/tiendanube` y `POST /products/images/push/tiendanube/bulk`.
	- Se removieron los botones “Enviar a Tiendanube” en `Stock` y `ProductDetail`.
	- Documentación actualizada para reflejar el reemplazo por la exportación a TiendaNegocio (`docs/IMAGES_STEP2.md`, `docs/PRODUCTS_UI.md`).
- feat(import): Añadido scaffolding de fallback IA para remitos (fase 1: sólo cuando pipeline clásico produce 0 líneas). Incluye:
	- (Fase 2) Trigger adicional por baja `classic_confidence` (< IMPORT_AI_CLASSIC_MIN_CONFIDENCE) y cálculo heurístico (`classic_confidence` event).
	- Prompt enriquecido con hint de líneas y confianza.
	- Nuevos modelos Pydantic (`RemitoAIItem`, `RemitoAIPayload`).
	- Cliente `ai_fallback` con validación estricta JSON y retries.
	- Variables de entorno: `IMPORT_AI_ENABLED`, `IMPORT_AI_MIN_CONFIDENCE`, `IMPORT_AI_MODEL`, `IMPORT_AI_TIMEOUT`, `IMPORT_AI_MAX_RETRIES`, `OPENAI_API_KEY`.
	- Eventos de logging `ai:*` integrados a `ImportLog`.
	- Documentación actualizada en `docs/IMPORT_PDF.md`.
	- Safe merge: sólo agrega líneas IA si no hay líneas clásicas.
	- Heurística refinada: añade métrica de densidad numérica y sanitización de outliers (cantidad >10k clamp, unit_cost>10M excluido).
	- Registro estructurado de `classic_confidence` en `ImportLog` (`stage=heuristic`).
	- Nuevo endpoint `GET /admin/services/pdf_import/metrics` con agregados (promedios de confianza, invocaciones IA, tasa de éxito, líneas añadidas, ventana 24h).
	- Tests añadidos: `test_ai_fallback_merge.py`, `test_pdf_import_metrics.py` (smoke) y ajuste de umbral en `test_classic_confidence.py`.

- feat(catalog): eliminación segura ahora elimina primero `supplier_price_history` antes de `supplier_products` para evitar NOT NULL FK en SQLite/PG.
- fix(catalog): error 500 al eliminar producto que no tenía stock ni referencias causado por FK `supplier_price_history.supplier_product_fk` -> ahora 200 con registro de cascada.
- docs: README ampliado con campo opcional `sku` en creación y detalle de reglas de borrado incluyendo cascada manual.
- feat(catalog): `POST /catalog/products` ahora acepta campo opcional `sku`; si no se provee se deriva de `supplier_sku` o `title`.
- feat(catalog): validación de formato SKU y pre-chequeo de duplicados (responde 409 sin generar excepción persistente).
- feat(api): handler global de `IntegrityError` que mapea `variants_sku_key` a `{code: duplicate_sku}` (HTTP 409) y otros constraints a `code: conflict`.
- docs(security): actualizado `docs/SECURITY.md` con detalles de manejo de integridad y validación de SKU.
- deps: agregado `onnxruntime` a `requirements.txt` para soporte completo de `rembg` (background removal) y documentadas dependencias del sistema (Tesseract, Ghostscript, QPDF) en `docs/dependencies.md`.
- docs: expandido `docs/dependencies.md` para incluir playwright, tenacity, onnxruntime y pasos de validación/instalación de binarios.
- ai: reemplazado stub de `OllamaProvider` por integración HTTP real (streaming opcional) con daemon Ollama (`/api/generate`).
- docs: nuevo `docs/ollama.md` con instrucciones de instalación y variables de entorno para LLM local.
- db/migrations: ampliado manejo de `alembic_version.version_num` creando la tabla manualmente con `VARCHAR(255)` para evitar `StringDataRightTruncation` al insertar revisiones largas (fix env.py).
- db/migrations/env.py: ahora fuerza `version_table_column_type=String(255)` y realiza preflight `_ensure_alembic_version_column` robusto (crea o altera según corresponda) antes de correr migraciones.
- db/migrations/env.py: logging mejorado (archivo por corrida, DB_URL ofuscado, historial de heads reciente) y `load_dotenv(..., override=True)` para asegurar consistencia de `DB_URL`.
- db/migrations/versions/20241105_auth_roles_sessions.py: eliminado abort estricto por placeholder de `ADMIN_PASS`; se agregó fallback seguro, carga explícita de `.env` y hash Argon2 con import local defensivo.
- scripts: agregado `scripts/check_admin_user.py` para verificación rápida post-migraciones del usuario admin.
- scripts/seed_admin.py: mensaje de advertencia si `ADMIN_PASS` es placeholder y creación idempotente del usuario admin.
- docs: documentado flujo de recuperación de migraciones rotas por longitud de `alembic_version` y placeholder de `ADMIN_PASS` (ver nuevo archivo `docs/MIGRATIONS_NOTES.md`).

- ui(compras): dropdown "Cargar compra" con estilos dark consistentes.
- ui(compras): nuevo PdfImportModal (proveedor obligatorio → subir PDF → procesar) que navega al borrador creado.
- ui(compras): flujo Manual rehecho: encabezado + grilla de líneas editable (sku prov., título, cantidad, costo unitario, % desc., nota).
- ui(compras): se eliminó cualquier acción de importar PDF de la vista Manual.
- feat(compras): guardar como BORRADOR desde la vista Manual (POST /purchases) y actualizaciones posteriores con PUT /purchases/{id}; toasts y validaciones básicas.
- feat: drag & drop, tema oscuro en buscador y modal de subida más robusto
- Add: upload UI (+), dry-run viewer, commit
- Add: productos canónicos y tabla de equivalencias
- Add: middleware de logging, endpoints `/healthz` y `/debug/*`, SQLAlchemy con `echo` opcional.
- Add: endpoints `GET/PATCH /canonical-products/{id}`, listado y borrado de `/equivalences`
- Add: comparador de precios `GET /canonical-products/{id}/offers` con mejor precio marcado
- Add: modo oscuro básico en el frontend
- Add: plantilla Excel por proveedor `GET /suppliers/{id}/price-list/template`
- Add: plantilla Excel genérica `GET /suppliers/price-list/template`
- fix: restaurar migración `20241105_auth_roles_sessions` renombrando archivo y `revision` para mantener la cadena de dependencias
- fix: evitar errores creando o borrando tablas ya existentes en `init_schema` mediante `sa.inspect`
- Add: componentes `CanonicalForm` y `EquivalenceLinker` integrados en `ImportViewer` y `ProductsDrawer`
- dev: valores por defecto inseguros para SECRET_KEY y ADMIN_PASS en `ENV=dev` (evita fallos en pruebas)
- deps: incluir `aiosqlite` para motor SQLite asíncrono
- dev: en ausencia de sesión y con `ENV=dev` se asume rol `admin` para facilitar pruebas
- fix: corregir comillas en `scripts/start.bat` y `start.bat` para rutas con espacios
- fix: soporte de `psycopg` asíncrono en Windows usando `WindowsSelectorEventLoopPolicy`
- fix: migración idempotente que agrega `users.identifier` si falta y actualiza el modelo
- fix: formulario de login centrado y autenticación/guest integrados con `AuthContext`

## [0.2.0] - 2025-09-12

### Added
- purchases: respuesta `confirm` con `applied_deltas` (debug=1) para trazabilidad de stock.
- purchases: bloqueo estricto opcional (env `PURCHASE_CONFIRM_REQUIRE_ALL_LINES`) cuando hay líneas sin vincular.
- admin: nuevo layout `/admin` con secciones Servicios, Usuarios, Imágenes y Health unificadas.
- admin/services: chequeo (`/deps/check`) e instalación (`/deps/install`) de dependencias opcionales (playwright, pdf OCR stack).
- images: stream SSE de logs/progreso (`/admin/image-jobs/logs/stream`) y cálculo de % progreso.
- import(SantaPlanta): heurísticas SKU (tokens numéricos), fallback camelot/pdfplumber + OCR mejorado, eventos detallados y retry.
- health: endpoints enriquecidos (`/health/service/*`, `/health/summary`) con reporte por servicio opcional y storage/redis/db/AI.
- services: util frontend `ensureServiceRunning` para espera idempotente de estado running.
- auth: endpoint para eliminar usuario con audit (DELETE `/auth/users/{id}`).
- scripts: herramienta `tools/clear_db_logs.py` para purgar tablas de logs; registro de tarea startup PowerShell.

### Changed
- orchestrator: detección robusta de Docker (verifica engine con `docker info`) y normalización de estados (running/starting/degraded).
- image jobs: endpoint `status` agrega objeto `progress` (total, pending, processed, percent).
- pipeline import: sanitización de `TESSDATA_PREFIX` y fallback heurístico de filas cuando no se detectan tablas estructuradas.
- start.bat: mensajes internacionalizados (acentos), build condicional frontend y manejo mejorado de Redis ausente.
- health summary: incluye mapa `services` con estado individual.

### Fixed
- import: múltiples mejoras de resiliencia frente a PDFs sin texto y paths OCR.
- purchases: sanitización de mensajes Unicode y logs por línea (`old_stock + delta -> new`).
- UI: carga de sección Stock tras invalidación de chunks (nueva build hash) al mejorar build flow.

### UI / UX
- Tema oscuro refinado (contraste placeholders, muted text) y toasts apilados (info/success/warning) con per-product delta.
- Panel de imágenes: modo Live (SSE) y barra de progreso animada.
- Panel de servicios: integra panel de health + logs streaming.
- PurchaseDetail: toasts por producto con incremento de stock y aviso de líneas sin vincular.

### Chore / Dev
- Documentación interna con docstrings en routers (purchases, health, services_admin, image_jobs, import pipeline).
- Limpieza y normalización de mensajes en scripts y logs.

---

## [0.2.1] - 2025-09-15

### Changed
- frontend: `deleteProducts` y `createProduct` ahora usan `/catalog/products` para alinearse con el backend.
- frontend: mensajes de error al eliminar productos muestran las causas del backend (stock > 0, referencias) y resumen parcial "Borrados X / Y".
- frontend: agregado "Seleccionar página"/"Deseleccionar página" en Stock y ProductsDrawer para selección rápida.

### Docs
- README: se documentó `DELETE /catalog/products` y `POST /catalog/products` en secciones relevantes; se ampliaron reglas y respuesta.
- docs/roles-endpoints.md: añadidos endpoints `/catalog/products` (POST/DELETE).
- README: sección de limpieza de logs ahora incluye `--skip-truncate` y nota sobre bloqueo de `backend.log` en Windows con marcador `backend.log.cleared`.

### Build
- frontend: build verificado con Vite (sin errores) tras los cambios anteriores.

