# Roles por endpoint

Este documento enumera cada endpoint de la API con el método HTTP y los roles requeridos.
Las rutas sin un rol específico son accesibles para cualquier usuario, incluido `guest`.

| Método | Ruta | Roles requeridos |
|--------|------|------------------|
| GET | /health | Ninguno |
| GET | /health/ai | Ninguno |
| POST | /auth/login | Ninguno |
| POST | /auth/guest | Ninguno |
| POST | /auth/logout | Ninguno (requiere CSRF) |
| GET | /auth/me | Ninguno |
| GET | /auth/users | admin |
| POST | /auth/users | admin (requiere CSRF) |
| PATCH | /auth/users/{user_id} | admin (requiere CSRF) |
| POST | /auth/users/{user_id}/reset-password | admin (requiere CSRF) |
| GET | /suppliers | Ninguno |
| GET | /suppliers/{supplier_id}/files | Ninguno |
| POST | /suppliers | admin (requiere CSRF) |
| PATCH | /suppliers/{supplier_id} | admin (requiere CSRF) |
| GET | /categories | Ninguno |
| GET | /categories/search | Ninguno |
| POST | /categories/generate-from-supplier-file | admin (requiere CSRF) |
| GET | /products | cliente, proveedor, colaborador, admin |
| PATCH | /products/{product_id}/stock | manager, admin (requiere CSRF) |
| GET | /price-history | cliente, proveedor, colaborador, admin |
| POST | /canonical-products | admin (requiere CSRF) |
| GET | /canonical-products | Ninguno |
| GET | /canonical-products/{canonical_id} | Ninguno |
| PATCH | /canonical-products/{canonical_id} | admin (requiere CSRF) |
| GET | /canonical-products/{canonical_id}/offers | Ninguno |
| GET | /equivalences | Ninguno |
| POST | /equivalences | manager, admin (requiere CSRF) |
| DELETE | /equivalences/{equivalence_id} | manager, admin (requiere CSRF) |
| GET | /suppliers/price-list/template | Ninguno |
| GET | /suppliers/{supplier_id}/price-list/template | Ninguno |
| POST | /suppliers/{supplier_id}/price-list/upload | proveedor, colaborador, admin (requiere CSRF) |
| GET | /imports/{job_id}/preview | Ninguno |
| GET | /imports/{job_id} | Ninguno |
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
