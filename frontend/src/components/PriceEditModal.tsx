// NG-HEADER: Nombre de archivo: PriceEditModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/PriceEditModal.tsx
// NG-HEADER: Descripción: Modal para edición de precio de venta (canónico) o compra (proveedor)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useMemo, useState } from 'react'
import { formatARS, parseDecimalInput } from '../lib/format'
import { getProductOfferings, getInternalProductOfferings, OfferingRow, updateSalePrice, updateSupplierBuyPrice } from '../services/productsEx'
import { showToast } from './Toast'

interface Props {
  productId: number
  canonicalProductId?: number | null
  currentSale?: number | null
  onSaved?: (kind: 'sale' | 'buy', value: number) => void
  onClose: () => void
}

export default function PriceEditModal({ productId, canonicalProductId, currentSale, onSaved, onClose }: Props) {
  const [mode, setMode] = useState<'sale' | 'buy'>(canonicalProductId ? 'sale' : 'buy')
  const [offerings, setOfferings] = useState<OfferingRow[]>([])
  const [supplierItemId, setSupplierItemId] = useState<string>('')
  const [price, setPrice] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingOfferings, setLoadingOfferings] = useState(false)

  useEffect(() => {
    // Prefill sale price if provided
    if (currentSale != null && currentSale > 0) setPrice(String(currentSale))
  }, [currentSale])

  useEffect(() => {
    // Load offerings for buy price (we can preload; selection is only required when mode === 'buy')
    setLoadingOfferings(true)
    const load = async () => {
      try {
        const list = canonicalProductId
          ? await getProductOfferings(canonicalProductId)
          : await getInternalProductOfferings(productId)
        setOfferings(list)
        if (list.length === 1) setSupplierItemId(String(list[0].supplier_item_id))
      } catch {
        setOfferings([])
      } finally {
        setLoadingOfferings(false)
      }
    }
    load()
  }, [productId, canonicalProductId])

  const canSave = useMemo(() => {
    const parsed = parseDecimalInput(price)
    if (parsed == null) return false
    if (mode === 'sale') return !!canonicalProductId
    return !!supplierItemId
  }, [price, mode, canonicalProductId, supplierItemId])

  async function save() {
    const parsedPrice = parseDecimalInput(price)
    if (parsedPrice == null) return

    setLoading(true)
    try {
      if (mode === 'sale') {
        if (!canonicalProductId) throw new Error('Producto canónico no disponible')
        const r = await updateSalePrice(canonicalProductId, Number(parsedPrice.toFixed(2)), note || undefined)
        showToast('success', `Precio de venta actualizado a ${formatARS(r.sale_price ?? 0)}`)
        if (r.sale_price != null) onSaved?.('sale', r.sale_price)
        onClose()
      } else {
        const finalSupplierItemId = Number(supplierItemId)
        if (!finalSupplierItemId) {
          showToast('error', 'Seleccione una oferta de proveedor')
          return
        }
        const r = await updateSupplierBuyPrice(finalSupplierItemId, Number(parsedPrice.toFixed(2)), note || undefined)
        showToast('success', `Precio de compra actualizado a ${formatARS(r.buy_price ?? 0)}`)
        if (r.buy_price != null) onSaved?.('buy', r.buy_price)
        onClose()
      }
    } catch (e: any) {
      showToast('error', e?.message || 'No se pudo guardar el precio')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal" style={{ width: 520, maxWidth: '92%' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ flex: 1, margin: 0 }}>Editar precio</h3>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <label className="label">Tipo</label>
            <div style={{ display: 'flex', gap: 12 }}>
              <label><input type="radio" name="price-mode" checked={mode === 'sale'} disabled={!canonicalProductId} onChange={() => setMode('sale')} /> Venta (canónico)</label>
              <label><input type="radio" name="price-mode" checked={mode === 'buy'} onChange={() => setMode('buy')} /> Compra (proveedor)</label>
            </div>
            {mode === 'buy' && (
              <div style={{ marginTop: 12 }}>
                <label className="label">Oferta</label>
                <select className="select w-full" disabled={loadingOfferings} value={supplierItemId} onChange={(e) => setSupplierItemId(e.target.value)}>
                  <option value="">Seleccione…</option>
                  {offerings.map((o) => (
                    <option key={o.supplier_item_id} value={o.supplier_item_id}>
                      {o.supplier_name} — SKU {o.supplier_sku} — {formatARS(o.buy_price)}
                    </option>
                  ))}
                </select>
                {!loadingOfferings && !offerings.length && (
                  <div className="text-sm" style={{ opacity: 0.8, marginTop: 6 }}>No hay ofertas asociadas a este producto todavía.</div>
                )}
              </div>
            )}
          </div>
          <div style={{ flex: 1 }}>
            <label className="label">Nuevo precio</label>
            <input className="input w-full" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="$0,00" />
            <label className="label" style={{ marginTop: 12 }}>Nota (opcional)</label>
            <input className="input w-full" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Motivo del cambio…" />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn-dark" disabled={!canSave || loading} onClick={save}>{loading ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </div>
    </div>
  )
}
