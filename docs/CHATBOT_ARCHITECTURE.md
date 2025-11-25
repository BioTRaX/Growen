<!-- NG-HEADER: Nombre de archivo: CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Ubicación: docs/CHATBOT_ARCHITECTURE.md -->
<!-- NG-HEADER: Descripción: Arquitectura propuesta para el chatbot administrativo con control de acceso y RAG -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Arquitectura chatbot administrativo

## Resumen

El chatbot administrativo brindará asistencia en tiempo real para desarrollo y soporte con acceso diferenciado según el rol del usuario. El objetivo es permitir a administradores consultar el repositorio completo y generar sugerencias controladas, mientras que colaboradores reciben un contexto operativo limitado a productos, clientes, proveedores, ventas y documentación de uso.

## Objetivos clave

- Autenticación unificada open source (Keycloak, Authentik u ORY) con soporte MFA y emisión de tokens OIDC.
- Autorización basada en roles (admin, colaborador) aplicada en backend (FastAPI) y en el motor RAG.
- Gateway de repositorio en modo lectura con escritura confinada a `PR/` para sugerencias de código.
- Pipeline RAG con chunking etiquetado por alcance, refresco incremental y almacenamiento de embeddings reutilizable.
- Auditoría completa de consultas, archivos accedidos y propuestas generadas.
- Documentación viva y pruebas automatizadas que abarquen autenticación, permisos y RAG.

## Fases de implementación

### Fase 0 – Descubrimiento y cimientos
- Revisión de `services/auth.py` y flujos actuales de login.
- Selección del proveedor OIDC open source (Keycloak/Authentik) y definición de claims (`role`, `scopes`).
- Diseño de matriz de permisos detallada (ver `docs/CHATBOT_ROLES.md`).

### Fase 1 – Autenticación y autorización base
- Integración del proveedor SSO/MFA con FastAPI utilizando `python-jose` o similar para validar tokens.
- Middleware que inyecta el rol en el contexto de `services/routers/chat.py` y futuros endpoints `/chatbot/*`.
- Persistencia opcional de sesiones (`chatbot_sessions`) para monitorear expiraciones y revocaciones.
- Pruebas unitarias en `tests/test_auth_{...}.py` para validar roles y expiración.

### Fase 2 – Gateway de repositorio
- Servicio FastAPI (`services/routers/repo_gateway.py`) que envuelve operaciones `git show`, `rg` y lectura segura de archivos.
- Endpoints planificados:
  - `GET /chatbot/repo/search?q=` (read-only, rate limit configurable).
  - `GET /chatbot/repo/file?path=` con sanitización y listas blancas.
  - `POST /chatbot/pr-suggestion` que valida que el path destino pertenezca a `PR/` y registra auditoría.
- Tests de integración asegurando que rutas fuera de `PR/` sean rechazadas.

### Fase 3 – Indexado y RAG
- Script `scripts/build_chatbot_index.py` para chunking (máx. 1k tokens) con etiquetas `role_scope=admin|collab`.
- Almacenamiento de embeddings en Postgres + pgvector (si ya instalado) o motor vectorial open source compatible.
- Actualizaciones incrementales mediante hooks de git o job agendado.
- Servicio `services/chatbot/rag.py` que filtra chunks según rol antes de invocar LLM (Ollama/OpenAI).

### Fase 4 – Auditoría y monitoreo
- Modelo `ChatbotAudit` en `db/models.py` + migración (ver `docs/MIGRATIONS_NOTES.md`).
- Registro de usuario, rol, prompt, respuesta, archivos tocados, hash de contenido y timestamp.
- Endpoint `GET /chatbot/audit/logs` con filtros por usuario, fecha y tipo de recurso.
- Integración con panel admin (`frontend/src/pages/admin/ChatbotAudit.tsx`, futuro) y alertas en `HealthPanel`.

### Fase 5 – Documentación, UX y capacitación
- Actualización de `README.md`, `Roadmap.md`, `docs/roles-endpoints.md` y creación de guías operativas.
- Playbooks para respuesta ante incidentes (revocación de tokens, limpieza de sugerencias en `PR/`).
- Comunicación interna y capacitación de administradores y colaboradores.

## Integración con tecnologías existentes

- Backend FastAPI ya expone routers bajo `services/routers/`; el chatbot reutilizará esta estructura.
- Los proveedores IA (`ai/providers/`) se mantienen; se ajustará `ai/router.py` para respetar filtros de rol.
- `AGENTS.md` deberá reflejar scripts nuevos y procedimientos de auditoría.
- Preferencia por dependencias open source ampliamente soportadas; documentar instalaciones adicionales (pgvector, Keycloak) en `docs/dependencies.md` si aplican.

## Consideraciones de seguridad

- Sanitizar inputs (paths, queries) para evitar traversal y fuga de secretos.
- Enmascarar variables sensibles en respuestas del chatbot.
- Aplicar rate limiting por rol y usuario.
- Mantener logs bajo retención definida y revisar cumplimiento normativo.

## Pruebas recomendadas

- Tests unitarios para middlewares de autenticación/autorización.
- Tests de integración para `/chatbot/*` (admin vs colaborador).
- Pruebas de regresión del pipeline RAG tras reindexado.
- Smoke test que valide escritura confinada a `PR/` y auditoría obligatoria.

## Migración a Tool-Calling para Productos (EN REVISIÓN - Ver Roadmap)

> **⚠️ ESTADO ACTUAL (2025-11-19)**: Esta sección describe el objetivo arquitectónico, pero la implementación completa requiere refactorización. **Problema detectado**: El router `ai/router.py` es síncrono y no puede usar correctamente `chat_with_tools` asíncrono, lo que impide la consulta efectiva de servicios MCP para stock/precios en tiempo real. Consultar **"Roadmap de Inteligencia Growen → Etapa 0: Refactorización Core AI"** en `Roadmap.md` para el plan de migración.

La obtención de información de productos (precio, stock básico) está en proceso de migración desde el módulo monolítico `services/chat/price_lookup.py` hacia un enfoque desacoplado basado en:

1. Tool calling con OpenAI (funciones `get_product_info` y `get_product_full_info`).
2. Microservicio MCP `mcp_servers/products_server` que encapsula lógica de fetch, permisos y cache.
3. Router `chat` que detecta consultas de producto y delega la resolución mediante `chat_with_tools` del provider OpenAI.

Ventajas:
- Menor complejidad en el backend principal.
- Permite escalar y versionar tools sin tocar núcleo del chatbot.
- Cache y control de acceso localizados en el servidor MCP.

Estado actual (2025-11-19):
- ✅ MCP Products Server implementado y funcional (`mcp_servers/products_server`).
- ✅ Tools `get_product_info` y `get_product_full_info` definidas y operativas.
- ❌ **Bloqueador**: Router síncrono impide uso correcto de `chat_with_tools` asíncrono.
- ⚠️ Endpoint `/chat` usa fallback a `price_lookup.py` (funcional pero no escala).
- ⚠️ `price_lookup.py` marcado como DEPRECATED pero aún en uso activo.
- ⏸️ Pendiente migrar WebSocket (`ws.py`) y Telegram (`telegram.py`) tras resolver problema de sincronía.

Próximos pasos (parte de Etapa 0):
- Convertir `AIRouter.run` a asíncrono (`async def`).
- Implementar `generate_async` en `OpenAIProvider` con inyección dinámica de tools según rol.
- Actualizar endpoints consumidores para usar `await router.run(...)`.
- Sincronizar esquemas JSON de tools entre provider y MCP.
- Extraer parsing residual a módulo liviano independiente de legacy.
- Eliminar funciones no usadas en `price_lookup.py` tras migrar canales restantes.
- Añadir nuevas tools (métricas de ventas, proveedores relacionados, equivalencias SKU) siguiendo el contrato MCP.

Configuración:
- Variable `MCP_PRODUCTS_URL` (default `http://mcp_products:8001/invoke_tool`); alinear con `docker-compose.yml` si el puerto expuesto difiere.
- `OPENAI_API_KEY` requerida para habilitar tool-calling cuando `ai_allow_external=true`.

Seguridad y permisos:
- `get_product_full_info` restringido a roles `admin|colaborador` (validado tanto en schema dinámico como en el MCP).
- Próxima iteración: token firmado y auditoría de invocaciones de tools.

Deprecación:
- Evitar agregar nueva lógica a `price_lookup.py`.
- Documentar en cada PR la eliminación progresiva de funciones legacy.

