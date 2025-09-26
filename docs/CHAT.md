<!-- NG-HEADER: Nombre de archivo: CHAT.md -->
<!-- NG-HEADER: Ubicación: docs/CHAT.md -->
<!-- NG-HEADER: Descripción: Referencia rápida de intents del chatbot Growen -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Intents soportados por el chat

## Consulta de precios y stock (`product_answer`)
- Mensajes como `¿cuánto sale <producto>?`, `¿tenés <producto> en stock?` o `/stock <sku>` disparan la resolución controlada.
- Se aceptan SKUs canónicos, internos y de proveedor. Si hay varias coincidencias se devuelve `status=ambiguous` con la lista para elegir.
- El payload incluye `results` con nombre, precio, proveedor, `stock_qty`, `stock_status`, `sku` y `variant_skus`.
- El texto renderizado muestra precio y un badge con la disponibilidad (`En stock`, `Pocas unidades`, `Sin stock`).
- Cuando no se encuentra nada se sugiere buscar por SKU y se dispara el evento `open-products` para abrir la vista detallada.

## Otros mensajes
- Si no coincide con un intent soportado, el mensaje se envía al `AIRouter` con la personalidad configurada en `ai/persona.py`.
- El WebSocket respeta el mismo flujo y expone `intent`, `took_ms` y `results` en el JSON de respuesta.

## Auditoría y métricas
- Cada consulta registra `chat.product_lookup` en `AuditLog` con query, intent, matches y stock reportado.
- El módulo `services/chat/price_lookup.py` mantiene contadores en memoria (`intent.*`, `status.*`, `matches.*`) y un estimador de latencia (`latency_p95_ms`, `latency_avg_ms`).
- `serialize_result` adjunta un snapshot de métricas para consumidores que deseen exponerlas vía endpoint o dashboard.

## Buenas prácticas
- Antes de agregar nuevos intents, documentarlos aquí y actualizar `docs/CHAT_PRICE_TODOS.md`.
- Toda respuesta estructurada debe incluir `type`, `intent`, `data` y `took_ms` para mantener consistencia entre HTTP y WebSocket.
- Cuando agregues nuevos campos al payload, sincronizá el renderizado en `ChatWindow.tsx` y las pruebas (`tests/test_chat_api.py`, `tests/test_chat_ws_price.py`).
