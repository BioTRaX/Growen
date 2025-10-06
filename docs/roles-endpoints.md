<!-- NG-HEADER: Nombre de archivo: roles-endpoints.md -->
<!-- NG-HEADER: Ubicación: docs/roles-endpoints.md -->
<!-- NG-HEADER: Descripción: Roles y endpoints expuestos por la API. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Roles por endpoint

Este documento enumera cada endpoint de la API con el método HTTP y los roles requeridos.
Además, se planifica un chatbot corporativo diferenciado por roles; los endpoints se detallan en la sección de próximos hitos para asegurar controles de acceso y auditoría.
Las rutas sin un rol específico son accesibles para cualquier usuario, incluido `guest`.

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
| GET | /products/{product_id} | cliente, proveedor, colaborador, admin |
| GET | /products/{product_id}/variants | cliente, proveedor, colaborador, admin |
| PATCH | /products/{product_id} | colaborador, admin (requiere CSRF) |
| PATCH | /products/{product_id}/stock | colaborador, admin (requiere CSRF) |
| GET | /products/{product_id}/audit-logs | colaborador, admin |
| GET | /price-history | cliente, proveedor, colaborador, admin |
| POST | /canonical-products | admin (requiere CSRF) |
| GET | /canonical-products | Ninguno |
| GET | /canonical-products/{canonical_id} | Ninguno |
| PATCH | /canonical-products/{canonical_id} | admin (requiere CSRF) |
| GET | /canonical-products/{canonical_id}/offers | Ninguno |
| GET | /equivalences | Ninguno |
| POST | /equivalences | colaborador, admin (requiere CSRF) |
| DELETE | /equivalences/{equivalence_id} | colaborador, admin (requiere CSRF) |
| POST | /catalog/products | Ninguno (requiere CSRF) |
| DELETE | /catalog/products | Ninguno (requiere CSRF) |
| GET | /suppliers/search | cliente, proveedor, colaborador, admin |
| PUT | /variants/{variant_id}/sku | colaborador, admin (requiere CSRF) |
| POST | /supplier-products/link | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/products/{product_id}/sale-price | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/supplier-items/{supplier_item_id}/buy-price | colaborador, admin (requiere CSRF) |
| POST | /products-ex/products/bulk-sale-price | colaborador, admin (requiere CSRF) |
| GET | /products-ex/products/{product_id}/offerings | cliente, proveedor, colaborador, admin |
| GET | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin |
| PUT | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin (requiere CSRF) |
| GET | /stock/export.xlsx | cliente, proveedor, colaborador, admin |
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
| POST | /webhooks/tiendanube/ | Ninguno |
| GET | /healthz* | admin |
| GET | /debug/db* | admin |
| GET | /debug/config* | admin |
| GET | /debug/imports/parsers* | admin |
| POST | /bug-report | Ninguno (sin CSRF; solo registra log) |
| POST | /purchases/{purchase_id}/rollback | colaborador, admin (requiere CSRF) |
| GET | /admin/services/metrics/bug-reports | admin |

Las rutas marcadas con * solo están disponibles cuando `ENV` es distinto de `production`.

El canal `/ws` envía un ping JSON cada 30 s y se cierra tras 60 s sin recibir mensajes.

## Visibilidad en el frontend (UI)

Además de los permisos del backend, la interfaz limita qué opciones se muestran según el rol:

- Invitado: solo ChatBot. No se muestran Proveedores, Clientes, Ventas, Compras, Admin, ni acciones de subida.
- Cliente/Proveedor: pueden ver Productos y Stock. No ven Proveedores, Clientes, Ventas, Compras ni Admin.
- Colaborador/Admin: ven todas las secciones y herramientas (incluye Proveedores, Clientes, Ventas, Compras, Admin, Imágenes productos, etc.).

Nota: Estas reglas de visibilidad no cambian la seguridad de los endpoints (que sigue controlada en el backend); simplemente reducen la superficie visible para cada rol.

## Parámetros y comportamientos recientes

- GET `/products` ahora acepta `type` para filtrar el listado:
	- `type=all` (default), `type=canonical` (sólo con producto canónico vinculado) o `type=supplier` (sin canónico).
	- El backend normaliza el título (`name`) y el precio de venta (`precio_venta`) priorizando los datos del canónico cuando existen; si no, usa los del proveedor.

- GET `/catalog/next-seq?category_id=…` devuelve la próxima secuencia por categoría para proponer SKUs canónicos bajo la regla `XXX_####_YYY`.
	- Uso: la UI lo consume para vista previa; la generación/validación real del SKU se hace en backend.

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

## Tools MCP (estado actual)

Las tools expuestas a modelos (OpenAI) vía tool-calling se documentan para trazabilidad de roles:

| Tool | Descripción | Roles permitidos |
|------|-------------|------------------|
| get_product_info | Retorna info básica de producto (sku, name, sale_price, stock). | guest, cliente, proveedor, colaborador, admin |
| get_product_full_info | Retorna info extendida (MVP: igual a básica; se ampliará). | colaborador, admin |

Invocación estándar desde el modelo: `POST /invoke_tool` en `mcp_products` con cuerpo `{ "tool_name": ..., "parameters": {"sku": "...", "user_role": "..." } }`.

Notas:
- `user_role` validado en el microservicio además de la selección dinámica de tools.
- Se añadirá auditoría y token firmado en próximos hitos (ver Roadmap).

