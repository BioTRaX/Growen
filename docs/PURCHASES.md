<!-- NG-HEADER: Nombre de archivo: PURCHASES.md -->
<!-- NG-HEADER: Ubicación: docs/PURCHASES.md -->
<!-- NG-HEADER: Descripción: Documentación de endpoints y flujo de Compras -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Compras (Purchases)

Esta documentación cubre el flujo de importación, validación, confirmación y reenvío de stock, así como utilidades de diagnóstico.

## Estados
`BORRADOR -> VALIDADA -> CONFIRMADA -> ANULADA`

## Endpoints principales

- `POST /purchases` Crea compra (BORRADOR)
- `PUT /purchases/{id}` Actualiza encabezado y líneas
- `POST /purchases/{id}/validate` Valida líneas (marca OK / SIN_VINCULAR)
- `POST /purchases/{id}/confirm` Confirma (impacta stock y precios)
- `POST /purchases/{id}/rollback` Rollback (revierte stock de una CONFIRMADA y marca ANULADA)
- `POST /purchases/{id}/cancel` Anula (revierte stock si estaba confirmada)
- `POST /purchases/import/santaplanta` Importa PDF y genera líneas
- `POST /purchases/{id}/resend-stock` Reenvía stock (nueva funcionalidad)

### Validación de compras (`POST /purchases/{id}/validate`)

Reglas clave de validación a partir del 2025-09-22:

- Si una línea tiene `supplier_sku`, se valida su existencia exacta en la base del proveedor (`SupplierProduct`) por `(supplier_id, supplier_product_id)`.
  - Si existe: la línea se marca `OK`. Si faltaba, se auto-completa `supplier_item_id` y (si corresponde) `product_id`.
  - Si NO existe: la línea se marca `SIN_VINCULAR` y se agrega el SKU faltante al arreglo `missing_skus`.
- Si una línea no tiene `supplier_sku`:
  - Se mantiene el comportamiento previo: `OK` sólo si ya está vinculada por `product_id` o `supplier_item_id`; en caso contrario `SIN_VINCULAR`.

Respuesta típica:

```json
{
  "status": "ok",
  "lines": 12,
  "unmatched": 3,
  "linked": 5,
  "missing_skus": ["ABC-123", "XYZ-9"]
}
```

Notas:
- `missing_skus` es una lista única de SKUs de proveedor ausentes en la base (puede haber múltiples líneas afectadas por el mismo SKU).
- `linked` cuenta cuántas líneas pudieron auto-vincularse durante la validación (por ejemplo, cuando existía el `SupplierProduct` pero la línea aún no tenía `supplier_item_id`).
- Esta validación no crea productos ni ítems de proveedor; sólo detecta y vincula si ya existen.

Impacto en importación de Santa Planta:
- Se deshabilitó el enlace difuso por título para evitar falsos positivos. La importación prioriza coincidencia exacta por `supplier_sku` y, en su defecto, heurísticas seguras (p. ej. tokens numéricos), pero no realizará auto-vínculos por similitud de texto.
- Recomendación: usar “Crear y vincular” desde Compras para los casos faltantes, o apoyarse en el validador IA (iAVaL) para sugerencias no vinculantes.


### iAVaL — Validador de IA del remito

Valida y propone correcciones del encabezado y líneas de una compra en BORRADOR comparando el documento del remito (PDF o EML) con los datos importados.

- `POST /purchases/{id}/iaval/preview`
  - Precondiciones:
    - `status == BORRADOR`
    - La compra tiene al menos un documento adjunto legible: PDF (preferido) o EML (correo)
  - Acción: extrae texto del adjunto (PDF preferido; si no hay, intenta EML), construye prompt con snapshot de la compra y el nombre del proveedor, invoca IA y devuelve una propuesta de cambios en formato estructurado con diffs amigables.
  - Respuesta:
    - `proposal`: `{ header, lines[] }`
    - `diff`: `{ header: { campo: {old,new} }, lines: [{ index, changes: { campo: {old,new} } }] }`
    - `confidence`: número [0..1]
    - `comments`: array de strings
    - `raw`: salida cruda del proveedor IA (solo texto)

- `POST /purchases/{id}/iaval/apply`
  - Precondición: `status == BORRADOR`
  - Body: `{ "proposal": { "header": {...}, "lines": [...] } }`
  - Query opcional: `emit_log=1` para generar archivos de logs de cambios (JSON y CSV) con timestamp y metadatos del remito.
  - Cambios permitidos:
    - Header: `remito_number`, `remito_date` (ISO), `vat_rate`
    - Líneas por índice: `qty`, `unit_cost`, `line_discount`, `supplier_sku`, `title`
  - Efecto: aplica cambios, registra `AuditLog` con acción `purchase.iaval.apply` y devuelve resumen `applied`.
  - Si `emit_log=1`: genera `data/purchases/{id}/logs/iaval_changes_<YYYYMMDD_HHMMSS>.json` y `...csv` (CSV con columnas `type,index,field,old,new`), registra `purchase.iaval.emit_change_log`. La respuesta incluye `log: { filename, path, csv_filename?, url_json?, url_csv? }`.

- `GET /purchases/{id}/logs/files/{filename}`
  - Descarga de archivos de logs (JSON/CSV) del flujo iAVaL.
  - Validación: `filename` debe comenzar con `iaval_changes_` y terminar en `.json` o `.csv` (se mitiga path traversal).
  - Content-Disposition: `attachment`.

Notas:
- No realiza re-asociación automática de `product_id`/`supplier_item_id`.
- Si no hay diferencias detectadas, el diff será vacío y se recomienda no aplicar cambios.
- La calidad del documento afectará la extracción de texto: para PDF se usa `pdfplumber` si está disponible; para EML se preferirá el cuerpo HTML, con fallback a texto plano.

## Notas sobre creación mínima de productos (/catalog/products)

Este endpoint existe como atajo mínimo para pruebas y herramientas internas; no reemplaza el flujo completo de creación usado por Compras.

- `POST /catalog/products`
  - Campos `purchase_price` y `sale_price` son opcionales.
  - Si se informan ambos, se registra un ítem en el historial de precios (SupplierPriceHistory) con la fecha del día.
  - Si se informa sólo `purchase_price` y no `sale_price`, se inicializa `current_sale_price = purchase_price` (no genera historial).
  - Si falta alguno de los dos (salvo el caso anterior), NO se genera historial. Aun así, se guardan los valores actuales en el ítem del proveedor (`current_purchase_price`/`current_sale_price`) sólo si fueron provistos.
  - Pensado para entornos de prueba y bootstrap; en producción, preferir flujos completos.

- `POST /products` (flujo preferido)
  - Usado por el flujo de Compras. La confirmación de compras impacta stock y puede actualizar precios en estructuras correspondientes.
  - Evita inconsistencias típicas de la creación mínima cuando hay reglas adicionales (equivalencias, canónicos, etc.).

## Reenvío de Stock (`/purchases/{id}/resend-stock`)
Permite volver a aplicar (o previsualizar) los deltas de stock de una compra **ya CONFIRMADA**.

### Casos de uso
- Reprocesar stock tras un rollback parcial o corrupción manual.
- Auditar diferencias detectadas en inventario.
- Asegurar consistencia si falló un paso externo (ej. sincronización a otro sistema) y se decide volver a sumar.

### Reglas
- Solo permitido si `status == CONFIRMADA`.
- No reescribe precios de compra ni genera nuevos `PriceHistory`.
- Soporta preview (`apply=0`) y ejecución real (`apply=1`).
- Incluye modo debug para devolver `applied_deltas`.
- Registra `AuditLog` con acciones:
  - `purchase_resend_stock_preview`
  - `purchase_resend_stock`
- Persiste timestamp del último apply en `purchase.meta.last_resend_stock_at`.

### Cooldown
Se evita el doble reenvío accidental con un cooldown configurable:
- Variable: `PURCHASE_RESEND_COOLDOWN_SECONDS` (default: 300 segundos).
- Si se intenta `apply=1` antes de que expire el período → HTTP 429.

### Parámetros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| apply | int (0/1) | 0 | 0=preview (no modifica), 1=aplica deltas |
| debug | int (0/1) | 0 | 1 incluye `applied_deltas` en respuesta y audit log |

### Respuesta (preview)
```json
{
  "status": "ok",
  "mode": "preview",
  "applied_deltas": [
    { "product_id": 12, "product_title": "X", "old": 40, "delta": 5, "new": 45, "line_id": 881 }
  ],
  "unresolved_lines": []
}
```

### Respuesta (apply)
Igual estructura pero `mode: "apply"` y stock actualizado.

### Errores frecuentes
| Código | Motivo |
|--------|--------|
| 400 | Compra no está CONFIRMADA |
| 404 | Compra inexistente |
| 429 | Cooldown activo |

## Verificación de totales al confirmar y Rollback

## Autocompletado de líneas (enriquecimiento) — Sept 2025

El endpoint `PUT /purchases/{id}` puede ejecutar un proceso de autocompletado heurístico de las líneas para rellenar datos faltantes y detectar anomalías menores. Está deshabilitado por defecto y se activa con la variable de entorno `PURCHASE_COMPLETION_ENABLED`.

### Objetivos
- Rellenar `unit_cost` si la línea carece de costo explícito pero puede inferirse (futuro: catálogo / historial de precios).
- Rellenar `line_discount` (porcentaje) si se dispone de pista contextual o estimación (placeholder actual: mantiene valor provisto; no inventa descuentos).
- Normalizar / validar `supplier_sku` cuando aparece vacío y la heurística pueda sugerir uno (actualmente no sugiere, sólo conserva cuando existe).
- Marcar indicadores estadísticos (outliers de precio, líneas enriquecidas) para futura auditoría o UI.

### Flujo actual (versión inicial / stub)
1. Después de aplicar las mutaciones de líneas del payload, si `PURCHASE_COMPLETION_ENABLED` ∈ {`1`,`true`,`True`} se construye una lista de `LineDraft`.
2. Se invoca `complete_purchase_lines` (módulo `services/purchases/completion.py`).
3. Por cada resultado (`LineCompletionResult`) se actualizan sólo campos vacíos o en cero (principio de no sobrescritura).
4. Se emite un log estructurado vía `_purchase_event_log` con evento `purchase_completion_stats`.
5. Fallos internos no abortan la operación: se loguea `purchase_completion_error` y se continúa.

### Eventos
| Evento | stage implícito | Detalle |
|--------|-----------------|---------|
| `purchase_completion_stats` | purchase_completion | `enriched`, `linked`, `with_outlier`, `price_enriched` |
| `purchase_completion_error` | purchase_completion | `error` (mensaje) |

### Campos que puede modificar (sólo si originalmente vacíos / 0)
| Campo | Condición de actualización | Nota |
|-------|----------------------------|------|
| `unit_cost` | `unit_cost is None` o `== 0` | Valor retornado por completion (futuro: derivado de histórico) |
| `line_discount` | `line_discount is None` o `== 0` | Se usará para representar % descuento; hoy no se genera nuevo valor |
| `supplier_sku` | vacío y resultado provee `supplier_sku` | La versión actual no infiere nuevos SKUs (placeholder) |

### Limitaciones actuales / Futuras extensiones
- No modifica cantidades (`qty`).
- No cambia títulos (`title`).
- No realiza fuzzy-link a `product_id` ni `supplier_item_id`; eso permanece en validación / confirmación.
- No persiste price history ni toca `SupplierProduct` (sólo en confirmación se actualizan precios oficialmente).
- Fuentes de datos (`_PriceProvider`, `_CatalogProvider`) son stubs; se extenderán para consultar historial y catálogo real.
- No genera alertas negativas: sólo enriquece silenciosamente y registra métricas.

### Ejemplo (log simplificado)
```json
{
  "event": "purchase_completion_stats",
  "purchase_id": 123,
  "enriched": 10,
  "linked": 0,
  "with_outlier": 0,
  "price_enriched": 4
}
```

### Recomendaciones
- Activar primero en entorno de prueba y revisar logs `purchase_event` filtrando `purchase_completion`. 
- Añadir tests que habiliten el flag y verifiquen que líneas sin costo reciben un valor (cuando las fuentes reales estén implementadas). 
- Extender `purchase_completion_stats` para incluir tiempo de ejecución (`elapsed_ms`) si se vuelve costoso.

### Próximos pasos sugeridos
1. Implementar adaptadores reales a historial de precios (`PriceHistory`) para rellenar costo faltante usando mediana/último registro.
2. Implementar lookup de catálogo (SKU → SupplierProduct) para inferir `supplier_item_id` y `product_id` (opcional, quizá en validación, no aquí).
3. Marcar `flags` por línea (ej. `outlier_price_above_p95`, `suggested_discount_from_total`).
4. Añadir endpoint de métricas `GET /admin/services/purchase_completion/metrics`.
5. UI: resaltar en color tenue valores completados automáticamente (tooltip con “autocompletado”).

### Metadatos de enriquecimiento (meta.enrichment)

Desde la versión `20250926_add_purchase_line_meta` se agrega una columna `meta` (JSON nullable) en `purchase_lines` para persistir trazabilidad de campos autocompletados.

Estructura actual (snapshot único por línea; se sobreescribe en cada ejecución):
```json
{
  "enrichment": {
    "algorithm_version": "20250926_1",
    "timestamp": "2025-09-26T14:55:12Z",
    "fields": {
      "unit_cost": { "enriched": true, "original": null },
      "line_discount": { "enriched": true, "original": 0.0 },
      "supplier_sku": { "enriched": true, "original": null }
    },
    "stats": { "with_outlier": 0, "price_enriched": 4 }
  }
}
```

Claves:
- `algorithm_version`: versión lógica del motor (incrementar cuando cambien heurísticas que afecten resultados).
- `timestamp`: ISO UTC de la ejecución.
- `fields`: mapa de campos modificados. Cada campo contiene:
  - `enriched`: `true` si fue autocompletado en esta pasada (no se guarda `false` para no generar ruido).
  - `original`: valor previo antes de completar (puede ser `null` si no existía).
- `stats`: resumen global de la ejecución (subset de métricas internas: outliers detectados y cuántos precios se enriquecieron a nivel compra).

Reglas:
- Sólo se agrega `meta.enrichment` si al menos un campo fue autocompletado.
- No sobrescribe valores existentes (principio de no destrucción); sólo llena vacíos / cero.
- En futuras versiones podría añadirse `history` (array) si se requiere auditoría longitudinal; hoy se mantiene simple.

Uso en UI:
- Para resaltar un campo: si `line.meta.enrichment.fields.<campo>.enriched` existe → aplicar clase CSS (e.g. `enriched-field`).
- Tooltip sugerido: "Autocompletado (versión: 20250926_1)".

Limitaciones / Futuro:
- Sin historial acumulado; sólo el último snapshot.
- No incluye razones heurísticas detalladas (se pueden derivar de eventos de log si se necesita debug profundo).
- Podría extenderse con `elapsed_ms` y `passes` cuando se integren más fases inteligentes.

Migración:
- Ver `MIGRATIONS_NOTES.md` entrada: `20250926_add_purchase_line_meta`.


Al confirmar una compra, el backend calcula y registra:
- purchase_total: total del remito (subtotal con descuentos de línea, descuento global e IVA)
- applied_total: total de las líneas que efectivamente impactaron stock (sólo las resueltas con product_id)
- diff y tolerancias (abs/pct)
- mismatch: verdadero si la diferencia supera la tolerancia

Respuesta de `POST /purchases/{id}/confirm` incluye `totals` y, si hay `mismatch`, agrega `can_rollback: true` y un `hint`.

UI:
- En `PurchaseDetail`, si tras confirmar hay `mismatch`, se muestra un prompt ofreciendo ejecutar Rollback inmediato.
- En el listado `Compras`, para filas en `CONFIRMADA` aparece un botón “Rollback” que revierte stock y marca `ANULADA`.

Variables de entorno:
- `PURCHASE_TOTAL_MISMATCH_TOLERANCE_PCT` (default 0.005 → 0.5%). Define la tolerancia relativa para considerar mismatch.

## Logging y Auditoría
Se introdujo helper `_purchase_event_log` que estandariza logs estructurados con prefijo `purchase_event` para facilitar parsing posterior.

Eventos relevantes:
- `purchase_confirm`
- `purchase_resend_stock_preview`
- `purchase_resend_stock`

Cada apply exitoso añade entrada con `cooldown_seconds` y timestamp persistido.

## UI
- UI compras: selector de proveedor unificado (autocompletado con lista inicial, soporte dark y feedback en modal PDF, ficha de proveedor y Nueva compra).

En la vista `PurchaseDetail` se muestra (si existe) el último reenvío: `Último reenvío stock: <fecha local>`.

- Auditoría de Stock (UI): se agregó un botón “Auditoría” que abre un panel lateral con los deltas aplicados (según AuditLog/ImportLog) mostrando producto, ID, delta y transición old→new por evento. Útil para diagnosticar casos reportados de “productos erróneos”.

- Botón “iAVaL” (solo en BORRADOR):
  - Requiere PDF adjunto. Abre un modal con confianza, comentarios y diffs (encabezado y líneas).
  - Al confirmar (“Sí, aplicar cambios”), llama al endpoint `apply` y refresca la compra.
  - Opcional: checkbox “Enviar logs de cambios” que, al aplicar, llama a `apply` con `emit_log=1`.
  - Si se generan logs, se muestran botones “Descargar log JSON/CSV” en el modal (usando el endpoint de descarga) sin cerrar inmediatamente el modal.

Mejoras recientes en la pantalla de Compras:
- Badge visual “SKU no encontrado”: después de ejecutar Validar, si la respuesta incluye `missing_skus`, en cada línea cuyo `supplier_sku` figure en esa lista se muestra un distintivo rojo junto al campo de SKU con el texto “SKU no encontrado”. Esto ayuda a detectar de inmediato qué líneas requieren creación/vinculación.
- Atajo para agregar línea: se cambió el gesto para insertar una nueva línea a Alt+Enter. Esto evita inserciones accidentales al presionar Enter durante la edición.

Variables de entorno relevantes para IA:
- `OPENAI_API_KEY` (si se usa OpenAI u OpenAI-compatible)
- `AI_MODEL` o equivalente (según provider)
- `AI_ALLOW_EXTERNAL` (habilita llamadas a proveedores externos)

- En la vista `/productos` (Stock) hay un botón "Completar ventas faltantes" (visible para colaboradores y admin) que completa `current_sale_price` con `current_purchase_price` en todos los ítems de proveedor que no tengan precio de venta. Si hay un proveedor filtrado, aplica sólo a ese proveedor. El backend registra auditoría del total actualizado.

### Nueva compra — selección de proveedor

En `Nueva compra`, el campo Proveedor usa un autocompletado con soporte dark mode. Al seleccionar, se asigna `supplier_id` en el borrador. Esto evita introducir IDs incorrectos y mejora la usabilidad.

### Importación por Email (POP)

Para proveedores que envían remitos por correo (ej. POP), el camino simple es extraer el PDF del email y usar el importador PDF existente (OCR/IA): ver `docs/IMPORT_EMAIL.md`. Más adelante se puede automatizar con un watcher IMAP.

## Buenas prácticas
- Editar el campo `supplier_sku` en una linea limpia cualquier `supplier_item_id`/`product_id` previo; la linea quedara en `SIN_VINCULAR` hasta que se seleccione un item valido.
- Usar siempre preview antes de aplicar en entornos sensibles.
- Verificar que no existan líneas `SIN_VINCULAR` antes de confirmar inicialmente.
- Monitorear audit logs para detectar patrones de reenvíos frecuentes (posible síntoma de otros problemas).

## Próximos pasos sugeridos
- Endpoint para historial resumido de reenvíos (si se requiere auditoría regulatoria).
- Métrica Prometheus: contador de reenvíos aplicados y rechazados por cooldown.

---
Actualizado: 2025-09-17.

## Reglas de precios al crear productos desde Compras

- Cuando se crea un producto desde la pantalla de Compras (botón "Crear y vincular" o "Crear todos"), si se informa `supplier_id` y `supplier_sku` y se pasa en contexto `purchase_id`, el backend inicializa los precios del `SupplierProduct` así:
  - `current_purchase_price` = costo efectivo de la línea (precio unitario menos descuento de línea).
  - `current_sale_price` = igual al costo efectivo (regla solicitada: precio de venta inicial = precio de compra).
  - Este set inicial no genera historial; la confirmación de la compra actualizará nuevamente el precio de compra y registrará `PriceHistory`.

- Edición de precios desde `/productos`:
  - Precio de compra: editable por fila vía `PATCH /products-ex/supplier-items/{supplier_item_id}/buy-price`.
  - Precio de venta:
    - Si el producto está vinculado a un canónico, se edita vía `PATCH /products-ex/products/{canonical_product_id}/sale-price`.
    - Si no hay canónico, se habilita la edición a nivel proveedor vía `PATCH /products-ex/supplier-items/{supplier_item_id}/sale-price` y la UI muestra/permite editar `precio_venta`.

Notas:
- La confirmación de compras también realiza auto-vínculo por SKU de proveedor si la línea no tenía `supplier_item_id`, actualiza `current_purchase_price` y genera `PriceHistory` (entity_type="supplier") y luego impacta stock.
- El endpoint de reenvío de stock no modifica precios ni historial.
