<!-- NG-HEADER: Nombre de archivo: MELI_INTEGRATION.md -->
<!-- NG-HEADER: Ubicación: docs/MELI_INTEGRATION.md -->
<!-- NG-HEADER: Descripción: Contrato técnico y operación segura de la integración Mercado Libre. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Integración Mercado Libre

## Arquitectura

La integración transaccional no comparte procesos ni cola con Mercado analítico. `meli_webhook_gateway` expone únicamente `GET /health/*`, `GET /integrations/meli/oauth/callback` y `POST /integrations/meli/webhook`. Persiste el sobre mínimo y responde rápido; `meli_sync_worker` consume exclusivamente `meli_sync`, renueva tokens y consulta la API oficial antes de actuar. El webhook se considera una notificación no confiable, nunca la fuente del contenido de negocio.

`meli_cloudflared` sólo participa de `meli_ingress` y `cloudflare_egress`. No comparte `backend`, por lo que no puede resolver ni alcanzar API, PostgreSQL, Redis o MCP. La configuración remota termina en `http_status:404` y sólo enruta callback y webhook al gateway.

## Secretos obligatorios

Crear fuera del repositorio archivos de una sola línea:

- `meli_app_id`: App ID de la aplicación.
- `meli_client_secret`: Secret Key.
- `meli_token_encryption_key`: 32 bytes aleatorios codificados en base64 URL-safe o 64 caracteres hexadecimales.
- `cloudflare_meli_tunnel_token`: token de ejecución del túnel remoto.

Compose los monta desde `GROWEN_SECRET_DIR` y usa `*_FILE`. Swarm consume secretos externos homónimos. El servicio falla al iniciar si falta una credencial, la URI de callback no es HTTPS o la configuración es ambigua. Los access/refresh tokens y el verificador PKCE se guardan con AES-256-GCM y AAD por propósito/cuenta; nunca se registran.

## Desarrollo con Compose

1. Copiar únicamente valores no sensibles de `.env.example` y definir `MELI_REDIRECT_URI` con la URL HTTPS exacta registrada en MeLi.
2. Aplicar `alembic upgrade head`.
3. Levantar la integración: `docker compose --profile meli up -d --build meli_webhook_gateway meli_sync_worker meli_cloudflared`.
4. Validar la salud interna con `docker compose --profile meli ps`: gateway y worker deben figurar `healthy`. Desde Internet, `GET https://<host>/health/live` debe responder 404 porque Cloudflare publica exclusivamente callback y webhook; una llamada incompleta al callback debe alcanzar el gateway y devolver un error de validación 4xx.

No se publica ningún puerto del gateway al host. Para depuración local sin túnel puede ejecutarse Uvicorn en loopback, nunca en una interfaz pública.

## Activación inicial y DNS

El archivo `cloudflare_meli_tunnel_token` contiene únicamente el token del conector, no el Tunnel ID ni el comando Docker, y no lleva extensión `.txt`. Si todavía faltan las credenciales MeLi, puede conectarse sólo el túnel con `docker compose --profile meli up -d --no-deps meli_cloudflared`; esto no inicia el gateway ni valida OAuth.

En Cloudflare, cada ruta Published application requiere la URL completa `http://meli_webhook_gateway:8080`. Restringir los paths a `^/integrations/meli/oauth/callback$` y `^/integrations/meli/webhook$`. Las URLs registradas en MeLi no incluyen los delimitadores `^` y `$`.

El CNAME del hostname hacia `<tunnel-id>.cfargotunnel.com` debe quedar **Proxied** (nube naranja). Con **DNS only**, puede resolverse directamente a una IPv6 privada del túnel y HTTPS no llegará al gateway, aunque el conector figure Healthy. Verificar también la activación de la zona y consultar los DNS autoritativos para distinguir configuración de caché.

Verificación local del 2026-09-04: gateway y worker saludables, `/health/ready` interno con HTTP 200, heartbeat correcto y revisión `20260831_meli_sync_v1` aplicada. Tras activar el proxy del CNAME, el DNS autoritativo devuelve direcciones públicas de Cloudflare. La nueva prueba HTTPS pública obtuvo callback sin parámetros HTTP 422, webhook con GET HTTP 405 y `/health/live` HTTP 404: las rutas alcanzan el gateway y health permanece bloqueado. Cierre del 2026-09-05: primera cuenta activa, ambos tokens cifrados persistidos, state consumido y permisos de 505 caracteres guardados tras migrar scopes a TEXT. Siguen pendientes una notificación POST real, sincronización de stock y renovación real; no se declara validación integral del worker.

## OAuth y cuentas múltiples

Growen solicita explícitamente `scope=read write offline_access` para lectura, sincronización de stock y renovación desatendida. La aplicación en DevCenter debe habilitar Acceso Offline y el vendedor debe aprobarlo. El incidente inicial devolvía `missing_refresh_token`, no un estado vencido: ante esa respuesta el callback ahora indica que falta acceso sin conexión y exige una autorización nueva. No se registra como activa una cuenta sin token de renovación. Se mantiene el TTL de 600 segundos; aumentar su duración no resuelve un permiso faltante.

En la activación asistida del 2026-09-04, sin API local escuchando, el operador inició un enlace mediante la función existente `create_authorization` dentro del gateway Docker. Se conservó `requested_by_user_id=None` para no atribuirlo a un usuario autenticado inexistente; no se modificaron permisos ni se expuso un endpoint adicional. El enlace dura 10 minutos con la configuración por defecto y exige aprobación del vendedor en MeLi. Esta operación administrativa no valida el endpoint de inicio con sesión y CSRF, cuyo smoke sigue pendiente. No guardar enlaces OAuth, códigos ni verificadores en documentación o logs.

Un administrador autenticado y con CSRF válido inicia el flujo mediante `POST /integrations/meli/oauth/authorizations`. Se genera `state` de un uso y PKCE S256; la base conserva sólo el hash de `state` y el verificador cifrado. El callback exige el mismo `redirect_uri`, consume el estado una sola vez, consulta `/users/me` y asocia los tokens al seller validado. Cada renovación reemplaza atómicamente access y refresh token, porque el refresh anterior deja de ser vigente.

## Webhooks

El endpoint acepta sólo JSON hasta `MELI_WEBHOOK_MAX_BYTES`, valida App ID, topic y un path relativo permitido. `_id` es la clave idempotente. Se devuelve HTTP 200 para una notificación válida, incluso duplicada, y el camino de recepción está diseñado para completar dentro del límite de 500 ms exigido por MeLi: el procesamiento queda en el outbox durable y la cola. El worker vuelve a pedir el recurso con Bearer token y verifica ownership antes de persistir su resultado. Preguntas y mensajes quedan marcados para despacho IA posterior, pero esta entrega no genera ni envía respuestas automáticas.

## Stock

La dirección inicial es Growen → MeLi. Un administrador crea el vínculo mediante `POST /integrations/meli/item-links`. El job toma `Product.stock`, exige un entero no negativo, comprueba que el ítem pertenezca al seller y actualiza `/items/{id}`. Variaciones usan su ID explícito. La presencia de `user_product_id`, `inventory_id`, ubicaciones o warehouse produce `unsupported_multiwarehouse`: no se declara éxito ni se intenta modificar inventario User Products/multiorigen.

## Cloudflare reproducible

`scripts/provision-meli-tunnel.ps1` usa un API token leído desde archivo, crea o reutiliza un túnel remoto, instala las dos reglas ingress, actualiza el CNAME proxied y guarda el token de ejecución fuera del repositorio. Probar primero con `-WhatIf`. El token API debe limitarse a escritura de Cloudflare Tunnel/Cloudflare One Connector para la cuenta y edición DNS para la zona, de acuerdo con los nombres disponibles en el panel actual. `infra/cloudflare/meli-tunnel.example.json` documenta la forma final sin credenciales. El contenedor usa `--token-file`, soportado por `cloudflared` para túneles administrados remotamente, y no necesita puertos entrantes.

## Referencias oficiales verificadas

- [Mercado Libre: autenticación y autorización](https://developers.mercadolibre.com.ar/es_ar/autenticacion-y-autorizacion/autenticacion-y-autorizacion): Authorization Code, `redirect_uri`, `state`, PKCE y Bearer token.
- [Mercado Libre: notificaciones de productos](https://developers.mercadolibre.com.ar/es_ar/preguntas-y-respuestas/productos-recibe-notificaciones): respuesta HTTP 200 dentro de 500 ms y consulta posterior del recurso.
- [Mercado Libre: stock multiwarehouse](https://developers.mercadolibre.com.ar/es_ar/motivos-para-comunicarse/stock-multiwarehouse): inventario por User Products/ubicación, separado del stock clásico de `/items`.
- [Cloudflare: tokens de Tunnel](https://developers.cloudflare.com/tunnel/advanced/tunnel-tokens/) y [parámetros de ejecución](https://developers.cloudflare.com/tunnel/advanced/run-parameters/): túnel remoto y lectura segura del token desde archivo.
- [Cloudflare: reglas ingress](https://developers.cloudflare.com/tunnel/advanced/local-management/configuration-file/): matching por hostname/path y regla catch-all final.

## Diagnóstico seguro

Si el callback falla con `StringDataRightTruncation` sobre `scopes`, aplicar `20260905_meli_scopes_text` y usar el modelo actualizado: los permisos funcionales pueden superar 500 caracteres. Después se requiere una autorización nueva; no reutilizar el código que ya se intercambió antes del fallo de persistencia.

El callback registra `meli_oauth_callback_failed` con una razón de lista cerrada (estado inválido/usado/vencido, seller diferente, campo esperado ausente o respuesta inválida). No incluye códigos OAuth, tokens, verificadores ni argumentos arbitrarios de excepciones. El mensaje público genérico no permite concluir por sí solo que el enlace venció: contrastar expiración y consumo del estado con esa razón antes de reautorizar.

- `docker compose --profile meli ps`: estado de los tres servicios.
- `docker compose --profile meli logs meli_cloudflared`: conexión del túnel; no pegar tokens en comandos.
- `docker compose --profile meli logs meli_sync_worker`: códigos de error, nunca payloads completos ni credenciales.
- Estados terminales y `last_error_code` se consultan en `meli_sync_jobs`, `meli_notifications` y `meli_item_links`.

Rotar inmediatamente una credencial si se expone. La clave de cifrado no puede reemplazarse sin un procedimiento de recifrado de tokens; ante pérdida, revocar/reautorizar todas las cuentas.
