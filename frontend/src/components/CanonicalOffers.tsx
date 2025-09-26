// NG-HEADER: Nombre de archivo: CanonicalOffers.tsx
// NG-HEADER: Ubicación: frontend/src/components/CanonicalOffers.tsx
// NG-HEADER: Descripción: Componente que muestra ofertas y equivalencias canónicas.
// NG-HEADER: Lineamientos: Ver AGENTS.md
// File consolidated below; removed duplicate earlier implementation
import { useEffect, useState } from 'react'
import { getProductOfferings, OfferingRow, updateSupplierBuyPrice } from '../services/productsEx'
import { showToast } from './Toast'
import { formatARS, parseDecimalInput } from '../lib/format'
import { useAuth } from '../auth/AuthContext'

interface Props {
  canonicalId: number
  onClose: () => void
}

export default function CanonicalOffers({ canonicalId, onClose }: Props) {
  const { state } = useAuth()
  const canEdit = state.role === 'admin' || state.role === 'colaborador'
  const [offers, setOffers] = useState<OfferingRow[]>([])
  const [editing, setEditing] = useState<number | null>(null)
  const [value, setValue] = useState('')

  useEffect(() => {
    getProductOfferings(canonicalId)
      .then(setOffers)
      .catch(() => {})
  }, [canonicalId])

  async function saveBuyPrice(id: number) {
    const parsed = parseDecimalInput(value)
    if (parsed == null) return
    try {
      const r = await updateSupplierBuyPrice(id, Number(parsed.toFixed(2)))
      setOffers((prev) => prev.map((o) => (o.supplier_item_id === id ? { ...o, buy_price: r.buy_price ?? null } : o)))
      setEditing(null)
      showToast('success', 'Precio de compra actualizado')
    } catch (e) {
      showToast('error', 'No se pudo guardar el precio')
    }
  }

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
      <div className="panel p-4" style={{ width: 600, maxHeight: '80%', overflow: 'auto' }}>
        <button onClick={onClose} style={{ float: 'right' }}>
          Cerrar
        </button>
        <h3>Comparativa de precios</h3>
        <table className="table w-full">
          <thead>
            <tr>
              <th>Proveedor</th>
              <th>SKU</th>
              <th className="text-center">Compra</th>
              <th className="text-center">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {offers.map((of) => (
              <tr key={of.supplier_item_id}>
                <td>{of.supplier_name}</td>
                <td>{of.supplier_sku}</td>
                <td className="text-center">
                  {canEdit && editing === of.supplier_item_id ? (
                    <input
                      autoFocus
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      onBlur={() => saveBuyPrice(of.supplier_item_id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveBuyPrice(of.supplier_item_id)
                        if (e.key === 'Escape') setEditing(null)
                      }}
                      style={{ width: 100 }}
                    />
                  ) : (
                    <span>
                      {formatARS(of.buy_price)}
                      {canEdit && (
                        <button
                          style={{ marginLeft: 6 }}
                          onClick={() => {
                            setEditing(of.supplier_item_id)
                            setValue(of.buy_price != null ? String(of.buy_price) : '')
                          }}
                        >
                          ✎
                        </button>
                      )}
                    </span>
                  )}
                </td>
                <td className="text-center">{of.updated_at ? new Date(of.updated_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
