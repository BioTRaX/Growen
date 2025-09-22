<!-- NG-HEADER: Nombre de archivo: BUG_REPORTS.md -->
<!-- NG-HEADER: Ubicación: docs/BUG_REPORTS.md -->
<!-- NG-HEADER: Descripción: Documentación del botón de reporte de errores y almacenamiento en logs -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Reporte de bugs desde la UI

Contexto
- Se agregó un botón flotante global (abajo a la derecha) visible en toda la app que permite enviar un reporte de error manual.
- Los reportes se persisten en `logs/BugReport.log` mediante un logger dedicado con rotación.

Uso
1. Hacer clic en el botón “Reportar”.
2. Escribir un breve detalle del problema (qué esperabas, qué sucedió, pasos, SKU, etc.).
3. (Opcional) Dejar activada la casilla “Adjuntar captura” para enviar una captura del estado actual de la pantalla (se toma al confirmar el envío).
4. Enviar. Se adjuntan automáticamente:
  - URL actual desde donde se realiza el reporte
  - User-Agent del navegador
  - Hora local en GMT-3 (lado cliente) y hora UTC/GMT-3 (lado servidor)
  - Si se habilita la captura: una imagen del DOM actual comprimida (JPEG por defecto) limitada en tamaño

Backend
- Endpoint: `POST /bug-report`
- Payload ejemplo:
  `{ "message": "No carga el detalle de producto", "url": "https://...", "user_agent": "...", "context": { "client_ts_gmt3": "2025-09-19T12:34:56.000Z" } }`
- Respuesta: `{ "status": "ok", "id": "br-<ts>" }`
- Log: `logs/BugReport.log` con formato de línea JSON dentro del mensaje, incluyendo `ts` (UTC) y `ts_gmt3` (servidor).
- No requiere CSRF (sólo registra logs) para permitir reporte también desde vistas sin sesión.

Capturas de pantalla (opcional)
- El frontend captura el contenido de la página con `html2canvas` y lo envía como Data URL (`image/jpeg` o `image/png`).
- El backend decodifica y guarda la imagen en `logs/bugreport_screenshots/<id>.jpg|.png` y agrega al log sólo metadatos: `screenshot_file`, `screenshot_bytes`, `screenshot_mime`.
- La imagen NO se embebe dentro de `BugReport.log` para mantenerlo liviano y legible.

Operación
- Retención: `logs/BugReport.log` es persistente y NO se limpia desde `POST /debug/clear-logs` ni desde scripts de limpieza. Se mantiene con rotación (hasta 5 archivos, 5 MB por archivo) para preservar historial de reportes.
 - Las capturas en `logs/bugreport_screenshots/` también se preservan por fuera de los borrados generales. Si se requiere una política de retención específica (p. ej., días o tamaño total), documentarla antes de aplicar cambios en scripts.
 - Las capturas en `logs/bugreport_screenshots/` se conservan por defecto. El script `scripts/cleanup_logs.py` permite aplicar una política opcional de retención:
   - `--screenshots-keep-days N`: borrar capturas más antiguas que N días (por defecto 30; 0 = deshabilitado)
   - `--screenshots-max-mb M`: mantener el tamaño total por debajo de M MB eliminando las más antiguas (por defecto 200; 0 = deshabilitado)
   - `--dry-run` para ver qué se eliminaría sin tocar archivos.

Notas
- El `ErrorBoundary` ya envía automáticamente errores no capturados a `/debug/frontend/log-error`.
- Este botón es complementario para registrar casos de negocio o flujos inesperados reportados por usuarios.
 - Privacidad: la captura incluye lo visible en la pantalla (texto, nombres, precios). Evitar incluir datos sensibles en pantalla al enviar reportes. El tamaño se limita en el cliente para no superar unos pocos cientos de KB por imagen.

## Métricas (admin)

- Endpoint: `GET /admin/services/metrics/bug-reports` (rol requerido: admin)
  - Parámetros opcionales:
    - `date_from=YYYY-MM-DD`, `date_to=YYYY-MM-DD` (si no se proveen, se usa la ventana de los últimos 7 días)
    - `with_screenshot=1` para contar sólo entradas que incluyan `screenshot_file`
  - Respuesta:
    - `{ "days": [{ "date": "YYYY-MM-DD", "count": number }...], "total": number }`
  - Fuente de datos: se parsea `logs/BugReport.log` (cada línea contiene un JSON al final) y se agrupa por día.

  ## Integración con Notion (Todos Errores)

  Modos soportados (controlados por `NOTION_MODE`):

  - `cards` (por defecto): crea/actualiza tarjetas con propiedades enriquecidas (Estado, Severidad, Servicio, etc.). Requiere un esquema de DB completo.
  - `sections`: DB mínima con una única propiedad de título (por ejemplo, "Sección"). Bajo cada página de sección ("Compras", "Stock", "App") se crean subpáginas por reporte con título `YYYY-MM-DD #N` y contenido de texto (path de screenshot y comentario).

  Flujo en modo `sections`:
  - `/bug-report` deriva la sección desde la URL del cliente: `/compras|/purchases` → Compras, `/stock` → Stock, `/admin` → App, resto → App.
  - Si la página de sección no existe en la base, se crea on-demand (requiere permisos de escritura de la integración).
  - Se crea una subpágina hija con título por fecha y número correlativo del día y se agregan párrafos con el path del screenshot (si hubo) y el comentario.
  - El middleware de 500s NO publica en Notion cuando `NOTION_MODE=sections` (solo log local).

  Variables relevantes:
  - `NOTION_FEATURE_ENABLED` (boolean)
  - `NOTION_API_KEY` (token de integración)
  - `NOTION_ERRORS_DATABASE_ID` (ID de la base "Todos Errores")
  - `NOTION_DRY_RUN` (1=solo loguea, no crea páginas)
  - `NOTION_MODE` (`cards` | `sections`)

  Validación y salud:
  - CLI: `python -m cli.ng notion validate-db` valida el esquema según el modo. En `sections` alcanza con tener una propiedad de tipo `title`; además advierte si faltan las páginas base (Compras/Stock/App).
  - `GET /admin/services/notion/health` devuelve `enabled/has_sdk/has_key/has_errors_db/dry_run` y `latency_ms` de una query simple.

### Cómo probar rápidamente (modo `sections`)

1) Variables de entorno (archivo `.env`):
  - `NOTION_FEATURE_ENABLED=1`
  - `NOTION_API_KEY=...` (token de la integración)
  - `NOTION_ERRORS_DATABASE_ID=...` (ID de la base "Todos Errores")
  - `NOTION_MODE=sections`
  - `NOTION_DRY_RUN=1` (para no escribir en Notion durante la prueba)

2) Validar base y conectividad:
  - `python -m cli.ng notion validate-db` → debe indicar la propiedad de título y advertir si faltan páginas base.

3) Smoke test sin servidor (dry-run):
  - `python scripts/smoke_notion_sections.py`
  - Esperado: tres líneas con `{ action: 'dry-run', parent: 'Compras|Stock|App', title: 'YYYY-MM-DD #1' }`.

4) Smoke vía endpoint (opcional):
  - Levantar la API y enviar `POST /bug-report` desde el frontend o con una llamada manual.
  - En modo `sections` y `NOTION_DRY_RUN=1`, la creación en Notion se simula y no realiza escritura.

5) Escritura real:
  - Cambiar `NOTION_DRY_RUN=0` y repetir el envío. Se crearán (si faltan) las páginas base en la DB y una subpágina hija por reporte.

### Checklist de despliegue (modo `sections`)

- [ ] Variables definidas: `NOTION_FEATURE_ENABLED`, `NOTION_API_KEY`, `NOTION_ERRORS_DATABASE_ID`, `NOTION_MODE=sections`, `NOTION_DRY_RUN` (0 en prod).
- [ ] La base de Notion tiene al menos una propiedad de tipo `title` (p.ej., "Sección").
- [ ] Páginas base presentes (o permisos para crearlas on‑demand): "Compras", "Stock", "App".
- [ ] Endpoint `/bug-report` operativo (revisa que `logs/BugReport.log` reciba entradas).
- [ ] Middleware 500 en backend: no publica en Notion en `sections` (esperado para reducir ruido).
- [ ] Documentación interna actualizada (esta página) y equipo informado del modo activo.

### Permisos y notas de seguridad (Notion)

- La integración debe tener acceso de lectura/escritura a la base `NOTION_ERRORS_DATABASE_ID` para crear páginas base y subpáginas.
- En `NOTION_DRY_RUN=1` no se realizan escrituras; se registran logs informativos para diagnóstico.
- El contenido publicado en subpáginas incluye texto del comentario y, si aplica, el path local del screenshot guardado por el backend.

### Troubleshooting

- `notion validate-db` falla con "No se pudo leer la base":
  - Verificar `NOTION_API_KEY` y `NOTION_ERRORS_DATABASE_ID`.
  - Confirmar que la integración tenga acceso a la base.
- Sección derivada incorrecta:
  - La heurística usa la URL del cliente: `/compras|/purchases` → Compras; `/stock` → Stock; `/admin` → App; caso contrario → App.
- No aparecen subpáginas en Notion:
  - Si `NOTION_DRY_RUN=1`, es esperable: no se escriben cambios. Cambiar a 0 para producir escrituras.
  - Revisar permisos de la integración y el ID de base.

## Catálogo de errores conocidos (modo `cards`)

Esta funcionalidad es opcional y aplica sólo cuando `NOTION_MODE=cards`. Permite sincronizar un catálogo local de patrones de errores hacia Notion como tarjetas base para seguimiento.

- Archivo de catálogo: `config/known_errors.json`
  - Estructura esperada (por patrón):
    - `id` (string, único)
    - `regex` (string, expresión regular IGNORECASE)
    - `servicio` (string: `api` | `frontend` | `worker_images` | ...)
    - `severidad` (Low | Medium | High | Critical)
    - `etiquetas` (array de strings)
    - `titulo` (string, opcional; por defecto usa `id`)
    - `sugerencia` (string, opcional)

- Publicación (CLI):
  - Pre-requisitos de entorno: `NOTION_FEATURE_ENABLED=1`, `NOTION_API_KEY=...`, `NOTION_ERRORS_DATABASE_ID=...`, `NOTION_MODE=cards`.
  - Ensayo: `python -m cli.ng notion sync-known-errors --dry-run`
  - Aplicar: `python -m cli.ng notion sync-known-errors`
  - Idempotencia: el upsert utiliza un fingerprint estable derivado del `id` del patrón.

- Propiedades esperadas en la base Notion (resumen):
  - Title (title), Estado (select), Severidad (select), Servicio (select), Entorno (select), Sección (select),
  - Fingerprint (rich_text), Mensaje (rich_text), Código (rich_text), URL (url),
  - FirstSeen (date), LastSeen (date), Etiquetas (multi_select), Stacktrace (rich_text), CorrelationId (rich_text)

Notas:
- Si tu base no tiene estas propiedades, ajusta el esquema o adapta el mapeo en `services/integrations/notion_errors.py`.
- Este catálogo no interfiere con el modo `sections`; son flujos independientes controlados por `NOTION_MODE`.
