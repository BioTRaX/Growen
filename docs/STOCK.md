<!-- NG-HEADER: Nombre de archivo: STOCK.md -->
<!-- NG-HEADER: Ubicación: docs/STOCK.md -->
<!-- NG-HEADER: Descripción: Contrato operativo vigente del módulo Vue de Stock y Faltantes. -->
<!-- NG-HEADER: Lineamientos: Ver AGENTS.md -->

# Stock y Faltantes

## Estado vigente

Las rutas `/stock` y `/stock/shortages` están en `state: active` y `runtime: vue` en `frontend-vue/config/modules.json`. Nginx las dirige a la SPA Vue; React conserva una copia temporal como mecanismo de rollback, pero ya no es el runtime principal de estas rutas.

El retiro del código React es un cambio posterior. Requiere smoke visual autenticado por rol, validación de concurrencia sobre PostgreSQL y la ventana de estabilidad acordada. La fuente de verdad del runtime es el manifiesto; este documento describe el contrato funcional.

## Rutas y permisos

| Ruta | Roles | Capacidades |
|---|---|---|
| `/stock` | `cliente`, `proveedor`, `colaborador`, `admin` | Listado, filtros y exportaciones XLSX/CSV/PDF |
| `/stock` | `colaborador`, `admin` | Edición de stock, precio de venta, precio de compra y exportación TiendaNegocio |
| `/stock/shortages` | `colaborador`, `admin` | Listado, métricas y alta de faltantes |

FastAPI es la autoridad final. Las mutaciones exigen sesión, rol `colaborador|admin` y CSRF.

## Stock Vue

La vista consulta el catálogo con `type=all`, orden `updated_at desc` y dos pestañas excluyentes: `stock=gt:0` y `stock=eq:0`. Los filtros `q`, `supplier_id`, `category_id`, `stock`, `page` y `page_size` se conservan en la URL. La búsqueda usa debounce de 300 ms, cancela la solicitud anterior y descarta respuestas obsoletas.

La tabla muestra producto, proveedor, precio efectivo de venta, precio de compra, stock, categoría y fecha de actualización. Para staff permite:

- Ajustar stock con hasta dos decimales. Vue envía `expected_stock`; el backend bloquea la fila, responde `409` si el saldo leído quedó desactualizado y registra `manual_adjustment` en `stock_ledger` dentro de la misma transacción.
- Editar el precio de venta efectivo. Si existe canónico se actualiza su precio; en caso contrario se actualiza la oferta del proveedor.
- Editar el precio de compra cuando existe `supplier_item_id`.

Las operaciones masivas de enriquecimiento, completar precios y catálogos pertenecen a Productos Vue y no forman parte de Stock.

## Exportaciones

| Formato | Endpoint | Roles |
|---|---|---|
| XLSX | `GET /stock/export.xlsx` | Usuarios autenticados |
| CSV | `GET /stock/export.csv` | Usuarios autenticados |
| PDF | `GET /stock/export.pdf` | Usuarios autenticados |
| TiendaNegocio XLSX | `GET /stock/export-tiendanegocio.xlsx` | `colaborador`, `admin` |

Todas reciben los filtros activos y comparten la misma selección de datos. Vue descarga XLSX/CSV/TiendaNegocio como blobs; el PDF se abre en una pestaña nueva y la URL temporal se revoca.

## Faltantes

`/stock/shortages` lista reportes paginados, métricas agregadas y filtro por motivo:

- `GIFT`: regalo.
- `PENDING_SALE`: venta pendiente.
- `UNKNOWN`: desconocido.

El alta busca productos remotamente desde dos caracteres, limita la respuesta a 50 elementos, cancela búsquedas anteriores y acepta cantidades positivas con hasta dos decimales. El backend bloquea el producto, descuenta la cantidad y registra tanto `stock_shortages` como el movimiento `shortage` en `stock_ledger`.

Si el resultado queda negativo, Vue exige confirmación explícita. Los estados persistidos son `OPEN` y `RECONCILED`.

## Validación y retiro de React

Validado el 2026-07-25:

- `npm.cmd run typecheck`: aprobado.
- `npm.cmd test`: 82 pruebas Vue aprobadas en 23 archivos.
- `npm.cmd run build`: aprobado.

Pendiente antes de eliminar `frontend/src/pages/Stock.tsx`, `frontend/src/pages/StockShortages.tsx` y sus consumidores:

1. Smoke visual autenticado para `cliente`, `proveedor`, `colaborador` y `admin`.
2. Prueba de concurrencia real sobre PostgreSQL para ajustes y faltantes; SQLite no demuestra el bloqueo pesimista.
3. Confirmar con `rg` que componentes, hooks y servicios React no tengan consumidores fuera del dominio.
4. Cumplir la ventana de estabilidad y documentar el retiro y el rollback.

