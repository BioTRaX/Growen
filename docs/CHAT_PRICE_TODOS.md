<!-- NG-HEADER: Nombre de archivo: CHAT_PRICE_TODOS.md -->
<!-- NG-HEADER: Ubicacion: docs/CHAT_PRICE_TODOS.md -->
<!-- NG-HEADER: Descripcion: Lista de tareas para habilitar consultas de precio en el chatbot -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

## Estado de migración (2025-10-06)
La fase inicial basada en `price_lookup.py` está DEPRECATED para el endpoint HTTP `/chat` y será reemplazada completamente por tool-calling (OpenAI → MCP Products). Este archivo se conserva para histórico y checklist residual de tareas no migradas (otros canales / métricas avanzadas).

## Prioridad de ejecución (nueva)
1. Migrar WebSocket y Telegram a tool-calling.
2. Eliminar lógica residual de `price_lookup.py` dejando solo parsing si sigue siendo requerido.
3. Auditoría y métricas de invocaciones de tools (latencia, rol, tool_name, error_rate).
4. Extender tool `get_product_full_info` con categorías, proveedores y equivalencias.
5. Tests de error (timeouts MCP, 4xx/5xx) y resiliencia.
6. Actualizar CHANGELOG y README (sección ChatBot) tras completar migración total.
## Backend (legacy completado)
- [x] Definir intent `price_query` en el flujo de chat (`services/chat/price_lookup.py` + `services/routers/chat.py`).
- [x] Crear modulo de dominio (p.ej. `services/chat/price_lookup.py`) con funcion `resolve_price(query: str, user_id: int | None)`.
- [x] Implementar busqueda por SKU exacto (interno y proveedor) y por nombre con fuzzy matching (`rapidfuzz`).
- [x] Determinar precio a retornar (`sale_price` del canonico; fallback a `SupplierProduct.current_sale_price`) y moneda (usar configuracion existente).
- [x] Manejar casos sin coincidencias o multiples resultados (retornar estructura con `status=no_match|ambiguous`).
- [x] Registrar auditoria (`AuditLog` accion `chat.price_lookup`) incluyendo `product_id`, `sku`, `result_status`).

## Frontend
- [x] Adaptar `ChatWindow` para renderizar mensajes con tipo `price_answer`.
- [x] Anadir copy en la pantalla inicial del chat indicando que se puede consultar precios.
- [x] Ajustar servicios de chat (fetch HTTP/WS) para manejar payload estructurado.

## IA / Prompting (legacy)
- [x] Actualizar `SYSTEM_PROMPT` en `ai/router.py` para priorizar intent `price_query` antes de delegar al modelo.
- [ ] Anadir ejemplos en los tests de prompts o fixtures para asegurar deteccion temprana.

## Observabilidad (pendiente tool-calling)
- [x] Registrar metricas en `ServiceLog` o `ImportLog` (nueva categoria) con totales de consultas y tiempos.
- [ ] Exportar m\u00e9tricas a Prometheus/endpoint dedicado.

## Pruebas (estado)
- [x] Unit tests para matcher del intent (`tests/test_ai_router.py`).
- [x] Unit/integration tests para `price_lookup` (mock de base de datos).
- [x] Test API que simule mensaje de chat y verifique respuesta (`tests/test_chat_api.py`).
- [x] Test E2E (Playwright) validando la tarjeta de precio en el chat.

## Documentacion (pendiente refactor final)
- [x] Crear/actualizar `docs/CHAT.md` describiendo intents soportados, formato de respuestas y limitaciones.
- [ ] Actualizar `README.md` seccion de chatbot con la nueva capacidad.
- [ ] Anadir entrada en `CHANGELOG.md` cuando se entregue la funcionalidad.

## Deploy / Configuracion (pendiente tool-calling ampliado)
- [ ] Revisar variables de entorno necesarias (moneda por defecto, formatos de precio).
- [ ] Confirmar que la consulta no expone precios restringidos por rol; aplicar filtros segun permisos del usuario autenticado.




