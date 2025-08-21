import { useEffect, useState } from 'react'
import { commitImport, getImportPreview } from '../services/imports'

interface Props {
  open: boolean
  jobId: number
  summary: any
  kpis: any
  onClose: () => void
}

export default function ImportViewer({ open, jobId, summary, kpis, onClose }: Props) {
  const [tab, setTab] = useState<'changes' | 'errors'>('changes')
  const [items, setItems] = useState<any[]>([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [error, setError] = useState('')
  const [localSummary, setLocalSummary] = useState(summary)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    const status = tab === 'changes' ? 'new,changed' : 'error,duplicate_in_file'
    getImportPreview(jobId, status, page)
      .then((r) => {
        setItems(r.items || [])
        if (r.summary) setLocalSummary(r.summary)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [open, tab, page, jobId])

  async function confirm() {
    try {
      setCommitting(true)
      const r = await commitImport(jobId)
      alert(`Insertados: ${r.inserted}, Actualizados: ${r.updated}, Cambios de precio: ${r.price_changes}`)
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCommitting(false)
    }
  }

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', padding: 20, borderRadius: 8, width: '80%', maxHeight: '80%', overflow: 'auto' }}>
        <h3>Revisión de importación #{jobId}</h3>
        {error && <div style={{ color: 'red' }}>{error}</div>}
        <div>
          <strong>KPIs:</strong>
          <pre>{JSON.stringify(kpis, null, 2)}</pre>
        </div>
        <div style={{ margin: '8px 0', display: 'flex', gap: 8 }}>
          <button onClick={() => { setTab('changes'); setPage(1) }} disabled={tab === 'changes'}>Cambios</button>
          <button onClick={() => { setTab('errors'); setPage(1) }} disabled={tab === 'errors'}>Errores</button>
        </div>
        {loading ? (
          <div>Cargando...</div>
        ) : (
          <pre style={{ maxHeight: 300, overflow: 'auto' }}>{JSON.stringify(items, null, 2)}</pre>
        )}
        <div>
          <strong>Resumen:</strong>
          <pre>{JSON.stringify(localSummary, null, 2)}</pre>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <div>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              Anterior
            </button>
            <span style={{ margin: '0 8px' }}>Página {page}</span>
            <button onClick={() => setPage((p) => p + 1)}>Siguiente</button>
          </div>
          <div>
            <button onClick={onClose} style={{ marginRight: 8 }}>
              Cerrar
            </button>
            <button onClick={confirm} disabled={committing}>
              {committing ? 'Confirmando...' : 'Confirmar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
