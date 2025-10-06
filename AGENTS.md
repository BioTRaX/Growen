<!-- NG-HEADER: Nombre de archivo: AGENTS.md -->
<!-- NG-HEADER: Ubicación: AGENTS.md -->
<!-- NG-HEADER: Descripción: Lineamientos para agentes de desarrollo -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Lineamientos para agentes de desarrollo

Este documento orienta a herramientas de asistencia de código (Copilot, Codex, Gemini, etc.) sobre cómo interactuar con este repositorio. No aplica a agentes internos de la aplicación.

## Idioma obligatorio
- Todas las respuestas y mensajes generados por agentes deben ser en español (tono claro y profesional latinoamericano). Si el usuario escribe en otro idioma, el agente puede citar fragmentos, pero la respuesta debe mantenerse en español.

## Estructura de prompt obligatoria
1. **Contexto**
2. **Observaciones**
3. **Errores y/u outputs**
4. **Objetivo**
5. **Propuesta de código o pasos**
6. **Criterios de aceptación** (siempre exigir "documentar los cambios y actualizar si algo está desactualizado")

## Estándares de entrega
- Código listo para revisión, con pruebas cuando apliquen.
- Mensajes de commit claros y en español.
- Documentar cambios de esquema o infraestructura.
- No introducir dependencias sin documentarlas y agregarlas a los requirements/README.
 - Mantener documentación viva: actualizar `Roadmap.md`, `README.md` y docs bajo `docs/` cuando cambien comportamientos, endpoints, modelos, flujos o requisitos de entorno. Toda interacción de agentes debe verificar y actualizar estos documentos (incluyendo este Roadmap) como parte de la entrega.

## Encabezado obligatorio (NG-HEADER)
Agregar al inicio de cada archivo de código y documentación `.md` (excepto `README.md`). Excepciones: `*.json`, `destinatarios.json`, binarios, imágenes, PDFs y otros archivos de datos.

Formato por lenguaje:

### Python
```py
#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### TypeScript/JavaScript
```ts
// NG-HEADER: Nombre de archivo: <basename>
// NG-HEADER: Ubicación: <ruta/desde/la/raiz>
// NG-HEADER: Descripción: <breve descripción>
// NG-HEADER: Lineamientos: Ver AGENTS.md
```

### Bash
```bash
#!/usr/bin/env bash
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### YAML / Dockerfile
```yaml
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```
```dockerfile
# NG-HEADER: Nombre de archivo: <basename>
# NG-HEADER: Ubicación: <ruta/desde/la/raiz>
# NG-HEADER: Descripción: <breve descripción>
# NG-HEADER: Lineamientos: Ver AGENTS.md
```

### HTML / CSS
```html
<!-- NG-HEADER: Nombre de archivo: <basename> -->
<!-- NG-HEADER: Ubicación: <ruta/desde/la/raiz> -->
<!-- NG-HEADER: Descripción: <breve descripción> -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
```
```css
/* NG-HEADER: Nombre de archivo: <basename> */
/* NG-HEADER: Ubicación: <ruta/desde/la/raiz> */
/* NG-HEADER: Descripción: <breve descripción> */
/* NG-HEADER: Lineamientos: Ver AGENTS.md */
```

### Markdown de documentación
```md
<!-- NG-HEADER: Nombre de archivo: <basename> -->
<!-- NG-HEADER: Ubicación: <ruta/desde/la/raiz> -->
<!-- NG-HEADER: Descripción: <breve descripción> -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
```

## Buenas prácticas para agentes
- Confirmar impacto de cambios (migraciones, variables de entorno, dependencias nativas).
- Dejar notas de migración cuando corresponda.
- Adjuntar ejemplos mínimos de uso y pruebas cuando sea razonable.
- Mantener consistencia de idioma en commits, PRs y documentación: español.

## Checklist para cada PR generado por un agente
- [ ] Se agregó/actualizó encabezado NG-HEADER cuando corresponde.
- [ ] Se actualizaron docs afectadas.
- [ ] Se listaron dependencias nuevas y prerequisitos.
- [ ] Se agregaron o actualizaron tests si aplica.
- [ ] Si la PR toca catálogo PDF (`/catalogs/*`), verificar sección "Catálogo (PDF)" (histórico, retention, endpoints) y mantener la limpieza de logs.

## Inventario de scripts (carpeta `scripts/`)

Referencia rápida para agentes: qué hace cada script, cuándo usarlo y precauciones. Evitar duplicar funcionalidad antes de revisar aquí.

### Diagnóstico / Migraciones / DB
- `check_schema.py`: Lista columnas clave y versiones Alembic presentes. Útil antes/después de migraciones.
- `debug_migrations.py`: Reporte de `alembic current`, `heads`, `history`; alerta si hay múltiples heads.
- `merge_heads_and_stamp.py`: Consolida múltiples heads hacia un merge ya existente (no genera archivo). Uso cuando `alembic` sigue mostrando múltiples heads tras crear migración de merge.
- `stamp_head_manual.py`: Fuerza la versión en `alembic_version` (acepta `TARGET_HEAD`). Uso excepcional (recuperación). Prefiere merge real.
- `db_check.py`: Verificaciones básicas de conexión / latencia (si aplica) (pendiente de ampliar si se requiere).
- `db_diag.py`: Diagnóstico más extenso (consultas adicionales o checks; revisar contenido antes de usar en producción).
- `db_port_probe.py`: Chequea disponibilidad del puerto DB (detección rápida de servicio caído o firewall local).
- `debug_migrations.py`: (Listado nuevamente para énfasis) No modificar sin actualizar `docs/MIGRATIONS_NOTES.md`.

### Administración de usuarios / seguridad básica
- `check_admin_user.py`: Verifica que el usuario admin exista.
- `seed_admin.py`: Crea usuario admin si falta (idempotente). Revisar credenciales en `.env`.
- `test_login_flow.py`: Prueba automatizada (smoke) del flujo de login (útil antes de despliegues).

### Logs / Limpieza
- `cleanup_logs.py`: Limpieza específica de archivos de log antiguos o rotaciones (confirmar política antes de ejecutar en producción).
- `clear_backend_log.py`: Vacía/rota `backend.log`.
- `clear_logs.py`: Limpieza más amplia (ver código antes de usar para evitar pérdida accidental).
- `stop_ports.ps1`: Intenta liberar puertos ocupados (útil tras cierres abruptos).

### Backend / Arranque / Entorno
- `run_api.cmd` / `run_frontend.cmd` / `start_stack.ps1` / `start_worker_images.cmd`: Scripts de conveniencia para iniciar servicios locales.
- `launch_backend.cmd`: Variante de arranque rápido backend (revisar duplicidad con `run_api.cmd`).
- `start.bat` / `stop.bat`: Atajos globales de inicio/parada.
- `start_worker_images.cmd`: Lanza worker de procesamiento de imágenes (ver dependencias en README o `docs/IMAGES.md`).

### Mantenimiento dependencias
- `fix_deps.bat`: Reparación / reinstalación de dependencias Python (consultar log `logs/fix_deps.log`).
- `generate_requirements.py`: Regenera `requirements.txt` (revisar antes de commitear; mantener orden y comentar si se añaden libs nuevas).

### Parches / Migraciones de datos puntuales
- `patch_add_identifier.py`: Agrega/normaliza identificadores en usuarios (una sola vez). Documentar si se reutiliza.
- `patch_summary_json.py`: Ajusta/crea campo `summary_json` en jobs de import (ver `docs/IMPORT_PDF.md`).
- `upload_debug_import.py`: Carga/ensayo para importar un archivo PDF de prueba (herramienta de depuración).
- `smoke_import_commit.py`: Prueba de flujo de importación (commit final) para garantizar que endpoints clave siguen funcionando.

### BOM / Encoding / Formato
- `fix_bom.ps1`: Quita BOM en archivos que puedan romper imports o tooling.

### Servicios / Scheduler / Monitoreo
- (Pendiente de centralizar) Scripts relacionados a `services` si se añaden: mantener aquí enumeración.

### Notas de uso para agentes
- Antes de crear un nuevo script, validar si la funcionalidad ya existe.
- Si un script modifica datos (parches), debe:
	1. Estar documentado en la PR.
	2. Tener explicación breve de idempotencia.
	3. Incluir salida clara (print) de acciones realizadas y elementos afectados.
- Actualizar esta sección y `docs/MIGRATIONS_NOTES.md` si el script toca migraciones.

### Scripts a revisar / mejorar (backlog sugerido)
- Consolidar `run_api.cmd` y `launch_backend.cmd` si son redundantes.
- Añadir script unificado `status_stack.py` que consulte salud de API, worker, frontend, DB.
- Agregar test automatizado (pytest) para validar integridad mínima de scripts críticos (ej. parseo de `alembic history`).

---
Actualizado inventario scripts: 2025-09-13.

## MCP Servers (Nueva capa de herramientas para IA)

Esta sección documenta lineamientos para crear y mantener microservicios bajo `mcp_servers/` orientados a exponer "tools" consumibles por agentes LLM mediante un contrato uniforme.

### Objetivos
- Separar preocupaciones: cada MCP Server actúa como fachada de dominio (productos, compras, ventas, etc.).
- Evitar acceso directo a la base: siempre consumir la API principal (`api`) vía HTTP.
- Control de acceso basado en roles (parámetro `user_role` en MVP; evolucionará a autenticación/verificación tokenizada).

### Estructura mínima de un MCP Server
```
mcp_servers/
	<domain>_server/
		__init__.py
		main.py          # FastAPI/Flask app con endpoint POST /invoke_tool
		tools.py         # Implementación de funciones async registradas
		requirements.txt # Dependencias aisladas (no mezclar con raíz salvo necesidad)
		Dockerfile       # Imagen autocontenida (usa red compartida con api)
		README.md        # Propósito, tools, ejemplos de uso
		tests/           # Pruebas (unit + integración con mocks httpx/respx)
```

### Convenciones de Tools
- Firma recomendada: `async def <name>(... , user_role: str) -> dict`.
- Validar inputs y roles temprano; lanzar `PermissionError` (subclase de `ValueError`) para mapear a 403.
- Retornar dict plano serializable (sin objetos ORM ni tipos complejos).
- Mantener TOOLS_REGISTRY en `tools.py` para despacho dinámico.

### Endpoint estándar
- `POST /invoke_tool` recibe `{ "tool_name": str, "parameters": { ... } }`.
- Respuesta `{ "tool_name": str, "result": { ... } }` o error HTTP:
	- 400 validación parámetros
	- 403 permiso insuficiente
	- 404 tool desconocida
	- 502 error upstream (API principal) / red

### Roles y Seguridad
- MVP: confianza en parámetro `user_role` (solo para prototipo interno).
- Próximos pasos obligatorios antes de exponer externamente:
	- Token firmado (HMAC o JWT) con claims de rol y expiración.
	- Lista blanca de tools por rol y rate limiting por IP/rol.
	- Auditoría de cada invocación (`tool_name`, latencia, rol, éxito/error).

### Tests
- Unit: validación de roles y shape de respuesta (mock de red cuando sea necesario).
- Integración: uso de `respx` para mockear endpoints de la API principal y simular latencias y códigos de error.
- Futuros: contract tests para garantizar estabilidad de payload al añadir campos nuevos (estrategia additive-only v1).

### Documentación
- Actualizar `Roadmap.md` al introducir nuevo MCP Server.
- Añadir sección en README raíz cuando la capa crezca (diagrama arquitectura actualizado).
- Anotar herramientas disponibles y roles requeridos en `docs/roles-endpoints.md` cuando salgan del estado MVP.

### Observabilidad (futuro)
- Métricas: invocaciones por tool, latencia p50/p95, tasa de error, top SKUs consultados, cache hit ratio.
- Logs estructurados JSON con `tool_name`, `role`, `elapsed_ms`, `status`.
- Circuit breakers / retry con backoff para HTTP hacia API principal.

### Ejemplo implementado (MVP)
- `mcp_servers/products_server`: tools `get_product_info` y `get_product_full_info` (roles admin|colaborador para la segunda) exponiendo datos de primer nivel de productos.

---
Actualizado MCP Servers: 2025-10-06.

