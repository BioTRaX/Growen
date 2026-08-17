<!-- NG-HEADER: Nombre de archivo: roles-endpoints.md -->
<!-- NG-HEADER: Ubicación: docs/roles-endpoints.md -->
<!-- NG-HEADER: Descripción: Roles y endpoints expuestos por la API. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Roles por endpoint

## Rollout Chat (2026-08-16)

| Método/ruta | Roles | Requisitos |
|---|---|---|
| `GET /admin/chat-rollout` | admin | sesión |
| `POST /admin/chat-rollout/pause\|resume\|rollback` | admin | sesión + CSRF |

No existe endpoint para forzar avance. Admin en Telegram continúa limitado a colaborador y sólo lectura cuando la fase `admin_capped` esté activa.

## Conocimiento canónico (2026-07-26)

| Método/ruta | Roles | Requisitos |
|---|---|---|
| `/canonical-products/{id}/knowledge*` | colaborador, admin | lectura staff; mutaciones + CSRF |
| `/knowledge-capabilities*` y override de confianza | admin | admin + CSRF |

## Chat e identidades externas (2026-07-22)

| Método/ruta | Roles | Requisitos |
|---|---|---|
| `POST /auth/external-identities/telegram/link-request` | usuario autenticado | CSRF, contraseña vigente, código privado de un uso |
| `GET /auth/me/external-identities` | usuario autenticado | identificadores enmascarados |
| `DELETE /auth/me/external-identities/{id}` | propietario | CSRF; revocación inmediata |
| `GET /admin/external-identities` | admin | identificadores enmascarados |
| `POST /admin/external-identities/{id}/approve` | segundo admin | CSRF; no permite autoaprobación |
| `POST /admin/external-identities/{id}/revoke` | admin | CSRF y auditoría |
| `POST /chat` / `WS /ws` | `guest`, cliente, proveedor, colaborador, admin | rol vigente por sesión; política por capacidades |
| Telegram polling | público | `guest` por defecto, techo colaborador, sólo lectura |
| `GET /admin/chats/metrics` | colaborador, admin | agregados sin contenido ni IDs en claro |

El registro central es la autoridad de tools. Invitados/clientes reciben perfil público; proveedor conserva alcance propio; colaborador recibe datos operativos; admin sólo conserva capacidades administrativas completas en web.

Estado UI 2026-08-15: Vue permite generar/revocar el vínculo propio y a un
segundo admin aprobar/revocar identidades, siempre con valores enmascarados. Los
flags continúan apagados. No habilitar `TELEGRAM_ROLE_LINKING_ENABLED` hasta
completar el smoke con sesión, reautenticación y CSRF reales para cada rol.

## Productos, taxonomía y tags (2026-07-18)

| Método/ruta | Lectura | Mutación |
|---|---|---|
| `/categories`, `/categories/search` | cliente, proveedor, colaborador, admin | `POST /categories`: colaborador, admin + CSRF |
| `/tags` | cliente, proveedor, colaborador, admin | `POST /tags`: colaborador, admin + CSRF |
| `/tags/products/{id}/tags*`, `/tags/products/bulk-tags` | — | colaborador, admin + CSRF |
| `/canonical-products/batch-job` | estado: colaborador, admin | alta: colaborador, admin + CSRF |

Este documento enumera cada endpoint de la API con el método HTTP y los roles requeridos.
Además, se planifica un chatbot corporativo diferenciado por roles; los endpoints se detallan en la sección de próximos hitos para asegurar controles de acceso y auditoría.
Las rutas sin un rol específico son accesibles para cualquier usuario, incluido `guest`.

## Operaciones administrativas Vue (2026-07-18)

| Dominio | Lecturas | Mutaciones |
|---|---|---|
| Drive Sync `/admin/drive-sync/*` | admin; WebSocket con sesión admin | admin + CSRF |
| Scheduler `/admin/scheduler/*` | admin | admin + CSRF |
| Conocimiento `/admin/knowledge/*` y búsqueda RAG HTTP | admin | admin + CSRF |
| Crawler `/admin/image-jobs/*` | admin | admin + CSRF |
| Revisión/procesamiento `/products/*/images*` | colaborador, admin | colaborador, admin + CSRF |
| Catálogos `/catalogs/diagnostics/*` | colaborador, admin | desbloqueo/eliminación: admin + CSRF |
| Chat Inbox `/admin/chats*`, `/admin/chat-quality/metrics` | colaborador, admin | revisión/feedback: colaborador, admin + CSRF |
| Prompts `/admin/chat-quality/prompts*` | admin | admin + CSRF |

| Método | Ruta | Roles requeridos |
|--------|------|------------------|
| GET | /health | Ninguno |
| GET | /health/ai | Ninguno |
| GET | /healthz/db | Ninguno |
| POST | /auth/login | Ninguno |
| POST | /auth/guest | Ninguno |
| POST | /auth/logout | Ninguno (requiere CSRF) |
| GET | /auth/me | Ninguno |
| GET | /auth/users | admin |
| POST | /auth/users | admin (requiere CSRF) |
| PATCH | /auth/users/{user_id} | admin (requiere CSRF) |
| POST | /auth/users/{user_id}/reset-password | admin (requiere CSRF) |
| GET | /suppliers | cliente, proveedor, colaborador, admin |
| GET | /suppliers/{supplier_id}/files | cliente, proveedor, colaborador, admin |
| POST | /suppliers | admin (requiere CSRF) |
| PATCH | /suppliers/{supplier_id} | admin (requiere CSRF) |
| DELETE | /suppliers | admin (requiere CSRF) |
| GET | /categories | cliente, proveedor, colaborador, admin |
| GET | /categories/search | cliente, proveedor, colaborador, admin |
| POST | /categories/generate-from-supplier-file | admin (requiere CSRF) |
| GET | /products | cliente, proveedor, colaborador, admin |
| POST | /products | colaborador, admin (requiere CSRF) |
| GET | /products/{product_id} | guest, cliente, proveedor, colaborador, admin |
| GET | /products/{product_id}/variants | cliente, proveedor, colaborador, admin |
| POST | /canonical-products/batch-job | colaborador, admin (requiere CSRF) |
| POST | /canonical-products/sku-preview | colaborador, admin (requiere CSRF) |
| GET | /canonical-products/batch-jobs/{job_id} | colaborador propietario, admin |
| PATCH | /products/{product_id} | colaborador, admin (requiere CSRF) |
| POST | /products/{product_id}/enrich | colaborador, admin (requiere CSRF) |
| DELETE | /products/{product_id}/enrichment | colaborador, admin (requiere CSRF) |
| POST | /products/enrich-multiple | colaborador, admin (requiere CSRF) |
| PATCH | /products/{product_id}/stock | colaborador, admin (requiere CSRF) |
| GET | /products/{product_id}/audit-logs | colaborador, admin |
| GET | /price-history | cliente, proveedor, colaborador, admin |
| POST | /canonical-products | admin (requiere CSRF) |
| GET | /canonical-products | Ninguno |
| GET | /canonical-products/{canonical_id} | Ninguno |
| PATCH | /canonical-products/{canonical_id} | colaborador, admin (requiere CSRF; edición canónica y SKU único) |
| GET | /canonical-products/{canonical_id}/offers | Ninguno |
| GET | /equivalences | Ninguno |
| POST | /equivalences | colaborador, admin (requiere CSRF) |
| DELETE | /equivalences/{equivalence_id} | colaborador, admin (requiere CSRF) |
| POST | /catalog/products | Ninguno (requiere CSRF) |
| DELETE | /catalog/products | colaborador, admin (requiere CSRF) |
| GET | /suppliers/search | cliente, proveedor, colaborador, admin |
| PUT | /variants/{variant_id}/sku | colaborador, admin (requiere CSRF) |
| POST | /supplier-products/link | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/products/{product_id}/sale-price | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/supplier-items/{supplier_item_id}/buy-price | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/supplier-items/{supplier_item_id}/sale-price | colaborador, admin (requiere CSRF) |
| POST | /products-ex/products/bulk-sale-price | colaborador, admin (requiere CSRF) |
| GET | /products-ex/products/{product_id}/offerings | cliente, proveedor, colaborador, admin |
| GET | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin |
| PUT | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin (requiere CSRF) |
| GET | /stock/export.xlsx | cliente, proveedor, colaborador, admin |
| GET | /stock/export.csv | cliente, proveedor, colaborador, admin |
| GET | /stock/export.pdf | cliente, proveedor, colaborador, admin |
| GET | /stock/export-tiendanegocio.xlsx | colaborador, admin |
| GET | /stock/shortages | colaborador, admin |
| GET | /stock/shortages/stats | colaborador, admin |
| POST | /stock/shortages | colaborador, admin (requiere CSRF) |
| GET | /catalog/next-seq | colaborador, admin |
| GET | /suppliers/price-list/template | cliente, proveedor, colaborador, admin |
| GET | /suppliers/{supplier_id}/price-list/template | cliente, proveedor, colaborador, admin |
| POST | /suppliers/{supplier_id}/price-list/upload | proveedor, colaborador, admin (requiere CSRF) |
| GET | /imports/{job_id}/preview | cliente, proveedor, colaborador, admin |
| GET | /imports/{job_id} | cliente, proveedor, colaborador, admin |
| POST | /imports/{job_id}/commit | proveedor, colaborador, admin (requiere CSRF) |
| GET | /actions/ | Ninguno |
| POST | /chat | Ninguno |
| WebSocket | /ws | Ninguno |
| GET | /healthz* | admin |
| GET | /debug/db* | admin |
| GET | /debug/config* | admin |
| GET | /debug/imports/parsers* | admin |
| POST | /bug-report | Ninguno (sin CSRF; solo registra log) |
| POST | /purchases/{purchase_id}/rollback | colaborador, admin (requiere CSRF) |
| GET | /admin/services/metrics/bug-reports | admin |
| GET | /admin/mcp/health | admin |
| POST | /admin/mcp/{name}/start | admin |
| POST | /admin/mcp/{name}/stop | admin |

Las rutas marcadas con * solo están disponibles cuando `ENV` es distinto de `production`.

El canal `/ws` envía un ping JSON cada 30 s y se cierra tras 60 s sin recibir mensajes.

## Visibilidad en el frontend (UI)

Además de los permisos del backend, la interfaz limita qué opciones se muestran según el rol:

- Invitado: solo ChatBot. No se muestran Proveedores, Clientes, Ventas, Compras, Admin, ni acciones de subida.
- Cliente/Proveedor: pueden ver Productos y Stock y exportar XLSX/CSV/PDF. No ven mutaciones, TiendaNegocio, Faltantes, Proveedores, Clientes, Ventas, Compras ni Admin.
- Colaborador: ve operaciones de dominio y Workers, pero no Usuarios, Backups, MCP ni acciones con capacidades administrativas.
- Admin: ve todas las secciones y herramientas habilitadas por el manifiesto.

En Vue, `/admin/servicios` y `/admin/servicios/workers` requieren `services.control`; `/admin/servicios/mcp-tools` es solo `admin`. La instalación de dependencias se oculta sin `services.dependencies.install`, aunque FastAPI continúa siendo la autoridad final.

Nota: Estas reglas de visibilidad no cambian la seguridad de los endpoints (que sigue controlada en el backend); simplemente reducen la superficie visible para cada rol.

## Parámetros y comportamientos recientes

- GET `/products` ahora acepta `type` para filtrar el listado:
	- `type=all` (default), `type=canonical` (sólo con producto canónico vinculado) o `type=supplier` (sin canónico).
	- El backend normaliza el título (`name`) y el precio de venta (`precio_venta`) priorizando los datos del canónico cuando existen; si no, usa los del proveedor.

- GET `/catalog/next-seq?category_id=…` devuelve una estimación no reservante para clientes heredados bajo la regla `XXX_####_YYY`.
	- Vue usa `POST /canonical-products/sku-preview` para lotes. Ninguno de los dos endpoints reserva números; la generación definitiva se hace en backend dentro de la transacción.

## Próximos endpoints (planificados)

Estos endpoints se agregarán en próximos hitos y pueden no estar disponibles aún en el entorno actual. Se documentan para alinear UI/roadmap.

| Método | Ruta | Roles requeridos | Notas |
|--------|------|------------------|-------|
| POST | /chatbot/query | colaborador, admin | Enrutador con respuestas filtradas por rol y auditoría obligatoria.
| POST | /chatbot/query/admin-context | admin | Variante que habilita contexto extendido (repositorio completo y métricas internas).
| GET | /chatbot/repo/search?q= | admin | Búsqueda de texto sobre el repositorio (read-only).
| GET | /chatbot/repo/file?path= | admin | Descarga controlada de archivos; aplica sanitización de path.
| POST | /chatbot/pr-suggestion | admin | Permite subir sugerencias bajo `PR/` con validación de ruta y auditoría.
| GET | /chatbot/audit/logs | admin | Consulta de auditoría con filtros por usuario, fechas y recursos.

## Clientes y Ventas Fase 4

| Método | Ruta | Roles | Seguridad/uso |
|---|---|---|---|
| GET | `/customers`, `/customers/{id}`, `/customers/{id}/sales`, `/customers/{id}/account` | colaborador, admin | Lectura paginada y enriquecida. |
| POST/PATCH/DELETE | `/customers`, `/customers/{id}`, `/customers/{id}/reactivate` | colaborador, admin | Sesión, rol, CSRF y auditoría. |
| POST | `/customers/{id}/account/adjustments` | admin | CSRF y motivo obligatorio. |
| GET | `/sales`, `/sales/{id}`, `/sales/reports/*` | colaborador, admin | Lectura enriquecida y reportes. |
| POST | `/sales/quote` | colaborador, admin | Cálculo sin persistencia; CSRF. |
| POST | `/sales` | colaborador, admin | CSRF, rate limit e `Idempotency-Key`. |
| POST/PATCH/DELETE | `/sales/{id}/*` | colaborador, admin | CSRF; transiciones restringidas por estado. |

Los permisos de acción retornados por el detalle son la fuente para habilitar controles Vue; el backend siempre vuelve a autorizar.

## Tools MCP (estado actual)

Las tools expuestas a modelos (OpenAI) vía tool-calling se documentan para trazabilidad de roles:

| Tool | Descripción | Roles permitidos |
|------|-------------|------------------|
| get_product_info | Perfil público: nombre, precio de venta y disponibilidad aproximada; SKU/stock exacto sólo se incluyen para perfiles operativos autorizados. | guest, cliente, proveedor, colaborador, admin |
| get_product_full_info | Retorna información operativa con SKU y stock exacto. En Telegram queda limitada por el rol efectivo y sólo lectura. | colaborador, admin web; colaborador efectivo en Telegram |

Invocación estándar: MCP Streamable HTTP en `/mcp`, descubrimiento con `tools/list` y ejecución con `tools/call`.

Notas:
- El rol se obtiene del JWT Bearer y no se expone como argumento al modelo.
- Growen filtra el catálogo y el servidor vuelve a validar el rol.
- La auditoría registra tool, sujeto, estado y latencia sin tokens ni parámetros sensibles.

