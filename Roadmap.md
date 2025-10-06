<!-- NG-HEADER: Nombre de archivo: Roadmap.md -->
<!-- NG-HEADER: Ubicación: Roadmap.md -->
<!-- NG-HEADER: Descripción: Hoja de ruta del proyecto, estado actual y pendientes (documentación viva) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roadmap del Proyecto

Última actualización: 2025-10-06

Este documento resume el estado actual del proyecto, las funcionalidades ya implementadas y los trabajos pendientes. Debe mantenerse actualizado por cada contribución (humana o de un agente) que cambie comportamiento, endpoints, modelos o UI relevante.

## Contexto

- Backend: FastAPI + SQLAlchemy (async) para gestión de compras (borradores, validación, confirmación), adjuntos (PDF remito), logs y auditoría.
- AI: Capa `ai/` con enrutador y proveedores (OpenAI y/o Ollama) para tareas de razonamiento y validación.
- Frontend: SPA React/TypeScript (Vite) con páginas de compras y servicios HTTP.
- Almacenamiento de archivos: `data/purchases/{id}/...` para PDFs y artefactos relacionados.

### Capa MCP Servers (estado)

Arquitectura **MCP Servers** (Model Context Protocol simplificado) establecida para exponer herramientas de dominio a LLMs.

Servicio actual:
- `mcp_products` (FastAPI independiente)
  - Tools: `get_product_info`, `get_product_full_info`.
  - Cache en memoria con TTL dinámico, token compartido opcional, logging y mapeo de errores (400/401/403/404/502/504).
  - Endpoint estándar `POST /invoke_tool`.
  - Consume API principal vía HTTP (no DB directa).
  - Dockerizado (`docker-compose.yml`, puerto 8100) — el código de integración usa por defecto `http://mcp_products:8001`; ajustar `MCP_PRODUCTS_URL` o alinear puertos.
  - Tests: permisos, cache, token auth, invocación tool (respx).

Integración chatbot:
- Endpoint `/chat` ahora usa tool-calling (OpenAI → MCP) para consultas de producto. `price_lookup.py` marcado DEPRECATED.

Próximos pasos MCP:
- Firmar token (HMAC/JWT) con expiración y rol.
- Auditoría estructurada de invocaciones (latencia, tool_name, rol, éxito/error).
- Extender tools: métricas de ventas, equivalencias SKU, historial de precios.
- Rate limiting por rol y circuito de retry/backoff.

## Estado actual (hecho)

- Se actualizo la persona del chatbot para reflejar un tono mas malhumorado, sarcastico y centrado en Nice Grow.
- El chatbot de precios ahora pide aclaracion cuando hay multiples coincidencias antes de compartir montos.
- Backend compras: update_purchase limpia los vinculos al editar SKUs y confirm_purchase expone deltas por linea.
- UI compras: se corrigió la codificación de textos en frontend/src/pages/PurchaseDetail.tsx para eliminar caracteres extra (acento, guion largo, preguntas).
- UI compras: selector de proveedor unificado (autocompletado con lista inicial, soporte dark y feedback en modal PDF, ficha de proveedor y Nueva compra).
- Flujo iAVaL (Validador de IA de remitos) — primera versión funcional:
  - Backend:
    - Endpoints nuevos:
      - `POST /purchases/{purchase_id}/iaval/preview` — Extrae texto del PDF, construye prompt con datos actuales de la compra, invoca IA y retorna propuesta estructurada + diffs.
      - `POST /purchases/{purchase_id}/iaval/apply` — Aplica cambios al borrador según la propuesta recibida, registra auditoría y persiste.
    - Utilidades:
      - Extracción de texto de PDF con `pdfplumber` (fallback seguro si no está disponible).
      - Builder de prompt con esquema de salida JSON estricto.
      - Normalización de salida IA y coerción a JSON (tolerante a prefijos/prosa del proveedor).
      - Detección de diffs permitidos:
        - Header: `remito_number`, `remito_date`, `vat_rate`.
        - Líneas por índice: `qty`, `unit_cost`, `line_discount`, `supplier_sku`, `title`.
      - Auditoría en `apply` (acción `purchase.iaval.apply`).
  - Frontend:
    - Servicios en `frontend/src/services/purchases.ts`:
      - `iavalPreview(id)` y `iavalApply(id, proposal, emitLog?)`.
    - UI en `frontend/src/pages/PurchaseDetail.tsx`:
      - Botón “iAVaL” visible en BORRADOR (deshabilitado si no hay PDF adjunto).
  - Modal de revisión de cambios: muestra confianza, comentarios, diffs de header y líneas; casilla “Enviar logs de cambios” para activar registro; botón “Sí, aplicar cambios” que aplica cambios y, si corresponde, habilita enlaces de descarga del log.
  - Seguridad/Reglas:
    - Operación limitada a estado BORRADOR y requiere al menos un PDF adjunto.
    - Cambios aplicables restringidos a campos permitidos (sin re-asociación automática de productos).

- Otras capacidades ya presentes (resumen):
  - Importación y edición de borradores de compras con cálculo de totales e IVA.
  - Validación de líneas (vinculación SKU proveedor / producto), creación rápida de productos y creación masiva.
  - Confirmación de compra con aplicación de deltas de stock y reenvío de stock en confirmadas.
  - Logs de importación y descarga de JSON de auditoría.

## Implementaciones pendientes (próximos hitos)

Hito 0 — Consolidación iAVaL (estado actual y cierre)
- Documentación específica del flujo iAVaL
  - Detallar en `docs/PURCHASES.md` el flujo, precondiciones, campos afectados, mensajes de error comunes y ejemplos de salida.
  - Documentar variables de entorno para IA: `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_DISABLE_OLLAMA=true`, timeouts.
- Pruebas automatizadas
  - Backend: tests de preview/apply con IA mockeada (JSON determinista), validando diffs y actualización de compra.
  - Frontend: smoke test del modal iAVaL y happy path de aplicación, y caso “sin diferencias”.
- UX/Ergonomía iAVaL
  - Plegado/paginación de diffs extensos, aviso cuando la confianza sea baja y resaltado claro de “sin diferencias”.
- Observabilidad y trazabilidad
  - Incluir `prompt_id`/`correlation_id` en logs; métricas básicas: ratio de aplicación, tiempo de respuesta, tasa de neutral/no-op.
- Estado proveedor IA
  - Forzar JSON-only en OpenAI (modo `json_object`), Ollama deshabilitado por env; fallback defensivo en preview para evitar 502 (ya implementado).

Hito 1 — Dominio SKU dual (SKU interno y SKU de proveedor)
- Objetivo
  - Asegurar que el sistema maneje y exponga claramente el SKU interno (editable) y el SKU de proveedor por cada relación proveedor–producto.
- Modelo/Datos (revisión de lo existente)
  - `Variant.sku` es el SKU interno único (global). Mantener constraint único.
  - `SupplierProduct.supplier_product_id` es el SKU del proveedor (único por `supplier_id`). Ya existe `UniqueConstraint(supplier_id, supplier_product_id)`.
  - `SupplierProduct.internal_product_id`/`internal_variant_id` vinculan a producto/variante internos. Mantener como fuente de verdad del mapeo.
  - Acciones: agregar índices si faltan en consultas de búsqueda por `supplier_id, supplier_product_id` y por `internal_variant_id`.
- Endpoints Backend
  - [Implementado] `PUT /variants/{id}/sku` (CSRF, admin|colaborador): editar SKU interno (valida regex y unicidad; audita cambio en `AuditLog`).
  - [Implementado] `POST /supplier-products/link` (CSRF): cuerpo `{ supplier_id, supplier_product_id, title?, internal_variant_id }` crea o actualiza la relación con validaciones (upsert amigable).

Hito 1.1 — Categorías manuales, asociación en productos y exportación de stock
- Objetivo
  - Permitir crear manualmente categorías de 2 niveles (Categoria, SubCategoria), asociarlas a productos existentes desde la UI, y ofrecer exportación XLS desde Stock.
- Modelo/Datos (existente y uso)
  - `Category`: ya implementado con jerarquía por `parent_id`. Se usarán niveles: `Categoria` (nivel 1, parent_id=null) y `SubCategoria` (nivel 2, parent_id=<id nivel 1>).
  - `Product.category_id`: FK a `categories.id` ya presente; se actualizará al asociar.
- Endpoints Backend
  - [Implementado] `GET /categories` y `POST /categories` (CSRF) para creación/listado; se utilizarán para alta manual de Categoria/SubCategoria.
  - [Nuevo] `PATCH /products/{product_id}` aceptará `category_id` para actualizar la categoría del producto (con validación de existencia y auditoría `product_update.category`).
  - [Implementado] `GET /stock/export.xlsx` (roles: cliente|proveedor|colaborador|admin): genera XLS con columnas `NOMBRE DE PRODUCTO`, `PRECIO DE VENTA` (canónico si existe, si no proveedor), `CATEGORIA` (path), `SKU PROPIO` respetando filtros del listado.
- Frontend
  - Productos (`/productos`):
    - [Implementado] Botones “Nueva categoría” y “Nueva subcategoría” con modales: crean `Categoria` (nivel 1) y `SubCategoria` (nivel 2) eligiendo `Categoria` padre. Usan `POST /categories` y refrescan lista.
    - En la ficha del producto (`/productos/:id`): agregar selector de `Categoria`/`SubCategoria` con guardado que llama a `PATCH /products/{id}` con `category_id`.
    - En ficha mantener y documentar edición de SKUs: ya existe `PUT /variants/{id}/sku` para SKU propio y modal “Agregar SKU de proveedor” que usa `POST /supplier-products/link`.
  - Stock (`/stock`):
    - [Implementado] Botón oscuro “Descargar XLS” que llama a `GET /stock/export.xlsx` respetando filtros vigentes y descarga el archivo.
- Criterios de aceptación
  - [Hecho] Se pueden crear `Categoria` y `SubCategoria` manualmente desde `/productos` y quedan visibles en filtros.
  - En la ficha de producto se puede asignar/modificar `Categoria/SubCategoria` y persiste en `Product.category_id`.
  - En la ficha se puede modificar SKU propio (variante) y SKU proveedor (vía vínculo) conforme endpoints actuales.
  - En `/stock` se descarga un XLS con columnas y datos solicitados, respetando filtros.
  - Auditoría: cambios de categoría quedan registrados en `AuditLog`.


  - [Implementado] Borrado de productos:
    - `DELETE /catalog/products` (CSRF): borrado con reglas. Bloquea cuando hay stock (`400`) o referencias en compras directas/indirectas (`409`); devuelve resumen con `deleted`, `blocked_stock`, `blocked_refs` para lotes.
    - `DELETE /products` (CSRF): borrado directo (no aplica reglas de stock/referencias). Pensado para usos internos y tests; elimina el producto y sus `SupplierProduct` asociados; devuelve `{ requested, deleted }`.
  - [Implementado] `GET /suppliers/search?q=`: autocompletar por `name|slug` (like, limit 20) para UI.
  - [Implementado] `GET /products/{product_id}/variants`: lista variantes del producto (id, sku, name, value) para alimentar modales de vínculo.
- Frontend
  - [Implementado] Componente `SupplierAutocomplete` creado (debounce, teclado, loading, vacío) e integrado en el modal de vínculo de la ficha.
  - [Implementado] Ficha de producto: botón “Agregar SKU de proveedor” abre modal con autocompletar de proveedor, `supplier_sku`, selector de variante interna y título opcional; al guardar, llama al upsert y refresca ofertas.
  - Compras: al editar una línea `SIN_VINCULAR`, permitir ingreso de `supplier_sku`; si coincide (supplier_id, supplier_sku) vincula y cambia a `OK`.
- Confirmación de compra (interacción con SKUs)
  - Durante `POST /purchases/{id}/confirm`, auto-vincular líneas no resueltas cuando (supplier_id, supplier_sku) existe y apunta a `internal_variant_id` válido.
- Criterios de aceptación
  - Se puede editar el SKU interno de una variante y persiste con unicidad garantizada.
  - Es posible vincular un nuevo SKU de proveedor a una variante desde UI y backend lo refleja (idempotente si ya existía).
  - El autocompletado de proveedor funciona en modales y formularios pertinentes.
  - En confirmación, líneas con `supplier_sku` reconocido se vinculan automáticamente.

Hito 2 — Confirmación de compras: correcciones de stock y seguridad transaccional
- Objetivo
  - Hacer la confirmación idempotente, precisa en stock y segura en concurrencia.
- Backend
  - Transacción atómica con nivel de aislamiento adecuado; locks pesimistas sobre `variants`/`inventory` al ajustar stock.
  - Redondeo consistente: cantidades enteras, precios con `Decimal` (2 decimales), control de desvío acumulado.
  - Idempotencia: marca de confirmación y protección ante re-ejecución (no duplica movimientos).
  - Price history: actualizar `SupplierProduct.current_purchase_price` y registrar `SupplierPriceHistory` en cada línea confirmada.
  - Auto-link previo a confirmar por (supplier_id, supplier_sku) cuando falte `product_id`/`variant_id`.
- Criterios de aceptación
  - Repetir confirmación no cambia stock ni duplica historial; responde 409 o 200 idempotente con indicación de “ya confirmado”.
  - Movimientos de stock consistentes con sumatoria de líneas; diferencias por redondeo ≤ $0.01.
  - Historial de precios creado por cada línea con precio válido.

Hito 3 — UI: Autocomplete de proveedor en fichas y flujos relevantes
- Objetivo
  - Reemplazar inputs numéricos de proveedor por un autocompletar usable y rápido.
- Backend
  - `GET /suppliers/search?q=` paginado, orden por `name`, retorna `{ id, name, slug }` (máx. 20).
- Frontend
  - Componente reutilizable `SupplierAutocomplete` (debounce 250ms, teclado accesible, loading state).
  - Usos:
    - [Implementado] Modal “Agregar SKU de proveedor” en ficha de producto.
    - [Implementado] Filtros de proveedor en `ProductsDrawer` y `Stock` reemplazados por autocompletar.
    - [Pendiente] Otros formularios con selección de proveedor (alta rápida, panel admin, usuarios, importación PDF, Compras listado) a migrar a autocompletar.
- Criterios de aceptación
  - Teclado: navegar, seleccionar; mouse: clic.
  - Vacío/no resultados: estados amigables, sin errores en consola.

Hito 1.2 — Ventas y Clientes (MVP)
- Backend: modelos `Customer`, `Sale`, `SaleLine`, `SalePayment`, `SaleAttachment` + endpoints mínimos (`/sales`, `/sales/customers`, adjuntos).
- Frontend: páginas `/clientes` y `/ventas`; botón desde Dashboard. Registro de venta descuenta stock y permite crear cliente mínimo en línea.
- Próximos: listado de ventas, anulación (reponer stock), reportes.

Hito 4 — Pipeline de extracción (PDF remito) más robusto
- Objetivo
  - Reducir dependencia de razonamiento IA en campos estructurables.
- Acciones
  - Extracción determinista de cabeceras y tabla (regex + heurísticas) antes de IA.
  - Perfiles de proveedor (Santa Planta primero): mapeos de columnas, normalizaciones (tildes, mayúsculas, separadores decimales), formatos de fecha.
  - OCR fallback con `ocrmypdf` cuando el PDF no tenga capa de texto o la calidad sea pobre (flag de diagnóstico en respuesta).
  - Artefactos: guardar tabla parseada (CSV/JSON) y comparación con borrador.
- Criterios de aceptación
  - Para Santa Planta, ≥ 95% de líneas correctamente parseadas sin IA en casos de prueba conocidos.
  - El preview iAVaL emite menos diffs triviales (p. ej. normalizaciones de formatting).

Hito 5 - Chatbot administrativo con acceso controlado
- Objetivo
  - Incorporar un chatbot corporativo con control de acceso estricto y soporte a tiempo real para desarrollo y soporte.
- Alcance
  - Roles diferenciados (Admin vs Colaborador) con permisos según alcance de información y capacidad de escritura limitada a `PR/`.
  - Integración con proveedor de SSO/MFA open source (p.ej. Keycloak/Authentik) usando OIDC y emisión de tokens con claims de rol.
  - Capa de gateway para repositorio en modo lectura y endpoint restringido para sugerencias en `PR/`.
  - Pipeline RAG con chunking etiquetado por rol y actualización incremental tras cambios en el repositorio.
  - Auditoría centralizada de consultas, respuestas y modificaciones, con reportes para admins.

### Ventas / Clientes (Sprint 1 + Sprint 2 parcial)
- Modelos y endpoints base de Customers y Sales (BORRADOR/CONFIRMADA/ENTREGADA/ANULADA) con líneas, pagos y adjuntos.
- Devoluciones parciales: `POST /sales/{id}/returns` + reposición de stock y auditoría `return_create`.
- Timeline consolidado: `GET /sales/{id}/timeline` (audit + pagos + devoluciones) para UI.
- Reportes agregados:
  - Ventas netas: `GET /sales/reports/net` (bruto, devoluciones, neto, ventas_count, devoluciones_count).
  - Top productos: `GET /sales/reports/top-products` (qty/monto vendidos, devueltos y netos).
  - Top clientes: `GET /sales/reports/top-customers` (bruto, devoluciones, neto, conteos).
- Cache in-memory TTL (60s) para reportes con invalidación autom. al confirmar venta o crear devolución.
- Libro de stock inicial: tabla `stock_ledger` + hooks en confirmación de venta (delta negativo) y devolución (delta positivo) con `balance_after`.
- Historial de stock por producto: `GET /products/{id}/stock/history` paginado.
- Búsqueda rápida de clientes: `GET /sales/customers/search?q=` con ranking (document_number exacta, nombre prefix, etc.).
- Endpoint dedicado de pagos `GET /sales/{id}/payments` (optimiza UI polling).
- Clamp automático de `discount_amount` al confirmar si excede `subtotal` (`sale_discount_clamped` audit).
- Indexación adicional ventas (status+sale_date, customer_id+sale_date) para acelerar filtros y reportes.
- Auditoría extendida: `sale_lines_ops`, `sale_payment_add`, `sale_confirm`, `sale_discount_clamped` con `elapsed_ms` y `stock_deltas`.
- Tests: lifecycle, timeline, reportes (net/top), ledger consistencia, clamp de descuento.

Pendiente siguiente iteración Ventas:
- Margen / costo en reportes (integrar costos de compra o precio promedio).
- Apoyo a notas de crédito / facturación y numeración de comprobantes.
- Depósitos múltiples y proyección de stock (reservas vs disponible).
- Paginación y filtros avanzados en historial de stock (fuente, rango fechas, tipo de movimiento).
- Prorrateo de descuento global a líneas para métrica de margen por producto.
- Entregables
  - Documentación viva: nuevos archivos `docs/CHATBOT_ARCHITECTURE.md`, `docs/CHATBOT_ROLES.md`, actualización de `README.md` y `docs/roles-endpoints.md`.
  - Suite de pruebas (unitarias/integración) para autenticación, gateway del repositorio, RAG y auditoría.
  - Scripts de soporte (`scripts/build_chatbot_index.py`, diagnósticos de auditoría) documentados en `AGENTS.md`.

Hito 5 — Pruebas y documentación cruzada
- Tests
  - Backend: unit/integration para endpoints nuevos (`variants/sku`, `supplier-products/link`, `suppliers/search`, confirmación idempotente).
  - Frontend: pruebas del componente `SupplierAutocomplete` y flujo de agregar SKU de proveedor.
- Documentación
  - Actualizar `docs/PURCHASES.md`, `docs/SUPPLIERS.md` y esta hoja de ruta al finalizar cada hito.

Hito 6 — Despliegue y migraciones
- Migraciones
  - Agregar índices que falten; no se prevén columnas nuevas críticas (revisión post-impl.).
- Rollout
  - Feature flags donde aplique; checklist de rollback.
- Criterios de aceptación
  - Migraciones aplican en < 2s en dataset de prueba y no bloquean el arranque.

Hito 7 - Chatbot: Consulta de precios en lenguaje natural
- Objetivo
  - Permitir que el chatbot responda el precio de venta actual de un producto a partir de consultas en español.
- Estado
  - Backend listo: matcher `price_query`, servicio `price_lookup`, búsqueda SKU/nombre y auditoría registrados.
  - Frontend en curso: ChatWindow representa respuestas `price_answer` con detalle de ofertas.
  - Prompt ajustado para desalentar respuestas inventadas sobre precios.
- Backend / Dominio
  - Agregar un intent específico en el router de chat (`services/routers/chat.py`, `ai/router.py`) que detecte solicitudes de precio.
  - Crear servicio de búsqueda de precios (`services/chat/price_lookup.py` o equivalente) que resuelva por SKU interno, SKU proveedor o coincidencia fuzzy de nombre.
  - Exponer información de precio preferente (`sale_price` canónico; fallback a `current_sale_price` del supplier item) y moneda configurable.
  - Manejar casos sin resultado o con múltiples coincidencias (respuesta con sugerencias y guía para desambiguar).
- Frontend / UI
  - Adaptar el render de respuestas del chat para mostrar formatos específicos de precio (texto más posible enlace a ficha de producto).
  - Ajustar prompt y ayudas en la interfaz para que los usuarios sepan que pueden preguntar por precios.
- IA / Prompting
  - Enriquecer el `SYSTEM_PROMPT` para que priorice el intent antes de delegar al LLM.
  - Definir fallback IA solo para clarificar consultas ambiguas, registrando eventos en ImportLog/ServiceLog.
- Observabilidad
  - Métricas básicas: cantidad de consultas de precio, tasa de éxito, latencia promedio, cantidad de resultados múltiples/no encontrados.
  - Auditoría opcional por usuario (`AuditLog` con acción `chat.price_lookup`).
- QA / Pruebas
  - Unit tests para matcher de intent y para el servicio de resolución de precios.
  - Tests API (`tests/test_ai_router.py`) simulando la conversación.
  - Playwright/E2E: flujo desde la SPA validando respuesta visible.
- Documentación
  - Actualizar `docs/CHAT.md` (crear si no existe) y `CHANGELOG.md` cuando se implemente.
  - Añadir sección en `README.md` sobre capacidades del chatbot.
- Criterios de aceptación
  - El chatbot debe responder con el precio vigente para al menos SKU exacto y nombre parcial.
  - Debe manejar ausencia de datos sin errores 500.
  - Respuestas alineadas con políticas de idioma (español) y tono definido.
## Detalles técnicos por área

- Backend (compras):
  - Modelos: `Purchase`, `PurchaseLine`, `PurchaseAttachment` (ver `db/models.py`).
  - Rutas: router de compras (ver `services/routers/purchases.py`).
  - iAVaL: helpers para PDF/prompt/JSON, endpoints `preview` y `apply` (precondiciones, diffs, auditoría).

- IA:
  - Router y providers en `ai/`. Uso de `Task.REASONING`.
  - Prompt con esquema de salida JSON: `{ header, lines[], confidence, comments[] }`.

- Frontend:
  - Servicios en `frontend/src/services/purchases.ts` (`iavalPreview`, `iavalApply`).
  - Pantalla `PurchaseDetail.tsx`: botón “iAVaL”, modal y refresco tras `apply`.

## Cómo probar manualmente (resumen)

- Caso base: Compra en BORRADOR con PDF adjunto en `data/purchases/{id}/`.
- Abrir la compra en el frontend → click en “iAVaL” → revisar cambios → “Sí, aplicar cambios”.
- Verificar actualización de header/líneas en la UI y logs de auditoría.

## Riesgos y consideraciones

- Respuestas de IA no estrictamente JSON → se mitigó con normalización/parsing robusto; mantener defensivo.
- PDFs con OCR deficiente → puede requerir `force_ocr` en flujos de importación o ajustes de extracción.
- No se realizan re-asociaciones de producto automáticas en esta versión.

## Trazabilidad y mantenimiento

- Por favor, actualizar este Roadmap en cada PR/commit que afecte:
  - Endpoints, modelos, capa IA, lógica de validación o UI.
  - Dependencias, variables de entorno o scripts de entorno.
- Vincular commits/PRs relevantes y anotar brevemente el impacto.

---
Notas de mantenimiento: Si se modifica la lógica de migraciones o diagnósticos, actualizar también `docs/MIGRATIONS_NOTES.md` y el inventario en `AGENTS.md`.







