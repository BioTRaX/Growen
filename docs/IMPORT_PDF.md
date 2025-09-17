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

### Eventos IA (fallback)
Cuando la característica está habilitada (`IMPORT_AI_ENABLED=true`) y:
1. El pipeline clásico no produce líneas, **o**
2. Produce líneas pero la confianza clásica (`classic_confidence`) es menor a `IMPORT_AI_CLASSIC_MIN_CONFIDENCE`,
se invoca un intento de extracción vía modelo de lenguaje. Eventos registrados:

- `ai:request` → intento (attempt, model)
- `ai:ok` → éxito de parseo IA (lines, overall)
- `ai:merged` → líneas IA agregadas (added, ignored_low_conf)
- `ai:no_data` → IA no aportó líneas (reason)
- `ai:skip_disabled` → IA deshabilitada o falta API key
- `ai:exception` → error interno no bloqueante

`classic_confidence` (0–1) es una heurística basada en:
- Proporción de líneas con SKU
- Proporción con cantidad > 0
- Proporción con costo > 0
- Diversidad de SKU (únicos / total)

Si `classic_confidence` < `IMPORT_AI_CLASSIC_MIN_CONFIDENCE`, la IA actúa en modo “refuerzo” y puede agregar líneas adicionales (sin reemplazar las existentes) si superan el umbral de confianza individual.

### Variables de entorno IA
| Variable | Descripción | Default |
|----------|-------------|---------|
| `IMPORT_AI_ENABLED` | Habilita el fallback IA | `false` |
| `IMPORT_AI_MIN_CONFIDENCE` | Umbral mínimo por línea para fusionar | `0.86` |
| `IMPORT_AI_CLASSIC_MIN_CONFIDENCE` | Umbral de confianza clásica para disparar IA con líneas presentes | `0.55` |
| `IMPORT_AI_MODEL` | Modelo a invocar | `gpt-4o-mini` |
| `IMPORT_AI_TIMEOUT` | Timeout por request (s) | `40` |
| `IMPORT_AI_MAX_RETRIES` | Reintentos en errores transitorios | `2` |
| `OPENAI_API_KEY` | API key OpenAI (si falta se ignora IA) | — |

### Salvaguardas IA
- Validación estricta Pydantic (tipos/rangos) antes de usar datos.
- Líneas IA con `confidence < IMPORT_AI_MIN_CONFIDENCE` se descartan.
- No reemplaza líneas clásicas; sólo agrega (fase 2: también cuando baja confianza).
- Errores de red/JSON no abortan la importación (solo eventos WARN/INFO).

- Cómo ver logs de una compra:
  - `GET /purchases/{id}/logs?limit=200` (incluye `AuditLog` + `ImportLog` con `correlation_id`)
  - En la UI, en Detalle de compra → “Logs de importación”.

- Servicio Importador (estado y deps):
  - `GET /admin/services/pdf_import/status`
  - `GET /health/service/pdf_import` (chequea `ocrmypdf`, `tesseract`, `qpdf`, `ghostscript`, `camelot`)

## Limpieza de logs
- Archivos (`logs/`): `python scripts/clear_logs.py`
- Tablas de logs (no críticas): `python -m tools.clear_db_logs` (usar `--include-audit` para incluir `audit_log`).

