// NG-HEADER: Nombre de archivo: PurchaseDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/PurchaseDetail.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import AppToolbar from '../components/AppToolbar'
import ToastContainer, { showToast } from '../components/Toast'
import { getPurchase, updatePurchase, validatePurchase, confirmPurchase, cancelPurchase, exportUnmatched, PurchaseLine, deletePurchase, getPurchaseLogs, searchSupplierProducts } from '../services/purchases'

type SuggestionResult = {
  id: number
  supplier_product_id: string
  title: string
  product_id: number
}


export default function PurchaseDetail() {
  const nav = useNavigate()
  const { id } = useParams()
  const pid = Number(id)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [data, setData] = useState<any | null>(null)
  const [lines, setLines] = useState<PurchaseLine[]>([])
  const [logsOpen, setLogsOpen] = useState(false)
  const [logs, setLogs] = useState<{ action: string; created_at?: string; meta: any }[]>([])
  const corrId = useMemo(() => {
    for (const l of logs) {
      if ((l as any)?.meta?.correlation_id) return (l as any).meta.correlation_id as string
    }
    return ''
  }, [logs])
  const dirty = useRef(false)
  const timer = useRef<number | null>(null)
  const [searchParams] = useSearchParams()
  const [activeSuggestion, setActiveSuggestion] = useState<{ lineIdx: number; results: SuggestionResult[] } | null>(null)
  const suggestionTimeout = useRef<number | null>(null)

  const addLine = useCallback(() => {
    setLines((prev) => [...prev, { title: '', supplier_sku: '', qty: 1, unit_cost: 0, line_discount: 0 }])
  }, [])

  const handleSkuChange = (lineIdx: number, sku: string) => {
    setLines(prev => prev.map((p, i) => i === lineIdx ? { ...p, supplier_sku: sku } : p))
    if (suggestionTimeout.current) clearTimeout(suggestionTimeout.current)
    if (sku.length < 3) {
      setActiveSuggestion({ lineIdx, results: [] })
      return
    }
    suggestionTimeout.current = window.setTimeout(async () => {
      if (!data?.supplier_id) return
      try {
        const results = await searchSupplierProducts(data.supplier_id, sku)
        setActiveSuggestion({ lineIdx, results })
      } catch {
        setActiveSuggestion({ lineIdx, results: [] })
      }
    }, 300)
  }

  const selectSuggestion = (lineIdx: number, item: SuggestionResult) => {
    setLines(prev => prev.map((p, i) => i === lineIdx ? { ...p, supplier_sku: item.supplier_product_id, title: item.title, supplier_item_id: item.id, product_id: item.product_id } : p))
    setActiveSuggestion(null)
  }

  const save = useCallback(async () => {
    if (!dirty.current || !pid) return
    setSaving(true)
    try {
      const payload = {
        note: data?.note,
        global_discount: data?.global_discount ?? 0,
        vat_rate: data?.vat_rate ?? 0,
        remito_date: data?.remito_date,
        depot_id: data?.depot_id ?? null,
        lines: lines.map((ln) => ({ ...ln, qty: Number(ln.qty || 0), unit_cost: Number(ln.unit_cost || 0), line_discount: Number(ln.line_discount || 0) }))
      }
      await updatePurchase(pid, payload)
      dirty.current = false
      showToast('success', 'Guardado')
    } catch {
      showToast('error', 'No se pudo guardar')
    } finally {
      setSaving(false)
    }
  }, [pid, data, lines])

  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save() }
    if (e.key === 'Escape') { e.preventDefault(); nav(PATHS.purchases) }
    if (e.key === 'Enter') { e.preventDefault(); addLine() }
  }, [nav, addLine, save])

  useEffect(() => {
    (async () => {
      setLoading(true)
      try {
        const p = await getPurchase(pid)
        setData(p)
        setLines(p.lines || [])
        // open logs drawer if requested
        if (searchParams.get('logs') === '1') {
          setLogsOpen(true)
        }
      } finally { setLoading(false) }
    })()
  }, [pid])

  useEffect(() => {
    timer.current = window.setInterval(save, 30000)
    return () => { if (timer.current) window.clearInterval(timer.current); window.removeEventListener('keydown', onKey) }
  }, [save])

  useEffect(() => { window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [onKey])
  useEffect(() => { dirty.current = true }, [data, lines])

  useEffect(() => {
    if (!logsOpen) return
    (async () => {
      try {
        const r = await getPurchaseLogs(pid, 200)
        setLogs(r.items || [])
      } catch {}
    })()
  }, [logsOpen, pid])

  const unmatched = useMemo(() => (lines || []).filter(l => !l.product_id && !l.supplier_item_id).length, [lines])
  const totals = useMemo(() => {
    const server = (data as any)?.totals
    if (server) return server
    const vatRate = Number(data?.vat_rate || 0)
    let subtotal = 0
    for (const ln of lines) {
      const qty = Number(ln.qty || 0)
      const unit = Number(ln.unit_cost || 0)
      const disc = Number(ln.line_discount || 0)
      const eff = unit * (1 - disc / 100)
      subtotal += qty * eff
    }
    const iva = subtotal * (vatRate / 100)
    const total = subtotal + iva
    return { subtotal, iva, total }
  }, [lines, data?.vat_rate, (data as any)?.totals])

  async function doValidate() {
    try {
      const res = await validatePurchase(pid)
      showToast('success', res.unmatched === 0 ? 'Validada, sin pendientes' : `Validada con ${res.unmatched} sin vincular`)
      const p = await getPurchase(pid)
      setData(p)
      setLines(p.lines || [])
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al validar')
    }
  }

  async function doConfirm() {
    try {
      await confirmPurchase(pid)
      showToast('success', 'Compra confirmada')
      const p = await getPurchase(pid)
      setData(p)
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al confirmar')
    }
  }

  async function doCancel() {
    const note = prompt('Motivo de anulación (obligatorio)')
    if (!note) return
    try {
      await cancelPurchase(pid, note)
      showToast('success', 'Compra anulada')
      nav('/compras')
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al anular')
    }
  }

  async function doDelete() {
    if (!data) return
    if (!(data.status === 'BORRADOR' || data.status === 'ANULADA')) {
      showToast('error', 'Solo se puede eliminar si está en BORRADOR o ANULADA')
      return
    }
    if (!confirm('¿Eliminar compra? Esta acción no se puede deshacer.')) return
    try {
      await deletePurchase(pid)
      showToast('success', 'Compra eliminada')
      nav(PATHS.purchases)
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'No se pudo eliminar')
    }
  }

  if (loading) return (<><AppToolbar /><div className="panel p-4">Cargando...</div></>)

  return (
    <>
      <AppToolbar />
      <div className="panel p-4">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Compra #{data?.id} — {data?.status}</h2>
          <div className="row" style={{ gap: 12, alignItems: 'center' }}>
            <div style={{ fontWeight: 600 }}>Total: {totals.total.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })}</div>
            <button className="btn-dark btn-lg" onClick={save} disabled={saving}>{saving ? 'Guardando...' : 'Guardar (Ctrl+S)'}</button>
            <button className="btn btn-lg" onClick={doValidate}>Validar</button>
            <button
              className="btn-primary btn-lg"
              onClick={doConfirm}
              disabled={data?.status === 'CONFIRMADA' || (lines?.length || 0) === 0 || (totals?.total || 0) === 0}
              title={(lines?.length || 0) === 0 ? 'No hay líneas importadas' : ((totals?.total || 0) === 0 ? 'Total de la compra es 0' : '')}
            >
              Confirmar
            </button>
            <button className="btn-secondary btn-lg" onClick={() => exportUnmatched(pid, 'csv')} disabled={!unmatched}>Exportar SIN_VINCULAR</button>
            <Link to={PATHS.purchases} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Cerrar</Link>
          </div>
        </div>
        <div className="text-sm" style={{ opacity: 0.8, marginBottom: 8 }}>
          Consejo amistoso: si el remito no coincide, no lo inventes, rey.
        </div>

        <div className="row mb-3" style={{ gap: 10, alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label className="label">Fecha</label>
            <input className="input" style={{ minWidth: 220 }} type="date" value={data?.remito_date || ''} onChange={(e) => setData({ ...data, remito_date: e.target.value })} disabled={(data?.attachments?.length || 0) > 0 && (data?.lines?.length || 0) > 0 && data?.status === 'BORRADOR'} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label className="label">Nº de remito</label>
            <input className="input" value={data?.remito_number || ''} onChange={(e) => setData({ ...data, remito_number: e.target.value })} disabled={(data?.attachments?.length || 0) > 0 && (data?.lines?.length || 0) > 0 && data?.status === 'BORRADOR'} />
          </div>
          {/* Quitar descuento global del header según especificación */}
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <label className="label">IVA %</label>
            <input className="input" type="number" step={0.01} value={data?.vat_rate ?? 0} onChange={(e) => setData({ ...data, vat_rate: Number(e.target.value) })} />
          </div>
          {Array.isArray((data as any)?.attachments) && (data as any).attachments.length > 0 && (
            <a className="btn" href={(data as any).attachments[0].url} target="_blank" rel="noreferrer">Ver PDF original</a>
          )}
          <button className="btn-secondary" onClick={() => setLogsOpen(true)}>Ver logs</button>
        </div>
        <textarea className="input w-full" rows={3} placeholder="Nota" value={data?.note || ''} onChange={(e) => setData({ ...data, note: e.target.value })} />

        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginTop: 16 }}>
          <h3 style={{ margin: 0 }}>Líneas ({lines.length}) {unmatched ? `— ${unmatched} SIN_VINCULAR` : ''}</h3>
          <div className="row">
            <button className="btn" onClick={addLine}>Agregar línea (Enter)</button>
          </div>
        </div>
        <table className="table w-full">
          <thead>
            <tr>
              <th>SKU prov.</th>
              <th>Título</th>
              <th className="text-center">Cant.</th>
              <th className="text-center">P. Unit. (bonif)</th>
              <th className="text-center">Desc. %</th>
              <th className="text-center">Subtotal</th>
              <th className="text-center">IVA</th>
              <th className="text-center">Total</th>
              <th className="text-center">Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((ln, idx) => (
              <tr key={idx}>
                <td style={{ position: 'relative' }}>
                  <input
                    className="input"
                    value={ln.supplier_sku || ''}
                    onChange={(e) => handleSkuChange(idx, e.target.value)}
                    onFocus={() => setActiveSuggestion({ lineIdx: idx, results: [] })}
                    onBlur={() => setTimeout(() => setActiveSuggestion(null), 200)}
                  />
                  {activeSuggestion?.lineIdx === idx && activeSuggestion.results.length > 0 && (
                    <div className="autocomplete-suggestions">
                      {activeSuggestion.results.map((r) => (
                        <div key={r.id} onMouseDown={() => selectSuggestion(idx, r)}>
                          {r.supplier_product_id} - {r.title}
                        </div>
                      ))}
                    </div>
                  )}
                </td>
                <td><input className="input w-full" value={ln.title || ''} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, title: e.target.value } : p))} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.qty || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, qty: Number(e.target.value) } : p))} style={{ width: 90 }} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.unit_cost || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, unit_cost: Number(e.target.value) } : p))} style={{ width: 110 }} /></td>
                <td className="text-center"><input className="input" type="number" step={0.01} value={ln.line_discount || 0} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, line_discount: Number(e.target.value) } : p))} style={{ width: 90 }} /></td>
                {(() => {
                  const qty = Number(ln.qty || 0)
                  const unit = Number(ln.unit_cost || 0)
                  const disc = Number(ln.line_discount || 0)
                  const eff = unit * (1 - disc / 100)
                  const sub = qty * eff
                  const iva = sub * Number(data?.vat_rate || 0) / 100
                  const tot = sub + iva
                  const fmt = (n: number) => n.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })
                  return (
                    <>
                      <td className="text-center">{fmt(sub)}</td>
                      <td className="text-center">{fmt(iva)}</td>
                      <td className="text-center">{fmt(tot)}</td>
                    </>
                  )
                })()}
                <td className="text-center" style={{ color: (!ln.product_id && !ln.supplier_item_id) ? '#e67e22' : undefined }}>{ln.state || ((!ln.product_id && !ln.supplier_item_id) ? 'SIN_VINCULAR' : 'OK')}</td>
                <td><button className="btn-secondary" onClick={() => setLines(prev => prev.filter((_, i) => i !== idx))}>Borrar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row" style={{ justifyContent: 'flex-end', gap: 16, marginTop: 8 }}>
          <div><b>Subtotal:</b> {totals.subtotal.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })}</div>
          <div><b>IVA:</b> {totals.iva.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })}</div>
          <div><b>Total:</b> {totals.total.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })}</div>
        </div>
        <div className="text-sm" style={{ opacity: 0.8, marginTop: 8 }}>Chicana del día: Si el PDF está torcido, no es arte: es el scanner del proveedor.</div>
        <div className="row" style={{ marginTop: 16, justifyContent: 'center' }}>
          <button className="btn-dark btn-lg" onClick={save} disabled={saving}>{saving ? 'Guardando...' : 'Guardar (Ctrl+S)'}</button>
          <button className="btn-secondary btn-lg" onClick={doCancel}>Anular</button>
          <button className="btn btn-danger btn-lg" onClick={doDelete} disabled={!(data?.status === 'BORRADOR' || data?.status === 'ANULADA')} title={!(data?.status === 'BORRADOR' || data?.status === 'ANULADA') ? 'Solo en BORRADOR o ANULADA' : ''}>Eliminar</button>
        </div>
      </div>
      {logsOpen && (
        <div style={{ position: 'fixed', top: 0, right: 0, height: '100%', width: 420, background: 'var(--panel-bg)', borderLeft: '1px solid var(--border)', boxShadow: '0 0 24px rgba(0,0,0,0.35)', zIndex: 60, display: 'flex', flexDirection: 'column' }}>
          <div className="row" style={{ padding: 12, borderBottom: '1px solid var(--border)', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontWeight: 600 }}>Logs de importación</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {corrId ? <button className="btn" onClick={() => { navigator.clipboard.writeText(corrId) }}>Copiar ID</button> : null}
              <a className="btn" href={`/purchases/${pid}/logs?format=json`} target="_blank" rel="noreferrer">Descargar JSON</a>
              <button className="btn-secondary" onClick={() => setLogsOpen(false)}>Cerrar</button>
            </div>
          </div>
          <div style={{ padding: 12, overflow: 'auto' }}>
            {corrId && (<div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>correlation_id: {corrId}</div>)}
            {logs.length === 0 ? (
              <div style={{ opacity: 0.8 }}>Sin logs</div>
            ) : (
              logs.map((l, i) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: 12, opacity: 0.7 }}>{l.created_at || ''} · {l.action}</div>
                  <pre className="code" style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(l.meta || {}, null, 2)}</pre>
                </div>
              ))
            )}
          </div>
        </div>
      )}
      <ToastContainer />
    </>
  )
}
