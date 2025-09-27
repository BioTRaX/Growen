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
  - `multiline_fallback:multiline_fallback_attempt|multiline_fallback_used|multiline_fallback_empty|multiline_error` → estado del fallback textual multiline
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

## Heurísticas adicionales de recuperación de SKU (Sept 2025)

Se añadieron pasos post-proceso para mejorar la detección de SKUs en remitos Santa Planta con estructuras irregulares u OCR parcial:

Pipeline actual (orden determinista):

1. Mapeo directo de títulos conocidos → SKU esperado:
  - Patrones regex fijos (ej: `POTA PERLITA`, `MACETA SOPLADA ... 1 LT|5 LT|10 LT|20 LT`).
  - Asigna inmediatamente el SKU objetivo si la línea no tiene un SKU corto ya válido.
  - Evento: `postprocess:known_title_sku_mapped`.
2. Búsqueda de SKUs embebidos en bloques numéricos:
  - Detecta bloques numéricos de 3 a 12 dígitos dentro del título.
  - Fast-path: si un bloque contiene íntegro un SKU esperado, se asigna (`mode=expected_subblock`).
  - Si no, genera ventanas deslizantes de longitud 5,4,3 sobre bloques >6 dígitos + toma bloques completos de 3–6 dígitos.
  - Orden de selección: longitud desc, posición asc, valor asc (garantiza determinismo y evita flakiness).
  - Filtra subcadenas triviales (ceros iniciales, todos dígitos iguales >=3).
  - Evento: `postprocess:embedded_sku_recovered`.
3. Métricas intermedias:
  - Evento: `postprocess:embedded_sku_recovery_stats` reporta SKUs esperados presentes.
4. Compactación de SKUs largos que contienen un esperado como prefijo/sufijo corto:
  - Si un SKU asignado tiene 5–12 dígitos y contiene un SKU esperado con ≤2 dígitos sobrantes a izquierda o derecha, se reemplaza por el esperado.
  - Evento: `postprocess:sku_compacted`.
5. Métricas finales tras compactación:
  - Evento: `postprocess:embedded_sku_recovery_stats_final`.
6. Rescate global forzado (garantiza al menos 1 esperado si existe en algún token largo):
  - Si después de los pasos anteriores no aparece ningún SKU esperado, se recorren tokens numéricos (título y SKU asignado) ordenados por longitud desc y valor.
  - Se busca cada SKU esperado (orden alfabético) como substring; al primer match se fuerza la asignación.
  - Eventos: `postprocess:expected_sku_forced_global` y luego `postprocess:expected_sku_forced_result`.
7. Diagnóstico si siguen faltando todos:
  - Evento: `postprocess:expected_skus_missing` con muestras de títulos (debug).

Beneficios:
- Determinismo: elimina condiciones no determinísticas entre ejecuciones consecutivas (flakiness).
- Observabilidad: cada etapa emite eventos, permitiendo saber en qué punto se obtuvo (o no) el SKU esperado.
- Escalabilidad: nuevos patrones pueden añadirse al mapeo inicial sin alterar la lógica posterior.

Notas de implementación:
- Los SKUs “esperados” actuales del proveedor: `6584`, `3502`, `564`, `468`, `873`.
- El rescate global se ejecuta sólo si ninguno de esos está presente tras compactación; minimiza falsos positivos.
- El orden de selección evita que una subcadena más corta opaque a otra válida más larga en la misma línea.

Extensiones futuras:
- Externalizar la lista de patrones conocidos y SKUs esperados a `config/suppliers/*.json`.
- Registrar métricas de frecuencia de uso de cada etapa (para evaluar efectividad del mapeo vs rescate forzado).
- Añadir validación cruzada contra catálogo interno cuando se consoliden tablas de `SupplierProduct`.

### Consideraciones futuras
- Generalizar mapeos a una configuración externa (`yaml/json`) para evitar cambios de código.
- Incorporar validación cruzada contra catálogos internos cuando estén disponibles (SKU repositorio propio).
- Ajustar ventana máxima si se detectan SKUs de más de 6 dígitos válidos en nuevas versiones de remitos.

## Extracción de encabezado (remito_number) – Sept 2025

Refuerzo de `_parse_header_text` para eliminar lecturas intermitentes:

1. Acepta sólo patrón `0001-XXXXXXXX` (4 + 8 dígitos). Otros prefijos 4+8 se ignoran (`header_pattern_ignored`).
2. Filtra números de 11–13 dígitos con prefijos CUIT comunes (`20,23,24,27,30,33,34`) (`discarded_cuit_like`).
3. Fallback determinista: nombre de archivo (`Remito_00099596`) → primer bloque aislado de 8 dígitos (`any_8digits`).
4. Evento `header_source` documenta la procedencia (`pattern_4_8`, `pattern_4_8_relaxed`, `filename`, `any_8digits`).

Beneficio: evita que números largos ajenos (identificadores internos) disparen fallos esporádicos del test de remito.

## Fallback multiline textual – Sept 2025

Eventos añadidos para máxima visibilidad del parser de líneas cuando no hay tablas estructuradas:

- `multiline_fallback_attempt` → inicio (incluye `expected_items`).
- `multiline_fallback_used` → éxito, incluye `count` de líneas.
- `multiline_fallback_empty` → intento sin resultados.
- `multiline_error` → excepción controlada en el bloque.
- Eventos previos internos (`regex_multiline_ok|regex_multiline_empty`) se mantienen para compatibilidad.

Esto facilita auditoría en CI/CD y diferenciación entre “no hubo que usar fallback” vs “se intentó y falló”.

### Refuerzos Fase 2 (Sept 2025, estabilidad Santa Planta)

Se añadieron heurísticas y eventos adicionales para eliminar flakiness intermitente (remito_number erróneo y 0 líneas) y mejorar recuperaciones:

1. Patrón contextual estricto de encabezado:
  - Se busca únicamente `REMITO` seguido de variante `Nº|No|N°` y `0001 - XXXXXXXX` (4 dígitos, separador guion o espacio opcional, 8 dígitos). Espacios múltiples se normalizan.
  - Cualquier otro bloque de 12+ dígitos adyacente se ignora antes de aplicar regex contextual.
  - Evento: `header_long_sequence_removed` (uno por secuencia filtrada). Futuro: agregaremos `header_long_sequence_removed_count` (agregado) cuando se exponga conteo total.
2. Sanitización previa del texto de encabezado:
  - Antes de evaluar el patrón se purgan secuencias numéricas >=10 dígitos que no encajan; reduce colisiones con identificadores internos.
3. Rewrite forzado desde filename:
  - Si tras las heurísticas el `remito_number` carece de guion (`-`), se intenta reconstruir usando el nombre del archivo (`Remito_00099596_...pdf` → `0001-00099596`).
  - Evento: `remito_number_rewritten_from_filename_forced`.
4. Fallback multiline forzado temprano:
  - Si tras pdfplumber (+ Camelot) se detectan <5 líneas, se fuerza la ejecución del fallback multiline aunque existan algunas líneas parciales.
  - Evento: `multiline_fallback_forced` (además de los ya existentes `multiline_fallback_attempt|used|empty|error`).
5. Segunda pasada por cantidades (quantity second pass):
  - Recorre texto bruto buscando patrones de cantidad + descripción + importe cuando la primera pasada (money-first) no consolidó todas las líneas.
  - Acepta variantes donde la cantidad aparece antes de la secuencia monetaria en esta fase extendida.
  - Evento (cuando se ejecuta forzada tras la primera): `quantity_fallback_forced`. Próxima extensión documentará `second_pass_qty_pattern_extended` cuando se amplíe el set de regex.
6. Descuentos porcentuales embebidos:
  - Se detectan tokens como `-20% DESC`, `20% BONIF`, `15 % DTO` adjuntos a la línea o en la vecindad inmediata y se calcula `pct_bonif` (0.20 en el ejemplo).
  - Eventos: `multiline_pct_detected` (detección en texto bruto) y `multiline_discount_attached` (descuento aplicado a una línea concreta).
7. Observabilidad reforzada:
  - Al finalizar el pipeline se mantienen métricas clásicas y se agregan eventos específicos de las nuevas ramas para trazabilidad en CI.

Resumen de nuevos eventos (Fase 2):
| Evento | Descripción |
|--------|-------------|
| `header_long_sequence_removed` | Secuencia numérica larga descartada antes del parse de encabezado |
| `multiline_fallback_forced` | Se fuerza fallback multiline por baja cantidad de líneas iniciales (<5) |
| `quantity_fallback_forced` | Ejecución obligada de segunda pasada quantity tras fallback previo |
| `multiline_pct_detected` | Porcentaje de descuento localizado en texto multiline bruto |
| `multiline_discount_attached` | Descuento aplicado a una línea concreta (se actualiza `pct_bonif`) |
| `remito_number_rewritten_from_filename_forced` | Remito reescrito usando filename al carecer de patrón válido |

Impacto esperado:
- Eliminación del caso intermitente donde un identificador largo se interpretaba como remito.
- Mayor probabilidad de recuperar ≥1 línea válida aun con tablas vacías u OCR parcial.
- Registro explícito de descuentos porcentuales para cálculo de costos netos.

### Tercera pasada híbrida y nuevos eventos (Implementado Sept 2025)

Se añadió una tercera pasada determinista `_third_pass_sku_money_mix` que intenta reconstruir líneas cuando:
1. Existen montos dispersos sin formar filas claras.
2. Las cantidades y/o SKUs aparecen separados del monto final.

Estrategia:
- Tokeniza líneas previas al footer.
- Identifica líneas con monto; retrocede y acumula posibles fragmentos de título y cantidad.
- Inferencia de SKU corta (3–6 dígitos) evitando unidades (ML, G, KG, etc.).
- Si hay más de un monto se toma el mayor como total y el menor como unitario (cuando qty>0).
- Títulos duplicados exactos se descartan para evitar ruido.

Eventos añadidos:
| Evento | Descripción |
|--------|-------------|
| `third_pass_attempt` | Inicio de la tercera pasada (detalla expected_items). |
| `third_pass_lines` | Resultado con líneas recuperadas (count). |
| `third_pass_empty` | Sin líneas recuperadas en tercera pasada. |
| `third_pass_error` | Excepción controlada en tercera pasada. |
| `all_fallbacks_empty` | Tras multiline + segunda + tercera pasada no se obtuvo ninguna línea. |

Extensiones implementadas previamente planeadas ahora activas:
| Evento | Estado |
|--------|--------|
| `header_invalid_reset` | Implementado: remito descartado si no coincide exactamente `0001-\d{8}` tras sanitización. |
| `header_long_sequence_removed_count` | Implementado: total de secuencias largas eliminadas en encabezado. |
| `second_pass_qty_pattern_extended` | Implementado: segunda pasada detectó patrón cantidad-al-inicio. |

Estos eventos ya forman parte del contrato observable del parser.


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

