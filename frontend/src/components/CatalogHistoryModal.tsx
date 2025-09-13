// NG-HEADER: Nombre de archivo: CatalogHistoryModal.tsx
// NG-HEADER: Ubicación: frontend/src/components/CatalogHistoryModal.tsx
// NG-HEADER: Descripción: Modal para listar catálogos PDF históricos y acceder a ver/descargar.
// NG-HEADER: Lineamientos: Ver AGENTS.md
import React, { useEffect, useState } from 'react'
import { listCatalogs, CatalogListItem, CatalogListResponse, deleteCatalog } from '../services/catalogs'
import { useToast } from './ToastProvider'

interface Props {
  open: boolean
  onClose: () => void
}

export const CatalogHistoryModal: React.FC<Props> = ({ open, onClose }) => {
  const [items, setItems] = useState<CatalogListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [fromDt, setFromDt] = useState('')
  const [toDt, setToDt] = useState('')
  const { push } = useToast()

  const load = () => {
    setLoading(true)
    listCatalogs({ page, page_size: pageSize, from_dt: fromDt || undefined, to_dt: toDt || undefined })
      .then((r: CatalogListResponse) => { setItems(r.items); setTotal(r.total); setPages(r.pages) })
      .catch(e => push({ message: e.message || 'Error cargando catálogos', kind: 'error' }))
      .finally(() => setLoading(false))
  }
  useEffect(() => { if (open) load() }, [open, page, fromDt, toDt])
  const resetAndLoad = () => { setPage(1); setTimeout(load, 0) }

  if (!open) return null

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={modalStyle} onClick={e => e.stopPropagation()}>
        <div style={headerStyle}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Histórico de catálogos</h2>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:8 }}>
          <input type="date" value={fromDt} onChange={e => { setFromDt(e.target.value); setPage(1) }} style={dateInput} />
          <input type="date" value={toDt} onChange={e => { setToDt(e.target.value); setPage(1) }} style={dateInput} />
          <button style={smallBtn} onClick={() => { setFromDt(''); setToDt(''); resetAndLoad() }}>Limpiar filtros</button>
          <a href={`/api/catalogs/export.csv${buildExportQS(fromDt,toDt)}`} style={smallLink} target="_blank" rel="noreferrer">Export CSV</a>
        </div>
        {loading && <div style={{ padding: '12px 4px' }}>Cargando...</div>}
        {!loading && items.length === 0 && <div style={{ padding: '12px 4px' }}>No hay catálogos generados.</div>}
        {!loading && items.length > 0 && (
          <div style={listStyle}>
            {items.map(it => (
              <div key={it.id} style={rowStyle}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: '#fff' }}>
                    {it.id} {it.latest && <span style={latestPill}>latest</span>}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>{new Date(it.modified_at).toLocaleString()} · {(it.size / 1024).toFixed(1)} KB</div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <a href={`/api/catalogs/${it.id}`} target="_blank" rel="noreferrer" style={actionLink}>Ver</a>
                  <a href={`/api/catalogs/${it.id}/download`} style={actionLink}>Descargar</a>
                  <button style={delBtn} onClick={async () => {
                    if (!window.confirm('¿Eliminar catálogo ' + it.id + '?')) return
                    try { await deleteCatalog(it.id); push({ kind:'success', message:'Catálogo eliminado' }); load() } catch(e:any){ push({ kind:'error', message:e.message||'Error' }) }
                  }}>Borrar</button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginTop:8 }}>
          <div style={{ fontSize:12 }}>{total} resultados · página {page}/{pages}</div>
          <div style={{ display:'flex', gap:6 }}>
            <button style={smallBtn} disabled={page<=1 || loading} onClick={() => setPage(p => Math.max(1, p-1))}>Anterior</button>
            <button style={smallBtn} disabled={page>=pages || loading} onClick={() => setPage(p => Math.min(pages, p+1))}>Siguiente</button>
          </div>
        </div>
      </div>
    </div>
  )
}

const backdropStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 80, zIndex: 1000
}
const modalStyle: React.CSSProperties = {
  width: 600, maxHeight: '70vh', background: '#1b1b1b', border: '1px solid #333', borderRadius: 8, padding: 16, overflow: 'hidden', display: 'flex', flexDirection: 'column'
}
const headerStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }
const closeBtn: React.CSSProperties = { background: 'transparent', border: 'none', color: '#aaa', cursor: 'pointer', fontSize: 18 }
const listStyle: React.CSSProperties = { overflowY: 'auto', paddingRight: 4, display: 'flex', flexDirection: 'column', gap: 4 }
const rowStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, padding: '8px 6px', background: '#232323', border: '1px solid #2d2d2d', borderRadius: 6 }
const actionLink: React.CSSProperties = { fontSize: 12, color: '#22c55e', textDecoration: 'none', background: '#143122', padding: '4px 8px', borderRadius: 4 }
const latestPill: React.CSSProperties = { fontSize: 10, background: '#f0f', color: '#000', padding: '2px 6px', marginLeft: 6, borderRadius: 12, fontWeight: 600 }
const dateInput: React.CSSProperties = { background:'#232323', border:'1px solid #333', color:'#ddd', padding:'4px 6px', borderRadius:4, fontSize:12 }
const smallBtn: React.CSSProperties = { background:'#143122', border:'1px solid #234', color:'#22c55e', padding:'4px 8px', borderRadius:4, fontSize:12, cursor:'pointer' }
const smallLink: React.CSSProperties = { background:'#222', border:'1px solid #444', color:'#7c4dff', padding:'4px 8px', borderRadius:4, fontSize:12, textDecoration:'none' }
const delBtn: React.CSSProperties = { background:'#2d1212', border:'1px solid #5c1f1f', color:'#f43f5e', padding:'4px 8px', borderRadius:4, fontSize:12, cursor:'pointer' }

function buildExportQS(fromDt: string, toDt: string) {
  const qs = new URLSearchParams()
  if (fromDt) qs.set('from_dt', fromDt)
  if (toDt) qs.set('to_dt', toDt)
  const s = qs.toString()
  return s ? ('?'+s) : ''
}

export default CatalogHistoryModal
