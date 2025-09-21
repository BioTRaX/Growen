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

  - Si `NOTION_FEATURE_ENABLED=true` y se configuran `NOTION_API_KEY` y `NOTION_ERRORS_DATABASE_ID`, cada reporte de `/bug-report` intenta crear/actualizar una tarjeta en Notion en background (sin bloquear la respuesta).
  - La sección (Compras/Stock/Productos) se deriva automáticamente a partir de la URL del cliente; si no aplica, queda "General".
  - Los errores 500 no manejados también generan tarjeta (middleware en `services/api.py`) con deduplicación por fingerprint.

  Variables relevantes:
  - `NOTION_FEATURE_ENABLED` (boolean)
  - `NOTION_API_KEY` (token de integración)
  - `NOTION_ERRORS_DATABASE_ID` (ID de la base "Todos Errores")
  - `NOTION_DRY_RUN` (1=solo loguea, no crea páginas)

  Health:
  - `GET /admin/services/notion/health` devuelve `enabled/has_sdk/has_key/has_errors_db/dry_run` y `latency_ms` de una query simple.
