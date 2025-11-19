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

### Seguridad de secretos (OBLIGATORIO)
- Nunca commits con credenciales, tokens o URLs con usuario:contraseña. Usar variables de entorno (`.env`, `env_file`) o placeholders en docs.
- Revisar `.gitignore` antes de crear scripts con parámetros sensibles; si el script requiere credenciales locales, proveer `*.example.ps1` y agregar el real al `.gitignore`.
- Si se detecta exposición accidental, remover inmediatamente el archivo del repo, reemplazar por versión sin secretos y comunicar para rotar las credenciales expuestas.

### Operativa de Git para agentes
- Evitar `git add`, `commit` y `push` salvo que el usuario lo solicite explícitamente. Priorizar PRs y revisiones.

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

## Workflow de Desarrollo (LOCAL primero, DOCKER para producción)

**Filosofía**: Desarrollar en local es 10x más rápido que recompilar Docker constantemente. Reservar Docker para testing de integración y producción.

**Flujo Recomendado**:
1. **Desarrollo diario**: API local + DB Docker (solo infraestructura)
   - Hot reload instantáneo (~1s vs 3-5 min rebuild)
   - Debugging directo (pdb, breakpoints)
   - Logs en tiempo real
2. **Testing integración**: Docker Compose completo (antes de merge)
3. **Producción**: Docker (idéntico a testing)

**Comandos esenciales desarrollo**:
```powershell
# Infra en Docker (una vez al día)
docker compose up -d db

# API local con hot reload
python -m uvicorn services.api:app --reload --port 8000

# Frontend local
cd frontend && npm run dev
```

**Cuándo SÍ recompilar Docker**:
- ✅ Nuevas dependencias en `requirements.txt`
- ✅ Cambios en `Dockerfile.*` o `docker-compose.yml`
- ✅ Antes de merge a main
- ✅ Deploy a producción

**Cuándo NO recompilar Docker**:
- ❌ Cambios en lógica Python/TypeScript (usa local con hot reload)
- ❌ Debugging de features nuevas
- ❌ Probar endpoints o UI

**Documentación completa**: `docs/DEVELOPMENT_WORKFLOW.md` (setup, tips, troubleshooting, comparación velocidades)

## Documentación contextual según tarea

Antes de realizar cualquier cambio, el agente DEBE consultar la documentación relevante según el contexto de la tarea:

### Por tipo de componente/sistema

| Tarea/Sistema | Documentos a consultar (orden de prioridad) |
|---------------|---------------------------------------------|
| **Base de datos / Modelos** | `docs/MIGRATIONS_NOTES.md`, `db/models.py`, `alembic/versions/` |
| **API / Endpoints** | `services/api.py`, `services/routers/*.py`, documentos específicos en `docs/API_*.md` |
| **Workers / Jobs asíncronos** | `docs/IMAGES.md`, `docs/API_MARKET.md`, `workers/*.py`, `services/jobs/*.py` |
| **Frontend / UI** | `frontend/src/**`, `docs/FRONTEND_DEBUG.md`, `docs/PRODUCTS_UI.md` |
| **Autenticación / Seguridad** | `docs/SECURITY.md`, `docs/CHATBOT_ROLES.md`, `services/auth.py` |
| **Docker / Infraestructura** | `docker-compose.yml`, `infra/Dockerfile.*`, sección "Convenciones Docker" en este archivo |
| **Tests** | `pytest.ini`, `tests/**`, sección correspondiente en `docs/` |
| **Scraping / Precios de mercado** | `docs/API_MARKET.md`, `workers/market_scraping.py`, `services/jobs/market_scheduler.py` |
| **Imágenes de productos** | `docs/IMAGES.md`, `docs/MEDIA.md`, `services/media/`, `workers/images.py` |
| **Importación PDF** | `docs/IMPORT_PDF.md`, `docs/IMPORT_PDF_AI_NOTES.md`, `services/routers/imports.py` |
| **Catálogos** | `docs/CATALOGS_OPERATIONS.md`, `services/routers/catalog.py` |
| **Clientes / Ventas** | `docs/SALES.md`, `services/routers/sales.py`, `services/routers/customers.py` |
| **Compras / Proveedores** | `docs/PURCHASES.md`, `docs/SUPPLIERS.md`, `services/routers/purchases.py` |
| **Chat / IA** | `docs/CHAT.md`, `docs/CHATBOT_ARCHITECTURE.md`, `docs/CHAT_PERSONA.md`, `ai/` |
| **MCP Servers** | `docs/MCP.md`, `mcp_servers/`, sección "MCP Servers" en este archivo |

### Por tipo de operación

| Operación | Documentos clave |
|-----------|------------------|
| **Migración de BD** | Leer `docs/MIGRATIONS_NOTES.md` ANTES de crear/modificar migraciones. Revisar `scripts/debug_migrations.py` |
| **Nuevo endpoint admin** | `docs/roles-endpoints.md`, `services/routers/services_admin.py` o similar como referencia |
| **Nuevo worker Dramatiq** | `docs/IMAGES.md` (referencia workers), `workers/market_scraping.py` (plantilla), verificar config Redis |
| **Cambio en modelos** | `db/models.py`, luego `alembic revision --autogenerate -m "descripción"`, actualizar `docs/MIGRATIONS_NOTES.md` |
| **Nuevo servicio Docker** | Revisar sección "Convenciones Docker" en este archivo, usar multi-stage builds |
| **Problema de conexión DB** | Verificar patrón: `DB_URL = os.getenv("DB_URL") or settings.db_url` (ver corrección 2025-11-15) |

### Documentos de arquitectura general

- **Roadmap.md**: Estado general del proyecto, features completadas/pendientes, deuda técnica
- **README.md**: Setup inicial, requisitos, comandos básicos
- **CONTRIBUTING.md**: Convenciones de código, flujo de desarrollo
- **CHANGELOG.md**: Historial de cambios importantes

### Patrón crítico: DB_URL en Docker (Lección 2025-11-15)

**PROBLEMA COMÚN**: Hardcodear fallback de `DB_URL` causa errores en contenedores Docker que usan PostgreSQL.

**❌ Incorrecto** (falla en Docker con Postgres):
```python
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./growen.db")
engine = create_async_engine(DB_URL, future=True)
```

**✅ Correcto** (funciona local y en Docker):
```python
from agent_core.config import settings

DB_URL = os.getenv("DB_URL") or settings.db_url
engine = create_async_engine(DB_URL, future=True)
```

**Razón**: En `docker-compose.yml` se setea `DB_URL: ""` (vacío) para que `settings.db_url` construya la URL desde `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`.

**Archivos que deben usar este patrón**:
- `workers/*.py`
- `services/jobs/*.py`
- Cualquier módulo que cree su propio engine SQLAlchemy

**Referencia**: Ver `db/session.py` como implementación canónica.

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
- `cleanup-docker-images.ps1`: Identifica y elimina interactívamente imágenes Docker dangling o no usadas (requiere confirmación explícita, soporta -DryRun y -PerImageConfirm). Uso: mantenimiento de espacio en disco evitando eliminar imágenes en uso.

### Auditoría / Compose
- `docker-compose-audit.ps1`: Audita `docker-compose.yml`, detecta imágenes públicas con tags desactualizados, permite actualizar versiones (con backup) y reconstruir/levantar el stack (`docker compose up --build -d`). Parámetros: `-OnlyReport`, `-SkipBuild`.

### Backend / Arranque / Entorno
- `run_api.cmd` / `run_frontend.cmd` / `start_stack.ps1`: Scripts de conveniencia para iniciar servicios locales.
- `launch_backend.cmd`: Variante de arranque rápido backend (revisar duplicidad con `run_api.cmd`).
- `start.bat` / `stop.bat`: Atajos globales de inicio/parada.

### Workers / Jobs Asíncronos (Dramatiq + Redis)
- `start_worker_images.cmd`: Lanza worker de procesamiento de imágenes (cola `images`). Ver dependencias en README o `docs/IMAGES.md`.
- `start_worker_market.cmd`: Lanza worker de scraping de precios de mercado (cola `market`). Requiere Redis. Ver `docs/API_MARKET.md`.
- `start_worker_all.cmd`: Lanza worker unificado que procesa ambas colas (`images` + `market`) con 3 threads. Uso recomendado para entornos con recursos limitados.
  - Sintaxis: `start_worker_all.cmd [images|market|all]` (default: `all`)
  - Logs: `logs/worker_all.log` (modo `all`), `logs/worker_images.log` o `logs/worker_market.log` (modo específico)
  - Requiere `REDIS_URL` configurado (default: `redis://localhost:6379/0`)

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
Actualizado inventario scripts: 2025-10-07.

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

## Convenciones Docker (Imágenes de Servicios)

Esta sección establece pautas para la construcción de imágenes Docker en el repositorio:

1. Multi-stage obligatorio para servicios Python y frontend: separar `builder` (toolchain, wheel builds) de `runtime` (mínimo). Evita arrastrar compiladores a producción.
2. Base Python: usar `python:3.13-slim-bookworm` salvo requerimiento puntual distinto. Justificar cambios de versión / distro en la PR.
3. Usuario no root: crear usuario del sistema (`app`) y ejecutar procesos con privilegios mínimos.
4. Virtualenv aislado en `/opt/venv` y añadir a `PATH`. No instalar dependencias globales en system site-packages.
5. Limpieza de capas: remover listas de APT (`rm -rf /var/lib/apt/lists/*`) y usar `--no-install-recommends`.
6. Dependencias de build vs runtime: instalar toolchain (gcc, build-essential, headers) sólo en la etapa builder; en runtime incluir únicamente librerías compartidas requeridas (ej. cairo, pango, gdk-pixbuf para weasyprint, opencv runtime si aplica).
7. Healthcheck: incluir `HEALTHCHECK` HTTP (ej. `curl -fsS http://127.0.0.1:PORT/health || exit 1`). Si no existe endpoint `/health`, fallback documentado (`/docs` ver ejemplo en Dockerfile.api) hasta que se implemente.
8. Determinismo: preferir `pip install -r requirements.txt` con versiones mínimas declaradas; opcional futuro: generar `requirements-lock.txt` (hashes) usando `pip-compile`.
9. Seguridad: no copiar `.env` ni archivos con secretos dentro de la imagen. Consumir variables sólo en runtime (`docker-compose.yml` / orquestador).
10. Tamaño: evaluar uso de `--strip` en compilaciones personalizadas y limpiar caches temporales (ej. modelos descargados) si no son requeridos en runtime.

Próximos pasos sugeridos:
- Introducir endpoint uniforme `/health` en todos los servicios.
- Implementar stage opcional de tests (`FROM builder as tester`) que ejecute `pytest` antes de pasar a runtime en CI.
- Generar métricas de tamaño comparativo antes/después de optimizaciones (documentar en `docs/PERFORMANCE.md`).

Actualizado Convenciones Docker: 2025-10-09.

