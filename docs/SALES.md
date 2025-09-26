<!-- NG-HEADER: Nombre de archivo: SALES.md -->
<!-- NG-HEADER: Ubicación: docs/SALES.md -->
<!-- NG-HEADER: Descripción: Módulo de Clientes y Ventas: modelos, endpoints y flujos -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Clientes y Ventas

Este módulo permite:
- Gestionar clientes (alta/edición básica).
- Registrar ventas con descuento automático de stock.
- Adjuntar comprobantes a ventas.

## Modelos
- customers: id, name, document_type?, document_number?, email?, phone?, address?, city?, province?, notes?, kind?, is_active, created_at, updated_at
- sales: id, customer_id?, status (BORRADOR|CONFIRMADA|ENTREGADA|ANULADA), discount_percent, discount_amount, subtotal, tax, total_amount, paid_total?, payment_status?, sale_date, note, created_by?, correlation_id?, meta?, timestamps
- sale_lines: id, sale_id, product_id, title_snapshot?, sku_snapshot?, qty, unit_price, line_discount_percent?, subtotal?, tax?, total?, supplier_item_id?, state?, note?
- sale_payments: id, sale_id, method (efectivo|debito|credito|transferencia|mercadopago|otro), amount, reference?, paid_at?, meta?, created_at
- sale_attachments: id, sale_id, filename, mime?, size?, path, created_at
 - returns: id, sale_id, status (BORRADOR|REGISTRADA|ANULADA), reason?, total_amount, created_by?, created_at, correlation_id?
 - return_lines: id, return_id, sale_line_id?, product_id, qty, unit_price, subtotal, note?

Migraciones relevantes: `20250918_sales_and_customers.py` y `20250925_extend_sales_customers_fields.py` (extensiones y nuevos índices).

## Endpoints
- GET /sales/customers: lista de clientes. Filtros: q. Paginación real.
- POST /sales/customers: alta (valida email único opcional, CUIT/DNI si corresponde).
- PUT /sales/customers/{id}: edición.
- DELETE /sales/customers/{id}: soft-delete (is_active=false).
- GET /sales/customers/{id}/sales: historial del cliente (paginado).
- GET /sales/customers/search?q=: búsqueda rápida priorizada (document_number exacta, nombre prefix, nombre/email/phone/doc_id contains) limitada por `limit`.
- GET /sales: listar ventas con filtros (status, customer_id, from, to) y paginación.
- GET /sales/{id}: detalle (líneas, pagos, adjuntos).
- POST /sales: crea una venta en BORRADOR (por defecto) sin afectar stock; opcionalmente status=CONFIRMADA valida stock y afecta inmediatamente.
- POST /sales/{id}/lines: agrega/actualiza/elimina líneas mientras la venta está en BORRADOR.
- PATCH /sales/{id}: actualiza encabezado (descuentos globales %, monto, notas, cliente) sólo en BORRADOR.
- POST /sales/{id}/confirm: confirma BORRADOR (valida stock y afecta) o ignora si ya CONFIRMADA.
- POST /sales/{id}/deliver: marca ENTREGADA (no mueve stock). [implementado]
- POST /sales/{id}/annul: anula (revierte stock si estaba confirmada; nota obligatoria). [implementado]
- POST /sales/{id}/payments: registrar pagos adicionales (múltiples métodos).
- GET /sales/{id}/payments: lista los pagos (endpoint separado para UI modular y polling ligero).
- GET /sales/{id}/receipt: comprobante simple (PDF/HTML).
- POST /sales/{id}/returns: crea devolución parcial/total (CONFIRMADA/ENTREGADA). Valida saldo disponible por línea y repone stock.
- GET /sales/{id}/returns: lista devoluciones de la venta.
- GET /sales/{id}/timeline: secuencia cronológica (audit + pagos + devoluciones) para UI timeline.
- GET /sales/reports/net: ventas netas (bruto, devoluciones, neto) con filtros fecha y sale_kind.
- GET /sales/reports/top-products: ranking productos con qty y monto neto.
- GET /sales/reports/top-customers: ranking clientes con bruto, devoluciones y neto.
- GET /products/{id}/stock/history: historial de movimientos (stock_ledger) orden descendente, paginado.
- GET /reports/sales: resumen por estado (count, amount) con filtros de fecha.
- GET /reports/sales/export.csv: exportación CSV.

 Notas:
- El descuento de stock es in-place sobre `products.stock` (compatibilidad con módulo actual). Recomendado a futuro: libro de stock.
- Validación de stock en Confirmar: si falta stock de algún item, la operación falla con 400 y no aplica cambios.
- Devoluciones: cada Return incrementa stock y registra audit_log `return_create` con deltas. No altera totales históricos de la venta (base para reporte neto futuro).
- Auditoría: acciones `sale_create`, `sale_confirm`, `sale_deliver`, `sale_annul`, `sale_patch`, `return_create` incluyen `elapsed_ms` y `stock_deltas` cuando corresponde.
- Precios: base canónico (CanonicalProduct.sale_price). Si no existe, fallback a SupplierProduct.current_sale_price; último recurso `variants[0].price`. UI exige precios > 0.
- Clamp de descuento: al confirmar, si `discount_amount` > `subtotal` se limita (clamp) al subtotal y se registra audit `sale_discount_clamped` con valores original y ajustado.
- Cache in-memory: reportes agregados (net, top-products, top-customers) usan cache TTL (60s). Invalida automáticamente en confirmación de venta o creación de devolución.
- stock_ledger: libro de movimientos (sale delta negativo, return delta positivo) con `balance_after` para auditoría de inventario. Endpoint público de solo lectura por producto.

## Frontend
- Rutas: /clientes (listado + CRUD), /ventas (listado), /ventas/nueva (POS), /ventas/:id (detalle).
- Páginas:
  - Clientes: tabla con filtros, modal crear/editar, soft delete.
  - Ventas (POS): buscador (SKU/título), tabla de líneas editable (qty, unit_price, %desc), totales con descuento global, módulo pagos múltiples, selector cliente (autocomplete), acciones Guardar/Confirmar/Anular/Entregar/Imprimir.
  - Detalle: timeline de eventos (líneas, pagos, confirmación, stock), adjuntos y comprobante.

## Próximos pasos
- Libro de stock y depósitos múltiples.
- Series de comprobantes y numeración.
- Reportes adicionales (por cliente, producto, margen) y dashboard /admin/servicios.
- Liquidación neta (ventas - devoluciones) y notas de crédito.
- Snapshots de producto (title/sku) se rellenan automáticamente al confirmar la venta (si estaban vacíos) asegurando persistencia histórica aun si el producto cambia luego.
- Auditoría ahora incluye correlation_id (session_id), user_id e IP cuando están disponibles en acciones: sale_create, sale_confirm, sale_deliver, sale_annul, sale_patch, sale_payment_add, return_create.
 - Auditoría extendida: 'sale_lines_ops' registra batch de operaciones (add/update/delete) con before/after por línea y 'sale_payment_add' incluye before/after de paid_total y payment_status.
 - Normalización de documento: en alta/edición de clientes se limpia `document_number` removiendo separadores y se valida formato básico (CUIT=11 dígitos, DNI 7-9 dígitos).
