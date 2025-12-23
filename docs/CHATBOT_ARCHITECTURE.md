<!-- NG-HEADER: Nombre de archivo: CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Ubicación: docs/CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Descripción: Arquitectura del chatbot, roles, personas y seguridad -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Arquitectura del Chatbot Administrativo

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

#### CULTIVATOR (Diagnóstico Técnico)
- **Activación**: Menciones de problemas de cultivo, imágenes de plantas
- **Comportamiento**: 
  - Usa contexto RAG si disponible
  - Hace preguntas diagnósticas conversacionales
  - Si hay producto relacionado, los Tags ayudan a filtrar
- **Transición**: Diagnóstico completo con producto → SALESMAN

#### SALESMAN (Cierre de Venta)
- **Activación**: Oportunidad de venta, consulta directa de precio
- **Comportamiento**:
  - Usa Tags de productos para recomendar
  - Crea urgencia si poco stock
  - NUNCA muestra SKUs técnicos a clientes
  - Prioriza beneficios, no datos internos

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

> ⚠️ **Estado (2025-11-19)**: Requiere refactorización. Router síncrono no puede usar `chat_with_tools` asíncrono.

### Arquitectura Objetivo

1. Tool calling con OpenAI (funciones `get_product_info`, `get_product_full_info`)
2. Microservicio MCP `mcp_servers/products_server`
3. Router `chat` detecta consultas y delega via `chat_with_tools`

### Estado Actual

| Componente | Estado |
|------------|--------|
| MCP Products Server | ✅ Implementado |
| Tools definidas | ✅ Operativas |
| Router asíncrono | ❌ **Bloqueador** |
| `/chat` endpoint | ⚠️ Usa fallback `price_lookup.py` |
| WebSocket y Telegram | ⏸️ Pendiente migrar |

### Próximos Pasos

1. Convertir `AIRouter.run` a async
2. Implementar `generate_async` en `OpenAIProvider`
3. Actualizar endpoints para usar `await router.run(...)`
4. Sincronizar esquemas JSON entre provider y MCP

### Configuración

```env
MCP_PRODUCTS_URL=http://mcp_products:8001/invoke_tool
OPENAI_API_KEY=sk-...  # Requerida para tool-calling
```

---

## 5. Reglas de Auditoría

Cada request del chatbot debe incluir:
- `user_id`, `role`, `source_ip`
- `prompt`, `artifacts`, `duration_ms`

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
