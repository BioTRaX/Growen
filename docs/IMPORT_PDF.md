<!-- NG-HEADER: Nombre de archivo: IMPORT_PDF.md -->
<!-- NG-HEADER: Ubicación: docs/IMPORT_PDF.md -->
<!-- NG-HEADER: Descripción: Flujo de importación de PDF con OCR -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Importación de PDF

El proceso de importación de PDF sigue el siguiente pipeline:
1. `pdfplumber` extrae texto y se detectan encabezado (remito/fecha) y anchors del pie: “Cantidad De Items: N” e “Importe Total: $ …”. Estos datos funcionan como control de calidad del parser.
2. `pdfplumber` intenta extraer tablas; se unen títulos multilínea (wrap) hasta encontrar una fila válida (SKU/Cant./números). Se generan métricas y muestras de filas.
3. Si no cierra el conteo de líneas esperado o `pdfplumber` no produce resultados, se prueba `Camelot` en dos sabores: lattice y stream. Se elige el mejor resultado y se corta si se alcanza exactamente el conteo esperado.
4. Si el PDF no contiene suficiente texto o se fuerza el proceso, se ejecuta OCR con `ocrmypdf` y se reintenta la extracción (primero `pdfplumber`, luego `Camelot` por sabores). Se limpia la salida OCR temporal al finalizar.
5. Si aún no se detectan líneas, se aplica un fallback heurístico textual (parser RegEx) para intentar recuperar líneas.

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
  - `fallback:regex_parser_attempt|ok|no_lines|error` → estado del fallback textual
  - `summary:done` / `summary:no_lines_after_pipeline`
   - `footer:expected_from_footer` → N de ítems esperado e importe total
   - `validation:expected_items_check` → comparación esperado vs obtenido
   - `validation:importe_total_check` → comparación de sumatoria vs importe total del documento (tolerancia de centavos)

  Además se persiste un resumen de intentos (`stage=attempts,event=summary`) con los tiempos por estrategia (pdfplumber, camelot-lattice, camelot-stream, ocr-*) y cantidad de líneas.

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

Todos los eventos IA (`stage="ai"`) registran `duration_s` (segundos) cuando aplica, lo que habilita calcular latencias en los endpoints de m?tricas.

`classic_confidence` (0–1) es una heurística ponderada basada en:
- Proporción de líneas con SKU (peso alto)
- Proporción con cantidad > 0
- Proporción con costo > 0
- Diversidad de SKU (únicos / total)
- Densidad numérica: proporción de tokens numéricos significativos respecto al total de tokens de títulos (mitiga escenarios de texto ruidoso sin datos transaccionales).

### Densidad numérica
Se calcula sobre los títulos normalizados: se tokeniza por `\W+`, se cuentan tokens numéricos de longitud 2–8 que no lucen como fechas triviales y se divide por el total de tokens (>=1). La densidad se trunca a [0,1].

### Sanitización de outliers
Antes de computar métricas de cantidad y costo se aplican reglas:
- Cantidad > 10,000 se clampa a 10,000 (evita inflar artificialmente proporciones por OCR defectuoso).
- `unit_cost_bonif` > 10,000,000 se ignora para la métrica de costo.
Esto reduce el impacto de lecturas anómalas en PDFs mal escaneados.

### Logging de la confianza
Cada importación registra un evento `ImportLog` con:
```
stage = "heuristic"
event = "classic_confidence"
details = { "value": <float>, "lines": <int> }
```
Esto habilita agregaciones y monitoreo histórico.

### Endpoint de métricas agregadas
`GET /admin/services/pdf_import/metrics` devuelve:
```json
{
  "total_imports": 123,
  "avg_classic_confidence": 0.71,
  "ai_invocations": 8,
  "ai_success": 6,
  "ai_success_rate": 0.75,
  "ai_lines_added": 14,
  "last_24h": {
    "avg_classic_confidence": 0.69,
    "ai_invocations": 2,
    "ai_success": 2,
    "ai_success_rate": 1.0,
    "ai_lines_added": 5
  }
}
```

### Endpoint de estad?sticas IA

`GET /admin/services/pdf_import/ai_stats` expone m?tricas granulares del fallback IA (acumuladas y para las ?ltimas 24 horas):

- `requests`, `success`, `success_rate`, `no_data`, `skip_disabled`.
- `errors` desglosa causas (`server_error`, `bad_status`, `json_decode_fail`, `validation_fail`, `empty_content`, `exception`).
- `avg_overall_confidence` resume la confianza promedio de las respuestas IA.
- `lines_proposed_total` / `lines_proposed_avg_per_success` y `lines_added_total` / `lines_added_avg_per_success` permiten medir aporte efectivo.
- `ignored_low_conf_total` cuantifica l?neas descartadas por baja confianza.
- `durations_ms` incluye `count`, `avg` y `p95` (milisegundos) a partir del campo `duration_s` registrado en ImportLog.
- `model_usage` lista cada modelo invocado con su participaci?n (`share`).
- `last_24h` repite la estructura limitada a la ventana de 24 horas.

Con estas m?tricas se monitorea la latencia de la IA y su efectividad para enriquecer importaciones problem?ticas.
Con esto se puede detectar degradaciones (ej. caída brusca de `avg_classic_confidence` o aumento de invocaciones IA con baja tasa de éxito).

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
Al finalizar cada importación, el backend ejecuta una limpieza ligera de archivos de `logs/` para dejar el entorno listo para un nuevo inicio (no bloqueante):

- Elimina rotaciones antiguas y archivos auxiliares grandes.
- Trunca `logs/backend.log` si es posible (si está bloqueado en Windows se deja un marcador).
- Mantiene `BugReport.log` y sus rotaciones.

Herramientas relacionadas:
- Archivos (`logs/`): `python scripts/clear_logs.py`
- Limpieza avanzada (`logs/` + capturas): `python scripts/cleanup_logs.py`
- Tablas de logs (no críticas): `python -m tools.clear_db_logs` (usar `--include-audit` para incluir `audit_log`).


## Notas sobre confirmación y stock/precios (Sept 2025)
- Al confirmar una compra (`POST /purchases/{id}/confirm`), si alguna línea no tenía `supplier_item_id` pero sí `supplier_sku`, el sistema intentará auto-vincularla con el `SupplierProduct` del proveedor por SKU al momento de la confirmación. Si el `SupplierProduct` ya está enlazado a un `Product` interno, se aplicará el impacto de stock y se actualizará `current_purchase_price` en `SupplierProduct` con registro en `price_history`.
- Si una compra ya confirmada necesitara re-aplicar stock (por ejemplo, por fallas de listeners externos), usar `POST /purchases/{id}/resend-stock?apply=1`. Este endpoint ahora también intenta resolver el vínculo por SKU cuando sea posible antes de aplicar stock. Por diseño, no re-escribe historial de precios para evitar duplicar eventos de precio.
- Política estricta opcional: si `PURCHASE_CONFIRM_REQUIRE_ALL_LINES=1`, la confirmación aborta con `422` si quedan líneas sin poder vincularse. Si está en `0` (default), se confirma y se registran `unresolved_lines` en `AuditLog`.

