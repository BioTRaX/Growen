<!-- NG-HEADER: Nombre de archivo: IMPORT_PDF.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_PDF.md -->
<!-- NG-HEADER: Descripción: Flujo de importación de PDF con OCR -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Importación de PDF

El proceso de importación de PDF sigue el siguiente pipeline:
1. `pdfplumber` intenta extraer texto y tablas.
2. `Camelot` (lattice/stream) busca tablas si no hubo éxito con pdfplumber.
3. Si el PDF no contiene suficiente texto o se fuerza el proceso, se ejecuta OCR con `ocrmypdf` y se reintenta la extracción.

## Flags relevantes
- `debug`: genera información adicional para diagnósticos (eventos del pipeline, muestras de filas).
- `force_ocr`: fuerza el uso de OCR incluso si el PDF tiene texto.

## Política de borrador vacío
- Controlada por `IMPORT_ALLOW_EMPTY_DRAFT` (por defecto `true`).
- Puede sobrescribirse en runtime vía variable de entorno.
- Si el pipeline no detecta líneas, en dev puede crearse un BORRADOR vacío con el PDF adjunto y logs asociados.

## Anti-duplicados (SKU y título)
- Durante la normalización de líneas se aplica un filtro de duplicados por:
  - SKU del proveedor (`supplier_sku`) normalizado a minúsculas.
  - Título normalizado (sin acentos, minúsculas, espacios colapsados).
- Las líneas descartadas no se cargan; se registran métricas en `AuditLog` e ítems `WARN` en `ImportLog` (`dedupe/ignored_duplicates_by_*`).

## Encabezados y correlación
- Todas las respuestas del import incluyen `X-Correlation-ID` en headers.
- En caso de error (`422`, `409` o `500`) se devuelve también ese header para facilitar el diagnóstico.

## Respuesta
- Siempre incluye `purchase_id`, `status` y `correlation_id`.
- Con `debug=1` devuelve `debug.events` (resumen) y `debug.samples` (hasta 8 líneas parseadas) para diagnóstico.

## Trazabilidad y diagnóstico
- Eventos del pipeline (ejemplos):
  - `header_extract:text_stats` → páginas y cantidad de caracteres
  - `pre_ocr:pdf_has_text` → si hay texto suficiente (threshold configurable)
  - `pdfplumber:tables_found` → tablas detectadas por página
  - `pdfplumber:lines_detected` → cantidad de líneas normalizadas
  - `camelot:tables_found` → tablas detectadas por flavor
  - `ocr:ocrmypdf_run` → resultado de OCR (ok/tiempo/stdout/stderr)
  - `summary:done` / `summary:no_lines_after_pipeline`

- Cómo ver logs de una compra:
  - `GET /purchases/{id}/logs?limit=200` (incluye `AuditLog` + `ImportLog` con `correlation_id`)
  - En la UI, en Detalle de compra → “Logs de importación”.

- Servicio Importador (estado y deps):
  - `GET /admin/services/pdf_import/status`
  - `GET /health/service/pdf_import` (chequea `ocrmypdf`, `tesseract`, `qpdf`, `ghostscript`, `camelot`)

## Limpieza de logs
- Archivos (`logs/`): `python scripts/clear_logs.py`
- Tablas de logs (no críticas): `python -m tools.clear_db_logs` (usar `--include-audit` para incluir `audit_log`).

