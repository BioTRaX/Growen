// NG-HEADER: Nombre de archivo: PurchaseDetail.tsx
// NG-HEADER: Ubicación: frontend/src/pages/PurchaseDetail.tsx
// NG-HEADER: Descripción: Pendiente de descripción
// NG-HEADER: Lineamientos: Ver AGENTS.md
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom'
import { PATHS } from '../routes/paths'
import AppToolbar from '../components/AppToolbar'
import ToastContainer, { showToast } from '../components/Toast'
import { getPurchase, updatePurchase, validatePurchase, confirmPurchase, cancelPurchase, exportUnmatched, PurchaseLine, deletePurchase, getPurchaseLogs, searchSupplierProducts, resendPurchaseStock, iavalPreview, iavalApply, rollbackPurchase } from '../services/purchases'
import { createProduct } from '../services/products'

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
  const [auditOpen, setAuditOpen] = useState(false)
  const appliedDeltas = useMemo(() => {
    // Buscar en logs eventos que contengan applied_deltas o applied deltas
    const items: { when?: string; list: { product_id?: number; product_title?: string | null; delta?: number; new?: number; old?: number }[] }[] = []
    for (const l of logs) {
      const m = l?.meta || {}
      const list = (m.applied_deltas || m.applied || []) as any[]
      if (Array.isArray(list) && list.length > 0) {
        items.push({ when: l.created_at, list: list as any })
      }
    }
    return items
  }, [logs])
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
  const [createForLine, setCreateForLine] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [newProdName, setNewProdName] = useState('')
  const [newProdStock, setNewProdStock] = useState('0')
  const [selectedLines, setSelectedLines] = useState<Set<number>>(new Set())
  const [bulkCreateOpen, setBulkCreateOpen] = useState(false)
  const [bulkPrefix, setBulkPrefix] = useState('')
  const [bulkCreating, setBulkCreating] = useState(false)
  // iAVaL (AI Validator)
  const [iavalOpen, setIavalOpen] = useState(false)
  const [iavalLoading, setIavalLoading] = useState(false)
  const [iavalResult, setIavalResult] = useState<any | null>(null)
  const [iavalError, setIavalError] = useState<string | null>(null)
  const [iavalEmitLog, setIavalEmitLog] = useState<boolean>(false)
    const [iavalDownload, setIavalDownload] = useState<{ url_json?: string; url_csv?: string | null } | null>(null)

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
        // Auto-link if an exact SKU match is present
        const exact = results.find(r => r.supplier_product_id === sku)
        if (exact) {
          setLines(prev => prev.map((p, i) => i === lineIdx ? { ...p, supplier_item_id: exact.id, product_id: exact.product_id, title: p.title || exact.title, state: 'OK' } : p))
          setActiveSuggestion(null)
          return
        }
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
      const res = await validatePurchase(pid) as any
      const msgs: string[] = []
      if (typeof res.linked === 'number' && res.linked > 0) msgs.push(`Autovinculadas ${res.linked}`)
      if (typeof res.unmatched === 'number') msgs.push(res.unmatched === 0 ? 'sin pendientes' : `${res.unmatched} sin vincular`)
      showToast('success', `Validada: ${msgs.join(' · ')}`)
      if (Array.isArray(res.missing_skus) && res.missing_skus.length > 0) {
        const list = res.missing_skus.slice(0, 6).join(', ')
        showToast('info', `SKUs no encontrados para este proveedor: ${list}${res.missing_skus.length > 6 ? '…' : ''}`)
      }
      const p = await getPurchase(pid)
      setData(p)
      setLines(p.lines || [])
    } catch (e: any) {
      showToast('error', e?.response?.data?.detail || 'Error al validar')
    }
  }

  async function doConfirm() {
    try {
      const res = await confirmPurchase(pid, true)
      showToast('success', 'Compra confirmada')
      if (Array.isArray(res.applied_deltas) && res.applied_deltas.length > 0) {
        for (const d of res.applied_deltas.slice(0, 5)) {
          const name = d.product_title || `Producto ${d.product_id}`
          const idLabel = d.product_id ? ` · ID ${d.product_id}` : ''
          showToast('info', `${name}${idLabel}: +${d.delta} (→ ${d.new})`)
        }
        if (res.applied_deltas.length > 5) showToast('info', `(+${res.applied_deltas.length - 5} más)`) 
      }
      if (Array.isArray(res.unresolved_lines) && res.unresolved_lines.length > 0) {
        showToast('warning', `Líneas sin producto: ${res.unresolved_lines.join(', ')}`)
      }
      // Si hay mismatch significativo ofrecer rollback inmediato
      if (res?.totals?.mismatch && res.can_rollback) {
        const pt = res.totals.purchase_total.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })
        const at = res.totals.applied_total.toLocaleString('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 2 })
        const ok = confirm(`Atención: los totales no coinciden.\nRemito: ${pt}\nAplicado a stock: ${at}\n\n¿Deseás hacer ROLLBACK ahora mismo?`)
        if (ok) {
          try {
            const rb = await rollbackPurchase(pid)
            showToast('success', 'Rollback aplicado')
            if (Array.isArray(rb.reverted) && rb.reverted.length > 0) {
              for (const d of rb.reverted.slice(0, 5)) {
                showToast('info', `Prod ${d.product_id}: ${d.delta}`)
              }
              if (rb.reverted.length > 5) showToast('info', `(+${rb.reverted.length - 5} más)`) 
            }
          } catch (e:any) {
            showToast('error', e?.response?.data?.detail || 'Error al hacer rollback')
          }
        }
      }
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
            <button className="btn-secondary btn-lg" onClick={() => setAuditOpen(true)} title="Ver auditoría de stock aplicada">Auditoría</button>
            {data?.status === 'BORRADOR' && (
              <button
                className="btn btn-lg"
                onClick={async () => {
                  setIavalOpen(true)
                  setIavalLoading(true)
                  setIavalError(null)
                  setIavalResult(null)
                  setIavalDownload(null)
                  try {
                    const res = await iavalPreview(pid)
                    setIavalResult(res)
                    const hasHeader = res?.diff && Object.keys(res.diff.header || {}).length > 0
                    const hasLines = res?.diff && Array.isArray(res.diff.lines) && res.diff.lines.some((ln: any) => ln && Object.keys(ln).length > 0)
                    if (!hasHeader && !hasLines) {
                      showToast('info', 'IA: No se detectaron diferencias para aplicar')
                    }
                  } catch (e: any) {
                    setIavalError(e?.response?.data?.detail || 'Error al ejecutar iAVaL')
                  } finally {
                    setIavalLoading(false)
                  }
                }}
                disabled={!Array.isArray((data as any)?.attachments) || ((data as any)?.attachments?.length || 0) === 0}
                title={!Array.isArray((data as any)?.attachments) || ((data as any)?.attachments?.length || 0) === 0 ? 'Necesita un PDF adjunto' : 'Validador de IA del remito'}
              >iAVaL</button>
            )}
            <button
              className="btn-primary btn-lg"
              onClick={doConfirm}
              disabled={data?.status === 'CONFIRMADA' || (lines?.length || 0) === 0 || (totals?.total || 0) === 0}
              title={(lines?.length || 0) === 0 ? 'No hay líneas importadas' : ((totals?.total || 0) === 0 ? 'Total de la compra es 0' : '')}
            >
              Confirmar
            </button>
            {data?.status === 'CONFIRMADA' && (
              <div className="dropdown" style={{ position: 'relative' }}>
                <button className="btn-secondary btn-lg" onClick={async () => {
                  try {
                    const prev = await resendPurchaseStock(pid, false, true)
                    if (!prev.applied_deltas || prev.applied_deltas.length === 0) {
                      showToast('info', 'Sin deltas de stock para re-aplicar')
                      return
                    }
                    if (confirm(`Se volverían a sumar ${prev.applied_deltas.reduce((a,b)=>a+(b.delta||0),0)} unidades en ${prev.applied_deltas.length} productos. ¿Aplicar?`)) {
                      const res = await resendPurchaseStock(pid, true, true)
                      showToast('success', 'Stock reenviado')
                      if (res.applied_deltas) {
                        for (const d of res.applied_deltas.slice(0, 5)) {
                          const name = d.product_title || `Prod ${d.product_id}`
                          showToast('info', `${name}: +${d.delta}`)
                        }
                        if (res.applied_deltas.length > 5) showToast('info', `(+${res.applied_deltas.length - 5} más)`) 
                      }
                    }
                  } catch (e:any) {
                    showToast('error', e?.response?.data?.detail || 'Error en reenviar stock')
                  }
                }}>Reenviar a Stock</button>
              </div>
            )}
            <button className="btn-secondary btn-lg" onClick={() => exportUnmatched(pid, 'csv')} disabled={!unmatched}>Exportar SIN_VINCULAR</button>
            <Link to={PATHS.purchases} className="btn-secondary btn-lg" style={{ textDecoration: 'none' }}>Cerrar</Link>
          </div>
        </div>
        <div className="text-sm" style={{ opacity: 0.8, marginBottom: 8 }}>
          Consejo amistoso: si el remito no coincide, no lo inventes, rey.
          {data?.meta?.last_resend_stock_at && (
            <span style={{ marginLeft: 16, fontWeight: 500 }}>Último reenvío stock: {new Date(data.meta.last_resend_stock_at).toLocaleString('es-AR')}</span>
          )}
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
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" onClick={addLine}>Agregar línea (Enter)</button>
            {Array.from(selectedLines).some(i => !lines[i]?.product_id && !lines[i]?.supplier_item_id) && (
              <button className="btn-dark" onClick={() => setBulkCreateOpen(true)}>Crear productos seleccionados</button>
            )}
          </div>
        </div>
        <table className="table w-full">
          <thead>
            <tr>
              <th></th>
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
            {lines.map((ln, idx) => {
              const isNew = (ln as any)._createdNow
              return (
              <tr key={idx} className={selectedLines.has(idx) ? 'row-selected' : ''}>
                <td className="text-center">
                  <input type="checkbox" checked={selectedLines.has(idx)} onChange={() => setSelectedLines(prev => { const n = new Set(prev); if (n.has(idx)) n.delete(idx); else n.add(idx); return n })} />
                </td>
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
                <td style={{ position: 'relative' }}>
                  <input className="input w-full" value={ln.title || ''} onChange={(e) => setLines(prev => prev.map((p, i) => i === idx ? { ...p, title: e.target.value } : p))} />
                  {isNew && <span style={{ position: 'absolute', top: 4, right: 6, background: '#2563eb', color: '#fff', fontSize: 10, padding: '2px 4px', borderRadius: 4 }}>NUEVO</span>}
                </td>
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
                <td style={{ display: 'flex', gap: 4 }}>
                  {!ln.product_id && !ln.supplier_item_id && (
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        setCreateForLine(idx)
                        setNewProdName(ln.title || '')
                        setNewProdStock(String(ln.qty || 0))
                      }}
                      title="Crear producto y vincular"
                    >Crear producto</button>
                  )}
                  <button className="btn-secondary" onClick={() => setLines(prev => prev.filter((_, i) => i !== idx))}>Borrar</button>
                </td>
              </tr>
              )
            })}
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
      {createForLine !== null && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 90, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="panel" style={{ padding: 20, width: 480, maxWidth: '95%' }}>
            <h3 style={{ marginTop: 0 }}>Crear producto para línea #{createForLine + 1}</h3>
            <label className="label">Nombre</label>
            <input className="input w-full" value={newProdName} onChange={e => setNewProdName(e.target.value)} />
            <label className="label" style={{ marginTop: 8 }}>Stock inicial (usar 0 si se crea desde la compra)</label>
            <input className="input" type="number" value={newProdStock} onChange={e => setNewProdStock(e.target.value)} />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button className="btn" onClick={() => setCreateForLine(null)} disabled={creating}>Cancelar</button>
              <button
                className="btn-dark"
                disabled={creating || !newProdName.trim()}
                onClick={async () => {
                  if (!newProdName.trim()) return
                  setCreating(true)
                  try {
                    // Para evitar doble carga de stock, forzamos 0 cuando el producto
                    // se crea desde una compra (la confirmación aplicará la cantidad de la línea).
                    const stockNum = 0
                    const prod = await createProduct({
                      title: newProdName.trim(),
                      initial_stock: stockNum,
                      supplier_id: data?.supplier_id || null,
                      supplier_sku: lines[createForLine!]?.supplier_sku || null,
                      purchase_id: pid,
                      purchase_line_index: createForLine!,
                    })
                    setLines(prev => prev.map((ln, i) => i === createForLine ? ({ ...(ln as any), product_id: prod.id, state: 'OK', _createdNow: true } as any) : ln))
                    showToast('success', 'Producto creado y vinculado')
                    setCreateForLine(null)
                  } catch (e: any) {
                    showToast('error', e?.message || 'No se pudo crear')
                  } finally { setCreating(false) }
                }}
              >{creating ? 'Creando...' : 'Crear y vincular'}</button>
            </div>
          </div>
        </div>
      )}
      {iavalOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 92, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="panel" style={{ padding: 20, width: 720, maxWidth: '96%', maxHeight: '90%', overflow: 'auto' }}>
            <h3 style={{ marginTop: 0 }}>iAVaL — Validador de IA del remito</h3>
            {iavalLoading && (<div>Cargando análisis...</div>)}
            {iavalError && (<div className="text-danger" style={{ marginBottom: 8 }}>{iavalError}</div>)}
            {!iavalLoading && iavalResult && (
              <>
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>Confianza: {Math.round((iavalResult.confidence || 0) * 100)}%</div>
                    {Array.isArray(iavalResult.comments) && iavalResult.comments.length > 0 && (
                      <ul style={{ marginTop: 6 }}>
                        {iavalResult.comments.map((c: string, i: number) => (<li key={i} style={{ fontSize: 13, opacity: .9 }}>{c}</li>))}
                      </ul>
                    )}
                  </div>
                  <div style={{ opacity: .8, fontSize: 12 }}>Solo en BORRADOR · Revisa y confirmá para aplicar</div>
                </div>
                <div style={{ marginTop: 12 }}>
                  <h4 style={{ margin: '8px 0' }}>Cambios de encabezado</h4>
                  {(() => {
                    const h = iavalResult?.diff?.header || {}
                    const keys = Object.keys(h)
                    if (keys.length === 0) return <div style={{ opacity: .8 }}>Sin cambios propuestos</div>
                    return (
                      <table className="table w-full">
                        <thead>
                          <tr><th>Campo</th><th>Actual</th><th>Propuesto</th></tr>
                        </thead>
                        <tbody>
                          {keys.map(k => (
                            <tr key={k}>
                              <td style={{ fontWeight: 600 }}>{k}</td>
                              <td>{String((data as any)?.[k] ?? '')}</td>
                              <td>{String((iavalResult?.proposal?.header || {})[k] ?? '')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  })()}
                </div>
                <div style={{ marginTop: 12 }}>
                  <h4 style={{ margin: '8px 0' }}>Cambios por línea</h4>
                  {(() => {
                    const diffs: any[] = iavalResult?.diff?.lines || []
                    const anyDiff = diffs.some((d) => d && Object.keys(d).length > 0)
                    if (!anyDiff) return <div style={{ opacity: .8 }}>Sin cambios propuestos</div>
                    return (
                      <table className="table w-full">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Campo</th>
                            <th>Actual</th>
                            <th>Propuesto</th>
                          </tr>
                        </thead>
                        <tbody>
                          {diffs.map((d, idx) => (
                            d && Object.keys(d).length > 0 ? (
                              Object.keys(d).map((k, j) => (
                                <tr key={`${idx}-${k}`}>
                                  <td>{idx + 1}</td>
                                  <td style={{ fontWeight: 600 }}>{k}</td>
                                  <td>{String((lines[idx] as any)?.[k] ?? '')}</td>
                                  <td>{String((((iavalResult?.proposal?.lines || [])[idx] || {}) as any)[k] ?? '')}</td>
                                </tr>
                              ))
                            ) : null
                          ))}
                        </tbody>
                      </table>
                    )
                  })()}
                </div>
                {iavalDownload && (iavalDownload.url_json || iavalDownload.url_csv) && (
                  <div className="row" style={{ gap: 12, marginTop: 10 }}>
                    {iavalDownload.url_json && (
                      <a className="btn" href={iavalDownload.url_json} target="_blank" rel="noreferrer">Descargar log JSON</a>
                    )}
                    {iavalDownload.url_csv && (
                      <a className="btn" href={iavalDownload.url_csv} target="_blank" rel="noreferrer">Descargar log CSV</a>
                    )}
                  </div>
                )}
              </>
            )}
            <div className="row" style={{ gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <div style={{ marginRight: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                <input id="emitLog" type="checkbox" checked={iavalEmitLog} onChange={(e) => setIavalEmitLog(e.target.checked)} />
                <label htmlFor="emitLog" className="text-sm">Enviar logs de cambios</label>
              </div>
              <button className="btn" onClick={() => setIavalOpen(false)} disabled={iavalLoading}>Cerrar</button>
              <button
                className="btn-dark"
                disabled={iavalLoading || !iavalResult || !data || data.status !== 'BORRADOR'}
                onClick={async () => {
                  if (!iavalResult) return
                  try {
                    setIavalLoading(true)
                    const res = await iavalApply(pid, iavalResult.proposal, iavalEmitLog)
                    showToast('success', 'Cambios aplicados')
                    if (res?.log?.filename) {
                      showToast('info', `Log generado: ${res.log.filename}`)
                      setIavalDownload({ url_json: res.log.url_json, url_csv: res.log.url_csv })
                    } else {
                      setIavalDownload(null)
                    }
                    // Refrescar compra en pantalla sin cerrar el modal (para permitir descarga)
                    const p = await getPurchase(pid)
                    setData(p)
                    setLines(p.lines || [])
                  } catch (e: any) {
                    showToast('error', e?.response?.data?.detail || 'No se pudo aplicar iAVaL')
                  } finally {
                    setIavalLoading(false)
                  }
                }}
              >Sí, aplicar cambios</button>
            </div>
          </div>
        </div>
      )}
      {bulkCreateOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 95, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="panel" style={{ padding: 20, width: 560, maxWidth: '96%' }}>
            <h3 style={{ marginTop: 0 }}>Crear productos seleccionados</h3>
            <p className="text-sm" style={{ opacity: .85 }}>Se crearán productos para cada línea seleccionada SIN_VINCULAR. Podés definir un prefijo opcional que se antepone al título existente.</p>
            <input className="input w-full" value={bulkPrefix} onChange={e => setBulkPrefix(e.target.value)} placeholder="Ej: SP - " />
            <div className="row" style={{ gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
              <button className="btn" onClick={() => setBulkCreateOpen(false)} disabled={bulkCreating}>Cancelar</button>
              <button className="btn-dark" disabled={bulkCreating} onClick={async () => {
                const targets = Array.from(selectedLines).filter(i => !lines[i]?.product_id && !lines[i]?.supplier_item_id)
                if (!targets.length) { showToast('error', 'No hay líneas elegibles'); return }
                setBulkCreating(true)
                let ok = 0
                try {
                  const newLines = [...lines]
                  for (const idx of targets) {
                    const ln = newLines[idx]
                    try {
                      const prod = await createProduct({
                        title: (bulkPrefix + (ln.title || '')) || 'Producto',
                        // Evitar doble suma: siempre crear con stock 0, confirm sumará la cantidad.
                        initial_stock: 0,
                        supplier_id: data?.supplier_id || null,
                        supplier_sku: ln.supplier_sku || null,
                        purchase_id: pid,
                        purchase_line_index: idx,
                      })
                      newLines[idx] = { ...(ln as any), product_id: prod.id, state: 'OK', _createdNow: true } as any
                      ok++
                    } catch (e:any) {
                      console.error('Error creando producto en lote', e)
                    }
                  }
                  setLines(newLines)
                  showToast('success', `Creados ${ok}/${targets.length}`)
                  setBulkCreateOpen(false)
                } finally { setBulkCreating(false) }
              }}>{bulkCreating ? 'Creando...' : 'Crear todos'}</button>
            </div>
          </div>
        </div>
      )}
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
      {auditOpen && (
        <div className="panel p-4" style={{ position: 'fixed', right: 16, top: 80, width: 420, maxHeight: '70vh', overflowY: 'auto', zIndex: 30 }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 700 }}>Auditoría de Stock</div>
            <button className="btn-secondary" onClick={() => setAuditOpen(false)}>Cerrar</button>
          </div>
          {appliedDeltas.length === 0 ? (
            <div style={{ opacity: .8, marginTop: 8 }}>Sin deltas registrados en logs de esta compra.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {appliedDeltas.map((grp, idx) => (
                <div key={idx} className="card" style={{ padding: 8, borderRadius: 8 }}>
                  <div style={{ fontSize: 12, opacity: .8 }}>Evento: {grp.when ? new Date(grp.when).toLocaleString('es-AR') : 's/d'}</div>
                  <ul style={{ margin: '6px 0 0 16px' }}>
                    {grp.list.map((d, i) => (
                      <li key={i}>
                        {(d.product_title || `Prod ${d.product_id || ''}`)}
                        {d.product_id ? ` (ID ${d.product_id})` : ''}
                        {typeof d.delta !== 'undefined' ? `: +${d.delta}` : ''}
                        {typeof d.new !== 'undefined' && typeof d.old !== 'undefined' ? ` (de ${d.old} → ${d.new})` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}
