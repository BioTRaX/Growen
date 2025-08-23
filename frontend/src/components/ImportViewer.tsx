import { useEffect, useState } from 'react'
import { commitImport, getImportPreview } from '../services/imports'
import CanonicalOffers from './CanonicalOffers'
import CanonicalForm from './CanonicalForm'
import EquivalenceLinker from './EquivalenceLinker'

interface Props {
  open: boolean
  jobId: number
  summary: any
  onClose: () => void
}

export default function ImportViewer({ open, jobId, summary, onClose }: Props) {
  const [tab, setTab] = useState<'changes' | 'errors'>('changes')
  const [items, setItems] = useState<any[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [error, setError] = useState('')
  const [localSummary, setLocalSummary] = useState(summary)
  const [canonicalId, setCanonicalId] = useState<number | null>(null)
  const [editCanonicalId, setEditCanonicalId] = useState<number | null>(null)
  const [equivData, setEquivData] = useState<
    { supplierId: number; supplierProductId: number } | null
  >(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    const status = tab === 'changes' ? 'new,changed' : 'error,duplicate_in_file'
    getImportPreview(jobId, status, page)
      .then((r) => {
        setItems(r.items || [])
        setTotal(r.total || 0)
        setPages(r.pages || 1)
        if (r.page && r.page !== page) setPage(r.page)
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
      <div style={{ background: 'var(--panel-bg)', color: 'var(--text-color)', padding: 20, borderRadius: 8, width: '80%', maxHeight: '80%', overflow: 'auto' }}>
        <h3>Revisión de importación #{jobId}</h3>
        {error && <div style={{ color: 'var(--text-color)' }}>{error}</div>}
        <div>
          <strong>KPIs:</strong>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(localSummary || {}).map(([k, v]) => (
              <div
                key={k}
                style={{
                  background: 'var(--panel-bg)',
                  color: 'var(--text-color)',
                  padding: '4px 8px',
                  borderRadius: 4,
                  minWidth: 80,
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: 12 }}>{k}</div>
                <div style={{ fontWeight: 'bold' }}>{v as number}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ margin: '8px 0', display: 'flex', gap: 8 }}>
          <button onClick={() => { setTab('changes'); setPage(1) }} disabled={tab === 'changes'}>
            Cambios ({(localSummary?.new || 0) + (localSummary?.changed || 0)})
          </button>
          <button onClick={() => { setTab('errors'); setPage(1) }} disabled={tab === 'errors'}>
            Errores ({(localSummary?.errors || 0) + (localSummary?.duplicates_in_file || 0)})
          </button>
        </div>
        {loading ? (
          <div>Cargando...</div>
        ) : (
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {items.map((it) => (
              <div key={it.row_index} style={{ marginBottom: 8 }}>
                <pre>{JSON.stringify(it, null, 2)}</pre>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {it.data?.canonical_product_id && (
                    <>
                      <button
                        onClick={() => setCanonicalId(it.data.canonical_product_id)}
                      >
                        Comparar precios
                      </button>
                      <button
                        onClick={() => setEditCanonicalId(it.data.canonical_product_id)}
                      >
                        Editar canónico
                      </button>
                    </>
                  )}
                  {!it.data?.canonical_product_id && (
                    <button onClick={() => setEditCanonicalId(0)}>
                      Nuevo canónico
                    </button>
                  )}
                  {it.data?.supplier_id && it.data?.supplier_product_id && (
                    <button
                      onClick={() =>
                        setEquivData({
                          supplierId: it.data.supplier_id,
                          supplierProductId: it.data.supplier_product_id,
                        })
                      }
                    >
                      Vincular equivalencia
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <div>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              Anterior
            </button>
            <span style={{ margin: '0 8px' }}>Página {page} de {pages}</span>
            <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages}>
              Siguiente
            </button>
            <span style={{ marginLeft: 8 }}>Total: {total}</span>
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
      {canonicalId && (
        <CanonicalOffers canonicalId={canonicalId} onClose={() => setCanonicalId(null)} />
      )}
      {editCanonicalId !== null && (
        <CanonicalForm
          canonicalId={editCanonicalId || undefined}
          onClose={() => setEditCanonicalId(null)}
        />
      )}
      {equivData && (
        <EquivalenceLinker
          supplierId={equivData.supplierId}
          supplierProductId={equivData.supplierProductId}
          onClose={() => setEquivData(null)}
        />
      )}
    </div>
  )
}
