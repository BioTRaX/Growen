<!-- NG-HEADER: Nombre de archivo: CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Ubicación: docs/CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Descripción: Arquitectura del chatbot, roles, personas y seguridad -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Arquitectura del Chatbot Administrativo

## Control de disponibilidad (2026-08-16)

La autorización y el rollout son capas separadas: primero se resuelve `User.role` y el techo del canal; luego `chat_rollout_state` decide si la fase admite el rol. El controlador de cinco minutos sólo autoavanza con permanencia, muestra, health, latencia, backlog, smokes y evaluaciones aprobados. Eventos y checks guardan códigos/métricas agregadas, nunca contenido.

## Autorización por capacidades y canal (2026-07-22)

Cada solicitud distingue `account_role` (valor vigente de `User.role`) de `effective_role` (rol tras el techo del canal). Telegram reduce admin a colaborador y rechaza toda mutación. Los roles canónicos son `guest`, `cliente`, `proveedor`, `colaborador` y `admin`; `anon` sólo se acepta como alias legacy de `guest`.

`agent_core/chat_policy.py` es el registro único de tools, roles, capacidades, canales, lectura/escritura, perfil de datos y sanitizador. El cliente MCP, `tools/list`, decoradores y servidor vuelven a consultar el registro; una tool desconocida se deniega. Las respuestas públicas eliminan recursivamente SKU y stock exacto.

El flujo es: validación/rate limit → identidad → persona → historial por tokens → RAG autorizado → tools autorizadas → modelo → sanitización → persistencia → métricas. HTTP, Telegram y todas las respuestas WebSocket —incluidas aclaraciones— usan el orquestador observable. React permanece como fallback hasta aprobar `vue_eligible` y los smokes.

## Enriquecimiento por tags de producto (2026-07-18)

Products MCP expone tags como `list[str]` en búsqueda y detalle. La búsqueda interpreta cada término con lógica AND y permite coincidencia por tag, además de nombre, descripción o SKU. Los tags enriquecen recuperación y conversación, pero no reemplazan categoría/subcategoría ni forman parte del identificador permanente del producto.

> **Documento consolidado** - Incluye arquitectura, roles, personas y matriz de permisos.

## Resumen

El chatbot administrativo brinda asistencia en tiempo real con acceso diferenciado según rol. Administradores pueden consultar el repositorio y generar sugerencias; colaboradores acceden a contexto operativo de productos, clientes y ventas.

---

## 1. Sistema de Personas Dinámicas

Growen utiliza una **máquina de estados** que adapta tono y estilo según rol y contexto.

### Identidad de Growen

- **Nombre**: Growen
- **Estilo**: Español rioplatense casual ("vos", "che", pero educado)
- **Personalidad**: Tiene opinión y experiencia en cultivo, no es robótico
- **Ambigüedad**: "¿Seré un bot? No lo sé, mi nombre es Growen. ¿Cómo estás?"

### Estados de la Máquina

#### OBSERVER (Estado Inicial)
- **Activación**: Inicio de conversación, saludos, sin contexto claro
- **Comportamiento**: Saluda casual, NO ofrece productos de inmediato
- **Transiciones**: Problema de cultivo → CULTIVATOR | Consulta de producto → SALESMAN

#### CULTIVATOR (Diagnóstico Técnico + Farmacéutico)
- **Activación**: Menciones de problemas de cultivo, imágenes de plantas
- **Comportamiento**: 
  - Usa contexto RAG si disponible
  - Hace preguntas diagnósticas conversacionales (pH, etapa, riego)
  - Si hay producto relacionado, los Tags ayudan a filtrar
  - **Rol Farmacéutico**: Tras diagnóstico, pregunta "¿Querés que busque productos?"
  - **Lógica NPK**: Interpreta tags "NPK X-X-X" para recomendar productos
    - Carencia N → buscar alto en 1er número
    - Carencia P → buscar alto en 2do número
    - Carencia K → buscar alto en 3er número
  - Muestra máximo 3 opciones variando precios
  - Solo recomienda productos con stock > 0 (proactivo)
- **Transición**: Diagnóstico completo con producto → SALESMAN

#### SALESMAN (Cierre de Venta)
- **Activación**: Oportunidad de venta, consulta directa de precio
- **Comportamiento**:
  - Usa Tags de productos para recomendar
  - **CERO URGENCIA**: NUNCA usa frases como "¡Quedan pocas!" o "¡Comprá ya!"
  - NUNCA muestra SKUs técnicos a clientes
  - Prioriza beneficios, no datos internos
  - **Manejo de stock**:
    - Stock > 0: "Disponible para entrega"
    - Stock = 0 (usuario pidió específicamente): "Disponible pero el tiempo de entrega será mayor"
    - Stock = 0 (recomendación proactiva): No mostrar, ofrecer alternativas


#### ASISTENTE (Admin/Colaborador)
- **Activación**: Rol admin o colaborador
- **Comportamiento**:
  - Tono directo y técnico
  - Muestra SKU canónico siempre
  - Stock exacto y ubicación
  - Respuestas concisas

### Detección de Persona

```python
from ai.persona import get_persona_prompt

persona_mode, system_prompt = get_persona_prompt(
    user_role="cliente",
    intent="DIAGNOSTICO",
    user_text="hojas amarillas",
    has_image=False,
    conversation_state={"current_mode": "CULTIVATOR"}
)
```

**Lógica de selección**:
1. Rol admin/colaborador → ASISTENTE
2. Palabras clave diagnósticas → CULTIVATOR  
3. `conversation_state.current_mode` si existe
4. Diagnóstico completo + producto → SALESMAN
5. Saludo o sin contexto → OBSERVER
6. Consulta directa producto/precio → SALESMAN

---

## 2. Matriz de Roles y Permisos

### Definiciones

| Rol | Descripción |
|-----|-------------|
| **Admin** | Operaciones sensibles, acceso al código completo, sugerencias en `PR/` |
| **Colaborador** | Equipo operativo, acceso a documentación funcional y datos operativos |
| **Invitado** | Sin autenticación, chatbot público limitado |

### Matriz de Permisos

| Recurso / Acción | Admin | Colaborador |
|------------------|:-----:|:-----------:|
| Documentación funcional (`docs/`, guías) | ✅ | ✅ |
| Métricas internas (health, logs) | ✅ | 🚫 |
| Buscar en código (`/chatbot/repo/search`) | ✅ | 🚫 |
| Descargar archivo repo (`/chatbot/repo/file`) | ✅ | 🚫 |
| Sugerencias de código (`/chatbot/pr-suggestion`) | ✅ (solo `PR/`) | 🚫 |
| Auditoría del chatbot | ✅ | 🚫 |
| Info operativa (productos, clientes, ventas) | ✅ | ✅ |
| Roadmap y decisiones de negocio | ✅ | ✅ |
| Configuración de providers IA | ✅ | 🚫 |

---

## 3. Fases de Implementación

### Fase 0 – Descubrimiento ✅
- Revisión de `services/auth.py`
- Diseño de matriz de permisos

### Fase 1 – Autenticación Base
- Integración SSO/MFA con FastAPI
- Middleware que inyecta rol en contexto
- Pruebas unitarias de roles

### Fase 2 – Gateway de Repositorio  
- Servicio `services/routers/repo_gateway.py`
- Endpoints: `/chatbot/repo/search`, `/chatbot/repo/file`, `/chatbot/pr-suggestion`
- Escritura confinada a `PR/`

### Fase 3 – Indexado y RAG
- Script `scripts/build_chatbot_index.py`
- Embeddings en Postgres + pgvector
- Filtrado por `role_scope`

### Fase 4 – Auditoría
- Modelo `ChatbotAudit`
- Registro: usuario, rol, prompt, respuesta, archivos

### Fase 5 – Documentación y UX
- Actualización de README, Roadmap
- Playbooks de respuesta a incidentes

---

## 4. Migración a Tool-Calling

> **Estado (2026-07-14)**: Tool calling asíncrono conectado y MCP real en migración compatible.

### Arquitectura Objetivo

1. Tool calling con OpenAI (funciones `get_product_info`, `get_product_full_info`)
2. Microservicio MCP `mcp_servers/products_server`
3. Router `chat` detecta consultas y delega via `chat_with_tools`

### Estado Actual

| Componente | Estado |
|------------|--------|
| MCP Products Server | ✅ Implementado |
| Tools definidas | ✅ Operativas |
| Registro central de políticas | ✅ Implementado y denegación por defecto |
| `POST /chat` | ✅ Orquestador, RAG/citas y trazabilidad |
| Telegram polling | ✅ Activo en desarrollo bajo `preflight` restringido al canary |
| WebSocket `/ws` | ✅ Respuestas, aclaraciones, streaming y RAG orquestados con citas |
| UI de identidades Telegram | ⚠️ Usuario/admin implementados; flags apagados y smoke sesión/CSRF pendiente |
| `Chat 😎` Vue | ⚠️ Typecheck, 90 pruebas y build aprobados; `ready/legacy` hasta smoke por rol |

### Próximos Pasos

1. Completar protección automática y purga remota histórica; los secretos ya fueron rotados y no hay API keys locales.
2. Validar la UI de vínculos/segunda aprobación con sesión real y completar smoke Vue por rol.
3. Sustituir tokens/costo estimados por usage real cuando exista proveedor; repetir el gate RAG en el entorno objetivo antes del rollout.
4. Ejecutar smoke por rol/canal y retirar schemas, RPC y runtime React sólo tras la ventana estable.

### Configuración

```env
MCP_PRODUCTS_URL=http://mcp_products:8100/mcp
OPENAI_API_KEY_FILE=<ruta_absoluta_fuera_del_repositorio>
AI_ALLOW_EXTERNAL=false
```

---

## 5. Reglas de Auditoría

Cada ejecución conserva sólo identificadores opacos y metadatos operativos:
- `correlation_id`, canal, rol real/efectivo y duración;
- modelo/proveedor, tokens agregados, citas, tools y código de error seguro.

No se registran prompts, respuestas, argumentos completos, Telegram IDs ni IP en la trazabilidad operativa de Chat.

Las sugerencias en `PR/` deben incluir:
- Diff resumido
- Hash del contenido base
- Resultado de validaciones

**Retención**: Mínimo 180 días + alertas por accesos inusuales.

---

## 6. Consideraciones de Seguridad

- Sanitizar inputs (paths, queries)
- Enmascarar variables sensibles en respuestas
- Rate limiting por rol y usuario
- Mantener logs bajo retención definida

---

## 7. Testing

- Tests unitarios para middlewares de auth
- Tests de integración para `/chatbot/*`
- Pruebas de regresión del pipeline RAG
- Smoke test de escritura confinada a `PR/`

---

## Checklist de Cumplimiento

- [ ] Rol admin validado mediante SSO/MFA
- [ ] Colaboradores sin acceso a `/chatbot/repo/*`
- [ ] RAG etiqueta chunks con `role_scope`
- [ ] Documentación actualizada
- [ ] Tests automáticos activos

---

## Referencias

- `ai/persona.py`: Definición de personas
- `ai/router.py`: Integración AIRouter
- `services/routers/chat.py`: Endpoint principal
- `docs/CHAT.md`: Documentación de intents y memoria
- `docs/RAG.md`: Sistema de Knowledge Base
