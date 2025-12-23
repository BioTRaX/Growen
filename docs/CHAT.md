<!-- NG-HEADER: Nombre de archivo: CHAT.md -->
<!-- NG-HEADER: Ubicacion: docs/CHAT.md -->
<!-- NG-HEADER: Descripcion: Documentación completa del chatbot Growen (intents, memoria, sesiones) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Chatbot Growen

> **Documento consolidado** - Incluye información de intents, memoria y sesiones persistentes.

## Resumen

El chatbot Growen responde en español rioplatense con tono casual y empático. Soporta consultas de productos (precio/stock) mediante tool-calling con OpenAI y MCP Products, además de mantener memoria conversacional persistente.

---

## Arquitectura de Tool Calling

Desde octubre 2025, las consultas de productos migran de `price_lookup.py` (DEPRECATED) a tool-calling:

- **Provider**: OpenAI decide cuándo invocar `get_product_info` o `get_product_full_info`
- **MCP Server**: `POST http://mcp_products:8001/invoke_tool`
- **Roles**: `admin|colaborador` acceden a tool avanzada; otros solo `get_product_info`
- **Endpoints afectados**: `POST /chat`, `WS /ws`, `POST /telegram/webhook/*`

> ⚠️ **Estado (2025-11-19)**: El router `ai/router.py` requiere refactorización asíncrona. Ver "Etapa 0" en `Roadmap.md`.

### Consideraciones de Diseño

1. **Robustez**: Si falla OpenAI, se degrada a eco sin romper interacción
2. **Latencia**: Segunda llamada al modelo solo si hay `tool_calls`
3. **Seguridad**: Control de tools por rol antes de cada request

---

## Intents Soportados

### Consulta de Productos (`product_answer`)

- Triggers: "¿cuánto sale X?", "¿tenés X en stock?", "/stock \<sku\>"
- Acepta: SKUs canónicos, internos y de proveedor
- Respuesta incluye: `type`, `intent`, `took_ms`, `results`, `needs_clarification`
- Métricas (solo admin): `data.metrics` con contadores y latencias

### Mensajes Libres

Si no coincide con intent controlado, se deriva al `AIRouter` manteniendo la personalidad configurada.

---

## Sistema de Sesiones Persistentes

### Modelos de Datos

**ChatSession**:
- `session_id` (PK): ej. "telegram:12345", "web:abc123"
- `user_identifier`: ID externo del usuario
- `status`: 'new', 'reviewed', 'archived'
- `tags`: JSON para etiquetas automáticas/manuales
- `admin_notes`: Texto de feedback para RLHF

**ChatMessage**:
- `session_id`: ForeignKey hacia ChatSession
- `role`: "user", "assistant", "tool", "system"
- `content`: Contenido del mensaje
- `meta`: JSON con metadatos (intent, tokens, etc.)

### Flujos de Creación

| Canal | Session ID | Ejemplo |
|-------|------------|---------|
| Telegram | `telegram:{chat_id}` | `telegram:123456789` |
| Web HTTP | `web:{session_id}` | `web:abc123` |
| WebSocket | `web:{sid}` o `web:{hash_ip}` | `web:hash_abc` |

### API de Administración

| Endpoint | Descripción |
|----------|-------------|
| `GET /admin/chats` | Lista sesiones (paginado, filtros por status) |
| `GET /admin/chats/{id}` | Detalle + mensajes |
| `GET /admin/chats/stats` | Métricas agregadas |
| `PATCH /admin/chats/{id}` | Actualizar status/notas/tags |

### Dashboard Admin

Acceder en `/admin/chats`:
- Layout 2 columnas: lista de conversaciones + vista de chat
- Filtros por status, paginación
- Panel de acciones: cambiar status, agregar notas

---

## Memoria y Follow-ups

- **Historial reciente**: Últimos 6 mensajes se inyectan automáticamente en prompts
- **Estado efímero**: `services/chat/memory.py` maneja aclaraciones por `session_id`/IP
- **Confirmaciones**: "sí", "dale", "stock" confirman lista anterior sin repetir query

### Política de Archivado

Script `scripts/archive_old_chat_sessions.py` archiva sesiones sin actividad:
```powershell
python scripts/archive_old_chat_sessions.py --days 90 --dry-run
```

---

## Logs y Métricas

- **Auditoría**: `AuditLog` con `action=chat.product_lookup`
- **Log estructurado**: `chat.lookup` con `correlation_id`, `intent`, `status`
- **Contadores en memoria**: `intent_counts`, `status_counts`, `matches_counts`
- **Propagación**: Middleware HTTP propaga `X-Correlation-Id`

---

## Buenas Prácticas

- Al agregar campos al payload, actualizar:
  - `serialize_result`
  - `ProductLookupOut`
  - `ChatWindow.tsx`
  - Tests en `tests/test_chat_*.py`
- Mantener TTL de memoria en `services/chat/memory.py`
- Documentar cambios de tono o intents en este archivo

---

## Próximas Fases (RLHF)

| Fase | Descripción |
|------|-------------|
| 3 | Etiquetado automático (sentimiento, intents problemáticos) |
| 4 | Feedback humano (marcar respuestas buena/mala) |
| 5 | Aprendizaje iterativo (ajuste de prompts) |

---

## Referencias

- `ai/persona.py`: Definición de personas y prompts
- `ai/router.py`: Router de IA
- `services/routers/chat.py`: Endpoint principal
- `services/chat/history.py`: Lógica de persistencia
- `services/chat/telegram_handler.py`: Integración Telegram
- `docs/CHATBOT_ARCHITECTURE.md`: Arquitectura completa
