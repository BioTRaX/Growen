<!-- NG-HEADER: Nombre de archivo: HANDOFF_SIYUAN_AGENTIC_20260828.md -->
<!-- NG-HEADER: Ubicación: docs/HANDOFF_SIYUAN_AGENTIC_20260828.md -->
<!-- NG-HEADER: Descripción: Handoff operativo para continuar SiYuan y la evolución del entorno agéntico. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Handoff: SiYuan y entorno agéntico

## Contexto

Growen integra SiYuan como portal documental offline-first y Git como fuente de verdad técnica. La integración MCP expone tools de lectura y creación controlada mediante STDIO para Codex y Streamable HTTP para el entorno Docker.

## Estado confirmado

- Rama de trabajo: `dev`.
- SiYuan v3.8.1 configurado en `127.0.0.1:6806`.
- MCP HTTP configurado en `127.0.0.1:8104`.
- Workspace persistente fuera del repositorio: `../growen-siyuan/workspace`.
- Secretos fuera del repositorio: `../growen-secrets`.
- Notebook configurado: `Nice Grow`.
- Prefijo permitido de escritura: `/Growen`.
- Codex STDIO configurado con `.venv\Scripts\python.exe`.
- Publicación inicial create-only ejecutada: 32 documentos creados y 50 omitidos por colisión.
- `Roadmap.md` contiene pendientes/futuro; el histórico está en `docs/archive/ROADMAP_HISTORY.md`.

## MCP SiYuan

Ubicación: `mcp_servers/siyuan_server/`

Tools disponibles:

- `list_siyuan_notebooks()`
- `search_siyuan_docs(query, limit=20)`
- `read_siyuan_document(document_id)`
- `create_siyuan_document(path, markdown)`

Restricciones relevantes:

- Header SiYuan: `Authorization: Token <token>`.
- Lecturas con timeout de 10 segundos y un reintento.
- Escrituras sin reintento.
- Sin SQL libre, actualización, movimiento ni eliminación.
- Las rutas deben estar bajo `/Growen` y no pueden contener `..`.
- Las escrituras son create-only y rechazan colisiones.

## Evolución agéntica implementada

- La skill `.agents/skills/retrospectiva-tecnica-sesion/SKILL.md` exige materializar una mejora agéntica autorizada, no sólo proponerla.
- `scripts/audit_agentic_environment.py` valida gobernanza, skills canónicas, frontmatter y adaptadores legacy.
- `scripts/check-quality.ps1 -AgentOnly` invoca el auditor.
- `tests/test_audit_agentic_environment.py` cubre caso válido y regresión de gobernanza.
- `docs/AGENT_SKILLS.md` documenta el auditor y su contrato.

## Último commit publicado

Commit: `f0e0e1d` — `feat: integra SiYuan MCP y sanea documentación`.

Fue publicado en `origin/dev`. No asumir que el worktree actual coincide con ese commit: posteriormente aparecieron cambios adicionales.

## Estado del worktree al preparar este handoff

Hay cambios posteriores al último commit en múltiples áreas, incluyendo:

- `mcp_servers/siyuan_server/`
- `scripts/publish_docs_to_siyuan.py`
- `scripts/smoke_siyuan_mcp.py`
- `scripts/check-quality.ps1`
- `scripts/audit_agentic_environment.py`
- `services/market/`
- `frontend/` y `frontend-vue/`
- migraciones y documentación

También hay archivos nuevos relacionados con pipeline de Mercado y una base de tareas SiYuan. Deben revisarse antes de hacer stage o commit.

## Validación pendiente

El host rechazó la ejecución de procesos externos por límite de uso, por lo que la nueva validación dinámica quedó pendiente. No usar Python del sistema como sustituto.

Ejecutar cuando el host esté disponible:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_audit_agentic_environment.py -q
.\.venv\Scripts\python.exe -m pytest mcp_servers\siyuan_server\tests -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-quality.ps1 -AgentOnly
git diff --check
```

Validación SiYuan opcional:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_siyuan_mcp.py
.\.venv\Scripts\python.exe scripts\publish_docs_to_siyuan.py
```

## Próximos pasos recomendados

1. Revisar los cambios posteriores al commit y distinguirlos de los cambios propios de la próxima entrega.
2. Ejecutar las pruebas con la venv y corregir el espacio final detectado en `frontend-vue/src/modules/images/views/ProductImagesView.vue` si continúa presente.
3. Auditar secretos sin imprimir valores.
4. Revisar la documentación nueva de Mercado y su migración antes de publicar.
5. Si el usuario autoriza publicación, usar la skill `git-commit-push`, confirmar rama `dev`, auditar alcance y publicar sólo después del quality gate.

## Reglas de continuidad

- Responder siempre en español.
- Ejecutar Python y pytest únicamente con `.venv\Scripts\python.exe` o Docker.
- No exponer secretos ni incluir archivos reales de `.env`.
- No ejecutar `git add`, commit o push sin autorización explícita.
- Mantener `README.md`, `Roadmap.md` y `docs/` actualizados.
- No declarar pruebas exitosas si el host no permitió ejecutarlas.
