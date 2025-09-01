<!-- NG-HEADER: Nombre de archivo: roles-endpoints.md -->
<!-- NG-HEADER: Ubicación: docs/roles-endpoints.md -->
<!-- NG-HEADER: Descripción: Pendiente de descripción -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Roles por endpoint

Este documento enumera cada endpoint de la API con el método HTTP y los roles requeridos.
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
| GET | /categories | cliente, proveedor, colaborador, admin |
| GET | /categories/search | cliente, proveedor, colaborador, admin |
| POST | /categories/generate-from-supplier-file | admin (requiere CSRF) |
| GET | /products | cliente, proveedor, colaborador, admin |
| PATCH | /products/{product_id}/stock | colaborador, admin (requiere CSRF) |
| GET | /price-history | cliente, proveedor, colaborador, admin |
| POST | /canonical-products | admin (requiere CSRF) |
| GET | /canonical-products | Ninguno |
| GET | /canonical-products/{canonical_id} | Ninguno |
| PATCH | /canonical-products/{canonical_id} | admin (requiere CSRF) |
| GET | /canonical-products/{canonical_id}/offers | Ninguno |
| GET | /equivalences | Ninguno |
| POST | /equivalences | colaborador, admin (requiere CSRF) |
| DELETE | /equivalences/{equivalence_id} | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/products/{product_id}/sale-price | colaborador, admin (requiere CSRF) |
| PATCH | /products-ex/supplier-items/{supplier_item_id}/buy-price | colaborador, admin (requiere CSRF) |
| POST | /products-ex/products/bulk-sale-price | colaborador, admin (requiere CSRF) |
| GET | /products-ex/products/{product_id}/offerings | cliente, proveedor, colaborador, admin |
| GET | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin |
| PUT | /products-ex/users/me/preferences/products-table | cliente, proveedor, colaborador, admin (requiere CSRF) |
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

Las rutas marcadas con * solo están disponibles cuando `ENV` es distinto de `production`.

El canal `/ws` envía un ping JSON cada 30 s y se cierra tras 60 s sin recibir mensajes.
