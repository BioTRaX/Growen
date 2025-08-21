import { useEffect, useState } from 'react'
import { getPriceHistory, PriceHistoryItem } from '../services/prices'

interface Props {
  productId?: number
  supplierProductId?: number
  onClose: () => void
}

export default function PriceHistoryModal({ productId, supplierProductId, onClose }: Props) {
  const [items, setItems] = useState<PriceHistoryItem[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    getPriceHistory({ product_id: productId, supplier_product_id: supplierProductId, page })
      .then((r) => {
        setItems(r.items)
        setTotal(r.total)
      })
      .catch(() => {})
  }, [productId, supplierProductId, page])

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{ background: '#fff', padding: 20, borderRadius: 8, width: 500 }}>
        <button onClick={onClose} style={{ float: 'right' }}>
          Cerrar
        </button>
        <h3>Historial de precios</h3>
        <table className="table w-full">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Compra</th>
              <th>Venta</th>
              <th>Δ% Compra</th>
              <th>Δ% Venta</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.as_of_date}>
                <td>{new Date(it.as_of_date).toLocaleDateString()}</td>
                <td>{it.purchase_price ?? ''}</td>
                <td>{it.sale_price ?? ''}</td>
                <td>{it.delta_purchase_pct ?? ''}</td>
                <td>{it.delta_sale_pct ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Anterior
          </button>
          <button disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>
            Siguiente
          </button>
        </div>
      </div>
    </div>
  )
}
