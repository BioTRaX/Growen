<!-- NG-HEADER: Nombre de archivo: CHAT.md -->
<!-- NG-HEADER: Ubicacion: docs/CHAT.md -->
<!-- NG-HEADER: Descripcion: Referencia rapida de intents del chatbot Growen -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Chatbot Growen

> **⚠️ NOTA IMPORTANTE (2025-11-19)**: La implementación de Tool Calling descrita en este documento está parcialmente funcional pero requiere refactorización arquitectónica. Se ha detectado un problema de sincronía: el router actual (`ai/router.py`) es síncrono, mientras que `chat_with_tools` en `OpenAIProvider` requiere `async/await` para consultar servicios MCP externos. Consultar **"Roadmap de Inteligencia Growen → Etapa 0"** en `Roadmap.md` para el plan de evolución completo. La funcionalidad actual usa fallback a `price_lookup.py` que es funcional pero limitado.

## Actualización (Tool Calling + MCP Products)

Desde octubre 2025 el intent de consulta de productos (precio/stock) migra del motor interno `price_lookup.py` a un flujo de Tool Calling con OpenAI y un servidor MCP (`mcp_products`).

- El proveedor OpenAI decide cuándo invocar las tools `get_product_info` o `get_product_full_info`.
- El servidor MCP se consume vía `POST http://mcp_products:8001/invoke_tool` y retorna un payload JSON con los datos del producto.
- Roles `admin` y `colaborador` ven la tool avanzada; otros roles solo `get_product_info`.
- El archivo `services/chat/price_lookup.py` queda marcado como `DEPRECATED` y se mantendrá temporalmente hasta retirar dependencias residuales (tests históricos y memoria de clarificación antigua en WS/Telegram).
- Endpoints afectados:
	- `POST /chat`: usa `chat_with_tools` cuando la consulta incluye un SKU explícito (p. ej. "SKU123"). En consultas por nombre o descripción, se mantiene un fallback local (`price_lookup.py`) que retorna `type=product_answer` con payload estructurado y soporta memoria de aclaración.
	- `WS /ws`: migrado a tool-calling (retirado ranking local; se simplifica la clarificación).
	- `POST /telegram/webhook/*`: migrado a tool-calling.

### Consideraciones de diseño
1. Robustez: si falla OpenAI o falta API key se degrada a eco (`openai:` prefix) para no romper interacción.
2. Latencia: segunda llamada al modelo ocurre solo si el primer response incluye `tool_calls`.
3. Seguridad: control de tools por rol antes de cada request a OpenAI.
4. Evolución: cuando se añadan nuevas tools, actualizar `_build_tools_schema` en `openai_provider.py` y documentarlas aquí.

### Próximos pasos sugeridos
- Eliminar dependencias residuales a `resolve_product_info` en memoria de clarificación avanzada.
- Añadir métricas de tool usage (latencia y código de estado MCP) en logs estructurados.
- Incorporar autenticación fuerte (token firmado) entre chatbot y MCP antes de exponer externamente.

---

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
- Cuando la consulta devuelve múltiples coincidencias (fallback local), se guarda un estado efímero (`services/chat/memory.py`) por `session_id`/IP.
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
