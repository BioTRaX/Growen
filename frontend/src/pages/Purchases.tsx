// NG-HEADER: Nombre de archivo: Purchases.tsx
// NG-HEADER: Ubicación: frontend/src/pages/Purchases.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import AppToolbar from '../components/AppToolbar'
import http from '../services/http'
import ToastContainer, { showToast } from '../components/Toast'
import { PATHS } from '../routes/paths'
import PdfImportModal from '../components/PdfImportModal'
import { deletePurchase } from '../services/purchases'

interface PurchaseRow {
  id: number
  supplier_id: number
  remito_number: string
  status: string
  remito_date: string
}

export default function Purchases() {
  const nav = useNavigate()
  const [rows, setRows] = useState<PurchaseRow[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [openPdf, setOpenPdf] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [status, setStatus] = useState('')
  const [remito, setRemito] = useState('')
  const [productName, setProductName] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const t = setTimeout(() => {
      http.get<{ items: PurchaseRow[] }>('/purchases', { params: {
        supplier_id: supplierId || undefined,
        status: status || undefined,
        remito_number: remito || undefined,
        product_name: productName || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }}).then(r => setRows(r.data.items)).catch(() => setRows([]))
    }, 250)
    return () => clearTimeout(t)
  }, [supplierId, status, remito, productName, dateFrom, dateTo])

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as any)) setMenuOpen(false)
    }
    window.addEventListener('click', onClick)
    return () => window.removeEventListener('click', onClick)
  }, [])

  return (
    <>
      <AppToolbar />
      <div className="panel p-4">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Compras</h2>
          <div className="row" style={{ gap: 12, position: 'relative', alignItems: 'center' }}>
            <div ref={menuRef} style={{ position: 'relative' }}>
              <button className="btn-primary btn-lg" onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v) }}>Cargar compra</button>
              {menuOpen && (
                <div className="panel" style={{ position: 'absolute', right: 0, minWidth: 300, background: 'var(--panel-bg)', border: '1px solid var(--border)', padding: 12, marginTop: 6, display: 'flex', flexDirection: 'column', gap: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.35)' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'stretch' }}>
                    <button className="btn-dark btn-lg" onClick={() => { setOpenPdf(true); setMenuOpen(false) }}>Con PDF de proveedor</button>
                    <Link to={PATHS.purchasesNew} className="btn-dark btn-lg" onClick={() => setMenuOpen(false)} style={{ textDecoration: 'none', display: 'block', textAlign: 'center' }}>Manual</Link>
                  </div>
                </div>
              )}
            </div>
            <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver</Link>
          </div>
        </div>
        <div className="text-sm" style={{ opacity: 0.8, marginBottom: 8 }}>
          Tip: si el remito no coincide, no lo inventes, rey. Pedí otro.
        </div>
        <div className="row" style={{ gap: 8, marginBottom: 8 }}>
          <input className="input" placeholder="Proveedor ID" value={supplierId} onChange={(e) => setSupplierId(e.target.value)} />
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Estado</option>
            <option>BORRADOR</option>
            <option>VALIDADA</option>
            <option>CONFIRMADA</option>
            <option>ANULADA</option>
          </select>
          <input className="input" placeholder="Remito" value={remito} onChange={(e) => setRemito(e.target.value)} />
          <input className="input" placeholder="Producto" value={productName} onChange={(e) => setProductName(e.target.value)} />
          <input className="input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input className="input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <table className="table w-full">
          <thead>
            <tr>
              <th>ID</th>
              <th>Proveedor</th>
              <th>Remito</th>
              <th>Fecha</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.supplier_id}</td>
                <td>{r.remito_number}</td>
                <td>{new Date(r.remito_date).toLocaleDateString()}</td>
                <td>{r.status}</td>
                <td>
                  <div className="row" style={{ justifyContent: 'flex-start', alignItems: 'center' }}>
                  <Link className="btn-secondary" to={`/compras/${r.id}`}>Abrir</Link>
                  {(r.status === 'BORRADOR' || r.status === 'ANULADA') && (
                    <button
                      className="btn btn-danger"
                      style={{ marginLeft: 6 }}
                      onClick={async () => {
                        if (!confirm('¿Eliminar compra? Esta acción no se puede deshacer.')) return
                        try {
                          await deletePurchase(r.id)
                          showToast('success', 'Eliminada')
                          setRows(rows.filter(x => x.id !== r.id))
                        } catch (e: any) {
                          showToast('error', e?.response?.data?.detail || 'No se pudo eliminar')
                        }
                      }}
                    >
                      Eliminar
                    </button>
                  )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row" style={{ justifyContent: 'center', marginTop: 12 }}>
          <Link to={PATHS.home} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Volver al inicio</Link>
        </div>
      </div>
      <ToastContainer />

  <PdfImportModal open={openPdf} onClose={() => setOpenPdf(false)} onSuccess={(id) => setTimeout(() => nav(`/compras/${id}?logs=1`), 300)} />
    </>
  )
}
