// NG-HEADER: Nombre de archivo: PdfImportModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/PdfImportModal.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import { listSuppliers, Supplier } from '../services/suppliers'
import { importSantaPlanta } from '../services/purchases'
import ToastContainer, { showToast } from './Toast'

type Props = {
  open: boolean
  onClose: () => void
  onSuccess: (purchaseId: number) => void
}

export default function PdfImportModal({ open, onClose, onSuccess }: Props) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [supplierId, setSupplierId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [debug, setDebug] = useState(false)
  const [forceOCR, setForceOCR] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [errorCid, setErrorCid] = useState<string | null>(null)
  const [errorDetail, setErrorDetail] = useState<any>(null)

  useEffect(() => { if (open) listSuppliers().then(setSuppliers).catch(() => setSuppliers([])) }, [open])

  if (!open) return null

  async function process() {
    if (!supplierId) { showToast('error', 'Elegí proveedor'); return }
    if (!file) { showToast('error', 'Adjuntá un PDF'); return }
    setLoading(true)
    setErrorMsg(null); setErrorCid(null); setErrorDetail(null)
    try {
      const res = await importSantaPlanta(Number(supplierId), file, debug, forceOCR)

  const correlationId = (res as any).correlation_id || (res as any).correlationId || null
      // Defensive extraction: some APIs may return `purchase_id` or `id`
      let purchaseId: number | null = null
  if (typeof (res as any).purchase_id !== 'undefined') purchaseId = Number((res as any).purchase_id)
  else if (typeof (res as any).id !== 'undefined') purchaseId = Number((res as any).id)
  else if ((res as any)?.parsed?.purchase_id) purchaseId = Number((res as any).parsed.purchase_id)

      if (Number.isFinite(purchaseId)) {
        showToast('success', `Importado, abriendo compra... (correlation: ${correlationId || 'N/A'})`)
        try {
          onSuccess(purchaseId as number)
        } catch (err) {
          // Ensure modal still closes if parent onSuccess throws
          console.error('onSuccess handler threw', err)
        }
        onClose()
      } else {
        // No valid id returned — show useful debug info and keep modal open so user can act
        showToast('error', `Import realizado pero no se devolvió purchase_id. Ver logs (id: ${correlationId || 'N/A'})`)
        setErrorMsg('Import realizado pero el servidor no devolvió el ID de la compra.')
        setErrorCid(correlationId)
        setErrorDetail(res)
        // keep modal open so user can inspect
      }

    } catch (e: any) {
      const detail = e?.response?.data
      const correlationId = e?.response?.headers?.['x-correlation-id']
      const msg = (typeof detail === 'string') ? detail : (detail?.detail || 'No se pudo importar')
      
      setErrorMsg(String(msg))
      setErrorCid(correlationId || null)
      setErrorDetail(detail || null)
      showToast('error', correlationId ? `${msg} (id: ${correlationId})` : String(msg))
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div className="panel" style={{ padding: 16, minWidth: 480, position: 'relative' }}>
        <h3 style={{ marginTop: 0 }}>Importar compra desde PDF</h3>
        <div className="row" style={{ gap: 8, marginBottom: 12 }}>
          <select className="select w-full" value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Proveedor</option>
            {suppliers.map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}
          </select>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <input className="input w-full" type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        <div className="row" style={{ gap: 8, marginTop: 8, alignItems: 'center' }}>
          <label><input type="checkbox" checked={debug} onChange={e => setDebug(e.target.checked)} /> Modo debug</label>
          <label><input type="checkbox" checked={forceOCR} onChange={e => setForceOCR(e.target.checked)} /> Forzar OCR</label>
        </div>
        {errorMsg && (
          <div style={{ marginTop: 10, color: '#e74c3c' }}>
            <div>{errorMsg}{errorCid ? <span> (ID: <a href={`/purchases/logs/by-correlation/${errorCid}`} target="_blank" rel="noopener noreferrer">{errorCid}</a>)</span> : ''}</div>
            {errorDetail?.events && (
              <button className="btn-secondary" style={{ marginTop: 6 }} onClick={() => alert(JSON.stringify(errorDetail, null, 2))}>Ver detalle</button>
            )}
          </div>
        )}
        <div className="row" style={{ gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
          <button className="btn-dark" onClick={onClose} disabled={loading}>Cancelar</button>
          <button className="btn-primary" onClick={process} disabled={loading || !supplierId || !file}>{loading ? 'Procesando...' : 'Procesar'}</button>
        </div>
        <ToastContainer />
        {loading && (
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8 }}>
            <div className="panel" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600 }}>Procesando PDF…</div>
              <div className="text-sm" style={{ opacity: 0.8 }}>No cierres esta ventana. Si tarda, activá “Modo debug”.</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


