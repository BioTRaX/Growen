<!-- NG-HEADER: Nombre de archivo: SALES.md -->
<!-- NG-HEADER: Ubicación: docs/SALES.md -->
<!-- NG-HEADER: Descripción: Documentación módulo Ventas y Clientes (API + flujos + reglas) -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Módulo Ventas y Clientes

## Resumen
Implementa un POS simple + pedidos con clientes (mini CRM), manejo de stock, devoluciones, reportes y auditoría. Las ventas se crean como `BORRADOR` y sólo afectan stock al confirmarse.

## Estados de Venta
- `BORRADOR`: editable (agregar/quitar líneas, notas, descuentos, pagos iniciales opcionales)
- `CONFIRMADA`: stock descontado; puede entregarse o anularse
- `ENTREGADA`: estado logístico final (no afecta más stock)
- `ANULADA`: revierte stock si estaba confirmada/entregada; no admite más cambios salvo lectura

## Endpoints Principales (`/sales`)

### Ventas
- POST `/sales` crear venta (rate-limited 30/min usuario/IP; configurable desactivar sólo con `SALES_RATE_LIMIT_DISABLED=1`).
  - Acepta `channel_id` (FK a sales_channels) y `additional_costs` (JSON array de objetos `{concept, amount}`).
- GET `/sales` listar (filtros por estado, fecha, cliente)
- GET `/sales/{id}` detalle (incluye `channel_id` y `additional_costs`)
- PATCH `/sales/{id}` actualizar campos (BORRADOR) - acepta `channel_id` y `additional_costs`

### Canales de Venta (nuevo 2025-11-30)
- GET `/sales/channels` listar canales
- POST `/sales/channels` crear canal (requiere rol colaborador/admin)
- DELETE `/sales/channels/{id}` eliminar canal (requiere rol admin)

Límite rate: 30/min por usuario (o IP). Implementación in-memory simple (adecuado single-process). Respuesta exceso: 429 `{code: rate_limited, retry_in: <segundos>}`. Para despliegues multi-proceso: migrar a Redis token bucket.

Variables:
- `SALES_RATE_LIMIT_DISABLED=1` desactiva temporalmente (uso local / scripts controlados). Ya no se utiliza `TESTING` para bypass.
 Pagos y Normalización
 Métodos normalizados: `tarjeta` -> `credito`; valores desconocidos -> `otro`.
 Estado global de pago `payment_status` en detalle de venta:
- `PENDIENTE` (sin pagos)
- `PARCIAL` (pagos < total)
- `PAGADA` (pagos >= total)

- POST `/sales/{id}/confirm` confirmar (valida stock y bloquea si hay líneas `SIN_VINCULAR`)
 2025-09-26: Eliminado bypass de rate limit por `TESTING`; se introduce `SALES_RATE_LIMIT_DISABLED`.
 2025-09-26: Normalización de método de pago (`tarjeta` -> `credito`).
 2025-09-26: Se agrega `payment_status` al detalle de venta.
 2025-09-26: Ajuste extractor métricas para soportar Postgres (dialecto JSON) y batch lines endpoint.

 Última actualización: 2025-09-26 (refrescado para rate limit, normalización pagos y payment_status)
- POST `/sales/{id}/annul` anular (restituye stock e invalida caches)
- POST `/sales/{id}/payments` agregar pago
- GET `/sales/{id}/payments` listar pagos
- GET `/sales/{id}/receipt` recibo HTML simple
- GET `/sales/export` exportación CSV (audit `sale_export_csv`)
- GET `/sales/metrics/summary` métricas de resumen (cache 30s)

## Clientes (`/sales/customers`)
CRUD básico + soft delete. Búsqueda rápida `GET /sales/customers/search?q=` con ranking.

## Catálogo
Endpoint de autocomplete: `GET /sales/catalog/search?q=` prioriza productos con stock y coincidencias en título / sku_root.

## Devoluciones
- POST `/sales/{id}/returns` crea devolución sobre venta confirmada/entregada (restaura stock)
- GET `/sales/{id}/returns` lista devoluciones

## Reportes (`/reports`)
- GET `/reports/sales` métricas agregadas (neto, top productos, top clientes)
- GET `/reports/sales/export.csv` exportación histórica

## Métricas Resumen (`/sales/metrics/summary`)
Respuesta:
```
{
  "today": {"count": 3, "net_total": 1520.5},
  "avg_confirm_ms": 23.4,
  "last7d": [ {"date":"2025-09-20","count":0,"net_total":0}, ... ],
  "top_products_today": [ {"product_id": 10, "title": "Producto A", "qty": 4, "total": 520.0} ]
}
```
Cache interno 30s. Extracción de `elapsed_ms` desde JSON via `json_extract` (SQLite). Si se usa Postgres, adaptar a `meta->>'elapsed_ms'`.

## Stock y Ledger
- Stock se descuenta recién en confirmación y se repone al anular o al registrar devoluciones.
- Modelo ORM `StockLedger` registra cada movimiento (`source_type`: `sale`, `return`, (futuro) `annul`, `adjust`).
- Campos: `product_id`, `source_type`, `source_id`, `delta` (negativo venta, positivo devolución), `balance_after`, `meta.sale_line_id`.
- Índices: (`product_id`,`created_at`) para historiales rápidos y (`source_type`,`source_id`) para rastrear movimientos de una operación.

## Descuentos
- Por línea: `line_discount` (% 0-100) aplicado a (qty * unit_price)
- Global: `discount_percent` o `discount_amount` (si ambos se envían prevalece monto). Se recalculan totales usando `Decimal` y se guardan `subtotal`, `total_amount`.

## Canales de Venta (nuevo 2025-11-30)
Permite clasificar ventas por origen (Instagram, WhatsApp, Local, MercadoLibre, etc.).

### Modelo `SalesChannel`
- `id`: PK
- `name`: String(100), único
- `created_at`: timestamp

### Uso
1. Crear canales: `POST /sales/channels { "name": "Instagram" }`
2. Al crear/editar venta, incluir `channel_id`
3. Listar canales: `GET /sales/channels`

## Costos Adicionales (nuevo 2025-11-30)
Permite agregar costos extra (envío, packaging, recargos) a una venta.

### Estructura
Campo `additional_costs` en `Sale` (tipo JSONB):
```json
[
  {"concept": "Envío", "amount": 500.00},
  {"concept": "Packaging premium", "amount": 150.00}
]
```

### Validación
- Debe ser un array de objetos
- Cada objeto debe tener `concept` (string) y `amount` (número válido)
- El monto se suma al total de la venta en el frontend (cálculo local)

### Uso
```
POST /sales {
  "customer": {"id": 1},
  "items": [...],
  "additional_costs": [
    {"concept": "Envío express", "amount": 800}
  ]
}
```

## Validaciones Clave
- Confirmación: falla con 409 si existen líneas `SIN_VINCULAR`.
- Confirmación: falla con 400 si falta stock (detalle por producto).
- Anulación: sólo para `CONFIRMADA` o `ENTREGADA`.
- Pagos: evita sobrepago > total + 0.02.

## Auditoría
Acciones registradas principales: `sale_create`, `sale_lines_ops` (batch líneas), `sale_confirm`, `sale_discount_clamped`, `sale_deliver`, `sale_annul`, `sale_payment_add`, `return_create`, `sale_export_csv`. Incluye `correlation_id` (session_id) y metadatos (stock_deltas, pagos antes/después, etc.).

## Rate Limiting
Aplicado a creación de ventas (POST /sales). Límite 30/min por usuario (o IP). Implementación in-memory simple (adecuado single-process). Respuesta exceso: 429 `{code: rate_limited, retry_in: <segundos>}`. Para despliegues multi-proceso: migrar a Redis token bucket. En entorno de test se puede desactivar con `TESTING=1`.

## Cache Reportes
Cache in-memory invalidado en confirmaciones, devoluciones y anulaciones. Métricas resumen cachea separadamente (30s).

## Futuras Mejoras Sugeridas
- Persistir source_type detallado en ledger para devoluciones vs anulaciones.
- Migrar cache a Redis en despliegues multi-proceso.
- Endpoint PDF oficial del recibo.
- Búsqueda de productos con trigram / full-text.
- Reportes por canal de venta.
- Integrar costos adicionales en el cálculo de totales del backend (actualmente solo frontend).

## Notas de Migración
Nueva migración `20250926_stock_ledger_and_sales_indexes.py`:
- Crea `stock_ledger`
- Índices adicionales en ventas, líneas, returns
- Índice único parcial `customers(document_number)` (Postgres) / índice normal fallback.

Nueva migración `20251130_sales_channels_and_costs.py`:
- Crea tabla `sales_channels` (id, name, created_at)
- Agrega `channel_id` (FK) y `additional_costs` (JSONB) a `sales`
- Índice en `sales.channel_id`

Actualizar `MIGRATIONS_NOTES.md` si se ajustan más cambios estructurales.

## Testing
Pruebas actuales:
- `test_sales_metrics_and_limits.py`: métricas y rate limiting.
- (Pendiente) prueba de clamp descuento, ledger (confirm + return), bloqueo por `SIN_VINCULAR`, invalidación cache (annul), export CSV.
Pruebas planificadas (backlog): validar estructura completa de movimientos en `StockLedger` y reconstrucción de stock por replay.

## Ejemplo Flujo POS Rápido
1. POST /sales (BORRADOR)
2. POST /sales/{id}/lines (agregar items)
3. PATCH /sales/{id} (aplicar descuento global)
4. POST /sales/{id}/confirm
5. POST /sales/{id}/payments (abonar)
6. GET /sales/{id}/receipt

---
Última actualización: 2025-11-30 (agregado: canales de venta, costos adicionales, UI mejorada con búsqueda en selectores)
