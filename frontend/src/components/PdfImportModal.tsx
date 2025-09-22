// NG-HEADER: Nombre de archivo: PdfImportModal.tsx
// NG-HEADER: Ubicacion: frontend/src/components/PdfImportModal.tsx
// NG-HEADER: Descripcion: Modal para importar compras PDF con selector de proveedor integrado al tema
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useState } from 'react'
import SupplierAutocomplete from './supplier/SupplierAutocomplete'
import type { SupplierSearchItem } from '../services/suppliers'
import { importSantaPlanta } from '../services/purchases'
import { serviceStatus, tailServiceLogs, ServiceLogItem } from '../services/servicesAdmin'
import { ensureServiceRunning } from '../lib/ensureServiceRunning'
import ToastContainer, { showToast } from './Toast'

type Props = {
  open: boolean
  onClose: () => void
  onSuccess: (purchaseId: number) => void
}

export default function PdfImportModal({ open, onClose, onSuccess }: Props) {
  const [supplierSel, setSupplierSel] = useState<SupplierSearchItem | null>(null)
  const [supplierId, setSupplierId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [debug, setDebug] = useState(false)
  const [forceOCR, setForceOCR] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [errorCid, setErrorCid] = useState<string | null>(null)
  const [errorDetail, setErrorDetail] = useState<any>(null)
  const [gateNeeded, setGateNeeded] = useState(false)
  const [gateBusy, setGateBusy] = useState(false)
  const [gateLogs, setGateLogs] = useState<ServiceLogItem[]>([])

  useEffect(() => {
    if (open) return
    setSupplierSel(null)
    setSupplierId('')
    setFile(null)
    setLoading(false)
    setDebug(false)
    setForceOCR(false)
    setErrorMsg(null)
    setErrorCid(null)
    setErrorDetail(null)
    setGateNeeded(false)
    setGateBusy(false)
    setGateLogs([])
  }, [open])

  if (!open) return null

  async function ensurePdfService(): Promise<boolean> {
    try {
      const st = await serviceStatus('pdf_import')
      if ((st?.status || '') !== 'running') {
        setGateNeeded(true)
        try { setGateLogs(await tailServiceLogs('pdf_import', 50)) } catch {}
        return false
      }
      return true
    } catch {
      return true
    }
  }

  async function startPdfNow() {
    setGateBusy(true)
    try {
      await ensureServiceRunning('pdf_import', { timeoutMs: 60_000, intervalMs: 1_500 })
      setGateNeeded(false)
      showToast('success', 'Importador PDF en ejecucion')
    } catch (e: any) {
      const msg = e?.message || e?.response?.data?.detail || 'No se pudo iniciar el Importador PDF'
      showToast('error', msg)
      try { setGateLogs(await tailServiceLogs('pdf_import', 120)) } catch {}
    } finally {
      setGateBusy(false)
    }
  }

  async function process() {
    if (!supplierId) { showToast('error', 'Elegi proveedor'); return }
    if (!file) { showToast('error', 'Adjunta un PDF'); return }
    const ok = await ensurePdfService()
    if (!ok) return
    setLoading(true)
    setErrorMsg(null); setErrorCid(null); setErrorDetail(null)
    try {
      const res = await importSantaPlanta(Number(supplierId), file, debug, forceOCR)
      const correlationId = (res as any).correlation_id || (res as any).correlationId || null

      let purchaseId: number | null = null
      if (typeof (res as any).purchase_id !== 'undefined') purchaseId = Number((res as any).purchase_id)
      else if (typeof (res as any).id !== 'undefined') purchaseId = Number((res as any).id)
      else if ((res as any)?.parsed?.purchase_id) purchaseId = Number((res as any).parsed.purchase_id)

      if (Number.isFinite(purchaseId)) {
        showToast('success', `Importado, abriendo compra... (correlation: ${correlationId || 'N/A'})`)
        try {
          onSuccess(purchaseId as number)
        } catch (err) {
          console.error('onSuccess handler threw', err)
        }
        onClose()
      } else {
        showToast('error', `Import realizado pero no se devolvio purchase_id. Ver logs (id: ${correlationId || 'N/A'})`)
        setErrorMsg('Import realizado pero el servidor no devolvio el ID de la compra.')
        setErrorCid(correlationId)
        setErrorDetail(res)
      }
    } catch (e: any) {
      const detail = e?.response?.data
      const correlationId = e?.response?.headers?.['x-correlation-id']
      const msg = typeof detail === 'string' ? detail : (detail?.detail || 'No se pudo importar')

      setErrorMsg(String(msg))
      setErrorCid(correlationId || null)
      setErrorDetail(detail || null)
      showToast('error', correlationId ? `${msg} (id: ${correlationId})` : String(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className='modal-backdrop'
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
      }}
    >
      <div className='panel' style={{ padding: 18, minWidth: 480, position: 'relative' }}>
        <h3 style={{ marginTop: 0, marginBottom: 12 }}>Importar compra desde PDF</h3>
        <div className='row' style={{ gap: 10, marginBottom: 12 }}>
          <SupplierAutocomplete
            value={supplierSel}
            onChange={(item) => { setSupplierSel(item); setSupplierId(item ? String(item.id) : '') }}
            placeholder='Proveedor'
            autoFocus
            className='w-full'
          />
        </div>
        <div className='row' style={{ gap: 10 }}>
          <input className='input w-full' type='file' accept='application/pdf' onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        <div className='row' style={{ gap: 12, marginTop: 10, alignItems: 'center' }}>
          <label><input type='checkbox' checked={debug} onChange={(e) => setDebug(e.target.checked)} /> Modo debug</label>
          <label><input type='checkbox' checked={forceOCR} onChange={(e) => setForceOCR(e.target.checked)} /> Forzar OCR</label>
        </div>
        {errorMsg && (
          <div style={{ marginTop: 12, color: 'var(--danger, #ef4444)' }}>
            <div>
              {errorMsg}
              {errorCid ? (
                <span>
                  {' '}(ID:{' '}
                  <a href={`/purchases/logs/by-correlation/${errorCid}`} target='_blank' rel='noopener noreferrer'>
                    {errorCid}
                  </a>)
                </span>
              ) : null}
            </div>
            {errorDetail?.events && (
              <button
                className='btn-secondary'
                style={{ marginTop: 6 }}
                onClick={() => alert(JSON.stringify(errorDetail, null, 2))}
              >
                Ver detalle
              </button>
            )}
          </div>
        )}
        <div className='row' style={{ gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
          <button className='btn-dark' onClick={onClose} disabled={loading}>Cancelar</button>
          <button className='btn-primary' onClick={process} disabled={loading || !supplierId || !file}>
            {loading ? 'Procesando...' : 'Procesar'}
          </button>
        </div>
        <ToastContainer />

        {gateNeeded && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(0,0,0,0.55)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 10,
            }}
          >
            <div className='panel' style={{ padding: 18, minWidth: 420 }}>
              <h4 style={{ marginTop: 0 }}>Importador apagado</h4>
              <p className='text-sm' style={{ opacity: 0.9 }}>
                Este paso necesita el servicio "Importador PDF (OCR)" encendido. Iniciarlo ahora?
              </p>
              <div className='row' style={{ gap: 10, marginTop: 10 }}>
                <button className='btn-secondary' onClick={() => setGateNeeded(false)} disabled={gateBusy}>Cancelar</button>
                <button className='btn-primary' onClick={startPdfNow} disabled={gateBusy}>
                  {gateBusy ? 'Iniciando...' : 'Iniciar ahora'}
                </button>
              </div>
              <details style={{ marginTop: 10 }}>
                <summary>Ver logs recientes</summary>
                <ul style={{ maxHeight: 160, overflow: 'auto', fontSize: 12, marginTop: 6 }}>
                  {gateLogs.map((log, idx) => (
                    <li key={idx}>
                      [{log.level}] {log.created_at} - {log.action} - {log.ok ? 'OK' : 'FAIL'} -
                      {' '}{(log as any).error || (log as any)?.payload?.detail || ''}
                    </li>
                  ))}
                </ul>
                <button
                  className='btn'
                  onClick={async () => {
                    try { setGateLogs(await tailServiceLogs('pdf_import', 120)) } catch {}
                  }}
                >
                  Actualizar logs
                </button>
              </details>
            </div>
          </div>
        )}

        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(0,0,0,0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 10,
            }}
          >
            <div className='panel' style={{ padding: 18, textAlign: 'center' }}>
              <div style={{ fontWeight: 600 }}>Procesando PDF...</div>
              <div className='text-sm' style={{ opacity: 0.8, marginTop: 4 }}>
                No cierres esta ventana. Si tarda, activa "Modo debug" para ver mas detalle.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
