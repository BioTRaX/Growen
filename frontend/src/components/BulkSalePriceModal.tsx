// NG-HEADER: Nombre de archivo: BulkSalePriceModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/BulkSalePriceModal.tsx
// NG-HEADER: Descripción: Componente React para el modal de actualización masiva de precios.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useMemo, useState } from 'react'
import { BulkMode, bulkUpdateSalePrice } from '../services/productsEx'
import { showToast } from './Toast'

interface Props {
  productIds: number[]
  onClose: (updated?: number) => void
}

export default function BulkSalePriceModal({ productIds, onClose }: Props) {
  const [mode, setMode] = useState<BulkMode>('set')
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const parsed = useMemo(() => {
    const v = value.replace(/,/g, '.')
    const num = Number(v)
    if (!isFinite(num) || num <= 0) return null
    // Validate decimal places: 2 for value modes, 4 for pct modes
    const [, dec = ''] = v.split('.')
    const maxDecimals = mode.endsWith('pct') ? 4 : 2
    if (dec.length > maxDecimals) return null
    return num
  }, [value, mode])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (parsed == null) return
    try {
      setBusy(true)
      const res = await bulkUpdateSalePrice({ product_ids: productIds, mode, value: parsed, note: note || undefined })
      showToast('success', `Actualizados ${res.updated} productos`)
      onClose(res.updated)
    } catch (e) {
      showToast('error', 'No se pudo aplicar la edición masiva')
      onClose(undefined)
    } finally {
      setBusy(false)
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
        zIndex: 50,
      }}
    >
      <form onSubmit={onSubmit} className="panel p-4" style={{ width: 420 }}>
        <h3 style={{ marginTop: 0 }}>Edición masiva de precio de venta</h3>
        <div style={{ marginBottom: 12, fontSize: 12 }}>
          {productIds.length} productos seleccionados
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <select className="select" value={mode} onChange={(e) => setMode(e.target.value as BulkMode)}>
            <option value="set">Fijar a</option>
            <option value="inc">Sumar</option>
            <option value="dec">Restar</option>
            <option value="inc_pct">Incrementar %</option>
            <option value="dec_pct">Decrementar %</option>
          </select>
          <input
            className="input"
            placeholder={mode.endsWith('pct') ? 'Porcentaje' : 'Valor'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            style={{ width: 140 }}
          />
        </div>
        <div style={{ fontSize: 12, marginTop: -4, marginBottom: 8, color: 'var(--muted)' }}>
          {mode.endsWith('pct') ? 'Usá . como separador decimal (hasta 4 decimales)' : 'Usá . como separador decimal (hasta 2 decimales)'}
        </div>
        <div style={{ marginBottom: 12 }}>
          <input className="input w-full" placeholder="Nota (opcional)" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={() => onClose()}>Cancelar</button>
          <button type="submit" className="btn-dark" disabled={busy || parsed == null}>
            {busy ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  )
}
