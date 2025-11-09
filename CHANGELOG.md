<!-- NG-HEADER: Nombre de archivo: CHANGELOG.md -->
<!-- NG-HEADER: Ubicación: CHANGELOG.md -->
<!-- NG-HEADER: Descripción: Historial de cambios y dependencias añadidas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Changelog

## [Unreleased]
### Added
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

