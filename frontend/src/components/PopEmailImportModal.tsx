// NG-HEADER: Nombre de archivo: PopEmailImportModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/PopEmailImportModal.tsx
// NG-HEADER: Descripción: Modal para importar compras POP desde email (.eml / HTML / Text)
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import SupplierAutocomplete from './supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
import { importPopEmail } from '../services/purchases'
import ToastContainer, { showToast } from './Toast'

type Props = {
  open: boolean
  onClose: () => void
  onSuccess: (purchaseId: number) => void
}

export default function PopEmailImportModal({ open, onClose, onSuccess }: Props) {
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [supplierId, setSupplierId] = useState('')
  const [mode, setMode] = useState<'eml' | 'html' | 'text'>('eml')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => { if (!open) { setFile(null); setText(''); setErrorMsg(null); setMode('eml') } }, [open])
  if (!open) return null

  async function process() {
    if (!supplierId) { showToast('error', 'Elegí proveedor'); return }
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await importPopEmail({ supplier_id: Number(supplierId), kind: mode, file: file || undefined, text: text || undefined })
      const pid = (res as any).purchase_id
      if (Number.isFinite(Number(pid))) {
        showToast('success', 'Importado, abriendo compra...')
        try { onSuccess(Number(pid)) } catch (err) { console.warn('onSuccess handler threw', err) }
        onClose()
      } else {
        setErrorMsg('Import realizado pero no se devolvió el ID de la compra.')
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'No se pudo importar'
      setErrorMsg(String(msg))
      showToast('error', String(msg))
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div className="panel" style={{ padding: 16, minWidth: 560, position: 'relative' }}>
        <h3 style={{ marginTop: 0 }}>Importar compra desde Email (POP)</h3>
        <div className="row" style={{ gap: 8, marginBottom: 8 }}>
          <SupplierAutocomplete value={supplierSel} onChange={(item) => { setSupplierSel(item); setSupplierId(item ? String(item.id) : '') }} placeholder="Proveedor" />
        </div>
        <div className="row" style={{ gap: 12, marginBottom: 8 }}>
          <label><input type="radio" checked={mode === 'eml'} onChange={() => setMode('eml')} /> Subir .eml</label>
          <label><input type="radio" checked={mode === 'html'} onChange={() => setMode('html')} /> Pegar HTML</label>
          <label><input type="radio" checked={mode === 'text'} onChange={() => setMode('text')} /> Pegar Texto</label>
        </div>
        {mode === 'eml' && (
          <div className="row" style={{ gap: 8 }}>
            <input className="input w-full" type="file" accept="message/rfc822,.eml" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
        )}
        {mode !== 'eml' && (
          <div className="row" style={{ gap: 8 }}>
            <textarea className="input" style={{ width: '100%', height: 220 }} placeholder={mode === 'html' ? '<html>...pegá acá el cuerpo del email...</html>' : 'Pegá acá el texto del email...'} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
        )}
        {errorMsg && (
          <div style={{ marginTop: 10, color: '#e74c3c' }}>{errorMsg}</div>
        )}
        <div className="row" style={{ gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
          <button className="btn-dark" onClick={onClose} disabled={loading}>Cancelar</button>
          <button className="btn-primary" onClick={process} disabled={loading || !supplierId || (mode === 'eml' && !file) || (mode !== 'eml' && !text.trim())}>{loading ? 'Procesando...' : 'Procesar'}</button>
        </div>
        <ToastContainer />
      </div>
    </div>
  )
}
