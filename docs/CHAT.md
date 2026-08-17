<!-- NG-HEADER: Nombre de archivo: CHAT.md -->
<!-- NG-HEADER: Ubicacion: docs/CHAT.md -->
<!-- NG-HEADER: Descripcion: Documentación completa del chatbot Growen (intents, memoria, sesiones) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Chatbot Growen

## Estado operativo (2026-08-17)

HTTP, WebSocket y Telegram comparten trazabilidad mediante `ChatOrchestrator`. Las aclaraciones WebSocket ya generan `ChatRun`, correlación y persistencia. Telegram consulta `chat_rollout_state` por mensaje: `preflight` admite sólo el canary y cada rol requiere su fase; los flags de entorno siguen siendo kill switch.

La generación local usa Ollama `llama3.1:8b`, sin eco ni fallback OpenAI. El
2026-08-17 el rollout de desarrollo pasó a `preflight/active`: sólo el canary
puede interactuar y el autoavance permanece apagado. PostgreSQL, Redis, Ollama
y el worker polling fueron verificados. Ver `docs/CHAT_DEPLOYMENT.md`.

El corpus RAG v1 ya está cargado en desarrollo: 10 fuentes clasificadas y documentos curados fragmentados. La evaluación real aprobó cero fugas, recall@5 y MRR sintéticos 1,00, recall curado 1,00, citas 100 %, inclusión dentro del presupuesto 100 % y separación/invalidation de cache. WebSocket incorpora ese contexto dentro del orquestador y devuelve citas normales o de cierre de streaming.

El nombre del modelo debe incluir el tag completo: `OLLAMA_MODEL=llama3.1:8b`.
Usar `llama3.1` cuando sólo está descargado `llama3.1:8b` hace que Ollama
responda 404 antes de iniciar la inferencia.

## Estado auditado histórico (2026-08-15)

- PostgreSQL está en el head único `20260726_canonical_knowledge_v1`, que incluye la cadena segura de Chat. No hay fuentes RAG, identidades externas, updates Telegram ni `chat_runs` en la base local; tampoco existen sesiones legacy `telegram:<id-numérico>`.
- Sólo PostgreSQL estaba activo durante la auditoría. API, Redis, MCP, Vue y el worker Telegram estaban apagados; los archivos de estado de ejecuciones anteriores no representan salud actual.
- HTTP y Telegram usan `ChatOrchestrator`. WebSocket recarga el rol vigente por mensaje y ya orquesta tools, fallback local, respuesta general y streaming; las respuestas de aclaración heredadas aún no crean la misma trazabilidad.
- `Chat 😎` aprobó typecheck, 89 pruebas Vue y build, pero sigue `ready/legacy`; Nginx no publica `/chat` hacia Vue mientras conserve ese runtime.
- Vue ya permite generar/revocar vínculos propios y aprobar/revocar identidades como segundo admin, siempre con identificadores enmascarados. Los flags continúan apagados y falta el smoke autenticado con sesión/CSRF reales.
- La suite focal backend aprobó 50 pruebas y omitió 6. Persisten warnings de conexiones SQLite no devueltas al pool en pruebas heredadas WebSocket/RAG.

## Plan de cierre y activación

1. **Seguridad P0**: los secretos fueron rotados y no hay API keys locales. Falta completar la purga de referencias históricas administradas por GitHub, habilitar protección automática y ejecutar el chequeo redactado de logs/configuración.
2. **Transporte único**: el router webhook fue retirado y la configuración sólo admite polling. Falta validar con Redis real reinicio, deduplicación, backpressure, retry, rate limit distribuido y alertas del health ya expuesto.
3. **Identidad operable**: las pantallas Vue están implementadas. Falta cubrir sesión real, reautenticación, CSRF, chats privados, autoaprobación y revocación inmediata mediante smoke por rol.
4. **Pipeline común**: historial, aclaraciones, respuestas generales, streaming y RAG WebSocket generan trazabilidad. Falta reemplazar tokens/costo estimados por usage real cuando exista proveedor compatible.
5. **RAG verificable**: corpus, scopes, centinelas, citas, cache y presupuesto ya aprobaron en desarrollo; falta repetir el gate en el entorno objetivo antes de rollout.
6. **Paridad Vue**: typecheck, 91 pruebas y build aprobaron; contrato de productos y citas WS están alineados. El smoke guest real aprobó y faltan cliente, proveedor, colaborador y admin, además de escenarios integrales de cancelación/errores.
7. **Rollout gradual**: habilitar guest, luego cliente/proveedor, colaborador y finalmente admin con techo colaborador; observar dashboard/Inbox. Sólo después cambiar `/chat` a `active/vue` y comenzar las dos releases más siete días de estabilidad antes de retirar React.

Cada paso debe dejar evidencia reproducible, documentación actualizada y un
rollback por flags; ninguna fase habilita automáticamente la siguiente.

## Pipeline multicanal seguro (2026-07-22)

HTTP, WebSocket y Telegram comparten contratos de autorización. `ChatOrchestrator` registra canal, roles, estado, latencia y tokens estimados sin conservar contenido operativo. WebSocket converge en tools, fallback local, aclaraciones, respuesta general, streaming y RAG con citas.

HTTP devuelve `correlation_id` y citas tipadas. Las invocaciones MCP registran nombre, autorización, estado y duración, nunca argumentos ni resultados. Chat Inbox presenta la última traza a personal autorizado.

Telegram admite `/vincular`, `/desvincular`, `/quien_soy` y `/privacidad`. Los vínculos elevados sólo funcionan en chat privado; grupos permanecen `guest`. El catálogo público expone precio de venta y disponibilidad aproximada, nunca SKU ni stock exacto.

El worker de polling no elimina webhook ni updates pendientes, registra `update_id` antes de procesar, usa cola acotada, concurrencia configurable y orden por persona. Iniciar exclusivamente con `scripts/start_worker_telegram_polling.cmd` después de configurar claves y flags. La API no expone ruta webhook y rechaza cualquier transporte distinto de `polling`.

El módulo Vue `/chat` incluye HTTP/WS, reconexión con backoff, fallback HTTP, cancelación, cards filtradas, citas, feedback y errores tipados. Permanece `ready/legacy` hasta completar el smoke por rol y la ventana de estabilidad.

## Chat Inbox y calidad supervisada (2026-07-18)

`/admin/chats` permite a staff buscar, filtrar, asignar, etiquetar y revisar conversaciones. Feedback, intención, sentimiento, confianza, modelo y señales problemáticas se conservan en PostgreSQL.

Los prompts usan el ciclo candidato, evaluación, aprobación y activación. Sólo admin puede promoverlos; se exige seguridad aprobada y mejora compuesta mínima del 5 % contra la versión activa. La versión anterior queda reactivable y cada respuesta registra la versión utilizada en `chat_messages.meta`.

> **Documento consolidado** - Incluye información de intents, memoria y sesiones persistentes.

## Resumen

El chatbot Growen responde en español rioplatense con tono casual y empático. En el perfil local, las consultas de productos usan el resolver determinista y la conversación usa Ollama; OpenAI/MCP queda como integración opcional futura cuando la política externa lo permita. Mantiene memoria conversacional persistente.

---

## Arquitectura de Tool Calling

Las consultas de productos conservan dos caminos autorizados durante la transición:

- **Ollama local**: resolución determinista de catálogo, sin depender de tool calling del modelo.
- **Proveedor externo opcional**: puede invocar `get_product_info` o `get_product_full_info` mediante MCP sólo cuando `AI_ALLOW_EXTERNAL=true` y exista secreto configurado.
- **MCP Servers**: Streamable HTTP en `/mcp`; Growen descubre `tools/list` y ejecuta `tools/call`.
- **Roles**: `admin|colaborador` acceden a tool avanzada; otros solo `get_product_info`
- **Endpoints/canales afectados**: `POST /chat`, `WS /ws` y worker Telegram polling. No existe endpoint webhook en la API.

> **Estado (2026-07-14)**: Router asíncrono y descubrimiento MCP implementados sobre Python 3.14.6. El retiro legacy depende de la ventana de observación documentada.

### Consideraciones de Diseño

1. **Robustez**: Si no existe un proveedor permitido o `AI_ALLOW_EXTERNAL=false`, falla cerrado con un error tipado; nunca responde con eco como sustituto de IA
2. **Latencia**: Segunda llamada al modelo solo si hay `tool_calls`
3. **Seguridad**: Control de tools por rol antes de cada request

---

## Intents Soportados

### Consulta de Productos (`product_answer`)

- Triggers: "¿cuánto sale X?", "¿tenés X en stock?", "/stock \<sku\>"
- El clasificador exige precio, stock, información de producto, SKU o comando
  explícito. Smalltalk y preguntas generales nunca se convierten por defecto en
  una búsqueda de catálogo.
- Acepta: SKUs canónicos, internos y de proveedor
- Con Ollama local, precio/stock usa el resolver determinista de catálogo y no
  depende de tool calling del modelo. Los perfiles públicos reciben precio y
  disponibilidad aproximada sin SKU, proveedor ni cantidad exacta.
- Respuesta incluye: `type`, `intent`, `took_ms`, `results`, `needs_clarification`
- Métricas (solo admin): `data.metrics` con contadores y latencias

### Mensajes Libres

Si no coincide con intent controlado, se deriva al `AIRouter` manteniendo la personalidad configurada.

---

## Sistema de Sesiones Persistentes

Los mensajes exitosos se guardan en `chat_messages` para memoria conversacional
y se archivan según la política de 90 días. Los logs operativos y `chat_runs`
guardan únicamente correlation ID opaco, canal, roles, latencia, tokens
estimados, estado y códigos seguros; no almacenan el texto, prompt, respuesta,
Telegram ID ni argumentos de tools. Si el proveedor falla antes de producir una
respuesta, no se agrega ese intercambio a la memoria, pero el run queda
`failed` y Telegram entrega un error público sin detalles.

### Modelos de Datos

**ChatSession**:
- `session_id` (PK): identificador opaco, por ejemplo `telegram:<hmac-opaco>` o `web:<id-sesión>`
- `user_identifier`: sujeto opaco; nunca un Telegram ID numérico en claro
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
| Telegram | `telegram:{conversation_key_opaca}` | `telegram:7f2c…` |
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
.\.venv\Scripts\python.exe scripts\archive_old_chat_sessions.py --days 90 --dry-run
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
