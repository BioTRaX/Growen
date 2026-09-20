<!-- NG-HEADER: Nombre de archivo: 2026-08-31-meli-sync-cloudflare-swarm-design.md -->
<!-- NG-HEADER: Ubicación: docs/superpowers/specs/2026-08-31-meli-sync-cloudflare-swarm-design.md -->
<!-- NG-HEADER: Descripción: Diseño aprobado para integración transaccional Mercado Libre, Cloudflare Tunnel y Docker Swarm. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Diseño de integración transaccional Mercado Libre

## Contexto

Growen necesita una integración transaccional de Mercado Libre separada del `market_worker` analítico. Debe manejar OAuth multicuenta, notificaciones, publicación de stock Growen → MeLi y preparar el despacho de eventos de atención al cliente, con ingreso exclusivo mediante Cloudflare Tunnel y una ruta productiva de alta disponibilidad en Docker Swarm.

## Arquitectura

Una imagen Python 3.14.6 compartida ejecuta dos servicios independientes: `meli_webhook_gateway` (FastAPI) y `meli_sync_worker` (Dramatiq, cola `meli_sync`). El gateway valida, deduplica y persiste antes de responder; el worker consulta recursos confiables en `https://api.mercadolibre.com`, refresca tokens y sincroniza stock. PostgreSQL es la fuente durable y Redis el transporte; una reconciliación periódica recupera trabajos persistidos que no llegaron al broker.

`cloudflared` usa un túnel administrado remotamente y el token se monta mediante `--token-file`. Sólo comparte una red `meli_ingress` con el gateway y una red de salida exclusiva; no puede resolver ni alcanzar API, PostgreSQL, Redis o workers. En Cloudflare se publican exclusivamente el callback OAuth y el webhook, con catch-all 404, WAF y rate limiting.

## Contratos

- `POST /integrations/meli/oauth/authorizations`: admin + sesión + CSRF; crea `state` de un uso, PKCE S256 y devuelve URL de autorización y expiración.
- `GET /integrations/meli/oauth/callback`: ruta pública; consume `state`, intercambia el código, valida `/users/me` y guarda la autorización cifrada sin devolver credenciales.
- `POST /integrations/meli/webhook`: ruta pública; limita cuerpo, valida esquema, `application_id`, tópico y ruta de recurso; persiste por `_id` y responde 200 también ante duplicados.
- `POST /integrations/meli/item-links`: admin + CSRF; vincula un producto Growen a ítem/variación MeLi y encola conciliación.
- `GET /health/live` y `GET /health/ready`: probes del gateway; el worker publica heartbeat Redis específico de la cola.

## Seguridad y datos

Los secretos estáticos se leen sólo desde `MELI_APP_ID_FILE`, `MELI_CLIENT_SECRET_FILE`, `MELI_TOKEN_ENCRYPTION_KEY_FILE` y `CLOUDFLARE_TUNNEL_TOKEN_FILE` fuera de desarrollo/tests. Access/refresh tokens y verificadores PKCE se cifran con AES-256-GCM y AAD de dominio; `state` sólo se persiste como SHA-256. El refresh usa bloqueo de fila y reemplazo atómico porque sólo el último refresh token es válido.

Las tablas son `meli_accounts`, `meli_oauth_states`, `meli_notifications`, `meli_item_links` y `meli_sync_jobs`. Se aplican constraints de estado, unicidad por seller/aplicación, deduplicación por notificación y un único vínculo activo por destino. Logs y respuestas excluyen tokens, códigos, state, cuerpos completos, prompts, mensajes y datos personales.

Los webhooks son avisos no confiables: no existe una firma general documentada por MeLi, por lo que el worker vuelve a consultar el recurso, valida host/ruta, seller y pertenencia antes de cualquier efecto. La v1 admite ítems y variaciones de inventario clásico. Si detecta stock multiorigen/User Products, falla cerrado con `unsupported_multiwarehouse`; no registra éxito falso.

## Operación y entregas

La primera entrega incorpora MeLi y Cloudflare en Compose. La segunda agrega un `docker-stack.yml` completo para Growen, con secretos externos, redes overlay, réplicas para gateway/worker/túnel, healthchecks, actualización rolling y rollback. La activación externa del túnel y DNS se realiza con un script idempotente y modo `-WhatIf`; requiere autorización operativa y nunca imprime el token.

## Pruebas y aceptación

Se cubren configuración fail-fast, cifrado/rotación, state/PKCE, callback, validación y deduplicación de webhook, recuperación del outbox, refresh concurrente, 401/429/5xx, stock simple/variación, rechazo multiorigen, aislamiento Compose/Swarm, healthchecks y smoke con MeLi/Cloudflare simulados. Las migraciones se prueban en cadena limpia e incremental y la documentación viva se actualiza.
