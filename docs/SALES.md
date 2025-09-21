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
- customers: id, name, email?, phone?, doc_id?, address?, notes?, created_at, updated_at
- sales: id, customer_id?, status (BORRADOR|CONFIRMADA|ANULADA), sale_date, total_amount, paid_total?, note, created_by?, timestamps
- sale_lines: id, sale_id, product_id, qty, unit_price, line_discount?, note?
- sale_payments: id, sale_id, method (efectivo|debito|credito|transferencia|mercadopago|otro), amount, reference?, created_at
- sale_attachments: id, sale_id, filename, mime?, size?, path, created_at

Migración: `20250918_sales_and_customers.py`.

## Endpoints
- GET /sales/customers: lista de clientes. Filtros: q. Paginación simple.
- POST /sales/customers: alta.
- PUT /sales/customers/{id}: edición.
- POST /sales: crea una venta y descuenta stock; si el cliente no existe, se crea con datos mínimos.
- POST /sales/{id}/attachments: sube adjunto (comprobante).

Notas:
- El descuento de stock es in-place sobre `products.stock` (compatibilidad con módulo actual).
- Validación de stock: si falta stock de algún item, la operación falla con 400.
- Precios: si no se informa unit_price, intenta usar `variants[0].price` si existe.

## Frontend
- Rutas nuevas: /clientes y /ventas. Accesibles desde Dashboard con botones.
- Páginas:
  - Clientes: listado y alta simple.
  - Ventas: selector de cliente (o nuevo) y productos con stock; crea venta básica.

## Próximos pasos
- Listar ventas con filtros y detalle.
- Reversión / anulación de venta (reponer stock).
- Múltiples depósitos y series de comprobantes.
- Reportes (diario, por cliente, por producto).
