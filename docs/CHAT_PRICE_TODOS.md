<!-- NG-HEADER: Nombre de archivo: CHAT_PRICE_TODOS.md -->
<!-- NG-HEADER: Ubicación: docs/CHAT_PRICE_TODOS.md -->
<!-- NG-HEADER: Descripción: Lista de tareas para habilitar consultas de precio en el chatbot -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

## Prioridad de ejecución
1. **Backend (fase inicial)**: resolver intent `price_query`, servicio `price_lookup`, reglas de búsqueda y auditoría (tareas en sección Backend).
2. **Frontend / UI**: soporte de respuestas `price_answer` y comunicación en la interfaz.
3. **IA / Prompting**: ajustes de SYSTEM_PROMPT y ejemplos para detección temprana.
4. **Observabilidad y Métricas**: instrumentación y contadores.
5. **Pruebas integrales**: unitarias, API y E2E para garantizar el flujo.
6. **Documentación + Deploy**: actualizar docs, README, CHANGELOG y revisar configuración/roles.
## Backend
- [x] Definir intent `price_query` en el flujo de chat (`services/chat/price_lookup.py` + `services/routers/chat.py`).
- [x] Crear módulo de dominio (p.ej. `services/chat/price_lookup.py`) con función `resolve_price(query: str, user_id: int | None)`.
- [x] Implementar búsqueda por SKU exacto (interno y proveedor) y por nombre con fuzzy matching (`rapidfuzz`).
- [x] Determinar precio a retornar (`sale_price` del canónico; fallback a `SupplierProduct.current_sale_price`) y moneda (usar configuración existente).
- [x] Manejar casos sin coincidencias o múltiples resultados (retornar estructura con `status=no_match|ambiguous`).
- [x] Registrar auditoría (`AuditLog` acción `chat.price_lookup`) incluyendo `product_id`, `sku`, `result_status`).

## Frontend
- [x] Adaptar `ChatWindow` para renderizar mensajes con tipo `price_answer`.
- [x] Añadir copy en la pantalla inicial del chat indicando que se puede consultar precios.
- [x] Ajustar servicios de chat (fetch HTTP/WS) para manejar payload estructurado.

## IA / Prompting
- [x] Actualizar `SYSTEM_PROMPT` en `ai/router.py` para priorizar intent `price_query` antes de delegar al modelo.
- [ ] Añadir ejemplos en los tests de prompts o fixtures para asegurar detección temprana.

## Observabilidad
- [ ] Registrar métricas en `ServiceLog` o `ImportLog` (nueva categoría) con totales de consultas y tiempos.
- [ ] Añadir contador Prometheus o endpoint de métricas si ya existe patrón similar.

## Pruebas
- [ ] Unit tests para matcher del intent (`tests/test_ai_router.py`).
- [ ] Unit/integration tests para `price_lookup` (mock de base de datos).
- [ ] Test API que simule mensaje de chat y verifique respuesta (`tests/test_chat_price_query.py`).
- [x] Test E2E (Playwright) validando la tarjeta de precio en el chat.

## Documentación
- [ ] Crear/actualizar `docs/CHAT.md` describiendo intents soportados, formato de respuestas y limitaciones.
- [ ] Actualizar `README.md` sección de chatbot con la nueva capacidad.
- [ ] Añadir entrada en `CHANGELOG.md` cuando se entregue la funcionalidad.

## Deploy / Configuración
- [ ] Revisar variables de entorno necesarias (moneda por defecto, formatos de precio).
- [ ] Confirmar que la consulta no expone precios restringidos por rol; aplicar filtros según permisos del usuario autenticado.



