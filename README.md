# Growen

## Documentacion

- Hoja de ruta: [Roadmap.md](./Roadmap.md)
- Capa MCP (servers/tools): [docs/MCP.md](./docs/MCP.md)
- Arquitectura chatbot admin: [docs/CHATBOT_ARCHITECTURE.md](./docs/CHATBOT_ARCHITECTURE.md)
- Roles del chatbot admin: [docs/CHATBOT_ROLES.md](./docs/CHATBOT_ROLES.md)
- Compras (incluye iAVaL - Validador de IA del remito): [docs/PURCHASES.md](./docs/PURCHASES.md)
- Persona de chat: [docs/CHAT_PERSONA.md](./docs/CHAT_PERSONA.md)
- SKU Canónico (formato, generación, secuencias): [docs/CANONICAL_SKU.md](./docs/CANONICAL_SKU.md)

## Chatbot Growen

- Growen responde en espanol rioplatense con tono malhumorado, humor negro y sarcasmo directo.
- Solo cubre temas de Nice Grow: catalogo, promociones, servicios y consejos de cultivo; desvia con ironia cualquier consulta ajena al rubro.
- Mantiene limites de seguridad: nada de insultos personales, discursos de odio ni llamados a la violencia.
- Cuando una consulta de precio coincide con varios productos, pide al usuario que aclare la opcion antes de informar montos (flujo legacy en deprecación).
- Migración en curso: consultas de producto en `/chat` ahora usan tool-calling (OpenAI → `mcp_products`) para obtener datos consistentes y cacheados; módulo `price_lookup.py` marcado DEPRECATED.
- Evolución próxima: chatbot corporativo diferenciado por roles con auditoría y acceso al repositorio controlado (ver documentación de arquitectura y roles).

## Endpoints clave (checklist rapido)

- Autenticacion
  - `POST /auth/login`: inicio de sesion
  - `GET /auth/me`: info de sesion actual

- Compras
  - `GET /purchases`: listar (filtros y paginacion)
  - `POST /purchases`: crear (BORRADOR)
  - `GET /purchases/{id}`: detalle con lineas y adjuntos
  - `PUT /purchases/{id}`: actualizar encabezado + lineas (upsert/delete)
  - `POST /purchases/{id}/validate`: validar (marca lineas OK/SIN_VINCULAR)
  - `POST /purchases/{id}/confirm`: confirmar (impacta stock y precios)
  - `POST /purchases/{id}/cancel`: anular (revierte stock si corresponde)
  - `GET /purchases/{id}/logs`: auditoria e import logs
  - `GET /purchases/{id}/attachments/{att}/file`: descargar adjunto inline
  - `POST /purchases/import/santaplanta`: importar PDF (pipeline OCR con dedupe)

- Admin / Servicios
  - `GET /admin/services`: listar servicios y estado
  - `GET /admin/services/{name}/status`: estado puntual
  - `POST /admin/services/{name}/start|stop`: control de servicio
  - `GET /admin/services/{name}/logs`: ultimos N logs
  - `GET /admin/services/{name}/logs/stream`: SSE de logs
  - `GET /admin/services/{name}/deps/check`: chequeos de deps
  - `POST /admin/services/{name}/deps/install`: instalar deps (dev)

- Imagenes / Crawler
  - `GET /admin/image-jobs/status`: estado del scheduler/crawler
  - `GET /admin/image-jobs/logs`: ultimos logs
  - `GET /admin/image-jobs/logs/stream`: SSE de logs
  - `POST /admin/image-jobs/trigger/*`: disparadores (crawl/purge/etc.)
  - `GET /admin/image-jobs/snapshots`: listar snapshot files por `correlation_id`
  - `GET /admin/image-jobs/snapshots/file?path=...`: servir snapshot

- Health / Diagnostico
  - `GET /health`: liveness
  - `GET /health/summary`: resumen (DB/Redis/Storage/Workers/etc.)
  - `GET /health/service/{name}`: deps por servicio (pdf_import/playwright/...)
  - `GET /health/db|redis|storage|optional|dramatiq`: checks especificos
  
- Backups (DB)
  - `GET /admin/backups`: listar backups
  - `POST /admin/backups/run`: crear backup inmediato
  - `GET /admin/backups/download/{filename}`: descargar
  - Ver guía completa: [docs/BACKUPS.md](./docs/BACKUPS.md)

- WebSocket
  - `WS /ws`: canal de chat; pings cada 30s; timeout lectura 60s

- Productos / Media (ejemplos)
  - `GET /products`: catalogo
  - `GET /media/*`: estaticos del build (cuando aplica)
  
- Ventas / Clientes (nuevo módulo)
  - `GET /sales` / `POST /sales` (rate limited) / flujo confirmación
  - `POST /sales/{id}/confirm|deliver|annul`
  - `POST /sales/{id}/payments` + `GET /sales/{id}/payments`
  - `GET /sales/metrics/summary` métricas rápidas (cache 30s)
  - `GET /sales/export` CSV histórico
  - `GET /sales/catalog/search` autocomplete productos
  - Documentación completa: [docs/SALES.md](./docs/SALES.md)

Notas:
- Rutas de Admin en frontend: `/admin/servicios`, `/admin/usuarios`, `/admin/imagenes-productos`.
- Alias legacy `/admin/imagenes` redirige a `/admin/imagenes-productos`.

## Ficha de producto: Minimal Dark + subida de imágenes

- Estética Minimal Dark:
  - Toggle en `/productos/:id` con selector “Estética: Default | Minimal Dark`.
  - Persiste por usuario en `user_preferences` (`scope = product_detail_style`) vía
    `GET/PUT /products-ex/users/me/preferences/product-detail`. Fallback a `localStorage`.
  - Estilo oscuro minimalista con más aire y acentos verdes/fucsia.

- Subir imagen (solo Admin):
  - Botón “Subir imagen” en la ficha (visible solo para rol `admin`).
  - Validaciones frontend: tipos `jpg/png/webp`, tamaño ≤ 10 MB, dimensiones ≥ 600×600.
  - Progreso de subida; toasts de éxito/error.
  - Endpoint backend: `POST /products/{id}/images/upload` (valida tipos/tamaño/dimensiones, AV opcional, deriva webp).
  - Auditoría: `audit_log` con `action=upload_image` y metadatos (producto, filename, size).

Tips:
- Colaborador mantiene acciones de URL (“Descargar”) y push a Tiendanube; la subida directa se reserva a Admin.

Agente para gestión de catálogo y stock de Nice Grow con interfaz de chat web e IA híbrida.

## Arquitectura

- **Backend**: FastAPI + WebSocket.
- **Base de datos**: PostgreSQL 15 (Alembic para migraciones).
- **IA**: ruteo automático entre Ollama (local) y OpenAI.
- **Frontend**: React + Vite con listas virtualizadas mediante `react-window`.
- **Adapters**: stubs de Tiendanube.
- **MCP Servers (nuevo)**: microservicios auxiliares (ej. `mcp_products`, `mcp_web_search`) que exponen herramientas (`tools`) vía un endpoint uniforme `POST /invoke_tool` para consumo de agentes LLM, actuando como fachada HTTP hacia la API principal (sin acceso directo a DB).
  - Products: tools `get_product_info` y `get_product_full_info` (URL default `http://mcp_products:8001/invoke_tool`, configurable con `MCP_PRODUCTS_URL`).
  - Web Search (MVP): tool `search_web(query)` que retorna títulos/URLs/snippets desde un buscador HTML (URL default `http://mcp_web_search:8002/invoke_tool`, configurable con `MCP_WEB_SEARCH_URL`).
  - Enriquecimiento IA puede anexar contexto de `search_web` al prompt si `AI_USE_WEB_SEARCH=1` y `ai_allow_external=true`.

## Enriquecimiento de productos con IA

- UI (detalle de producto): botón “Enriquecer con IA” (visibilidad: admin/colaborador) y menú de acciones:
  - Reenriquecer (force): `POST /products/{id}/enrich?force=true`.
  - Borrar enriquecimiento: `DELETE /products/{id}/enrichment`.
- Backend:
  - `POST /products/{id}/enrich` genera descripción y puede mapear campos técnicos (`weight_kg`, `height_cm`, `width_cm`, `depth_cm`, `market_price_reference`).
  - Si la respuesta incluye “Fuentes”, se escribe un `.txt` bajo `/media/enrichment_logs/` y se expone `enrichment_sources_url`.
  - Metadatos de trazabilidad: `last_enriched_at` y `enriched_by` se setean al enriquecer y se limpian al borrar.
  - Auditoría: acción `enrich`/`reenrich` con `prompt_hash`, `fields_generated`, `source_file` y, si `AI_USE_WEB_SEARCH=1`, `web_search_query` y `web_search_hits`.
- Acciones masivas: `POST /products/enrich-multiple` (máximo 20 IDs por solicitud) con validaciones de título y omitidos si ya enriquecidos (a menos que `force`).
- Flags relevantes:
  - `AI_USE_WEB_SEARCH` (0/1): activa búsqueda web MCP para anexar contexto al prompt.
  - `AI_WEB_SEARCH_MAX_RESULTS` (default 3): máxima cantidad de resultados anexados.
  - `ai_allow_external` (settings): debe estar en `true` para permitir llamadas externas.

## Requisitos

- Python 3.11+
- Node.js LTS
- PostgreSQL 15
- Opcional (dev/pruebas): SQLite 3 con `aiosqlite` (ya incluido en dependencias)
- Opcional: Docker y Docker Compose
# Modo “Docker Stack” (dev en Windows)

Para entornos Windows con Docker Desktop/WSL2, el arranque por defecto usa un modo seguro que evita tocar el engine cuando ya hay contenedores activos:

- `USE_DOCKER_STACK=1` (por defecto): el script de inicio se acopla al stack Docker ya levantado, valida puertos (API 8000, DB 5433, FE 5173) y omite levantar uvicorn local o compilar el frontend.
- `DB_NO_TOUCH_IF_PRE_OK=1`: si el PRE‑FLIGHT detectó la DB OK, no intenta `compose up db` ante flaps momentáneos.
- `DB_FLAP_BACKOFF_SEC=10`: backoff entre reintentos si la DB flapea (ajustable a 30–60 en entornos más lentos).

Consejo: si el engine WSL/Docker Desktop está inestable, reiniciar Docker Desktop y reintentar. Los snapshots forenses del arranque quedan en `logs/start.log` (incluyen `docker info/ps`, probes de puertos y `pg_isready`).

- El backend usa httpx para llamadas a proveedores (Ollama / APIs); ya viene incluido.

### Requisitos para importación de PDFs (OCR)

Para la funcionalidad completa de importación de remitos en PDF, que incluye Reconocimiento Óptico de Caracteres (OCR), se requieren las siguientes dependencias de sistema:

- **ocrmypdf**: para aplicar la capa de OCR a los PDFs.
- **tesseract**: el motor de OCR. Se recomienda instalar el idioma español.
- **ghostscript**: para procesar archivos PDF y PostScript.
- **poppler**: utilidades para renderizar PDFs (usado por `pdf2image`).

En Windows, se pueden instalar con `scoop` o `choco`. En Debian/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y ocrmypdf tesseract-ocr tesseract-ocr-spa ghostscript poppler-utils
```

Para verificar que todas las dependencias están correctamente instaladas y accesibles en el `PATH` del sistema, se puede usar el script "doctor":

```bash
python tools/doctor.py
```

O a través del endpoint de la API (disponible solo para administradores en entorno de desarrollo): `GET /admin/import/doctor`.
- OCR: `ocrmypdf` (requiere Tesseract, Ghostscript y Poppler). TODO: agregar "doctor" para validar instalación.

## Instalación local

Antes de instalar dependencias, `pyproject.toml` debe listar los paquetes o usar un directorio `src/`.
Este repositorio mantiene sus módulos en la raíz, así que es necesario declararlos explícitamente:

```toml
[tool.setuptools.packages.find]
include = ["agent_core", "ai", "cli", "adapters", "services", "db"]
```

```bash
# Crear una nueva revisión a partir de los modelos
alembic -c ./alembic.ini revision -m "descripcion" --autogenerate

# Aplicar las migraciones pendientes
alembic -c ./alembic.ini upgrade head

# Revertir la última migración
alembic -c ./alembic.ini downgrade -1
```

Si se prefiere un layout `src/`, trasladá las carpetas anteriores a `src/` y añadí `where = ["src"]` en la misma sección.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# en producción reemplazar los placeholders SECRET_KEY, ADMIN_USER y ADMIN_PASS
# en desarrollo se usan valores de prueba si se omiten
# las variables de entorno se cargan automáticamente desde .env
# crear base de datos growen en PostgreSQL
alembic -c ./alembic.ini upgrade head
uvicorn services.api:app --reload
```

## Migraciones automáticas

`start.sh`, `scripts/start.bat` y `scripts/run_api.cmd` invocan `scripts\stop.bat`, luego `scripts\fix_deps.bat` y posteriormente `scripts\run_migrations.cmd`, que ejecuta `alembic upgrade head` con logging detallado.
Si la migración falla, `run_migrations.cmd` muestra la ruta del log en `logs\migrations` y el proceso se detiene para evitar correr con un esquema desactualizado.
De esta forma la base siempre está en el esquema más reciente sin comandos manuales.

### Diagnóstico de migraciones

El script `python scripts/debug_migrations.py` genera un reporte en `logs/migrations/report_<timestamp>.txt` con:

- `alembic current`
- `alembic heads`
- `alembic history --verbose -n 30`

También verifica la conexión a la base y avisa si hay múltiples *heads*.
El código de salida es 0 si todo está correcto o 1 si detecta anomalías.

Los logs detallados de Alembic se guardan en `logs/migrations/alembic_<timestamp>.log`.
El nivel de detalle se ajusta con `ALEMBIC_LOG_LEVEL` en `.env`. `DEBUG_MIGRATIONS=1` agrega verbosidad al reporte.

### Permisos mínimos en esquema

Para evitar errores como `permiso denegado al esquema public`, el usuario de la base de datos debe contar con permisos sobre el esquema `public`:

```sql
ALTER DATABASE growen OWNER TO growen;
GRANT USAGE, CREATE ON SCHEMA public TO growen;
```

## Migraciones idempotentes

Cuando existen tablas creadas manualmente o por otras ramas, las migraciones detectan el esquema real y agregan columnas, claves foráneas e índices faltantes en lugar de fallar con errores como `DuplicateTable` o `UndefinedColumn`. Esto vuelve a las migraciones seguras e idempotentes.

La revisión inicial `init_schema` usa `sa.inspect` para crear tablas solo cuando faltan y eliminarlas únicamente si existen, evitando fallas en upgrades o downgrades.

Comandos útiles en `psql` para verificar el estado de una tabla:

```sql
\d supplier_price_history
SELECT column_name FROM information_schema.columns
  WHERE table_name='supplier_price_history'
  ORDER BY ordinal_position;
```

## Compras (BORRADOR → VALIDADA → CONFIRMADA → ANULADA)

- Endpoints: `POST /purchases`, `PUT /purchases/{id}`, `POST /purchases/{id}/validate`, `POST /purchases/{id}/confirm`, `POST /purchases/{id}/cancel`, `GET /purchases`, `GET /purchases/{id}`, `POST /purchases/import/santaplanta`, `GET /purchases/{id}/unmatched/export`.
- Importación Santa Planta (PDF): parser heurístico que crea una compra en estado BORRADOR, adjunta el PDF y realiza matching preferente por SKU proveedor (fallback por título a futuro).
- Confirmación: incrementa stock de producto, actualiza `current_purchase_price` del `supplier_product` y registra `price_history` (entity_type `supplier`). Audita la operación.

### Notificaciones por Telegram (opcional)

La app puede enviar notificaciones por Telegram, por ejemplo al confirmar una compra.

Variables de entorno (ver `.env`):
- `TELEGRAM_ENABLED`: `1` para habilitar la integración (por defecto `0`).
- `TELEGRAM_BOT_TOKEN`: token del bot emitido por `@BotFather`.
- `TELEGRAM_DEFAULT_CHAT_ID`: chat ID numérico por defecto (usuario, grupo o canal).
- `PURCHASE_TELEGRAM_TOKEN` y `PURCHASE_TELEGRAM_CHAT_ID` (opcionales): overrides específicos para notificaciones de Compras; si están vacíos, se usan los valores globales.

Cómo obtener el `chat_id`:
- Escribí a tu bot y luego consultá `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates` (en dev) para ver el `chat.id` numérico del último mensaje.
- En grupos, asegurate de que el bot esté agregado y que la privacidad permita leer los mensajes necesarios.

Notas de seguridad:
- No publiques el token del bot. Si se filtra, revocalo con `@BotFather` y generá uno nuevo.
- Mantené `.env` fuera del control de versiones y usá gestores de secretos en entornos de despliegue.

### Webhook de Telegram para el Chatbot

Podés hablarle al bot de Telegram y que responda con el mismo pipeline del chat HTTP:

- Endpoint: `POST /telegram/webhook/{TELEGRAM_WEBHOOK_TOKEN}`
- Variables:
  - `TELEGRAM_ENABLED=1`
  - `TELEGRAM_BOT_TOKEN=<tu token>`
  - `TELEGRAM_WEBHOOK_TOKEN=<token de path>` (elige una cadena difícil de adivinar)
  - `TELEGRAM_WEBHOOK_SECRET=<opcional>` para validar el header `X-Telegram-Bot-Api-Secret-Token`

Pasos para configurar:
1) Publicá temporalmente la API o usá un túnel (ngrok/localtunnel).
2) Registrá el webhook en Telegram (opcionalmente con secret):
   - URL base: `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook`
   - Query: `url=<PUBLIC_URL>/telegram/webhook/<TELEGRAM_WEBHOOK_TOKEN>` y `secret_token=<TELEGRAM_WEBHOOK_SECRET>` (si lo definiste).
3) Escribí al bot: invocará el endpoint y responderá con el pipeline actual (intents de precio + fallback IA).

Seguridad:
- El path token más el secret header hacen que el webhook no sea invocable por terceros.
- El servicio no responde a updates sin texto/chat_id.

### Mejoras recientes (Productos & Compras)

- Tabla de productos: ahora cuenta con scroll horizontal para navegar todas las columnas cuando la suma de anchos excede el viewport. Se añadió un contenedor con `overflow-x: auto` y una barra inferior siempre accesible.
- Alta manual: botón "Nuevo producto" (roles admin / colaborador) dentro de la vista de productos abre un modal para crear y refresca la lista inmediatamente.
- Importación Santa Planta: en el detalle de compra, cada línea `SIN_VINCULAR` incluye un botón "Crear producto" que abre un diálogo ligero inline para generar el producto y vincularlo a la línea en un paso. El estado de la línea pasa a `OK` y, al confirmar la compra, se aplica el ajuste de stock.
- Optimización UX: no es necesario salir de la pantalla de la compra para dar de alta productos nuevos derivados del PDF.

#### Extensiones adicionales

- Creación masiva en Compras: seleccionar múltiples líneas `SIN_VINCULAR` y usar "Crear productos seleccionados" para generar productos en lote. Cada producto toma el título existente (con prefijo opcional) y el stock inicial igual a la cantidad de la línea.
- Auto‐link por SKU: al tipear un SKU exacto que coincide con un `supplier_product_id` existente, la línea se vincula automáticamente (estado pasa a `OK`).
- Badge `NUEVO`: líneas cuyo producto fue creado en la sesión actual muestran un sello visual sobre el título.
- (Pendiente) creación simultánea de supplier_item cuando se cree el producto manualmente (requiere exponer endpoint backend). Por ahora sólo se crea el producto interno.

Próximos pasos sugeridos:
1. Creación masiva para múltiples líneas `SIN_VINCULAR` seleccionadas.
2. Sugerencia automática de categoría a partir de tokens frecuentes del título.
3. Etiqueta visual para productos creados durante la sesión (p.ej. badge "NUEVO").
4. Opción de precargar precio de venta canónico si existe heurística de margen.
- Filtros: proveedor, fecha (rango), estado, depósito, remito y búsqueda por nombre de producto.
- Export: líneas `SIN_VINCULAR` en CSV o XLSX (si está disponible `openpyxl`).
- Frontend: `/compras`, `/compras/nueva`, `/compras/:id`; autoguardado cada 30s; atajos Enter/Ctrl+S/Esc; tips y chicanas visibles.
- Notificaciones opcionales por Telegram en confirmación: variables `PURCHASE_TELEGRAM_TOKEN` y `PURCHASE_TELEGRAM_CHAT_ID`.

Archivo de ejemplo: `samples/santaplanta_compra.csv` (cabeceras: `supplier_name,remito_number,remito_date,supplier_sku,title,qty,unit_cost,line_discount,global_discount,vat_rate,note`).

## Tono argentino + sarcástico (seguro)

- Prompt global: `ai/persona.py` impone estilo rioplatense, directo y con humor sarcástico leve, con salvaguardas (sin insultos ni odio/violencia).
- Router de IA: `ai/router.py` inyecta `SYSTEM_PROMPT` por defecto para todos los proveedores.
- Errores del sistema: middleware en `services/api.py` devuelve mensajes de error con tono breve y claro.

#### Problemas comunes

- **Múltiples heads**: ejecutar `python scripts/debug_migrations.py` para identificar las revisiones y crear una migración de *merge* si es necesario.
- **UndefinedTable / UndefinedColumn**: revisar `logs/migrations/alembic_<timestamp>.log`; puede indicar que falta una migración previa.
- **DuplicateTable / DuplicateIndex**: las migraciones actuales son idempotentes; reejecutarlas no debería fallar.
- **Seeds inválidos**: asegurarse de que las columnas requeridas existan antes de insertar datos.
- **Acceso denegado al iniciar en Windows**: `start.bat` abre procesos con `start` y `cmd /k`. Para que Windows respete rutas con espacios, las líneas usan comillas dobles consecutivas, por ejemplo:
   - API: `cmd /k ""%VENV%\python.exe" ... >> "%LOG_DIR%\backend.log" 2>&1"`
   - Frontend: `cmd /k "pushd ""%ROOT%frontend"" && npm run dev >> "%LOG_DIR%\frontend.log" 2>&1"`
   Quitar alguna de esas comillas provoca errores como “Acceso denegado” o que el comando se ejecute en el directorio equivocado. Mantené el patrón intacto y ejecutá el script desde la raíz del proyecto.

Orden de ejecución recomendado:

1. `scripts\stop.bat`
2. `scripts\fix_deps.bat`
3. `scripts\run_migrations.cmd`
4. Inicio de backend y frontend

### Base de datos (PostgreSQL) en Windows

- Imagen base: `postgres:15.10-bookworm`, reforzada con `apt-get dist-upgrade` en `infra/Dockerfile.postgres` (ejecutá `docker compose build db && docker compose up -d db` tras cambios).
- En Windows suele estar ocupado el puerto 5432 por otra instalación. El docker-compose mapea Postgres del contenedor al puerto 5433 del host para evitar conflictos.
  - Verificá que `.env` tenga una URL válida, por ejemplo: `DB_URL=postgresql+psycopg://<user>:<pass>@127.0.0.1:5433/growen` (no publiques credenciales reales).
- Si se reutiliza un volumen previo del contenedor y la contraseña del usuario `growen` no coincide, podés ajustarla sin borrar datos:
  1. `docker exec -it growen-postgres sh`
  2. `psql -U growen -d growen -c "ALTER USER growen WITH PASSWORD 'NuevaPass';"`
  3. Actualizá `.env` con la contraseña nueva y reiniciá la API.
- Aplicá migraciones con `python -m alembic upgrade head` para crear/actualizar el esquema.

### Fallback automático a SQLite (desarrollo)

Si al ejecutar `start.bat` Postgres no está disponible en `127.0.0.1:5433` y no es posible iniciarlo con Docker (por ejemplo, Docker Desktop apagado), el script activa un modo de desarrollo con SQLite usando `dev.db`:

- Se establece `DB_URL=sqlite+aiosqlite:///./dev.db` solo para esa sesión.
- Las migraciones se ejecutan contra SQLite para crear el esquema mínimo.
- Se ejecuta un seed idempotente del usuario administrador (usuario `admin`, password por defecto `admin1234` si no se define `ADMIN_PASS`).
- La API se inicia normalmente y podés validar pantallas y flujos básicos sin depender de Postgres.

Notas importantes:
- Este fallback es solo para desarrollo local. Algunas funciones que dependen de características específicas de PostgreSQL o de jobs de fondo pueden estar limitadas.
- Cuando Postgres vuelva a estar disponible, volvés al modo normal simplemente arrancando Docker y re-ejecutando `start.bat`.

## Troubleshooting
- Chequeo rápido de stack (Windows):
  - Usa `scripts/status_stack.ps1` para verificar DB, API y frontend.
  - Ejemplo (PowerShell):
    - `powershell -NoProfile -ExecutionPolicy Bypass -File "scripts/status_stack.ps1"`
  - Salida esperada:
    - `DB (127.0.0.1:5433): OK`
    - `/health: OK`
    - `/app: OK`
  - Código de salida:
    - `0`: DB y `/health` OK (frontend opcional).
    - `1`: DB o `/health` fallan.
  - Parámetros opcionales:
    - `-ApiUrl` (default `http://127.0.0.1:8000`), `-DbHostName` (default `127.0.0.1`), `-DbPort` (default `5433`).
  - Si DB marca FAIL:
    - Asegurá Docker Desktop corriendo.
    - Levantá la DB: `docker compose up -d db` (mapea 5433→5432).
  - Si `/health` marca FAIL:
    - Relanzá el backend y confirmá que `DB_URL` apunta a Postgres.
    - Reintenta cuando `/health` devuelva 200.

- Login devuelve 503: Base de datos no disponible.
  - La API devuelve 503 si la DB está temporalmente indisponible (timeout, reinicio, backup).
  - Esperá unos segundos y reintentá; revisá `scripts/status_stack.ps1`.


Al iniciar la API con `scripts\run_api.cmd`, el script registra cada paso en `logs\run_api.log` y Uvicorn redirige su salida a `logs\backend.log`. Estos archivos permiten diagnosticar fallas de arranque y pueden inspeccionarse con `type` o cualquier editor de texto:

```cmd
type logs\run_api.log
type logs\backend.log
```

### Limpieza rápida de logs

Para iniciar una sesión de depuración limpia:

```bash
python scripts/cleanup_logs.py --dry-run   # muestra acciones
python scripts/cleanup_logs.py             # elimina rotaciones y trunca backend.log
python scripts/cleanup_logs.py --skip-truncate  # no intenta truncar backend.log (útil si está bloqueado por el proceso)
python scripts/cleanup_logs.py --keep-days 2
```

Acciones del script:
- Elimina `backend.log.*` y `.bak` (no borra `backend.log` principal; lo trunca).
- Borra logs de diagnósticos y jobs de imágenes si coinciden con patrones.
- Conserva estructura de carpetas. Usa `--keep-days N` para preservar archivos recientes.
 - Opcional: limpieza de capturas del botón de reporte según política:
   - `--screenshots-keep-days N` (por defecto 30; 0 = sin límite por días)
   - `--screenshots-max-mb M` (por defecto 200; 0 = sin límite)

Recomendado antes de reproducir un escenario (confirmar compra, probar WebSocket de chat, etc.) para aislar el nuevo output.

Notas en Windows:
- Si `backend.log` está bloqueado por el proceso de la API, el script registrará el error de permiso y creará el marcador `backend.log.cleared` para indicar que se intentó limpiar. Usá `--skip-truncate` para omitir el truncado y aun así limpiar rotaciones.

### Migraciones

- Este repositorio ya incluye el árbol de Alembic; **no** ejecutes `alembic init`.
- `alembic.ini` define `script_location = %(here)s/db/migrations`, por lo que las rutas se resuelven respecto al archivo y no al directorio actual.
- Si `alembic_version.version_num` quedó en `VARCHAR(32)`, el arranque la ensancha automáticamente a `VARCHAR(255)` para soportar identificadores de revisión largos.
- Cada ejecución de `scripts\run_migrations.cmd` genera un archivo en `logs\migrations\alembic_YYYYMMDD_HHMMSS.log` con todo el `stdout` y `stderr` de Alembic.
- Si el arranque se detiene por un error de migración, revisar la ruta indicada y solucionar el problema antes de volver a ejecutar `scripts\start.bat`.
- Al invocar Alembic manualmente, las opciones globales como `--raiseerr` y `-x log_sql=1` deben ubicarse **antes** del subcomando. `log_sql=1` activa `sqlalchemy.echo` para registrar cada consulta. Ejemplo:

```
alembic --raiseerr -x log_sql=1 -c alembic.ini upgrade head
```

## Instalación Frontend

```bash
cd frontend
npm install
npm run dev
```

En desarrollo, Vite proxya `/ws`, `/chat` y `/actions` hacia `http://localhost:8000`, evitando errores de CORS. Durante el arranque pueden mostrarse errores de proxy WebSocket si la API aún no está disponible; una vez arriba, la conexión se restablece sola. El chat abre un WebSocket en `/ws` y, si no está disponible, utiliza `POST /chat`, que admite la variante con o sin barra final para evitar redirecciones 307. El servidor envía un ping cada 30 s y corta la sesión tras 60 s sin recibir datos; el frontend ignora esos pings, cierra limpiamente y reintenta con backoff exponencial si la conexión se pierde. Para modificar las URLs se puede crear `frontend/.env.development` con `VITE_WS_URL` y `VITE_API_BASE`.

### Botón de reporte de bugs
- La UI incluye un botón flotante global (abajo a la derecha) para enviar reportes manuales de errores o problemas.
- Opcionalmente adjunta una captura de pantalla del estado actual (guardada como archivo en `logs/bugreport_screenshots/`).
- Los reportes se registran en `logs/BugReport.log` del backend mediante `POST /bug-report`.
- Más info en `docs/BUG_REPORTS.md`.

### Producción: SPA fallback

El backend sirve el build de Vite directamente y aplica un fallback de SPA para que al refrescar rutas del cliente (por ejemplo `/productos` o `/stock`) no se produzca `404`.

- Activos estáticos del bundle: `GET /assets/*` (montados con `StaticFiles`).
- Rutas API y documentación se registran antes; el fallback no las intercepta.
- Fallback: cualquier ruta no API ni estática devuelve `index.html`.

Requisitos del build:

- `vite.config` con `base: '/'`.
- El `index.html` referencia los activos bajo `/assets/`.

Pruebas manuales:

1. Abrir `/productos` y presionar F5: debe renderizar sin `404`.
2. Abrir `/stock` y presionar F5: debe renderizar sin `404`.
3. Solicitar `/assets/<archivo>.js` devuelve el asset.
4. Endpoints como `/products`, `/auth/me`, `/docs` deben seguir funcionando normalmente.

## Catálogo — Edición inline y preferencias

- Edición inline de Precio de venta (canónico) con guardado en `Enter`/`onBlur` y `Esc` para cancelar. Solo `admin` y `colaborador` ven controles de edición.
- Panel de Comparativa por producto con ofertas de proveedores, ordenadas por menor precio de compra; permite editar precio de compra inline (roles `admin|colaborador`).
- Preferencias de columnas por usuario (orden, visibilidad, anchos) persistidas en backend. Botón “Diseño” para configurar y “Restaurar diseño” para volver a valores por defecto.
- Edición masiva de precio de venta con modos `set|inc|dec|inc_pct|dec_pct` (modal). Requiere CSRF.

Endpoints relevantes (precio y compras), prefijo `/products-ex` para precios:

- `PATCH /products/{product_id}/sale-price` (admin, colaborador; CSRF)
- `PATCH /supplier-items/{supplier_item_id}/buy-price` (admin, colaborador; CSRF)

### Eliminación segura de productos

- `DELETE /catalog/products` (CSRF; roles `admin|colaborador`). Cuerpo `{ "ids": number[] }`.
- Reglas de negocio:
  - 400 si el producto tiene `stock > 0`.
  - 409 si el producto posee referencias en compras (`purchase_lines.product_id`).
  - Si no hay bloqueos: se eliminan dependencias compatibles sin ON DELETE CASCADE: `supplier_products`, `variants`, `inventories` e `images`; luego el `product`.
- Respuesta: `{ requested, deleted, blocked_stock?: number[], blocked_refs?: number[] }`.
- Auditoría: `AuditLog { action: "product_delete" }` por cada producto con metadatos de cascada.

### Anti-duplicados en import de Compras (SantaPlanta)

- Se filtran líneas duplicadas por `supplier_sku` y por `title` normalizado (trim, lower, sin tildes).
- Se registran métricas en `ImportLog` con nivel `WARN`:
  - `ignored_duplicates_by_sku` y `ignored_duplicates_by_title`.
- La respuesta de `POST /purchases/import/santaplanta` incluye `lines_unique`, `ignored_by_sku` e `ignored_by_title` en metadatos y encabezado `X-Correlation-Id` para trazar logs.
- Auditoría de import con estos campos para trazabilidad.
- `POST /products/bulk-sale-price` (admin, colaborador; CSRF)
- `GET /products/{product_id}/offerings`
- `GET/PUT /users/me/preferences/products-table` (PUT requiere CSRF)

### Creación manual de productos

Soporte para crear productos internos manualmente (roles `admin` y `colaborador`).

Backend:
- `POST /catalog/products` (CSRF) JSON mínimo (modal rápido):
  ```json
  {
    "title": "Nombre",
    "initial_stock": 0,
    "supplier_id": 1,
    "supplier_sku": "OPCIONAL",
    "sku": "SKU-INTERNO-OPC", 
    "purchase_price": 100.0,
    "sale_price": 150.0
  }
  ```
  - Requiere proveedor y precios de compra/venta.
  - Campo `sku` (opcional) permite forzar un SKU interno distinto del del proveedor; si se omite usa `supplier_sku` o el `title` normalizado (truncado a 50). Validación regex: `[A-Za-z0-9._\-]{2,50}`.
  - Crea `Product` + `Variant` (SKU = `sku_root`), valida SKU único global antes de insertar (pre-check) y el constraint garantiza consistencia.
  - Crea `SupplierProduct` y registra `current_purchase_price`/`current_sale_price` e historial en `supplier_price_history`.
  - Respuesta incluye `id`, `sku_root`, `supplier_item_id`.
  - Compatibilidad: el endpoint `/products` completo sigue disponible para flujos avanzados (categoría, estado, enlaces canónicos).
  - Si el SKU ya existe, devuelve 409 con detalle.

Notas adicionales:
- Se registra un `SupplierPriceHistory` inicial con los precios enviados.
- `initial_stock` > 0 crea registro en `inventory` y sincroniza `products.stock`.

Eliminación segura (`DELETE /catalog/products`):
- Reglas single-id: 400 si stock > 0; 409 si referencias en `purchase_lines`.
- Éxito: elimina en orden manual dependencias sin ON DELETE CASCADE: `supplier_price_history`, `supplier_products`, `variants`, `inventory`, `images`, luego `product` y registra `audit_log` con conteos.
- Respuesta: `{ requested, deleted, blocked_stock, blocked_refs }`.

Frontend:
- Botón "Nuevo producto" en panel Productos abre modal.
- Formulario: Nombre (requerido), Categoría (lazy load al enfocar), Stock inicial (≥0).
- Al crear reinicia a página 1 y refresca lista, muestra toast.

Validaciones:
- `initial_stock >= 0`.
- `category_id` debe existir si se envía.

Limitaciones actuales / posibles mejoras:
- Sin variantes automáticas ni carga de imágenes en el modal.
- Futuro: clonación, importación CSV, set de atributos iniciales.


## Consultar precios y stock desde el chat

- Preguntá "¿cuánto sale <producto>?" o "¿tenés <producto> en stock?" para obtener precio y disponibilidad con badge de stock.
- Usá `/stock <sku>` o mencioná SKUs internos/proveedor para coincidencias exactas.
- La respuesta del bot incluye proveedor, SKU y variantes relevantes; si no encuentra nada, ofrece abrir el listado de Productos.

## Subir listas de precios desde el chat

- Arrastrá y soltá un archivo `.xlsx` o `.csv` sobre la zona punteada encima del chat para abrir el modal de carga.
- También podés usar el botón **Adjuntar Excel**.
- El modal muestra nombre y tamaño del archivo y habilita **Subir** solo cuando hay proveedor seleccionado.
- Se validan formato y tamaño antes de enviar. El límite se define con `VITE_MAX_UPLOAD_MB`.
- Solo los roles `proveedor`, `colaborador` y `admin` ven la opción de adjuntar. Si el usuario es `proveedor`, su `supplier_id` queda preseleccionado.

## Autenticación y roles

La API implementa sesiones mediante la cookie `growen_session` y un token CSRF almacenado en `csrf_token`. Cada vez que se inicia o cierra sesión se generan nuevos valores para ambas cookies, evitando la fijación de sesiones. Todas las mutaciones deben enviar el encabezado `X-CSRF-Token` coincidiendo con dicha cookie. Las rutas que modifican datos añaden dependencias `require_roles` para comprobar que el usuario posea el rol autorizado.

Si no hay cookie de sesión y el entorno es `dev`, se asume rol `admin` por defecto para agilizar pruebas; en otros entornos el rol por omisión es `guest`.

El login acepta **identificador** o email junto con la contraseña. Una migración idempotente agrega la columna `identifier` si falta y la rellena a partir del correo; esto permite que bases antiguas sigan funcionando. Al ejecutar las migraciones se crea, si no existe, un usuario administrador usando `ADMIN_USER` y `ADMIN_PASS` definidos en `.env` (ver `.env.example`). En producción el servidor se niega a iniciar si `ADMIN_PASS` queda en el placeholder `REEMPLAZAR_ADMIN_PASS`.

Nota sobre fallback en desarrollo: si `ADMIN_PASS` está en placeholder y el entorno es `dev`, el sistema (config, migración y script `seed_admin.py`) usa la contraseña temporal `admin1234`. Esta contraseña SOLO es válida para entornos locales y debe reemplazarse siempre en producción definiendo un valor seguro en `.env` antes de iniciar la aplicación. Cualquier entorno distinto de `dev` abortará el arranque si persiste el placeholder.

### Endpoints principales

- `POST /auth/login` valida credenciales por identificador o email y genera una sesión nueva.
- `POST /auth/guest` crea una sesión con rol `guest` sin usuario, regenerando el token.
- `POST /auth/logout` cierra la sesión, crea una nueva sesión de invitado y regenera el token (requiere CSRF).
- `GET /auth/me` informa el estado actual.
- `GET /auth/users` lista usuarios (solo admin).
- `POST /auth/users` crea usuarios (solo admin, requiere CSRF).
- `PATCH /auth/users/{id}` actualiza usuarios (solo admin, requiere CSRF).
- `POST /auth/users/{id}/reset-password` regenera la contraseña (solo admin, requiere CSRF).

### Roles y permisos

| Rol         | Permisos principales |
|-------------|---------------------|
| invitado    | Solo lectura |
| cliente     | Solo lectura |
| proveedor   | Subir Excel de su proveedor asignado |
| colaborador | Subir Excel y aplicar importaciones de cualquier proveedor |
| admin       | Todos los permisos, incluyendo registrar usuarios |

La lista completa de rutas y roles se encuentra en [docs/roles-endpoints.md](docs/roles-endpoints.md).

### Variables de entorno relevantes

```env
SECRET_KEY=REEMPLAZAR_SECRET_KEY
# ADMIN_USER y ADMIN_PASS se definen en .env (ver .env.example);
# en producción cambie los placeholders
SESSION_EXPIRE_MINUTES=1440 # duración de la sesión en minutos (1 día recomendado)
AUTH_ENABLED=true
# se ignora en producción; allí siempre es true
COOKIE_SECURE=false
COOKIE_DOMAIN=
```

`SECRET_KEY` y las credenciales iniciales (`ADMIN_USER` y `ADMIN_PASS`, definidas en `.env`) deben reemplazarse por valores robustos en producción.
En entornos de desarrollo se usarán valores de prueba si se dejan en los placeholders, pero conviene ajustarlos igualmente.
Mantener estas claves fuera del control de versiones y rotarlas periódicamente.

`SESSION_EXPIRE_MINUTES` define cuánto tiempo permanece válida una sesión.
El valor recomendado de `1440` mantiene la sesión durante un día. Al expirar,
el usuario debe volver a autenticarse. Valores más altos reducen la frecuencia
de inicio de sesión pero incrementan el riesgo ante robo de cookies; valores
más bajos obligan a reautenticarse con mayor frecuencia y elevan la seguridad.

## Botonera

La interfaz presenta una botonera fija sobre el chat con accesos rápidos:

- **Adjuntar Excel** abre el modal de carga de listas de precios.
- **Proveedores** muestra la gestión básica de proveedores (listar y crear).
- **Productos** abre un panel para buscar en la base, ajustar stock y gestionar canónicos: permite editar fichas canónicas y vincular equivalencias manualmente. Los resultados se cargan bajo demanda al desplazarse gracias a `react-window`.
- **Usuarios** despliega el panel de administración para listar, crear, editar y restablecer contraseñas. Solo es visible para el rol `admin`.

La barra queda visible al hacer scroll y usa un estilo mínimo con sombreado suave.

## Panel de usuarios

El panel accesible en `/admin` consume los endpoints de autenticación para gestionar cuentas:

- `GET /auth/users` lista los usuarios existentes con su rol.
- `POST /auth/users` crea nuevas cuentas asignando nombre, email y rol.
- `PATCH /auth/users/{user_id}` permite actualizar el rol o desactivar usuarios.
- `POST /auth/users/{user_id}/reset-password` genera una contraseña temporal y la devuelve en la respuesta.

Todas estas operaciones requieren el rol `admin` y envían encabezado `X-CSRF-Token`.

## Modo oscuro

El frontend define un esquema de color gris con acentos violeta (`#7C4DFF`) y verde (`#22C55E`).
Un botón en la barra permite alternar el tema y, por defecto, se respeta `prefers-color-scheme` del sistema.

## Contrato del Chat (DEV)

- **HTTP**: `POST /chat` con cuerpo `{ "text": "hola" }` → responde `{ "role": "assistant", "text": "..." }`.
- **WebSocket**: se envía texto plano y cada mensaje recibido es un JSON `{ "role": "assistant", "text": "..." }`. El servidor agrega pings periódicos `{ "role": "ping" }` para mantener viva la conexión y la cierra tras 60 s sin actividad; el cliente los descarta y reintenta con backoff exponencial si se pierde el canal.
- **Sesión**: si la cookie `growen_session` está presente, el backend incluye el nombre y rol del usuario en el prompt para personalizar la respuesta de la IA.
- **Proveedor**: Ollama es el motor por defecto (`OLLAMA_MODEL=llama3.1`). El backend intenta primero con `stream=False` y, si la API falla, cae a modo *streaming* acumulando las partes. En ambos casos normaliza la respuesta y remueve prefijos como `ollama:` antes de reenviarla.

La interfaz muestra las respuestas del asistente con la etiqueta visual **Growen**.

## Importación de listas de precios

Flujo básico: **upload → preview → commit**.

La API permite subir archivos de proveedores en formato `.xlsx` para revisar y aplicar nuevas listas de precios.

1. `POST /suppliers/{supplier_id}/price-list/upload` recibe el archivo del proveedor (campo `file` en `multipart/form-data`) y un parámetro `dry_run` (por defecto `true`). Es obligatorio que el proveedor exista y tenga un *parser* registrado.
2. `GET /imports/{job_id}/preview?status=new,changed&page=1&page_size=50` lista las filas normalizadas filtradas por `status` y paginadas. La respuesta devuelve `{items, summary, total, pages, page}` y permite inspeccionar también `status=error,duplicate_in_file` para los fallos. Durante esta vista previa es posible crear o editar productos canónicos y vincular equivalencias manualmente desde cada fila.
3. `POST /imports/{job_id}/commit` aplica los cambios, creando categorías, productos y relaciones en `supplier_products`.

Cada proveedor define su mapeo en `config/suppliers/*.yml`. Por cada archivo se genera automáticamente un `GenericExcelParser`.
También pueden agregarse parsers especializados instalando paquetes que expongan un `entry_point` en el grupo `growen.suppliers.parsers`.
Para depurar los parsers habilitados se puede llamar a `GET /debug/imports/parsers`, disponible solo para administradores y deshabilitado en producción.

| Proveedor | Configuración |
|-----------|---------------|
| `santa-planta` | `config/suppliers/santa-planta.yml` |

En modo *dry-run* se puede revisar el contenido antes de confirmar los cambios definitivos.

Las tablas `import_jobs` e `import_job_rows` guardan cada archivo cargado y sus filas normalizadas.
`supplier_price_history` registra los cambios de precios para auditoría.
`GET /price-history` permite consultar ese historial filtrando por `supplier_product_id` o `product_id` y admite paginación. Solo está disponible para los roles `cliente`, `proveedor`, `colaborador` y `admin`.

### Plantillas Excel

`GET /suppliers/price-list/template` devuelve una plantilla genérica con la hoja `data` y los encabezados:
`ID`, `Agrupamiento`, `Familia`, `SubFamilia`, `Producto`, `Compra Minima`, `Stock`, `PrecioDeCompra`, `PrecioDeVenta`.
`GET /suppliers/{supplier_id}/price-list/template` genera la misma estructura pero permite personalizar el nombre del archivo según el proveedor.
Ambas rutas requieren un rol válido (`cliente`, `proveedor`, `colaborador` o `admin`).
La celda `A1` incluye una nota con instrucciones y la fila 2 trae un ejemplo. En el modal de carga hay un botón **Descargar plantilla genérica** que llama a `GET /suppliers/price-list/template` y otro **Descargar plantilla** que usa `GET /suppliers/{supplier_id}/price-list/template` para obtener el archivo específico antes de completar los datos.

### Adjuntar Excel desde el chat

La interfaz de chat incluye un botón **+** y la opción de la botonera **Adjuntar Excel** para subir listas de precios sin pasar por la IA.

1. Hacer clic en **Adjuntar Excel** o arrastrar un archivo `.xlsx` sobre la ventana.
2. El modal exige elegir un proveedor; si no existen proveedores se muestra un estado vacío con el botón **Crear proveedor**.
3. Tras seleccionar proveedor y archivo, el frontend llama a `POST /suppliers/{supplier_id}/price-list/upload?dry_run=true`.
4. Growen envía un mensaje de sistema con el `job_id` y abre un visor que pagina las filas llamando a `GET /imports/{job_id}/preview`, mostrando el total de filas, la página actual y el número de páginas devueltos por la API.
5. El visor abre la pestaña **Cambios** por defecto para resaltar las variaciones y muestra el recuento en cada pestaña; desde allí se pueden filtrar errores y finalmente ejecutar `POST /imports/{job_id}/commit`.

Errores comunes:

- **400** columnas faltantes.
- **413** tamaño excedido (límite `MAX_UPLOAD_MB`).

### Flujo del visor de importaciones

El visor trabaja de forma paginada llamando a `GET /imports/{job_id}/preview`. Como atajo, `GET /imports/{job_id}` devuelve `status`, `summary` y las primeras filas para hidratar vistas iniciales sin paginación.

1. La pestaña **Cambios** solicita `status=new,changed` para concentrar las filas a aplicar.
2. **Errores** y **Duplicados en archivo** reutilizan el mismo endpoint variando `status`.
3. Cada respuesta entrega `{items, summary, total, pages, page}` con los totales por tipo de fila.
4. Desde cada fila pueden crearse productos canónicos o equivalencias antes de confirmar.
5. Al finalizar la revisión se envía `POST /imports/{job_id}/commit` para persistir los ajustes.

## Productos canónicos (`/canonical-products`)

Para comparar precios entre proveedores se mantiene un catálogo propio de productos canónicos.
Cada oferta puede asociarse a uno de ellos mediante equivalencias (ver sección siguiente).
- El frontend incluye el formulario **CanonicalForm** para crear o editar estos registros. El SKU propio (`sku_custom`) puede:
  - Autogenerarse con el botón "Auto" usando el patrón `XXX_####_YYY` (prefijo/sufijo derivados de categoría y subcategoría, secuencia por categoría).
  - Ser editado manualmente con validación de unicidad en backend.

- **Crear canónico**: `POST /canonical-products` con `name`, `brand` y `specs_json` opcional. El sistema genera `ng_sku` con el formato `NG-000001` y, si no se provee `sku_custom`, genera uno canónico como se indicó arriba.
- **Buscar canónicos**: `GET /canonical-products?q=&page=` permite paginar y filtrar.
- **Detalle/edición**: `GET /canonical-products/{id}` y `PATCH /canonical-products/{id}` devuelven y actualizan un canónico.
- **Comparador**: `GET /canonical-products/{id}/offers` ordena las ofertas por precio de venta y marca la mejor con `mejor_precio`.

Notas de UX:
- Al crear un canónico desde la lista de productos (columna "Canónico" → "Nuevo"), el formulario se abre con el nombre del producto del proveedor prellenado. Al guardar, se autovincula una equivalencia con esa oferta del proveedor (si existe `supplier_item_id`).

## Equivalencias (`/equivalences`)

Las equivalencias enlazan una oferta de proveedor (`supplier_product`) con un producto canónico para habilitar la comparación de precios.
El componente **EquivalenceLinker** permite gestionar estos vínculos desde la interfaz.

- **Vincular oferta**: `POST /equivalences` une un `supplier_product` existente con un `canonical_product`.
- **Listar equivalencias**: `GET /equivalences?supplier_id=&canonical_product_id=` soporta filtros y paginación.
- **Eliminar equivalencia**: `DELETE /equivalences/{id}`.

## Comparativa de precios

El endpoint `GET /canonical-products/{id}/offers` devuelve todas las ofertas vinculadas a un canónico ordenadas por precio, destacando el mejor con el campo `mejor_precio`. Desde la interfaz se accede a esta tabla desde el visor de importación y el panel de productos cuando el artículo tiene una equivalencia canónica.

Variables de entorno relevantes:

```env
AUTO_CREATE_CANONICAL=true
FUZZY_SUGGESTION_THRESHOLD=0.87
SUGGESTION_CANDIDATES=3
```

Estas opciones controlan la creación automática y las sugerencias durante la
importación de listas. Las coincidencias se calculan con `rapidfuzz` y solo se
aceptan si superan el umbral `FUZZY_SUGGESTION_THRESHOLD`.

## Consulta de productos

`GET /products` lista los productos disponibles con filtros, orden y paginación. Requiere los roles `cliente`, `proveedor`, `colaborador` o `admin`.

Parámetros soportados:

- `supplier_id`: filtra por proveedor.
- `category_id`: filtra por categoría interna.
- `q`: búsqueda parcial por nombre del producto o título del proveedor.
- `page` y `page_size`: paginación (por defecto `1` y `20`).
- `sort_by`: `updated_at`, `precio_venta`, `precio_compra` o `name`.
- `order`: `asc` o `desc`.
- `type`: `all` (default), `canonical` o `supplier`. Permite alternar entre ver solo filas con canónico, solo ofertas de proveedor o todo.

Si se envían otros valores en `sort_by` u `order`, la API responde `400 Bad Request`.

Ejemplo de respuesta:

```json
{
  "page": 1,
  "page_size": 20,
  "total": 1,
  "items": [
    {
      "product_id": 1,
      "name": "Carpa Indoor 80x80",
      "supplier": {"id": 1, "slug": "santa-planta", "name": "Santa Planta"},
      "precio_compra": 10000.0,
      "precio_venta": 12500.0,
      "compra_minima": 1,
      "category_path": "Carpas>80x80",
      "stock": 0,
      "updated_at": "2025-08-15T20:33:00Z"
    }
  ]
}
```

Este endpoint se utiliza para consultar el catálogo existente desde el frontend.

Comportamiento de campos (fallback canónico → proveedor):
- Si un producto está vinculado a un canónico, la UI prioriza `canonical_sale_price` y `canonical_name` cuando están presentes; si no, cae a `precio_venta` y `supplier_title` del proveedor.

Para modificar el stock manualmente existe `PATCH /products/{id}/stock` con cuerpo `{ "stock": <int> }`.

## Historial de precios

`GET /price-history` devuelve el historial de precios ordenado por fecha.
Debe indicarse `supplier_product_id` o `product_id` y se puede paginar con `page` y `page_size`.
La respuesta incluye `purchase_price`, `sale_price` y sus variaciones porcentuales (`delta_purchase_pct`, `delta_sale_pct`).
Solo los roles `cliente`, `proveedor`, `colaborador` o `admin` pueden consultarlo y el panel de productos enlaza a esta vista para auditoría.

## Inicio rápido (1‑clic)

Levanta API y frontend al mismo tiempo.

### Windows

Ejecutar **desde CMD** con doble clic en `scripts\start.bat`. El script realiza estas etapas:

1. Llama a `scripts\stop.bat` para liberar los puertos **8000** y **5173**.
2. Aplica las migraciones mediante `scripts\migrate.bat` y guarda el log en `logs\migrations\alembic_YYYYMMDD_HHMMSS.log`.
3. Abre dos ventanas:
   - Growen API (Uvicorn) en http://127.0.0.1:8000/docs
   - Growen Frontend (Vite) en http://127.0.0.1:5173/

Requisitos previos:

- Python 3.11 (si no existe un virtualenv, `scripts\start.bat` intentará crearlo automáticamente)
- Node.js/npm instalados (si faltan paquetes de frontend, `scripts\start.bat` ejecutará `npm install` en `frontend` cuando sea necesario)
- `.env` completado (DB_URL, IA, etc.)
- `frontend/.env` creado a partir de `frontend/.env.example` si se necesita ajustar `VITE_API_URL`.

Comportamiento de auto-configuración de `scripts\start.bat`:

- Si no existe `.venv`, el script intentará crear un entorno virtual en `.venv` y actualizar `pip`/`setuptools`.
- Tras crear el virtualenv, se ejecuta `python -m tools.doctor`. Si la variable de entorno `ALLOW_AUTO_PIP_INSTALL=true` está definida, el doctor intentará instalar `requirements.txt` automáticamente.
- Si `tools.doctor` detecta problemas críticos, el script pausará y te dará la opción de abortar o continuar.
- Si `frontend/node_modules` no existe, `scripts\start.bat` ejecutará `npm install` dentro de `frontend`.

Esto facilita un inicio de desarrollo “1‑clic” en máquinas nuevas.

Para detener manualmente los servicios, ejecutar `scripts\stop.bat` desde CMD.

PowerShell no requerido (los scripts son CMD puro).

Para iniciar solo el backend en Windows se puede ejecutar `scripts\run_api.cmd`, que detiene procesos previos, instala dependencias, aplica migraciones y guarda la salida de Uvicorn en `logs/backend.log`.  El script también escribe información de depuración, como rutas base y códigos de retorno, en `logs/run_api.log`.

### Arranque en Windows (rutas con espacios)

Los `.bat` están preparados para ejecutarse desde rutas como `C:\\Nice Grow\\Agentes\\Growen` sin errores de sintaxis:

- Todas las rutas se envuelven entre comillas.
- Se usa `pushd`/`popd` en lugar de `cd` para cambiar de directorio.
- `scripts\start.bat` encadena `stop` → `migrate` → `api + frontend` en ventanas separadas.
- Para registrar cada consulta SQL en el log de migraciones ejecutar `scripts\start.bat /sql`.

Nota de compatibilidad (psycopg asíncrono): en Windows la aplicación establece `WindowsSelectorEventLoopPolicy` al iniciar para evitar errores del conector asíncrono de PostgreSQL.

### Debian/Ubuntu

```bash
chmod +x start.sh
./start.sh
```

**Requisitos previos**: entorno virtual creado (`python -m venv .venv`), `pip install -e .`, Node.js instalado y `.env` con `DB_URL` y `OLLAMA_MODEL=llama3.1`. El backend escucha en `http://localhost:8000` y el frontend en `http://localhost:5173`.

En Windows puede aparecer un aviso de firewall; permitir el acceso para ambos puertos. Si alguna de las aplicaciones no inicia, verificar que los puertos 8000 y 5173 estén libres.

**Modelos Ollama**: instalar [Ollama](https://ollama.com/download) y ejecutar `ollama pull llama3.1`. Si la descarga falla, probar con `ollama pull llama3` u otra variante disponible. La variable `OLLAMA_MODEL` apunta por defecto a `llama3.1`.

## Instalación con Docker

```bash
docker compose up --build
```
Levanta PostgreSQL, API en `:8000` y frontend en `:5173`.

## Migraciones (Alembic)

Las migraciones se administran con Alembic usando la carpeta `db/migrations`. El archivo `env.py` carga automáticamente las
variables definidas en `.env`, por lo que no es necesario configurar la URL en `alembic.ini`.

```bash
cp .env.example .env   # en Windows usar: copy .env.example .env
# Completar DB_URL y, en producción, definir SECRET_KEY y las credenciales ADMIN_USER/ADMIN_PASS reemplazando los placeholders
alembic -c ./alembic.ini upgrade head

# Crear una nueva revisión a partir de los modelos
alembic -c ./alembic.ini revision -m "descripcion" --autogenerate

# Aplicar las migraciones pendientes
alembic -c ./alembic.ini upgrade head

# Revertir la última migración
alembic -c ./alembic.ini downgrade -1
```

## Variables de entorno

Consulta `.env.example` para la lista completa. Variables destacadas:

- `DB_URL`: URL de PostgreSQL (obligatoria; la aplicación no arranca si falta. Si la contraseña tiene caracteres reservados, encodéalos, ej.: `=` → `%3D`. Si tu contraseña tiene caracteres raros, ponela sin encodar en variables separadas y construí la URL con `SQLAlchemy URL.create()`; pero si usás `DB_URL` ya encodada, el `env.py` ahora la maneja bien.).
- `ENV`: entorno de ejecución (`dev`, `production`). En `dev` se completan orígenes locales y se flexibilizan claves por defecto para facilitar pruebas.
- `AI_MODE`: `auto`, `openai` u `ollama`.
- `AI_ALLOW_EXTERNAL`: si es `false`, solo se usa Ollama.
- `OLLAMA_URL`: URL base de Ollama (por defecto `http://localhost:11434`).
- `OLLAMA_MODEL`: modelo de Ollama (por defecto `llama3.1`).
- `OPENAI_API_KEY`, `OPENAI_MODEL`.
- `AI_MAX_TOKENS_SHORT`, `AI_MAX_TOKENS_LONG`: límites de tokens para respuestas cortas/largas.
- `AI_TIMEOUT_OLLAMA_MS`, `AI_TIMEOUT_OPENAI_MS`: timeouts de peticiones a proveedores.
- `SECRET_KEY`: clave usada para firmar sesiones; en producción reemplace el
  placeholder `REEMPLAZAR_SECRET_KEY`, rote el valor periódicamente y manténgalo
  fuera del control de versiones. En desarrollo se usa un valor de prueba si no
  se define uno propio.
- `SESSION_EXPIRE_MINUTES`: tiempo de expiración de la sesión en minutos (por
  defecto 1440 = 1 día). Incrementarlo prolonga las sesiones pero aumenta el
  riesgo ante robo de cookies; reducirlo fuerza reautenticaciones más frecuentes
  y eleva la seguridad.
- `COOKIE_SECURE`: activa cookies seguras; se ignora en producción donde siempre están habilitadas.
- `ALLOWED_ORIGINS`: orígenes permitidos para CORS, separados por coma. En
  desarrollo se completan automáticamente los pares `localhost`/`127.0.0.1`; en
  producción se debe especificar cada dominio explícitamente.
- `LOG_LEVEL`: nivel de logging de la aplicación (`DEBUG`, `INFO`, etc.).
- `DEBUG_SQL`: si vale `1`, SQLAlchemy mostrará cada consulta ejecutada.
- `ADMIN_USER`, `ADMIN_PASS`: credenciales del administrador inicial definidas en `.env`
  (copiado desde `.env.example`). En producción la aplicación aborta el inicio si
  `ADMIN_PASS` queda en el placeholder `REEMPLAZAR_ADMIN_PASS`.
- `MAX_UPLOAD_MB`: tamaño máximo de archivos a subir.
- `AUTH_ENABLED`: si es `true`, requiere sesión autenticada.
- `PRODUCTS_PAGE_MAX`: límite máximo de resultados por página.
- `PRICE_HISTORY_PAGE_SIZE`: tamaño por defecto al paginar el historial de precios.

### Variables para importación de PDFs

- `IMPORT_OCR_LANG`: Idioma para Tesseract OCR (por defecto `spa`).
- `IMPORT_OCR_TIMEOUT`: Timeout en segundos para el proceso de OCR (por defecto `180`).
- `IMPORT_PDF_TEXT_MIN_CHARS`: Mínimo de caracteres de texto a extraer de un PDF para considerarlo válido sin OCR (por defecto `100`).
- `IMPORT_ALLOW_EMPTY_DRAFT`: Si es `true` (default), al importar un PDF sin líneas detectables, se crea una compra en `BORRADOR` vacía. Si es `false`, se devuelve un error `422`.

## Endpoints de diagnóstico

Rutas públicas de salud:

- `GET /health`: responde `{"status":"ok"}` si la app está viva.
- `GET /health/ai`: informa los proveedores de IA disponibles.
- `GET /healthz/db`: realiza `SELECT 1` contra la base y devuelve `{"db":"ok"}`.

Rutas de diagnóstico para administradores (omitidas en producción):

- `GET /healthz`: responde `{"status":"ok"}` si la app está viva.
- `GET /debug/db`: ejecuta `SELECT 1` contra la base de datos.
- `GET /debug/config`: muestra `ALLOWED_ORIGINS` y la `DB_URL` sin contraseña.
- `GET /debug/imports/parsers`: enumera los parsers registrados para las importaciones.
- `GET /admin/import/doctor`: verifica la presencia de dependencias externas para OCR (`ocrmypdf`, `tesseract`, etc.).

## Registro de solicitudes

La API incluye un middleware que registra cada solicitud HTTP con metodo, ruta, codigo de respuesta y tiempo de respuesta. Las excepciones se capturan y se registran con traza.

- Configuracion: `LOG_LEVEL` controla el nivel de detalle; `DEBUG_SQL=1` muestra las consultas SQL.
- Ubicacion de logs: los scripts de arranque redirigen Uvicorn a `logs/backend.log` y dejan trazas de migraciones en `logs/migrations/`.

Notas adicionales de entorno:

- `HOST`, `PORT`: host y puerto del servidor de desarrollo.
- `ALEMBIC_LOG_LEVEL` y `DEBUG_MIGRATIONS`: controlan el detalle de logs de migraciones y diagnosticos.
- En `ENV=dev`, si `SECRET_KEY` y `ADMIN_PASS` quedan en placeholders se usan valores de prueba; en produccion el arranque aborta si no se reemplazan.
- SQLite opcional (dev/pruebas): `DB_URL=sqlite+aiosqlite:///ruta.db`.

## Comandos y chat

En el chat o vía API se pueden usar:

- `/help`
- `/sync pull --dry-run`
- `/sync push --dry-run`
- `/stock adjust --sku=SKU --qty=5`
- `/import archivo.xlsx --supplier=SLUG`
- `/import last --apply`
- `/search maceta`

La ruta `GET /actions` devuelve acciones rápidas.

## Flujo de chat e intents

El endpoint de chat y el WebSocket analizan cada mensaje para detectar comandos.

1. Si el texto corresponde a un intent conocido, se ejecuta el handler asociado y se retorna una respuesta estructurada.
2. Cuando el intent es desconocido, se invoca `AIRouter.run` con la tarea `Task.SHORT_ANSWER` para generar una contestación libre mediante IA.

El WebSocket utiliza la misma lógica para cada mensaje entrante y, ante una desconexión del cliente (`WebSocketDisconnect`), Starlette cierra el canal automáticamente, por lo que el servidor no invoca `close()` manualmente.

Cuando el proveedor de IA elegido no soporta la tarea solicitada, el ruteador registra una advertencia y cambia a **Ollama** como alternativa.

## Carga de catálogo desde proveedores (ingesta)

Permite subir archivos `.csv` o `.xlsx` de distintos proveedores para poblar el catálogo interno.

- El stock inicial siempre se crea en `0`.
- Los campos se normalizan según mapeos en `config/suppliers/*.yml`.
- Se puede ejecutar desde el chat o por CLI:

```bash
python -m cli.ng ingest file datos.xlsx --supplier default --dry-run
```

Con `--dry-run` se generan reportes en `data/reports/` sin tocar la base. Al aplicar sin ese flag se insertan/actualizan productos y variantes.

Si el archivo no incluye SKU ni GTIN se genera uno interno estable. Las categorías y marcas se crean si no existen y los productos quedan en estado `draft` por defecto.

### Ingesta Santa Planta (mensual)

1. En el chat adjuntá el Excel `ListaPrecios_export_XXXX.xlsx`.
2. Growen detecta automáticamente el proveedor y ejecuta un *dry-run*.
3. Revisá los reportes generados en `data/reports/`.
4. Para aplicar los cambios ejecutá `/import last --apply` en el chat o:

```bash
python -m cli.ng ingest file ListaPrecios_export_XXXX.xlsx --supplier santa-planta --dry-run
python -m cli.ng ingest last --apply
```

### Historial de precios

Cada ingestión registra los precios de compra y venta en la tabla `supplier_price_history` con las variaciones porcentuales respecto del último valor conocido.

### Stock

Los productos tienen la columna `stock` en `products` con valor inicial `0`.
La importación de listas de precios no modifica este valor; se ajusta manualmente desde el buscador o vía API.

## Gestión de proveedores

Desde la botonera puede abrirse un modal que lista los proveedores actuales y permite crear nuevos ingresando **Nombre** y **Slug**. El slug debe ser único y se utiliza para asociar parsers y archivos, por lo que conviene mantenerlo estable.

La API expone endpoints para administrar proveedores externos:

- `GET /suppliers` lista todos los proveedores con la cantidad de archivos cargados. Requiere rol `cliente`, `proveedor`, `colaborador` o `admin`.
- `POST /suppliers` crea un nuevo proveedor validando que el `slug` sea único.
- `PATCH /suppliers/{id}` actualiza el nombre de un proveedor existente.
- `GET /suppliers/{id}/files` muestra los archivos cargados por un proveedor. Requiere rol `cliente`, `proveedor`, `colaborador` o `admin`.

Estos recursos facilitan la organización de las distintas listas de precio y su historial.

## Categorías desde proveedor

Se puede proponer y generar la jerarquía de categorías a partir de un archivo de proveedor:

```bash
POST /categories/generate-from-supplier-file
{
  "file_id": 1,
  "dry_run": true
}
```

Con `dry_run=true` solo se informa qué rutas de categoría se detectarían. Si se envía `dry_run=false`, las categorías faltantes se crean respetando la jerarquía `parent_id`.

Además, `GET /categories` lista las categorías con su ruta completa y `GET /categories/search?q=` permite búsquedas parciales.

## IA híbrida

La política por defecto utiliza:

- **Ollama** para NLU y respuestas cortas.
- **OpenAI** para generación de contenido.

Instala [Ollama](https://ollama.com/download) y descarga el modelo configurado. Para deshabilitar proveedores externos establece `AI_ALLOW_EXTERNAL=false`.

## Pruebas manuales E2E

Para comprobar las mutaciones desde el navegador se documentan pruebas manuales en [tests/manual/e2e-mutations.md](tests/manual/e2e-mutations.md).

## CLI

```bash
python -m cli.ng db-init
```

## Roadmap

- M0: estructura base y stubs (este repositorio)
- M1: sincronización real con Tiendanube
- M2: mejoras de IA y comandos
- M3: despliegue completo

Contribuciones y feedback son bienvenidos.

## Catálogo (PDF)

Feature para generar un PDF de catálogo seleccionando productos desde la vista **Stock**.

Endpoints (`/catalogs/*`, roles: `admin` y `colaborador`):

- `POST /catalogs/generate` cuerpo `{ "ids": [...] }` genera un archivo timestamp `catalog_YYYYMMDD_HHMMSS.pdf` y actualiza `ultimo_catalogo.pdf` (symlink o copia).
- `GET /catalogs` lista catálogos existentes con paginación y filtros:
  - Query params: `page=1`, `page_size=20` (<=500), `from_dt=YYYY-MM-DD`, `to_dt=YYYY-MM-DD`.
  - Respuesta: `{items:[{id,filename,size,modified_at,latest}], total, page, page_size, pages}` ordenados desc.
- `GET /catalogs/{id}` / `HEAD /catalogs/{id}` / `GET /catalogs/{id}/download` accesos por id (formato `YYYYMMDD_HHMMSS`).
- `HEAD /catalogs/latest` verifica existencia del alias.
- `GET /catalogs/latest` sirve inline el más reciente.
- `GET /catalogs/latest/download` descarga el más reciente.
- `GET /catalogs/export.csv` exporta la lista (mismos filtros `from_dt`, `to_dt`).
- `DELETE /catalogs/{id}` elimina el catálogo indicado. Si el eliminado era el que apuntaba `ultimo_catalogo.pdf`, se reasigna el alias al siguiente más reciente (orden por `mtime`). Si no quedan catálogos, el alias se elimina. Respuesta: `{ "deleted": "YYYYMMDD_HHMMSS" }`.

Notas sobre `DELETE`:
- No requiere CSRF (solo roles) para alinearse con otros endpoints de lectura; si se desea endurecer, agregar `Depends(require_csrf)`.
- Detección de "latest" contempla dos modos: (1) si `ultimo_catalogo.pdf` es symlink compara el destino; (2) si es copia compara bytes.
- Retención (`CATALOG_RETENTION`) actúa solo en generación, no en delete manual.
- Intentar borrar dos veces devuelve `404` en la segunda (el archivo ya no existe).

Generación:
- Agrupa productos por categoría raíz (si no tiene, usa "Sin categoría").
- Sección 1: listado por categoría mostrando título y **precio de venta** (si existe). No incluye precio de compra ni stock.
- Sección 2: fichas 2×2 (4 por página) por categoría, sin mezclar categorías en una página. Cada ficha: imagen principal (si existe), título, **precio de venta**, descripción "blanda" (HTML sanitizado y truncado a ~1000 chars, luego 600 chars dentro de la ficha) sin tags.
- El precio de venta se toma de `product.sale_price` (cuando esté disponible) o, si está ausente, de la variante con `promo_price` o `price` mínima (fallback). Nunca se incluyen precios de compra.
- Estilo dark con acentos verde (#22C55E) y fucsia (#f0f).
- HTML → PDF vía WeasyPrint; fallback degradado ReportLab si falla la librería principal.

Dependencias:
- `weasyprint` (opcional, agregado a `pyproject.toml`; en Windows requiere dependencias GTK externas).
- `reportlab` como fallback.

Frontend:
- En `Stock` se agregó selección múltiple (checkbox por fila) y botones: **Generar catálogo**, **Ver catálogo**, **Descargar catálogo** y **Limpiar selección**.
- Generar exige al menos un producto seleccionado (alert si no).
- Ver/Descargar validan existencia con `HEAD` primero; si 404 muestra alerta.

Ruta de guardado: archivos en `./catalogos/catalog_YYYYMMDD_HHMMSS.pdf` + alias `ultimo_catalogo.pdf`.

Retención: configurar `CATALOG_RETENTION=N` (variable de entorno). Si `N>0`, se conservan solo los N catálogos más nuevos (no afecta `ultimo_catalogo.pdf`). `0` = ilimitado.

Logs:
- Sistema de logging ampliado (observabilidad fina): por cada generación se producen (a) un log detallado JSONL con pasos y (b) un resumen JSON.
- Pasos registrados (orden típico):
  1. `start` (count, user)
  2. `products_loaded` (products)
  3. `images_loaded` (images)
  4. `groups_built` (groups)
  5. `html_built` (size)
  6. `pdf_rendered` (bytes)
  7. `pdf_written` (file, bytes)
  8. `latest_updated` (mode=symlink|copy) ó `latest_update_failed`
  9. `retention_applied`
 10. `summary_written`
  (Si ocurre un error en symlink/copy se agrega `latest_update_failed`).
- Ruta de logs:
  - Resumen: `logs/catalogs/summary_YYYYMMDD_HHMMSS.json`
  - Detallado: `logs/catalogs/detail/catalog_YYYYMMDD_HHMMSS.log` (cada línea JSON independiente)
- Contenido del resumen: `{ generated_at, file, size, count, duration_ms }`.
- Retención de PDFs: controlada por `CATALOG_RETENTION` (N más recientes; 0 = ilimitado).
- Retención de logs detallados: se conservan los últimos 40 (`MAX_DETAIL_LOGS=40` en código). Los resúmenes actualmente no se purgan automáticamente.
- Ya NO se borran todos los `.log` al final: solo se aplica política de recorte a detallados antiguos; esto asegura trazabilidad forense reciente sin crecimiento descontrolado.
- Logging estructurado adicional en el logger Python (`[catalog] start / ok`).

Diagnóstico (endpoints nuevos, roles `admin|colaborador`):

- `GET /catalogs/diagnostics/status` → `{ active_generation: {running, started_at, ids}, detail_logs, summaries }`.
- `GET /catalogs/diagnostics/summaries?limit=20` → últimos resúmenes parseados.
- `GET /catalogs/diagnostics/log/{id}` → devuelve el log detallado (lista `items` + `count`). `id` formato `YYYYMMDD_HHMMSS`.

Concurrencia:
- Si ya hay una generación activa, `POST /catalogs/generate` responde `409` `{ "detail": "Ya hay una generación en curso" }` para evitar solapamientos (protección simple en memoria).

Errores típicos de generación y diagnóstico:
- `404 Productos no encontrados` si todos los IDs suministrados no existen.
- `500 No se pudo generar el PDF` ante fallo de render (WeasyPrint + fallback ReportLab agotados).
- `500 No se pudo escribir log detallado de catálogo` solo afecta observabilidad; el PDF igual puede generarse.

Uso de los logs detallados:
- Permiten medir tiempos inter-etapas (diferencia entre timestamps consecutivos) para optimización futura (ej. render HTML vs render PDF).
- Facilitan reintentos manuales si se observa cuellos en `images_loaded` o `pdf_rendered` (dependencias de librerías y fuentes).

Extensiones futuras sugeridas (no implementadas aún):
- Parametrizar `MAX_DETAIL_LOGS` por variable de entorno (`CATALOG_DETAIL_LOG_RETENTION`).
- Endpoint para métricas agregadas (p95/p99 `duration_ms`).
- Flag `dry_run` para validar estructura sin escribir archivos.

Notas futuras:
- Resumen de logs previo a la limpieza para auditoría opcional.
Frontend: incluye modal de Histórico que lista catálogos con marca 'latest', links Ver / Descargar y tamaños.

### Pruebas manuales (Catálogo PDF)

1. Generar 2 catálogos (seleccionar conjuntos distintos de productos) con ~5 s de diferencia para asegurar timestamps distintos.
2. `GET /catalogs` debe listar ambos ordenados (más nuevo primero) y exactamente uno con `latest=true`.
3. Borrar el MÁS ANTIGUO (`DELETE /catalogs/{id_antiguo}`):
  - Respuesta `200 {"deleted": id}`.
  - `GET /catalogs` solo muestra el restante y sigue `latest=true`.
  - `HEAD /catalogs/{id_antiguo}` devuelve `404`.
4. Generar un tercer catálogo. Confirmar que ahora el nuevo tiene `latest=true`.
5. Borrar el que figura como `latest` actualmente:
  - `DELETE` debe reasignar `ultimo_catalogo.pdf` al inmediatamente anterior.
  - `HEAD /catalogs/latest` sigue devolviendo `200`.
  - En Windows sin permisos de symlink puede usarse copia; validar que el contenido (tamaño) coincide con el archivo esperado.
6. Borrar el último catálogo restante y verificar:
  - `HEAD /catalogs/latest` => `404`.
  - `GET /catalogs` => lista vacía.
7. Generar 3 catálogos con `CATALOG_RETENTION=2` (ajustar variable y reiniciar backend): tras el tercero, el primero (más viejo) debe haber desaparecido automáticamente; `DELETE` sobre uno de los dos restantes debe seguir funcionando y actualizar alias según corresponda.
8. CSV export: con varios catálogos presentes llamar `GET /catalogs/export.csv?from_dt=YYYY-MM-DD&to_dt=YYYY-MM-DD`; abrir el CSV y corroborar que las filas coinciden con `GET /catalogs` filtrado.
9. Filtros de fecha: usar `from_dt` del día actual y `to_dt` anterior (debe devolver vacío); invertir para ver resultados.
10. Concurrencia: lanzar dos borrados casi simultáneos (ej. ejecutar DELETE dos veces); segunda debe devolver `404`.
11. Frontend: abrir modal Histórico, usar botón "Borrar" y confirmar toasts de éxito y refresco de la lista; borrar el `latest` y validar que la marca "latest" migra al siguiente.
12. Error handling: intentar `DELETE /catalogs/valor_malformado` (longitud distinta a 15) => `400 ID inválido`.

Checklist rápido post-borrado de latest:
- `ultimo_catalogo.pdf` apunta (symlink) o contiene (copia) el nuevo más reciente.
- No quedan referencias a un archivo inexistente.
- La paginación sigue consistente (`page_size`, `total`, `pages`).

## Importar remitos (Santa Planta)

El sistema incluye un pipeline robusto para importar remitos en formato PDF del proveedor Santa Planta, creando una compra en estado `BORRADOR`.

- **Endpoint**: `POST /purchases/import/santaplanta?supplier_id=ID&force_ocr=0|1`
- **Pipeline de parsing**: El sistema intenta extraer datos secuencialmente con `pdfplumber` (para PDFs con texto) y `camelot` (para PDFs basados en tablas). Si no se obtiene un mínimo de texto (`IMPORT_PDF_TEXT_MIN_CHARS`), se invoca automáticamente a `ocrmypdf` para aplicar OCR. La opción `force_ocr=1` fuerza la ejecución de OCR desde el inicio.
- **Política de borrador vacío**: Si tras todos los intentos no se detectan líneas, el comportamiento depende de la variable `IMPORT_ALLOW_EMPTY_DRAFT`:
    - `true` (default): Se crea una compra vacía en estado `BORRADOR` y se devuelve un status `200 OK`. La UI mostrará una advertencia.
    - `false`: Se devuelve un error `422 Unprocessable Entity` con un mensaje explicativo.
- **Respuesta**: La respuesta de la API incluye `purchase_id`, un `correlation_id` para seguimiento, y los totales parseados (`parsed.totals`).
- **Logs de importación**: Cada paso del proceso de importación (ej. "iniciando ocr", "parseando con camelot") se registra en `ImportLog`. El resultado final (éxito o fracaso) se guarda en `AuditLog`.
- **UI**: Desde la interfaz de compras, un botón "Ver logs" permite abrir un panel con el timeline de eventos, copiar el `correlation_id` y descargar el log completo en formato JSON (`GET /purchases/{id}/logs?format=json`).

## Documentación adicional

- [Importación de PDF](docs/IMPORT_PDF.md)
- [Crawler de imágenes](docs/IMAGES.md)
- [Seguridad](docs/SECURITY.md)
- [Gestión de proveedores](docs/SUPPLIERS.md)
- [Flujo de Compras y Reenvío de Stock](docs/PURCHASES.md)

## Lineamientos de agentes

Consulta [AGENTS.md](AGENTS.md) para la estructura de prompts, el uso del encabezado NG-HEADER y el checklist de PRs.

