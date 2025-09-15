<!-- NG-HEADER: Nombre de archivo: CHANGELOG.md -->
<!-- NG-HEADER: Ubicación: CHANGELOG.md -->
<!-- NG-HEADER: Descripción: Historial de cambios y dependencias añadidas -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->
# Changelog

## [Unreleased]
- deps: agregado `onnxruntime` a `requirements.txt` para soporte completo de `rembg` (background removal) y documentadas dependencias del sistema (Tesseract, Ghostscript, QPDF) en `docs/dependencies.md`.
- docs: expandido `docs/dependencies.md` para incluir playwright, tenacity, onnxruntime y pasos de validación/instalación de binarios.
- ai: reemplazado stub de `OllamaProvider` por integración HTTP real (streaming opcional) con daemon Ollama (`/api/generate`).
- docs: nuevo `docs/ollama.md` con instrucciones de instalación y variables de entorno para LLM local.
- db/migrations: ampliado manejo de `alembic_version.version_num` creando la tabla manualmente con `VARCHAR(255)` para evitar `StringDataRightTruncation` al insertar revisiones largas (fix env.py).
- db/migrations/env.py: ahora fuerza `version_table_column_type=String(255)` y realiza preflight `_ensure_alembic_version_column` robusto (crea o altera según corresponda) antes de correr migraciones.
- db/migrations/env.py: logging mejorado (archivo por corrida, DB_URL ofuscado, historial de heads reciente) y `load_dotenv(..., override=True)` para asegurar consistencia de `DB_URL`.
- db/migrations/versions/20241105_auth_roles_sessions.py: eliminado abort estricto por placeholder de `ADMIN_PASS`; se agregó fallback seguro, carga explícita de `.env` y hash Argon2 con import local defensivo.
- scripts: agregado `scripts/check_admin_user.py` para verificación rápida post-migraciones del usuario admin.
- scripts/seed_admin.py: mensaje de advertencia si `ADMIN_PASS` es placeholder y creación idempotente del usuario admin.
- docs: documentado flujo de recuperación de migraciones rotas por longitud de `alembic_version` y placeholder de `ADMIN_PASS` (ver nuevo archivo `docs/MIGRATIONS_NOTES.md`).

- ui(compras): dropdown "Cargar compra" con estilos dark consistentes.
- ui(compras): nuevo PdfImportModal (proveedor obligatorio → subir PDF → procesar) que navega al borrador creado.
- ui(compras): flujo Manual rehecho: encabezado + grilla de líneas editable (sku prov., título, cantidad, costo unitario, % desc., nota).
- ui(compras): se eliminó cualquier acción de importar PDF de la vista Manual.
- feat(compras): guardar como BORRADOR desde la vista Manual (POST /purchases) y actualizaciones posteriores con PUT /purchases/{id}; toasts y validaciones básicas.
- feat: drag & drop, tema oscuro en buscador y modal de subida más robusto
- Add: upload UI (+), dry-run viewer, commit
- Add: productos canónicos y tabla de equivalencias
- Add: middleware de logging, endpoints `/healthz` y `/debug/*`, SQLAlchemy con `echo` opcional.
- Add: endpoints `GET/PATCH /canonical-products/{id}`, listado y borrado de `/equivalences`
- Add: comparador de precios `GET /canonical-products/{id}/offers` con mejor precio marcado
- Add: modo oscuro básico en el frontend
- Add: plantilla Excel por proveedor `GET /suppliers/{id}/price-list/template`
- Add: plantilla Excel genérica `GET /suppliers/price-list/template`
- fix: restaurar migración `20241105_auth_roles_sessions` renombrando archivo y `revision` para mantener la cadena de dependencias
- fix: evitar errores creando o borrando tablas ya existentes en `init_schema` mediante `sa.inspect`
- Add: componentes `CanonicalForm` y `EquivalenceLinker` integrados en `ImportViewer` y `ProductsDrawer`
- dev: valores por defecto inseguros para SECRET_KEY y ADMIN_PASS en `ENV=dev` (evita fallos en pruebas)
- deps: incluir `aiosqlite` para motor SQLite asíncrono
- dev: en ausencia de sesión y con `ENV=dev` se asume rol `admin` para facilitar pruebas
- fix: corregir comillas en `scripts/start.bat` y `start.bat` para rutas con espacios
- fix: soporte de `psycopg` asíncrono en Windows usando `WindowsSelectorEventLoopPolicy`
- fix: migración idempotente que agrega `users.identifier` si falta y actualiza el modelo
- fix: formulario de login centrado y autenticación/guest integrados con `AuthContext`

## [0.2.0] - 2025-09-12

### Added
- purchases: respuesta `confirm` con `applied_deltas` (debug=1) para trazabilidad de stock.
- purchases: bloqueo estricto opcional (env `PURCHASE_CONFIRM_REQUIRE_ALL_LINES`) cuando hay líneas sin vincular.
- admin: nuevo layout `/admin` con secciones Servicios, Usuarios, Imágenes y Health unificadas.
- admin/services: chequeo (`/deps/check`) e instalación (`/deps/install`) de dependencias opcionales (playwright, pdf OCR stack).
- images: stream SSE de logs/progreso (`/admin/image-jobs/logs/stream`) y cálculo de % progreso.
- import(SantaPlanta): heurísticas SKU (tokens numéricos), fallback camelot/pdfplumber + OCR mejorado, eventos detallados y retry.
- health: endpoints enriquecidos (`/health/service/*`, `/health/summary`) con reporte por servicio opcional y storage/redis/db/AI.
- services: util frontend `ensureServiceRunning` para espera idempotente de estado running.
- auth: endpoint para eliminar usuario con audit (DELETE `/auth/users/{id}`).
- scripts: herramienta `tools/clear_db_logs.py` para purgar tablas de logs; registro de tarea startup PowerShell.

### Changed
- orchestrator: detección robusta de Docker (verifica engine con `docker info`) y normalización de estados (running/starting/degraded).
- image jobs: endpoint `status` agrega objeto `progress` (total, pending, processed, percent).
- pipeline import: sanitización de `TESSDATA_PREFIX` y fallback heurístico de filas cuando no se detectan tablas estructuradas.
- start.bat: mensajes internacionalizados (acentos), build condicional frontend y manejo mejorado de Redis ausente.
- health summary: incluye mapa `services` con estado individual.

### Fixed
- import: múltiples mejoras de resiliencia frente a PDFs sin texto y paths OCR.
- purchases: sanitización de mensajes Unicode y logs por línea (`old_stock + delta -> new`).
- UI: carga de sección Stock tras invalidación de chunks (nueva build hash) al mejorar build flow.

### UI / UX
- Tema oscuro refinado (contraste placeholders, muted text) y toasts apilados (info/success/warning) con per-product delta.
- Panel de imágenes: modo Live (SSE) y barra de progreso animada.
- Panel de servicios: integra panel de health + logs streaming.
- PurchaseDetail: toasts por producto con incremento de stock y aviso de líneas sin vincular.

### Chore / Dev
- Documentación interna con docstrings en routers (purchases, health, services_admin, image_jobs, import pipeline).
- Limpieza y normalización de mensajes en scripts y logs.

---

