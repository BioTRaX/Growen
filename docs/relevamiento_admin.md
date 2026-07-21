<!-- NG-HEADER: Nombre de archivo: relevamiento_admin.md -->
<!-- NG-HEADER: Ubicación: docs/relevamiento_admin.md -->
<!-- NG-HEADER: Descripción: Relevamiento funcional y técnico del portal React previo a la migración a Vue 3. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Relevamiento del portal de administración actual

Fecha de corte: 2026-07-17.

## 1. Contexto

El frontend productivo relevado reside en `frontend/` y es una SPA React 19 + TypeScript + Vite. `frontend-vue/` es el destino parcial de la migración y no se tomó como fuente para definir la paridad: cuando existe una diferencia, manda el comportamiento observable del frontend React y el contrato del router FastAPI actual.

El relevamiento parte de `frontend/src/App.tsx`, `frontend/src/routes/paths.ts`, las páginas y componentes importados por esas rutas, los clientes de `frontend/src/services/` y los routers incluidos por `services/api.py`. No se modificó código React ni Vue.

El término **portal de administración** incluye aquí toda la SPA operativa autenticada —productos, stock, mercado, compras, proveedores, clientes, ventas y `/admin/*`— porque comparte sesión, toolbar, chat y contratos que deben conservarse durante la migración.

### Roles usados por la SPA

| Rol | Acceso de rutas actual |
|---|---|
| `guest` | `/guest` y detalle `/productos/:id` en solo lectura. |
| `cliente` | Dashboard, Productos, Stock y detalle de producto. |
| `proveedor` | Igual conjunto de rutas generales que `cliente`. |
| `colaborador` | Módulos operativos y layout `/admin`; varias acciones internas siguen exigiendo `admin` en backend. |
| `admin` | Acceso completo, incluida gestión de usuarios y backups. |

## 2. Observaciones

### 2.1 Inventario de rutas y vistas

| Ruta | Vista React | Roles del router | Propósito y navegación principal |
|---|---|---|---|
| `/login` | `Login` | Pública | Login por identificador/email y contraseña; acceso invitado. |
| `/guest` | `Dashboard` | Todos, incluido `guest` | Dashboard limitado; el toolbar oculta acciones no permitidas. |
| `/` | `Dashboard` | Todos salvo `guest` | Shell operativo, chat y accesos a Compras, Clientes y Ventas. |
| `/productos` | `Productos` + `ProductsDrawer` | `cliente`, `proveedor`, `colaborador`, `admin` | Catálogo, filtros, stock/precios, canónicos, equivalencias, tags y acciones masivas. |
| `/productos/:id` | `ProductDetail` | Todos, incluido `guest` | Ficha, variantes, precios, categoría, enriquecimiento, imágenes y auditoría según rol. |
| `/productos/:id/imagen` | `ProductImagesGallery` | `colaborador`, `admin` | Galería y procesamiento avanzado de imágenes. |
| `/stock` | `Stock` | `cliente`, `proveedor`, `colaborador`, `admin` | Existencias, precios, exportaciones, catálogos y enriquecimiento masivo. |
| `/stock/shortages` | `StockShortages` | `colaborador`, `admin` | Alta, listado, métricas y filtros de faltantes reportados. |
| `/mercado` | `Market` | `colaborador`, `admin` | Referencias de mercado, fuentes, precios y actualización individual/masiva. |
| `/proveedores` | `Suppliers` | `colaborador`, `admin` | Listado, alta y borrado masivo de proveedores. |
| `/proveedores/:id` | `SupplierDetail` | `colaborador`, `admin` | Edición de datos/contacto/notas y archivos del proveedor. |
| `/compras` | `Purchases` | `colaborador`, `admin` | Listado filtrable, importación PDF/email, rollback y acceso a detalle. |
| `/compras/nueva` | `PurchaseNew` | `colaborador`, `admin` | Alta manual de borrador y líneas. |
| `/compras/:id` | `PurchaseDetail` | `colaborador`, `admin` | Edición, validación, iAVaL, confirmación, stock, logs y anulación. |
| `/clientes` | `Customers` | `colaborador`, `admin` | Alta y listado de clientes. |
| `/clientes/:id` | `CustomerDetail` | `colaborador`, `admin` | Edición del cliente e historial paginado de ventas. |
| `/ventas` | `Sales` | `colaborador`, `admin` | Alta de venta, documentos, canales y operaciones sobre ventas recientes. |
| `/ventas/:id` | `SaleDetail` | `colaborador`, `admin` | Detalle de cabecera, productos, costos y pagos. |
| `/imagenes-productos` | `ImagesAdminPanel` | `colaborador`, `admin` | Operación del crawler, revisión, logo y procesamiento masivo de imágenes. |
| `/admin` | `AdminLayout` | `colaborador`, `admin` | Redirige a la última sección guardada o a `/admin/servicios`. |
| `/admin/servicios` | `ServicesPage` / `ServicesView` Vue | `colaborador`, `admin` | Migrada: resumen de workers y, solo para admin, MCP. |
| `/admin/servicios/workers` | `WorkersPage` / `WorkersView` Vue | `colaborador`, `admin` | Migrada: inicio/parada, health, dependencias y logs/SSE. |
| `/admin/servicios/mcp-tools` | `MCPToolsPage` / `McpToolsView` Vue | `admin` | Migrada: estado e inicio/parada de servidores MCP; permiso corregido contra backend. |
| `/admin/usuarios` | `UsersPage` / `UsersView` Vue | `admin` | Migrada: búsqueda, alta, edición, reset y eliminación de usuarios. |
| `/admin/imagenes-productos` | Redirección | `colaborador`, `admin` | Redirige a `/imagenes-productos`. |
| `/admin/drive-sync` | `DriveSyncPage` | `colaborador`, `admin` | Sincronización de Drive, progreso por WebSocket y reproceso de errores. |
| `/admin/backups` | `BackupsPage` / `BackupsView` Vue | `admin` | Migrada: listado, ejecución y descarga autenticada de backups. |
| `/admin/catalogos/diagnostico` | `CatalogDiagnosticsPage` | `colaborador`, `admin` | Estado, resúmenes y log detallado de generación de catálogos. |
| `/admin/scheduler` | `SchedulerControl` | `colaborador`, `admin` | Scheduler de actualización de mercado y ejecución manual. |
| `/admin/cerebro` | `KnowledgePage` | `colaborador`, `admin` | Archivos, carga, indexación y fuentes de conocimiento. |
| `/admin/dashboard` | `DashboardStats` | `colaborador`, `admin` | Salud del sistema y estadísticas del chat. |
| `/admin/chats` | `ChatInbox` | `colaborador`, `admin` | Bandeja de conversaciones, estado y notas administrativas. |
| `/admin/imagenes` | Redirección legacy | `colaborador`, `admin` | Alias hacia `/imagenes-productos`. |
| Cualquier otra | Redirección | — | Envía a `/login`. |

### 2.2 Funcionalidad transversal

- `AuthProvider` rehidrata la sesión al montar la SPA y Axios agrega cookies y `X-CSRF-Token` a mutaciones. Un `401` limpia la sesión.
- `AppToolbar` ofrece navegación por rol, cambio de tema, logout y el evento `open-upload` para listas de precios.
- `Dashboard` monta `ChatWindow`, que usa WebSocket con fallback HTTP, soporta drag-and-drop, comandos, visor de importación, proveedores y catálogo embebido.
- `ErrorBoundary` reporta fallos de render del frontend; `BugReportButton` permite un reporte manual global.
- `ToastProvider`, tema y `MassCanonicalProvider` envuelven todas las rutas.
- El layout admin conserva `lastAdminTab` en `localStorage` y consulta una vez por día si hubo backup automático.

### 2.3 Detalle funcional por vista

#### Acceso y Dashboard

**Login (`/login`).** Inputs: usuario/email y contraseña. Acciones: iniciar sesión y entrar como invitado. Endpoints: `POST /auth/login`, `GET /auth/me`, `POST /auth/guest`.

**Dashboard (`/` y `/guest`).** Presenta toolbar, chat y botones Compras/Clientes/Ventas para staff. El chat envía texto, recibe respuestas y abre herramientas contextuales; la importación Excel permite elegir/crear proveedor, descargar plantilla, subir en dry-run, revisar cambios/errores y confirmar. Endpoints: `WS /ws`, `POST /chat`, los endpoints de importación indicados en la matriz consolidada y `POST /auth/logout` al salir.

#### Productos, Stock, Mercado e Imágenes

**Productos (`/productos`).** Filtros: texto, proveedor, categoría, stock, recientes y tipo (`all/canonical/supplier`); paginación y preferencias de columnas. Acciones: alta de producto/oferta, alta de categoría/subcategoría, selección, borrado, stock inline, precio de venta individual/masivo, completar precios faltantes, historial de precios, ofertas por proveedor, canónico, equivalencia, tags, actividad, diagnóstico local y wizard/recovery de canonización masiva. Endpoints principales: `GET/POST /products`, `DELETE /catalog/products`, `PATCH /products/{id}/stock`, `GET/POST /categories`, `GET/PUT /products-ex/users/me/preferences/products-table`, familia `/products-ex/*`, `/canonical-products/*`, `/equivalences`, `/tags/*`, `GET /price-history` y `/products/{id}/audit-logs`.

**Detalle de producto (`/productos/:id`).** Muestra nombre/SKU preferido, descripción sanitizada, precio, categoría, datos técnicos, tags, variantes, ofertas e imágenes. Staff puede editar descripción, categoría, datos técnicos, SKU canónico/interno, precios, vincular SKU de proveedor, enriquecer/reenriquecer/limpiar IA, borrar producto y operar imágenes; `guest` ve solo lectura. Inputs: selector de estilo, URL/archivo de imagen, descripción, categoría, campos numéricos técnicos, SKU y formulario de vínculo. Endpoints: `GET/PATCH /products/{id}`, `POST /products/{id}/enrich[?force=true]`, `DELETE /products/{id}/enrichment`, auditorías, variantes/ofertas, preferencias de detalle, categorías, tags, precios, vínculo y familia de imágenes.

**Galería (`/productos/:id/imagen`).** Selecciona imagen, portada y versión; muestra metadatos. Acciones: set primary, eliminar, rotar ±90°, crop personalizado o cuadrado, WebP, watermark, logo y descarga. Endpoints: `GET /products/{id}/images`, `POST/DELETE /products/{id}/images/{imageId}/*` detallados más abajo.

**Stock (`/stock`).** Tabs con/sin stock; filtros por texto, proveedor y categoría; edición inline de stock, precio de compra y precio de venta efectivo. Acciones masivas: selección, borrado, enriquecimiento, completar precios; exportaciones XLSX/CSV/PDF/TiendaNegocio; generar/ver/descargar catálogo e histórico. Endpoints: `GET /products`, `PATCH /products/{id}/stock`, familia `/products-ex/*`, `DELETE /catalog/products`, `POST /products/enrich-multiple`, exportaciones `/stock/export*` y familia `/catalogs/*`.

**Faltantes (`/stock/shortages`).** Dashboard de contadores, filtro por motivo y paginación. El modal busca un producto y captura motivo, cantidad estimada y observación. Endpoints: `GET /stock/shortages`, `GET /stock/shortages/stats`, `POST /stock/shortages`, `GET /products`.

**Mercado (`/mercado`).** Filtros por texto, proveedor y categoría; selección masiva; edición de precio de venta y borrado de canónicos sin producto interno. El detalle administra precio de referencia, fuentes estáticas/dinámicas, edición/borrado, refresco de precios, descubrimiento y alta masiva de sugerencias. Endpoints: `GET /market/products`, `PATCH /market/products/{id}/sale-price`, `POST /market/products/batch-refresh`, familia de fuentes y descubrimiento, y `DELETE /canonical-products/{id}`.

**Imágenes de productos (`/imagenes-productos`).** Configura job (`active`, modo, tasa, reintentos y scope), consulta estado/logs/snapshots, streaming live, prueba por título, fuerza crawl/purge y limpia logs. Revisa imágenes pendientes, busca/selecciona productos, procesa WebP/watermark/logo y administra el logo global. Si Playwright está apagado ofrece iniciarlo y ver logs. Endpoints: familia `/admin/image-jobs/*`, `/products/images/review*`, `GET /products`, procesamientos `/products/{id}/images/*`, `/admin/images/logo*` y familia `/admin/services/{name}/*`.

#### Compras y Proveedores

**Compras (`/compras`).** Filtros: proveedor, estado, remito, producto y rango de fechas. Acciones: abrir detalle, rollback de confirmada, eliminar borrador/anulada e importar por PDF o email. PDF captura proveedor, archivo, debug y OCR; email admite `.eml`, HTML o texto. Endpoints: `GET /purchases`, `POST /purchases/import/santaplanta`, `POST /purchases/import/pop-email`, `POST /purchases/{id}/rollback`, `DELETE /purchases/{id}` y servicios de gating/logs del importador. Ante error, el modal muestra el correlation ID y permite copiarlo sin invocar una ruta de logs inexistente.

**Nueva compra (`/compras/nueva`).** Cabecera con proveedor, remito, fecha, IVA y nota; grilla editable de SKU, producto, cantidad, costo, descuento y nota. Guarda primero el borrador y luego sus líneas. Endpoints: `POST /purchases`, `PUT /purchases/{id}`.

**Detalle de compra (`/compras/:id`).** Edita cabecera/líneas; autocompleta SKU del proveedor; crea productos individual o masivamente. Acciones: guardar, validar, confirmar, auditoría, reenvío/preview de stock, iAVaL, exportar no vinculados, ver/copiar/descargar logs, anular, rollback y eliminar. Endpoints: `GET/PUT/DELETE /purchases/{id}`, `/validate`, `/confirm`, `/cancel`, `/rollback`, `/resend-stock`, `/iaval/vision`, `/logs`, `/unmatched/export`, `GET /suppliers/{id}/items` y `POST /products`.

**Proveedores (`/proveedores`).** Listado con selección; alta con slug, nombre, ubicación y contacto; borrado masivo con resumen de bloqueados/errores. Endpoints: `GET/POST/DELETE /suppliers`.

**Detalle de proveedor (`/proveedores/:id`).** Edita nombre, ubicación, contacto y notas; slug solo lectura. Lista, sube y descarga archivos con nota opcional. Endpoints: `GET/PATCH /suppliers/{id}`, `GET /suppliers/{id}/files`, `POST /suppliers/{id}/files/upload`, `GET /suppliers/files/{fileId}/download`.

#### Clientes y Ventas

**Clientes (`/clientes`).** Alta rápida por nombre y email y listado navegable. Endpoints: `GET/POST /customers`.

**Detalle de cliente (`/clientes/:id`).** Edita nombre, dirección, email y teléfono; lista ventas paginadas y abre detalle. Endpoints: `GET/PUT /customers/{id}`, `GET /customers/{id}/sales`.

**Ventas (`/ventas`).** Alta con fecha, cliente existente/nuevo, canal, líneas de producto/cantidad/precio, costos adicionales, documentos y nota. Lista ventas recientes y permite confirmar, entregar, anular y abrir detalle. Endpoints: `GET/POST /customers`, `GET /sales/products`, `GET/POST /sales`, `GET/POST/DELETE /sales/channels`, `POST /sales/{id}/attachments`, `/confirm`, `/deliver`, `/annul`.

**Detalle de venta (`/ventas/:id`).** Vista de cabecera/estado/cliente/canal, líneas, costos y pagos. Resuelve datos complementarios de cliente, productos y canales. Endpoints: `GET /sales/{id}`, `GET /customers/{id}`, `GET /products/{id}`, `GET /sales/channels`.

#### Administración

**Servicios (`/admin/servicios`).** Tarjetas resumen de workers y MCP con conteos de activos/total y navegación a subpaneles. Endpoints: `GET /admin/services`, `GET /admin/mcp/health`.

**Workers (`/admin/servicios/workers`).** Por servicio: modo local/Docker, iniciar, detener, panic stop, auto-start, health, check/instalación de dependencias, logs, borrado y stream SSE. Endpoints: familia `/admin/services/*` y `GET /health/service/{name}`.

**MCP Tools (`/admin/servicios/mcp-tools`).** Estado de servidores MCP y acciones start/stop. Endpoints: `GET /admin/mcp/health`, `POST /admin/mcp/{name}/start`, `POST /admin/mcp/{name}/stop`.

**Usuarios (`/admin/usuarios`).** Filtros por texto y rol; alta con identificador, email, nombre, contraseña, rol y proveedor; edición, reset y eliminación. Endpoints: `GET/POST /auth/users`, `PATCH/DELETE /auth/users/{id}`, `POST /auth/users/{id}/reset-password`, `GET /suppliers/search`.

**Drive Sync (`/admin/drive-sync`).** Consulta estado, inicia sincronización completa o desde carpeta de errores, muestra progreso/archivo actual, contadores, errores y mensajes en tiempo real. Endpoints: `GET /admin/drive-sync/status`, `POST /admin/drive-sync/start`, `GET /admin/drive-sync/errors-folder-id`, `WS /admin/drive-sync/ws`.

**Backups (`/admin/backups`).** Ejecuta backup, lista archivo/fecha/tamaño y descarga. Endpoints: `GET /admin/backups`, `POST /admin/backups/run`, `GET /admin/backups/download/{filename}`. El layout usa además `GET /admin/backups/last-auto`.

**Diagnóstico de catálogos (`/admin/catalogos/diagnostico`).** Refresca generación activa, últimos resúmenes y detalle temporal del log seleccionado. Endpoints: `GET /catalogs/diagnostics/status`, `/summaries`, `/log/{id}`. El histórico de Stock agrega `GET /config` y, solo admin, `POST /unlock`.

**Scheduler (`/admin/scheduler`).** Muestra estado, configuración y estadísticas; activa/desactiva, inicia/detiene, configura hora/intervalo y ejecuta manualmente con máximo de productos y antigüedad. Endpoints: `GET /admin/scheduler/status`, `POST /start`, `/stop`, `/toggle`, `/config`, `/run-now` bajo el mismo prefijo.

**Cerebro (`/admin/cerebro`).** Estado de almacenamiento/indexación, archivos de `/Conocimientos`, upload, indexación de archivo o carpeta con `force`, polling de tarea y eliminación de una fuente de la base. Endpoints: `GET /admin/knowledge/files`, `/status`, `/tasks/{id}`; `POST /upload`, `/index`; `DELETE /sources/{id}`.

**Dashboard admin (`/admin/dashboard`).** Salud de proceso, storage, DB, Redis, Dramatiq y proveedores IA; estadísticas de sesiones/mensajes/chat. Endpoints: `GET /health/summary`, `GET /admin/chats/stats`.

**Chat admin (`/admin/chats`).** Lista paginada con filtro de estado; muestra mensajes y metadatos de una sesión; cambia estado y guarda notas. Endpoints: `GET /admin/chats`, `GET /admin/chats/{sessionId}`, `PATCH /admin/chats/{sessionId}`.

### 2.4 Mapa consolidado de endpoints consumidos

Los segmentos `{id}`, `{productId}`, `{imageId}`, `{name}`, `{sessionId}` y similares son parámetros dinámicos. Los query params se muestran cuando cambian el flujo funcional.

#### Sesión, shell, chat y diagnóstico global

| Método | Endpoint | Consumidor/acción |
|---|---|---|
| POST | `/auth/login` | Login. |
| POST | `/auth/guest` | Sesión invitada. |
| GET | `/auth/me` | Rehidratación y confirmación de sesión. |
| POST | `/auth/logout` | Salir. |
| WS | `/ws` | Chat en tiempo real. |
| POST | `/chat` | Fallback HTTP del chat. |
| POST | `/bug-report` | Reporte manual global. |
| POST | `/debug/frontend/log-error` | ErrorBoundary. |
| GET | `/health/summary` | Health y dashboard admin. |

#### Productos, categorías, canónicos, precios y tags

| Método | Endpoint(s) | Acción |
|---|---|---|
| GET / POST | `/products` | Buscar/listar y crear producto. |
| GET / PATCH | `/products/{id}` | Detalle y edición de descripción/categoría/datos técnicos. |
| DELETE | `/catalog/products` | Borrado individual o masivo protegido. |
| PATCH | `/products/{id}/stock` | Stock inline. |
| GET | `/products/{id}/variants` | Variantes. |
| PUT | `/variants/{variantId}/sku` | SKU de variante. |
| POST | `/supplier-products/link` | Vincular oferta/variante. |
| GET | `/products/{id}/audit-logs` | Actividad/diagnóstico. |
| POST | `/products/{id}/enrich` y `?force=true` | Enriquecer/reenriquecer. |
| DELETE | `/products/{id}/enrichment` | Limpiar enriquecimiento. |
| POST | `/products/enrich-multiple` | Enriquecimiento masivo. |
| GET / POST | `/categories` | Listar y crear categoría/subcategoría. |
| GET / POST / PATCH / DELETE | `/canonical-products`, `/canonical-products/{id}` | CRUD de canónicos. |
| GET | `/canonical-products/{id}/offers` | Ofertas del canónico. |
| GET | `/canonical-products/resolve?sku=...` | Resolver SKU. |
| POST | `/canonical-products/batch-job` | Canonización masiva. |
| GET | `/catalog/next-seq?category_id=...` | Próxima secuencia de SKU. |
| POST | `/equivalences` | Alta/actualización de equivalencia. |
| GET / POST | `/tags` | Listar/crear tags. |
| POST / DELETE | `/tags/products/{productId}/tags`, `/tags/products/{productId}/tags/{tagId}` | Asignar/quitar tags. |
| POST | `/tags/products/bulk-tags` | Tags masivos. |
| GET | `/price-history` | Historial de precios por producto/oferta. |
| PATCH | `/products-ex/products/{id}/sale-price` | Precio de venta canónico. |
| PATCH | `/products-ex/supplier-items/{id}/buy-price` | Precio de compra de oferta. |
| PATCH | `/products-ex/supplier-items/{id}/sale-price` | Precio de venta fallback. |
| POST | `/products-ex/products/bulk-sale-price` | Precio de venta masivo. |
| POST | `/products-ex/supplier-items/fill-missing-sale` | Completar precios faltantes. |
| GET | `/products-ex/products/{id}/offerings` y `/products-ex/products/internal/{id}/offerings` | Comparativa de ofertas. |
| GET / PUT | `/products-ex/users/me/preferences/products-table` | Preferencias de tabla. |
| GET / PUT | `/products-ex/users/me/preferences/product-detail` | Preferencia visual de ficha. |

#### Imágenes

| Método | Endpoint | Acción |
|---|---|---|
| GET / POST | `/products/{productId}/images`, `/products/{productId}/images/upload` | Listar/subir. |
| POST | `/products/{productId}/images/from-url` | Descargar desde URL. |
| POST / DELETE | `/products/{productId}/images/{imageId}/set-primary`, `/products/{productId}/images/{imageId}` | Portada/eliminar. |
| POST | `/products/{productId}/images/{imageId}/lock` | Lock/unlock. |
| POST | `/products/{productId}/images/{imageId}/rotate` | Rotar. |
| POST | `/products/{productId}/images/{imageId}/crop-custom` y `/crop-square` | Recortar. |
| POST | `/products/{productId}/images/{imageId}/process/remove-bg` | Quitar fondo. |
| POST | `/products/{productId}/images/{imageId}/process/watermark` | Watermark. |
| POST | `/products/{productId}/images/{imageId}/process/logo` | Aplicar logo. |
| POST | `/products/{productId}/images/{imageId}/seo/refresh` | Regenerar SEO. |
| POST | `/products/{productId}/images/{imageId}/generate-webp` | Generar WebP. |
| GET | `/products/{productId}/images/audit-logs` | Auditoría de imágenes. |
| GET / POST | `/products/images/review`, `/products/images/{imageId}/review/approve`, `/review/reject` | Cola de revisión. |
| GET / POST | `/admin/images/logo`, `/admin/images/logo/upload` | Logo global. |

#### Stock y catálogos

| Método | Endpoint | Acción |
|---|---|---|
| GET | `/stock/export.xlsx`, `/stock/export.csv`, `/stock/export.pdf` | Exportar vista filtrada. |
| GET | `/stock/export-tiendanegocio.xlsx` | Exportar TiendaNegocio. |
| GET / POST | `/stock/shortages`, `GET /stock/shortages/stats` | Listar/crear y métricas de faltantes. |
| POST | `/catalogs/generate` | Generar PDF. |
| HEAD / GET | `/catalogs/latest`, `/catalogs/latest/download` | Verificar, ver y descargar último. |
| GET | `/catalogs` y `/catalogs/export.csv` | Histórico y exportación. |
| GET / DELETE | `/catalogs/{id}`, `GET /catalogs/{id}/download` | Ver, borrar y descargar histórico. |
| GET | `/catalogs/diagnostics/status`, `/config`, `/summaries`, `/log/{id}` | Diagnóstico. |
| POST | `/catalogs/diagnostics/unlock` | Desbloqueo administrativo. |

#### Mercado

| Método | Endpoint | Acción |
|---|---|---|
| GET | `/market/products` | Listado filtrado. |
| GET / POST | `/market/products/{id}/sources` | Fuentes y alta manual. |
| PATCH / DELETE | `/market/sources/{sourceId}` | Editar/eliminar fuente. |
| POST | `/market/products/{id}/refresh-market` | Refrescar precio individual. |
| POST | `/market/products/batch-refresh` | Refresco masivo. |
| PATCH | `/market/products/{id}/sale-price` | Precio de venta. |
| PATCH | `/market/products/{id}/market-reference` | Referencia de mercado. |
| POST | `/market/products/{id}/discover-sources?max_results=...` | Descubrir fuentes. |
| POST | `/market/products/{id}/sources/from-suggestion` | Agregar sugerencia. |
| POST | `/market/products/{id}/sources/batch-from-suggestions` | Agregar sugerencias masivas. |

#### Compras, proveedores e importaciones

| Método | Endpoint | Acción |
|---|---|---|
| GET / POST | `/purchases` | Listar/crear borrador. |
| GET / PUT / DELETE | `/purchases/{id}` | Detalle, guardar y eliminar. |
| POST | `/purchases/{id}/validate`, `/confirm`, `/cancel`, `/rollback`, `/resend-stock` | Ciclo de vida e impacto de stock. |
| POST | `/purchases/{id}/iaval/vision` | Preview/aplicación IA vigente. |
| GET | `/purchases/{id}/logs` y `?format=json` | Timeline/descarga de logs. |
| GET | `/purchases/{id}/unmatched/export?fmt=...` | Exportar no vinculados. |
| POST | `/purchases/import/santaplanta` | Importar PDF. |
| POST | `/purchases/import/pop-email` | Importar email. |
| GET / POST / DELETE | `/suppliers` | Listar/crear/borrar masivo. |
| GET / PATCH | `/suppliers/{id}` | Detalle/edición. |
| GET / POST | `/suppliers/{id}/items` | Buscar/crear oferta. |
| GET | `/suppliers/search` | Autocomplete. |
| GET / POST | `/suppliers/{id}/files`, `/suppliers/{id}/files/upload` | Archivos. |
| GET | `/suppliers/files/{fileId}/download` | Descargar archivo. |
| GET | `/suppliers/price-list/template`, `/suppliers/{id}/price-list/template` | Plantillas. |
| POST | `/suppliers/{id}/price-list/upload?dry_run=true` | Preview de lista. |
| GET | `/imports/{jobId}/preview` | Cambios/errores paginados. |
| POST | `/imports/{jobId}/commit` | Confirmar importación. |

#### Clientes y ventas

| Método | Endpoint | Acción |
|---|---|---|
| GET / POST | `/customers` | Listar/crear. |
| GET / PUT | `/customers/{id}` | Detalle/editar. |
| GET | `/customers/{id}/sales` | Historial paginado. |
| GET / POST | `/sales` | Listar/crear. |
| GET | `/sales/products`, `/sales/{id}` | Selector y detalle. |
| GET / POST | `/sales/channels` | Listar y crear canales. |
| POST | `/sales/{id}/attachments` | Documentos. |
| POST | `/sales/{id}/confirm`, `/deliver`, `/annul` | Ciclo de vida. |

#### Administración operativa

| Método | Endpoint | Acción |
|---|---|---|
| GET | `/auth/users` | Listar/buscar usuarios. |
| POST | `/auth/users` | Crear. |
| PATCH / DELETE | `/auth/users/{id}` | Editar/eliminar. |
| POST | `/auth/users/{id}/reset-password` | Reset. |
| GET | `/admin/services` | Inventario. |
| GET / POST | `/admin/services/{name}/status`, `/start`, `/stop` | Estado y control. |
| POST | `/admin/services/panic-stop` | Detención total. |
| GET / DELETE | `/admin/services/{name}/logs` | Logs. |
| SSE | `/admin/services/{name}/logs/stream` | Logs live. |
| GET / POST | `/admin/services/{name}/deps/check`, `/deps/install` | Dependencias. |
| PATCH | `/admin/services/{name}` | Auto-start. |
| GET | `/health/service/{name}`, `/admin/services/tools/health` | Health. |
| GET / POST | `/admin/mcp/health`, `/admin/mcp/{name}/start`, `/admin/mcp/{name}/stop` | MCP. |
| GET / PUT | `/admin/image-jobs/status`, `/settings` | Estado/configuración. |
| GET | `/admin/image-jobs/logs`, `/logs/stream`, `/snapshots`, `/snapshots/file` | Observabilidad. |
| POST | `/admin/image-jobs/probe`, `/clean-logs`, `/trigger/crawl-missing`, `/trigger/purge` | Operación del crawler. |
| GET / POST | `/admin/backups`, `/admin/backups/run` | Backups. |
| GET | `/admin/backups/download/{filename}`, `/admin/backups/last-auto` | Descargar/notificar. |
| GET / POST | `/admin/drive-sync/status`, `/admin/drive-sync/start` | Sync. |
| GET / WS | `/admin/drive-sync/errors-folder-id`, `/admin/drive-sync/ws` | Reproceso/progreso. |
| GET / POST | `/admin/scheduler/status`, `/start`, `/stop`, `/run-now`, `/toggle`, `/config` | Scheduler. |
| GET / POST / DELETE | `/admin/knowledge/files`, `/status`, `/tasks/{id}`, `/upload`, `/index`, `/sources/{id}` | Conocimiento. |
| GET / PATCH | `/admin/chats`, `/admin/chats/{sessionId}` | Bandeja/detalle/edición. |
| GET | `/admin/chats/stats` | Métricas. |

## 3. Errores y/u outputs

### Hallazgos que deben resolverse o conservarse conscientemente

1. **Permisos visibles inconsistentes en Admin.** `/admin` admite `colaborador` y el menú siempre muestra Usuarios y Backups. Usuarios tiene guard de ruta `admin`; Backups no tiene guard de vista, pero todos sus endpoints requieren `admin`. El nuevo sidebar debe filtrar ambos plugins por capacidad/rol y no depender del 403.
2. **El crawler mezcla permisos.** `/imagenes-productos` admite `colaborador`, pero varias lecturas y operaciones de `/admin/image-jobs/*` son `admin`; el panel captura algunos errores, aunque no degrada todas las acciones por capacidad.
3. **“Adjuntar Excel” no era realmente global (resuelto en legacy).** `AppToolbar` ahora lo muestra solo en Dashboard, donde vive el listener y el diálogo. En Vue deberá mantenerse en el shell si se decide convertirlo en acción global.
4. **Panel legacy sin ruta activa.** `AdminPanel.tsx` sigue en el repositorio e importa herramientas antiguas, pero `App.tsx` no lo monta: `/admin` usa `AdminLayout`. No debe migrarse como vista adicional; sus acciones exclusivas —por ejemplo `/debug/clear-logs`— no forman parte del inventario de endpoints consumidos por las rutas activas.
5. **Contratos legacy iAVaL.** El servicio TypeScript conserva helpers para `/iaval/preview` y `/iaval/apply`, pero ninguna vista activa los importa; `PurchaseDetail` usa `/iaval/vision`. Migrar el contrato vigente y mantener los legacy solo si aparece un consumidor confirmado.
6. **Navegación de imágenes con aliases.** Toolbar usa `/admin/imagenes`, Admin usa `/admin/imagenes-productos` y ambos terminan en `/imagenes-productos`. Vue debe publicar una ruta canónica y redirects explícitos.
7. **Descargas y streams no pasan siempre por Axios.** Catálogos, plantillas, archivos, SSE y WebSockets construyen URL directamente; el cliente Vue debe conservar cookies, base URL, CSRF donde aplique y descarga de blobs.
8. **La seguridad real está en backend.** Varias rutas de lectura son amplias, mientras botones de mutación se ocultan por rol. El mapeo Vue debe distinguir `routeRoles`, `viewRoles` y `actionCapabilities`.
9. **Enlace de log PDF roto (resuelto).** `PdfImportModal` ya no construye `/purchases/logs/by-correlation/{id}`: muestra el correlation ID inline y permite copiarlo. No se incorporó un contrato backend ficticio.

## 4. Objetivo

Usar este documento como baseline de paridad para reemplazar la SPA React por Vue 3 + Vite + Vuetify sin perder rutas, roles, formularios, acciones, estados intermedios, descargas, streams ni contratos HTTP/WS. Cada plugin Vue debe poder marcarse como `pendiente`, `parcial` o `equivalente` contra las vistas y endpoints anteriores.

## 5. Propuesta de código o pasos

### 5.1 Mapeo a Plugin-based UI (Sidebar + Main Content)

El shell objetivo debe ser único: `AppShell` con sidebar filtrado por rol/capacidad, toolbar responsive, breadcrumbs, slot de contenido principal, host de diálogos/toasts y manejo global de sesión/errores. Las vistas de dominio se registran como plugins lazy con metadatos (`id`, label, icono, ruta, roles, capabilities, orden y grupo).

| Grupo de sidebar | Plugins/vistas inyectadas en Main Content |
|---|---|
| Inicio | Dashboard/Chat. |
| Productos | Catálogo, Detalle, Stock, Faltantes, Mercado, Imágenes. |
| Operaciones | Compras, Proveedores, Clientes, Ventas. |
| Administración | Servicios, Workers, MCP, Usuarios, Drive Sync, Backups, Scheduler, Cerebro, Dashboard técnico, Chat Inbox, Diagnóstico de catálogos. |

Las rutas de detalle (`/productos/:id`, `/compras/:id`, etc.) no necesitan entrada propia en el sidebar: son vistas hijas del plugin de dominio y se renderizan en el mismo Main Content.

### 5.2 Componentes reutilizables sugeridos

**Átomos**

- `RoleBadge`, `StatusChip`, `MoneyText`, `DateTimeText`, `InlineLoader`, `EmptyState`, `ErrorState`.
- Botones semánticos `PrimaryAction`, `DangerAction`, `IconAction`; inputs numéricos monetarios y de cantidad.
- `CsrfAwareDownloadLink` para blobs/descargas con sesión.

**Moléculas**

- `EntitySearchAutocomplete` especializado como Product/Supplier/Customer selector.
- `FilterBar`, `DateRangeFilter`, `PaginationBar`, `ColumnPreferences`, `BulkSelectionBar`.
- `ConfirmDialog`, `FileDropzone`, `UploadProgress`, `LogViewer`, `LiveStreamToggle`.
- `PriceEditor`, `StockEditor`, `CategoryPicker`, `TagPicker`, `ServiceStatusCard`, `HealthCard`.

**Organismos/compuestos**

- `DataTableShell` para Productos, Stock, Compras, Proveedores, Clientes, Ventas y Chat Inbox.
- `ProductFormDialog`, `CanonicalWizard`, `ImageManager`, `MarketSourcesManager`.
- `PurchaseHeaderForm`, `PurchaseLinesEditor`, `PurchaseValidationPanel`.
- `SaleForm`, `SaleLinesEditor`, `AdditionalCostsEditor`, `AttachmentsPanel`.
- `ServiceControlPanel`, `JobMonitor`, `CatalogHistoryDialog`, `AuditTimeline`.

### 5.3 Orden de migración recomendado

1. Shell, sesión, capacidades, cliente HTTP/CSRF, errores, toasts, descargas y transporte WS/SSE.
2. Primitivas de formulario, tablas/filtros/paginación y diálogos.
3. Productos + Stock + categorías/precios, por ser la base de Mercado, Compras y Ventas.
4. Compras + Proveedores; luego Clientes + Ventas.
5. Mercado + Imágenes, que agregan jobs, polling, streams y procesamiento.
6. Plugins `/admin/*`, aplicando visibilidad por capacidad y retirando el `AdminPanel` legacy.
7. Pruebas de paridad por ruta, rol y acción; recién después, cambio del frontend servido en producción.

## 6. Criterios de aceptación

- El inventario de rutas se contrasta con `frontend/src/App.tsx` y `frontend/src/routes/paths.ts`.
- Cada vista productiva tiene propósito, inputs, acciones y endpoints asociados.
- Existe un listado consolidado de endpoints HTTP, descargas, WebSocket y SSE consumidos por la SPA.
- Los aliases y componentes legacy están identificados y no se cuentan como nuevas funcionalidades.
- El mapeo a Vue separa shell, plugins, vistas hijas, átomos, moléculas y organismos sin generar código Vue.
- La futura migración conserva roles de ruta y aplica capacidades por acción para evitar controles visibles que terminan en 403.
- Toda implementación posterior debe documentar los cambios y actualizar `Roadmap.md`, `README.md` y la documentación que haya quedado desactualizada.
