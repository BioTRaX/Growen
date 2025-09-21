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
