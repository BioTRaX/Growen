<!-- NG-HEADER: Nombre de archivo: CHAT.md -->
<!-- NG-HEADER: Ubicacion: docs/CHAT.md -->
<!-- NG-HEADER: Descripcion: Referencia rapida de intents del chatbot Growen -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Chatbot Growen

## Intents soportados

### Consulta de productos (`product_answer`)
- Preguntas del tipo `cuanto sale <producto>`, `tenes <producto> en stock?` o `/stock <sku>` activan la resolucion controlada.
- Se aceptan SKUs canonicos, internos y de proveedor. El motor prioriza coincidencias exactas y ordena por disponibilidad (`ok`, `low`, `out`).
- La respuesta incluye `type=product_answer`, `intent` (price|stock|mixed), `took_ms`, `results` y `needs_clarification` (true cuando es necesario refinar).
- Para roles administradores se adjunta `data.metrics` con contadores agregados y latencias.
- Cada entrada provee nombre, precio formateado, proveedor, SKU, variantes y un badge de stock (`En stock`, `Pocas unidades`, `Sin stock`).

### Mensajes libres
- Si el texto no coincide con el intent controlado, el mensaje se deriva al `AIRouter` manteniendo la personalidad configurada.
- El WebSocket expone la misma estructura (`type`, `intent`, `data`, `took_ms`).

## Memoria y follow-ups
- Cuando la consulta devuelve multiples coincidencias, se guarda un estado efimero (`services/chat/memory.py`) por `session_id`/IP.
- Mensajes breves como `si`, `dale` o `stock` confirman la lista anterior sin repetir la query original.
- Si el usuario responde con algo ambiguo, el bot pide aclaracion (`clarify_prompt`) en lugar de adivinar.

## Logs y metricas
- `log_product_lookup` persiste cada consulta en `AuditLog` (`action=chat.product_lookup`) incluyendo query, filtros detectados y resultados.
- Se emite un log estructurado `chat.lookup` con `correlation_id`, `intent`, `status`, cantidad de matches y latencia (`logger.info`).
- El modulo mantiene contadores en memoria (`intent_counts`, `status_counts`, `matches_counts`) y un buffer de latencias (media y p95). El snapshot se expone en `data.metrics` solo para perfiles administrativos.
- El middleware HTTP (`services/api.py`) propaga `X-Correlation-Id` a `request.state.correlation_id` para que endpoints y logs compartan el mismo identificador.

## Checklist de tono y estilo
- Mantener tono cordial y profesional: descartado cualquier comentario que denigre a clientes o colaboradores.
- Evitar chistes internos cuando el usuario este frente a una duda real; priorizar la resolucion.
- Confirmar cuando se requiera informacion extra (`clarify_prompt`) antes de emitir datos dudosos.
- No exponer precios restringidos segun el rol autenticado (revisar `ALLOWED_PRODUCT_INTENT_ROLES`).

## Buenas practicas
- Al agregar nuevos campos al payload actualizar `serialize_result`, `ProductLookupOut`, `ChatWindow.tsx` y las pruebas (`tests/test_chat_api.py`, `tests/test_chat_ws_price.py`).
- Documentar intents o cambios de tono en este archivo y marcar los pendientes en `docs/CHAT_PRICE_TODOS.md`.
- Mantener el TTL de la memoria en `services/chat/memory.py` para evitar que queden consultas viejas asociadas a un usuario.
